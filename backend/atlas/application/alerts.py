"""Alert rules evaluated from the latest scan. Channels stay off until configured.

Nothing in this module opens a socket unless a channel row is enabled and a
transport is asked to deliver that one message.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from atlas.logging import get_logger, log_event
from atlas.redact import mask_secrets
from atlas.storage.db import Store

logger = get_logger("atlas.alerts")

DEFAULT_RULES = (
    ("new_port", "change"),
    ("new_user", "change"),
    ("new_ssh_key", "change"),
    ("unit_failed", "state"),
    ("container_down", "state"),
    ("memory_low", "threshold"),
    ("cert_expiring", "state"),
)
_KINDS = {"webhook": ("https://", "http://"), "telegram": ("",)}
COOLDOWN = timedelta(minutes=15)
Transport = Callable[[str, str, str], None]


class AlertError(Exception):
    """A channel was refused before it was stored."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def ensure_rules(conn: sqlite3.Connection) -> None:
    """Insert the built-in rules the first time alerts are used."""
    for name, kind in DEFAULT_RULES:
        conn.execute(
            "INSERT INTO alert_rules (name, kind, enabled) VALUES (?, ?, 1) "
            "ON CONFLICT(name) DO NOTHING",
            (name, kind),
        )
    conn.commit()


def save_channel(conn: sqlite3.Connection, kind: str, target: str, *, enabled: bool = False) -> int:
    """Store one delivery channel. It is off unless the caller enables it."""
    if kind not in _KINDS:
        raise AlertError("The channel must be webhook or telegram.")
    cleaned = target.strip()
    if kind == "webhook" and not cleaned.startswith(_KINDS["webhook"]):
        raise AlertError("A webhook target must be an http or https URL.")
    if not cleaned or "\n" in cleaned:
        raise AlertError("The channel target is empty.")
    cursor = conn.execute(
        "INSERT INTO alert_channels (kind, target, enabled) VALUES (?, ?, ?)",
        (kind, cleaned, 1 if enabled else 0),
    )
    conn.commit()
    log_event(logger, logging.INFO, "alert.channel_saved", kind=kind, enabled=enabled)
    return int(cursor.lastrowid or 0)


