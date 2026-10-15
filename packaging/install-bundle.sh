#!/bin/sh
# Install a built ATLAS archive. No compiler, npm, or network is required.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")" && pwd)

if [ "$(id -u)" -ne 0 ]; then
  echo "Installing onto / requires root." >&2
  exit 1
fi
if [ ! -x "$root/python/bin/python3" ] || [ ! -f "$root/frontend/dist/index.html" ]; then
  echo "This directory is not a complete ATLAS archive." >&2
  exit 1
fi

shell=/usr/sbin/nologin
if [ ! -x "$shell" ]; then
  shell=/sbin/nologin
fi
if ! id atlas >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/atlas --shell "$shell" atlas
fi
uid=$(id -u atlas)

mkdir -p /opt/atlas/frontend /etc/atlas /var/lib/atlas /usr/lib/systemd/system /usr/lib/tmpfiles.d
rm -rf /opt/atlas/python /opt/atlas/app /opt/atlas/frontend/dist
cp -a "$root/python" /opt/atlas/python
cp -a "$root/app" /opt/atlas/app
cp -a "$root/frontend/dist" /opt/atlas/frontend/dist
chown -R atlas:atlas /var/lib/atlas
chmod 0700 /var/lib/atlas

awk '
  /^ExecStart=/ {
    print "Environment=PYTHONPATH=/opt/atlas/app"
    print "ExecStart=/opt/atlas/python/bin/python3 -m atlas.cli.main serve --db /var/lib/atlas/atlas.db --root / --helper-socket /run/atlas/helper.sock"
    next
  }
  { print }
' "$root/packaging/atlas.service" > /usr/lib/systemd/system/atlas.service

awk -v uid="$uid" '
  /^ExecStart=/ {
    print "Environment=PYTHONPATH=/opt/atlas/app"
    print "ExecStart=/opt/atlas/python/bin/python3 -m atlas.helper --socket /run/atlas/helper.sock --uid " uid
    next
  }
  { print }
' "$root/packaging/atlas-helper.service" > /usr/lib/systemd/system/atlas-helper.service

cp "$root/packaging/atlas.tmpfiles" /usr/lib/tmpfiles.d/atlas.conf
if command -v systemd-tmpfiles >/dev/null 2>&1; then
  systemd-tmpfiles --create /usr/lib/tmpfiles.d/atlas.conf
fi
printf '%s\n' "Installed from a signed archive. The interpreter is /opt/atlas/python." \
  > /etc/atlas/README

systemctl daemon-reload
systemctl enable --now atlas.service atlas-helper.service
echo "installed"
ls -l /run/atlas/web.sock
