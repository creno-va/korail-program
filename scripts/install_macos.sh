#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

MODEL=${MODEL:-qwen3-vl:4b}
PYTHON_BIN=${PYTHON_BIN:-python3}

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    brew install ffmpeg
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    brew install ollama
  fi
else
  echo "Homebrew was not found. Install Python 3.11+ and FFmpeg manually."
fi

"$PYTHON_BIN" -m venv .venv
. "$PROJECT_ROOT/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install .

echo ""
echo "Install complete."
echo "Run GUI: sh scripts/run_gui.sh"
echo "Run root video analysis: sh scripts/analyze_root_videos.sh"
