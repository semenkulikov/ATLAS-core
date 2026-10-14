"""Small helpers collectors share while they accumulate facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from atlas.collectors.view import CommandResult, HostView, ReadOutcome
from atlas.domain import (
    CollectorResult,
    Entity,
    Evidence,
    Fact,
    SourceDeclaration,
    SourceStatus,
    command_evidence,
    fact,
    file_evidence,
    unknown,
)


def declare(
    collector: str,
    kind: str,
    target: str,
    purpose_en: str,
    purpose_ru: str,
    *,
    requires_root: bool = False,
) -> SourceDeclaration:
    """Build one data-manifest row."""
    return SourceDeclaration(collector, kind, target, purpose_en, purpose_ru, requires_root)


@dataclass
class Bag:
    """Mutable collector output for one pass."""

    collector: str
    now: datetime
    facts: list[Fact] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    sources: list[SourceStatus] = field(default_factory=list)

    def read(self, view: HostView, path: str, *, max_bytes: int = 1_048_576) -> ReadOutcome:
        outcome = view.read(path, max_bytes=max_bytes)
        self.sources.append(SourceStatus(self.collector, path, outcome.status, outcome.reason))
        return outcome

    def command(self, view: HostView, argv: list[str], *, timeout: float = 8.0) -> CommandResult:
        result = view.runner.run(argv, timeout=timeout)
        if result.stdout or result.code == 0:
            status = "ok"
            reason = None
        elif result.code == 127:
            status = "absent"
            reason = result.stderr or "command not available"
        else:
            status = "unavailable"
            reason = result.stderr or f"exit {result.code}"
        self.sources.append(SourceStatus(self.collector, " ".join(argv), status, reason))
        return result

    def note(self, target: str, status: str, reason: str | None = None) -> None:
        self.sources.append(SourceStatus(self.collector, target, status, reason))

    def add_file(
        self,
        subject: str,
        predicate: str,
        value: str,
        path: str,
        line: int,
        quote: str,
        sha256: str | None,
        *,
        rule: str | None = None,
    ) -> None:
        self.facts.append(
            fact(
                subject,
                predicate,
                value,
                [
                    file_evidence(
                        path,
                        line,
                        quote,
                        sha256=sha256,
                        collected_at=self.now,
                    )
                ],
                collected_at=self.now,
                rule=rule,
            )
        )

    def add_command(
        self,
        subject: str,
        predicate: str,
        value: str,
        argv: list[str],
        quote: str,
        *,
        rule: str | None = None,
        extra: list[Evidence] | None = None,
    ) -> None:
        evidence = [command_evidence(argv, quote, collected_at=self.now)]
        if extra:
            evidence.extend(extra)
        self.facts.append(
            fact(
                subject,
                predicate,
                value,
                evidence,
                collected_at=self.now,
                rule=rule,
            )
        )

    def add_unknown(self, subject: str, predicate: str, reason: str) -> None:
        self.facts.append(unknown(subject, predicate, reason, collected_at=self.now))

    def entity(self, kind: str, key: str, payload: dict[str, object]) -> None:
        self.entities.append(Entity(kind, key, payload))

    def freeze(self) -> CollectorResult:
        return CollectorResult(tuple(self.facts), tuple(self.entities), tuple(self.sources))
