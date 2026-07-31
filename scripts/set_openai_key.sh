#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: sh scripts/set_openai_key.sh sk-..." >&2
  exit 2
fi

if [ "$(uname -s)" = "Darwin" ]; then
  DEFAULT_ENV_FILE="$HOME/Library/Application Support/KorailAnalyzer/.env"
else
  DEFAULT_ENV_FILE="$HOME/.korail_analyzer/.env"
fi
ENV_FILE="${KORAIL_ENV_FILE:-$DEFAULT_ENV_FILE}"
mkdir -p "$(dirname "$ENV_FILE")"
umask 077
printf 'OPENAI_API_KEY=%s\n' "$1" > "$ENV_FILE"

echo "OPENAI_API_KEY has been saved to $ENV_FILE"
echo "Restart the app if it is already open."
