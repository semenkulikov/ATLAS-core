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
    scan.add_argument("--output", default="atlas-report", help="Report path without an extension.")
    scan.add_argument("--db", default=None, help="Also store the snapshot in this SQLite file.")
    scan.set_defaults(func=cmd_scan)
    manifest = sub.add_parser("manifest", help="Print the list of sources ATLAS reads")
    manifest.add_argument("--lang", choices=("en", "ru"), default="en")
    manifest.set_defaults(func=cmd_manifest)
    serve = sub.add_parser("serve", help="Serve the panel API")
    serve.add_argument("--db", required=True, help="SQLite file for scans and accounts.")
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
    serve.set_defaults(func=cmd_serve)
    token = sub.add_parser("token", help="Manage one-time install tokens")
    token_sub = token.add_subparsers(dest="token_command", required=True)
    token_new = token_sub.add_parser("new", help="Print a one-time owner enrollment token")
    token_new.add_argument("--db", required=True)
    token_new.set_defaults(func=cmd_token_new)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan ``--root`` and write the requested report files."""
    view = open_view(Path(args.root))
    formats = args.formats or ["md", "json", "html"]
    if args.db:
        store = Store.open(Path(args.db))
        try:
            scan_id = run_scan(view, store, "manual", lower_priority=True)
            _write_reports(store, scan_id, Path(args.output), formats)
        finally:
            store.close()
        return 0
    with tempfile.TemporaryDirectory(prefix="atlas-scan-") as temporary:
        store = Store.open(Path(temporary) / "scan.db")
        try:
            scan_id = run_scan(view, store, "oneshot", lower_priority=True)
            _write_reports(store, scan_id, Path(args.output), formats)
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
        )
        uvicorn.run(create_app(store, settings), host=host, port=int(port_text), log_config=None)
        return 0
    socket_path = args.socket or "/run/atlas/web.sock"
    settings = Settings(Path(args.root), tls=bool(args.tls), allowed_hosts=hosts)
    uvicorn.run(create_app(store, settings), uds=socket_path, log_config=None)
    return 0


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
