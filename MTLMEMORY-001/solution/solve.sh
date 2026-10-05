#!/bin/bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python3 "$(dirname "$0")/compute.py" \
  --data-dir "${SOURCE_DIR:-/app/data/mtlmemory}" \
  --method-contract "${METHOD_CONTRACT:-/app/method_contract.json}" \
  --output-dir "${OUTPUT_DIR:-/app/output}" \
  --private-dir "${PRIVATE_DIR:-/app/oracle_private}" \
  --headline-population "${MTLMEMORY_HEADLINE:-crossfit_selected_at_least_five_splits}"
