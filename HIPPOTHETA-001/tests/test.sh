#!/bin/bash
set -uo pipefail
# Provisioning errors are infrastructure failures, not model scores.
if python3 /tests/private_reference.py; then
  :
else
  exit 78
fi
mkdir -p /logs/verifier
if python3 -m pytest -q /tests/test_outputs.py -rA; then
    printf '1.0\n' > /logs/verifier/reward.txt
else
    printf '0.0\n' > /logs/verifier/reward.txt
fi
