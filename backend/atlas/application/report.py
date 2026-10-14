"""Render a stored scan as Markdown, JSON, or a self-contained HTML file."""

from __future__ import annotations

import html
import json
from typing import Any

from atlas import __version__
from atlas.storage.db import Store

_KINDS = (
    "os",
    "resources",
    "network",
    "service",
    "container",
    "port",
    "user",
    "ssh_key",
    "schedule",
    "site",
    "package",
    "runtime",
    "datastore",
    "firewall",
    "image",
    "volume",
)


def build_report(store: Store, scan_id: int) -> dict[str, Any]:
    """Assemble the export document for one scan."""
    sections = {kind: store.entities(scan_id, kind) for kind in _KINDS}
    facts = store.facts(scan_id)
    return {
        "product": "ATLAS",
        "version": __version__,
        "scan_id": scan_id,
        "sections": sections,
        "unknowns": [fact for fact in facts if fact["certainty"] == "unknown"],
        "sources": store.sources(scan_id),
        "changes": store.changes(scan_id),
        "fact_count": len(facts),
    }


def render_json(report: dict[str, Any]) -> str:
    """Serialize a report as JSON."""
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    """Serialize a report as Markdown tables."""
    lines = [
        "# ATLAS report",
        "",
        f"Scan {report['scan_id']}. {report['fact_count']} facts.",
        "",
    ]
    for kind, rows in report["sections"].items():
        if not rows:
            continue
        lines.extend([f"## {kind}", ""])
        for row in rows:
            lines.append(f"### {row['key']}")
            lines.append("")
            for key, value in row["payload"].items():
                lines.append(f"- {key}: {_md(value)}")
            lines.append("")
    if report["unknowns"]:
        lines.extend(["## Unknown", ""])
        for fact in report["unknowns"]:
            lines.append(f"- `{fact['subject']}` {fact['predicate']}: {_md(fact['value'])}")
        lines.append("")
    unavailable = [row for row in report["sources"] if row["status"] == "unavailable"]
    if unavailable:
        lines.extend(["## Unreadable sources", ""])
        for row in unavailable:
            lines.append(f"- `{row['target']}`: {_md(row['reason'])}")
        lines.append("")
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    """Serialize a report as one HTML document with no external assets."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>ATLAS report</title>",
        "<style>",
        "body{background:#08090a;color:#d0d6e0;font:15px/1.5 Inter,system-ui,sans-serif;margin:32px}",
        "h1,h2{color:#fff;font-weight:590;letter-spacing:-0.011em}",
        "code,pre{font-family:ui-monospace,monospace;color:#d0d6e0}",
        "section{background:#0f1011;border:1px solid #23252a;border-radius:12px;padding:16px;margin:16px 0}",
        "dt{color:#8a8f98} dd{margin:0 0 8px}",
        "</style></head><body>",
        f"<h1>ATLAS report</h1><p>Scan {int(report['scan_id'])}. {int(report['fact_count'])} facts.</p>",
    ]
    for kind, rows in report["sections"].items():
        if not rows:
            continue
        parts.append(f"<section><h2>{_esc(kind)}</h2>")
        for row in rows:
            parts.append(f"<h3>{_esc(row['key'])}</h3><dl>")
            for key, value in row["payload"].items():
                parts.append(f"<dt>{_esc(key)}</dt><dd>{_esc(_flat(value))}</dd>")
            parts.append("</dl>")
        parts.append("</section>")
    if report["unknowns"]:
        parts.append("<section><h2>Unknown</h2><ul>")
        for fact in report["unknowns"]:
            parts.append(
                f"<li><code>{_esc(fact['subject'])}</code> {_esc(fact['predicate'])}: {_esc(fact['value'])}</li>"
            )
        parts.append("</ul></section>")
    parts.append("</body></html>\n")
    return "".join(parts)


def _md(value: object) -> str:
    return _flat(value).replace("|", "\\|")


def _flat(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)
