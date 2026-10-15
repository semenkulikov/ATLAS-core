"""Collectors for web servers, datastores, and container engines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from atlas.collectors.bag import Bag, declare
from atlas.collectors.host import read_packages
from atlas.collectors.parse import (
    ServerSite,
    certificate_not_after,
    parse_apache,
    parse_caddy,
    parse_nginx,
    port_from_proxy,
)
from atlas.collectors.services import _line, files_under, processes
from atlas.collectors.view import HostView
from atlas.domain import CollectorResult

_ENGINE_PATHS = ("/containers/json", "/images/json", "/networks", "/volumes")
_SOCKETS = (
    Path("/var/run/docker.sock"),
    Path("/run/docker.sock"),
    Path("/run/podman/podman.sock"),
)
_DATASTORES = (
    ("postgres", "PostgreSQL", ("postgres", "postmaster")),
    ("mysql", "MySQL", ("mysqld", "mariadbd")),
    ("redis", "Redis", ("redis-server",)),
    ("mongo", "MongoDB", ("mongod",)),
    ("rabbitmq", "RabbitMQ", ("rabbitmq-server",)),
)


class WebCollector:
    """Read nginx, Apache, and Caddy configs and keep the domain to upstream map."""

    name = "web"
    declarations = (
        declare(
            "web",
            "file",
            "/etc/nginx/**",
            "nginx server names, listen ports, roots, and proxy_pass.",
            "Имена, порты, корни и proxy_pass nginx.",
        ),
        declare(
            "web",
            "file",
            "/etc/apache2/sites-enabled/**",
            "Apache vhosts.",
            "Виртуальные хосты Apache.",
        ),
        declare(
            "web",
            "file",
            "/etc/httpd/conf.d/**",
            "Apache vhosts on RHEL layouts.",
            "Виртуальные хосты Apache в раскладке RHEL.",
        ),
        declare(
            "web",
            "file",
            "/etc/caddy/Caddyfile",
            "Caddy sites and reverse proxies.",
            "Сайты и reverse_proxy Caddy.",
        ),
        declare(
            "web",
            "file",
            "/etc/ssl/**",
            "Public certificate named by a web server config.",
            "Публичный сертификат, на который ссылается конфиг веб-сервера.",
        ),
        declare(
            "web",
            "file",
            "/etc/letsencrypt/live/**",
            "Public certificate from Let's Encrypt.",
            "Публичный сертификат Let's Encrypt.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        _collect_nginx(view, bag)
        _collect_apache(view, bag, "/etc/apache2/sites-enabled")
        _collect_apache(view, bag, "/etc/httpd/conf.d")
        caddy = bag.read(view, "/etc/caddy/Caddyfile")
        if caddy.ok and caddy.text:
            sites = parse_caddy("/etc/caddy/Caddyfile", caddy.text)
            for index, site in enumerate(sites):
                _emit_site(bag, "caddy", f"caddy-{index}", site, caddy.sha256, caddy.text)
        return bag.freeze()


class DatastoreCollector:
    """Recognize databases and brokers from packages and process names. Never connects."""

    name = "datastores"
    declarations = (
        declare(
            "datastores",
            "file",
            "/proc/<pid>/comm",
            "Process name of a database or broker.",
            "Имя процесса базы или брокера.",
        ),
        declare(
            "datastores",
            "file",
            "/proc/<pid>/cmdline",
            "Command line of a database or broker.",
            "Командная строка базы или брокера.",
        ),
        declare(
            "datastores",
            "file",
            "/var/lib/dpkg/status",
            "Package version of a recognized datastore.",
            "Версия пакета распознанной службы данных.",
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        packages, target, status, reason = read_packages(view)
        bag.note(target, status, reason)
        running = processes(view)
        units = [Path(path).name for path in files_under(view, "/etc/systemd/system", limit=500)]
        for key, title, comms in _DATASTORES:
            version = next((version for name, version in packages.items() if key in name), None)
            matched = [
                row for row in running if row[1] in comms or any(name in row[2] for name in comms)
            ]
            unit_hit = next((name for name in units if key in name), None)
            if version is None and not matched and unit_hit is None:
                continue
            payload: dict[str, object] = {"engine": title, "version": version, "unit": unit_hit}
            if version is not None:
                bag.add_file(
                    f"datastore:{key}",
                    "datastore.version",
                    version,
                    "/var/lib/dpkg/status",
                    1,
                    f"{key} {version}",
                    None,
                    rule="package.version",
                )
            if matched:
                pid, comm, cmdline = matched[0]
                bag.add_command(
                    f"datastore:{key}",
                    "datastore.process",
                    comm,
                    ["proc", str(pid), "comm"],
                    cmdline or comm,
                    rule="process.comm",
                )
                payload["pid"] = pid
                payload["command"] = cmdline
            else:
                why = (
                    "unit file exists and no matching process was visible"
                    if unit_hit is not None
                    else "package is installed and no matching process was visible"
                )
                bag.add_unknown(f"datastore:{key}", "datastore.process", why)
            bag.entity("datastore", key, payload)
        return bag.freeze()


class ContainerCollector:
    """Read Docker or Podman through the engine API. Only GET requests are issued."""

    name = "containers"
    declarations = (
        declare(
            "containers",
            "api",
            "GET /containers/json",
            "Containers, ports, labels, and restart policy.",
            "Контейнеры, порты, метки и политика перезапуска.",
            requires_root=True,
        ),
        declare(
            "containers",
            "api",
            "GET /images/json",
            "Images known to the engine.",
            "Образы, известные движку.",
            requires_root=True,
        ),
        declare(
            "containers",
            "api",
            "GET /networks",
            "Engine networks.",
            "Сети движка.",
            requires_root=True,
        ),
        declare(
            "containers",
            "api",
            "GET /volumes",
            "Engine volumes.",
            "Тома движка.",
            requires_root=True,
        ),
        declare(
            "containers",
            "file",
            "/var/run/docker.sock",
            "Docker engine socket, read-only methods.",
            "Сокет Docker, только методы чтения.",
            requires_root=True,
        ),
        declare(
            "containers",
            "file",
            "/run/podman/podman.sock",
            "Podman engine socket, read-only methods.",
            "Сокет Podman, только методы чтения.",
            requires_root=True,
        ),
    )

    def collect(self, view: HostView) -> CollectorResult:
        bag = Bag(self.name, view.now)
        payload, origin, status = engine_payload(view)
        bag.note(origin, status, None if status == "ok" else origin)
        if payload is None:
            if status == "unavailable":
                bag.add_unknown("host", "containers", origin)
            return bag.freeze()
        for item in _as_list(payload.get("containers")):
            _emit_container(bag, item)
        for item in _as_list(payload.get("images")):
            if isinstance(item, dict):
                image_id = str(item.get("Id", ""))[:20] or "untagged"
                bag.entity(
                    "image",
                    image_id,
                    {
                        "id": item.get("Id"),
                        "tags": item.get("RepoTags") or [],
                        "size": item.get("Size"),
                    },
                )
        for item in _as_list(payload.get("networks")):
            if isinstance(item, dict) and item.get("Name"):
                bag.entity(
                    "network",
                    str(item["Name"]),
                    {"name": item["Name"], "driver": item.get("Driver")},
                )
        volumes = payload.get("volumes")
        volume_rows = volumes.get("Volumes") if isinstance(volumes, dict) else volumes
        for item in _as_list(volume_rows):
            if isinstance(item, dict) and item.get("Name"):
                bag.entity(
                    "volume",
                    str(item["Name"]),
                    {"name": item["Name"], "mountpoint": item.get("Mountpoint")},
                )
        return bag.freeze()


def engine_get(sock: Path, path: str) -> Any:
    """GET one allowlisted engine path. Any other path is refused."""
    base = path.split("?", 1)[0]
    if base not in _ENGINE_PATHS:
        raise ValueError(f"engine path is not allowlisted: {base}")
    transport = httpx.HTTPTransport(uds=str(sock))
    with httpx.Client(transport=transport, base_url="http://docker", timeout=5.0) as client:
        response = client.get(path)
        response.raise_for_status()
        body: Any = response.json()
        return body


def engine_payload(view: HostView) -> tuple[dict[str, Any] | None, str, str]:
    """Return ``(payload, origin, status)`` from a fixture file or a local engine socket."""
    fixture = view.fixture_json("docker.json")
    if isinstance(fixture, dict):
        return fixture, "docker.json", "ok"
    if not view.is_live:
        return None, "container engine", "absent"
    for sock in _SOCKETS:
        if not sock.exists():
            continue
        try:
            payload = {
                "containers": engine_get(sock, "/containers/json?all=1"),
                "images": engine_get(sock, "/images/json"),
                "networks": engine_get(sock, "/networks"),
                "volumes": engine_get(sock, "/volumes"),
            }
        except (OSError, httpx.HTTPError, ValueError) as exc:
            if view.helper_socket:
                break
            return None, f"{sock}: {exc.__class__.__name__}", "unavailable"
        return payload, str(sock), "ok"
    if view.helper_socket:
        from atlas.helper.client import engine_bundle

        try:
            payload = engine_bundle(view.helper_socket)
        except (OSError, ValueError) as exc:
            return None, f"helper: {exc.__class__.__name__}", "unavailable"
        if payload is None:
            return None, "helper:engine", "unavailable"
        return payload, "helper:engine", "ok"
    return None, "container engine", "absent"


def _collect_nginx(view: HostView, bag: Bag) -> None:
    if not view.mapped("/etc/nginx").exists():
        bag.note("/etc/nginx", "absent", "nginx config directory is not present")
        return
    for logical in files_under(view, "/etc/nginx", limit=200):
        outcome = bag.read(view, logical)
        if not outcome.ok or outcome.text is None:
            continue
        for index, site in enumerate(parse_nginx(logical, outcome.text)):
            _emit_site(bag, "nginx", f"{logical}:{index}", site, outcome.sha256, outcome.text)
            _emit_certificates(view, bag, site)


def _collect_apache(view: HostView, bag: Bag, directory: str) -> None:
    if not view.mapped(directory).exists():
        bag.note(directory, "absent", "directory is not present")
        return
    for logical in files_under(view, directory, limit=100):
        outcome = bag.read(view, logical)
        if not outcome.ok or outcome.text is None:
            continue
        for index, site in enumerate(parse_apache(logical, outcome.text)):
            _emit_site(bag, "apache", f"{logical}:{index}", site, outcome.sha256, outcome.text)


def _public_cert_path(path: str) -> bool:
    name = Path(path).name.lower()
    if name.endswith(".key") or "privkey" in name or "private" in name:
        return False
    allowed = ("/etc/ssl/", "/etc/nginx/", "/etc/letsencrypt/live/")
    return path.startswith(allowed) and name.endswith((".crt", ".pem", ".cer"))


def _emit_certificates(view: HostView, bag: Bag, site: ServerSite) -> None:
    for line, path in site.certificates:
        if not _public_cert_path(path):
            bag.add_unknown("certificate", path, "a private key path is not read")
            continue
        outcome = bag.read(view, path)
        if not outcome.ok or outcome.text is None:
            continue
        expiry = certificate_not_after(outcome.text)
        if expiry is None:
            bag.add_unknown("certificate", path, "the certificate expiry could not be read")
            continue
        bag.add_file(
            f"certificate:{path}",
            "cert.not_after",
            expiry.isoformat(),
            path,
            line,
            expiry.date().isoformat(),
            outcome.sha256,
        )
        bag.entity("certificate", path, {"path": path, "not_after": expiry.isoformat()})


def _emit_site(
    bag: Bag,
    server: str,
    key: str,
    site: ServerSite,
    digest: str | None,
    text: str,
) -> None:
    subject = f"site:{key}"
    names = [name for _, name in site.names]
    if site.names:
        line, _value = site.names[0]
        bag.add_file(
            subject, "site.names", " ".join(names), site.path, line, _line(text, line), digest
        )
    else:
        bag.add_unknown(subject, "site.names", "server name is not set")
    for line, value in site.proxies:
        bag.add_file(subject, "site.proxy_pass", value, site.path, line, _line(text, line), digest)
        port = port_from_proxy(value)
        if port is not None:
            bag.add_file(
                subject,
                "site.proxy_port",
                str(port),
                site.path,
                line,
                _line(text, line),
                digest,
                rule="proxy_pass.port",
            )
    for line, value in site.roots:
        bag.add_file(subject, "site.root", value, site.path, line, _line(text, line), digest)
    bag.entity(
        "site",
        key,
        {
            "server": server,
            "names": names,
            "listens": [value for _, value in site.listens],
            "proxies": [value for _, value in site.proxies],
            "roots": [value for _, value in site.roots],
            "path": site.path,
        },
    )


def _emit_container(bag: Bag, item: object) -> None:
    if not isinstance(item, dict):
        return
    container_id = str(item.get("Id", ""))
    names = item.get("Names") if isinstance(item.get("Names"), list) else []
    name = str(names[0]).lstrip("/") if names else container_id[:12]
    labels = item.get("Labels") if isinstance(item.get("Labels"), dict) else {}
    raw_host = item.get("HostConfig")
    host: dict[str, Any] = raw_host if isinstance(raw_host, dict) else {}
    raw_policy = host.get("RestartPolicy")
    policy: dict[str, Any] = raw_policy if isinstance(raw_policy, dict) else {}
    raw_binds = host.get("Binds")
    binds = raw_binds if isinstance(raw_binds, list) else []
    raw_mounts = item.get("Mounts")
    mounts = raw_mounts if isinstance(raw_mounts, list) else []
    subject = f"container:{container_id or name}"
    state = str(item.get("State", ""))
    bag.add_command(
        subject,
        "container.state",
        state,
        ["GET", "/containers/json"],
        json.dumps({"name": name, "image": item.get("Image"), "state": state})[:200],
    )
    bag.entity(
        "container",
        container_id or name,
        {
            "id": container_id,
            "name": name,
            "image": item.get("Image"),
            "state": state,
            "status": item.get("Status"),
            "ports": item.get("Ports") if isinstance(item.get("Ports"), list) else [],
            "labels": labels,
            "restart_policy": policy.get("Name"),
            "binds": binds,
            "mounts": mounts,
        },
    )


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []
