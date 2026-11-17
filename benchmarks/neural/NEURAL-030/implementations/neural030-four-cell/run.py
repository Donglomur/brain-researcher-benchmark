"""NEURAL030 CLI: compile selected local source bytes; never load package pyc."""
import sys
if not sys.flags.isolated:
    raise RuntimeError('Invoke this operator CLI with Python -I')
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types

HERE = Path(__file__).resolve().parent


def need(value, message):
    if not value:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate JSON member')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def captured(path, cap):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No linked source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, 'Bounded ordinary source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        attrs = ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
             == getattr(linked, k) for k in attrs), 'Stable complete source bytes')
        return raw
    finally:
        os.close(fd)


def source_check(size, sha):
    raw = captured(HERE/'SOURCE_MANIFEST.json', 262144)
    need(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha, 'Root-selected source manifest')
    manifest = strict(raw)
    need(manifest['schema'] == 'neural030-fixed-adaptive-source-v1' and manifest['task_id'] == 'NEURAL-030',
         'Exact source package')
    bodies = {}
    for name, pin in manifest['files'].items():
        need(type(name) is str and name and '/' not in name and name not in ('.', '..'), 'Flat source member')
        body = captured(HERE/name, 1048576)
        need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
             'Pinned source body')
        bodies[name] = body
    return manifest, bodies


def load_modules(bodies, names):
    modules = {}
    for name in names:
        module = types.ModuleType(name); module.__file__ = str(HERE/(name+'.py'))
        sys.modules[name] = module
        exec(compile(bodies[name+'.py'], module.__file__, 'exec'), module.__dict__)
        modules[name] = module
    return modules


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=('inspect', 'run', 'grade'))
    ap.add_argument('--source-bytes', required=True, type=int)
    ap.add_argument('--source-sha256', required=True)
    ap.add_argument('--request')
    args = ap.parse_args(argv)
    _, bodies = source_check(args.source_bytes, args.source_sha256)
    if args.operation == 'inspect':
        need(args.request is None, 'Inspect has no data input')
        result = {'task_id': 'NEURAL-030', 'sessions': 16, 'dispatches': 128,
            'candidate_interface': 'candidate.py --input /input --output /output/submission.json',
            'case_path': '/input/public/case.json', 'source_complete': True,
            'native_qualification': False, 'scientific_qualification': False,
            'authentic_adaptive_agent_established': False}
    else:
        need(args.request is not None, 'Explicit trusted operator request')
        modules = load_modules(bodies, ('io_utils', 'absence', 'runtime_contract', 'native', 'views', 'budget', 'executor'))
        request = strict(captured(args.request, 65536))
        modules['executor'].validate_request(request)
        if args.operation == 'run':
            result = modules['executor'].execute(request, bodies, captured(HERE/'SOURCE_MANIFEST.json', 262144))
        else:
            modules = load_modules(bodies, ('source_binding', 'temporal', 'packet', 'features',
                                            'baseline', 'reference', 'score', 'grading'))
            result = modules['grading'].grade(request)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
