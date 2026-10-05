#!/bin/bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/matplotlib}"
exec python3 "$(dirname "$0")/compute.py" \
  --data-dir "${DATA_DIR:-/app/data/aasmstage}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "${OUTPUT_DIR:-/app/output}" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}" "$@"
