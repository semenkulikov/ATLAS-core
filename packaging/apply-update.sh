#!/bin/sh
# Apply a requested ATLAS release. Root only. Started by atlas-update.service.
# The panel never runs this; the helper only starts the unit after writing
# /run/atlas/update-request with the target version (X.Y.Z).
set -eu

REQUEST="${ATLAS_UPDATE_REQUEST:-/run/atlas/update-request}"
REPO="${ATLAS_REPO:-semenkulikov/ATLAS-core}"
ARCH="${ATLAS_ARCH:-linux-x86_64}"
INSTALL_ROOT="${ATLAS_INSTALL_ROOT:-/opt/atlas}"

# install.sh replaces /opt/atlas; continue from a copy outside that tree.
case "$0" in
  /tmp/atlas-apply-update-$$.sh | /tmp/atlas-apply-update.sh) ;;
  *)
    copy=/tmp/atlas-apply-update.sh
    cp "$0" "$copy"
    chmod 755 "$copy"
    exec /bin/sh "$copy" "$@"
    ;;
esac

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root." >&2
  exit 1
fi
if [ ! -f "$REQUEST" ]; then
  echo "No update request at $REQUEST." >&2
  exit 1
fi

VERSION=$(tr -d '[:space:]' < "$REQUEST")
case "$VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *)
    echo "Update request is not a version: $VERSION" >&2
    exit 1
    ;;
esac

PUB="$INSTALL_ROOT/packaging/minisign.pub"
MINISIGN="$INSTALL_ROOT/packaging/minisign"
if [ ! -f "$PUB" ]; then
  echo "Trusted public key missing at $PUB." >&2
  exit 1
fi
if [ ! -x "$MINISIGN" ]; then
  echo "Bundled minisign missing at $MINISIGN." >&2
  exit 1
fi

WORKDIR=$(mktemp -d)
cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

cp "$PUB" "$WORKDIR/minisign.pub"
cp "$MINISIGN" "$WORKDIR/minisign"
chmod 755 "$WORKDIR/minisign"

NAME="atlas-${VERSION}-${ARCH}"
BASE="https://github.com/${REPO}/releases/download/v${VERSION}"
cd "$WORKDIR"

echo "Updating ATLAS to ${VERSION}…"
curl -fsSLO "${BASE}/${NAME}.tar.gz"
curl -fsSLO "${BASE}/${NAME}.tar.gz.sha256"
curl -fsSLO "${BASE}/${NAME}.tar.gz.minisig"

hash=$(awk '{print $1; exit}' "${NAME}.tar.gz.sha256")
if [ -z "$hash" ] || [ "${#hash}" -ne 64 ]; then
  echo "Checksum file is missing or malformed." >&2
  exit 1
fi
printf '%s  %s\n' "$hash" "${NAME}.tar.gz" > "${NAME}.tar.gz.sha256.check"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "${NAME}.tar.gz.sha256.check"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 -c "${NAME}.tar.gz.sha256.check"
else
  echo "No sha256 tool found." >&2
  exit 1
fi

"$WORKDIR/minisign" -V -p "$WORKDIR/minisign.pub" -m "${NAME}.tar.gz" \
  -x "${NAME}.tar.gz.minisig"

tar -xzf "${NAME}.tar.gz"
if [ ! -x "${NAME}/install.sh" ]; then
  echo "Archive is missing install.sh." >&2
  exit 1
fi

# Drop the request so a restart does not re-apply the same tag by accident.
rm -f "$REQUEST"

"${NAME}/install.sh"
echo "ATLAS ${VERSION} applied."
