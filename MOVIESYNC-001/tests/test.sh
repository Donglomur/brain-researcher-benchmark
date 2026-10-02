#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
printf '0\n' > /logs/verifier/reward.txt
if python3 -I -B -c '
import sys, tempfile
sys.pycache_prefix = tempfile.mkdtemp(prefix="moviesync-trusted-pycache-")
sys.path.insert(0, "/tests")
import pytest
from importlib.metadata import entry_points
plugins = [p.load() for p in entry_points(group="pytest11")
           if p.dist.metadata["Name"].lower() == "pytest-json-ctrf"]
assert len(plugins) == 1, "fixed CTRF plugin unavailable"
raise SystemExit(pytest.main(["-c", "/dev/null", "--confcutdir=/tests", "-p", "no:cacheprovider",
    "--ctrf", "/logs/verifier/ctrf.json", "--junitxml=/logs/verifier/junit.xml",
    "/tests/test_outputs.py", "-rA"], plugins=plugins))
'; then
    printf '1\n' > /logs/verifier/reward.txt
else
    status=$?
    printf '0\n' > /logs/verifier/reward.txt
    exit "$status"
fi
