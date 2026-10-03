#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
TASK_SOLUTION="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec timeout --kill-after=10s 180s python3 -I -B "$TASK_SOLUTION/compute.py"
