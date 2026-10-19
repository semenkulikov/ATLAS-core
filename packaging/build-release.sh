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

# Always rebuild the panel. A stale frontend/dist once shipped the 1.0.x UI inside 1.1.0.
rm -rf "$root/frontend/dist"
npm --prefix "$root/frontend" ci
npm --prefix "$root/frontend" run build
if ! grep -q 'lang="ru"' "$root/frontend/dist/index.html"; then
  echo "frontend/dist/index.html must declare lang=ru" >&2
  exit 1
fi
js=$(find "$root/frontend/dist/assets" -name 'index-*.js' | head -n 1)
if [ -z "$js" ] || ! grep -q 'Приложения' "$js"; then
  echo "built panel JS is missing the Applications label (Приложения)" >&2
  exit 1
fi

rm -rf "$stage"
mkdir -p "$root/dist"

# Static minisign for hosts that do not have it (apply-update.sh refuses unsigned archives).
minisign_url="https://github.com/jedisct1/minisign/releases/download/0.12/minisign-0.12-linux.tar.gz"
minisign_stage=$(mktemp -d)
curl -fsSL -o "$minisign_stage/minisign.tar.gz" "$minisign_url"
tar -xzf "$minisign_stage/minisign.tar.gz" -C "$minisign_stage"
minisign_bin=$(find "$minisign_stage" -type f -name minisign | head -n 1)
if [ -z "$minisign_bin" ] || [ ! -x "$minisign_bin" ]; then
  # Archive may lack +x; still accept a file named minisign.
  minisign_bin=$(find "$minisign_stage" -type f -name minisign | head -n 1)
fi
if [ -z "$minisign_bin" ]; then
  echo "minisign binary missing from $minisign_url" >&2
  exit 1
fi
chmod 755 "$minisign_bin"

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
    "$root/packaging/atlas-update.service" "$root/packaging/atlas.tmpfiles" \
    "$root/packaging/pick-uid.sh" "$root/packaging/remove-atlas.sh" \
    "$root/packaging/atlas-cli.sh" "$root/packaging/apply-update.sh" \
    "$root/packaging/minisign.pub" \
    "$stage/packaging/"
  cp "$minisign_bin" "$stage/packaging/minisign"
  cp "$root/packaging/install-bundle.sh" "$stage/install.sh"
  chmod 755 "$stage/install.sh" "$stage/packaging/pick-uid.sh" \
    "$stage/packaging/remove-atlas.sh" "$stage/packaging/atlas-cli.sh" \
    "$stage/packaging/apply-update.sh" "$stage/packaging/minisign"
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

# Docker path also needs update tooling and the panel checks already ran on the host.
if [ ! -f "$stage/packaging/minisign" ]; then
  mkdir -p "$stage/packaging"
  cp "$root/packaging/atlas-update.service" "$root/packaging/apply-update.sh" \
    "$root/packaging/minisign.pub" "$stage/packaging/" 2>/dev/null || true
  cp "$minisign_bin" "$stage/packaging/minisign"
  chmod 755 "$stage/packaging/minisign" "$stage/packaging/apply-update.sh"
fi
if [ ! -x "$stage/packaging/minisign" ] || [ ! -f "$stage/packaging/minisign.pub" ]; then
  echo "staged tree is missing packaging/minisign or minisign.pub" >&2
  exit 1
fi
if [ ! -f "$stage/packaging/apply-update.sh" ] || [ ! -f "$stage/packaging/atlas-update.service" ]; then
  echo "staged tree is missing apply-update.sh or atlas-update.service" >&2
  exit 1
fi
rm -rf "$minisign_stage"

# Drop AppleDouble leftovers and refuse non-UTF-8 migrations before packaging.
find "$stage" -name '._*' -type f -delete 2>/dev/null || true
mig="$stage/app/atlas/storage/migrations"
if [ ! -d "$mig" ]; then
  echo "staged tree is missing migrations at $mig" >&2
  exit 1
fi
for sql in "$mig"/*.sql; do
  base=$(basename "$sql")
  case "$base" in
    [0-9][0-9][0-9]_*.sql) ;;
    *)
      echo "refusing unexpected migration name: $base" >&2
      exit 1
      ;;
  esac
  if ! python3 -c "from pathlib import Path; Path(r'''$sql''').read_text(encoding='utf-8')"; then
    echo "migration is not UTF-8: $sql" >&2
    exit 1
  fi
done

# Portable archive: no macOS xattrs (avoids LIBARCHIVE.xattr warnings on Linux).
export COPYFILE_DISABLE=1
export COPY_EXTENDED_ATTRIBUTES_DISABLE=1
(
  cd "$root/dist"
  if tar --help 2>&1 | grep -q -- '--format'; then
    tar --format=ustar -czf "${name}.tar.gz" "$name"
  else
    tar -czf "${name}.tar.gz" "$name"
  fi
)
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
