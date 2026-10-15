#!/bin/sh
# One-command ATLAS install for Linux x86_64.
# Usage: curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
set -eu

REPO="${ATLAS_REPO:-semenkulikov/ATLAS-core}"
VERSION="${ATLAS_VERSION:-1.0.0}"
ARCH="${ATLAS_ARCH:-linux-x86_64}"
NAME="atlas-${VERSION}-${ARCH}"
BASE="https://github.com/${REPO}/releases/download/v${VERSION}"
WORKDIR="${TMPDIR:-/tmp}/atlas-install-$$"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "Downloading ${NAME}..."
curl -fsSLO "${BASE}/${NAME}.tar.gz"
curl -fsSLO "${BASE}/${NAME}.tar.gz.sha256"
curl -fsSLO "${BASE}/minisign.pub" || true
curl -fsSLO "${BASE}/${NAME}.tar.gz.minisig" || true

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 -c "${NAME}.tar.gz.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "${NAME}.tar.gz.sha256"
else
  echo "No sha256 tool found; refusing to install without a checksum check." >&2
  exit 1
fi

if command -v minisign >/dev/null 2>&1 && [ -f "${NAME}.tar.gz.minisig" ] && [ -f minisign.pub ]; then
  minisign -V -p minisign.pub -m "${NAME}.tar.gz"
else
  echo "minisign not installed; checksum verified, signature skipped."
fi

tar -xzf "${NAME}.tar.gz"
if [ ! -x "${NAME}/install.sh" ]; then
  echo "Archive is missing install.sh." >&2
  exit 1
fi

"${NAME}/install.sh"
echo "ATLAS ${VERSION} is installed. Remove with:"
echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/main/packaging/remove-atlas.sh | sudo sh"
