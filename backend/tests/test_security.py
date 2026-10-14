"""Login, sessions, and recovery refuse the cases the panel must not accept."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from atlas.security.accounts import (
    AccessError,
    actor_from_api_token,
    actor_from_session,
    begin_enrollment,
    begin_member,
    confirm_enrollment,
    issue_api_token,
    issue_bootstrap,
    login,
    reset_owner_totp,
)
from atlas.security.tokens import verify_totp
from atlas.storage.db import Store

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_a_rejected_code_and_a_second_owner_are_refused(tmp_path: Path) -> None:
    assert verify_totp("MFRGGZDFMZTWQ2LK", "abcd") is False
    store = Store.open(tmp_path / "atlas.db")
    try:
        token = issue_bootstrap(store.conn, now=NOW, ttl_seconds=600)
        enrollment = begin_enrollment(
            store.conn,
            token=token,
            username="owner",
            password="a-long-password",
            now=NOW,
            ttl_seconds=600,
        )
        code = pyotp.TOTP(enrollment.totp_secret).now()
        actor = confirm_enrollment(store.conn, token=enrollment.token, code=code, now=NOW)
        with pytest.raises(AccessError, match="owner"):
            issue_bootstrap(store.conn, now=NOW, ttl_seconds=600)
        with pytest.raises(AccessError, match="operator or a viewer"):
            begin_member(
                store.conn,
                username="guest",
                password="a-long-password",
                role="owner",
                now=NOW,
                ttl_seconds=600,
            )
        waits: list[float] = []
        with pytest.raises(AccessError):
            login(
                store.conn,
                username="owner",
                password="wrong-password",
                code=code,
                now=NOW,
                sleeper=waits.append,
            )
        assert waits
        store.conn.execute(
            "UPDATE accounts SET locked_until = ? WHERE username = 'owner'",
            ((NOW + timedelta(minutes=15)).isoformat(),),
        )
        store.conn.commit()
        with pytest.raises(AccessError):
            login(
                store.conn,
                username="owner",
                password="a-long-password",
                code=code,
                now=NOW,
                sleeper=waits.append,
            )
        expired = actor_from_session(
            store.conn, actor.raw_session or "", now=NOW, idle_seconds=60, touch=False
        )
        assert expired is not None
        store.conn.execute(
            "UPDATE sessions SET absolute_expires_at = ? WHERE id = ?",
            ((NOW - timedelta(seconds=1)).isoformat(), actor.session_id),
        )
        store.conn.commit()
        assert (
            actor_from_session(
                store.conn, actor.raw_session or "", now=NOW, idle_seconds=60, touch=True
            )
            is None
        )
        raw = issue_api_token(
            store.conn,
            account_id=actor.account_id,
            name="ci",
            scope="viewer",
            now=NOW,
            ttl_seconds=60,
        )
        assert actor_from_api_token(store.conn, raw, now=NOW) is not None
        assert actor_from_api_token(store.conn, raw, now=NOW + timedelta(seconds=120)) is None
        assert actor_from_api_token(store.conn, "missing", now=NOW) is None
        with pytest.raises(AccessError, match="scope"):
            issue_api_token(
                store.conn,
                account_id=actor.account_id,
                name="bad",
                scope="root",
                now=NOW,
                ttl_seconds=None,
            )
        uri = reset_owner_totp(store.conn, "owner")
        assert uri.startswith("otpauth://")
        with pytest.raises(AccessError):
            reset_owner_totp(store.conn, "missing")
    finally:
        store.close()
