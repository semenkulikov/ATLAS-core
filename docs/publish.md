# Publishing the panel

Leave the listener on `/run/atlas/web.sock` and open it with `ssh -L`. That is the supported path.

A public bind is refused unless `atlas serve` is given `--tls` and at least one `--allow` address. Put TLS on a reverse proxy or a private network you already trust. Do not publish the panel to the open internet to make a demo.

`packaging/install.sh --url` exits on purpose. There is no signed release archive yet, so the installer will not download one.
