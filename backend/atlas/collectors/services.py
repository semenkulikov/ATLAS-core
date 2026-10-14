"""Collectors for systemd, cron, listening ports, and firewalls."""

from __future__ import annotations

import os
from pathlib import Path

from atlas.collectors.bag import Bag, declare
from atlas.collectors.parse import (
    ListenPort,
    UnitFile,
    is_exposed_address,
    parse_crontab,
    parse_proc_net,
    parse_systemctl_show,
    parse_unit,
    tcp_state_counts,
)
from atlas.collectors.view import HostView, logical_path
from atlas.domain import CollectorResult
from atlas.redact import mask_secrets

SYSTEMCTL_SERVICES = ["systemctl", "show", "--type=service", "--all", "--no-pager"]
SYSTEMCTL_TIMERS = ["systemctl", "show", "--type=timer", "--all", "--no-pager"]
_UNIT_DIRS = ("/etc/systemd/system", "/lib/systemd/system", "/usr/lib/systemd/system")


class SystemdCollector:
    """Read unit files and overlay runtime state from systemctl."""

    name = "systemd"
    declarations = (
        declare(
            "systemd",
            "file",
            "/etc/systemd/system/*",
            "Unit files installed by the administrator.",
            "Юниты, установленные администратором.",
        ),
        declare(
            "systemd",
            "file",
            "/lib/systemd/system/*",
            "Packaged unit files.",
            "Юниты из пакетов.",
        ),
        declare(
            "systemd",
            "file",
            "/usr/lib/systemd/system/*",
            "Packaged unit files on usr-merged systems.",
            "Юниты из пакетов в /usr.",
        ),
        declare(
            "systemd",
            "command",
            "systemctl show --type=service",
            "Runtime state of services.",
            "Состояние служб во время работы.",
        ),
        declare(
            "systemd",
            "command",
            "systemctl show --type=timer",
            "Runtime state of timers.",
            "Состояние таймеров во время работы.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        files = _unit_files(view, bag)
        shown = _systemctl(view, bag, SYSTEMCTL_SERVICES)
        shown.update(_systemctl(view, bag, SYSTEMCTL_TIMERS))
        names = set(files) | set(shown)
        if not names:
            bag.add_unknown("host", "systemd", "no unit files and systemctl produced no output")
            return bag.freeze()
        for name in sorted(names):
            if name.endswith((".service", ".timer")):
                _emit_unit(bag, name, files.get(name), shown.get(name))
        return bag.freeze()


class SchedulerCollector:
    """Read cron tables. User crontabs need root and are reported as unavailable otherwise."""

    name = "schedulers"
    declarations = (
        declare("schedulers", "file", "/etc/crontab", "System crontab.", "Системный crontab."),
        declare("schedulers", "file", "/etc/cron.d/*", "Cron drop-ins.", "Файлы в cron.d."),
        declare(
            "schedulers",
            "file",
            "/var/spool/cron/**",
            "Per-user crontabs.",
            "Crontab пользователей.",
            requires_root=True,
        ),
        declare("schedulers", "command", "atq", "Pending at jobs.", "Очередь at."),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        _cron_file(bag, view, "/etc/crontab", has_user_field=True, user_from_name=False)
        for logical in files_under(view, "/etc/cron.d", limit=100):
            _cron_file(bag, view, logical, has_user_field=True, user_from_name=False)
        for directory in ("/var/spool/cron/crontabs", "/var/spool/cron"):
            for logical in files_under(view, directory, limit=100):
                _cron_file(bag, view, logical, has_user_field=False, user_from_name=True)
        atq = bag.command(view, ["atq"])
        if atq.stdout.strip():
            bag.add_command(
                "host",
                "at.queue",
                str(len(atq.stdout.splitlines())),
                ["atq"],
                atq.stdout[:200],
            )
            bag.entity("schedule", "atq", {"type": "at", "text": atq.stdout[:2000]})
        return bag.freeze()


class PortsCollector:
    """Read listening sockets from /proc/net and attach a process when the inode is visible."""

    name = "ports"
    declarations = (
        declare(
            "ports", "file", "/proc/net/tcp", "Listening TCP sockets.", "Слушающие TCP-сокеты."
        ),
        declare(
            "ports", "file", "/proc/net/tcp6", "Listening TCP6 sockets.", "Слушающие TCP6-сокеты."
        ),
        declare(
            "ports", "file", "/proc/net/udp", "Listening UDP sockets.", "Слушающие UDP-сокеты."
        ),
        declare(
            "ports", "file", "/proc/net/udp6", "Listening UDP6 sockets.", "Слушающие UDP6-сокеты."
        ),
        declare(
            "ports",
            "file",
            "/proc/<pid>/fd",
            "Process that owns a socket inode.",
            "Процесс, которому принадлежит inode сокета.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        inodes = socket_owners(view)
        found = False
        for logical, protocol in (
            ("/proc/net/tcp", "tcp"),
            ("/proc/net/tcp6", "tcp6"),
            ("/proc/net/udp", "udp"),
            ("/proc/net/udp6", "udp6"),
        ):
            outcome = bag.read(view, logical)
            if not outcome.ok or outcome.text is None:
                continue
            if protocol == "tcp":
                for state, count in tcp_state_counts(outcome.text).items():
                    bag.add_file(
                        "host",
                        f"tcp.{state}",
                        str(count),
                        logical,
                        1,
                        f"{state} {count}",
                        outcome.sha256,
                    )
            for port in parse_proc_net(outcome.text, protocol):
                found = True
                _emit_port(bag, logical, outcome.sha256, outcome.text, port, inodes)
        if not found:
            bag.add_unknown("host", "ports", "listening sockets could not be read")
        return bag.freeze()


class FirewallCollector:
    """Read firewall rules. A missing tool is recorded as absent, not as an empty policy."""

    name = "firewall"
    declarations = (
        declare(
            "firewall",
            "command",
            "nft list ruleset",
            "nftables ruleset.",
            "Правила nftables.",
            requires_root=True,
        ),
        declare(
            "firewall",
            "command",
            "iptables-save",
            "iptables rules.",
            "Правила iptables.",
            requires_root=True,
        ),
        declare(
            "firewall",
            "command",
            "ufw status verbose",
            "ufw status.",
            "Состояние ufw.",
            requires_root=True,
        ),
        declare(
            "firewall",
            "command",
            "firewall-cmd --list-all",
            "firewalld zones.",
            "Зоны firewalld.",
            requires_root=True,
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        commands = (
            ["nft", "list", "ruleset"],
            ["iptables-save"],
            ["ufw", "status", "verbose"],
            ["firewall-cmd", "--list-all"],
        )
        for argv in commands:
            result = bag.command(view, argv, timeout=8)
            text = result.stdout.strip()
            if not text:
                continue
            masked = mask_secrets(text)[:8000]
            bag.add_command(
                "host", "firewall.rules", f"{len(text.splitlines())} lines", argv, masked[:200]
            )
            bag.entity("firewall", " ".join(argv), {"command": argv, "rules": masked})
        return bag.freeze()


def files_under(view: HostView, directory: str, *, limit: int) -> list[str]:
    """Return host paths of regular files under ``directory``, ignoring symlinks."""
    base = view.mapped(directory)
    if not base.is_dir():
        return []
    found: list[str] = []
    for path in sorted(base.rglob("*")):
        if len(found) >= limit:
            break
        if path.is_file() and not path.is_symlink():
            found.append(logical_path(view, path))
    return found


def _unit_files(view: HostView, bag: Bag) -> dict[str, tuple[str, UnitFile, str | None]]:
    chosen: dict[str, tuple[str, UnitFile, str | None]] = {}
    count = 0
    for directory in _UNIT_DIRS:
        for logical in files_under(view, directory, limit=500):
            if not logical.endswith((".service", ".timer")):
                continue
            count += 1
            if count > 500:
                bag.note(directory, "unavailable", "unit file list truncated at 500")
                return chosen
            outcome = bag.read(view, logical)
            if not outcome.ok or outcome.text is None:
                continue
            parsed = parse_unit(logical, outcome.text)
            name = Path(logical).name
            current = chosen.get(name)
            if current is None or "/etc/systemd/" in logical:
                chosen[name] = (logical, parsed, outcome.sha256)
    return chosen


def _systemctl(view: HostView, bag: Bag, argv: list[str]) -> dict[str, dict[str, str]]:
    result = bag.command(view, argv, timeout=20)
    if not result.stdout.strip():
        return {}
    return parse_systemctl_show(result.stdout)


def _emit_unit(
    bag: Bag,
    name: str,
    file_info: tuple[str, UnitFile, str | None] | None,
    runtime: dict[str, str] | None,
) -> None:
    subject = f"unit:{name}"
    kind = "timer" if name.endswith(".timer") else "service"
    payload: dict[str, object] = {"unit": name, "kind": kind}
    if file_info is not None:
        logical, parsed, digest = file_info
        _emit_file_fields(bag, subject, logical, parsed, digest, payload)
    if runtime:
        for prop, predicate in (
            ("ActiveState", "unit.active"),
            ("SubState", "unit.sub"),
            ("UnitFileState", "unit.enabled"),
        ):
            if runtime.get(prop):
                bag.add_command(
                    subject,
                    predicate,
                    runtime[prop],
                    SYSTEMCTL_SERVICES,
                    f"{prop}={runtime[prop]}",
                )
                payload[predicate] = runtime[prop]
        if file_info is None and runtime.get("Description"):
            payload["description"] = runtime["Description"]
    elif file_info is not None:
        bag.add_unknown(subject, "unit.active", "systemctl is not available")
    entity_kind = "schedule" if kind == "timer" else "service"
    bag.entity(entity_kind, name, payload)


def _emit_file_fields(
    bag: Bag,
    subject: str,
    logical: str,
    parsed: UnitFile,
    digest: str | None,
    payload: dict[str, object],
) -> None:
    pairs = (
        ("description", parsed.description, parsed.description_line, "unit.description"),
        ("exec_start", parsed.exec_start, parsed.exec_line, "unit.exec_start"),
        ("user", parsed.user, parsed.user_line, "unit.user"),
        (
            "working_directory",
            parsed.working_directory,
            parsed.working_line,
            "unit.working_directory",
        ),
        ("restart", parsed.restart, parsed.restart_line, "unit.restart"),
    )
    for field_name, value, line, predicate in pairs:
        if value is None or line is None:
            bag.add_unknown(subject, predicate, f"{field_name} is not set in the unit file")
            payload[field_name] = None
            continue
        bag.add_file(subject, predicate, value, logical, line, f"{field_name}={value}", digest)
        payload[field_name] = value


def _cron_file(
    bag: Bag,
    view: HostView,
    logical: str,
    *,
    has_user_field: bool,
    user_from_name: bool,
) -> None:
    outcome = bag.read(view, logical)
    if not outcome.ok or outcome.text is None:
        return
    jobs = parse_crontab(logical, outcome.text, has_user_field=has_user_field)
    user_name = Path(logical).name if user_from_name else None
    for job in jobs:
        key = f"cron:{logical}:{job.line}"
        bag.add_file(
            key,
            "schedule.command",
            job.command,
            logical,
            job.line,
            f"{job.schedule} {job.command}",
            outcome.sha256,
        )
        bag.entity(
            "schedule",
            key,
            {
                "type": "cron",
                "schedule": job.schedule,
                "user": user_name or job.user,
                "command": job.command,
                "path": logical,
                "line": job.line,
            },
        )


def _emit_port(
    bag: Bag,
    logical: str,
    digest: str | None,
    text: str,
    port: ListenPort,
    inodes: dict[str, tuple[int, str, str]],
) -> None:
    subject = f"port:{port.protocol}:{port.port}:{port.address}"
    quote = _line(text, port.line)
    bag.add_file(
        subject, "port.bind", f"{port.address}:{port.port}", logical, port.line, quote, digest
    )
    exposed = is_exposed_address(port.address)
    bag.add_file(
        subject,
        "port.exposed",
        "yes" if exposed else "no",
        logical,
        port.line,
        quote,
        digest,
        rule="port.exposed",
    )
    owner = inodes.get(port.inode)
    payload: dict[str, object] = {
        "protocol": port.protocol,
        "address": port.address,
        "port": port.port,
        "exposed": exposed,
        "inode": port.inode,
    }
    if owner is None:
        bag.add_unknown(subject, "port.process", "socket inode is not visible to this user")
        payload["process"] = None
    else:
        pid, comm, cmdline = owner
        bag.add_command(
            subject, "port.process", f"{pid} {comm}", ["proc", str(pid), "fd"], cmdline or comm
        )
        payload["process"] = {"pid": pid, "comm": comm, "cmdline": cmdline}
    bag.entity("port", subject, payload)


def socket_owners(view: HostView) -> dict[str, tuple[int, str, str]]:
    """Map a socket inode to the process that holds it, when /proc allows it."""
    owners: dict[str, tuple[int, str, str]] = {}
    proc = view.mapped("/proc")
    if not proc.is_dir():
        return owners
    seen = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        seen += 1
        if seen > 2000:
            break
        comm, cmdline = process_names(entry)
        view.files_read.append(f"/proc/{entry.name}/fd")
        try:
            fds = list((entry / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                owners[target[8:-1]] = (int(entry.name), comm, cmdline)
    return owners


def process_names(entry: Path) -> tuple[str, str]:
    """Return ``(comm, cmdline)`` for one /proc entry, with secret-shaped text masked."""
    comm = mask_secrets(_text(entry / "comm").strip())
    cmdline = mask_secrets(_text(entry / "cmdline").replace("\x00", " ").strip())
    return comm, cmdline


def processes(view: HostView) -> list[tuple[int, str, str]]:
    """Return visible processes as ``(pid, comm, cmdline)``."""
    proc = view.mapped("/proc")
    if not proc.is_dir():
        return []
    rows: list[tuple[int, str, str]] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        view.files_read.append(f"/proc/{entry.name}/comm")
        view.files_read.append(f"/proc/{entry.name}/cmdline")
        comm, cmdline = process_names(entry)
        if comm or cmdline:
            rows.append((int(entry.name), comm, cmdline))
        if len(rows) >= 2000:
            break
    return rows


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _line(text: str, line: int) -> str:
    rows = text.splitlines()
    if line < 1 or line > len(rows):
        return ""
    return rows[line - 1].strip()
