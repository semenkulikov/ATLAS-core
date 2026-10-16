"""Command line entry point for a one-off scan."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from atlas.application.report import build_report, render_html, render_json, render_markdown
from atlas.application.scan import run_scan
from atlas.collectors.view import open_view
from atlas.logging import configure_logging
from atlas.storage.db import Store

_HOST_DB = Path("/var/lib/atlas/atlas.db")


def _host_db_default() -> str | None:
    """Prefer the installed database when it is already on disk."""
    return str(_HOST_DB) if _HOST_DB.is_file() else None


def _add_db(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    default = _host_db_default()
    parser.add_argument(
        "--db",
        default=default,
        required=required and default is None,
        help="SQLite file. Defaults to /var/lib/atlas/atlas.db when installed.",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the ATLAS command line and return a process status."""
    configure_logging()
    parser = argparse.ArgumentParser(prog="atlas", description="Inventory one Linux server.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Scan a host and write a report")
    scan.add_argument(
        "--root", default="/", help="Filesystem root. A fixture directory scans only that tree."
    )
    scan.add_argument(
        "--format",
        action="append",
        choices=("md", "json", "html"),
        dest="formats",
        help="Repeat to choose formats. The default is all three.",
    )
    scan.add_argument(
        "--output",
        default="/var/lib/atlas/reports/latest" if _HOST_DB.is_file() else "atlas-report",
        help="Report path without an extension.",
    )
    _add_db(scan)
    scan.add_argument(
        "--helper-socket",
        default="/run/atlas/helper.sock",
        help="Unix socket of the root helper for privileged inventory reads.",
    )
    scan.set_defaults(func=cmd_scan)
    manifest = sub.add_parser("manifest", help="Print the list of sources ATLAS reads")
    manifest.add_argument("--lang", choices=("en", "ru"), default="en")
    manifest.set_defaults(func=cmd_manifest)
    serve = sub.add_parser("serve", help="Serve the panel API")
    _add_db(serve, required=True)
    serve.add_argument("--root", default="/", help="Filesystem root the panel is allowed to read.")
    serve.add_argument("--socket", default="", help="Unix socket path. Used when --tcp is omitted.")
    serve.add_argument("--tcp", default="", help="Loopback address, for example 127.0.0.1:8765.")
    serve.add_argument(
        "--tls", action="store_true", help="Mark cookies Secure and allow a public bind."
    )
    serve.add_argument(
        "--allow", action="append", default=[], help="Client IP allowed when binding publicly."
    )
    serve.add_argument("--host-name", action="append", default=[], help="Accepted Host header.")
    serve.add_argument(
        "--helper-socket",
        default="",
        help="Unix socket of the root helper. Empty means control calls are refused.",
    )
    serve.set_defaults(func=cmd_serve)
    control = sub.add_parser("control", help="Turn host control on or off")
    control_sub = control.add_subparsers(dest="control_command", required=True)
    for name in ("enable", "disable"):
        item = control_sub.add_parser(name)
        _add_db(item, required=True)
        item.set_defaults(func=cmd_control)
    token = sub.add_parser("token", help="Manage one-time install tokens")
    token_sub = token.add_subparsers(dest="token_command", required=True)
    token_new = token_sub.add_parser("new", help="Print a one-time owner enrollment token")
    _add_db(token_new, required=True)
    token_new.set_defaults(func=cmd_token_new)
    status = sub.add_parser("status", help="Show the version, control switch, and latest scan")
    _add_db(status, required=True)
    status.set_defaults(func=cmd_status)
    doctor = sub.add_parser("doctor", help="Check file permissions and outbound alert channels")
    _add_db(doctor, required=True)
    doctor.set_defaults(func=cmd_doctor)
    reset = sub.add_parser("user", help="Local account recovery")
    reset_sub = reset.add_subparsers(dest="user_command", required=True)
    reset_2fa = reset_sub.add_parser("reset-2fa", help="Replace the owner TOTP secret")
    _add_db(reset_2fa, required=True)
    reset_2fa.add_argument("--username", default="owner")
    reset_2fa.set_defaults(func=cmd_reset_2fa)
    expose = sub.add_parser("expose", help="Show how the panel may be reached")
    expose.set_defaults(func=cmd_expose)
    uninstall = sub.add_parser("uninstall", help="Remove ATLAS files under a prefix")
    uninstall.add_argument("--prefix", default="/")
    uninstall.add_argument("--purge", action="store_true")
    uninstall.set_defaults(func=cmd_uninstall)
    exported = sub.add_parser("export", help="Write the latest completed scan as a report")
    _add_db(exported, required=True)
    exported.add_argument(
        "--format",
        action="append",
        choices=("md", "json", "html"),
        dest="formats",
        help="Repeat to choose formats. The default is all three.",
    )
    exported.add_argument(
        "--output", default="atlas-export", help="Report path without an extension."
    )
    exported.set_defaults(func=cmd_export)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan ``--root`` and write the requested report files."""
    helper = getattr(args, "helper_socket", None) or "/run/atlas/helper.sock"
    helper_path = helper if Path(helper).exists() else None
    view = open_view(Path(args.root), helper_socket=helper_path)
    formats = args.formats or ["md", "json", "html"]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.db:
        store = Store.open(Path(args.db))
        try:
            scan_id = run_scan(
                view, store, "manual", lower_priority=True, helper_socket=helper_path
            )
            _write_reports(store, scan_id, output, formats)
        finally:
            store.close()
        return 0
    with tempfile.TemporaryDirectory(prefix="atlas-scan-") as temporary:
        store = Store.open(Path(temporary) / "scan.db")
        try:
            scan_id = run_scan(
                view, store, "oneshot", lower_priority=True, helper_socket=helper_path
            )
            _write_reports(store, scan_id, output, formats)
        finally:
            store.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the API on a Unix socket, or on loopback when ``--tcp`` is set."""
    import uvicorn

    from atlas.api.app import create_app
    from atlas.api.settings import Settings, refuse_public_bind

    db_path = Path(args.db)
    store = Store.open(db_path)
    _start_sampler(store)
    hosts = tuple(args.host_name) or ("127.0.0.1", "localhost")
    if args.tcp:
        host, _, port_text = args.tcp.rpartition(":")
        if not host or not port_text.isdigit():
            sys.stderr.write("Use --tcp 127.0.0.1:PORT.\n")
            return 2
        refuse_public_bind(host, tls=bool(args.tls), allowed_ips=tuple(args.allow))
        settings = Settings(
            Path(args.root),
            tls=bool(args.tls),
            allowed_hosts=hosts,
            allowed_ips=tuple(args.allow),
            public_bind=host not in {"127.0.0.1", "localhost", "::1"},
            helper_socket=args.helper_socket,
        )
        uvicorn.run(create_app(store, settings), host=host, port=int(port_text), log_config=None)
        return 0
    socket_path = args.socket or "/run/atlas/web.sock"
    _unlink_socket(socket_path)
    _tighten_socket(socket_path)
    settings = Settings(
        Path(args.root),
        tls=bool(args.tls),
        allowed_hosts=hosts,
        helper_socket=args.helper_socket,
    )
    uvicorn.run(create_app(store, settings), uds=socket_path, log_config=None)
    return 0


