"""Domain rules: a claim without proof cannot be stored as a fact."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.domain import Certainty, EvidenceKind, fact, file_evidence, unknown

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
