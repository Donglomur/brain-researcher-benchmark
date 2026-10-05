#!/bin/bash
set -uo pipefail
# Provisioning errors are infrastructure failures, not model scores.
if python3 /tests/private_reference.py; then
  :
else
  exit 78
fi
mkdir -p /logs/verifier
python3 -m pytest /tests/test_outputs.py -q --ctrf /logs/verifier/ctrf.json
status=$?
if [ "$status" -eq 0 ]; then
    printf '1.0\n' > /logs/verifier/reward.txt
else
    printf '0.0\n' > /logs/verifier/reward.txt
fi
exit 0
