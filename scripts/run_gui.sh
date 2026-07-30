#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
GUI_EXE="$PROJECT_ROOT/.venv/bin/korail-analyzer-gui"

if [ ! -x "$GUI_EXE" ]; then
  echo "GUI launcher not found."
  echo "Run: sh scripts/bootstrap.sh"
  exit 1
fi

exec "$GUI_EXE"
