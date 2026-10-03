#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
if timeout --kill-after=10s 240s python3 -I -B -c '
import hashlib,os,stat,sys,tempfile
from pathlib import Path
sys.pycache_prefix=tempfile.mkdtemp(prefix="petvt-private-cache-")
root=Path("/tests")
pins={"test_outputs.py":"b62094421e713a39e1dd6a1ed1c40a5a873e9bf42dc07f3958dd18f278965e72",
      "grader_bootstrap.py":"557e431e4ea5774b76ac632acdcf57d652fc3381ba08b9b6b31468b2cd589bdd"}
for name,pin in pins.items():
    p=root/name
    assert not p.is_symlink()
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),"rb") as stream:
        before=os.fstat(stream.fileno());raw=stream.read(262145)
        signature=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        assert stat.S_ISREG(before.st_mode) and 0<before.st_size<=262144
        assert signature(before)==signature(os.fstat(stream.fileno()))==signature(p.lstat())
    assert len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==pin
import pytest
from importlib.metadata import entry_points
plugins=[e.load() for e in entry_points(group="pytest11") if e.dist.metadata["Name"].lower()=="pytest-json-ctrf"]
assert len(plugins)==1
raise SystemExit(pytest.main(["-q","-c","/dev/null","--rootdir=/tests","--noconftest","--import-mode=importlib","-p","no:cacheprovider","-o","junit_family=xunit1","--ctrf","/logs/verifier/ctrf.json","--junitxml=/logs/verifier/junit.xml","/tests/test_outputs.py::test_source_bound_petvt_sensitivity"],plugins=plugins))
'; then
    printf '1\n' > /logs/verifier/reward.txt
else
    status=$?
    printf '0\n' > /logs/verifier/reward.txt
    exit "$status"
fi
