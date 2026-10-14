"""Read a host, or a fixture directory that stands in for one, without touching secrets."""

from __future__ import annotations

import hashlib
import os

# Commands are argv lists. The shell is never invoked.
import subprocess  # nosec B404
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol

from atlas.redact import env_key_names

FORBIDDEN_BASENAMES = frozenset(
    {
        "shadow",
        "shadow-",
        "gshadow",
        "gshadow-",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
_PRIVATE_KEY_MARK = "PRIVATE KEY"


def is_forbidden_path(path: str) -> bool:
    """Return whether ``path`` points at material ATLAS must never read."""
    name = PurePosixPath(path).name
    if name in FORBIDDEN_BASENAMES:
        return True
    stem = name.split(".", 1)[0]
    return stem in FORBIDDEN_BASENAMES


def is_env_file(path: str) -> bool:
    """Return whether ``path`` is an environment file whose values must be dropped."""
    name = PurePosixPath(path).name
    return name == ".env" or name.startswith(".env.")


@dataclass(frozen=True, slots=True)
class ReadOutcome:
    """Result of one file read."""

    path: str
    status: str
    text: str | None
    reason: str | None
    sha256: str | None

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.text is not None


def _outcome(
    path: str,
    status: str,
    text: str | None = None,
    reason: str | None = None,
    sha256: str | None = None,
) -> ReadOutcome:
    return ReadOutcome(path, status, text, reason, sha256)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured output of one argv command. The shell is never involved."""

    argv: tuple[str, ...]
    code: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Run a command by argv."""

    def run(self, argv: list[str], timeout: float = 8.0) -> CommandResult:
        """Return the command result. A missing binary has code 127."""


class SubprocessRunner:
    """Run commands on the machine ATLAS is scanning."""

    def run(self, argv: list[str], timeout: float = 8.0) -> CommandResult:
        try:
            completed = subprocess.run(  # nosec B603
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(tuple(argv), 127, "", str(exc))
        return CommandResult(
            tuple(argv),
            completed.returncode,
            completed.stdout[:1_000_000],
            completed.stderr[:20_000],
        )


class FixtureRunner:
    """Return scripted command output from ``commands.json`` and never touch the host."""

    def __init__(self, root: Path) -> None:
        import json

        path = root / "commands.json"
        self._commands: dict[str, dict[str, object]] = {}
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._commands = {str(key): value for key, value in loaded.items()}

    def run(self, argv: list[str], timeout: float = 8.0) -> CommandResult:
        del timeout
        entry = self._commands.get(" ".join(argv))
        if entry is None:
            return CommandResult(tuple(argv), 127, "", "not in fixture")
        stdout = entry.get("stdout", "")
        stderr = entry.get("stderr", "")
        code = entry.get("code", 0)
        return CommandResult(
            tuple(argv),
            int(code) if isinstance(code, int) else 0,
            stdout if isinstance(stdout, str) else "",
            stderr if isinstance(stderr, str) else "",
        )


@dataclass
class HostView:
    """Filesystem and command view. Fixture roots cannot see the real host."""

    root: Path
    runner: CommandRunner
    now: datetime
    files_read: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.root.resolve() == Path("/").resolve()

    def mapped(self, path: str) -> Path:
        """Map a host path into this view. Fixture reads stay under ``root``."""
        if self.is_live:
            return Path(path)
        return self.root / path.lstrip("/")

    def read(self, path: str, *, max_bytes: int = 1_048_576) -> ReadOutcome:
        """Read a text file. Secrets are refused or reduced to key names."""
        if is_forbidden_path(path):
            return _outcome(path, "unavailable", reason="secret material is never read")
        target = self.mapped(path)
        try:
            resolved = target.resolve(strict=True)
        except FileNotFoundError:
            return _outcome(path, "absent", reason="file not found")
        except OSError as exc:
            return _outcome(path, "unavailable", reason=exc.strerror or "unreadable")
        if not self.is_live and not _is_inside(resolved, self.root.resolve()):
            return _outcome(path, "unavailable", reason="path escapes the scan root")
        if is_forbidden_path(str(resolved)):
            return _outcome(path, "unavailable", reason="secret material is never read")
        try:
            data = resolved.read_bytes()
        except PermissionError:
            return _outcome(path, "unavailable", reason="permission denied")
        except OSError as exc:
            return _outcome(path, "unavailable", reason=exc.strerror or "unreadable")
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        if _PRIVATE_KEY_MARK in text:
            return _outcome(path, "unavailable", reason="private key material is never read")
        digest = None if truncated else hashlib.sha256(data).hexdigest()
        reason = "truncated" if truncated else None
        if is_env_file(path):
            names = env_key_names(text)
            return _outcome(
                path, "ok", "\n".join(names), reason or "values are not collected", None
            )
        return _outcome(path, "ok", text, reason, digest)

    def fixture_json(self, name: str) -> object | None:
        """Load a JSON document that exists only in a fixture, never on a live host."""
        if self.is_live:
            return None
        path = self.root / name
        if not path.is_file():
            return None
        import json

        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        return loaded


def open_view(root: Path, now: datetime | None = None) -> HostView:
    """Open a live view for ``/`` and a fixture view for any other directory."""
    moment = now or datetime.now(UTC)
    if root.resolve() == Path("/").resolve():
        return HostView(root, SubprocessRunner(), moment)
    return HostView(root, FixtureRunner(root), moment)


def logical_path(view: HostView, path: Path) -> str:
    """Return the host path for a file inside the view."""
    if view.is_live:
        return str(path)
    relative = path.relative_to(view.root)
    return "/" + relative.as_posix()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def try_lower_priority() -> None:
    """Ask the kernel to run this collector behind real work. Failure is ignored."""
    try:
        os.nice(19)
    except OSError:
        return
    try:
        subprocess.run(  # nosec B603 B607
            ["ionice", "-c", "3", "-p", str(os.getpid())],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
