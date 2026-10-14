# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow SemVer. 1.0.0 waits for a Linux install matrix, a ZAP baseline, and an external review.

## [Unreleased]

- Inventory scan, project discovery, authenticated panel, metrics, and logs.
- Host control is off until `atlas control enable`. Actions go to a root helper with a fixed whitelist and an audit hash chain.
- Alert rules are recorded locally. Telegram, SMTP, and webhook channels stay off until the owner enables one.
- `packaging/install.sh` lays down directories and systemd units. It does not download a release.
