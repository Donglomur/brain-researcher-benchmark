#!/bin/bash
set -euo pipefail
OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$TASK_DIR/solution/compute.py" \
  --source-dir "${SOURCE_DIR:-/app/source}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --method "${ALLEN2P_METHOD:-same_trials}" \
  --output-dir "$OUTPUT_DIR" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}"
