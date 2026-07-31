#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

MODEL=${MODEL:-gpt-5.6-terra}
PYTHON_BIN=${PYTHON_BIN:-python3}

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    brew install ffmpeg
  fi
else
  echo "Homebrew was not found. Install Python 3.11+ and FFmpeg manually."
fi

"$PYTHON_BIN" -m venv .venv
. "$PROJECT_ROOT/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install .

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set. Set it in the environment or save it in the app's API settings before analysis."
fi

echo ""
echo "Install complete."
echo "Run GUI: sh scripts/run_gui.sh"
echo "Run root video analysis: sh scripts/analyze_root_videos.sh"
