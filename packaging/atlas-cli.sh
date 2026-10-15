#!/bin/sh
# /usr/local/bin/atlas — thin wrapper around the installed panel CLI.
set -eu
export PYTHONPATH=/opt/atlas/app
bin=/opt/atlas/python/bin/python3
if [ ! -x "$bin" ]; then
  echo "ATLAS is not installed under /opt/atlas." >&2
  exit 1
fi
# The data directory is owned by atlas; drop privileges when run as root.
if [ "$(id -u)" -eq 0 ] && id atlas >/dev/null 2>&1; then
  exec sudo -u atlas env PYTHONPATH=/opt/atlas/app "$bin" -m atlas.cli.main "$@"
fi
exec "$bin" -m atlas.cli.main "$@"
