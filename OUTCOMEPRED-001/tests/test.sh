#!/bin/bash
set -euo pipefail
# Provisioning errors are infrastructure failures, not model scores.
if python3 /tests/private_reference.py; then
  :
else
  exit 78
fi
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if python3 -m pytest -q -p no:cacheprovider /tests/test_outputs.py; then
    echo 1 > /logs/verifier/reward.txt
else
    exit 1
fi
