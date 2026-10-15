"""Install-time checks and removal of the product's own files.

Removal only touches the fixed product paths under the chosen prefix. A symlink
that points outside that prefix is refused.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from atlas import __version__
from atlas.application.actions import control_enabled
from atlas.application.alerts import list_channels
from atlas.storage.db import Store

PRODUCT_PATHS = (
    "opt/atlas",
    "etc/atlas",
    "usr/lib/systemd/system/atlas.service",
    "usr/lib/systemd/system/atlas-helper.service",
    "usr/lib/tmpfiles.d/atlas.conf",
)
DATA_PATH = "var/lib/atlas"
Runner = Callable[[list[str]], None]


def diagnose(store: Store, database: Path, *, observed_mode: int | None = None) -> list[str]:
    """Return human-readable checks. Unsafe findings start with ``warning:``."""
    notes = [f"version {__version__}"]
    mode = database.stat().st_mode & 0o777 if observed_mode is None else observed_mode
    if mode == 0o600:
        notes.append("database mode is 0600")
    else:
        notes.append(f"warning: database mode is {mode:04o}, expected 0600")
    notes.append("control is on" if control_enabled(store) else "control is off")
    enabled = [row for row in list_channels(store.conn) if row["enabled"]]
    if enabled:
        notes.append(f"warning: {len(enabled)} alert channel(s) can send data off the host")
    else:
        notes.append("alert channels are off")
    return notes


def uninstall(prefix: Path, *, purge: bool, run: Runner | None = None) -> list[str]:
    """Remove product files under ``prefix``. Data stays unless ``purge`` is set."""
    base = prefix.resolve()
    removed: list[str] = []
    for relative in PRODUCT_PATHS:
        removed.extend(_remove(base, relative))
    if purge:
        removed.extend(_remove(base, DATA_PATH))
    if base == Path("/").resolve() and run is not None:
        run(["userdel", "atlas"])
    return removed


def _remove(base: Path, relative: str) -> list[str]:
    path = (base / relative).resolve()
    if not _inside(base, path):
        raise SystemExit(f"Refusing to remove {path}, it is outside {base}.")
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        _rmtree(path)
    return [str(path)]


def _inside(base: Path, path: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _rmtree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_symlink() or child.is_file():
            if not _inside(path, child.resolve()):
                raise SystemExit(f"Refusing to remove {child}, it leaves {path}.")
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()
