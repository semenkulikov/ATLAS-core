# Security model

ATLAS keeps a proof for every inventory claim. The panel is closed unless the owner opens it.

## What is protected

The listener defaults to the Unix socket `/run/atlas/web.sock`. A TCP port is optional and starts on loopback. Binding a public address requires TLS and an address allow list, or the process exits. Every route, including health, requires a password and TOTP. Sessions use `HttpOnly` and `SameSite=Strict` cookies. State-changing browser requests also send a CSRF token.

The web process does not run root actions. `atlas-helper` accepts a whitelist on a Unix socket and checks the peer uid on Linux (`SO_PEERCRED`). Stopping `sshd`, `ssh`, `atlas`, `atlas-helper`, or a network manager requires `force`. Reboot waits 10 seconds and can be cancelled. Each attempt is appended to a hash chain.

Secrets are masked in evidence, logs, and reports. The collectors do not read `/etc/shadow` or private keys. Alert channels are stored disabled. Enabling one is the only path that opens an outbound connection.

## What is not protected

A person with root on the host can read the database, the socket, and the helper. The documentation states that limit on purpose. The panel does not hide its systemd units.

## Still open before 1.0

The systemd units in `packaging/` carry the hardening flags, and they have not been exercised on Debian, Ubuntu, and AlmaLinux in CI. There is no signed release archive and no completed external review.
