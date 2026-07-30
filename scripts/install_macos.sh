#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

MODEL=${MODEL:-gemma3:4b}
PYTHON_BIN=${PYTHON_BIN:-python3}

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    brew install ffmpeg
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    brew install ollama
  fi
else
  echo "Homebrew was not found. Install Python 3.11+, FFmpeg, and Ollama manually."
fi

"$PYTHON_BIN" -m venv .venv
. "$PROJECT_ROOT/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install .

if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    mkdir -p "$PROJECT_ROOT/output"
    nohup ollama serve > "$PROJECT_ROOT/output/ollama.log" 2>&1 &
    sleep 5
  fi
  ollama pull "$MODEL"
else
  echo "Ollama was not found. Install Ollama manually, then run: ollama pull $MODEL"
fi

echo ""
echo "Install complete."
echo "Run GUI: sh scripts/run_gui.sh"
echo "Run root video analysis: sh scripts/analyze_root_videos.sh"
