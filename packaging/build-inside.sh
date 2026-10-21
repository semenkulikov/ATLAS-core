#!/bin/bash
# Runs inside linux/amd64. Downloads the interpreter and installs ATLAS into the stage.
set -euo pipefail

stage=${STAGE:?}
url=${PYTHON_URL:?}
export PIP_DISABLE_PIP_VERSION_CHECK=1

apt-get update
apt-get install -y --no-install-recommends curl ca-certificates
rm -rf "$stage"
mkdir -p "$stage/packaging" "$stage/frontend"
curl -fsSL -o /tmp/python.tar.gz "$url"
tar -xzf /tmp/python.tar.gz -C "$stage"
cp -a /src/backend /tmp/backend
"$stage/python/bin/python3" -m pip install --upgrade pip
"$stage/python/bin/python3" -m pip install --target "$stage/app" /tmp/backend
cp -a /src/frontend/dist "$stage/frontend/dist"
cp /src/packaging/atlas.service /src/packaging/atlas-helper.service \
  /src/packaging/atlas-update.service /src/packaging/atlas.tmpfiles \
  /src/packaging/pick-uid.sh /src/packaging/remove-atlas.sh \
  /src/packaging/atlas-cli.sh /src/packaging/apply-update.sh \
  /src/packaging/minisign.pub \
  "$stage/packaging/"
# Host build-release.sh also places packaging/minisign into the stage after this script.
cp /src/packaging/install-bundle.sh "$stage/install.sh"
chmod 755 "$stage/install.sh" "$stage/packaging/pick-uid.sh" \
  "$stage/packaging/remove-atlas.sh" "$stage/packaging/atlas-cli.sh" \
  "$stage/packaging/apply-update.sh" "$stage/python/bin/python3"
PYTHONPATH="$stage/app" "$stage/python/bin/python3" -c 'import atlas,fastapi,uvicorn,websockets,psutil,pyotp; print(atlas.__version__)'
