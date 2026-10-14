"""Process settings for the panel. The defaults keep the listener off the network."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """How the API process may be reached."""

    root: Path
    tls: bool = False
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    allowed_ips: tuple[str, ...] = ()
    session_idle_seconds: int = 30 * 60
    bootstrap_ttl_seconds: int = 15 * 60
    public_bind: bool = False
    helper_socket: str = ""


def refuse_public_bind(host: str, *, tls: bool, allowed_ips: tuple[str, ...]) -> None:
    """Refuse a non-loopback listener that is missing TLS or an address allow list."""
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    if tls and allowed_ips:
        return
    raise SystemExit(
        "Refusing to listen on a public address without TLS and an address allow list."
    )
