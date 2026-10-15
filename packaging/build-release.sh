#!/bin/sh
# Build dist/atlas-<version>-linux-x86_64.tar.gz with a bundled CPython.
# Prefer Docker when the daemon is up; otherwise cross-install manylinux wheels
# from the host (macOS/Linux) — no container required.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
version=$(awk -F'"' '/^__version__ = / { print $2 }' "$root/backend/atlas/__init__.py")
python_url="https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.12.15%2B20261013-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
name="atlas-${version}-linux-x86_64"
stage="$root/dist/$name"

if [ ! -f "$root/frontend/dist/index.html" ]; then
  npm --prefix "$root/frontend" ci
  npm --prefix "$root/frontend" run build
fi

rm -rf "$stage"
mkdir -p "$root/dist"

build_with_docker() {
  docker run --rm --platform linux/amd64 \
    -e STAGE="/dist/$name" \
    -e PYTHON_URL="$python_url" \
    -v "$root":/src:ro \
    -v "$root/dist":/dist \
    python:3.12-slim-bookworm \
    bash /src/packaging/build-inside.sh
}

build_host() {
  # Same layout as build-inside.sh, without apt or a Linux container.
  mkdir -p "$stage/packaging" "$stage/frontend"
  curl -fsSL -o /tmp/atlas-python.tar.gz "$python_url"
  tar -xzf /tmp/atlas-python.tar.gz -C "$stage"
  if [ -x "$root/backend/.venv/bin/python" ]; then
    host_py="$root/backend/.venv/bin/python"
  elif [ -x "$root/.tools/bin/python" ]; then
    host_py="$root/.tools/bin/python"
  else
    host_py=$(command -v python3)
  fi
  "$host_py" -m pip install -q --upgrade pip wheel hatchling
  wheelhouse=$(mktemp -d)
  "$host_py" -m pip wheel -q -w "$wheelhouse" "$root/backend"
  "$host_py" -m pip install -q \
    --target "$stage/app" \
    --platform manylinux_2_17_x86_64 \
    --platform manylinux2014_x86_64 \
    --python-version 312 \
    --implementation cp \
    --abi cp312 \
    --only-binary=:all: \
    argon2-cffi fastapi httpx psutil pydantic pyotp pyyaml uvicorn
  "$host_py" -m pip install -q --target "$stage/app" --no-deps --no-index \
    --find-links "$wheelhouse" atlas
  rm -rf "$wheelhouse"
  cp -a "$root/frontend/dist" "$stage/frontend/dist"
  cp "$root/packaging/atlas.service" "$root/packaging/atlas-helper.service" \
    "$root/packaging/atlas.tmpfiles" "$root/packaging/pick-uid.sh" \
    "$root/packaging/remove-atlas.sh" "$root/packaging/atlas-cli.sh" \
    "$stage/packaging/"
  cp "$root/packaging/install-bundle.sh" "$stage/install.sh"
  chmod 755 "$stage/install.sh" "$stage/packaging/pick-uid.sh" \
    "$stage/packaging/remove-atlas.sh" "$stage/packaging/atlas-cli.sh"
  # Bundled interpreter may not run on this host; mark it executable for Linux.
  chmod 755 "$stage/python/bin/"* 2>/dev/null || true
  echo "staged $version (host cross-install)"
}

if [ "${ATLAS_NO_DOCKER:-}" = 1 ]; then
  build_host
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  build_with_docker
else
  echo "Docker unavailable; building with host pip (manylinux wheels)." >&2
  build_host
fi

tar -C "$root/dist" -czf "$root/dist/${name}.tar.gz" "$name"
# Basename only — get-atlas.sh runs shasum -c next to the tarball.
(
  cd "$root/dist"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${name}.tar.gz" > "${name}.tar.gz.sha256"
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${name}.tar.gz" > "${name}.tar.gz.sha256"
  fi
)
echo "wrote $root/dist/${name}.tar.gz"
