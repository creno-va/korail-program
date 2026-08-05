#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

VERSION=""
SKIP_PYINSTALLER_INSTALL=0
SKIP_RUNTIME_DOWNLOADS=0
BUILD_APP_ONLY=0
SKIP_DMG=0
ARCH_NAME=${KORAIL_PACKAGE_ARCH:-$(uname -m)}
PYTHON_BIN=${PYTHON_BIN:-python3}
CODESIGN_IDENTITY=${KORAIL_CODESIGN_IDENTITY:-}
INSTALLER_SIGN_IDENTITY=${KORAIL_INSTALLER_SIGN_IDENTITY:-}
OLLAMA_MACOS_URL=${OLLAMA_MACOS_URL:-https://github.com/ollama/ollama/releases/latest/download/Ollama-darwin.zip}
FFMPEG_MACOS_URL=${FFMPEG_MACOS_URL:-https://evermeet.cx/ffmpeg/getrelease/zip}
FFPROBE_MACOS_URL=${FFPROBE_MACOS_URL:-https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      VERSION=$2
      shift 2
      ;;
    --skip-pyinstaller-install)
      SKIP_PYINSTALLER_INSTALL=1
      shift
      ;;
    --skip-runtime-downloads)
      SKIP_RUNTIME_DOWNLOADS=1
      shift
      ;;
    --build-app-only)
      BUILD_APP_ONLY=1
      shift
      ;;
    --skip-dmg)
      SKIP_DMG=1
      shift
      ;;
    --arch-name)
      ARCH_NAME=$2
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "macOS packaging must run on macOS because it uses pkgbuild, productbuild, and hdiutil." >&2
  exit 1
fi

if [ -z "$VERSION" ]; then
  VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n 1)
fi

if [ -z "$VERSION" ]; then
  echo "Could not read project version from pyproject.toml" >&2
  exit 1
fi

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

need_command "$PYTHON_BIN"
need_command curl
need_command unzip
need_command pkgbuild
need_command productbuild
need_command hdiutil

