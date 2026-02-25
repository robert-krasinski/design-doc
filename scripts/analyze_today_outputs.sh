#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUTS_DIR="$ROOT_DIR/outputs"
TODAY_UTC="${TODAY_UTC:-$(date -u +%F)}"
TODAY_DIR="$OUTPUTS_DIR/$TODAY_UTC"
ANALYSIS_DIR="$OUTPUTS_DIR/analysis/$TODAY_UTC"
JSON_OUT="$ANALYSIS_DIR/run_evaluation.json"

if [[ ! -d "$OUTPUTS_DIR" ]]; then
  echo "Outputs directory not found: $OUTPUTS_DIR" >&2
  exit 1
fi

if [[ ! -d "$TODAY_DIR" ]]; then
  echo "No outputs found for UTC date $TODAY_UTC at: $TODAY_DIR" >&2
  exit 1
fi

mkdir -p "$ANALYSIS_DIR"

python "$ROOT_DIR/analyze_outputs.py" \
  --outputs-dir "$OUTPUTS_DIR" \
  --date "$TODAY_UTC" \
  --format table \
  --write "$JSON_OUT" \
  "$@"

echo
echo "Wrote JSON analysis: $JSON_OUT"
