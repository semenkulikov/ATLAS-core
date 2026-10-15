# Security

ATLAS is built for a single trusted host. The panel is private by default and does not send data out unless you turn alerts on.

## Defaults

- Access over SSH tunnel to a local socket — not exposed to the public internet
- Owner login with password and 2FA
- Host control actions stay off until you explicitly enable them
- Secrets are not stored in reports; private keys and password hashes are never read
- Alerts (Telegram / webhook) stay disabled until you configure them

## Limits

Anyone with root on the server can read ATLAS data directly. That is expected for an on-host tool.
