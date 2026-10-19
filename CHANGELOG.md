# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow SemVer. Distro and arm64 install checks are left to users; this release was verified on Ubuntu 24.04 x86_64.

## [1.1.1] - 2026-10-19

### Fixed
- Release builds always rebuild the panel. 1.1.0 shipped a stale frontend with the previous navigation.

### Added
- Settings → About shows the installed version and the latest GitHub release.
- Owner can start a signed self-update from the panel (`app.update` → `atlas-update.service`).
- Release archive bundles a minisign binary so upgrades verify the signature without a host package.

## [1.1.0] - 2026-10-19

### Added
- Application-first panel: Overview, Applications, Monitoring, Network, Access, Logs, Events, and Settings. System services stay one click away instead of in the main menu.
- Directories that share a name and an environment suffix group into one application. A manual rename or split survives the next scan in the browser.
- Host passport on `GET /api/v1/host`: memory, disk, addresses, sshd, sessions, sites, and when the scan finished.

### Changed
- Uptime, sizes, and chart counters are shown as days, binary sizes, percents, and rates.
- Ports in `127.0.0.0/8` and `::1` are local. Private addresses are the internal network.
- A unit that an enabled socket or template parent starts is no longer listed as failing to come back after reboot.
- Logs open the system journal first and explain how to join `systemd-journal` when the panel cannot read it.

## [1.0.3] - 2026-10-16

### Fixed
- Crash-loop on Mac-built archives: ignore AppleDouble `._*.sql` and only apply `NNN_*.sql` UTF-8 migrations.
- Stale `/run/atlas/web.sock` after failed starts; unlink before bind and on service start.
- Installer verifies the panel socket accepts connections before reporting success.
- Release tarballs are packed as ustar without macOS xattrs.

### Changed
- `atlas doctor` reports migration junk and whether panel/helper sockets are listening.

## [1.0.2] - 2026-10-16

### Added
- Working vs system list split (users, services, ports, schedules) with a collapsed system section.
- `GET /api/v1/users/{name}` with facts and SSH keys in the user detail panel.
- Error modals, clearer EN/RU copy, human chart titles, live badges on Monitoring and Logs.

### Changed
- Action confirm dialogs use a red frame (no Acid Lime on dangerous confirms).
- Service detail facts resolve under the `unit:` subject prefix.

### Fixed
- Panel no longer shows raw API keys/ops as primary UI text.

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
