#!/bin/bash
set -euo pipefail
OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$TASK_DIR/solution/compute.py" --output-dir "$OUTPUT_DIR" \
  --source-dir "${SOURCE_DIR:-/app/data/timedecode}" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}"
