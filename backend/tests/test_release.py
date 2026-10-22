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
from atlas.application.scan import run_scan
from atlas.cli.main import main
from atlas.collectors.view import open_view
from atlas.metrics.series import enforce_metric_budget, query_series, rollup_and_prune
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
    missing = tmp_path / "missing.sock"
    notes = diagnose(
        Store.open(database),
        database,
        web_socket=missing,
        helper_socket=missing,
    )
    assert any(note == "database mode is 0600" for note in notes)
    assert any(note == "alert channels are off" for note in notes)
    assert any("panel socket missing" in note for note in notes)
    database.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    observed = database.stat().st_mode & 0o777
    warn = diagnose(
        Store.open(database),
        database,
        observed_mode=observed,
        web_socket=missing,
        helper_socket=missing,
    )
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
    # --url hands off to get-atlas.sh, which must run as root.
    remote = subprocess.run(
        ["sh", str(script), "--url"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert remote.returncode == 1
    assert "root" in remote.stderr.lower()
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


def test_fixture_reads_stay_inside_the_manifest() -> None:
    from atlas.collectors.registry import COLLECTORS, undeclared
    from atlas.collectors.view import open_view

    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"
    view = open_view(fixture)
    for collector in COLLECTORS:
        collector.collect(view)
    assert undeclared(view.files_read, view.commands_run) == []


def test_system_journal_is_not_a_unit_named_syslog(tmp_path: Path, monkeypatch) -> None:
    from atlas.application import logs

    seen: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        seen.append(list(argv))

        class Done:
            returncode = 0
            stdout = "kept\n"

        return Done()

    monkeypatch.setattr(logs.subprocess, "run", fake_run)
    assert logs.read_log(tmp_path, "journal:syslog", 10)["lines"] == ["kept"]
    assert seen[0][:2] == ["journalctl", "--system"]
    assert "-u" not in seen[0]
    logs.read_log(tmp_path, "journal:atlas", 5)
    assert seen[1][1:3] == ["-u", "atlas"]


def test_log_filter_and_certificate_date(tmp_path: Path) -> None:
    import base64
    from datetime import UTC, datetime, timedelta

    from atlas.application.logs import LogError, read_log
    from atlas.collectors.parse import certificate_not_after
    from atlas.helper.protocol import build_plan

    log = tmp_path / "app.log"
    log.write_text("alpha\nbeta\n", encoding="utf-8")
    assert read_log(tmp_path, "app.log", 20, query="alpha")["lines"] == ["alpha"]
    try:
        read_log(tmp_path, "app.log", 20, pattern="(.+)+")
    except LogError as exc:
        assert "broad" in exc.message
    else:
        raise AssertionError("expected the pattern to be refused")
    der = b"\x17\x0d260101000000Z\x17\x0d261020000000Z"
    pem = (
        "-----BEGIN CERTIFICATE-----\n"
        + base64.b64encode(der).decode()
        + "\n-----END CERTIFICATE-----\n"
    )
    expiry = certificate_not_after(pem)
    assert expiry == datetime(2026, 10, 20, tzinfo=UTC)
    store = Store.open(tmp_path / "atlas.db")
    try:
        scan_id = _scan(store)
        store.conn.execute(
            "INSERT INTO entities (scan_id, kind, entity_key, payload) VALUES (?, 'certificate', ?, ?)",
            (scan_id, "/etc/ssl/shop.crt", json.dumps({"not_after": expiry.isoformat()})),
        )
        store.conn.commit()
        created = evaluate(store, now=expiry - timedelta(days=1))
        assert any(item["rule"] == "cert_expiring" for item in created)
    finally:
        store.close()
    plan = build_plan("image.prune", {})
    assert plan.argv == ("docker", "image", "prune", "--force")
    assert plan.confirm == "images"


def test_fixture_matches_the_expected_facts(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"
    expected = json.loads((fixture / "expected-facts.json").read_text(encoding="utf-8"))
    store = Store.open(tmp_path / "atlas.db")
    try:
        scan_id = run_scan(open_view(fixture), store, "golden")
        actual = sorted(
            [row["subject"], row["predicate"], row["certainty"], row["value"]]
            for row in store.facts(scan_id)
        )
    finally:
        store.close()
    assert actual == expected


def test_export_writes_the_latest_scan(tmp_path: Path) -> None:
    database = tmp_path / "atlas.db"
    store = Store.open(database)
    try:
        _scan(store)
    finally:
        store.close()
    output = tmp_path / "out" / "report"
    assert main(["export", "--db", str(database), "--output", str(output), "--format", "json"]) == 0
    assert output.with_suffix(".json").is_file()
    empty = Store.open(tmp_path / "empty.db")
    empty.close()
    assert (
        main(["export", "--db", str(tmp_path / "empty.db"), "--output", str(tmp_path / "none")])
        == 1
    )


def test_metric_budget_drops_the_oldest_points(tmp_path: Path) -> None:
    store = Store.open(tmp_path / "atlas.db")
    try:
        for index in range(5):
            store.conn.execute(
                "INSERT INTO metric_points (series, ts, value) VALUES ('host.load.1', ?, 1)",
                (1_000 + index,),
            )
        store.conn.commit()
        dropped = enforce_metric_budget(store.conn, limit_bytes=64 * 2)
        store.conn.commit()
        assert dropped == 3
        left = store.conn.execute("SELECT ts FROM metric_points ORDER BY ts").fetchall()
        assert [int(row["ts"]) for row in left] == [1003, 1004]
    finally:
        store.close()


def test_oneshot_does_not_install_units(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "packaging" / "install.sh"
    bare = os.pathsep.join(
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and not (Path(entry) / "atlas").exists()
    )
    completed = subprocess.run(
        ["sh", str(script), "--prefix", str(tmp_path / "root"), "--oneshot"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": bare},
    )
    assert completed.returncode == 0, completed.stderr
    assert "oneshot" in completed.stdout
    assert not (tmp_path / "root").exists()
    report = tmp_path / "out"
    report.mkdir()
    fake = tmp_path / "bin"
    fake.mkdir()
    atlas = fake / "atlas"
    atlas.write_text(
        "#!/bin/sh\nfor ext in md json html; do printf report > atlas-report.$ext; done\n",
        encoding="utf-8",
    )
    atlas.chmod(0o755)
    wrote = subprocess.run(
        ["sh", str(script), "--oneshot"],
        check=False,
        capture_output=True,
        text=True,
        cwd=report,
        env={**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert wrote.returncode == 0, wrote.stderr
    assert (report / "atlas-report.md").is_file()
    assert (report / "atlas-report.json").is_file()
    assert (report / "atlas-report.html").is_file()


def test_release_installs_a_websocket_library() -> None:
    root = Path(__file__).resolve().parents[2]
    project = (root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    script = (root / "packaging" / "build-release.sh").read_text(encoding="utf-8")
    assert "websockets" in project
    assert "websockets" in script


def test_scan_timer_runs_as_the_panel_user() -> None:
    root = Path(__file__).resolve().parents[2]
    unit = (root / "packaging" / "atlas-scan.service").read_text(encoding="utf-8")
    timer = (root / "packaging" / "atlas-scan.timer").read_text(encoding="utf-8")
    assert "User=atlas" in unit
    assert "ProtectHome=yes" in unit
    assert (
        "scan --root / --db /var/lib/atlas/atlas.db --helper-socket /run/atlas/helper.sock" in unit
    )
    assert "OnActiveSec=15min" in timer
    assert "OnUnitActiveSec=6h" in timer
    for name in ("install.sh", "install-bundle.sh", "remove-atlas.sh"):
        script = (root / "packaging" / name).read_text(encoding="utf-8")
        assert "atlas-scan.timer" in script
    bundle = (root / "packaging" / "install-bundle.sh").read_text(encoding="utf-8")
    assert "systemctl start atlas-scan.timer" in bundle
    assert "systemctl start atlas-scan.service" not in bundle


def test_panel_unit_can_read_the_system_journal() -> None:
    root = Path(__file__).resolve().parents[2]
    unit = (root / "packaging" / "atlas.service").read_text(encoding="utf-8")
    assert "SupplementaryGroups=systemd-journal" in unit
    for name in ("install.sh", "install-bundle.sh"):
        script = (root / "packaging" / name).read_text(encoding="utf-8")
        assert "usermod -aG systemd-journal atlas" in script


def _scan(store: Store) -> int:
    store.conn.execute(
        "INSERT INTO scans (started_at, status, mode) VALUES ('t', 'succeeded', 'test')"
    )
    store.conn.commit()
    row = store.conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])
