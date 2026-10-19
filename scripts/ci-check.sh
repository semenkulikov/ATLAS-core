#!/bin/sh
# Run the same checks as .github/workflows/ci.yml.
# Usage:
#   scripts/ci-check.sh           # all jobs
#   scripts/ci-check.sh backend   # backend only
#   scripts/ci-check.sh frontend  # frontend only
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

scope=${1:-all}
failed=0

run() {
  echo ""
  echo "==> $*"
  if ! "$@"; then
    failed=1
    echo "FAILED: $*"
  fi
}

need_backend=0
need_frontend=0
case "$scope" in
  all)
    need_backend=1
    need_frontend=1
    ;;
  backend) need_backend=1 ;;
  frontend) need_frontend=1 ;;
  *)
    echo "Usage: $0 [all|backend|frontend]" >&2
    exit 2
    ;;
esac

if [ "$need_backend" -eq 1 ]; then
  echo "CI check: backend"
  run uv sync --frozen --project backend --group dev
  run uv run --project backend ruff check backend
  run uv run --project backend ruff format --check backend
  run uv run --project backend mypy --config-file backend/pyproject.toml backend/atlas
  run uv run --project backend pytest backend/tests \
    --cov=atlas.domain --cov=atlas.detectors --cov=atlas.security \
    --cov-report=term-missing \
    --cov-fail-under=85
  run uv run --project backend bandit -q -r backend/atlas -c backend/pyproject.toml
  run uv run --project backend pip-audit backend
  if command -v semgrep >/dev/null 2>&1; then
    run semgrep scan --config p/python --error --metrics=off backend/atlas
  elif command -v uvx >/dev/null 2>&1; then
    run uvx --from 'semgrep>=1.76' semgrep scan --config p/python --error --metrics=off backend/atlas
  else
    echo "WARN: semgrep not installed; CI will still run it on push." >&2
  fi
fi

if [ "$need_frontend" -eq 1 ]; then
  echo "CI check: frontend"
  if [ ! -d frontend/node_modules ]; then
    run npm --prefix frontend ci
  fi
  run npm --prefix frontend test
  run npm --prefix frontend run check
fi

if [ "$failed" -ne 0 ]; then
  echo ""
  echo "ci-check failed (same gates as GitHub Actions)."
  exit 1
fi
echo ""
echo "ci-check passed."
