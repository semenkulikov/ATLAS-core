#!/bin/sh
# Install ATLAS directories and systemd units. This script does not download a release.
set -eu

prefix=/
dry=0
start=1
oneshot=0
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
# shellcheck disable=SC1091
. "$root/packaging/pick-uid.sh"

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      prefix=$2
      shift 2
      ;;
    --dry-run)
      dry=1
      shift
      ;;
    --no-start)
      start=0
      shift
      ;;
    --oneshot)
      oneshot=1
      shift
      ;;
    --url)
      echo "Release downloads stay disabled until a signed release exists." >&2
      exit 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$oneshot" -eq 1 ]; then
  echo "oneshot report only; no units are installed"
  if [ "$dry" -eq 1 ]; then
    exit 0
  fi
  if command -v atlas >/dev/null 2>&1; then
    atlas scan --format md --format json --format html --output atlas-report
  else
    echo "Run: atlas scan --format md --format json --format html"
  fi
  exit 0
fi

echo "prefix $prefix"
echo "opt $prefix/opt/atlas"
echo "units $prefix/usr/lib/systemd/system/atlas.service"
echo "data $prefix/var/lib/atlas"

if [ "$dry" -eq 1 ]; then
  exit 0
fi

if [ "$prefix" = / ]; then
  if [ "$(id -u)" -ne 0 ]; then
    echo "Installing onto / requires root." >&2
    exit 1
  fi
  if ! id atlas >/dev/null 2>&1; then
    uid=$(pick_atlas_uid)
    shell=/usr/sbin/nologin
    if [ ! -x "$shell" ]; then
      shell=/sbin/nologin
    fi
    useradd --system --uid "$uid" --home-dir /var/lib/atlas --shell "$shell" atlas
  fi
  uid=$(id -u atlas)
else
  uid=0
fi

mkdir -p \
  "$prefix/opt/atlas" \
  "$prefix/etc/atlas" \
  "$prefix/var/lib/atlas" \
  "$prefix/usr/lib/systemd/system" \
  "$prefix/usr/lib/tmpfiles.d"

sed "s/__UID__/$uid/" "$root/packaging/atlas-helper.service" \
  > "$prefix/usr/lib/systemd/system/atlas-helper.service"
cp "$root/packaging/atlas.service" "$prefix/usr/lib/systemd/system/atlas.service"
cp "$root/packaging/atlas.tmpfiles" "$prefix/usr/lib/tmpfiles.d/atlas.conf"
if [ "$prefix" = / ] && command -v systemd-tmpfiles >/dev/null 2>&1; then
  systemd-tmpfiles --create "$prefix/usr/lib/tmpfiles.d/atlas.conf"
fi
if [ "$prefix" = / ] && command -v python3 >/dev/null 2>&1; then
  if [ ! -x "$prefix/opt/atlas/.venv/bin/atlas" ]; then
    python3 -m venv "$prefix/opt/atlas/.venv"
    "$prefix/opt/atlas/.venv/bin/pip" install -e "$root/backend"
  fi
  if [ -f "$root/frontend/package.json" ] && [ ! -f "$root/frontend/dist/index.html" ] && command -v npm >/dev/null 2>&1; then
    npm --prefix "$root/frontend" ci
    npm --prefix "$root/frontend" run build
  fi
  chown -R atlas:atlas "$prefix/opt/atlas/.venv" "$prefix/var/lib/atlas"
  chmod 0700 "$prefix/var/lib/atlas"
fi
printf '%s\n' "The application lives in /opt/atlas. Repeat this script to repair units." \
  > "$prefix/etc/atlas/README"

if [ "$prefix" = / ] && [ "$start" -eq 1 ]; then
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
    exit 1
  fi
  echo "Open the panel from your workstation:"
  echo "  ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@$(hostname -f 2>/dev/null || hostname)"
  if [ -x /opt/atlas/.venv/bin/atlas ]; then
    echo "One-time enrollment token:"
    sudo -u atlas /opt/atlas/.venv/bin/atlas token new --db /var/lib/atlas/atlas.db
  fi
fi

echo "installed"
