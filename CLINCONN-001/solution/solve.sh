#!/bin/bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SOLUTION_DIR/compute.py" \
  --data-dir "${DATA_DIR:-/app/data/clinconn}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "${OUTPUT_DIR:-/app/output}" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}"
