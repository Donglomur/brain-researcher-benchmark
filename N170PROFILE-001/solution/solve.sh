#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python3 -I -B -c '
import hashlib, os, stat, sys, tempfile, types
from pathlib import Path
sys.pycache_prefix = tempfile.mkdtemp(prefix="n170-oracle-pycache-")
root = Path("/solution")
assert root.is_dir() and not root.is_symlink()
pins = {
    "mat_metadata": "66fb278c78255e382b85359d26e76df2059c3f9c9dfb2b3ca73ec138148623f7",
    "measurement_kernel": "bc12162f1496b3f4b83419748ee33905a050331cc815ea7d7a9788e6a6fbba9e",
    "oracle_source": "36558dd21ce1722f2dd4be6d29a2215e988795b19d474611a29e92c8cdf5bb60",
    "compute": "7a9c34d48bd992014a8811788b40b694aeb2827244b0be02efe177be00caa7ec",
}
identity = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
compiled = {}
for name, pin in pins.items():
    path = root / (name + ".py")
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),"rb") as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 1048576
        raw = stream.read(1048577)
        assert identity(before) == identity(os.fstat(stream.fileno())) == identity(path.lstat())
    assert len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == pin
    compiled[name] = compile(raw,str(path),"exec")
for name, code in compiled.items():
    module = types.ModuleType(name)
    module.__file__ = str(root / (name + ".py"))
    sys.modules[name] = module
    exec(code,module.__dict__)
raise SystemExit(sys.modules["compute"].main())
'
