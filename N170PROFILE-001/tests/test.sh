#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
if timeout --signal=TERM --kill-after=10s 1800s python3 -I -B -c '
import hashlib, os, stat, sys, tempfile, types
from pathlib import Path
sys.pycache_prefix = tempfile.mkdtemp(prefix="n170-trusted-pycache-")
private = Path("/tests")
assert private.is_dir() and not private.is_symlink(), "private test directory"
path = private / "grader_bootstrap.py"
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
with os.fdopen(fd, "rb") as stream:
    before = os.fstat(stream.fileno())
    assert stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 1048576
    raw = stream.read(1048577)
    after = os.fstat(stream.fileno())
identity = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
assert identity(before) == identity(after) == identity(path.lstat()), "bootstrap changed"
assert len(raw) == before.st_size
assert hashlib.sha256(raw).hexdigest() == "3e1c4264d8854c49581789cb9e481b79ac97769a8439cbb1f455ef092ac30f5e", "bootstrap identity"
module = types.ModuleType("grader_bootstrap")
module.__file__ = str(path)
sys.modules[module.__name__] = module
exec(compile(raw, str(path), "exec"), module.__dict__)
sys.path.insert(0, str(private))
module.load_private()
import pytest
from importlib.metadata import entry_points
plugins = [entry.load() for entry in entry_points(group="pytest11")
           if entry.dist.metadata["Name"].lower() == "pytest-json-ctrf"]
assert len(plugins) == 1, "fixed CTRF plugin unavailable"
raise SystemExit(pytest.main(["-c", "/dev/null", "--rootdir=/tests", "--confcutdir=/tests", "-p", "no:cacheprovider",
    "-o", "junit_family=xunit1", "--ctrf", "/logs/verifier/ctrf.json",
    "--junitxml=/logs/verifier/junit.xml", "/tests/test_outputs.py::test_source_bound_n170",
    "-rA"], plugins=plugins))
'; then
    printf '1\n' > /logs/verifier/reward.txt
else
    status=$?
    printf '0\n' > /logs/verifier/reward.txt
    exit "$status"
fi
