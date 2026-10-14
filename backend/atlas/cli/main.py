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
