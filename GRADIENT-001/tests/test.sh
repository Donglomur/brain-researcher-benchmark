#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
timeout --signal=TERM --kill-after=10 3000 python3 -I -B - <<'PY'
import hashlib
import os
from pathlib import Path
import re
import stat
import types

PIN = '7f63d618eb5086e32bcfa30a632aada9f5819b4cd64f36f2d3248b9f5fb062bf'
if type(PIN) is not str or re.fullmatch('[0-9a-f]{64}', PIN) is None:
    raise ValueError('unfrozen_shell_entrypoint_pin')
path = Path('/tests/entrypoint.py')
for part in (*reversed(path.parents), path):
    mode = part.lstat().st_mode
    if stat.S_ISLNK(mode) or (part != path and not stat.S_ISDIR(mode)):
        raise ValueError('shell_entrypoint_path')
before = path.lstat()
if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 1024**2:
    raise ValueError('shell_entrypoint_size')
def signature(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns
with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
    if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('shell_entrypoint_changed')
    raw = stream.read(before.st_size + 1)
    if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('shell_entrypoint_changed')
if signature(path.lstat()) != signature(before) or len(raw) != before.st_size:
    raise ValueError('shell_entrypoint_changed')
if hashlib.sha256(raw).hexdigest() != PIN: raise ValueError('shell_entrypoint_sha256')
module = types.ModuleType('_gradient_retained_entrypoint'); module.__file__ = str(path)
exec(compile(raw, str(path), 'exec'), module.__dict__)
raise SystemExit(module.main('grader'))
PY
status=$?
if [ "$status" -eq 0 ]; then
    printf '1\n' > /logs/verifier/reward.txt
fi
exit "$status"
