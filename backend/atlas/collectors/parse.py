"""Pure parsers for the files and command outputs the collectors read."""

from __future__ import annotations

import base64
import hashlib
import re
import socket
from dataclasses import dataclass, field


def parse_os_release(text: str) -> dict[str, tuple[str, int]]:
    """Return os-release keys mapped to ``(value, line)``."""
    found: dict[str, tuple[str, int]] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key.strip()] = (value.strip().strip('"').strip("'"), number)
    return found


def parse_meminfo(text: str) -> dict[str, int]:
    """Return meminfo values in bytes."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.split()
        if not parts:
            continue
        try:
            amount = int(parts[0])
        except ValueError:
            continue
        if len(parts) > 1 and parts[1].lower() == "kb":
            amount *= 1024
        values[key.strip()] = amount
    return values


def parse_cpuinfo(text: str) -> tuple[str | None, int, int | None]:
    """Return ``(model, logical_cpus, line_of_model)``."""
    model: str | None = None
    model_line: int | None = None
    count = 0
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("processor"):
            count += 1
        if model is None and line.lower().startswith("model name"):
            model = line.split(":", 1)[1].strip()
            model_line = number
    if count == 0 and model is not None:
        count = 1
    return model, count, model_line


@dataclass(frozen=True, slots=True)
class Mount:
    device: str
    mountpoint: str
    fstype: str
    line: int


_NETWORK_FS = frozenset({"nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs"})
_SKIP_FS = frozenset(
    {
        "proc",
        "sysfs",
        "devtmpfs",
        "devpts",
        "cgroup",
        "cgroup2",
        "securityfs",
        "pstore",
        "bpf",
        "tracefs",
        "debugfs",
        "configfs",
        "fusectl",
        "mqueue",
        "hugetlbfs",
        "autofs",
        "binfmt_misc",
        "nsfs",
        "ramfs",
        "tmpfs",
        "overlay",
        "squashfs",
    }
)


def parse_mounts(text: str) -> list[Mount]:
    """Return real filesystems. Pseudo filesystems are omitted."""
    mounts: list[Mount] = []
    for number, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) < 3:
            continue
        fstype = parts[2]
        if fstype in _SKIP_FS:
            continue
        mounts.append(Mount(parts[0], parts[1].replace("\\040", " "), fstype, number))
    return mounts


def is_network_fs(fstype: str) -> bool:
    """Return whether measuring this filesystem could block on the network."""
    return fstype in _NETWORK_FS


def parse_resolv(text: str) -> list[tuple[str, int]]:
    """Return nameserver addresses and the line they came from."""
    servers: list[tuple[str, int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("nameserver"):
            parts = stripped.split()
            if len(parts) >= 2:
                servers.append((parts[1], number))
    return servers


@dataclass(frozen=True, slots=True)
class PasswdUser:
    name: str
    uid: int
    gid: int
    gecos: str
    home: str
    shell: str
    line: int


def parse_passwd(text: str) -> list[PasswdUser]:
    """Parse ``/etc/passwd``. Malformed lines are skipped."""
    users: list[PasswdUser] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 7:
            continue
        try:
            uid = int(parts[2])
            gid = int(parts[3])
        except ValueError:
            continue
        users.append(PasswdUser(parts[0], uid, gid, parts[4], parts[5], parts[6], number))
    return users


def parse_groups(text: str) -> dict[str, list[str]]:
    """Return ``user -> group names`` from ``/etc/group``."""
    membership: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        name = parts[0]
        for user in parts[3].split(","):
            if user:
                membership.setdefault(user, []).append(name)
    return membership


def parse_dpkg_status(text: str) -> dict[str, str]:
    """Return installed package names mapped to versions."""
    packages: dict[str, str] = {}
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            _remember_package(packages, current)
            current = {}
            continue
        if line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    _remember_package(packages, current)
    return packages


def _remember_package(packages: dict[str, str], fields: dict[str, str]) -> None:
    name = fields.get("Package")
    version = fields.get("Version")
    status = fields.get("Status", "install ok installed")
    if name and version and "installed" in status and "not-installed" not in status:
        packages[name] = version


def parse_package_table(text: str) -> dict[str, str]:
    """Parse ``name<tab>version`` lines from dpkg-query or rpm."""
    packages: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        name, version = line.split("\t", 1)
        name = name.strip()
        version = version.strip()
        if name and version:
            packages[name] = version
    return packages


@dataclass(frozen=True, slots=True)
class UnitFile:
    path: str
    description: str | None
    description_line: int | None
    exec_start: str | None
    exec_line: int | None
    user: str | None
    user_line: int | None
    working_directory: str | None
    working_line: int | None
    restart: str | None
    restart_line: int | None


def parse_unit(path: str, text: str) -> UnitFile:
    """Parse the few systemd keys inventory cares about, with line numbers."""
    values: dict[str, tuple[str, int]] = {}
    section = ""
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].lower()
            continue
        if section != "service" and section != "timer" and "=" not in line:
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip().lower(), (value.strip(), number))
    return UnitFile(
        path=path,
        description=_pick(values, "description"),
        description_line=_line(values, "description"),
        exec_start=_pick(values, "execstart"),
        exec_line=_line(values, "execstart"),
        user=_pick(values, "user"),
        user_line=_line(values, "user"),
        working_directory=_pick(values, "workingdirectory"),
        working_line=_line(values, "workingdirectory"),
        restart=_pick(values, "restart"),
        restart_line=_line(values, "restart"),
    )


def _pick(values: dict[str, tuple[str, int]], key: str) -> str | None:
    found = values.get(key)
    if found is None:
        return None
    return found[0]


def _line(values: dict[str, tuple[str, int]], key: str) -> int | None:
    found = values.get(key)
    if found is None:
        return None
    return found[1]


def parse_systemctl_show(text: str) -> dict[str, dict[str, str]]:
    """Parse ``systemctl show`` output into ``unit id -> properties``."""
    units: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            _store_unit(units, current)
            current = {}
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key] = value
    _store_unit(units, current)
    return units


def _store_unit(units: dict[str, dict[str, str]], current: dict[str, str]) -> None:
    unit_id = current.get("Id")
    if unit_id:
        units[unit_id] = current


@dataclass(frozen=True, slots=True)
class CronJob:
    schedule: str
    user: str | None
    command: str
    line: int
    path: str


def parse_crontab(path: str, text: str, *, has_user_field: bool) -> list[CronJob]:
    """Parse crontab lines. ``has_user_field`` is true for ``/etc/cron.d``."""
    jobs: list[CronJob] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            parts = line.split(maxsplit=2 if has_user_field else 1)
            if has_user_field and len(parts) >= 3:
                jobs.append(CronJob(parts[0], parts[1], parts[2], number, path))
            elif not has_user_field and len(parts) >= 2:
                jobs.append(CronJob(parts[0], None, parts[1], number, path))
            continue
        parts = line.split()
        needed = 6 if has_user_field else 5
        if len(parts) <= needed:
            continue
        schedule = " ".join(parts[:5])
        if has_user_field:
            jobs.append(CronJob(schedule, parts[5], " ".join(parts[6:]), number, path))
        else:
            jobs.append(CronJob(schedule, None, " ".join(parts[5:]), number, path))
    return jobs


@dataclass(frozen=True, slots=True)
class ListenPort:
    protocol: str
    address: str
    port: int
    inode: str
    line: int


def parse_proc_net(text: str, protocol: str) -> list[ListenPort]:
    """Parse ``/proc/net/tcp`` or ``udp`` and keep sockets in state LISTEN."""
    ports: list[ListenPort] = []
    for number, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) < 10 or ":" not in parts[1]:
            continue
        state = parts[3]
        if protocol.startswith("tcp") and state != "0A":
            continue
        if protocol.startswith("udp") and state not in {"07", "0A"}:
            continue
        local, port_hex = parts[1].split(":")
        try:
            address = _decode_address(local)
            port = int(port_hex, 16)
            inode = parts[9]
        except (ValueError, OSError):
            continue
        ports.append(ListenPort(protocol, address, port, inode, number))
    return ports


def _decode_address(hex_addr: str) -> str:
    raw = bytes.fromhex(hex_addr)
    if len(raw) == 4:
        return str(socket.inet_ntop(socket.AF_INET, raw[::-1]))
    groups = [raw[index : index + 4][::-1] for index in range(0, 16, 4)]
    return str(socket.inet_ntop(socket.AF_INET6, b"".join(groups)))


def is_exposed_address(address: str) -> bool:
    """Return whether a bind address accepts connections from outside the host."""
    return address not in {"127.0.0.1", "::1"}


def fingerprint_authorized_keys(text: str) -> list[tuple[int, str, str, str]]:
    """Return ``(line, key_type, sha256 fingerprint, comment)`` for each key."""
    found: list[tuple[int, str, str, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        parsed = _split_key_line(raw.strip())
        if parsed is None:
            continue
        key_type, blob, comment = parsed
        digest = _fingerprint(blob)
        if digest is None:
            continue
        found.append((number, key_type, digest, comment))
    return found


def _split_key_line(line: str) -> tuple[str, str, str] | None:
    if not line or line.startswith("#"):
        return None
    parts = line.split()
    for index, part in enumerate(parts):
        if part.startswith(("ssh-", "ecdsa-", "sk-ssh-", "sk-ecdsa-")):
            if index + 1 >= len(parts):
                return None
            comment = " ".join(parts[index + 2 :])
            return part, parts[index + 1], comment
    return None


def _fingerprint(blob: str) -> str | None:
    try:
        raw = base64.b64decode(blob, validate=True)
    except ValueError:
        return None
    if not raw:
        return None
    encoded = base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
    return f"SHA256:{encoded}"


@dataclass
class ServerSite:
    path: str
    names: list[tuple[int, str]] = field(default_factory=list)
    listens: list[tuple[int, str]] = field(default_factory=list)
    proxies: list[tuple[int, str]] = field(default_factory=list)
    roots: list[tuple[int, str]] = field(default_factory=list)


def parse_nginx(path: str, text: str) -> list[ServerSite]:
    """Extract server blocks. Nested location blocks stay inside the server."""
    sites: list[ServerSite] = []
    current: ServerSite | None = None
    depth = 0
    server_depth: int | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_hash_comment(raw).strip()
        if not line:
            continue
        opens = line.count("{")
        closes = line.count("}")
        if current is None and line.startswith("server") and "{" in line:
            current = ServerSite(path)
            server_depth = depth
            depth += opens - closes
            continue
        if current is not None:
            _take_nginx_directive(current, line, number)
        depth += opens - closes
        if current is not None and server_depth is not None and depth <= server_depth:
            sites.append(current)
            current = None
            server_depth = None
    if current is not None:
        sites.append(current)
    return sites


def _take_nginx_directive(site: ServerSite, line: str, number: int) -> None:
    body = line.replace("{", " ").replace("}", " ")
    if body.startswith("server_name"):
        for name in body.replace(";", "").split()[1:]:
            site.names.append((number, name))
    elif body.startswith("listen"):
        value = body.split(None, 1)[1].replace(";", "").strip() if " " in body else ""
        if value:
            site.listens.append((number, value))
    elif body.startswith("proxy_pass"):
        value = body.split(None, 1)[1].replace(";", "").strip() if " " in body else ""
        if value:
            site.proxies.append((number, value))
    elif body.startswith("root ") or body == "root":
        parts = body.replace(";", "").split()
        if len(parts) >= 2:
            site.roots.append((number, parts[1]))


def parse_apache(path: str, text: str) -> list[ServerSite]:
    """Extract the directives that tie a vhost to a directory or an upstream."""
    site = ServerSite(path)
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_hash_comment(raw).strip()
        lower = line.lower()
        if lower.startswith("servername ") or lower.startswith("serveralias "):
            for name in line.split()[1:]:
                site.names.append((number, name))
        elif lower.startswith("documentroot "):
            site.roots.append((number, line.split(None, 1)[1].strip().strip('"')))
        elif lower.startswith("proxypass "):
            parts = line.split()
            if len(parts) >= 3:
                site.proxies.append((number, parts[2]))
        elif lower.startswith("listen "):
            site.listens.append((number, line.split(None, 1)[1].strip()))
    if not (site.names or site.roots or site.proxies or site.listens):
        return []
    return [site]


def parse_caddy(path: str, text: str) -> list[ServerSite]:
    """Extract site addresses and reverse_proxy lines from a Caddyfile."""
    sites: list[ServerSite] = []
    current: ServerSite | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_hash_comment(raw).strip()
        if not line:
            continue
        if line.endswith("{") and not line.startswith(("reverse_proxy", "root", "file_server")):
            current = ServerSite(path)
            address = line[:-1].strip()
            if address:
                current.names.append((number, address))
            sites.append(current)
            continue
        if current is None:
            continue
        if line.startswith("reverse_proxy"):
            parts = line.split()
            if len(parts) >= 2:
                current.proxies.append((number, parts[1]))
        elif line.startswith("root "):
            parts = line.replace("*", "").split()
            if len(parts) >= 2:
                current.roots.append((number, parts[-1]))
    return [site for site in sites if site.names or site.proxies or site.roots]


def parse_sshd_config(text: str) -> dict[str, tuple[str, int]]:
    """Return the first value of each sshd keyword."""
    found: dict[str, tuple[str, int]] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        key = parts[0].lower()
        value = parts[1].strip() if len(parts) == 2 else ""
        found.setdefault(key, (value, number))
    return found


def sudoers_mentions(text: str, user: str, groups: list[str]) -> list[tuple[int, str]]:
    """Return sudoers lines that name the user or one of their groups."""
    hits: list[tuple[int, str]] = []
    group_names = {f"%{group}" for group in groups}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split()[0]
        if first == user or first in group_names:
            hits.append((number, line))
    return hits


def line_containing(text: str, needle: str) -> tuple[int, str]:
    """Return the first line that contains ``needle``, or line 1."""
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number, line.strip()
    lines = text.splitlines()
    if not lines:
        return 1, ""
    return 1, lines[0].strip()


_PROXY_TARGET = re.compile(r"^(?:\w+://)?(?P<host>\[[^\]]+\]|[^:/]+)?(?::(?P<port>\d+))?")


def port_from_proxy(value: str) -> int | None:
    """Pull a port out of a proxy_pass or upstream URL."""
    match = _PROXY_TARGET.match(value.strip().rstrip(";"))
    if match is None or not match.group("port"):
        return None
    try:
        return int(match.group("port"))
    except ValueError:
        return None


def _strip_hash_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line
