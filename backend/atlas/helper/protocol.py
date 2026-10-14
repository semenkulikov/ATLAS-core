"""Typed operations the root helper is allowed to run.

The web process never builds a shell command. Each operation becomes a fixed
argument list, and a protected unit is refused unless the caller sets force.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_UNIT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9:._@-]{0,127}$")
_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
_USER = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
PUBLIC_KEY = re.compile(
    r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256|sk-ssh-ed25519@openssh.com) "
    r"[A-Za-z0-9+/=]+(?: [\x20-\x7e]{0,80})?$"
)

PROTECTED_UNITS = frozenset(
    {
        "sshd.service",
        "ssh.service",
        "atlas.service",
        "atlas-helper.service",
        "NetworkManager.service",
        "systemd-networkd.service",
        "networking.service",
    }
)
PROTECTED_ACCOUNTS = frozenset({"root", "atlas"})

_SERVICE = {
    "service.start": "start",
    "service.stop": "stop",
    "service.restart": "restart",
    "service.enable": "enable",
    "service.disable": "disable",
}
_CONTAINER = {
    "container.start": "start",
    "container.stop": "stop",
    "container.restart": "restart",
    "container.pause": "pause",
    "container.remove": "rm",
}


class ProtocolError(Exception):
    """The request is not in the whitelist or its parameters do not match."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class Plan:
    """One whitelist operation, already checked."""

    op: str
    argv: tuple[str, ...]
    risk: str
    confirm: str
    delay_seconds: int = 0


def build_plan(op: str, params: dict[str, object]) -> Plan:
    """Return the argument vector for ``op`` or refuse the request."""
    force = params.get("force") is True
    if op in _SERVICE:
        unit = _unit(params.get("unit"))
        if unit in PROTECTED_UNITS and not force:
            raise ProtocolError(f"{unit} is protected. Repeat with force if you mean it.")
        return Plan(op, ("systemctl", _SERVICE[op], unit), "medium", unit)
    if op in _CONTAINER:
        name = _token(params.get("name"), _NAME, "container name")
        risk = "high" if op == "container.remove" else "medium"
        argv = ["docker", _CONTAINER[op]]
        if op == "container.remove" and params.get("volumes") is True:
            argv.append("--volumes")
        argv.append(name)
        return Plan(op, tuple(argv), risk, name)
    if op == "journal.vacuum":
        size = params.get("size", "200M")
        if not isinstance(size, str) or not re.fullmatch(r"\d{1,5}[KMG]", size):
            raise ProtocolError("The vacuum size must look like 200M.")
        return Plan(op, ("journalctl", "--vacuum-size", size), "medium", size)
    if op in {"account.lock", "account.unlock"}:
        username = _token(params.get("username"), _USER, "username")
        if username in PROTECTED_ACCOUNTS and not force:
            raise ProtocolError(f"{username} cannot be changed without force.")
        flag = "-l" if op == "account.lock" else "-u"
        return Plan(op, ("passwd", flag, username), "high", username)
    if op in {"host.reboot", "host.poweroff"}:
        hostname = _token(params.get("hostname"), _NAME, "hostname")
        command = "reboot" if op == "host.reboot" else "poweroff"
        return Plan(op, ("systemctl", command), "critical", hostname, delay_seconds=10)
    if op in {"ssh.add", "ssh.remove"}:
        username = _token(params.get("username"), _USER, "username")
        key = params.get("key")
        if not isinstance(key, str) or PUBLIC_KEY.fullmatch(key.strip()) is None:
            raise ProtocolError("The SSH line is not a public key.")
        if "PRIVATE KEY" in key:
            raise ProtocolError("A private key is not accepted.")
        return Plan(op, (), "high", username)
    raise ProtocolError("That operation is not in the whitelist.")


def _unit(value: object) -> str:
    if not isinstance(value, str):
        raise ProtocolError("A unit name is required.")
    name = value if "." in value else f"{value}.service"
    if _UNIT.fullmatch(name) is None or "/" in name or name.startswith("-"):
        raise ProtocolError("The unit name is not usable.")
    return name


def _token(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ProtocolError(f"The {label} is not usable.")
    return value
