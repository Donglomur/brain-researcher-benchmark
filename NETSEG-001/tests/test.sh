#!/bin/bash
set -euo pipefail
echo 0 > /logs/verifier/reward.txt
if python3 -m pytest --ctrf /logs/verifier/ctrf.json --junitxml=/logs/verifier/junit.xml \
   -o junit_family=xunit1 /tests/test_outputs.py -rA
then echo 1 > /logs/verifier/reward.txt; exit 0
else te=$?; echo 0 > /logs/verifier/reward.txt; exit $te; fi
