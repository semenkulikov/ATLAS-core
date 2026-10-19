"""Compare the installed ATLAS version with the latest GitHub release."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from atlas import __version__

_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DEFAULT_REPO = "semenkulikov/ATLAS-core"
_CACHE_SECONDS = 300.0

_cache: dict[str, object] = {"fetched_at": 0.0, "latest": None, "error": None}


def parse_tag(tag: str) -> str | None:
    """Return ``X.Y.Z`` from a release tag, or ``None`` when the tag is unusable."""
    cleaned = tag.strip()
    if cleaned.startswith("v") or cleaned.startswith("V"):
        cleaned = cleaned[1:]
    if _VERSION.fullmatch(cleaned) is None:
        return None
    return cleaned


def version_tuple(version: str) -> tuple[int, int, int]:
    """Split a validated ``X.Y.Z`` string into comparable integers."""
    major, minor, patch = version.split(".", 2)
    return int(major), int(minor), int(patch)


def is_newer(candidate: str, current: str) -> bool:
    """Return whether ``candidate`` is strictly newer than ``current``."""
    return version_tuple(candidate) > version_tuple(current)


def latest_from_payload(payload: object) -> str | None:
    """Pull the latest tag from a GitHub ``/releases/latest`` JSON body."""
    if not isinstance(payload, dict):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        return None
    return parse_tag(tag)


def fetch_latest(
    *,
    repo: str = _DEFAULT_REPO,
    opener: Callable[[str], object] | None = None,
    now: Callable[[], float] | None = None,
    cache_seconds: float = _CACHE_SECONDS,
) -> dict[str, object]:
    """Return ``current``, ``latest``, and whether an update is available.

    Network failures leave ``latest`` empty and set ``error``. The current
    process version is always returned.
    """
    clock = now or time.time
    stamped = clock()
    cached_at = float(_cache.get("fetched_at") or 0.0)
    if stamped - cached_at < cache_seconds and _cache.get("latest") is not None:
        latest = str(_cache["latest"])
        return {
            "current": __version__,
            "latest": latest,
            "update_available": is_newer(latest, __version__),
            "error": None,
        }

    error: str | None = None
    latest: str | None = None
    try:
        payload = (opener or _http_get)(f"https://api.github.com/repos/{repo}/releases/latest")
        latest = latest_from_payload(payload)
        if latest is None:
            error = "The latest release tag is not a version."
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        error = str(exc) or exc.__class__.__name__

    if latest is not None:
        _cache["fetched_at"] = stamped
        _cache["latest"] = latest
        _cache["error"] = None
    else:
        _cache["error"] = error

    return {
        "current": __version__,
        "latest": latest,
        "update_available": bool(latest and is_newer(latest, __version__)),
        "error": error,
    }


def clear_cache() -> None:
    """Drop the in-process GitHub cache (tests)."""
    _cache["fetched_at"] = 0.0
    _cache["latest"] = None
    _cache["error"] = None


def _http_get(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ATLAS/{__version__}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.loads(response.read().decode("utf-8"))