def _unlink_socket(socket_path: str) -> None:
    """Remove a stale Unix socket so bind can succeed after a crash."""
    import os

    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        return
    except OSError:
        return


def _tighten_socket(socket_path: str) -> None:
    """Make the panel socket group-readable. A world-writable socket is refused."""
    import os
    import threading
    import time

    def once() -> None:
        for _ in range(50):
            if os.path.exists(socket_path):
                # Group-writable Unix socket for the atlas service user (not a world file).
                os.chmod(socket_path, 0o660)  # nosec B103  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
                return
            time.sleep(0.1)

    threading.Thread(target=once, name="atlas-socket", daemon=True).start()


def _start_sampler(store: Store) -> None:
    """Record one sample immediately, then one every 10 seconds, while serve runs."""
    import threading
    import time

    from atlas.logging import get_logger
    from atlas.metrics.sampler import default_sampler
    from atlas.metrics.series import rollup_and_prune, write_sample

    sampler = default_sampler()
    logger = get_logger("atlas.metrics")

    def once() -> None:
        try:
            sample = sampler.sample()
            write_sample(store.conn, sample)
            rollup_and_prune(store.conn, now=int(sample.collected_at))
        except Exception:
            logger.exception("metrics.sample_failed")

    def loop() -> None:
        while True:
            time.sleep(10)
            once()

    once()
    threading.Thread(target=loop, name="atlas-metrics", daemon=True).start()


