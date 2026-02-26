#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUTS_DIR="$ROOT_DIR/outputs"
TARGET_DATE="${TARGET_DATE:-${SELECTED_DATE:-}}"

# Allow `scripts/analyze_outputs.sh YYYY-MM-DD` as a convenience.
if [[ $# -gt 0 && "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  TARGET_DATE="$1"
  shift
fi

TARGET_DATE="${TARGET_DATE:-$(date -u +%F)}"
DATE_DIR="$OUTPUTS_DIR/$TARGET_DATE"
ANALYSIS_DIR="$OUTPUTS_DIR/analysis/$TARGET_DATE"
JSON_OUT="$ANALYSIS_DIR/run_evaluation.json"
ANALYSIS_CREATED_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
HTML_OUT="$ANALYSIS_DIR/run_evaluation_${ANALYSIS_CREATED_UTC}.html"

if [[ ! -d "$OUTPUTS_DIR" ]]; then
  echo "Outputs directory not found: $OUTPUTS_DIR" >&2
  exit 1
fi

if [[ ! -d "$DATE_DIR" ]]; then
  echo "No outputs found for UTC date $TARGET_DATE at: $DATE_DIR" >&2
  exit 1
fi

mkdir -p "$ANALYSIS_DIR"

python "$ROOT_DIR/analyze_outputs.py" \
  --outputs-dir "$OUTPUTS_DIR" \
  --date "$TARGET_DATE" \
  --format table \
  --write "$JSON_OUT" \
  --write-html "$HTML_OUT" \
  "$@"

echo
echo "Wrote JSON analysis: $JSON_OUT"
echo "Wrote HTML analysis: $HTML_OUT"
open $HTML_OUT
