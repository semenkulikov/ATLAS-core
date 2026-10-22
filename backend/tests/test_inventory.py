"""A fixture host stands in for a server. Secrets planted beside it must not come back."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from atlas.application.report import build_report, render_html, render_json, render_markdown
from atlas.application.scan import run_scan
from atlas.collectors.host import SshCollector
from atlas.collectors.platforms import engine_get
from atlas.collectors.registry import declarations
from atlas.collectors.services import FirewallCollector, SystemdCollector
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


def test_sshd_without_a_port_line_uses_the_default(tmp_path: Path) -> None:
    root = tmp_path / "host"
    config = root / "etc" / "ssh"
    config.mkdir(parents=True)
    (config / "sshd_config").write_text("PermitRootLogin no\n", encoding="utf-8")
    result = SshCollector().collect(open_view(root))
    port = next(item for item in result.facts if item.predicate == "sshd.port")
    assert port.value == "22"
    assert port.certainty.value == "derived"
    assert port.rule == "sshd.default-port"
    entity = next(item for item in result.entities if item.kind == "sshd")
    assert entity.payload["port"] == "22"


def test_package_does_not_invoke_a_shell() -> None:
    root = Path(__file__).resolve().parents[1] / "atlas"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text
        assert "os.system(" not in text


def test_unloaded_unit_file_is_shown_by_name(tmp_path: Path) -> None:
    root = tmp_path / "host"
    unit_dir = root / "etc" / "systemd" / "system"
    unit_dir.mkdir(parents=True)
    (unit_dir / "ledger.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /opt/ledger/main.py\n",
        encoding="utf-8",
    )
    (unit_dir / "worker@.service").write_text(
        "[Service]\nExecStart=/usr/bin/true\n",
        encoding="utf-8",
    )
    commands = {
        "systemctl show --type=service --all --no-pager": {
            "stdout": "Id=nginx.service\nActiveState=active\n\n"
        },
        "systemctl show --no-pager ledger.service": {
            "stdout": (
                "Id=ledger.service\nActiveState=inactive\nSubState=dead\nUnitFileState=disabled\n"
            )
        },
    }
    (root / "commands.json").write_text(json.dumps(commands), encoding="utf-8")
    result = SystemdCollector().collect(open_view(root))
    services = {item.key: item.payload for item in result.entities if item.kind == "service"}
    assert services["ledger.service"]["unit.active"] == "inactive"
    assert services["ledger.service"]["unit.enabled"] == "disabled"
    assert "unit.active" not in services["worker@.service"]
    asked = [source.target for source in result.sources]
    assert "systemctl show --no-pager ledger.service" in asked
    assert not any(target.startswith("systemctl") and "worker@" in target for target in asked)


def test_firewall_is_read_in_the_host_namespace(tmp_path: Path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    commands = {
        "nsenter -t 1 -n nft list ruleset": {
            "stdout": (
                "chain input {\n"
                "  type filter hook input priority 0; policy drop;\n"
                "  tcp dport 22 accept\n"
                "}\n"
            )
        }
    }
    (root / "commands.json").write_text(json.dumps(commands), encoding="utf-8")
    result = FirewallCollector().collect(open_view(root))
    entity = next(item for item in result.entities if item.kind == "firewall")
    assert entity.payload["policy"] == "drop"
    assert {"protocol": "tcp", "port": 22} in entity.payload["ports"]
    assert entity.key.startswith("nsenter -t 1 -n nft")


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
