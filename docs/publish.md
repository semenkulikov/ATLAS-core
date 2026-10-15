# Publishing the panel

Leave the listener on `/run/atlas/web.sock` and open it with `ssh -L`. That is the supported path.

A public bind is refused unless `atlas serve` is given `--tls` and at least one `--allow` address. Put TLS on a reverse proxy or a private network you already trust. Do not publish the panel to the open internet to make a demo.

## Signed release

Assets live on [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest):

- `atlas-1.0.0-linux-x86_64.tar.gz`
- `atlas-1.0.0-linux-x86_64.tar.gz.minisig`
- `atlas-1.0.0-linux-x86_64.tar.gz.sha256`
- `minisign.pub`

Verify with `minisign -V` and the checksum, extract, then run **one** install command:

```bash
sudo ./atlas-1.0.0-linux-x86_64/install.sh
```

`packaging/install.sh --url` still exits on purpose: a git checkout does not download the archive. Prefer the signed release flow in [README.md](../README.md).
