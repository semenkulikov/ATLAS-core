#!/bin/sh
# Install ATLAS directories and systemd units. This script does not download a release.
set -eu

prefix=/
dry=0
start=1
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)

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
    useradd --system --home-dir /var/lib/atlas --shell /usr/sbin/nologin atlas
  fi
  uid=$(id -u atlas)
else
  uid=0
fi

mkdir -p \
  "$prefix/opt/atlas" \
  "$prefix/etc/atlas" \
  "$prefix/var/lib/atlas" \
  "$prefix/usr/lib/systemd/system"

sed "s/__UID__/$uid/" "$root/packaging/atlas-helper.service" \
  > "$prefix/usr/lib/systemd/system/atlas-helper.service"
cp "$root/packaging/atlas.service" "$prefix/usr/lib/systemd/system/atlas.service"
printf '%s\n' "Install the application into /opt/atlas and create its virtualenv before starting the units." \
  > "$prefix/etc/atlas/README"

if [ "$prefix" = / ] && [ "$start" -eq 1 ]; then
  systemctl daemon-reload
  systemctl enable --now atlas.service atlas-helper.service
fi

echo "installed"
