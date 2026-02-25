#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUTS_DIR="$ROOT_DIR/outputs"

if [[ ! -d "$OUTPUTS_DIR" ]]; then
  echo "Outputs directory not found: $OUTPUTS_DIR" >&2
  exit 1
fi

# Remove all contents but keep the outputs directory itself.
find "$OUTPUTS_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

# Recreate common subfolders if needed (no-op if not present in repo yet).
mkdir -p "$OUTPUTS_DIR"

echo "Emptied outputs directory: $OUTPUTS_DIR"
