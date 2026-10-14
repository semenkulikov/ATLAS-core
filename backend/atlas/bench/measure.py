"""Import the metrics sampler in a fresh process and print its RSS.

The number is a developer measurement. The release gate is the same command
on a Linux CI host, where the panel and the collector run as separate processes.
"""

from __future__ import annotations

import json
import platform
import sys

from atlas.metrics.sampler import default_sampler


def main() -> None:
    sample = default_sampler().sample()
    rss = _rss_bytes()
    json.dump(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sampler": sample.source,
            "rss_bytes": rss,
            "memory_total_bytes": None if sample.memory is None else sample.memory.total_bytes,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


def _rss_bytes() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    return int(psutil.Process().memory_info().rss)


if __name__ == "__main__":
    main()
