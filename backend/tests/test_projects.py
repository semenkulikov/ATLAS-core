"""Project cards come from anchors, and every stack claim cites a file."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.application.scan import run_scan
from atlas.collectors.platforms import decode_docker_stream
from atlas.collectors.view import FixtureRunner, HostView, SubprocessRunner, open_view
from atlas.detectors.discover import _git_facts, discover, find_root, project_snapshot
from atlas.detectors.rules import apply_rules, requirement_versions
from atlas.domain import CollectorResult, Entity
from atlas.knowledge.loader import reference_for
from atlas.storage.db import Store

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "partial-host"
CANARY = "ATLAS_CANARY_7f3a9c"
discover_mod = sys.modules["atlas.detectors.discover"]


def test_shop_project_is_django_and_searchable(tmp_path: Path) -> None:
    root = tmp_path / "host"
    shutil.copytree(FIXTURE, root, symlinks=True)
    readme = root / "opt" / "shop" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + f"\ntoken={CANARY}\n", encoding="utf-8")
    store = Store.open(tmp_path / "atlas.db")
    try:
        scan_id = run_scan(open_view(root), store, "oneshot")
        projects = store.projects(scan_id)
        shop = [row for row in projects if row["payload"]["root_path"] == "/opt/shop"]
        assert shop
        project_id = shop[0]["key"]
        facts = store.facts(scan_id, f"project:{project_id}")
        assert any(row["value"] == "Django" and row["certainty"] == "derived" for row in facts)
        assert any(
            row["predicate"] == "dependency.django" and row["value"] == "4.2.16" for row in facts
        )
        assert any(
            row["value"] == "web" and row["rule"] == "stack.compose.service" for row in facts
        )
        hits = store.search_docs(scan_id, "storefront")
        assert hits
        assert CANARY not in store.dump_text(scan_id)
        services = {row["key"]: row["payload"] for row in store.entities(scan_id, "service")}
        assert services["nginx.service"]["reference"]["source"] == "knowledge"
        assert not any(
            row["value"] == services["nginx.service"]["reference"]["summary_en"]
            for row in store.facts(scan_id)
        )
    finally:
        store.close()


def test_rules_cover_node_go_and_static(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "srv" / "api").mkdir(parents=True)
    (root / "srv" / "api" / "package.json").write_text(
        '{"dependencies": {"express": "^4.18.0"}}\n', encoding="utf-8"
    )
    (root / "srv" / "tool").mkdir(parents=True)
    (root / "srv" / "tool" / "go.mod").write_text(
        "module example.com/tool\n\ngo 1.22\n", encoding="utf-8"
    )
    (root / "srv" / "site").mkdir(parents=True)
    (root / "srv" / "site" / "index.html").write_text("<html>site</html>\n", encoding="utf-8")
    view = open_view(root)
    express = apply_rules(view, "/srv/api", "node server.js", view.now)
    assert any(hit.value == "Express" for hit in express)
    assert any(hit.value == "Node.js" for hit in express)
    go = apply_rules(view, "/srv/tool", "", view.now)
    assert any(hit.value == "example.com/tool" for hit in go)
    static = apply_rules(view, "/srv/site", "", view.now)
    assert any(hit.value == "Static site" for hit in static)


def test_aiogram_needs_a_python_entrypoint(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "opt" / "ledger").mkdir(parents=True)
    (root / "opt" / "ledger" / "requirements.txt").write_text("aiogram==3.13.1\n", encoding="utf-8")
    view = open_view(root)
    library = apply_rules(view, "/opt/ledger", "gunicorn app:app", view.now)
    assert not any(hit.rule == "stack.aiogram-bot" for hit in library)
    launched = apply_rules(view, "/opt/ledger", "python /opt/ledger/main.py", view.now)
    assert any(hit.rule == "stack.aiogram-bot" for hit in launched)


def test_reference_catalog_does_not_invent_a_unit() -> None:
    assert reference_for("nginx.service") is not None
    assert reference_for("shop.service") is None


def test_discover_uses_a_systemd_anchor(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    project = root / "opt" / "shop"
    project.mkdir(parents=True)
    (project / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    view = open_view(root)
    result = discover(
        view,
        [
            CollectorResult(
                (),
                (
                    Entity(
                        "service",
                        "api.service",
                        {
                            "unit": "api.service",
                            "working_directory": "/opt/shop",
                            "exec_start": "uvicorn app:app",
                        },
                    ),
                ),
                (),
            )
        ],
    )
    assert result.projects
    assert result.projects[0]["root_path"] == "/opt/shop"
    assert any(item.value == "FastAPI" for item in result.facts)


def test_a_script_path_anchors_a_project_without_indexing_requirements(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    project = root / "root" / "session_bot"
    project.mkdir(parents=True)
    (project / "requirements.txt").write_text("aiogram==3.13.1\n", encoding="utf-8")
    (project / "README.md").write_text("\n\n# Session\n\nA bot.\n", encoding="utf-8")
    view = open_view(root)
    result = discover(
        view,
        [
            CollectorResult(
                (),
                (
                    Entity(
                        "service",
                        "session-bot.service",
                        {
                            "unit": "session-bot.service",
                            "working_directory": None,
                            "exec_start": "/root/session_bot/venv/bin/python /root/session_bot/main.py",
                        },
                    ),
                ),
                (),
            )
        ],
    )
    assert result.projects[0]["root_path"] == "/root/session_bot"
    paths = [str(doc["path"]) for doc in result.docs]
    assert any(path.endswith("README.md") for path in paths)
    assert not any(path.endswith("requirements.txt") for path in paths)


def test_an_unreadable_directory_does_not_abort_discovery(tmp_path: Path, monkeypatch) -> None:
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    view = open_view(tmp_path, now=datetime(2026, 10, 15, tzinfo=UTC))
    original = Path.exists

    def denied(self: Path, *, follow_symlinks: bool = True) -> bool:
        if self.name == ".git" and "hidden" in self.parts:
            raise PermissionError(13, "Permission denied", str(self))
        return original(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "exists", denied)
    assert find_root(view, "/hidden/app") is None


def test_a_git_checkout_records_the_commit(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'shop'\n", encoding="utf-8")
    (root / "README.md").write_text("# shop\n<script>alert(1)</script>\n", encoding="utf-8")
    (root / "requirements.txt").write_text("-r extra.txt\nDjango==4.2.16\n", encoding="utf-8")
    _git(root, ["init"])
    _git(root, ["config", "user.email", "ada@example.test"])
    _git(root, ["config", "user.name", "Ada"])
    _git(root, ["add", "pyproject.toml", "README.md", "requirements.txt"])
    _git(root, ["commit", "-m", "init"])
    _git(root, ["remote", "add", "origin", "https://example.test/shop.git"])
    view = open_view(tmp_path, now=datetime(2026, 10, 14, tzinfo=UTC))
    assert find_root(view, "/proj/README.md") == "/proj"
    facts = _git_facts(view, "/proj", "project:shop")
    predicates = {item.predicate: item.value for item in facts}
    assert len(predicates["git.commit"]) == 40
    assert predicates["git.remote"] == "https://example.test/shop.git"
    assert predicates["git.dirty"] == "no"
    versions = requirement_versions("-r extra.txt\n# note\nDjango==4.2.16\n")
    assert versions == [(3, "Django", "4.2.16")]


def test_a_borrowed_directory_records_stack_and_dependency_facts(
    tmp_path: Path, monkeypatch
) -> None:
    tree = tmp_path / "tree"
    project = tree / "opt" / "ledger"
    project.mkdir(parents=True)
    (project / "requirements.txt").write_text("flask==3.0.3\n", encoding="utf-8")
    moment = datetime(2026, 10, 21, tzinfo=UTC)
    readable = HostView(tree, FixtureRunner(tree), moment)
    anchor = "/opt/ledger/venv/bin/python /opt/ledger/app.py"
    snapshot = project_snapshot(readable, "/opt/ledger", anchor)
    assert "Flask" in snapshot["stack"]
    seen: dict[str, str] = {}

    def borrow(socket_path: str, start: str, anchor_text: str = "") -> dict[str, object]:
        del socket_path, start
        seen["anchor"] = anchor_text
        return snapshot

    monkeypatch.setattr(discover_mod, "find_root", lambda view, start: None)
    monkeypatch.setattr(discover_mod, "_borrow_project", borrow)
    hidden = HostView(tree, FixtureRunner(tree), moment, helper_socket="/run/atlas/helper.sock")
    result = discover(
        hidden,
        [
            CollectorResult(
                (),
                (
                    Entity(
                        "service",
                        "ledger.service",
                        {
                            "unit": "ledger.service",
                            "working_directory": None,
                            "exec_start": anchor,
                        },
                    ),
                ),
                (),
            )
        ],
    )
    assert seen["anchor"] == anchor
    assert any(
        item.predicate == "dependency.flask" and item.value == "3.0.3" for item in result.facts
    )
    assert any(item.value == "Flask" for item in result.facts)


def test_a_long_command_snapshot_is_kept(monkeypatch) -> None:
    blob = "x" * 1_500_000

    class Completed:
        returncode = 0
        stdout = blob
        stderr = ""

    monkeypatch.setattr("atlas.collectors.view.subprocess.run", lambda *args, **kwargs: Completed())
    result = SubprocessRunner().run(["systemctl", "show", "--type=service", "--all"])
    assert len(result.stdout) == 1_500_000


def test_docker_log_frames_become_text() -> None:
    payload = b"hello\n"
    frame = bytes([1, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload
    assert decode_docker_stream(frame) == "hello\n"
    assert decode_docker_stream(b"plain line\n") == "plain line\n"


def _git(root: Path, args: list[str]) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
