# Publishing the panel

Leave the listener on `/run/atlas/web.sock` and open it with `ssh -L`. That is the supported path.

A public bind is refused unless `atlas serve` is given `--tls` and at least one `--allow` address. Put TLS on a reverse proxy or a private network you already trust. Do not publish the panel to the open internet to make a demo.

The signed archive is `atlas-0.1.0-linux-x86_64.tar.gz`. Verify it with `packaging/minisign.pub` before extracting. `packaging/install.sh --url` still exits on purpose: a git checkout does not download the archive for you.
