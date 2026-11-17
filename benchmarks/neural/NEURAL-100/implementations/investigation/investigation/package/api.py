"""Portable source inspection and explicit operator-only inactive invocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import types

LOADER_PIN = {'bytes': 4487, 'sha256': 'e62cfcaddca4d75477a55ecd5f010d72a4f1ab4abe45a4792073f15ad8f33789'}


def open_source(root, source_pin):
    root = Path(root).absolute()
    path = root / 'loader.py'
    if any(p.is_symlink() for p in (path, *path.parents)) or '..' in path.parts:
        raise ValueError('Ordinary source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != LOADER_PIN['bytes']:
            raise ValueError('Exact bootstrap extent')
        raw = os.read(fd, LOADER_PIN['bytes'] + 1)
        after, named = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if not all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields):
            raise ValueError('Stable bootstrap')
    finally:
        os.close(fd)
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != LOADER_PIN:
        raise ValueError('Fixed loader identity')
    module = types.ModuleType('neural100_investigation_loader')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module.load(root, source_pin)


def inspect(source_pin):
    sources = open_source(Path(__file__).parent, source_pin)
    return {'schema': 'neural100_investigation_source_inspection_v1',
            'task_id': 'NEURAL-100', 'source': sources.identity,
            'source_members': len(sources.raw), 'status': 'inactive_source_only',
            'recordings': 47, 'participants': 41, 'area_recordings': {'A1': 39, 'A2': 8},
            'conditions': 8, 'candidate_artifacts': ['report.json', 'claims.json'],
            'reference_calls_per_future_grade': 1, 'scientific_qualified': False,
            'runtime_qualified': False, 'central_run_or_score_admission_changed': False,
            'authentic_inputs_opened': False}


def run(selection_path, selection_pin, source_pin):
    sources = open_source(Path(__file__).parent, source_pin)
    common, policy = sources.module('common'), sources.module('policy')
    selection = common.parse(common.capture(selection_path, 32768, selection_pin))
    policy.selection(selection, source_pin)
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('An existing timer belongs to another caller')
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError('Original whole invocation deadline')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, selection['whole_seconds'])
    try:
        return sources.module('controller').run(selection, sources)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect'])
    parser.add_argument('--source-bytes', type=int, required=True)
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect({'bytes': args.source_bytes, 'sha256': args.source_sha256}),
                     sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
