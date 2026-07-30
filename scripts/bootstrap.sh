#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

PYTHON_BIN=${PYTHON_BIN:-python3}

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

. "$PROJECT_ROOT/.venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install -e .
