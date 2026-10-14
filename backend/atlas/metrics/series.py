"""Persist host samples and read them back in buckets.

Raw points are the source. A query with a step larger than one second
averages the points that fall in each bucket. Nothing here talks to the network.
"""

from __future__ import annotations

import sqlite3

from atlas.metrics.sampler import HostSample

_ALLOWED_PREFIXES = ("host.",)


def write_sample(conn: sqlite3.Connection, sample: HostSample) -> None:
    """Store the numeric fields of one sample. Counters are stored as read."""
    ts = int(sample.collected_at)
    points: list[tuple[str, int, float]] = []
    if sample.memory is not None:
        points.append(("host.memory.total_bytes", ts, float(sample.memory.total_bytes)))
        points.append(("host.memory.available_bytes", ts, float(sample.memory.available_bytes)))
    if sample.loadavg is not None:
        points.append(("host.load.1", ts, sample.loadavg[0]))
        points.append(("host.load.5", ts, sample.loadavg[1]))
        points.append(("host.load.15", ts, sample.loadavg[2]))
    if sample.cpu is not None:
        points.append(("host.cpu.idle", ts, sample.cpu.idle))
        points.append(("host.cpu.iowait", ts, sample.cpu.iowait))
        points.append(("host.cpu.steal", ts, sample.cpu.steal))
    for disk in sample.disks:
        points.append((f"host.disk.{disk.name}.read_bytes", ts, float(disk.read_bytes)))
        points.append((f"host.disk.{disk.name}.write_bytes", ts, float(disk.write_bytes)))
    for nic in sample.network:
        points.append((f"host.net.{nic.name}.rx_bytes", ts, float(nic.rx_bytes)))
        points.append((f"host.net.{nic.name}.tx_bytes", ts, float(nic.tx_bytes)))
    conn.executemany(
        "INSERT OR REPLACE INTO metric_points (series, ts, value) VALUES (?, ?, ?)",
        points,
    )
    conn.commit()


def query_series(
    conn: sqlite3.Connection, series: str, start: int, end: int, step: int
) -> list[dict[str, float | int]]:
    """Return averaged points for one series inside ``[start, end]``."""
    if not series.startswith(_ALLOWED_PREFIXES) or any(char in series for char in " \n\t'\""):
        raise ValueError("unknown series")
    if step < 1:
        raise ValueError("step must be at least 1")
    rows = conn.execute(
        "SELECT ts, value FROM metric_points WHERE series = ? AND ts >= ? AND ts <= ? ORDER BY ts",
        (series, start, end),
    ).fetchall()
    if step == 1:
        return [{"ts": int(row["ts"]), "value": float(row["value"])} for row in rows]
    buckets: dict[int, list[float]] = {}
    for row in rows:
        bucket = int(row["ts"]) - (int(row["ts"]) % step)
        buckets.setdefault(bucket, []).append(float(row["value"]))
    return [
        {"ts": ts, "value": sum(values) / len(values)} for ts, values in sorted(buckets.items())
    ]
