# ATLAS

**See your whole server — and every project on it — in one place.**

ATLAS is a production control panel for a single Linux host. It discovers what is running, tracks live health, and gives you dashboards for the products and services that live on that machine: inventory, metrics, logs, alerts, and safe remote actions — without bolting on five separate tools.

[![Release](https://img.shields.io/github/v/release/semenkulikov/ATLAS-core?label=release)](https://github.com/semenkulikov/ATLAS-core/releases/latest)
[![License](https://img.shields.io/github/license/semenkulikov/ATLAS-core)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/semenkulikov/ATLAS-core/ci.yml?branch=main&label=CI)](https://github.com/semenkulikov/ATLAS-core/actions)
[![Русский](https://img.shields.io/badge/README-RU-blue)](README.ru.md)

---

## Why ATLAS

| | |
| --- | --- |
| **Full picture** | Users, services, containers, sites, packages, and the projects they belong to |
| **Live dashboards** | CPU, memory, and service health for the host and for what you actually run |
| **One panel** | Inventory, monitor, logs, settings, and alerts in a single UI |
| **Stays on the host** | No SaaS dependency; data does not leave the server unless you turn on alerts |
| **Safe by default** | Password + 2FA, control actions off until you enable them |

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

Then open the panel through SSH:

```bash
ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@YOUR_HOST
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), use the one-time token from the installer, set a password and 2FA. The installer runs a first scan automatically; you can also start a new one from **Overview → Run scan**.

### Upgrade

Same command as install. It pulls the **latest** GitHub release, replaces `/opt/atlas`, restarts the services, and keeps `/var/lib/atlas` (accounts, scans, settings):

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

After upgrade, hard-refresh the panel (Ctrl/Cmd+Shift+R) so the new UI loads.  
Pin a version if you need to: `ATLAS_VERSION=1.0.1 curl … | sudo sh`.

CLI on the host (after 1.0.1):

```bash
atlas status
atlas scan
atlas control enable
```

### Remove

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

---

## Requirements

- Linux x86_64 (verified on Ubuntu 24.04)
- Root for install
- SSH access to reach the panel

---

## Docs

- [Security](docs/security-model.md) · [FAQ](docs/faq.md) · [Commands](docs/cli.md)
- [Русская документация](README.ru.md)
- [Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest) · [Changelog](CHANGELOG.md)

---

## License

Apache-2.0 — [LICENSE](LICENSE)
