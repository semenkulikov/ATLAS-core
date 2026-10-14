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

The panel API listens on a Unix socket. `atlas token new` prints a one-time enrollment token; the first account needs that token, a password, and a TOTP code. A TCP listener is off unless you pass `--tcp`, and a public address is refused without TLS and an address allow list. Host control stays off until `atlas control enable` is run against the same database. The panel then asks a separate root helper, and it does not run those commands itself.

```bash
uv run --project backend python -m atlas.cli.main token new --db /tmp/atlas.db
uv run --project backend python -m atlas.cli.main serve --db /tmp/atlas.db --root fixtures/partial-host --tcp 127.0.0.1:8765
```

Build the panel and the same process serves it from `frontend/dist`:

```bash
npm install --prefix frontend
npm run build --prefix frontend
```

Alert channels stay off until the owner enables one. `atlas doctor --db <file>` reports file mode and whether a channel can leave the host. `atlas status` prints the version. `atlas expose` prints the listener rules. `atlas uninstall --prefix <path>` removes product files and keeps the database unless `--purge` is set.

`packaging/install.sh` creates `/opt/atlas`, `/etc/atlas`, `/var/lib/atlas`, and the systemd units. It does not download a release. Passing `--url` exits with an error until a signed archive exists.

The security model is in [docs/security-model.md](docs/security-model.md) ([русский](docs/security-model.ru.md)). Detector notes are in [docs/detectors.md](docs/detectors.md). Collected paths are printed by `atlas manifest`.

License: Apache-2.0.
