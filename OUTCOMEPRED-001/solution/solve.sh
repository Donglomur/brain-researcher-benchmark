#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/compute.py" \
  --data-dir "${SOURCE_DIR:-/app/data/outcomepred}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "${OUTPUT_DIR:-/app/output}" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}" "$@"
