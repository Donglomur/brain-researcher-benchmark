"""Native private grade: selected source, two captures, closure, admission, reference."""
import hashlib
import os
from pathlib import Path
import stat
import sys
import types

LOADER_PIN = {'bytes': 4487, 'sha256': 'e62cfcaddca4d75477a55ecd5f010d72a4f1ab4abe45a4792073f15ad8f33789'}


def load_source(expected):
    root = Path('/trustedgrade')
    path = root / 'loader.py'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != LOADER_PIN['bytes']:
            raise ValueError('Selected grade bootstrap extent')
        raw = os.read(fd, LOADER_PIN['bytes'] + 1)
        after, named = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if not all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields):
            raise ValueError('Stable native bootstrap')
    finally:
        os.close(fd)
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != LOADER_PIN:
        raise ValueError('Exact native loader source')
    module = types.ModuleType('neural100_native_grade_loader')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module.load(root, expected)


def main():
    if len(sys.argv) != 5:
        raise ValueError('Grade memory, export SHA, source extent and source SHA operands required')
    memory, export_sha = int(sys.argv[1]), sys.argv[2]
    source = {'bytes': int(sys.argv[3]), 'sha256': sys.argv[4]}
    cg = Path('/sys/fs/cgroup')
    if (os.getuid() != 65534 or (cg / 'memory.max').read_text().strip() != str(memory)
            or (cg / 'memory.swap.max').read_text().strip() != '0'
            or (cg / 'pids.max').read_text().strip() != '64'):
        raise ValueError('Observed selected grade bounds')
    quota, period = map(int, (cg / 'cpu.max').read_text().split())
    if quota != period or period <= 0:
        raise ValueError('Observed existing one-CPU profile')
    import numpy as np
    import h5py
    if sys.version_info[:2] != (3, 12) or np.__version__ != '2.2.6' or h5py.__version__ != '3.13.0':
        raise ValueError('Selected native numerical dependencies')
    sources = load_source(source)
    c, grading = sources.module('common'), sources.module('grading')
    c.need(export_sha == sources.data['export_pin']['sha256'], 'Selected dataset/source export')
    raw = {name: c.capture(Path('/submission') / name, cap)
           for name, cap in grading.OUTPUT_CAPS.items()}
    closure_raw = c.capture('/submission/CLOSURE.json', 8192)
    closure = c.parse(closure_raw)
    grading.closure_admit(closure, source, {name: c.pin(body) for name, body in raw.items()})
    # Only the public source-design roster is needed for the common support barrier.
    row = next(r for r in sources.data['files'] if r['target'] == 'public/ROSTER.json')
    roster = c.parse(c.capture(Path('/package') / row['target'], 65536, c.only_pin(row)))
    result = grading.run_grade('/package', source, sources.data, raw['report.json'],
                               raw['claims.json'], closure, roster, np)
    result['source'] = source
    result['export_manifest_sha256'] = export_sha
    result['candidate_closure'] = c.pin(closure_raw)
    # Exclusive output publication; host still requires actual native natural-zero closure.
    c.save('/output/grade.json', c.encoded(result), 2000000)


if __name__ == '__main__':
    main()
