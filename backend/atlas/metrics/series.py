"""Persist host samples and read them back in buckets.

Raw points are the source. A query with a step larger than one second
averages the points that fall in each bucket. Nothing here talks to the network.
"""

from __future__ import annotations

import sqlite3

from atlas.metrics.sampler import HostSample

_ALLOWED_PREFIXES = ("host.",)
_POINT_BYTES = 64
DEFAULT_METRIC_BUDGET = 200 * 1024 * 1024


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
    for unit in sample.units:
        if unit.memory_bytes is not None:
            points.append((f"host.service.{unit.name}.memory_bytes", ts, float(unit.memory_bytes)))
        if unit.cpu_usage_usec is not None:
            points.append(
                (f"host.service.{unit.name}.cpu_usage_usec", ts, float(unit.cpu_usage_usec))
            )
    for container in sample.containers:
        if container.memory_bytes is not None:
            points.append(
                (f"host.container.{container.name}.memory_bytes", ts, float(container.memory_bytes))
            )
        if container.cpu_usage_usec is not None:
            points.append(
                (
                    f"host.container.{container.name}.cpu_usage_usec",
                    ts,
                    float(container.cpu_usage_usec),
                )
            )
    conn.executemany(
        "INSERT OR REPLACE INTO metric_points (series, ts, value) VALUES (?, ?, ?)",
        points,
    )
    conn.commit()


def rollup_and_prune(conn: sqlite3.Connection, *, now: int) -> int:
    """Fold old raw points into rollups and drop what is past the retention window.

    Raw points last 24 hours, one-minute rollups last 30 days, and five-minute
    rollups last 365 days. Returns the number of raw points removed.
    """
    day = 24 * 60 * 60
    month = 30 * day
    year = 365 * day
    _fold(conn, source="metric_points", step=60, older_than=now - day)
    removed = conn.execute("DELETE FROM metric_points WHERE ts < ?", (now - day,)).rowcount
    _fold_rollups(conn, source_step=60, step=300, older_than=now - month)
    conn.execute("DELETE FROM metric_rollups WHERE step = 60 AND ts < ?", (now - month,))
    conn.execute("DELETE FROM metric_rollups WHERE step = 300 AND ts < ?", (now - year,))
    enforce_metric_budget(conn)
    conn.commit()
    return int(removed)


def enforce_metric_budget(
    conn: sqlite3.Connection, *, limit_bytes: int = DEFAULT_METRIC_BUDGET
) -> int:
    """Drop the oldest raw points once their estimate passes ``limit_bytes``.

    Each stored point counts as 64 bytes. The default cap is 200 MiB.
    """
    if limit_bytes < _POINT_BYTES:
        raise ValueError("metric budget is below one point")
    count = int(conn.execute("SELECT COUNT(*) AS n FROM metric_points").fetchone()["n"])
    keep = limit_bytes // _POINT_BYTES
    if count <= keep:
        return 0
    drop = count - keep
    conn.execute(
        "DELETE FROM metric_points WHERE rowid IN ("
        "SELECT rowid FROM metric_points ORDER BY ts ASC, rowid ASC LIMIT ?)",
        (drop,),
    )
    return drop


def _fold(conn: sqlite3.Connection, *, source: str, step: int, older_than: int) -> None:
    if source != "metric_points":
        raise ValueError("unknown metric table")
    rows = conn.execute(
        "SELECT series, ts, value FROM metric_points WHERE ts < ? ORDER BY series, ts",
        (older_than,),
    ).fetchall()
    _write_buckets(conn, rows, step)


def _fold_rollups(
    conn: sqlite3.Connection, *, source_step: int, step: int, older_than: int
) -> None:
    rows = conn.execute(
        "SELECT series, ts, value FROM metric_rollups WHERE step = ? AND ts < ? ORDER BY series, ts",
        (source_step, older_than),
    ).fetchall()
    _write_buckets(conn, rows, step)


def _write_buckets(conn: sqlite3.Connection, rows: list[sqlite3.Row], step: int) -> None:
    buckets: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        bucket = int(row["ts"]) - (int(row["ts"]) % step)
        buckets.setdefault((str(row["series"]), bucket), []).append(float(row["value"]))
    conn.executemany(
        "INSERT INTO metric_rollups (series, step, ts, value) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(series, step, ts) DO UPDATE SET value = excluded.value",
        [(series, step, ts, sum(values) / len(values)) for (series, ts), values in buckets.items()],
    )


_HOST_PREFIXES = ("host.cpu.", "host.memory.", "host.load.", "host.disk.")
_VIRTUAL_IFACE = (
    "docker",
    "br-",
    "veth",
    "virbr",
    "cni",
    "flannel",
    "cali",
    "dummy",
    "tun",
    "tap",
    "ifb",
)


def _virtual_nic(series: str) -> bool:
    if not series.startswith("host.net."):
        return False
    iface = series.removeprefix("host.net.")
    if iface.endswith(".rx_bytes"):
        iface = iface.removesuffix(".rx_bytes")
    elif iface.endswith(".tx_bytes"):
        iface = iface.removesuffix(".tx_bytes")
    else:
        return False
    return iface.startswith(_VIRTUAL_IFACE)


def list_series(conn: sqlite3.Connection) -> list[str]:
    """Return host series that already have a point.

    Container series sort first and used to fill the whole page, which hid the
    uplink. Host totals and physical interfaces stay ahead of that page.
    """
    rows = conn.execute(
        "SELECT DISTINCT series FROM metric_points WHERE series LIKE 'host.%' ORDER BY series"
    ).fetchall()
    names = [str(row["series"]) for row in rows]
    preferred = [
        name
        for name in names
        if name.startswith(_HOST_PREFIXES)
        or (name.startswith("host.net.") and not _virtual_nic(name))
    ]
    rest = [name for name in names if name not in set(preferred)]
    return (preferred + rest)[: max(36, len(preferred))]


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
    if not rows and step > 1:
        rollup_step = 300 if step >= 300 else 60
        rows = conn.execute(
            "SELECT ts, value FROM metric_rollups WHERE series = ? AND step = ? "
            "AND ts >= ? AND ts <= ? ORDER BY ts",
            (series, rollup_step, start, end),
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
