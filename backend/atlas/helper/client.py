"""Talk to the root helper over its Unix socket."""

from __future__ import annotations

import json
import socket
from typing import Any


def call_helper(path: str, request: dict[str, object]) -> dict[str, object]:
    """Send one JSON request and return the JSON answer."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(path)
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        raw = b""
        while b"\n" not in raw and len(raw) < 4_000_000:
            chunk = client.recv(65536)
            if not chunk:
                break
            raw += chunk
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise OSError("the helper answer is not an object")
    return payload


def read_file(path: str, target: str) -> dict[str, object]:
    """Ask the helper for one allowlisted file."""
    return call_helper(path, {"op": "read.file", "params": {"path": target}})


def read_engine(path: str, route: str) -> dict[str, object]:
    """Ask the helper for one allowlisted Docker Engine GET."""
    return call_helper(path, {"op": "read.engine", "params": {"path": route}})


def read_command(path: str, argv: list[str]) -> dict[str, object]:
    """Ask the helper for one fixed inventory command."""
    return call_helper(path, {"op": "read.command", "params": {"argv": argv}})


def engine_bundle(path: str) -> dict[str, Any] | None:
    """Return the four engine documents, or ``None`` when the helper refuses."""
    payload: dict[str, Any] = {}
    routes = (
        ("containers", "/containers/json?all=1"),
        ("images", "/images/json"),
        ("networks", "/networks"),
        ("volumes", "/volumes"),
    )
    for key, route in routes:
        answer = read_engine(path, route)
        if not answer.get("ok"):
            return None
        payload[key] = answer.get("body")
    return payload
