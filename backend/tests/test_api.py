"""The panel API requires a password and a second factor, and it hides secrets."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from atlas.api.app import create_app
from atlas.api.settings import Settings, refuse_public_bind
from atlas.application.scan import run_scan
from atlas.collectors.view import open_view
from atlas.metrics.sampler import HostSample, MemorySample
from atlas.metrics.series import query_series, write_sample
from atlas.security.accounts import issue_bootstrap
from atlas.storage.db import Store

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"
CANARY = "ATLAS_CANARY_7f3a9c"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_owner_can_read_and_a_viewer_cannot_scan(tmp_path: Path) -> None:
    root = tmp_path / "host"
    shutil.copytree(FIXTURE, root, symlinks=True)
    readme = root / "opt" / "shop" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + f"\ntoken={CANARY}\n", encoding="utf-8")
    (root / "opt" / "shop" / "app.log").write_text(f"started\ntoken={CANARY}\n", encoding="utf-8")
    store = Store.open(tmp_path / "atlas.db")
    run_scan(open_view(root), store, "oneshot")
    delays: list[float] = []
    app = create_app(
        store,
        Settings(root, allowed_hosts=("testserver",)),
        sleeper=delays.append,
        clock=lambda: NOW,
    )
    client = TestClient(app)
    anonymous = client.get("/api/v1/host")
    assert anonymous.status_code == 401
    assert anonymous.headers["content-type"].startswith("application/problem+json")

    secret = _enroll(client, store, "owner", "a-long-password")
    denied = client.post("/api/v1/scans")
    assert denied.status_code == 403
    assert denied.json()["code"] == "auth.csrf"
    csrf = client.cookies["atlas_csrf"]
    scanned = client.post("/api/v1/scans", headers={"x-csrf-token": csrf})
    assert scanned.status_code == 200

    host = client.get("/api/v1/host")
    assert host.status_code == 200
    assert host.headers["etag"]
    assert CANARY not in host.text
    again = client.get("/api/v1/host", headers={"if-none-match": host.headers["etag"]})
    assert again.status_code == 304
    assert "frame-ancestors 'none'" in host.headers["content-security-policy"]

    users = client.get("/api/v1/users").json()["items"]
    assert any(item["key"] == "deploy" for item in users)
    deploy = client.get("/api/v1/users/deploy")
    assert deploy.status_code == 200
    deploy_body = deploy.json()
    assert deploy_body["entity"]["key"] == "deploy"
    assert any(row["predicate"] == "user.shell" for row in deploy_body["facts"])
    unit = client.get("/api/v1/services/nginx.service")
    assert unit.status_code == 200
    assert any(row["predicate"] == "unit.active" for row in unit.json()["facts"])

    projects = client.get("/api/v1/projects").json()["items"]
    shop = next(item for item in projects if item["payload"]["root_path"] == "/opt/shop")
    card = client.get(f"/api/v1/projects/{shop['key']}")
    assert any(row["value"] == "Django" for row in card.json()["facts"])
    fact_id = next(row["id"] for row in card.json()["facts"] if row["value"] == "Django")
    proof = client.get(f"/api/v1/facts/{fact_id}/evidence")
    assert proof.status_code == 200
    assert proof.json()["evidence"]
    hits = client.get("/api/v1/search", params={"q": "storefront"})
    assert hits.json()["hits"]
    assert CANARY not in hits.text
    log = client.get("/api/v1/logs", params={"source": "opt/shop/app.log"})
    assert "started" in log.text
    assert CANARY not in log.text
    blocked = client.get("/api/v1/logs", params={"source": "../secrets"})
    assert blocked.status_code == 400

    member = client.post(
        "/api/v1/accounts",
        headers={"x-csrf-token": csrf},
        json={"username": "reader", "password": "another-password", "role": "viewer"},
    )
    assert member.status_code == 200
    viewer = TestClient(app)
    viewer_secret = _confirm(
        viewer, member.json()["enrollment_token"], member.json()["otpauth_uri"]
    )
    forbidden = viewer.post("/api/v1/scans", headers={"x-csrf-token": viewer.cookies["atlas_csrf"]})
    assert forbidden.status_code == 403
    assert viewer.get("/api/v1/services").status_code == 200
    assert viewer.get("/api/v1/openapi.json").status_code == 403
    assert client.get("/api/v1/openapi.json").status_code == 200

    bad_password = client.post(
        "/api/v1/auth/login",
        json={
            "username": "owner",
            "password": "wrong-password-1",
            "code": pyotp.TOTP(secret).now(),
        },
    )
    bad_code = client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "a-long-password", "code": "000000"},
    )
    assert bad_password.status_code == 401
    assert bad_password.json() == bad_code.json()
    assert delays

    token = client.post(
        "/api/v1/tokens",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"name": "export", "scope": "viewer"},
    )
    outsider = TestClient(app)
    exported = outsider.get(
        "/api/v1/export",
        params={"format": "json"},
        headers={"authorization": f"Bearer {token.json()['token']}"},
    )
    assert exported.status_code == 200
    assert CANARY not in exported.text
    denied_token = outsider.get(
        "/api/v1/scans",
        headers={"authorization": f"Bearer {token.json()['token']}"},
    )
    assert denied_token.status_code == 403

    sample = HostSample(
        1_700_000_000, None, (), (0.2, 0.1, 0.0), MemorySample(100, 40, 0, 0), (), (), "test"
    )
    write_sample(store.conn, sample)
    points = query_series(store.conn, "host.load.1", 1_700_000_000, 1_700_000_000, 1)
    assert points[0]["value"] == 0.2
    queried = client.get(
        "/api/v1/metrics/query",
        params={"series": "host.load.1", "start": 1, "end": 2_000_000_000, "step": 60},
    )
    assert queried.json()["points"]

    with client.websocket_connect("/api/v1/stream") as socket:
        socket.send_json({"subscribe": "logs.follow", "source": "opt/shop/app.log"})
        message = socket.receive_json()
    assert CANARY not in str(message)
    try:
        with client.websocket_connect(
            "/api/v1/stream", headers={"origin": "https://evil.example"}
        ) as socket:
            socket.receive_json()
        raise AssertionError("a foreign origin must not open the stream")
    except WebSocketDisconnect:
        pass
    _ = viewer_secret
    store.close()


def test_live_sessions_read_who_without_a_scan(tmp_path: Path, monkeypatch) -> None:
    from atlas.collectors.view import CommandResult

    store = Store.open(tmp_path / "atlas.db")
    app = create_app(
        store,
        Settings(tmp_path, allowed_hosts=("testserver",)),
        sleeper=lambda _seconds: None,
        clock=lambda: NOW,
    )
    client = TestClient(app)
    _enroll(client, store, "owner", "a-long-password")

    def scripted(self, argv, timeout=8.0):
        del self, timeout
        assert argv == ["who"]
        return CommandResult(tuple(argv), 0, "root pts/9 2026-10-22 (203.0.113.8)\n", "")

    monkeypatch.setattr("atlas.collectors.view.SubprocessRunner.run", scripted)
    body = client.get("/api/v1/sessions/live")
    assert body.status_code == 200
    assert body.json() == {"ok": True, "text": "root pts/9 2026-10-22 (203.0.113.8)\n"}
    assert store.latest_scan_id() is None
    store.close()


def test_public_bind_is_refused_without_tls() -> None:
    try:
        refuse_public_bind("0.0.0.0", tls=False, allowed_ips=())
    except SystemExit as exc:
        assert "TLS" in str(exc)
    else:
        raise AssertionError("expected the bind to be refused")


def test_bootstrap_expires(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    token = issue_bootstrap(store.conn, now=NOW, ttl_seconds=60)
    app = create_app(
        store,
        Settings(tmp_path, allowed_hosts=("testserver",)),
        sleeper=lambda _seconds: None,
        clock=lambda: NOW + timedelta(hours=1),
    )
    response = TestClient(app).post(
        "/api/v1/auth/bootstrap",
        json={"token": token, "username": "owner", "password": "a-long-password"},
    )
    assert response.status_code == 401
    store.close()


def _enroll(client: TestClient, store: Store, username: str, password: str) -> str:
    token = issue_bootstrap(store.conn, now=NOW, ttl_seconds=600)
    started = client.post(
        "/api/v1/auth/bootstrap",
        json={"token": token, "username": username, "password": password},
    )
    assert started.status_code == 200
    return _confirm(client, started.json()["enrollment_token"], started.json()["otpauth_uri"])


def _confirm(client: TestClient, token: str, uri: str) -> str:
    secret = uri.split("secret=")[1].split("&")[0]
    confirmed = client.post(
        "/api/v1/auth/enroll", json={"token": token, "code": pyotp.TOTP(secret).now()}
    )
    assert confirmed.status_code == 200
    return secret
