#!/bin/bash
set -euo pipefail
OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$TASK_DIR/solution/compute.py" \
  --data-dir "${DATA_DIR:-/app/data/somato}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "$OUTPUT_DIR" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}"
