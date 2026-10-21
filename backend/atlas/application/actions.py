"""Decide whether a panel action may be sent to the helper.

Control stays off until ``atlas control enable``. The helper still checks the
whitelist on its own; this module adds the role, the typed confirmation, and
the second factor.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from atlas.application.audit import append_audit
from atlas.helper.protocol import ProtocolError, build_plan
from atlas.redact import mask_secrets
from atlas.security.tokens import verify_totp
from atlas.storage.db import Store

_OWNER_ONLY = ("journal.", "account.", "ssh.", "host.", "app.")


class ActionError(Exception):
    """The panel refused the action before the helper saw it."""

    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def control_enabled(store: Store) -> bool:
    """Return whether the owner has turned control on."""
    row = store.conn.execute("SELECT value FROM settings WHERE key = 'control'").fetchone()
    return row is not None and row["value"] == "on"


def set_control(store: Store, enabled: bool) -> None:
    """Turn control on or off. This is the local switch, not a panel button."""
    store.conn.execute(
        "INSERT INTO settings (key, value) VALUES ('control', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("on" if enabled else "off",),
    )
    store.conn.commit()


_BOOT_STATES = frozenset({"enabled", "static", "indirect", "generated", "alias"})
_SSH_UNITS = frozenset({"ssh.service", "sshd.service"})
_SSH_SOCKETS = ("ssh.socket", "sshd.socket")


def _socket_returns(row: dict[str, object]) -> bool:
    return row.get("unit.enabled") in _BOOT_STATES or row.get("unit.active") == "active"


def _starts_on_boot(name: str, enabled: object, by_name: dict[str, dict[str, object]]) -> bool:
    """A unit comes back when it, its socket, or its template parent is enabled."""
    if enabled in _BOOT_STATES:
        return True
    if name in _SSH_UNITS and any(
        _socket_returns(by_name.get(socket, {})) for socket in _SSH_SOCKETS
    ):
        return True
    if name.endswith(".service"):
        socket = f"{name[: -len('.service')]}.socket"
        if _socket_returns(by_name.get(socket, {})):
            return True
        if "@" in name:
            parent = f"{name.split('@', 1)[0]}.service"
            if by_name.get(parent, {}).get("unit.enabled") in _BOOT_STATES:
                return True
    return False


def restart_risks(store: Store) -> list[dict[str, str]]:
    """Services and containers that are running but will not come back on boot."""
    scan_id = store.latest_scan_id()
    if scan_id is None:
        return []
    found: list[dict[str, str]] = []
    services = list(store.entities(scan_id, "service"))
    by_name = {str(row["key"]): row["payload"] for row in services}
    for row in services:
        payload = row["payload"]
        active = payload.get("unit.active")
        enabled = payload.get("unit.enabled")
        if active == "active" and not _starts_on_boot(str(row["key"]), enabled, by_name):
            found.append({"kind": "service", "name": str(row["key"]), "enabled": str(enabled)})
    for row in store.entities(scan_id, "container"):
        payload = row["payload"]
        policy = payload.get("restart_policy")
        if policy in {None, "", "no"}:
            raw_name = payload.get("name")
            label = (
                raw_name.strip()
                if isinstance(raw_name, str) and raw_name.strip()
                else str(row["key"])
            )
            found.append({"kind": "container", "name": label, "enabled": str(policy)})
    return found


def request_action(
    store: Store,
    *,
    username: str,
    role: str,
    ip: str,
    op: str,
    params: dict[str, object],
    confirm: str,
    code: str,
    helper_socket: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Check the panel rules, call the helper, and append the audit row."""
    stamped = now or datetime.now(UTC)
    safe = _public_params(params)
    try:
        outcome = _attempt(
            store,
            username=username,
            role=role,
            op=op,
            params=params,
            confirm=confirm,
            code=code,
            helper_socket=helper_socket,
        )
    except ActionError as exc:
        append_audit(
            store.conn,
            actor=username,
            ip=ip,
            action=op,
            params=safe,
            result=exc.code,
            now=stamped,
        )
        raise
    if outcome.get("pending"):
        result = "pending"
    elif outcome.get("ok"):
        result = "ok"
    else:
        result = "failed"
    append_audit(
        store.conn,
        actor=username,
        ip=ip,
        action=op,
        params=safe,
        result=result,
        now=stamped,
    )
    return outcome