def list_channels(conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Return channels without their targets, so a token is not echoed back."""
    rows = conn.execute("SELECT id, kind, enabled FROM alert_channels ORDER BY id").fetchall()
    return [
        {"id": int(row["id"]), "kind": row["kind"], "enabled": bool(row["enabled"])} for row in rows
    ]


def list_events(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, object]]:
    """Return the newest alert events."""
    rows = conn.execute(
        "SELECT id, rule_name, subject, state, message, ts, delivered "
        "FROM alert_events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def evaluate(
    store: Store,
    *,
    now: datetime | None = None,
    transport: Transport | None = None,
    cooldown: timedelta = COOLDOWN,
) -> list[dict[str, object]]:
    """Open, resolve, and optionally deliver alerts for the latest scan."""
    stamped = now or datetime.now(UTC)
    ensure_rules(store.conn)
    findings = _findings(store, stamped)
    open_keys = _open_keys(store.conn)
    created: list[dict[str, object]] = []
    for rule, subject, message in findings:
        if (rule, subject) in open_keys:
            continue
        created.append(_record(store.conn, rule, subject, "firing", message, stamped))
    for rule, subject in open_keys:
        if any(item[0] == rule and item[1] == subject for item in findings):
            continue
        created.append(
            _record(store.conn, rule, subject, "resolved", f"{subject} recovered", stamped)
        )
    _deliver(store.conn, stamped, transport or _network_transport, cooldown)
    return created


def _findings(store: Store, now: datetime) -> list[tuple[str, str, str]]:
    scan_id = store.latest_scan_id()
    if scan_id is None:
        return []
    enabled = {
        row["name"] for row in store.conn.execute("SELECT name FROM alert_rules WHERE enabled = 1")
    }
    found: list[tuple[str, str, str]] = []
    for change in store.changes(scan_id):
        kind = str(change["entity_kind"])
        key = str(change["entity_key"])
        if change["change_kind"] != "added":
            continue
        rule = {"port": "new_port", "user": "new_user", "ssh_key": "new_ssh_key"}.get(kind)
        if rule is not None and rule in enabled:
            found.append((rule, key, f"new {kind} {key}"))
    if "unit_failed" in enabled:
        for row in store.entities(scan_id, "service"):
            if row["payload"].get("unit.active") == "failed":
                found.append(("unit_failed", str(row["key"]), f"{row['key']} is failed"))
    if "container_down" in enabled:
        for row in store.entities(scan_id, "container"):
            state = str(row["payload"].get("state") or "")
            if state in {"exited", "dead"}:
                found.append(("container_down", str(row["key"]), f"{row['key']} is {state}"))
    if "memory_low" in enabled and _memory_low(store.conn):
        found.append(("memory_low", "host", "available memory is below 10 percent"))
    if "cert_expiring" in enabled:
        horizon = now + timedelta(days=14)
        for row in store.entities(scan_id, "certificate"):
            raw = row["payload"].get("not_after")
            if not isinstance(raw, str):
                continue
            expiry = datetime.fromisoformat(raw)
            if expiry <= horizon:
                found.append(("cert_expiring", str(row["key"]), f"{row['key']} expires {raw}"))
    return found


def _memory_low(conn: sqlite3.Connection) -> bool:
    total = _latest(conn, "host.memory.total_bytes")
    available = _latest(conn, "host.memory.available_bytes")
    if total is None or available is None or total <= 0:
        return False
    return available / total < 0.10


def _latest(conn: sqlite3.Connection, series: str) -> float | None:
    row = conn.execute(
        "SELECT value FROM metric_points WHERE series = ? ORDER BY ts DESC LIMIT 1",
        (series,),
    ).fetchone()
    return None if row is None else float(row["value"])


def _open_keys(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT rule_name, subject, state FROM alert_events ORDER BY id").fetchall()
    state: dict[tuple[str, str], str] = {}
    for row in rows:
        state[(str(row["rule_name"]), str(row["subject"]))] = str(row["state"])
    return {key for key, value in state.items() if value == "firing"}


def _record(
    conn: sqlite3.Connection, rule: str, subject: str, state: str, message: str, now: datetime
) -> dict[str, object]:
    conn.execute(
        "INSERT INTO alert_events (rule_name, subject, state, message, ts, delivered) "
        "VALUES (?, ?, ?, ?, ?, 0)",
        (
            rule,
            subject,
            state,
            mask_secrets(message),
            now.isoformat(),
        ),
    )
    conn.commit()
    return {"rule": rule, "subject": subject, "state": state, "message": message}


def _deliver(
    conn: sqlite3.Connection, now: datetime, transport: Transport, cooldown: timedelta
) -> None:
    channels = conn.execute("SELECT kind, target FROM alert_channels WHERE enabled = 1").fetchall()
    if not channels:
        return
    cutoff = (now - cooldown).isoformat()
    pending = conn.execute(
        "SELECT id, rule_name, subject, message FROM alert_events WHERE delivered = 0 ORDER BY id"
    ).fetchall()
    for row in pending:
        recent = conn.execute(
            "SELECT id FROM alert_events WHERE rule_name = ? AND subject = ? "
            "AND delivered = 1 AND ts >= ? LIMIT 1",
            (row["rule_name"], row["subject"], cutoff),
        ).fetchone()
        if recent is not None:
            continue
        message = str(row["message"])
        for channel in channels:
            transport(str(channel["kind"]), str(channel["target"]), message)
        conn.execute("UPDATE alert_events SET delivered = 1 WHERE id = ?", (row["id"],))
        conn.commit()


def _network_transport(kind: str, target: str, message: str) -> None:
    if kind == "webhook":
        import httpx

        response = httpx.post(target, json={"text": message}, timeout=5.0)
        response.raise_for_status()
        return
    if kind == "telegram":
        import httpx

        token, _, chat = target.partition(" ")
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message},
            timeout=5.0,
        )
        response.raise_for_status()
        return
    raise AlertError("The channel kind is not supported.")
