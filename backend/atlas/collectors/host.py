"""Collectors for the host passport: OS, resources, network, packages, users, SSH."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from atlas.collectors.bag import Bag, declare
from atlas.collectors.parse import (
    fingerprint_authorized_keys,
    is_network_fs,
    line_containing,
    parse_cpuinfo,
    parse_dpkg_status,
    parse_groups,
    parse_meminfo,
    parse_mounts,
    parse_os_release,
    parse_package_table,
    parse_passwd,
    parse_resolv,
    parse_sshd_config,
    sudoers_mentions,
)
from atlas.collectors.view import HostView
from atlas.domain import CollectorResult

UNAME = ["uname", "-s", "-r", "-m", "-n"]
VIRT = ["systemd-detect-virt"]
IP_ADDR = ["ip", "-j", "addr"]
IP_ROUTE = ["ip", "-j", "route"]
DPKG_QUERY = ["dpkg-query", "-W"]
RPM_QUERY = ["rpm", "-qa", "--queryformat", "%{NAME}\t%{VERSION}-%{RELEASE}\n"]
RUNTIMES = (
    ("python", ["python3", "--version"]),
    ("node", ["node", "--version"]),
    ("java", ["java", "-version"]),
    ("go", ["go", "version"]),
)
_PACKAGE_CAP = 5000


class OsCollector:
    """Read the operating system identity from local files and uname."""

    name = "os"
    declarations = (
        declare(
            "os",
            "file",
            "/etc/os-release",
            "Distribution name and version.",
            "Название и версия дистрибутива.",
        ),
        declare("os", "file", "/etc/hostname", "Hostname file.", "Файл имени хоста."),
        declare("os", "file", "/etc/timezone", "Configured timezone.", "Настроенный часовой пояс."),
        declare(
            "os",
            "file",
            "/etc/localtime",
            "Timezone symlink target.",
            "Куда указывает ссылка часового пояса.",
        ),
        declare("os", "file", "/proc/uptime", "Host uptime.", "Время работы хоста."),
        declare(
            "os", "command", "uname -s -r -m -n", "Kernel and architecture.", "Ядро и архитектура."
        ),
        declare(
            "os", "command", "systemd-detect-virt", "Virtualization type.", "Тип виртуализации."
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        identity: dict[str, object] = {}
        release = bag.read(view, "/etc/os-release")
        if release.ok and release.text is not None:
            parsed = parse_os_release(release.text)
            for key, predicate in (
                ("ID", "os.id"),
                ("VERSION_ID", "os.version"),
                ("PRETTY_NAME", "os.pretty_name"),
            ):
                if key not in parsed:
                    bag.add_unknown("host", predicate, f"{key} is missing from /etc/os-release")
                    continue
                value, line = parsed[key]
                quote = _quote(release.text, line)
                bag.add_file(
                    "host", predicate, value, "/etc/os-release", line, quote, release.sha256
                )
                identity[predicate] = value
        else:
            bag.add_unknown("host", "os.pretty_name", release.reason or "os-release is unavailable")

        uname = bag.command(view, UNAME)
        if uname.stdout.strip():
            parts = uname.stdout.split()
            labels = ("kernel.name", "kernel.release", "arch", "hostname")
            for label, value in zip(labels, parts, strict=False):
                bag.add_command("host", label, value, UNAME, uname.stdout.strip())
                identity[label] = value
        else:
            bag.add_unknown("host", "kernel.release", "uname produced no output")

        hostname = bag.read(view, "/etc/hostname")
        if hostname.ok and hostname.text:
            value = hostname.text.strip().splitlines()[0]
            bag.add_file("host", "hostname.file", value, "/etc/hostname", 1, value, hostname.sha256)
            identity["hostname_file"] = value

        timezone = _timezone(view, bag)
        if timezone is not None:
            identity["timezone"] = timezone

        uptime = bag.read(view, "/proc/uptime")
        if uptime.ok and uptime.text:
            raw = uptime.text.split()[0]
            bag.add_file(
                "host", "uptime.seconds", raw, "/proc/uptime", 1, uptime.text.strip(), uptime.sha256
            )
            identity["uptime_seconds"] = raw
        else:
            bag.add_unknown("host", "uptime.seconds", uptime.reason or "uptime is unavailable")

        virt = bag.command(view, VIRT)
        if virt.stdout.strip():
            value = virt.stdout.strip().splitlines()[0]
            bag.add_command("host", "virt.type", value, VIRT, virt.stdout.strip())
            identity["virt"] = value
        else:
            bag.add_unknown(
                "host", "virt.type", virt.stderr or "systemd-detect-virt is unavailable"
            )

        bag.entity("os", "host", identity)
        return bag.freeze()


class ResourcesCollector:
    """Read CPU, memory, and mount points. Usage of network filesystems is skipped."""

    name = "resources"
    declarations = (
        declare(
            "resources",
            "file",
            "/proc/cpuinfo",
            "CPU model and logical cores.",
            "Модель CPU и число логических ядер.",
        ),
        declare(
            "resources", "file", "/proc/meminfo", "Memory and swap totals.", "Объём памяти и swap."
        ),
        declare(
            "resources",
            "file",
            "/proc/mounts",
            "Mount points and filesystem types.",
            "Точки монтирования и типы файловых систем.",
        ),
        declare(
            "resources",
            "command",
            "statvfs",
            "Disk and inode usage of local mounts.",
            "Занятость диска и inode локальных разделов.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        payload: dict[str, object] = {"filesystems": []}
        cpu = bag.read(view, "/proc/cpuinfo")
        if cpu.ok and cpu.text is not None:
            model, count, model_line = parse_cpuinfo(cpu.text)
            bag.add_file(
                "host",
                "cpu.count",
                str(count),
                "/proc/cpuinfo",
                1,
                f"processor count {count}",
                cpu.sha256,
            )
            payload["cpu_count"] = count
            if model is not None and model_line is not None:
                bag.add_file(
                    "host",
                    "cpu.model",
                    model,
                    "/proc/cpuinfo",
                    model_line,
                    _quote(cpu.text, model_line),
                    cpu.sha256,
                )
                payload["cpu_model"] = model
            else:
                bag.add_unknown("host", "cpu.model", "model name is missing from /proc/cpuinfo")
        else:
            bag.add_unknown("host", "cpu.model", cpu.reason or "cpuinfo is unavailable")

        memory = bag.read(view, "/proc/meminfo")
        if memory.ok and memory.text is not None:
            info = parse_meminfo(memory.text)
            for key, predicate in (
                ("MemTotal", "memory.total_bytes"),
                ("MemAvailable", "memory.available_bytes"),
                ("SwapTotal", "swap.total_bytes"),
            ):
                if key not in info:
                    bag.add_unknown("host", predicate, f"{key} is missing from /proc/meminfo")
                    continue
                line, quote = line_containing(memory.text, key)
                bag.add_file(
                    "host", predicate, str(info[key]), "/proc/meminfo", line, quote, memory.sha256
                )
                payload[predicate] = info[key]
        else:
            bag.add_unknown("host", "memory.total_bytes", memory.reason or "meminfo is unavailable")

        mounts = bag.read(view, "/proc/mounts")
        filesystems: list[dict[str, object]] = []
        if mounts.ok and mounts.text is not None:
            for mount in parse_mounts(mounts.text):
                subject = f"mount:{mount.mountpoint}"
                quote = _quote(mounts.text, mount.line)
                bag.add_file(
                    subject,
                    "fs.type",
                    mount.fstype,
                    "/proc/mounts",
                    mount.line,
                    quote,
                    mounts.sha256,
                )
                row: dict[str, object] = {
                    "device": mount.device,
                    "mountpoint": mount.mountpoint,
                    "fstype": mount.fstype,
                }
                if is_network_fs(mount.fstype):
                    bag.add_unknown(
                        subject,
                        "fs.used_bytes",
                        "network filesystem is not measured",
                    )
                    row["usage"] = None
                elif view.is_live:
                    usage = _statvfs(mount.mountpoint)
                    if usage is None:
                        bag.add_unknown(subject, "fs.used_bytes", "statvfs failed")
                        row["usage"] = None
                    else:
                        bag.add_command(
                            subject,
                            "fs.total_bytes",
                            str(usage[0]),
                            ["statvfs", mount.mountpoint],
                            f"total={usage[0]} available={usage[1]}",
                            rule="statvfs",
                        )
                        row["total_bytes"] = usage[0]
                        row["available_bytes"] = usage[1]
                        row["inode_total"] = usage[2]
                        row["inode_free"] = usage[3]
                else:
                    bag.add_unknown(
                        subject, "fs.used_bytes", "disk usage is read from the live mount"
                    )
                    row["usage"] = None
                filesystems.append(row)
        else:
            bag.add_unknown("host", "mounts", mounts.reason or "mounts are unavailable")
        payload["filesystems"] = filesystems
        bag.entity("resources", "host", payload)
        return bag.freeze()


class NetworkCollector:
    """Read addresses, routes, resolvers, and interface counters."""

    name = "network"
    declarations = (
        declare("network", "command", "ip -j addr", "Interface addresses.", "Адреса интерфейсов."),
        declare("network", "command", "ip -j route", "Routing table.", "Таблица маршрутов."),
        declare("network", "file", "/etc/resolv.conf", "DNS resolvers.", "DNS-резолверы."),
        declare(
            "network",
            "file",
            "/proc/net/dev",
            "Per-interface traffic counters.",
            "Счётчики трафика по интерфейсам.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        interfaces: list[dict[str, Any]] = []
        addresses = bag.command(view, IP_ADDR)
        if addresses.stdout.strip():
            interfaces = _interfaces_from_ip(addresses.stdout)
            for row in interfaces:
                name = str(row["name"])
                for address in row["addresses"]:
                    bag.add_command(
                        f"iface:{name}",
                        "net.address",
                        str(address),
                        IP_ADDR,
                        addresses.stdout[:200],
                    )
        else:
            bag.add_unknown("host", "net.address", "ip addr produced no output")

        routes = bag.command(view, IP_ROUTE)
        default_route = None
        if routes.stdout.strip():
            default_route = _default_route(routes.stdout)
            if default_route is None:
                bag.add_unknown("host", "net.default_route", "no default route in ip route output")
            else:
                bag.add_command(
                    "host", "net.default_route", default_route, IP_ROUTE, routes.stdout[:200]
                )
        else:
            bag.add_unknown("host", "net.default_route", "ip route produced no output")

        resolvers: list[str] = []
        resolv = bag.read(view, "/etc/resolv.conf")
        if resolv.ok and resolv.text is not None:
            for address, line in parse_resolv(resolv.text):
                resolvers.append(address)
                bag.add_file(
                    "host",
                    "dns.server",
                    address,
                    "/etc/resolv.conf",
                    line,
                    _quote(resolv.text, line),
                    resolv.sha256,
                )
        elif resolv.status != "ok":
            bag.add_unknown("host", "dns.server", resolv.reason or "resolv.conf is unavailable")

        counters = bag.read(view, "/proc/net/dev")
        dev_rows: list[dict[str, object]] = []
        if counters.ok and counters.text is not None:
            dev_rows = _net_dev(counters.text)
        bag.entity(
            "network",
            "host",
            {
                "interfaces": interfaces,
                "default_route": default_route,
                "resolvers": resolvers,
                "counters": dev_rows,
            },
        )
        return bag.freeze()


class PackagesCollector:
    """Read the package database and the versions of common language runtimes."""

    name = "packages"
    declarations = (
        declare(
            "packages",
            "file",
            "/var/lib/dpkg/status",
            "Installed dpkg packages and versions.",
            "Установленные пакеты dpkg и их версии.",
        ),
        declare(
            "packages",
            "command",
            "dpkg-query -W",
            "Installed dpkg packages when the status file is unreadable.",
            "Пакеты dpkg, если файл status недоступен.",
        ),
        declare(
            "packages", "command", "rpm -qa", "Installed rpm packages.", "Установленные пакеты rpm."
        ),
        declare(
            "packages", "command", "python3 --version", "Python runtime version.", "Версия Python."
        ),
        declare(
            "packages", "command", "node --version", "Node.js runtime version.", "Версия Node.js."
        ),
        declare("packages", "command", "java -version", "Java runtime version.", "Версия Java."),
        declare("packages", "command", "go version", "Go runtime version.", "Версия Go."),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        packages, target, status, reason = read_packages(view)
        bag.note(target, status, reason)
        if not packages and status != "ok":
            bag.add_unknown("host", "packages", reason or "package database is unavailable")
        names = sorted(packages)
        if len(names) > _PACKAGE_CAP:
            bag.add_unknown("host", "packages", f"package list truncated at {_PACKAGE_CAP}")
            names = names[:_PACKAGE_CAP]
        for name in names:
            bag.entity("package", name, {"name": name, "version": packages[name]})
        runtimes: list[dict[str, str]] = []
        for runtime, argv in RUNTIMES:
            result = bag.command(view, argv)
            text = (result.stdout or result.stderr).strip()
            if not text:
                bag.add_unknown(
                    "host", f"runtime.{runtime}", f"{runtime} version command produced no output"
                )
                continue
            first = text.splitlines()[0]
            bag.add_command("host", f"runtime.{runtime}", first, argv, first)
            runtimes.append({"name": runtime, "version": first})
            bag.entity("runtime", runtime, {"name": runtime, "version": first})
        bag.entity("packages", "summary", {"count": len(names), "runtimes": runtimes})
        return bag.freeze()


class UsersCollector:
    """Read accounts, groups, and sudoers mentions. Shadow is never opened."""

    name = "users"
    declarations = (
        declare(
            "users",
            "file",
            "/etc/passwd",
            "Account names, ids, homes, and shells.",
            "Имена, id, домашние каталоги и оболочки.",
        ),
        declare("users", "file", "/etc/group", "Group membership.", "Членство в группах."),
        declare(
            "users",
            "file",
            "/etc/sudoers",
            "Sudo rules that name an account or group.",
            "Правила sudo, где назван пользователь или группа.",
            requires_root=True,
        ),
        declare(
            "users",
            "file",
            "/etc/sudoers.d/*",
            "Drop-in sudo rules.",
            "Дополнительные правила sudo.",
            requires_root=True,
        ),
        declare("users", "command", "who", "Active login sessions.", "Активные сессии."),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        passwd = bag.read(view, "/etc/passwd")
        groups_file = bag.read(view, "/etc/group")
        membership = parse_groups(groups_file.text) if groups_file.ok and groups_file.text else {}
        sudo_text = _read_sudoers(view, bag)
        if not passwd.ok or passwd.text is None:
            bag.add_unknown("host", "users", passwd.reason or "passwd is unavailable")
            return bag.freeze()
        for user in parse_passwd(passwd.text):
            subject = f"user:{user.name}"
            quote = _quote(passwd.text, user.line)
            bag.add_file(
                subject, "user.uid", str(user.uid), "/etc/passwd", user.line, quote, passwd.sha256
            )
            bag.add_file(
                subject, "user.shell", user.shell, "/etc/passwd", user.line, quote, passwd.sha256
            )
            bag.add_file(
                subject, "user.home", user.home, "/etc/passwd", user.line, quote, passwd.sha256
            )
            groups = membership.get(user.name, [])
            if groups_file.ok:
                bag.add_file(
                    subject,
                    "user.groups",
                    ",".join(groups),
                    "/etc/group",
                    1,
                    ",".join(groups) or "no supplementary groups",
                    groups_file.sha256,
                )
            mentions: list[str] = []
            if sudo_text is None:
                bag.add_unknown(subject, "user.sudo", "sudoers is unreadable")
            else:
                hits = sudoers_mentions(sudo_text[0], user.name, groups)
                mentions = [line for _, line in hits]
                if hits:
                    line_no, line = hits[0]
                    bag.add_file(
                        subject,
                        "user.sudo",
                        line,
                        sudo_text[1],
                        line_no,
                        line,
                        None,
                        rule="sudoers.mention",
                    )
                else:
                    bag.add_file(
                        subject,
                        "user.sudo",
                        "not listed",
                        sudo_text[1],
                        1,
                        "no matching sudoers line",
                        None,
                    )
            bag.entity(
                "user",
                user.name,
                {
                    "name": user.name,
                    "uid": user.uid,
                    "gid": user.gid,
                    "gecos": user.gecos,
                    "home": user.home,
                    "shell": user.shell,
                    "groups": groups,
                    "sudo": mentions,
                },
            )
        who = bag.command(view, ["who"])
        if who.stdout.strip():
            bag.add_command(
                "host", "sessions", str(len(who.stdout.splitlines())), ["who"], who.stdout[:200]
            )
            bag.entity("sessions", "who", {"text": who.stdout[:4000]})
        return bag.freeze()


class SshCollector:
    """Fingerprint authorized keys and read a few sshd settings. Private keys are refused."""

    name = "ssh"
    declarations = (
        declare(
            "ssh",
            "file",
            "*/.ssh/authorized_keys",
            "Public key type and SHA256 fingerprint in each home.",
            "Тип и отпечаток SHA256 публичного ключа в домашнем каталоге.",
            requires_root=True,
        ),
        declare(
            "ssh",
            "file",
            "/etc/ssh/sshd_config",
            "sshd port and authentication settings.",
            "Порт sshd и параметры аутентификации.",
            requires_root=True,
        ),
        declare(
            "ssh",
            "file",
            "/etc/ssh/sshd_config.d/*",
            "Drop-in sshd settings.",
            "Дополнительные параметры sshd.",
            requires_root=True,
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        passwd = view.read("/etc/passwd")
        users = parse_passwd(passwd.text) if passwd.ok and passwd.text else []
        if not users:
            bag.note("/etc/passwd", passwd.status, passwd.reason)
        for user in users:
            path = str(Path(user.home) / ".ssh" / "authorized_keys")
            outcome = bag.read(view, path)
            if not outcome.ok or outcome.text is None:
                if outcome.status == "unavailable":
                    bag.add_unknown(
                        f"user:{user.name}",
                        "ssh.keys",
                        outcome.reason or "authorized_keys is unreadable",
                    )
                continue
            keys = fingerprint_authorized_keys(outcome.text)
            if not keys:
                bag.add_unknown(
                    f"user:{user.name}", "ssh.keys", "no public keys in authorized_keys"
                )
                continue
            for line_no, key_type, digest, comment in keys:
                bag.add_file(
                    f"sshkey:{digest}",
                    "ssh.fingerprint",
                    digest,
                    path,
                    line_no,
                    f"{key_type} {digest}",
                    outcome.sha256,
                )
                bag.entity(
                    "ssh_key",
                    digest,
                    {
                        "user": user.name,
                        "type": key_type,
                        "fingerprint": digest,
                        "comment": comment,
                        "path": path,
                    },
                )
        _sshd(view, bag)
        return bag.freeze()


def _quote(text: str, line: int) -> str:
    rows = text.splitlines()
    if line < 1 or line > len(rows):
        return ""
    return rows[line - 1].strip()


def _timezone(view: HostView, bag: Bag) -> str | None:
    path = view.mapped("/etc/localtime")
    try:
        if path.is_symlink():
            target = os.readlink(path)
            marker = "zoneinfo/"
            if marker in target:
                value = target.split(marker, 1)[1]
                bag.add_command("host", "timezone", value, ["readlink", "/etc/localtime"], target)
                bag.note("/etc/localtime", "ok", None)
                return value
    except OSError as exc:
        bag.note("/etc/localtime", "unavailable", exc.strerror)
    timezone = bag.read(view, "/etc/timezone")
    if timezone.ok and timezone.text:
        value = timezone.text.strip().splitlines()[0]
        bag.add_file("host", "timezone", value, "/etc/timezone", 1, value, timezone.sha256)
        return value
    bag.add_unknown("host", "timezone", "timezone is not set")
    return None


def _statvfs(mountpoint: str) -> tuple[int, int, int, int] | None:
    try:
        usage = os.statvfs(mountpoint)
    except OSError:
        return None
    return (
        usage.f_frsize * usage.f_blocks,
        usage.f_frsize * usage.f_bavail,
        usage.f_files,
        usage.f_ffree,
    )


def _interfaces_from_ip(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        addresses: list[str] = []
        info = item.get("addr_info", [])
        if isinstance(info, list):
            for address in info:
                if isinstance(address, dict) and isinstance(address.get("local"), str):
                    prefix = address.get("prefixlen")
                    local = address["local"]
                    addresses.append(local if prefix is None else f"{local}/{prefix}")
        rows.append({"name": item.get("ifname", ""), "addresses": addresses})
    return rows


def _default_route(text: str) -> str | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    for item in payload:
        if isinstance(item, dict) and item.get("dst") == "default":
            gateway = item.get("gateway", "")
            device = item.get("dev", "")
            return f"{gateway} dev {device}".strip()
    return None


def _net_dev(text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name in {"lo", "face"} or name.startswith("Inter"):
            continue
        parts = rest.split()
        if len(parts) < 9:
            continue
        try:
            rows.append({"name": name, "rx_bytes": int(parts[0]), "tx_bytes": int(parts[8])})
        except ValueError:
            continue
    return rows


def read_packages(view: HostView) -> tuple[dict[str, str], str, str, str | None]:
    """Return package versions and the source that produced them.

    The tuple is ``(packages, target, status, reason)``.
    """
    status = view.read("/var/lib/dpkg/status", max_bytes=8_000_000)
    if status.ok and status.text:
        return parse_dpkg_status(status.text), status.path, status.status, status.reason
    queried = view.runner.run(DPKG_QUERY, timeout=20)
    if queried.stdout.strip():
        return parse_package_table(queried.stdout), " ".join(DPKG_QUERY), "ok", None
    rpm = view.runner.run(RPM_QUERY, timeout=20)
    if rpm.stdout.strip():
        return parse_package_table(rpm.stdout), " ".join(RPM_QUERY), "ok", None
    return {}, "packages", "unavailable", "neither dpkg nor rpm is available"


def _read_sudoers(view: HostView, bag: Bag) -> tuple[str, str] | None:
    chunks: list[str] = []
    main = bag.read(view, "/etc/sudoers")
    source = "/etc/sudoers"
    if main.ok and main.text is not None:
        chunks.append(main.text)
    directory = view.mapped("/etc/sudoers.d")
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            logical = "/etc/sudoers.d/" + path.name
            extra = bag.read(view, logical)
            if extra.ok and extra.text:
                chunks.append(extra.text)
                source = logical
    if not chunks:
        return None
    return "\n".join(chunks), source


def _sshd(view: HostView, bag: Bag) -> None:
    files = ["/etc/ssh/sshd_config"]
    dropin = view.mapped("/etc/ssh/sshd_config.d")
    if dropin.is_dir():
        files.extend(
            "/etc/ssh/sshd_config.d/" + path.name
            for path in sorted(dropin.iterdir())
            if path.is_file() and not path.is_symlink()
        )
    merged: dict[str, tuple[str, int, str]] = {}
    any_ok = False
    for path in files:
        outcome = bag.read(view, path)
        if not outcome.ok or outcome.text is None:
            continue
        any_ok = True
        for key, (value, line) in parse_sshd_config(outcome.text).items():
            merged.setdefault(key, (value, line, path))
    if not any_ok:
        bag.add_unknown("host", "sshd.port", "sshd_config is unreadable")
        return
    for key, predicate in (
        ("port", "sshd.port"),
        ("permitrootlogin", "sshd.permit_root_login"),
        ("passwordauthentication", "sshd.password_authentication"),
        ("pubkeyauthentication", "sshd.pubkey_authentication"),
    ):
        if key not in merged:
            bag.add_unknown("host", predicate, f"{key} is not set in sshd_config")
            continue
        value, line, path = merged[key]
        bag.add_file("host", predicate, value, path, line, f"{key} {value}", None)
    bag.entity(
        "sshd",
        "config",
        {
            predicate: merged[key][0]
            for key, predicate in (
                ("port", "port"),
                ("permitrootlogin", "permit_root_login"),
                ("passwordauthentication", "password_authentication"),
            )
            if key in merged
        },
    )
