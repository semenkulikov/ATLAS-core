#!/bin/sh
# Build dist/atlas-<version>-linux-x86_64.tar.gz with a bundled CPython.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
version=$(awk -F'"' '/^__version__ = / { print $2 }' "$root/backend/atlas/__init__.py")
python_url="https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.12.15%2B20261013-x86_64-unknown-linux-gnu-install_only.tar.gz"
name="atlas-${version}-linux-x86_64"
stage="$root/dist/$name"

if [ ! -f "$root/frontend/dist/index.html" ]; then
  npm --prefix "$root/frontend" ci
  npm --prefix "$root/frontend" run build
fi

rm -rf "$stage"
mkdir -p "$root/dist"
docker run --rm --platform linux/amd64 \
  -e STAGE="/dist/$name" \
  -e PYTHON_URL="$python_url" \
  -v "$root":/src:ro \
  -v "$root/dist":/dist \
  python:3.12-slim-bookworm \
  bash /src/packaging/build-inside.sh

tar -C "$root/dist" -czf "$root/dist/${name}.tar.gz" "$name"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$root/dist/${name}.tar.gz" > "$root/dist/${name}.tar.gz.sha256"
fi
echo "wrote $root/dist/${name}.tar.gz"
