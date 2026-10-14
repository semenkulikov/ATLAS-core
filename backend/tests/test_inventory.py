"""A fixture host stands in for a server. Secrets planted beside it must not come back."""

from __future__ import annotations

import shutil
from pathlib import Path

from atlas.application.report import build_report, render_html, render_json, render_markdown
from atlas.application.scan import run_scan
from atlas.collectors.platforms import engine_get
from atlas.collectors.registry import declarations
from atlas.collectors.view import open_view
from atlas.storage.db import Store

CANARY = "ATLAS_CANARY_7f3a9c"
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"


def _plant(root: Path) -> None:
    (root / "etc").mkdir(exist_ok=True)
    (root / "etc" / "shadow").write_text(f"root:{CANARY}:19000:0:99999:7:::\n", encoding="utf-8")
    key = root / "opt" / "shop" / "id_rsa"
    key.write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\n" + CANARY + "\n-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    (root / "opt" / "shop" / ".env").write_text(
        f"SECRET_KEY={CANARY}\nDATABASE_URL=postgres://shop:{CANARY}@127.0.0.1/shop\n",
        encoding="utf-8",
    )
    nginx = root / "etc" / "nginx" / "sites-enabled" / "shop.conf"
    nginx.write_text(
        nginx.read_text(encoding="utf-8")
        + f'\nproxy_set_header Authorization "Bearer {CANARY}";\n',
        encoding="utf-8",
    )


def test_fixture_scan_keeps_proof_and_drops_secrets(tmp_path: Path) -> None:
    root = tmp_path / "host"
    shutil.copytree(FIXTURE, root, symlinks=True)
    _plant(root)
    view = open_view(root)
    shadow = view.read("/etc/shadow")
    assert shadow.status == "unavailable"
    assert shadow.text is None
    env = view.read("/opt/shop/.env")
    assert env.text is not None
    assert CANARY not in env.text
    assert "SECRET_KEY" in env.text

    store = Store.open(tmp_path / "atlas.db")
    try:
        scan_id = run_scan(view, store, "oneshot")
        blob = store.dump_text(scan_id)
        report = build_report(store, scan_id)
        rendered = "\n".join(
            [blob, render_json(report), render_markdown(report), render_html(report)]
        )
        assert CANARY not in rendered
        facts = {(row["subject"], row["predicate"], row["value"]) for row in store.facts(scan_id)}
        assert ("host", "os.pretty_name", "Ubuntu 24.04.1 LTS") in facts
        assert ("unit:shop.service", "unit.working_directory", "/opt/shop") in facts
        assert ("unit:nginx.service", "unit.active", "active") in facts
        assert ("port:tcp:80:0.0.0.0", "port.exposed", "yes") in facts
        assert ("port:tcp:8000:127.0.0.1", "port.exposed", "no") in facts
        services = {row["key"]: row["payload"] for row in store.entities(scan_id, "service")}
        assert services["shop.service"]["working_directory"] == "/opt/shop"
        assert services["nginx.service"]["unit.active"] == "active"
        ports = store.entities(scan_id, "port")
        exposed = next(row for row in ports if row["payload"]["port"] == 80)
        assert exposed["payload"]["process"]["comm"] == "nginx"
        assert any(row["key"] == "deploy" for row in store.entities(scan_id, "user"))
        keys = store.entities(scan_id, "ssh_key")
        assert keys and str(keys[0]["payload"]["fingerprint"]).startswith("SHA256:")
        sites = store.entities(scan_id, "site")
        assert sites[0]["payload"]["names"] == ["shop.example.com"]
        assert ("site:/etc/nginx/sites-enabled/shop.conf:0", "site.proxy_port", "8000") in facts
        schedules = store.entities(scan_id, "schedule")
        assert any(row["payload"].get("command") == "/opt/shop/backup.sh" for row in schedules)
        containers = store.entities(scan_id, "container")
        assert containers[0]["payload"]["name"] == "shop-web"
        assert store.entities(scan_id, "datastore")[0]["key"] == "postgres"
    finally:
        store.close()


def test_second_scan_records_changes(tmp_path: Path) -> None:
    root = tmp_path / "host"
    shutil.copytree(FIXTURE, root, symlinks=True)
    store = Store.open(tmp_path / "atlas.db")
    try:
        first = run_scan(open_view(root), store, "manual")
        assert store.changes(first) == []
        (root / "etc" / "hostname").write_text("web-2\n", encoding="utf-8")
        second = run_scan(open_view(root), store, "manual")
        changes = store.changes(second)
        assert any(row["change_kind"] == "modified" for row in changes)
    finally:
        store.close()


def test_manifest_covers_every_collector() -> None:
    rows = declarations()
    collectors = {row.collector for row in rows}
    assert "os" in collectors
    assert "containers" in collectors
    assert all(row.purpose_en and row.purpose_ru for row in rows)


def test_engine_get_refuses_unlisted_paths() -> None:
    try:
        engine_get(Path("/tmp/atlas-no-such.sock"), "/containers/create")
    except ValueError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("unlisted engine path was accepted")


def test_package_does_not_invoke_a_shell() -> None:
    root = Path(__file__).resolve().parents[1] / "atlas"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text
        assert "os.system(" not in text


def test_scanner_does_not_import_the_web_framework() -> None:
    import subprocess
    import sys

    subprocess.check_call(
        [
            sys.executable,
            "-c",
            "import atlas.application.scan, sys; assert 'fastapi' not in sys.modules",
        ]
    )
