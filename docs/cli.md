# Command reference

| Command | What it does |
| --- | --- |
| `atlas scan --root <path> --format md\|json\|html` | One report. Without `--db` the database is temporary. |
| `atlas manifest --lang en\|ru` | Every file and command a collector declares. |
| `atlas serve --db <file>` | Panel on `/run/atlas/web.sock`. Add `--tcp 127.0.0.1:PORT` for loopback. |
| `atlas token new --db <file>` | One-time enrollment token. |
| `atlas control enable\|disable --db <file>` | Host actions stay off until enable. |
| `atlas status --db <file>` | Version, control switch, latest scan. |
| `atlas doctor --db <file>` | File mode and whether an alert channel can leave the host. |
| `atlas expose` | How the panel may be reached. |
| `atlas user reset-2fa --db <file>` | New TOTP secret for the owner. Local only. |
| `atlas export --db <file>` | Latest completed scan as Markdown, JSON, and HTML. |
| `atlas uninstall --prefix <path> [--purge]` | Remove product files. The database stays unless `--purge`. |

Production install uses the signed archive's `install.sh` (see [README.md](../README.md)). `packaging/install.sh` is for a git checkout and does not download a release.

`atlas-helper --socket <path> --uid <web uid>` is the root process. It is not started by `serve`.
