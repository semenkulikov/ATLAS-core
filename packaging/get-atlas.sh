#!/bin/sh
# Install or upgrade ATLAS on Linux x86_64.
# Usage: curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
# Pin a version: ATLAS_VERSION=1.0.0 curl … | sudo sh
set -eu

REPO="${ATLAS_REPO:-semenkulikov/ATLAS-core}"
ARCH="${ATLAS_ARCH:-linux-x86_64}"
WORKDIR="${TMPDIR:-/tmp}/atlas-install-$$"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

resolve_version() {
  if [ -n "${ATLAS_VERSION:-}" ]; then
    printf '%s\n' "$ATLAS_VERSION"
    return
  fi
  # Latest published GitHub release tag without the leading v.
  tag=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    | head -n 1)
  if [ -z "$tag" ]; then
    echo "Could not resolve the latest release. Set ATLAS_VERSION=…" >&2
    exit 1
  fi
  printf '%s\n' "${tag#v}"
}

VERSION=$(resolve_version)
NAME="atlas-${VERSION}-${ARCH}"
BASE="https://github.com/${REPO}/releases/download/v${VERSION}"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "Installing ATLAS ${VERSION}…"
curl -fsSLO "${BASE}/${NAME}.tar.gz"
curl -fsSLO "${BASE}/${NAME}.tar.gz.sha256"
curl -fsSLO "${BASE}/minisign.pub" || true
curl -fsSLO "${BASE}/${NAME}.tar.gz.minisig" || true

# Accept "HASH  basename" or a mistaken absolute path from older builds.
hash=$(awk '{print $1; exit}' "${NAME}.tar.gz.sha256")
if [ -z "$hash" ] || [ "${#hash}" -ne 64 ]; then
  echo "Checksum file is missing or malformed." >&2
  exit 1
fi
printf '%s  %s\n' "$hash" "${NAME}.tar.gz" > "${NAME}.tar.gz.sha256.check"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 -c "${NAME}.tar.gz.sha256.check"
elif command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "${NAME}.tar.gz.sha256.check"
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
echo "ATLAS ${VERSION} is ready."
echo "Same command upgrades an existing install. Remove with:"
echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/main/packaging/remove-atlas.sh | sudo sh"
