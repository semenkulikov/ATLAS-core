# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow SemVer. Distro and arm64 install checks are left to users; this release was verified on Ubuntu 24.04 x86_64.

## [1.0.1] - 2026-10-15

### Added
- Overview **Run scan** button for owners, and a first scan during install.
- `/usr/local/bin/atlas` CLI wrapper so `atlas scan` and `atlas control enable` work after install.
- In-place upgrade via the same one-liner; keeps accounts and database.

### Fixed
- Upgrade no longer prints a useless enrollment token when an owner already exists.
- CLI defaults `--db` to `/var/lib/atlas/atlas.db` on an installed host.

## [1.0.0] - 2026-10-15

### Added
- Privileged inventory reads through the root helper: Docker Engine, sudoers, authorized_keys, and firewall commands.
- Cgroup series for systemd services and containers on the monitor, plus a one-second live stream that stays in memory.
- Alert channel form in Settings for webhook and Telegram. Channels stay off until the owner enables one.
- Command palette search against indexed documents, with `g` then `s`/`m`/`l` shortcuts.
- Free system UID selection, socket wait, enrollment token printout, and `StateDirectoryMode=0700` in the installer.
- CI coverage gate at 85% for domain, detectors, and security, plus pip-audit and Semgrep.

### Changed
- Install size budget is 400 MiB with a stripped bundled interpreter.
- Panel socket and helper socket stay group-readable for `atlas`.
- SMTP alert delivery is removed.

### Fixed
- User collection continues when `/etc/sudoers.d` is unreadable.
- Helper socket ownership no longer blocks the panel after a helper restart.
