#!/bin/bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$SOLUTION_DIR/compute.py" --output-dir "${OUTPUT_DIR:-/app/output}" "$@"
