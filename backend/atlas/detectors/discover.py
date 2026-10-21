"""Find projects from running anchors and describe them only with readable files."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess  # nosec B404
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from atlas.collectors.parse import port_from_proxy
from atlas.collectors.view import HostView, logical_path
from atlas.detectors.rules import apply_rules, hits_to_facts, requirement_versions
from atlas.domain import (
    CollectorResult,
    Entity,
    Fact,
    command_evidence,
    fact,
    file_evidence,
    unknown,
)
from atlas.knowledge.loader import reference_for
from atlas.redact import mask_secrets

MARKERS = (
    ".git",
    "pyproject.toml",
    "requirements.txt",
    "manage.py",
    "package.json",
    "go.mod",
    "composer.json",
    "pom.xml",
    "Cargo.toml",
    "docker-compose.yml",
    "compose.yml",
)
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".cache",
    "dist",
    "build",
}
DOC_PREFIXES = ("readme", "changelog", "architecture", "spec", "tz", "тз")
_MAX_DOCS = 200
_MAX_DOC_BYTES = 1_000_000
_MAX_DEPTH = 6


@dataclass(frozen=True, slots=True)
class Discovery:
    """Projects, documents, edges, and the facts that support them."""

    facts: tuple[Fact, ...]
    projects: tuple[dict[str, object], ...]
    edges: tuple[dict[str, str], ...]
    docs: tuple[dict[str, object], ...]


def annotate_references(results: list[CollectorResult]) -> list[CollectorResult]:
    """Attach catalog text to known units. The text stays out of the fact table."""
    annotated: list[CollectorResult] = []
    for result in results:
        entities: list[Entity] = []
        for entity in result.entities:
            if entity.kind != "service":
                entities.append(entity)
                continue
            ref = reference_for(str(entity.payload.get("unit", entity.key)))
            if ref is None:
                entities.append(entity)
                continue
            payload = dict(entity.payload)
            payload["reference"] = ref
            entities.append(Entity(entity.kind, entity.key, payload))
        annotated.append(CollectorResult(result.facts, tuple(entities), result.sources))
    return annotated


def discover(view: HostView, results: list[CollectorResult]) -> Discovery:
    """Build project cards from the anchors collectors already proved."""
    facts: list[Fact] = []
    projects: list[dict[str, object]] = []
    edges: list[dict[str, str]] = []
    docs: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for anchor_kind, directory, anchor_text, source in _anchors(results):
        root = find_root(view, directory)
        borrowed: dict[str, object] | None = None
        if root is None and view.helper_socket:
            borrowed = _borrow_project(view.helper_socket, directory)
            raw_root = borrowed.get("root") if borrowed else None
            root = raw_root if isinstance(raw_root, str) and raw_root.startswith("/") else None
        if root is None:
            continue
        key = (anchor_kind, os.path.normpath(root))
        if key in seen:
            continue
        seen.add(key)
        fingerprint = hashlib.sha256(f"{anchor_kind}\n{key[1]}".encode()).hexdigest()[:16]
        subject = f"project:{fingerprint}"
        if borrowed is None:
            hits = apply_rules(view, root, anchor_text, view.now)
            project_facts = hits_to_facts(subject, hits, view.now)
            project_facts.extend(_version_facts(view, root, subject))
            project_facts.extend(_compose_services(view, root, subject))
            project_facts.extend(_git_facts(view, root, subject))
            project_docs = _index_docs(view, root, fingerprint)
            stack = [hit.value for hit in hits]
        else:
            project_facts = []
            project_docs = _docs_from_borrow(borrowed, fingerprint)
            stack_raw = borrowed.get("stack")
            stack = [str(item) for item in stack_raw] if isinstance(stack_raw, list) else []
        if not project_docs:
            project_facts.append(
                unknown(
                    subject,
                    "project.docs",
                    "no documentation files under the project root",
                    collected_at=view.now,
                )
            )
        facts.extend(project_facts)
        docs.extend(project_docs)
        projects.append(
            {
                "project_id": fingerprint,
                "name": Path(root).name,
                "root_path": root,
                "fingerprint": fingerprint,
                "anchor_kind": anchor_kind,
                "anchor": source,
                "stack": stack,
            }
        )
        edges.append(
            {
                "src": source,
                "dst": subject,
                "kind": "anchor",
                "evidence_ref": directory,
            }
        )
    edges.extend(_port_edges(results))
    return Discovery(tuple(facts), tuple(projects), tuple(edges), tuple(docs))


def project_snapshot(view: HostView, root: str) -> dict[str, object]:
    """Describe one project the helper can read and the panel user cannot."""
    hits = apply_rules(view, root, "", view.now)
    docs: list[dict[str, object]] = []
    for doc in _index_docs(view, root, "")[:40]:
        body = doc.get("body")
        if isinstance(body, str) and len(body) > 80_000:
            doc = {**doc, "body": body[:80_000]}
        docs.append(doc)
    return {"root": root, "stack": [hit.value for hit in hits], "docs": docs}


def _borrow_project(socket_path: str, start: str) -> dict[str, object] | None:
    from atlas.helper.client import read_project

    try:
        answer = read_project(socket_path, start)
    except (OSError, ValueError):
        return None
    project = answer.get("project")
    if not answer.get("ok") or not isinstance(project, dict):
        return None
    return project


def _docs_from_borrow(borrowed: dict[str, object], project_id: str) -> list[dict[str, object]]:
    raw = borrowed.get("docs")
    if not isinstance(raw, list):
        return []
    docs: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        copied["project_id"] = project_id
        docs.append(copied)
    return docs


def find_root(view: HostView, start: str) -> str | None:
    """Walk from an anchor directory up to the nearest project marker."""
    current = start
    mapped = view.mapped(current)
    try:
        is_file = mapped.is_file()
    except OSError:
        is_file = False
    if is_file:
        current = str(Path(current).parent)
    for _ in range(_MAX_DEPTH + 2):
        if _has_marker(view, current):
            return current
        parent = str(Path(current).parent)
        if parent == current:
            return None
        current = parent
    return None


def _anchors(results: list[CollectorResult]) -> list[tuple[str, str, str, str]]:
    found: list[tuple[str, str, str, str]] = []
    for result in results:
        for entity in result.entities:
            found.extend(_entity_anchors(entity))
    return found


def _entity_anchors(entity: Entity) -> list[tuple[str, str, str, str]]:
    payload = entity.payload
    if entity.kind == "service":
        directory = payload.get("working_directory")
        command = str(payload.get("exec_start") or "")
        if isinstance(directory, str) and directory.startswith("/"):
            return [("systemd", directory, command, f"unit:{entity.key}")]
        guessed = _path_in_command(command)
        if guessed:
            return [("systemd", guessed, command, f"unit:{entity.key}")]
    if entity.kind == "container":
        labels = payload.get("labels") if isinstance(payload.get("labels"), dict) else {}
        working = (
            labels.get("com.docker.compose.project.working_dir")
            if isinstance(labels, dict)
            else None
        )
        command = str(payload.get("name") or "")
        anchors: list[tuple[str, str, str, str]] = []
        if isinstance(working, str) and working.startswith("/"):
            anchors.append(("container", working, command, f"container:{entity.key}"))
        binds = payload.get("binds")
        bind_list = binds if isinstance(binds, list) else []
        for bind in bind_list:
            source = str(bind).split(":", 1)[0]
            if source.startswith("/"):
                anchors.append(("container", source, command, f"container:{entity.key}"))
        return anchors
    if entity.kind == "schedule":
        command = str(payload.get("command") or "")
        path = _path_in_command(command)
        if path:
            return [("cron", str(Path(path).parent), command, f"schedule:{entity.key}")]
    if entity.kind == "site":
        roots_value = payload.get("roots")
        roots = roots_value if isinstance(roots_value, list) else []
        return [
            ("web", str(root), str(root), f"site:{entity.key}")
            for root in roots
            if isinstance(root, str) and root.startswith("/")
        ]
    return []


def _path_in_command(command: str) -> str | None:
    for token in command.split():
        if (
            token.startswith("/")
            and not token.startswith("/usr/sbin")
            and not token.startswith("/usr/bin")
        ):
            return token
    return None


def _has_marker(view: HostView, logical: str) -> bool:
    base = view.mapped(logical)
    try:
        if not base.is_dir() or base.is_symlink():
            return False
    except OSError:
        return False
    for marker in MARKERS:
        candidate = base / marker
        try:
            present = candidate.exists()
        except OSError:
            continue
        if present:
            return True
    return False


def _version_facts(view: HostView, root: str, subject: str) -> list[Fact]:
    outcome = view.read(str(Path(root) / "requirements.txt"))
    if not outcome.ok or outcome.text is None:
        return []
    facts: list[Fact] = []
    for line, name, version in requirement_versions(outcome.text)[:40]:
        if version:
            facts.append(
                fact(
                    subject,
                    f"dependency.{name}",
                    version,
                    [
                        file_evidence(
                            str(Path(root) / "requirements.txt"),
                            line,
                            f"{name}=={version}",
                            sha256=outcome.sha256,
                            collected_at=view.now,
                        )
                    ],
                    collected_at=view.now,
                )
            )
        else:
            facts.append(
                unknown(
                    subject,
                    f"dependency.{name}",
                    "dependency is not pinned",
                    collected_at=view.now,
                )
            )
    return facts


def _compose_services(view: HostView, root: str, subject: str) -> list[Fact]:
    for name in ("docker-compose.yml", "compose.yml"):
        logical = str(Path(root) / name)
        outcome = view.read(logical)
        if not outcome.ok or outcome.text is None:
            continue
        try:
            loaded = yaml.safe_load(outcome.text)
        except yaml.YAMLError:
            return [
                unknown(
                    subject,
                    "compose.services",
                    "compose file could not be parsed",
                    collected_at=view.now,
                )
            ]
        services = loaded.get("services") if isinstance(loaded, dict) else None
        if not isinstance(services, dict):
            return []
        return [
            fact(
                subject,
                "compose.service",
                str(service),
                [
                    file_evidence(
                        logical,
                        1,
                        f"services.{service}",
                        sha256=outcome.sha256,
                        collected_at=view.now,
                    )
                ],
                collected_at=view.now,
                rule="stack.compose.service",
            )
            for service in list(services)[:30]
        ]
    return []


def _git_facts(view: HostView, root: str, subject: str) -> list[Fact]:
    try:
        has_git = (view.mapped(root) / ".git").exists()
    except OSError:
        has_git = False
    if not has_git:
        return [unknown(subject, "git.branch", "no git directory", collected_at=view.now)]
    facts: list[Fact] = []
    head = view.read(str(Path(root) / ".git" / "HEAD"))
    if head.ok and head.text:
        facts.append(
            fact(
                subject,
                "git.head",
                head.text.strip(),
                [
                    file_evidence(
                        str(Path(root) / ".git" / "HEAD"),
                        1,
                        head.text.strip(),
                        sha256=head.sha256,
                        collected_at=view.now,
                    )
                ],
                collected_at=view.now,
            )
        )
    mapped = str(view.mapped(root))
    log = _git(mapped, ["log", "-1", "--format=%H%n%cI%n%an"])
    if log and len(log.splitlines()) >= 3:
        commit, when, author = log.splitlines()[:3]
        facts.append(
            fact(
                subject,
                "git.commit",
                commit,
                [command_evidence(["git", "log", "-1"], log, collected_at=view.now)],
                collected_at=view.now,
            )
        )
        facts.append(
            fact(
                subject,
                "git.author",
                author,
                [command_evidence(["git", "log", "-1"], author, collected_at=view.now)],
                collected_at=view.now,
            )
        )
        facts.append(
            fact(
                subject,
                "git.committed_at",
                when,
                [command_evidence(["git", "log", "-1"], when, collected_at=view.now)],
                collected_at=view.now,
            )
        )
    else:
        facts.append(
            unknown(subject, "git.commit", "git log is unavailable", collected_at=view.now)
        )
    remote = _git(mapped, ["remote", "get-url", "origin"])
    if remote:
        facts.append(
            fact(
                subject,
                "git.remote",
                _strip_remote(remote),
                [
                    command_evidence(
                        ["git", "remote", "get-url", "origin"], remote, collected_at=view.now
                    )
                ],
                collected_at=view.now,
            )
        )
    status = _git(mapped, ["status", "--porcelain"])
    if status is not None:
        dirty = "yes" if status.strip() else "no"
        facts.append(
            fact(
                subject,
                "git.dirty",
                dirty,
                [
                    command_evidence(
                        ["git", "status", "--porcelain"], status or "clean", collected_at=view.now
                    )
                ],
                collected_at=view.now,
                rule="git.status",
            )
        )
    return facts


def _git(path: str, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(  # nosec B603 B607
            ["git", "-C", path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _strip_remote(url: str) -> str:
    masked = mask_secrets(url.strip())
    return masked


def _index_docs(view: HostView, root: str, project_id: str) -> list[dict[str, object]]:
    base = view.mapped(root)
    try:
        readable = base.is_dir()
    except OSError:
        readable = False
    if not readable:
        return []
    found: list[dict[str, object]] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        relative = Path(dirpath).relative_to(base)
        depth = 0 if str(relative) == "." else len(relative.parts)
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [
            name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")
        ]
        for filename in filenames:
            if len(found) >= _MAX_DOCS:
                return found
            if not _is_doc(filename, depth):
                continue
            path = Path(dirpath) / filename
            try:
                if path.is_symlink():
                    continue
                stat = path.stat()
            except OSError:
                continue
            logical = logical_path(view, path)
            outcome = view.read(logical, max_bytes=_MAX_DOC_BYTES)
            if not outcome.ok or outcome.text is None:
                continue
            body = _plain_text(mask_secrets(outcome.text))
            found.append(
                {
                    "project_id": project_id,
                    "path": logical,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                    "sha256": outcome.sha256,
                    "body": body,
                }
            )
    return found


def _plain_text(text: str) -> str:
    """Drop HTML tags so a README cannot carry a script into the panel."""
    return re.sub(r"<[^>]{0,200}>", "", text)


def _is_doc(filename: str, depth: int) -> bool:
    lowered = filename.lower()
    if lowered.startswith(DOC_PREFIXES):
        return True
    if lowered.endswith(".md"):
        return True
    if lowered in {"openapi.yaml", "openapi.yml", "openapi.json"}:
        return True
    return depth > 0 and lowered.endswith(".rst")


def _port_edges(results: list[CollectorResult]) -> list[dict[str, str]]:
    sites: list[Entity] = []
    ports: list[Entity] = []
    for result in results:
        for entity in result.entities:
            if entity.kind == "site":
                sites.append(entity)
            elif entity.kind == "port":
                ports.append(entity)
    edges: list[dict[str, str]] = []
    for site in sites:
        proxies_value = site.payload.get("proxies")
        proxies = proxies_value if isinstance(proxies_value, list) else []
        for proxy in proxies:
            port = port_from_proxy(str(proxy))
            if port is None:
                continue
            for listener in ports:
                if listener.payload.get("port") == port:
                    edges.append(
                        {
                            "src": f"site:{site.key}",
                            "dst": listener.key,
                            "kind": "proxy",
                            "evidence_ref": str(proxy),
                        }
                    )
    return edges
