"""Control stays off until the host switch is on, and the helper stays on a whitelist."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.api.settings import Settings
from atlas.application.actions import control_enabled, restart_risks
from atlas.application.audit import verify_chain
from atlas.application.scan import run_scan
from atlas.cli.main import main
from atlas.collectors.view import open_view
from atlas.helper.protocol import ProtocolError, build_plan
from atlas.helper.server import HelperServer
from atlas.helper.sshkeys import authorized_keys_path, change_key
from atlas.security.accounts import begin_member, issue_bootstrap
from atlas.storage.db import Store

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
PUBLIC = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAtlasPublicKeyExampleValue1234567890 owner"


def test_whitelist_refuses_a_protected_unit_and_a_shell_character() -> None:
    with pytest.raises(ProtocolError):
        build_plan("service.stop", {"unit": "nginx;reboot"})
    with pytest.raises(ProtocolError):
        build_plan("service.stop", {"unit": "sshd"})
    forced = build_plan("service.stop", {"unit": "sshd.service", "force": True})
    assert forced.argv == ("systemctl", "stop", "sshd.service")
    assert "sh" not in forced.argv
    with pytest.raises(ProtocolError):
        build_plan("account.lock", {"username": "root"})
    with pytest.raises(ProtocolError):
        build_plan("ssh.add", {"username": "deploy", "key": "-----BEGIN PRIVATE KEY-----\n"})
    reboot = build_plan("host.reboot", {"hostname": "web-1"})
    assert reboot.delay_seconds == 10
    assert reboot.argv == ("systemctl", "reboot")
    update = build_plan("app.update", {"version": "1.1.2"})
    assert update.risk == "high"
    assert update.confirm == "1.1.2"
    assert update.argv == ("systemctl", "start", "atlas-update.service")
    with pytest.raises(ProtocolError):
        build_plan("app.update", {"version": "v1.1.2"})
    with pytest.raises(ProtocolError):
        build_plan("app.update", {"version": "1.1.2;reboot"})
    remove = build_plan("container.remove", {"name": "atlas-probe", "force": True})
    assert remove.argv == ("docker", "rm", "--force", "atlas-probe")
    listed = build_plan("read.dir", {"path": "/etc/sudoers.d"})
    sockets = build_plan("read.command", {"argv": ["ss", "-lntup"]})
    assert sockets.argv == ("ss", "-lntup")
    project = build_plan("read.project", {"path": "/root/session_bot/main.py"})
    assert project.confirm == "/root/session_bot/main.py"
    with pytest.raises(ProtocolError):
        build_plan("read.project", {"path": "/etc/passwd"})
    assert listed.confirm == "/etc/sudoers.d"
    with pytest.raises(ProtocolError):
        build_plan("read.dir", {"path": "/etc/passwd"})


def test_ssh_edit_keeps_a_backup(tmp_path: Path) -> None:
    message = change_key(tmp_path, "deploy", PUBLIC, remove=False)
    path = authorized_keys_path(tmp_path, "deploy")
    assert "added" in message
    assert path.read_text(encoding="utf-8").strip() == PUBLIC
    assert path.stat().st_mode & 0o777 == 0o600
    change_key(tmp_path, "deploy", PUBLIC, remove=True)
    assert path.with_name("authorized_keys.atlas.bak").is_file()
    assert path.read_text(encoding="utf-8") == ""


def test_helper_rejects_a_foreign_peer_and_can_cancel_reboot() -> None:
    directory = Path("/tmp") / f"atlas-h-{os.getpid()}-{time.time_ns()}"
    directory.mkdir()
    path = directory / "h.sock"
    calls: list[tuple[str, ...]] = []
    peers = {"uid": 1}

    def runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
        calls.append(argv)
        return 0, "", ""

    server = HelperServer(
        path,
        allowed_uids=frozenset({1000}),
        runner=runner,
        peer_of=lambda _conn: peers["uid"],
        keys_root=directory,
        delay_scale=30,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _wait_for(path)
    try:
        refused = _ask(path, {"op": "service.start", "params": {"unit": "nginx"}})
        assert refused["ok"] is False
        assert calls == []
        peers["uid"] = 1000
        protected = _ask(path, {"op": "service.stop", "params": {"unit": "sshd.service"}})
        assert protected["ok"] is False
        assert calls == []
        started = _ask(path, {"op": "service.start", "params": {"unit": "nginx.service"}})
        assert started["ok"] is True
        assert calls == [("systemctl", "start", "nginx.service")]
        pending = _ask(path, {"op": "host.reboot", "params": {"hostname": "web-1"}})
        assert pending["pending"]
        cancelled = _ask(path, {"op": "host.cancel", "pending": pending["pending"]})
        assert cancelled == {"ok": True, "result": "cancelled"}
        time.sleep(0.05)
        assert calls == [("systemctl", "start", "nginx.service")]
    finally:
        server.close()
        shutil.rmtree(directory, ignore_errors=True)


def test_reboot_risk_names_containers_and_keeps_ssh_when_its_socket_is_on(tmp_path: Path) -> None:
    from atlas.domain import Entity

    store = Store.open(tmp_path / "atlas.db")
    scan_id = store.start_scan("manual")
    store._insert_entity(
        scan_id,
        Entity(
            "service",
            "ssh.service",
            {"unit.active": "active", "unit.enabled": "disabled"},
        ),
    )
    store._insert_entity(
        scan_id,
        Entity(
            "service",
            "ssh.socket",
            {"unit.active": "active", "unit.enabled": "enabled"},
        ),
    )
    store._insert_entity(
        scan_id,
        Entity(
            "container",
            "355f1f16ea14",
            {"name": "remnawave", "restart_policy": "no"},
        ),
    )
    store.finish_scan(scan_id, "succeeded")
    risks = restart_risks(store)
    assert all(item["name"] != "ssh.service" for item in risks)
    assert {"kind": "container", "name": "remnawave", "enabled": "no"} in risks
    store.close()


def test_control_is_off_until_the_host_command(tmp_path: Path) -> None:
    database = tmp_path / "atlas.db"
    store = Store.open(database)
    assert control_enabled(store) is False
    assert main(["control", "enable", "--db", str(database)]) == 0
    assert control_enabled(store) is True
    assert verify_chain(store.conn) is True
    assert main(["control", "disable", "--db", str(database)]) == 0
    assert control_enabled(store) is False
    store.close()


def test_panel_records_a_refused_action_and_a_helper_call(tmp_path: Path) -> None:
    root = tmp_path / "host"
    shutil.copytree(FIXTURE, root, symlinks=True)
    store = Store.open(tmp_path / "atlas.db")
    run_scan(open_view(root), store, "oneshot")
    risks = restart_risks(store)
    assert {"kind": "service", "name": "shop.service", "enabled": "disabled"} in risks
    assert all(item["name"] != "nginx.service" for item in risks)

    directory = Path("/tmp") / f"atlas-h-{os.getpid()}-{time.time_ns()}"
    directory.mkdir()
    socket_path = directory / "h.sock"
    calls: list[tuple[str, ...]] = []

    def runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
        calls.append(argv)
        return 0, "", ""

    server = HelperServer(
        socket_path,
        allowed_uids=frozenset({1000}),
        runner=runner,
        peer_of=lambda _conn: 1000,
        delay_scale=30,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _wait_for(socket_path)
    app = create_app(
        store,
        Settings(root, allowed_hosts=("testserver",), helper_socket=str(socket_path)),
        sleeper=lambda _seconds: None,
        clock=lambda: NOW,
    )
    client = TestClient(app)
    secret = _enroll(client, store)
    blocked = client.post(
        "/api/v1/actions/service.start",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"params": {"unit": "nginx.service"}, "confirm": "nginx.service"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "control.disabled"
    assert calls == []

    assert main(["control", "enable", "--db", str(tmp_path / "atlas.db")]) == 0
    missing = client.post(
        "/api/v1/actions/service.start",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"params": {"unit": "nginx.service"}, "confirm": "nginx"},
    )
    assert missing.status_code == 400
    started = client.post(
        "/api/v1/actions/service.start",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"params": {"unit": "nginx.service"}, "confirm": "nginx.service"},
    )
    assert started.status_code == 200
    assert calls == [("systemctl", "start", "nginx.service")]
    guarded = client.post(
        "/api/v1/actions/service.stop",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"params": {"unit": "sshd.service"}, "confirm": "sshd.service"},
    )
    assert guarded.status_code == 400
    status = client.get("/api/v1/control")
    assert status.json()["enabled"] is True

    member = begin_member(
        store.conn,
        username="reader",
        password="another-password",
        role="viewer",
        now=NOW,
        ttl_seconds=900,
    )
    viewer = TestClient(app)
    _confirm(
        viewer,
        member.token,
        pyotp.TOTP(member.totp_secret).provisioning_uri(name="reader", issuer_name="ATLAS"),
    )
    denied = viewer.post(
        "/api/v1/actions/service.restart",
        headers={"x-csrf-token": viewer.cookies["atlas_csrf"]},
        json={"params": {"unit": "nginx.service"}, "confirm": "nginx.service"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "auth.forbidden"
    assert viewer.get("/api/v1/audit").status_code == 403

    reboot = client.post(
        "/api/v1/actions/host.reboot",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={
            "params": {"hostname": "web-1"},
            "confirm": "web-1",
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert reboot.status_code == 200
    assert reboot.json()["pending"]
    assert any(item["name"] == "shop.service" for item in reboot.json()["risks"])
    cancelled = client.post(
        "/api/v1/actions/host.cancel",
        headers={"x-csrf-token": client.cookies["atlas_csrf"]},
        json={"params": {"pending": reboot.json()["pending"]}},
    )
    assert cancelled.status_code == 200
    audit = client.get("/api/v1/audit")
    assert audit.status_code == 200
    assert audit.json()["intact"] is True
    assert any(row["result"] == "control.disabled" for row in audit.json()["items"])
    store.conn.execute("UPDATE audit_log SET result = 'tampered' WHERE id = 1")
    assert verify_chain(store.conn) is False
    assert client.get("/api/v1/audit").json()["intact"] is False
    server.close()
    shutil.rmtree(directory, ignore_errors=True)
    store.close()


def test_helper_does_not_import_the_web_framework() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, atlas.helper.server; assert 'fastapi' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert probe.returncode == 0, probe.stderr


def _ask(path: Path, payload: dict[str, object]) -> dict[str, object]:
    last = ""
    for _ in range(20):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(path))
                client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
                raw = b""
                while b"\n" not in raw and len(raw) < 65536:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
            answer = json.loads(raw.decode("utf-8"))
            if isinstance(answer, dict):
                return answer
        except OSError as exc:
            last = str(exc)
            time.sleep(0.02)
    raise AssertionError(last)


def _wait_for(path: Path) -> None:
    for _ in range(50):
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(path)


def _enroll(client: TestClient, store: Store) -> str:
    token = issue_bootstrap(store.conn, now=NOW, ttl_seconds=900)
    started = client.post(
        "/api/v1/auth/bootstrap",
        json={"token": token, "username": "owner", "password": "a-long-password"},
    )
    secret = _secret(started.json()["otpauth_uri"])
    _confirm(client, started.json()["enrollment_token"], started.json()["otpauth_uri"])
    return secret


def _confirm(client: TestClient, token: str, uri: str) -> None:
    response = client.post(
        "/api/v1/auth/enroll", json={"token": token, "code": pyotp.TOTP(_secret(uri)).now()}
    )
    assert response.status_code == 200


def _secret(uri: str) -> str:
    return uri.split("secret=")[1].split("&")[0]
