#!/bin/sh
# Install a built ATLAS archive. No compiler, npm, or network is required.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
# shellcheck disable=SC1091
. "$root/packaging/pick-uid.sh"

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
  uid=$(pick_atlas_uid)
  useradd --system --uid "$uid" --home-dir /var/lib/atlas --shell "$shell" atlas
else
  uid=$(id -u atlas)
fi

mkdir -p /opt/atlas/frontend /etc/atlas /var/lib/atlas /usr/lib/systemd/system /usr/lib/tmpfiles.d
rm -rf /opt/atlas/python /opt/atlas/app /opt/atlas/frontend/dist
cp -a "$root/python" /opt/atlas/python
cp -a "$root/app" /opt/atlas/app
cp -a "$root/frontend/dist" /opt/atlas/frontend/dist
cp -a "$root/packaging" /opt/atlas/packaging
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
systemctl enable atlas.service atlas-helper.service
systemctl restart atlas-helper.service atlas.service

i=0
while [ "$i" -lt 150 ]; do
  if [ -S /run/atlas/web.sock ]; then
    break
  fi
  i=$((i + 1))
  sleep 0.1
done
if [ ! -S /run/atlas/web.sock ]; then
  echo "The panel socket did not appear." >&2
  systemctl --no-pager --full status atlas.service >&2 || true
  exit 1
fi

echo "installed"
ls -l /run/atlas/web.sock

# Fresh install: seed inventory. Upgrade: keep the existing DB and accounts.
has_owner=0
if [ -f /var/lib/atlas/atlas.db ]; then
  if sudo -u atlas /opt/atlas/python/bin/python3 -c \
    "import sqlite3; c=sqlite3.connect('/var/lib/atlas/atlas.db'); print(c.execute('select count(*) from accounts').fetchone()[0])" \
    2>/dev/null | grep -qx '[1-9][0-9]*'; then
    has_owner=1
  fi
fi

if [ "$has_owner" -eq 0 ]; then
  echo "Running the first inventory scan…"
  mkdir -p /var/lib/atlas/reports
  chown atlas:atlas /var/lib/atlas/reports
  sudo -u atlas env PYTHONPATH=/opt/atlas/app /opt/atlas/python/bin/python3 -m atlas.cli.main scan \
    --db /var/lib/atlas/atlas.db \
    --helper-socket /run/atlas/helper.sock \
    --output /var/lib/atlas/reports/latest \
    || echo "First scan failed; run it from the panel after login." >&2
fi

echo "Open the panel from your workstation:"
echo "  ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@$(hostname -f 2>/dev/null || hostname)"
if [ "$has_owner" -eq 0 ]; then
  echo "One-time enrollment token:"
  sudo -u atlas env PYTHONPATH=/opt/atlas/app /opt/atlas/python/bin/python3 -m atlas.cli.main token new --db /var/lib/atlas/atlas.db
else
  echo "Existing owner kept. Sign in with your password and 2FA."
  echo "To refresh inventory after an upgrade, use Overview → Run scan in the panel."
fi