def cmd_token_new(args: argparse.Namespace) -> int:
    """Print a one-time enrollment token. It is not stored in the clear."""
    from datetime import UTC, datetime

    from atlas.security.accounts import AccessError, issue_bootstrap

    store = Store.open(Path(args.db))
    try:
        token = issue_bootstrap(store.conn, now=datetime.now(UTC), ttl_seconds=15 * 60)
    except AccessError as exc:
        sys.stderr.write(exc.message + "\n")
        return 1
    finally:
        store.close()
    sys.stdout.write(token + "\n")
    return 0


def cmd_control(args: argparse.Namespace) -> int:
    """Turn the control switch on or off and record that in the audit chain."""
    from datetime import UTC, datetime

    from atlas.application.actions import set_control
    from atlas.application.audit import append_audit

    enabled = args.control_command == "enable"
    store = Store.open(Path(args.db))
    try:
        set_control(store, enabled)
        append_audit(
            store.conn,
            actor="cli",
            ip="local",
            action="control.enable" if enabled else "control.disable",
            params={},
            result="ok",
            now=datetime.now(UTC),
        )
    finally:
        store.close()
    sys.stdout.write("control on\n" if enabled else "control off\n")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print the product version and whether control is on."""
    from atlas import __version__
    from atlas.application.actions import control_enabled

    store = Store.open(Path(args.db))
    try:
        scan_id = store.latest_scan_id()
        state = "on" if control_enabled(store) else "off"
    finally:
        store.close()
    sys.stdout.write(f"atlas {__version__}\ncontrol {state}\nlatest scan {scan_id}\n")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Print checks. Exit 1 when a finding is unsafe."""
    from atlas.application.lifecycle import diagnose

    database = Path(args.db)
    observed = database.stat().st_mode & 0o777
    store = Store.open(database)
    try:
        notes = diagnose(store, database, observed_mode=observed)
    finally:
        store.close()
    sys.stdout.write("\n".join(notes) + "\n")
    return 1 if any(note.startswith("warning:") for note in notes) else 0


def cmd_reset_2fa(args: argparse.Namespace) -> int:
    """Print a new TOTP provisioning URI for the owner. The old secret stops working."""
    from atlas.security.accounts import AccessError, reset_owner_totp

    store = Store.open(Path(args.db))
    try:
        uri = reset_owner_totp(store.conn, args.username)
    except AccessError as exc:
        sys.stderr.write(exc.message + "\n")
        return 1
    finally:
        store.close()
    sys.stdout.write(uri + "\n")
    return 0


def cmd_expose(_args: argparse.Namespace) -> int:
    """Print the supported ways to reach the panel."""
    sys.stdout.write(
        "Default listener: unix socket /run/atlas/web.sock\n"
        "Loopback TCP: atlas serve --tcp 127.0.0.1:8765\n"
        "A public address starts only with --tls and at least one --allow address.\n"
    )
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove product files. The database stays unless --purge is set."""
    import subprocess  # nosec B404

    from atlas.application.lifecycle import uninstall

    def run(argv: list[str]) -> None:
        subprocess.run(argv, check=False)  # nosec B603

    removed = uninstall(Path(args.prefix), purge=bool(args.purge), run=run)
    sys.stdout.write("removed " + (", ".join(removed) if removed else "nothing") + "\n")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Write the newest succeeded scan. A database with no scan exits with status 1."""
    store = Store.open(Path(args.db))
    try:
        scan_id = store.latest_scan_id()
        if scan_id is None:
            sys.stderr.write("no completed scan\n")
            return 1
        _write_reports(store, scan_id, Path(args.output), args.formats or ["md", "json", "html"])
    finally:
        store.close()
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    """Print the data-collection manifest."""
    from atlas.collectors.registry import render_manifest

    sys.stdout.write(render_manifest(args.lang))
    return 0


def _write_reports(store: Store, scan_id: int, output: Path, formats: list[str]) -> None:
    report = build_report(store, scan_id)
    writers = {"md": render_markdown, "json": render_json, "html": render_html}
    written: list[str] = []
    for fmt in formats:
        path = output.with_suffix(f".{fmt}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(writers[fmt](report), encoding="utf-8")
        written.append(str(path))
    unavailable = sum(1 for row in report["sources"] if row["status"] == "unavailable")
    sys.stdout.write(
        f"scan {scan_id} finished: {report['fact_count']} facts, {unavailable} sources unavailable\n"
    )
    sys.stdout.write("wrote " + ", ".join(written) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
