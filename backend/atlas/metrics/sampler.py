"""Host metrics sampler.

The hot path stays behind :class:`MetricsSampler`. Inventory, the API, and the
panel depend on that interface only, so the implementation can move to another
language if the memory budget in the design notes is missed.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CpuTimes:
    """Cumulative CPU counters. Deltas are computed by the caller."""

    user: float
    nice: float
    system: float
    idle: float
    iowait: float
    irq: float
    softirq: float
    steal: float

    @property
    def total(self) -> float:
        return (
            self.user
            + self.nice
            + self.system
            + self.idle
            + self.iowait
            + self.irq
            + self.softirq
            + self.steal
        )


@dataclass(frozen=True, slots=True)
class MemorySample:
    total_bytes: int
    available_bytes: int
    swap_total_bytes: int
    swap_free_bytes: int


@dataclass(frozen=True, slots=True)
class DiskSample:
    name: str
    read_bytes: int
    write_bytes: int
    reads: int
    writes: int


@dataclass(frozen=True, slots=True)
class NetSample:
    name: str
    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int
    rx_errors: int
    tx_errors: int


@dataclass(frozen=True, slots=True)
class CgroupSample:
    """One cgroup reading for a systemd unit or a container."""

    kind: str
    name: str
    memory_bytes: int | None
    cpu_usage_usec: int | None


@dataclass(frozen=True, slots=True)
class HostSample:
    """One reading of the host. Missing sources are ``None`` or empty tuples."""

    collected_at: float
    cpu: CpuTimes | None
    cores: tuple[CpuTimes, ...]
    loadavg: tuple[float, float, float] | None
    memory: MemorySample | None
    disks: tuple[DiskSample, ...]
    network: tuple[NetSample, ...]
    source: str
    units: tuple[CgroupSample, ...] = ()
    containers: tuple[CgroupSample, ...] = ()


class MetricsSampler(Protocol):
    """Narrow hot-path interface shared by the Python sampler and any replacement."""

    def sample(self) -> HostSample:
        """Return one host sample. A missing source leaves its field empty."""


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _cpu_from_fields(fields: list[str]) -> CpuTimes | None:
    numbers: list[float] = []
    for part in fields[1:9]:
        try:
            numbers.append(float(part))
        except ValueError:
            return None
    while len(numbers) < 8:
        numbers.append(0.0)
    return CpuTimes(
        user=numbers[0],
        nice=numbers[1],
        system=numbers[2],
        idle=numbers[3],
        iowait=numbers[4],
        irq=numbers[5],
        softirq=numbers[6],
        steal=numbers[7],
    )


class ProcMetricsSampler:
    """Read Linux ``/proc`` directly. This is the default hot path."""

    def __init__(self, proc_root: Path | None = None) -> None:
        self._proc = proc_root or Path("/proc")

    def sample(self) -> HostSample:
        cpu, cores = self._cpu()
        units, containers = self._cgroups()
        return HostSample(
            collected_at=time.time(),
            cpu=cpu,
            cores=cores,
            loadavg=self._loadavg(),
            memory=self._memory(),
            disks=self._disks(),
            network=self._network(),
            source="proc",
            units=units,
            containers=containers,
        )

    def _cpu(self) -> tuple[CpuTimes | None, tuple[CpuTimes, ...]]:
        text = _read(self._proc / "stat")
        if text is None:
            return None, ()
        total: CpuTimes | None = None
        cores: list[CpuTimes] = []
        for line in text.splitlines():
            fields = line.split()
            if not fields:
                continue
            if fields[0] == "cpu":
                total = _cpu_from_fields(fields)
            elif fields[0].startswith("cpu"):
                core = _cpu_from_fields(fields)
                if core is not None:
                    cores.append(core)
        return total, tuple(cores)

    def _loadavg(self) -> tuple[float, float, float] | None:
        text = _read(self._proc / "loadavg")
        if text is None:
            return None
        parts = text.split()
        if len(parts) < 3:
            return None
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return None

    def _memory(self) -> MemorySample | None:
        text = _read(self._proc / "meminfo")
        if text is None:
            return None
        values: dict[str, int] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            number = raw.strip().split()
            if not number:
                continue
            try:
                values[key] = int(number[0]) * 1024
            except ValueError:
                continue
        if "MemTotal" not in values:
            return None
        return MemorySample(
            total_bytes=values.get("MemTotal", 0),
            available_bytes=values.get("MemAvailable", values.get("MemFree", 0)),
            swap_total_bytes=values.get("SwapTotal", 0),
            swap_free_bytes=values.get("SwapFree", 0),
        )

    def _disks(self) -> tuple[DiskSample, ...]:
        text = _read(self._proc / "diskstats")
        if text is None:
            return ()
        disks: list[DiskSample] = []
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 14:
                continue
            name = parts[2]
            if name.startswith(("loop", "ram")):
                continue
            try:
                disks.append(
                    DiskSample(
                        name=name,
                        reads=int(parts[3]),
                        read_bytes=int(parts[5]) * 512,
                        writes=int(parts[7]),
                        write_bytes=int(parts[9]) * 512,
                    )
                )
            except ValueError:
                continue
        return tuple(disks)

    def _network(self) -> tuple[NetSample, ...]:
        text = _read(self._proc / "net" / "dev")
        if text is None:
            return ()
        rows: list[NetSample] = []
        for line in text.splitlines():
            if ":" not in line:
                continue
            name, rest = line.split(":", 1)
            name = name.strip()
            if name == "lo":
                continue
            parts = rest.split()
            if len(parts) < 11:
                continue
            try:
                rows.append(
                    NetSample(
                        name=name,
                        rx_bytes=int(parts[0]),
                        rx_packets=int(parts[1]),
                        rx_errors=int(parts[2]),
                        tx_bytes=int(parts[8]),
                        tx_packets=int(parts[9]),
                        tx_errors=int(parts[10]),
                    )
                )
            except ValueError:
                continue
        return tuple(rows)

    def _cgroups(self) -> tuple[tuple[CgroupSample, ...], tuple[CgroupSample, ...]]:
        root = Path("/sys/fs/cgroup")
        if not root.is_dir():
            return (), ()
        units: list[CgroupSample] = []
        containers: list[CgroupSample] = []
        slice_dir = root / "system.slice"
        if slice_dir.is_dir():
            try:
                entries = sorted(slice_dir.iterdir())
            except OSError:
                entries = []
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                name = entry.name
                if name.endswith(".service"):
                    sample = _cgroup_sample("service", name.removesuffix(".service"), entry)
                    if sample is not None:
                        units.append(sample)
                    if len(units) >= 12:
                        break
                if name.startswith("docker-") and name.endswith(".scope"):
                    cid = name.removeprefix("docker-").removesuffix(".scope")[:12]
                    sample = _cgroup_sample("container", cid, entry)
                    if sample is not None:
                        containers.append(sample)
                    if len(containers) >= 12:
                        break
        return tuple(units), tuple(containers)


def _cgroup_sample(kind: str, name: str, directory: Path) -> CgroupSample | None:
    if not name or any(char in name for char in "/ \n\t'\""):
        return None
    memory_text = _read(directory / "memory.current")
    cpu_text = _read(directory / "cpu.stat")
    memory_bytes = None
    cpu_usage = None
    if memory_text is not None:
        try:
            memory_bytes = int(memory_text.strip())
        except ValueError:
            memory_bytes = None
    if cpu_text is not None:
        for line in cpu_text.splitlines():
            if line.startswith("usage_usec "):
                try:
                    cpu_usage = int(line.split()[1])
                except (IndexError, ValueError):
                    cpu_usage = None
                break
    if memory_bytes is None and cpu_usage is None:
        return None
    return CgroupSample(kind, name, memory_bytes, cpu_usage)


class PsutilMetricsSampler:
    """Fallback used where ``/proc`` is absent, including developer machines."""

    def sample(self) -> HostSample:
        import psutil

        times = psutil.cpu_times()
        cpu = CpuTimes(
            user=float(getattr(times, "user", 0.0)),
            nice=float(getattr(times, "nice", 0.0)),
            system=float(getattr(times, "system", 0.0)),
            idle=float(getattr(times, "idle", 0.0)),
            iowait=float(getattr(times, "iowait", 0.0)),
            irq=float(getattr(times, "irq", 0.0)),
            softirq=float(getattr(times, "softirq", 0.0)),
            steal=float(getattr(times, "steal", 0.0)),
        )
        virtual = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disks = tuple(
            DiskSample(
                name=name,
                read_bytes=int(row.read_bytes),
                write_bytes=int(row.write_bytes),
                reads=int(row.read_count),
                writes=int(row.write_count),
            )
            for name, row in (psutil.disk_io_counters(perdisk=True) or {}).items()
        )
        network = tuple(
            NetSample(
                name=name,
                rx_bytes=int(row.bytes_recv),
                tx_bytes=int(row.bytes_sent),
                rx_packets=int(row.packets_recv),
                tx_packets=int(row.packets_sent),
                rx_errors=int(row.errin),
                tx_errors=int(row.errout),
            )
            for name, row in psutil.net_io_counters(pernic=True).items()
            if name not in {"lo", "lo0"}
        )
        load: tuple[float, float, float] | None
        try:
            one, five, fifteen = os.getloadavg()
            load = (one, five, fifteen)
        except OSError:
            load = None
        return HostSample(
            collected_at=time.time(),
            cpu=cpu,
            cores=(),
            loadavg=load,
            memory=MemorySample(
                total_bytes=int(virtual.total),
                available_bytes=int(virtual.available),
                swap_total_bytes=int(swap.total),
                swap_free_bytes=int(swap.free),
            ),
            disks=disks,
            network=network,
            source="psutil",
        )


def default_sampler(proc_root: Path | None = None) -> MetricsSampler:
    """Prefer ``/proc`` and fall back to psutil when it is not there."""
    root = proc_root or Path("/proc")
    if (root / "stat").is_file() and (root / "meminfo").is_file():
        return ProcMetricsSampler(root)
    return PsutilMetricsSampler()
