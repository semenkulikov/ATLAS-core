#!/bin/sh
# One-command ATLAS removal.
# Usage: curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
# Offline: sudo /opt/atlas/packaging/remove-atlas.sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

systemctl stop atlas-scan.timer atlas-scan.service atlas-update.service atlas.service atlas-helper.service 2>/dev/null || true
systemctl disable atlas-scan.timer atlas-scan.service atlas-update.service atlas.service atlas-helper.service 2>/dev/null || true

if [ -x /opt/atlas/python/bin/python3 ] && [ -d /opt/atlas/app ]; then
  PYTHONPATH=/opt/atlas/app /opt/atlas/python/bin/python3 -m atlas.cli.main uninstall --prefix / --purge || true
fi

rm -rf /opt/atlas /etc/atlas /var/lib/atlas /run/atlas
rm -f /usr/local/bin/atlas \
  /usr/lib/systemd/system/atlas.service \
  /usr/lib/systemd/system/atlas-helper.service \
  /usr/lib/systemd/system/atlas-update.service \
  /usr/lib/systemd/system/atlas-scan.service \
  /usr/lib/systemd/system/atlas-scan.timer \
  /usr/lib/tmpfiles.d/atlas.conf
systemctl daemon-reload 2>/dev/null || true
userdel atlas 2>/dev/null || true
groupdel atlas 2>/dev/null || true

echo "ATLAS removed."
