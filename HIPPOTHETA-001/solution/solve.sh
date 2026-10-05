#!/bin/bash
set -euo pipefail
OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"
PRIVATE_DIR="${PRIVATE_DIR:-/app/oracle_private}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OUTPUT_DIR PRIVATE_DIR
python3 "$TASK_DIR/solution/compute.py" --source-dir "${SOURCE_DIR:-/app/source}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "$OUTPUT_DIR" --private-dir "$PRIVATE_DIR"
