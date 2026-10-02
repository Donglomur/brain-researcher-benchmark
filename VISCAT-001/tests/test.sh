#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
if python3 -m pytest /tests/test_outputs.py -rA --ctrf /logs/verifier/ctrf.json \
  --junitxml=/logs/verifier/junit.xml -o junit_family=xunit1 -p no:cacheprovider; then
  printf '1\n' > /logs/verifier/reward.txt
else
  exit $?
fi
