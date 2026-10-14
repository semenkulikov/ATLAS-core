"""Domain rules: a claim without proof cannot be stored as a fact."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.domain import (
    Certainty,
    Evidence,
    EvidenceKind,
    Fact,
    api_evidence,
    command_evidence,
    fact,
    failed_collector,
    file_evidence,
    process_evidence,
    unknown,
)

CANARY = "ATLAS_CANARY_7f3a9c"
NOW = datetime(2026, 10, 14, tzinfo=UTC)


def test_direct_fact_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        fact("host", "os.id", "ubuntu", [], collected_at=NOW)


def test_derived_fact_names_its_rule() -> None:
    proof = file_evidence(
        "/etc/a", 1, "proxy_pass http://127.0.0.1:8000;", sha256=None, collected_at=NOW
    )
    derived = fact(
        "site:shop", "site.proxy_port", "8000", [proof], collected_at=NOW, rule="proxy_pass.port"
    )
    assert derived.certainty is Certainty.DERIVED
    assert derived.rule == "proxy_pass.port"
    assert derived.evidence[0].kind is EvidenceKind.FILE


def test_unknown_fact_keeps_the_reason() -> None:
    missing = unknown("host", "virt.type", "systemd-detect-virt is unavailable", collected_at=NOW)
    assert missing.certainty is Certainty.UNKNOWN
    assert missing.evidence == ()
    assert "unavailable" in missing.value


def test_evidence_and_values_mask_secrets() -> None:
    proof = file_evidence(
        "/etc/nginx/site.conf",
        4,
        f'proxy_set_header Authorization "Bearer {CANARY}";',
        sha256="abc",
        collected_at=NOW,
    )
    stored = fact("site:shop", "site.header", f"token={CANARY}", [proof], collected_at=NOW)
    assert CANARY not in proof.excerpt
    assert CANARY not in stored.value
    assert len(proof.excerpt) <= 200


def test_a_claim_without_a_subject_or_a_reference_is_refused() -> None:
    proof = file_evidence("/etc/os-release", 1, "ID=ubuntu", sha256=None, collected_at=NOW)
    with pytest.raises(ValueError, match="reference"):
        Evidence(EvidenceKind.FILE, "", "ID=ubuntu", None, NOW)
    with pytest.raises(ValueError, match="subject"):
        Fact("host", "", "ubuntu", Certainty.FACT, (proof,), NOW)
    with pytest.raises(ValueError, match="explains"):
        unknown("host", "virt.type", "", collected_at=NOW)
    with pytest.raises(ValueError, match="names its rule"):
        Fact("host", "os.id", "ubuntu", Certainty.DERIVED, (proof,), NOW)
    with pytest.raises(ValueError, match="has no rule"):
        Fact("host", "os.id", "ubuntu", Certainty.FACT, (proof,), NOW, rule="guess")
    assert command_evidence(["uname"], "Linux", collected_at=NOW).kind is EvidenceKind.COMMAND
    assert api_evidence("/containers/json", "[]", collected_at=NOW).kind is EvidenceKind.API
    assert process_evidence(1, "systemd", collected_at=NOW).kind is EvidenceKind.PROCESS
    failed = failed_collector("os", "collector raised", NOW)
    assert failed.facts[0].certainty is Certainty.UNKNOWN
    assert failed.sources[0].status == "unavailable"
