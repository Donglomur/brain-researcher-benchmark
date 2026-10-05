#!/bin/bash
set -euo pipefail
# Provisioning errors are infrastructure failures, not model scores.
if python3 /tests/private_reference.py; then
  :
else
  exit 78
fi
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
if python3 -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA; then
    printf '1\n' > /logs/verifier/reward.txt
else
    exit_code=$?
    exit "$exit_code"
fi
