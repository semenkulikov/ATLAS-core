"""Run one inventory pass and store the snapshot."""

from __future__ import annotations

import logging

from atlas.collectors.registry import COLLECTORS
from atlas.collectors.view import HostView, try_lower_priority
from atlas.detectors.discover import annotate_references, discover
from atlas.domain import failed_collector
from atlas.logging import get_logger, log_event
from atlas.storage.db import Store

logger = get_logger("atlas.scan")


def run_scan(
    view: HostView,
    store: Store,
    mode: str,
    *,
    lower_priority: bool = False,
) -> int:
    """Collect the host into ``store`` and return the scan id.

    A collector that raises is recorded as unavailable. It does not abort the scan.
    """
    if lower_priority:
        try_lower_priority()
    scan_id = store.start_scan(mode)
    results = []
    try:
        for collector in COLLECTORS:
            log_event(logger, logging.INFO, "collector_start", collector=collector.name)
            try:
                result = collector.collect(view)
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "collector_failed",
                    collector=collector.name,
                    error=exc.__class__.__name__,
                )
                result = failed_collector(collector.name, exc.__class__.__name__, view.now)
            log_event(
                logger,
                logging.INFO,
                "collector_done",
                collector=collector.name,
                facts=len(result.facts),
                sources=len(result.sources),
            )
            results.append(result)
        results = annotate_references(results)
        found = discover(view, results)
        store.persist(scan_id, results)
        store.save_discovery(scan_id, found)
        store.finish_scan(scan_id, "succeeded")
    except Exception as exc:
        store.finish_scan(scan_id, "failed", exc.__class__.__name__)
        raise
    return scan_id
