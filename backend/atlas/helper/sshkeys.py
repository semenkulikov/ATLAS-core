"""Edit authorized_keys without invoking a shell.

The previous file is copied aside first. A line that is not a public key is
left untouched and the write is refused.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from atlas.helper.protocol import PUBLIC_KEY, ProtocolError


def authorized_keys_path(root: Path, username: str) -> Path:
    """Return the keys file for ``username`` inside ``root``."""
    home = root / "root" if username == "root" else root / "home" / username
    return home / ".ssh" / "authorized_keys"


def change_key(root: Path, username: str, key: str, *, remove: bool) -> str:
    """Add or remove one public key. Returns a short result sentence."""
    line = key.strip()
    if PUBLIC_KEY.fullmatch(line) is None or "PRIVATE KEY" in line:
        raise ProtocolError("The SSH line is not a public key.")
    path = authorized_keys_path(root, username)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = [item for item in current.splitlines() if item.strip()]
    if remove:
        kept = [item for item in lines if item.strip() != line]
        if len(kept) == len(lines):
            raise ProtocolError("That key is not in the file.")
        lines = kept
        verb = "removed"
    else:
        if line not in lines:
            lines.append(line)
        verb = "added"
    if path.is_file():
        shutil.copy2(path, path.with_name("authorized_keys.atlas.bak"))
    path.write_text("".join(f"{item}\n" for item in lines), encoding="utf-8")
    path.chmod(0o600)
    return f"{verb} a public key for {username}"
