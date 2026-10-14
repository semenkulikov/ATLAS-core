"""Facts, evidence, and the records a scan persists.

A direct fact is something ATLAS read. A derived fact names the rule that
produced it. An unknown fact is an explanation, never a guess presented as data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.redact import excerpt, mask_secrets


class Certainty(StrEnum):
    FACT = "fact"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class EvidenceKind(StrEnum):
    FILE = "file"
    COMMAND = "command"
    API = "api"
    PROCESS = "process"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One proof: a file line, a command, an API reply, or a process."""

    kind: EvidenceKind
    ref: str
    excerpt: str
    file_sha256: str | None
    collected_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "excerpt", excerpt(self.excerpt))
        if not self.ref:
            raise ValueError("evidence needs a reference")


@dataclass(frozen=True, slots=True)
class Fact:
    """One claim about the host."""

    subject: str
    predicate: str
    value: str
    certainty: Certainty
    evidence: tuple[Evidence, ...]
    collected_at: datetime
    rule: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", mask_secrets(self.value))
        if not self.subject or not self.predicate:
            raise ValueError("a fact needs a subject and a predicate")
        if self.certainty is Certainty.UNKNOWN:
            if not self.value:
                raise ValueError("an unknown fact explains why")
            return
        if not self.evidence:
            raise ValueError("facts need evidence")
        if self.certainty is Certainty.DERIVED and not self.rule:
            raise ValueError("a derived fact names its rule")
        if self.certainty is Certainty.FACT and self.rule is not None:
            raise ValueError("a direct fact has no rule name")


def file_evidence(
    path: str,
    line: int,
    quote: str,
    *,
    sha256: str | None,
    collected_at: datetime,
) -> Evidence:
    """Build evidence that points at a file line."""
    return Evidence(
        kind=EvidenceKind.FILE,
        ref=f"{path}:{line}",
        excerpt=quote,
        file_sha256=sha256,
        collected_at=collected_at,
    )


def command_evidence(argv: list[str], quote: str, *, collected_at: datetime) -> Evidence:
    """Build evidence that points at a command and a short slice of its output."""
    return Evidence(
        kind=EvidenceKind.COMMAND,
        ref=" ".join(argv),
        excerpt=quote,
        file_sha256=None,
        collected_at=collected_at,
    )


def api_evidence(ref: str, quote: str, *, collected_at: datetime) -> Evidence:
    """Build evidence that points at an engine API path."""
    return Evidence(
        kind=EvidenceKind.API,
        ref=ref,
        excerpt=quote,
        file_sha256=None,
        collected_at=collected_at,
    )


def process_evidence(pid: int, quote: str, *, collected_at: datetime) -> Evidence:
    """Build evidence that points at a process."""
    return Evidence(
        kind=EvidenceKind.PROCESS,
        ref=f"pid:{pid}",
        excerpt=quote,
        file_sha256=None,
        collected_at=collected_at,
    )


def fact(
    subject: str,
    predicate: str,
    value: str,
    evidence: list[Evidence] | tuple[Evidence, ...],
    *,
    collected_at: datetime,
    rule: str | None = None,
) -> Fact:
    """Build a direct fact, or a derived fact when ``rule`` is set."""
    certainty = Certainty.DERIVED if rule else Certainty.FACT
    return Fact(
        subject=subject,
        predicate=predicate,
        value=value,
        certainty=certainty,
        evidence=tuple(evidence),
        collected_at=collected_at,
        rule=rule,
    )


def unknown(
    subject: str,
    predicate: str,
    reason: str,
    *,
    collected_at: datetime,
    evidence: tuple[Evidence, ...] = (),
) -> Fact:
    """Build an unknown fact. ``reason`` is shown to the operator as the value."""
    return Fact(
        subject=subject,
        predicate=predicate,
        value=reason,
        certainty=Certainty.UNKNOWN,
        evidence=evidence,
        collected_at=collected_at,
        rule=None,
    )


@dataclass(frozen=True, slots=True)
class Entity:
    """A table row derived from facts: a unit, a port, a user, a project."""

    kind: str
    key: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class SourceStatus:
    """Whether a declared source could be read."""

    collector: str
    target: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CollectorResult:
    """Everything one collector learned in a single pass."""

    facts: tuple[Fact, ...]
    entities: tuple[Entity, ...]
    sources: tuple[SourceStatus, ...]


@dataclass(frozen=True, slots=True)
class SourceDeclaration:
    """A collector's public promise about what it reads. The data manifest is built from these."""

    collector: str
    kind: str
    target: str
    purpose_en: str
    purpose_ru: str
    requires_root: bool


def failed_collector(name: str, reason: str, when: datetime) -> CollectorResult:
    """A collector that raised still produces an unknown fact instead of aborting the scan."""
    return CollectorResult(
        facts=(
            unknown(
                f"collector:{name}",
                "status",
                reason,
                collected_at=when,
            ),
        ),
        entities=(),
        sources=(SourceStatus(name, name, "unavailable", reason),),
    )
