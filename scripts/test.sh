#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Virtual environment not found."
  echo "Run: sh scripts/bootstrap.sh"
  exit 1
fi

exec "$PYTHON_BIN" -m unittest discover -s tests
