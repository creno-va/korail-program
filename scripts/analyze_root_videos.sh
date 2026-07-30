#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
ANALYZER="$PROJECT_ROOT/.venv/bin/korail-analyzer"

MODEL=${KORAIL_VISION_MODEL:-gemma3:4b}
INTERVAL_SEC=${KORAIL_INTERVAL_SEC:-10}
MIN_REPORT_RISK=${KORAIL_MIN_REPORT_RISK:-medium}

if [ ! -x "$ANALYZER" ]; then
  echo "Analyzer launcher not found."
  echo "Run: sh scripts/install_macos.sh"
  exit 1
fi

exec "$ANALYZER" analyze-videos "$PROJECT_ROOT" \
  --out "$PROJECT_ROOT/output/analysis" \
  --interval-sec "$INTERVAL_SEC" \
  --model "$MODEL" \
  --min-report-risk "$MIN_REPORT_RISK"
