# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow SemVer. 1.0.0 waits for a Linux install matrix, a ZAP baseline, and an external review.

## [Unreleased]

- Inventory scan, project discovery, authenticated panel, metrics, and logs.
- Host control is off until `atlas control enable`. Actions go to a root helper with a fixed whitelist and an audit hash chain.
- Alert rules are recorded locally. Telegram, SMTP, and webhook channels stay off until the owner enables one.
- `packaging/install.sh` lays down directories and systemd units. It does not download a release.
- The shop fixture has an expected fact list. `atlas export` writes the latest scan. Metric storage drops the oldest points past 200 MiB.
- First-time setup shows a QR code for the authenticator app.
- A scan continues when a project directory is unreadable. An empty panel says so in the selected language.
- Hostname and architecture follow GNU uname's fixed field order.
- The panel socket is group-readable. Oneshot writes a report when `atlas` is installed. Charts follow the series that were stored.
- Stopping one unit no longer deletes the shared runtime directory of the other. The helper does not take ownership of that directory.
