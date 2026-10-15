# Publishing the panel

Leave the listener on `/run/atlas/web.sock` and open it with `ssh -L`. That is the supported path.

A public bind is refused unless `atlas serve` is given `--tls` and at least one `--allow` address. Put TLS on a reverse proxy or a private network you already trust. Do not publish the panel to the open internet to make a demo.

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

The installer downloads the signed x86_64 archive from [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest), checks SHA-256 (and minisign when available), then runs the archive `install.sh`.

## Manual archive

```bash
# after download + verify + extract
sudo ./atlas-1.0.0-linux-x86_64/install.sh
```

Assets: `.tar.gz`, `.minisig`, `.sha256`, `minisign.pub`.
