"""Action log with a hash chain.

Each row stores the hash of the previous row. Changing or deleting a row
makes :func:`verify_chain` fail. The application only inserts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

GENESIS = "0" * 64


def append_audit(
    conn: sqlite3.Connection,
    *,
    actor: str,
    ip: str,
    action: str,
    params: dict[str, object],
    result: str,
    now: datetime | None = None,
) -> str:
    """Append one row and return its hash."""
    stamped = (now or datetime.now(UTC)).isoformat()
    previous = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = str(previous["hash"]) if previous is not None else GENESIS
    body = {
        "ts": stamped,
        "actor": actor,
        "ip": ip,
        "action": action,
        "params": params,
        "result": result,
        "prev_hash": prev_hash,
    }
    digest = hashlib.sha256(
        f"{prev_hash}\n{json.dumps(body, sort_keys=True, separators=(',', ':'))}".encode()
    ).hexdigest()
    conn.execute(
        "INSERT INTO audit_log (ts, actor, ip, action, params, result, prev_hash, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stamped,
            actor,
            ip,
            action,
            json.dumps(params, sort_keys=True),
            result,
            prev_hash,
            digest,
        ),
    )
    conn.commit()
    return digest


def list_audit(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    """Return the newest rows, still in chain order."""
    rows = conn.execute(
        "SELECT id, ts, actor, ip, action, params, result, prev_hash, hash "
        "FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    found = [dict(row) for row in rows]
    found.reverse()
    return found


def verify_chain(conn: sqlite3.Connection) -> bool:
    """Return whether every row still matches the previous hash."""
    rows = conn.execute(
        "SELECT ts, actor, ip, action, params, result, prev_hash, hash FROM audit_log ORDER BY id"
    ).fetchall()
    prev = GENESIS
    for row in rows:
        if row["prev_hash"] != prev:
            return False
        params = json.loads(row["params"])
        body = {
            "ts": row["ts"],
            "actor": row["actor"],
            "ip": row["ip"],
            "action": row["action"],
            "params": params,
            "result": row["result"],
            "prev_hash": row["prev_hash"],
        }
        digest = hashlib.sha256(
            f"{prev}\n{json.dumps(body, sort_keys=True, separators=(',', ':'))}".encode()
        ).hexdigest()
        if digest != row["hash"]:
            return False
        prev = str(row["hash"])
    return True
