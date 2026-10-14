"""Alerts stay quiet, old metrics roll up, and uninstall cannot leave its prefix."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from datetime import timedelta
from pathlib import Path

from atlas.application.alerts import AlertError, evaluate, save_channel
from atlas.application.lifecycle import diagnose, uninstall
from atlas.cli.main import main
from atlas.metrics.series import query_series, rollup_and_prune
from atlas.storage.db import Store


def test_alerts_do_not_send_until_a_channel_is_enabled(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    sent: list[str] = []
    _scan(store)
    store.conn.execute(
        "INSERT INTO changes (scan_id, entity_kind, entity_key, change_kind, after_json) "
        "VALUES (1, 'port', 'tcp:22', 'added', '{}')"
    )
    store.conn.commit()
    created = evaluate(store, transport=lambda _kind, _target, message: sent.append(message))
    assert created[0]["rule"] == "new_port"
    assert sent == []
    again = evaluate(store, transport=lambda _kind, _target, message: sent.append(message))
    assert again == []
    save_channel(store.conn, "webhook", "https://alerts.example/hook", enabled=True)
    evaluate(store, transport=lambda _kind, _target, message: sent.append(message))
    assert sent == ["new port tcp:22"]
    evaluate(store, transport=lambda _kind, _target, message: sent.append(message))
    assert sent == ["new port tcp:22"]
    store.close()


def test_a_failed_unit_resolves_when_it_recovers(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    sent: list[str] = []
    scan_id = _scan(store)
    store.conn.execute(
        "INSERT INTO entities (scan_id, kind, entity_key, payload) VALUES (?, 'service', ?, ?)",
        (scan_id, "shop.service", json.dumps({"unit.active": "failed"})),
    )
    store.conn.commit()
    save_channel(store.conn, "webhook", "https://alerts.example/hook", enabled=True)

    def transport(_kind: str, _target: str, message: str) -> None:
        sent.append(message)

    evaluate(store, transport=transport)
    assert sent == ["shop.service is failed"]
    store.conn.execute("DELETE FROM entities WHERE entity_key = 'shop.service'")
    store.conn.commit()
    evaluate(store, transport=transport, cooldown=timedelta(0))
    assert sent[-1] == "shop.service recovered"
    store.close()


def test_channel_target_must_be_a_url(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    try:
        save_channel(store.conn, "webhook", "file:///tmp/hook")
    except AlertError as exc:
        assert "http" in exc.message
    else:
        raise AssertionError("expected the target to be refused")
    store.close()


def test_old_points_become_rollups(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    now = 2_000_000
    store.conn.execute(
        "INSERT INTO metric_points (series, ts, value) VALUES ('host.load.1', ?, 2)",
        (now - 2 * 24 * 60 * 60,),
    )
    store.conn.commit()
    removed = rollup_and_prune(store.conn, now=now)
    assert removed == 1
    points = query_series(store.conn, "host.load.1", 0, now, 60)
    assert points
    assert points[0]["value"] == 2
    store.close()


def test_uninstall_keeps_data_until_purge_and_refuses_a_symlink(tmp_path: Path) -> None:
    opt = tmp_path / "opt" / "atlas"
    data = tmp_path / "var" / "lib" / "atlas"
    opt.mkdir(parents=True)
    data.mkdir(parents=True)
    (data / "atlas.db").write_text("keep", encoding="utf-8")
    removed = uninstall(tmp_path, purge=False, run=lambda _argv: None)
    assert str(opt.resolve()) in removed
    assert data.is_dir()
    uninstall(tmp_path, purge=True, run=lambda _argv: None)
    assert not data.exists()

    outside = Path("/tmp") / f"atlas-outside-{os.getpid()}"
    outside.mkdir()
    try:
        (tmp_path / "opt" / "atlas").symlink_to(outside)
        try:
            uninstall(tmp_path, purge=True, run=lambda _argv: None)
        except SystemExit:
            assert outside.is_dir()
        else:
            raise AssertionError("expected the symlink to be refused")
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_doctor_and_expose(tmp_path: Path) -> None:
    database = tmp_path / "atlas.db"
    store = Store.open(database)
    store.close()
    database.chmod(0o600)
    notes = diagnose(Store.open(database), database)
    assert any(note == "database mode is 0600" for note in notes)
    assert any(note == "alert channels are off" for note in notes)
    database.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    observed = database.stat().st_mode & 0o777
    warn = diagnose(Store.open(database), database, observed_mode=observed)
    assert any(note.startswith("warning:") for note in warn)
    database.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    assert main(["doctor", "--db", str(database)]) == 1
    assert main(["expose"]) == 0
    assert main(["status", "--db", str(database)]) == 0


def test_installer_dry_run_and_prefix(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "packaging" / "install.sh"
    dry = subprocess.run(
        ["sh", str(script), "--prefix", str(tmp_path / "dry"), "--dry-run"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert dry.returncode == 0
    assert "/opt/atlas" in dry.stdout
    assert not (tmp_path / "dry").exists()
    refused = subprocess.run(
        ["sh", str(script), "--url", "https://example.invalid/atlas.tar"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 2
    installed = subprocess.run(
        ["sh", str(script), "--prefix", str(tmp_path / "root"), "--no-start"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    unit = tmp_path / "root" / "usr" / "lib" / "systemd" / "system" / "atlas-helper.service"
    assert "PrivateNetwork=yes" in unit.read_text(encoding="utf-8")
    assert "__UID__" not in unit.read_text(encoding="utf-8")


def _scan(store: Store) -> int:
    store.conn.execute(
        "INSERT INTO scans (started_at, status, mode) VALUES ('t', 'succeeded', 'test')"
    )
    store.conn.commit()
    row = store.conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])
