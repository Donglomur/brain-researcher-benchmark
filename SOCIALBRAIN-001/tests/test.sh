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
sys.pycache_prefix = tempfile.mkdtemp(prefix="socialbrain-trusted-pycache-")
root = Path("/tests")
assert root.is_dir() and not root.is_symlink()
pins = {"score_submission.py": "9f1c3ac8acab44a699bb43a02ee8471f5ab10c61d0b5bc22758478e74504a26c",
        "test_outputs.py": "426fa07a5f9da88040c62df42c3f2c2c439af59a66c61296d32068bd44a99d89"}
buffers = {}
signature = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
for name, digest in pins.items():
    path = root / name
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 1048576
        raw = stream.read(1048577)
        assert signature(before) == signature(os.fstat(stream.fileno())) == signature(path.lstat())
    assert len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest
    buffers[name] = raw
module = types.ModuleType("score_submission")
module.__file__ = str(root / "score_submission.py")
sys.modules[module.__name__] = module
exec(compile(buffers["score_submission.py"], module.__file__, "exec"), module.__dict__)
import pytest
from importlib.metadata import entry_points
plugins = [entry.load() for entry in entry_points(group="pytest11")
           if entry.dist.metadata["Name"].lower() == "pytest-json-ctrf"]
assert len(plugins) == 1, "fixed CTRF plugin unavailable"
raise SystemExit(pytest.main(["-c", "/dev/null", "--rootdir=/tests", "--confcutdir=/tests", "-p", "no:cacheprovider",
    "-o", "junit_family=xunit1", "--ctrf", "/logs/verifier/ctrf.json",
    "--junitxml=/logs/verifier/junit.xml", "/tests/test_outputs.py::test_source_bound_socialbrain", "-rA"], plugins=plugins))
'; then
    printf '1\n' > /logs/verifier/reward.txt
else
    status=$?
    printf '0\n' > /logs/verifier/reward.txt
    exit "$status"
fi
