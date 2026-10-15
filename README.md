# ATLAS

**Inventory agent for one Linux server.**  
ATLAS maps what runs on the host and keeps the file, command, or API response behind every claim. Unreadable sources stay unknown. A scan does not open a network port and does not send data off the machine.

[![Release](https://img.shields.io/github/v/release/semenkulikov/ATLAS-core?label=release)](https://github.com/semenkulikov/ATLAS-core/releases/latest)
[![License](https://img.shields.io/github/license/semenkulikov/ATLAS-core)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/semenkulikov/ATLAS-core/ci.yml?branch=main&label=CI)](https://github.com/semenkulikov/ATLAS-core/actions)
[![Русский](https://img.shields.io/badge/README-RU-blue)](README.ru.md)

---

## Install (signed x86_64 archive)

Verified on **Ubuntu 24.04 x86_64**. Debian, AlmaLinux, and arm64 are left to users for now.

After download and signature check, install is one command:

```bash
VER=1.0.0
BASE="https://github.com/semenkulikov/ATLAS-core/releases/download/v${VER}"

curl -fsSLO "${BASE}/atlas-${VER}-linux-x86_64.tar.gz"
curl -fsSLO "${BASE}/atlas-${VER}-linux-x86_64.tar.gz.minisig"
curl -fsSLO "${BASE}/atlas-${VER}-linux-x86_64.tar.gz.sha256"
curl -fsSLO "${BASE}/minisign.pub"

minisign -V -p minisign.pub -m "atlas-${VER}-linux-x86_64.tar.gz"
shasum -a 256 -c "atlas-${VER}-linux-x86_64.tar.gz.sha256"

tar -xzf "atlas-${VER}-linux-x86_64.tar.gz"
sudo "./atlas-${VER}-linux-x86_64/install.sh"
```

`install.sh` creates the `atlas` user (free system UID), lays out `/opt/atlas`, `/etc/atlas`, `/var/lib/atlas` (mode `0700`), enables systemd units, waits for `/run/atlas/web.sock`, and prints a tunnel command plus a **one-time enrollment token**.

Do not pipe an unsigned script into a shell. `packaging/install.sh --url` exits on purpose: a git checkout does not download the archive for you.

### Open the panel

```bash
ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@YOUR_HOST
```

Then open `http://127.0.0.1:8765`, enroll with the token, password, and TOTP.

### Uninstall

```bash
sudo -u atlas env PYTHONPATH=/opt/atlas/app \
  /opt/atlas/python/bin/python3 -m atlas.cli.main uninstall --prefix / --purge
```

---

## What you get

| Area | Behavior |
| --- | --- |
| Inventory | OS, users, systemd, ports, nginx/sites, packages, Docker/Podman via the root helper |
| Evidence | Every fact points at a file, command, or API path; secrets are masked |
| Panel | FastAPI on a Unix socket; first account needs enrollment token + password + TOTP |
| Metrics | Host series plus cgroup CPU/memory for units and containers; live 1s stream while Monitor is open |
| Alerts | Webhook and Telegram only; both off until you enable a channel |
| Control | Off until `atlas control enable`; actions go through a peer-checked helper whitelist |
| Size | Bundled stripped CPython; documented budget 400 MiB (~141 MiB tree in 1.0.0) |

---

## Develop from a checkout

```bash
uv sync --project backend --group dev
uv run --project backend python -m atlas.cli.main scan \
  --root fixtures/partial-host --output /tmp/atlas-report

npm install --prefix frontend && npm run build --prefix frontend
uv run --project backend python -m atlas.cli.main token new --db /tmp/atlas.db
uv run --project backend python -m atlas.cli.main serve \
  --db /tmp/atlas.db --root fixtures/partial-host --tcp 127.0.0.1:8765
```

Collector source list:

```bash
uv run --project backend python -m atlas.cli.main manifest
uv run --project backend python -m atlas.cli.main manifest --lang ru
```

Git-tree install (no release download): `sudo packaging/install.sh`.

---

## Documentation

| Topic | EN | RU |
| --- | --- | --- |
| Security model | [docs/security-model.md](docs/security-model.md) | [docs/security-model.ru.md](docs/security-model.ru.md) |
| CLI | [docs/cli.md](docs/cli.md) | [docs/cli.ru.md](docs/cli.ru.md) |
| FAQ | [docs/faq.md](docs/faq.md) | [docs/faq.ru.md](docs/faq.ru.md) |
| Publishing the panel | [docs/publish.md](docs/publish.md) | [docs/publish.ru.md](docs/publish.ru.md) |
| Detectors | [docs/detectors.md](docs/detectors.md) | [docs/detectors.ru.md](docs/detectors.ru.md) |
| Security policy | [SECURITY.md](SECURITY.md) | — |

Release notes: [CHANGELOG.md](CHANGELOG.md) · Latest assets: [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest)

---

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