mkdir -p .venv
if [ ! -x ".venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

PYTHON="$PROJECT_ROOT/.venv/bin/python"
PYINSTALLER="$PROJECT_ROOT/.venv/bin/pyinstaller"

if [ "$SKIP_PYINSTALLER_INSTALL" -eq 0 ]; then
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -e .
  "$PYTHON" -m pip install "pyinstaller>=6.11"
fi

if [ ! -x "$PYINSTALLER" ]; then
  echo "PyInstaller was not found. Rerun without --skip-pyinstaller-install." >&2
  exit 1
fi

MACOS_VENDOR_ROOT="$PROJECT_ROOT/packaging/vendor/macos"
OLLAMA_VENDOR="$MACOS_VENDOR_ROOT/ollama"
FFMPEG_VENDOR="$MACOS_VENDOR_ROOT/ffmpeg"

test_ollama_runtime() {
  [ -f "$1/ollama" ]
}

test_ffmpeg_runtime() {
  [ -f "$1/bin/ffmpeg" ] && [ -f "$1/bin/ffprobe" ]
}

install_ollama_runtime() {
  if test_ollama_runtime "$OLLAMA_VENDOR"; then
    return
  fi

  TMP_ROOT=$(mktemp -d)
  trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM
  ZIP_PATH="$TMP_ROOT/Ollama-darwin.zip"
  EXTRACT_PATH="$TMP_ROOT/extract"
  echo "Downloading Ollama macOS runtime: $OLLAMA_MACOS_URL"
  curl -fL "$OLLAMA_MACOS_URL" -o "$ZIP_PATH"
  mkdir -p "$EXTRACT_PATH"
  unzip -q "$ZIP_PATH" -d "$EXTRACT_PATH"
  RESOURCES="$EXTRACT_PATH/Ollama.app/Contents/Resources"
  if [ ! -d "$RESOURCES" ]; then
    echo "Could not find Ollama.app/Contents/Resources in downloaded archive." >&2
    exit 1
  fi
  rm -rf "$OLLAMA_VENDOR"
  mkdir -p "$OLLAMA_VENDOR"
  ditto "$RESOURCES" "$OLLAMA_VENDOR"
  chmod 755 "$OLLAMA_VENDOR/ollama" 2>/dev/null || true
  chmod 755 "$OLLAMA_VENDOR/lib/ollama/llama-server" 2>/dev/null || true
  if ! test_ollama_runtime "$OLLAMA_VENDOR"; then
    echo "Downloaded Ollama runtime is incomplete: $OLLAMA_VENDOR" >&2
    exit 1
  fi
}

download_ffmpeg_binary() {
  URL=$1
  NAME=$2
  TARGET=$3
  TMP_ROOT=$(mktemp -d)
  ZIP_PATH="$TMP_ROOT/$NAME.zip"
  EXTRACT_PATH="$TMP_ROOT/extract"

  echo "Downloading $NAME: $URL"
  curl -fL "$URL" -o "$ZIP_PATH"
  mkdir -p "$EXTRACT_PATH"
  unzip -q "$ZIP_PATH" -d "$EXTRACT_PATH"
  FOUND=$(find "$EXTRACT_PATH" -type f -name "$NAME" | head -n 1)
  if [ -z "$FOUND" ]; then
    echo "Could not find $NAME in downloaded archive." >&2
    exit 1
  fi
  cp "$FOUND" "$TARGET"
  chmod 755 "$TARGET"
  rm -rf "$TMP_ROOT"
}

install_ffmpeg_runtime() {
  if test_ffmpeg_runtime "$FFMPEG_VENDOR"; then
    return
  fi

  rm -rf "$FFMPEG_VENDOR"
  mkdir -p "$FFMPEG_VENDOR/bin"
  download_ffmpeg_binary "$FFMPEG_MACOS_URL" "ffmpeg" "$FFMPEG_VENDOR/bin/ffmpeg"
  download_ffmpeg_binary "$FFPROBE_MACOS_URL" "ffprobe" "$FFMPEG_VENDOR/bin/ffprobe"

  if ! test_ffmpeg_runtime "$FFMPEG_VENDOR"; then
    echo "Downloaded FFmpeg runtime is incomplete: $FFMPEG_VENDOR" >&2
    exit 1
  fi
}

copy_bundled_runtime() {
  APP_PATH=$1
  RUNTIME_ROOT="$APP_PATH/Contents/MacOS/runtime"

  if ! test_ollama_runtime "$OLLAMA_VENDOR"; then
    echo "Ollama runtime is missing. Rerun without --skip-runtime-downloads." >&2
    exit 1
  fi
  if ! test_ffmpeg_runtime "$FFMPEG_VENDOR"; then
    echo "FFmpeg runtime is missing. Rerun without --skip-runtime-downloads." >&2
    exit 1
  fi

  rm -rf "$RUNTIME_ROOT"
  mkdir -p "$RUNTIME_ROOT"
  ditto "$OLLAMA_VENDOR" "$RUNTIME_ROOT/ollama"
  ditto "$FFMPEG_VENDOR" "$RUNTIME_ROOT/ffmpeg"
  chmod 755 "$RUNTIME_ROOT/ollama/ollama" 2>/dev/null || true
  chmod 755 "$RUNTIME_ROOT/ollama/lib/ollama/llama-server" 2>/dev/null || true
  chmod 755 "$RUNTIME_ROOT/ffmpeg/bin/ffmpeg" "$RUNTIME_ROOT/ffmpeg/bin/ffprobe" 2>/dev/null || true
}

sign_app() {
  APP_PATH=$1
  if ! command -v codesign >/dev/null 2>&1; then
    return
  fi
  if [ -n "$CODESIGN_IDENTITY" ]; then
    codesign --force --deep --options runtime --sign "$CODESIGN_IDENTITY" "$APP_PATH"
  else
    codesign --force --deep --sign - "$APP_PATH" || true
  fi
}

rm -rf "$PROJECT_ROOT/build/korail-analyzer-macos"
rm -rf "$PROJECT_ROOT/build/macos"
rm -rf "$PROJECT_ROOT/dist/KorailAnalyzer"
rm -rf "$PROJECT_ROOT/dist/Korail Analyzer.app"
mkdir -p "$PROJECT_ROOT/dist/installer"

KORAIL_APP_VERSION="$VERSION" "$PYINSTALLER" --noconfirm "packaging/pyinstaller/korail-analyzer-macos.spec"

APP_PATH="$PROJECT_ROOT/dist/Korail Analyzer.app"
if [ ! -d "$APP_PATH" ]; then
  echo "PyInstaller did not create $APP_PATH" >&2
  exit 1
fi

if [ "$SKIP_RUNTIME_DOWNLOADS" -eq 0 ]; then
  install_ollama_runtime
  install_ffmpeg_runtime
fi
copy_bundled_runtime "$APP_PATH"
sign_app "$APP_PATH"

if [ "$BUILD_APP_ONLY" -eq 1 ]; then
  echo "App bundle created: $APP_PATH"
  exit 0
fi

PKG_ROOT="$PROJECT_ROOT/build/macos/pkg-root"
COMPONENT_PKG="$PROJECT_ROOT/build/macos/KorailAnalyzer-component.pkg"
PKG_PATH="$PROJECT_ROOT/dist/installer/KorailAnalyzerInstaller-$VERSION-macos-$ARCH_NAME.pkg"
DMG_ROOT="$PROJECT_ROOT/build/macos/dmg-root"
DMG_PATH="$PROJECT_ROOT/dist/installer/KorailAnalyzerInstaller-$VERSION-macos-$ARCH_NAME.dmg"

rm -rf "$PKG_ROOT" "$DMG_ROOT"
mkdir -p "$PKG_ROOT/Applications" "$DMG_ROOT"
ditto "$APP_PATH" "$PKG_ROOT/Applications/Korail Analyzer.app"

pkgbuild \
  --root "$PKG_ROOT" \
  --install-location "/" \
  --identifier "kr.co.korail.analyzer" \
  --version "$VERSION" \
  --scripts "$PROJECT_ROOT/packaging/macos/scripts" \
  "$COMPONENT_PKG"

if [ -n "$INSTALLER_SIGN_IDENTITY" ]; then
  productbuild --sign "$INSTALLER_SIGN_IDENTITY" --package "$COMPONENT_PKG" "$PKG_PATH"
else
  productbuild --package "$COMPONENT_PKG" "$PKG_PATH"
fi

if [ "$SKIP_DMG" -eq 0 ]; then
  cp "$PKG_PATH" "$DMG_ROOT/"
  hdiutil create \
    -volname "Korail Analyzer $VERSION" \
    -srcfolder "$DMG_ROOT" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
fi

echo "macOS installer created: $PKG_PATH"
if [ "$SKIP_DMG" -eq 0 ]; then
  echo "macOS dmg created: $DMG_PATH"
fi
