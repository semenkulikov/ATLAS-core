"""Installed version vs GitHub latest, without a live network."""

from __future__ import annotations

from pathlib import Path

from atlas.application.update import (
    clear_cache,
    fetch_latest,
    is_newer,
    latest_from_payload,
    parse_tag,
)
from atlas.helper.protocol import build_plan
from atlas.helper.server import HelperServer


def test_parse_and_compare_versions() -> None:
    assert parse_tag("v1.1.1") == "1.1.1"
    assert parse_tag("1.0.0") == "1.0.0"
    assert parse_tag("latest") is None
    assert parse_tag("1.1") is None
    assert is_newer("1.1.1", "1.1.0")
    assert not is_newer("1.1.0", "1.1.0")
    assert not is_newer("1.0.9", "1.1.0")


def test_latest_from_github_payload() -> None:
    assert latest_from_payload({"tag_name": "v1.2.0"}) == "1.2.0"
    assert latest_from_payload({"tag_name": "nightly"}) is None
    assert latest_from_payload([]) is None


def test_fetch_latest_uses_opener_and_cache() -> None:
    clear_cache()
    calls = {"n": 0}

    def opener(_url: str) -> dict[str, str]:
        calls["n"] += 1
        return {"tag_name": "v9.9.9"}

    first = fetch_latest(opener=opener, now=lambda: 100.0, cache_seconds=60.0)
    assert first["latest"] == "9.9.9"
    assert first["update_available"] is True
    assert first["error"] is None
    assert calls["n"] == 1

    second = fetch_latest(opener=opener, now=lambda: 120.0, cache_seconds=60.0)
    assert second["latest"] == "9.9.9"
    assert calls["n"] == 1

    clear_cache()
    failed = fetch_latest(
        opener=lambda _url: (_ for _ in ()).throw(TimeoutError("slow")),
        now=lambda: 200.0,
        cache_seconds=60.0,
    )
    assert failed["latest"] is None
    assert failed["update_available"] is False
    assert failed["error"]
    assert failed["current"]


def test_helper_writes_update_request_then_starts_unit(tmp_path: Path) -> None:
    request = tmp_path / "update-request"
    calls: list[tuple[str, ...]] = []

    def runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
        calls.append(argv)
        return 0, "", ""

    server = HelperServer(
        tmp_path / "unused.sock",
        allowed_uids=frozenset({0}),
        runner=runner,
        update_request_path=request,
    )
    plan = build_plan("app.update", {"version": "1.1.1"})
    outcome = server._start_update(plan)
    assert outcome["ok"] is True
    assert request.read_text(encoding="utf-8").strip() == "1.1.1"
    assert calls == [("systemctl", "start", "atlas-update.service")]


def test_helper_clears_request_when_systemctl_fails(tmp_path: Path) -> None:
    request = tmp_path / "update-request"

    def runner(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 1, "", "failed"

    server = HelperServer(
        tmp_path / "unused.sock",
        allowed_uids=frozenset({0}),
        runner=runner,
        update_request_path=request,
    )
    outcome = server._start_update(build_plan("app.update", {"version": "1.1.1"}))
    assert outcome["ok"] is False
    assert not request.exists()
