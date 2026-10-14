"""Parser tests for the /proc sampler and the secret redactor."""

from __future__ import annotations

from pathlib import Path

from atlas.metrics.sampler import ProcMetricsSampler, default_sampler
from atlas.redact import env_key_names, excerpt, mask_secrets

CANARY = "ATLAS_CANARY_7f3a9c"


def test_proc_sampler_reads_a_fixture_tree(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "stat").write_text(
        "cpu  100 10 50 1000 5 1 2 3 0 0\ncpu0 40 5 20 400 2 0 1 1 0 0\n",
        encoding="utf-8",
    )
    (proc / "meminfo").write_text(
        "MemTotal:       2048000 kB\nMemAvailable:   1024000 kB\n"
        "SwapTotal:      512000 kB\nSwapFree:       512000 kB\n",
        encoding="utf-8",
    )
    (proc / "loadavg").write_text("0.5 0.4 0.3 1/100 10\n", encoding="utf-8")
    (proc / "diskstats").write_text(
        "   8       0 sda 10 0 20 0 5 0 8 0 0 0 0 0 0 0 0\n"
        "   7       0 loop0 1 0 2 0 1 0 2 0 0 0 0 0 0 0 0\n",
        encoding="utf-8",
    )
    net = proc / "net"
    net.mkdir()
    (net / "dev").write_text(
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    "
        "packets errs drop fifo colls carrier compressed\n"
        "    lo: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0\n"
        "  eth0: 100 2 1 0 0 0 0 0 50 3 4 0 0 0 0 0\n",
        encoding="utf-8",
    )

    sample = ProcMetricsSampler(proc).sample()

    assert sample.source == "proc"
    assert sample.cpu is not None
    assert sample.cpu.user == 100
    assert len(sample.cores) == 1
    assert sample.memory is not None
    assert sample.memory.total_bytes == 2048000 * 1024
    assert sample.loadavg == (0.5, 0.4, 0.3)
    assert [disk.name for disk in sample.disks] == ["sda"]
    assert sample.disks[0].read_bytes == 20 * 512
    assert [row.name for row in sample.network] == ["eth0"]
    assert sample.network[0].tx_errors == 4


def test_proc_sampler_survives_missing_and_garbage(tmp_path: Path) -> None:
    sample = ProcMetricsSampler(tmp_path).sample()
    assert sample.cpu is None
    assert sample.memory is None
    assert sample.disks == ()

    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "stat").write_text("cpu not-a-number\n", encoding="utf-8")
    (proc / "meminfo").write_text("MemTotal: nope\n", encoding="utf-8")
    (proc / "loadavg").write_text("?\n", encoding="utf-8")
    assert ProcMetricsSampler(proc).sample().cpu is None


def test_default_sampler_returns_a_memory_reading() -> None:
    sample = default_sampler().sample()
    assert sample.source in {"proc", "psutil"}
    assert sample.memory is not None
    assert sample.memory.total_bytes > 0


def test_mask_secrets_hides_canaries() -> None:
    raw = "\n".join(
        [
            f"password={CANARY}",
            f"Authorization: Bearer {CANARY}",
            f"postgres://shop:{CANARY}@127.0.0.1:5432/shop",
            f"token: {CANARY}",
            f"ghp_{CANARY}",
            f"-----BEGIN OPENSSH PRIVATE KEY-----\n{CANARY}\n-----END OPENSSH PRIVATE KEY-----",
        ]
    )
    masked = mask_secrets(raw)
    assert CANARY not in masked
    assert "password=***" in masked
    assert "shop:***@" in masked


def test_excerpt_clips_and_masks() -> None:
    text = "password=super-secret " + ("a" * 400)
    clipped = excerpt(text, limit=50)
    assert "super-secret" not in clipped
    assert len(clipped) == 50
    assert clipped.endswith("…")


def test_env_key_names_drop_values() -> None:
    text = f"# comment\nexport SECRET={CANARY}\nPLAIN=value\nnot a pair\n"
    assert env_key_names(text) == ["SECRET", "PLAIN"]
    assert CANARY not in "".join(env_key_names(text))
