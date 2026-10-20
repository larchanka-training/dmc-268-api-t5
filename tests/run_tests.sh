#!/usr/bin/env bash
# Full local check: database, Alembic migration round-trip, linters, tests.
#
# Usage:  tests/run_tests.sh [--down]
#   --down  stop the database container after the run (data volume is kept)
#
# Requirements: Python 3.13 virtualenv in .venv with `poetry install` done,
# Docker (OrbStack/Docker Desktop) running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv not found. Create it: /opt/homebrew/bin/python3.13 -m venv .venv" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

PY_VERSION="$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$PY_VERSION" < "3.13" ]]; then
  echo "ERROR: Python >= 3.13 required, .venv has $PY_VERSION" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "ERROR: neither 'docker compose' nor 'docker-compose' found" >&2
  exit 1
fi

if [[ "${1:-}" == "--down" ]]; then
  trap '"${COMPOSE[@]}" down' EXIT
fi

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/dmc}"

echo "==> Starting PostgreSQL (pgvector)"
"${COMPOSE[@]}" up -d --wait db

echo "==> Alembic: upgrade -> downgrade -> upgrade -> check"
alembic upgrade head
alembic downgrade base
alembic upgrade head
alembic check

echo "==> ruff"
ruff format --check .
ruff check .

echo "==> mypy"
mypy app alembic

echo "==> pytest"
pytest

echo "OK: all checks passed"
