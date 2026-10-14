"""Declarative stack rules. A rule fires only when every condition is readable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from atlas.collectors.view import HostView
from atlas.domain import Evidence, Fact, command_evidence, fact, file_evidence

_RULES = Path(__file__).resolve().parent / "rules" / "stacks.yaml"
_TOKEN = re.compile(r"[a-z0-9][a-z0-9._+-]*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RuleHit:
    rule: str
    predicate: str
    value: str
    evidence: tuple[Evidence, ...]


def load_rules() -> list[dict[str, object]]:
    """Read the built-in stack rules."""
    loaded = yaml.safe_load(_RULES.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def apply_rules(
    view: HostView,
    logical_root: str,
    anchor_text: str,
    when: datetime,
) -> list[RuleHit]:
    """Return the stack rules that match this project root."""
    hits: list[RuleHit] = []
    for rule in load_rules():
        hit = _apply_one(view, logical_root, anchor_text, when, rule)
        if hit is not None:
            hits.append(hit)
    return hits


def requirement_versions(text: str) -> list[tuple[int, str, str | None]]:
    """Return ``(line, name, exact version or None)`` from a requirements file."""
    found: list[tuple[int, str, str | None]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", ".")):
            continue
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
        if not name or not _TOKEN.fullmatch(name):
            continue
        version = None
        if "==" in line:
            version = line.split("==", 1)[1].split(";", 1)[0].strip() or None
        found.append((number, name, version))
    return found


def _apply_one(
    view: HostView,
    logical_root: str,
    anchor_text: str,
    when: datetime,
    rule: dict[str, object],
) -> RuleHit | None:
    evidence: list[Evidence] = []
    if "all" in rule:
        conditions = rule["all"]
        if not isinstance(conditions, list) or not _all(
            view, logical_root, anchor_text, when, conditions, evidence
        ):
            return None
    elif "any" in rule:
        conditions = rule["any"]
        if not isinstance(conditions, list) or not _any(
            view, logical_root, anchor_text, when, conditions, evidence
        ):
            return None
    else:
        return None
    value = rule.get("value")
    if rule.get("value_from") == "go.mod":
        module = _go_module(view, logical_root)
        value = module or "Go module"
    if not isinstance(value, str) or not evidence:
        return None
    rule_name = str(rule.get("rule", rule.get("name", "stack")))
    return RuleHit(rule_name, str(rule["predicate"]), value, tuple(evidence))


def hits_to_facts(subject: str, hits: list[RuleHit], when: datetime) -> list[Fact]:
    """Turn rule hits into derived facts."""
    return [
        fact(
            subject,
            hit.predicate,
            hit.value,
            list(hit.evidence),
            collected_at=when,
            rule=hit.rule,
        )
        for hit in hits
    ]


def _all(
    view: HostView,
    logical_root: str,
    anchor_text: str,
    when: datetime,
    conditions: list[object],
    evidence: list[Evidence],
) -> bool:
    for condition in conditions:
        if not isinstance(condition, dict):
            return False
        if "any" in condition:
            nested = condition["any"]
            if not isinstance(nested, list) or not _any(
                view, logical_root, anchor_text, when, nested, evidence
            ):
                return False
            continue
        ok, proof = _condition(view, logical_root, anchor_text, when, condition)
        if not ok:
            return False
        if proof is not None:
            evidence.append(proof)
    return True


def _any(
    view: HostView,
    logical_root: str,
    anchor_text: str,
    when: datetime,
    conditions: list[object],
    evidence: list[Evidence],
) -> bool:
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        ok, proof = _condition(view, logical_root, anchor_text, when, condition)
        if ok:
            if proof is not None:
                evidence.append(proof)
            return True
    return False


def _condition(
    view: HostView,
    logical_root: str,
    anchor_text: str,
    when: datetime,
    condition: dict[str, object],
) -> tuple[bool, Evidence | None]:
    relative = str(condition.get("path", ""))
    if relative == "anchor.txt":
        needle = str(condition.get("contains", ""))
        if needle and needle.lower() in anchor_text.lower():
            return True, command_evidence(["anchor"], anchor_text[:200], collected_at=when)
        return False, None
    logical = str(Path(logical_root) / relative)
    if "exists" in condition:
        outcome = view.read(logical)
        wanted = bool(condition["exists"])
        present = outcome.ok
        if wanted != present:
            return False, None
        if not wanted:
            return True, None
        quote = (outcome.text or "").splitlines()[:1]
        return True, file_evidence(
            logical,
            1,
            quote[0] if quote else relative,
            sha256=outcome.sha256,
            collected_at=when,
        )
    needle = str(condition.get("contains", "")).lower()
    if not needle:
        return False, None
    outcome = view.read(logical)
    if not outcome.ok or outcome.text is None:
        return False, None
    pattern = re.compile(rf"(?i)(?:^|[^a-z0-9]){re.escape(needle)}(?:[^a-z0-9]|$)")
    for number, line in enumerate(outcome.text.splitlines(), start=1):
        if pattern.search(line):
            return True, file_evidence(
                logical,
                number,
                line.strip(),
                sha256=outcome.sha256,
                collected_at=when,
            )
    return False, None


def _go_module(view: HostView, logical_root: str) -> str | None:
    outcome = view.read(str(Path(logical_root) / "go.mod"))
    if not outcome.ok or outcome.text is None:
        return None
    for line in outcome.text.splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return None
