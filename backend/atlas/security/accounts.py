"""Accounts, one-time enrollment, sessions, and API tokens.

Login failures share one error. The database records the attempt and the
caller waits, but the response does not say which of the three checks failed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from atlas.security.passwords import hash_password, verify_password
from atlas.security.tokens import (
    hash_token,
    new_token,
    new_totp_secret,
    provisioning_uri,
    verify_totp,
)

_REJECTED = "The username, password, or second factor was not accepted."
_LOCK_AFTER = 8
_LOCK_MINUTES = 15


class AccessError(Exception):
    """A credential or enrollment check failed with a client-facing message."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class Actor:
    """The account behind a request."""

    account_id: int
    username: str
    role: str
    via: str
    session_id: int | None
    csrf_token: str | None
    raw_session: str | None


@dataclass(frozen=True, slots=True)
class Enrollment:
    """A password that is not an account until the TOTP code is confirmed."""

    token: str
    username: str
    role: str
    totp_secret: str


def issue_bootstrap(conn: sqlite3.Connection, *, now: datetime, ttl_seconds: int) -> str:
    """Create the one-time install token. Fails once an owner already exists."""
    existing = conn.execute("SELECT id FROM accounts WHERE role = 'owner' LIMIT 1").fetchone()
    if existing is not None:
        raise AccessError("auth.enrolled", "An owner account already exists.")
    token = new_token()
    expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
    conn.execute(
        "INSERT INTO bootstrap_tokens (token_hash, expires_at) VALUES (?, ?)",
        (hash_token(token), expires),
    )
    conn.commit()
    return token


def begin_enrollment(
    conn: sqlite3.Connection,
    *,
    token: str,
    username: str,
    password: str,
    now: datetime,
    ttl_seconds: int,
) -> Enrollment:
    """Check the install token and remember a pending owner until TOTP succeeds."""
    _require_password(username, password)
    row = _bootstrap(conn, token, now)
    if row is None:
        raise AccessError("auth.rejected", _REJECTED)
    if conn.execute("SELECT id FROM accounts WHERE role = 'owner' LIMIT 1").fetchone():
        raise AccessError("auth.enrolled", "An owner account already exists.")
    return _store_enrollment(
        conn,
        token=token,
        username=username,
        password=password,
        role="owner",
        now=now,
        ttl_seconds=ttl_seconds,
    )


def begin_member(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    role: str,
    now: datetime,
    ttl_seconds: int,
) -> Enrollment:
    """Start enrollment for an account the owner is creating."""
    if role not in {"operator", "viewer"}:
        raise AccessError("auth.role", "A new account can be an operator or a viewer.")
    _require_password(username, password)
    if conn.execute("SELECT id FROM accounts WHERE username = ?", (username,)).fetchone():
        raise AccessError("auth.username", "That username is already in use.")
    return _store_enrollment(
        conn,
        token=new_token(),
        username=username,
        password=password,
        role=role,
        now=now,
        ttl_seconds=ttl_seconds,
    )


def confirm_enrollment(conn: sqlite3.Connection, *, token: str, code: str, now: datetime) -> Actor:
    """Turn a pending enrollment into an account after the TOTP code matches."""
    row = conn.execute(
        "SELECT username, password_hash, totp_secret, role, expires_at "
        "FROM enrollments WHERE token_hash = ?",
        (hash_token(token),),
    ).fetchone()
    if row is None or _expired(str(row["expires_at"]), now):
        raise AccessError("auth.rejected", _REJECTED)
    if not verify_totp(str(row["totp_secret"]), code):
        raise AccessError("auth.rejected", _REJECTED)
    if conn.execute("SELECT id FROM accounts WHERE username = ?", (row["username"],)).fetchone():
        raise AccessError("auth.username", "That username is already in use.")
    cursor = conn.execute(
        "INSERT INTO accounts (username, password_hash, totp_secret, role, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (row["username"], row["password_hash"], row["totp_secret"], row["role"], now.isoformat()),
    )
    account_id = int(cursor.lastrowid or 0)
    conn.execute("DELETE FROM enrollments WHERE token_hash = ?", (hash_token(token),))
    conn.execute(
        "UPDATE bootstrap_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
        (now.isoformat(), hash_token(token)),
    )
    conn.commit()
    return _open_session(conn, account_id, str(row["username"]), str(row["role"]), now)


def login(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    code: str,
    now: datetime,
    sleeper: Callable[[float], None],
) -> Actor:
    """Open a session. Every failure looks the same and waits a little longer."""
    row = conn.execute(
        "SELECT id, username, password_hash, totp_secret, role, failed_attempts, locked_until "
        "FROM accounts WHERE username = ?",
        (username,),
    ).fetchone()
    attempts = int(row["failed_attempts"]) if row is not None else 1
    if row is not None and _locked(row["locked_until"], now):
        sleeper(_delay(attempts))
        raise AccessError("auth.rejected", _REJECTED)
    password_ok = verify_password(password, str(row["password_hash"]) if row else None)
    totp_ok = bool(row) and password_ok and verify_totp(str(row["totp_secret"]), code)
    if row is None or not password_ok or not totp_ok:
        if row is not None:
            _record_failure(conn, int(row["id"]), attempts, now)
        sleeper(_delay(attempts))
        raise AccessError("auth.rejected", _REJECTED)
    conn.execute(
        "UPDATE accounts SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (int(row["id"]),),
    )
    conn.commit()
    return _open_session(conn, int(row["id"]), str(row["username"]), str(row["role"]), now)


