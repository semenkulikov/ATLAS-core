#!/bin/sh
# Point this clone at the shared hooks in .githooks/
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

chmod 755 "$root/.githooks/pre-commit" "$root/scripts/ci-check.sh" "$root/scripts/install-git-hooks.sh"
git config core.hooksPath .githooks
echo "Git hooks path set to .githooks (pre-commit runs scripts/ci-check.sh)."
echo "Manual run: scripts/ci-check.sh"
