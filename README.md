# ATLAS

ATLAS is an open-source inventory agent for one Linux server. It records what is on the machine and the file, command, or API response each claim came from. A field that cannot be read stays unknown.

A scan does not open a network port and does not send anything off the host.

```bash
uv sync --project backend --group dev
uv run --project backend python -m atlas.cli.main scan --root fixtures/partial-host --output /tmp/atlas-report
```

The report is written as Markdown, JSON, and HTML. Point `--root` at `/` to scan the machine you are on. `--db` keeps the snapshot; without it the database is temporary and only the report remains.

The list of files and commands ATLAS reads is generated from the collectors:

```bash
uv run --project backend python -m atlas.cli.main manifest
uv run --project backend python -m atlas.cli.main manifest --lang ru
```

The metrics sampler is replaceable. See [the collector-language note](docs/adr/0001-collector-language.md).

License: Apache-2.0.
