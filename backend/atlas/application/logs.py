"""Read log lines on demand and mask them before they leave this module.

ATLAS does not copy logs into its own database. A path has to stay inside the
scan root, and names that hold credentials are refused.
"""

from __future__ import annotations

import re
import subprocess  # nosec B404
from pathlib import Path

from atlas.collectors.view import is_forbidden_path
from atlas.redact import env_key_names, mask_secrets

_UNIT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-")


class LogError(Exception):
    """The requested log source cannot be read."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def read_log(
    root: Path,
    source: str,
    limit: int,
    *,
    query: str = "",
    pattern: str = "",
) -> dict[str, object]:
    """Return the newest lines from a file under ``root`` or from journald."""
    bounded = max(1, min(limit, 500))
    if source.startswith("journal:"):
        lines = _journal(source.removeprefix("journal:"), bounded)
        return {"status": "ok", "source": source, "lines": _select(lines, query, pattern)}
    path = _inside_root(root, source)
    if path.name == ".env" or path.name.endswith(".env"):
        text = "\n".join(env_key_names(path.read_text(encoding="utf-8", errors="replace")))
    else:
        text = _tail_text(path, bounded)
    if "PRIVATE KEY" in text:
        raise LogError("This file looks like a private key and is not shown.")
    lines = [mask_secrets(line)[:2000] for line in text.splitlines()[-bounded:]]
    return {"status": "ok", "source": source, "lines": _select(lines, query, pattern)}


def _select(lines: list[str], query: str, pattern: str) -> list[str]:
    if len(pattern) > 80 or "(+" in pattern or ")+" in pattern or "*)" in pattern:
        raise LogError("The pattern is too broad.")
    chosen = lines
    if pattern:
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise LogError("The pattern is not a valid expression.") from exc
        chosen = [line for line in chosen if compiled.search(line)]
    if query:
        chosen = [line for line in chosen if query in line]
    return chosen


def _inside_root(root: Path, source: str) -> Path:
    if source.startswith("/") or ".." in Path(source).parts:
        raise LogError("The log path has to stay inside the scan root.")
    if is_forbidden_path(source):
        raise LogError("This path is never read.")
    candidate = (root / source).resolve()
    root_resolved = root.resolve()
    if not candidate.is_relative_to(root_resolved):
        raise LogError("The log path has to stay inside the scan root.")
    if not candidate.is_file():
        raise LogError("The log file is not there.")
    return candidate


def _tail_text(path: Path, limit: int) -> str:
    data = path.read_bytes()
    chunk = data[-(limit * 1024) :]
    return chunk.decode("utf-8", errors="replace")


def _journal(unit: str, limit: int) -> list[str]:
    if not unit or any(char not in _UNIT for char in unit):
        raise LogError("The unit name is not usable.")
    try:
        completed = subprocess.run(  # nosec B603 B607
            ["journalctl", "-u", unit, "-n", str(limit), "--no-pager", "-o", "cat"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LogError("journalctl is not available.") from exc
    if completed.returncode != 0 and not completed.stdout:
        raise LogError("journalctl could not read that unit.")
    return [mask_secrets(line)[:2000] for line in completed.stdout.splitlines()[-limit:]]