def _attempt(
    store: Store,
    *,
    username: str,
    role: str,
    op: str,
    params: dict[str, object],
    confirm: str,
    code: str,
    helper_socket: str,
) -> dict[str, object]:
    if op == "host.cancel":
        return _cancel(store, role, params, helper_socket)
    if not control_enabled(store):
        raise ActionError(403, "control.disabled", "Control is off. Enable it on the host first.")
    if role == "viewer" or (role != "owner" and op.startswith(_OWNER_ONLY)):
        raise ActionError(403, "auth.forbidden", "This action is outside the current role.")
    if role not in {"owner", "operator"}:
        raise ActionError(403, "auth.forbidden", "This action is outside the current role.")
    try:
        plan = build_plan(op, params)
    except ProtocolError as exc:
        raise ActionError(400, "action.rejected", exc.message) from exc
    if confirm != plan.confirm:
        raise ActionError(400, "action.confirm", "Type the name of the object to confirm.")
    if plan.op.startswith("host."):
        known = scanned_hostname(store)
        if known and plan.confirm != known:
            raise ActionError(400, "action.confirm", "Type the hostname of this machine.")
    if plan.risk in {"high", "critical"} and not _totp_ok(store, username, code):
        raise ActionError(401, "auth.rejected", "The second factor was not accepted.")
    if not helper_socket:
        raise ActionError(503, "helper.down", "The helper socket is not configured.")
    payload: dict[str, object] = {"op": op, "params": params}
    if op in {"host.reboot", "host.poweroff"}:
        payload["risks"] = restart_risks(store)
    try:
        answer = _call_helper(helper_socket, {"op": op, "params": params})
    except OSError as exc:
        raise ActionError(503, "helper.down", "The helper is not accepting requests.") from exc
    if isinstance(payload.get("risks"), list):
        answer["risks"] = payload["risks"]
    return answer


def scanned_hostname(store: Store) -> str:
    """Return the hostname from the latest scan, or an empty string."""
    scan_id = store.latest_scan_id()
    if scan_id is None:
        return ""
    for row in store.entities(scan_id, "os"):
        payload = row["payload"]
        host = payload.get("hostname") or payload.get("hostname_file")
        if isinstance(host, str) and host:
            return host
    return ""


def _cancel(
    store: Store, role: str, params: dict[str, object], helper_socket: str
) -> dict[str, object]:
    if not control_enabled(store):
        raise ActionError(403, "control.disabled", "Control is off. Enable it on the host first.")
    if role != "owner":
        raise ActionError(403, "auth.forbidden", "This action is outside the current role.")
    token = params.get("pending")
    if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{16}", token) is None:
        raise ActionError(400, "action.rejected", "A pending id is required.")
    if not helper_socket:
        raise ActionError(503, "helper.down", "The helper socket is not configured.")
    try:
        return _call_helper(helper_socket, {"op": "host.cancel", "pending": token})
    except OSError as exc:
        raise ActionError(503, "helper.down", "The helper is not accepting requests.") from exc


def _public_params(params: dict[str, object]) -> dict[str, object]:
    return {
        key: mask_secrets(value) if isinstance(value, str) else value
        for key, value in params.items()
    }


def _totp_ok(store: Store, username: str, code: str) -> bool:
    row = store.conn.execute(
        "SELECT totp_secret FROM accounts WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return False
    return verify_totp(str(row["totp_secret"]), code)


def _call_helper(path: str, request: dict[str, object]) -> dict[str, object]:
    from atlas.helper.client import call_helper

    return call_helper(path, request)
