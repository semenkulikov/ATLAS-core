# Collector language

ATLAS starts on Python. The metrics sampler is the hot path, and it sits behind `MetricsSampler` in `atlas.metrics.sampler`. Inventory, the API, and the panel call that interface. Replacing the implementation with a Go or Rust sampler does not require changes above it.

## Measurement

Taken on 14 October 2026, CPython 3.13.5, macOS arm64, after `python -m atlas.bench.measure`:

| Process | RSS |
| --- | --- |
| Sampler import and one sample (`psutil` fallback, this machine has no `/proc`) | 20.8 MiB |
| Same interpreter after importing the scanner and scanning `fixtures/partial-host` | 39.3 MiB |

These numbers are a developer measurement. They are not the release gate. The gate is the same idle-RSS check on Linux, where `/proc` is the sampler and the panel, the scan child, and the privileged helper are separate processes. The budget is 100 MiB RSS combined while idle, and 150 MiB with the interface open.

## Why this is enough to continue

The sampler process is well under the idle budget, and a full fixture scan in one process is still under it. The web framework is not imported by the scanner. The privileged helper will stay on the standard library. If a later Linux run exceeds the budget by more than 10 percent, the sampler implementation is what gets replaced.

## Consequences

- New metrics code goes through `MetricsSampler`.
- The scan child and the helper do not import FastAPI.
- `atlas.bench.measure` stays in the tree so the number can be taken again.
