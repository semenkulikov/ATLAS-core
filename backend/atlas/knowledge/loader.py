"""Reference descriptions for well-known services. These are not facts about a host."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_CATALOG = Path(__file__).resolve().parent / "services.yaml"


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict[str, str]]:
    """Load the built-in service catalog once."""
    loaded = yaml.safe_load(_CATALOG.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    rows: dict[str, dict[str, str]] = {}
    for key, value in loaded.items():
        if isinstance(value, dict):
            rows[str(key)] = {str(item_key): str(item) for item_key, item in value.items()}
    return rows


def reference_for(unit_name: str) -> dict[str, str] | None:
    """Return catalog text for a unit, or None when the unit is not in the catalog.

    The result is reference text. Callers must not store it as a fact.
    """
    stem = unit_name.split(".", 1)[0].split("@", 1)[0].lower()
    if len(stem) < 3:
        return None
    for key, row in catalog().items():
        if key == stem or key.startswith(stem) or stem.startswith(key):
            return {
                "source": "knowledge",
                "name": row.get("name", key),
                "summary_en": row.get("summary_en", ""),
                "summary_ru": row.get("summary_ru", ""),
            }
    return None
