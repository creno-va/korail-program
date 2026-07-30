#!/usr/bin/env sh
set -eu

REPO=${REPO:-creno-va/korail-program}
VERSION=${VERSION:-latest}
MODEL=${MODEL:-gemma4:12b}
INSTALL_ROOT=${INSTALL_ROOT:-"$HOME/Applications/KorailProgram"}
PYTHON_BIN=${PYTHON_BIN:-python3}

if [ "$VERSION" = "latest" ]; then
  RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest")
  TAG=$(printf "%s" "$RELEASE_JSON" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
else
  TAG=$VERSION
fi

if [ -z "$TAG" ]; then
  echo "Could not resolve release tag."
  exit 1
fi

TMP_ROOT=$(mktemp -d)
ZIP_PATH="$TMP_ROOT/source.zip"
EXTRACT_PATH="$TMP_ROOT/source"
SOURCE_DIR="$INSTALL_ROOT/source"
SOURCE_URL="https://github.com/$REPO/archive/refs/tags/$TAG.zip"

mkdir -p "$INSTALL_ROOT"
echo "Downloading $SOURCE_URL"
curl -fL "$SOURCE_URL" -o "$ZIP_PATH"
mkdir -p "$EXTRACT_PATH"
unzip -q "$ZIP_PATH" -d "$EXTRACT_PATH"
EXPANDED_DIR=$(find "$EXTRACT_PATH" -mindepth 1 -maxdepth 1 -type d | head -n 1)

rm -rf "$SOURCE_DIR"
cp -R "$EXPANDED_DIR" "$SOURCE_DIR"

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    brew install ffmpeg
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    brew install ollama
  fi
else
  echo "Homebrew was not found. Install Python 3.11+, FFmpeg, and Ollama manually if missing."
fi

"$PYTHON_BIN" -m venv "$INSTALL_ROOT/.venv"
. "$INSTALL_ROOT/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install "$SOURCE_DIR"

if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    nohup ollama serve > "$INSTALL_ROOT/ollama.log" 2>&1 &
    sleep 5
  fi
  ollama pull "$MODEL"
else
  echo "Ollama was not found. Install Ollama manually, then run: ollama pull $MODEL"
fi

cat > "$INSTALL_ROOT/run_gui.sh" <<EOF
#!/usr/bin/env sh
exec "$INSTALL_ROOT/.venv/bin/korail-analyzer-gui"
EOF

cat > "$INSTALL_ROOT/analyze_videos.sh" <<EOF
#!/usr/bin/env sh
INPUT_DIR=\${1:-\$PWD}
exec "$INSTALL_ROOT/.venv/bin/korail-analyzer" analyze-videos "\$INPUT_DIR" --out "\$PWD/output/analysis" --model "$MODEL"
EOF

chmod +x "$INSTALL_ROOT/run_gui.sh" "$INSTALL_ROOT/analyze_videos.sh"

echo ""
echo "Install complete: $INSTALL_ROOT"
echo "Run GUI: $INSTALL_ROOT/run_gui.sh"
echo "Analyze videos: $INSTALL_ROOT/analyze_videos.sh /path/to/videos"
