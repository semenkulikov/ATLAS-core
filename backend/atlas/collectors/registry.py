"""The collector registry and the data-collection manifest."""

from __future__ import annotations

from atlas.collectors.host import (
    NetworkCollector,
    OsCollector,
    PackagesCollector,
    ResourcesCollector,
    SshCollector,
    UsersCollector,
)
from atlas.collectors.platforms import ContainerCollector, DatastoreCollector, WebCollector
from atlas.collectors.services import (
    FirewallCollector,
    PortsCollector,
    SchedulerCollector,
    SystemdCollector,
)
from atlas.domain import SourceDeclaration

COLLECTORS = (
    OsCollector(),
    ResourcesCollector(),
    NetworkCollector(),
    PackagesCollector(),
    UsersCollector(),
    SshCollector(),
    SystemdCollector(),
    SchedulerCollector(),
    PortsCollector(),
    FirewallCollector(),
    WebCollector(),
    DatastoreCollector(),
    ContainerCollector(),
)


def declarations() -> tuple[SourceDeclaration, ...]:
    """Return every source the collectors have declared."""
    rows: list[SourceDeclaration] = []
    for collector in COLLECTORS:
        rows.extend(collector.declarations)
    return tuple(rows)


def render_manifest(language: str) -> str:
    """Render the public list of files and commands ATLAS reads."""
    english = language != "ru"
    title = "What ATLAS reads" if english else "Что читает ATLAS"
    intro = (
        "Every collector declares its sources. A scan records when a source was missing or unreadable. "
        "ATLAS does not read /etc/shadow, private keys, or the values of environment files."
        if english
        else "Каждый сборщик объявляет свои источники. Сканирование записывает, если источник отсутствует или недоступен. "
        "ATLAS не читает /etc/shadow, закрытые ключи и значения файлов окружения."
    )
    header = (
        "| Collector | Kind | Source | Root | Purpose |"
        if english
        else "| Сборщик | Вид | Источник | Root | Назначение |"
    )
    lines = [f"# {title}", "", intro, "", header, "| --- | --- | --- | --- | --- |"]
    for row in declarations():
        purpose = row.purpose_en if english else row.purpose_ru
        root = "yes" if row.requires_root else "no"
        lines.append(f"| {row.collector} | {row.kind} | `{row.target}` | {root} | {purpose} |")
    lines.append("")
    return "\n".join(lines)