def actor_from_session(
    conn: sqlite3.Connection, raw_session: str, *, now: datetime, idle_seconds: int, touch: bool
) -> Actor | None:
    """Resolve a session cookie. Expired sessions are removed."""
    row = conn.execute(
        "SELECT s.id, s.account_id, s.csrf_token, s.absolute_expires_at, s.idle_expires_at, "
        "a.username, a.role FROM sessions s JOIN accounts a ON a.id = s.account_id "
        "WHERE s.token_hash = ?",
        (hash_token(raw_session),),
    ).fetchone()
    if row is None:
        return None
    if _expired(str(row["absolute_expires_at"]), now) or _expired(str(row["idle_expires_at"]), now):
        conn.execute("DELETE FROM sessions WHERE id = ?", (int(row["id"]),))
        conn.commit()
        return None
    if touch:
        idle = (now + timedelta(seconds=idle_seconds)).isoformat()
        conn.execute("UPDATE sessions SET idle_expires_at = ? WHERE id = ?", (idle, int(row["id"])))
        conn.commit()
    return Actor(
        int(row["account_id"]),
        str(row["username"]),
        str(row["role"]),
        "session",
        int(row["id"]),
        str(row["csrf_token"]),
        raw_session,
    )


def actor_from_api_token(
    conn: sqlite3.Connection, raw_token: str, *, now: datetime
) -> Actor | None:
    """Resolve a bearer token. The scope becomes the actor role for that request."""
    row = conn.execute(
        "SELECT t.account_id, t.scope, t.expires_at, a.username FROM api_tokens t "
        "JOIN accounts a ON a.id = t.account_id WHERE t.token_hash = ?",
        (hash_token(raw_token),),
    ).fetchone()
    if row is None:
        return None
    expires = row["expires_at"]
    if expires is not None and _expired(str(expires), now):
        return None
    return Actor(
        int(row["account_id"]), str(row["username"]), str(row["scope"]), "token", None, None, None
    )


def issue_api_token(
    conn: sqlite3.Connection,
    *,
    account_id: int,
    name: str,
    scope: str,
    now: datetime,
    ttl_seconds: int | None,
) -> str:
    """Create an API token and return the raw value once."""
    if scope not in {"owner", "operator", "viewer"}:
        raise AccessError("auth.scope", "The token scope is not one of the known roles.")
    raw = new_token()
    expires = None if ttl_seconds is None else (now + timedelta(seconds=ttl_seconds)).isoformat()
    conn.execute(
        "INSERT INTO api_tokens (account_id, name, token_hash, scope, expires_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, name, hash_token(raw), scope, expires, now.isoformat()),
    )
    conn.commit()
    return raw


def reset_owner_totp(conn: sqlite3.Connection, username: str) -> str:
    """Replace the owner's TOTP secret and return the new provisioning URI.

    This is a local recovery command. It does not accept a request from the panel.
    """
    row = conn.execute(
        "SELECT role FROM accounts WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None or row["role"] != "owner":
        raise AccessError("auth.rejected", "That owner account is not in this database.")
    secret = new_totp_secret()
    conn.execute("UPDATE accounts SET totp_secret = ? WHERE username = ?", (secret, username))
    conn.commit()
    return provisioning_uri(secret, username)


def _store_enrollment(
    conn: sqlite3.Connection,
    *,
    token: str,
    username: str,
    password: str,
    role: str,
    now: datetime,
    ttl_seconds: int,
) -> Enrollment:
    secret = new_totp_secret()
    expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
    conn.execute("DELETE FROM enrollments WHERE token_hash = ?", (hash_token(token),))
    conn.execute(
        "INSERT INTO enrollments (token_hash, username, password_hash, totp_secret, role, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (hash_token(token), username, hash_password(password), secret, role, expires),
    )
    conn.commit()
    return Enrollment(token, username, role, secret)


def _open_session(
    conn: sqlite3.Connection, account_id: int, username: str, role: str, now: datetime
) -> Actor:
    raw = new_token()
    csrf = new_token()
    absolute = (now + timedelta(hours=12)).isoformat()
    idle = (now + timedelta(minutes=30)).isoformat()
    cursor = conn.execute(
        "INSERT INTO sessions (account_id, token_hash, csrf_token, created_at, "
        "absolute_expires_at, idle_expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, hash_token(raw), csrf, now.isoformat(), absolute, idle),
    )
    conn.commit()
    return Actor(account_id, username, role, "session", int(cursor.lastrowid or 0), csrf, raw)


def _bootstrap(conn: sqlite3.Connection, token: str, now: datetime) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT id, expires_at, used_at FROM bootstrap_tokens WHERE token_hash = ?",
        (hash_token(token),),
    ).fetchone()
    if row is None or row["used_at"] is not None or _expired(str(row["expires_at"]), now):
        return None
    return cast(sqlite3.Row, row)


def _record_failure(
    conn: sqlite3.Connection, account_id: int, attempts: int, now: datetime
) -> None:
    failed = attempts + 1
    locked = (now + timedelta(minutes=_LOCK_MINUTES)).isoformat() if failed >= _LOCK_AFTER else None
    conn.execute(
        "UPDATE accounts SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (failed, locked, account_id),
    )
    conn.commit()


def _require_password(username: str, password: str) -> None:
    if len(username) < 2 or len(password) < 12 or password == username:
        raise AccessError(
            "auth.password", "Use a username and a password of at least 12 characters."
        )


def _expired(value: str, now: datetime) -> bool:
    return datetime.fromisoformat(value) <= now


def _locked(value: object, now: datetime) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return datetime.fromisoformat(value) > now


def _delay(attempts: int) -> float:
    step = min(max(attempts, 0), 4)
    return float(2**step)
