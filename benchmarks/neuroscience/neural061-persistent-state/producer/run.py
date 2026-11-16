"""Source inspector. Actual effectful assembly is the explicit loader.make_host API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types


def need(condition, message):
    if not condition:
        raise ValueError(message)


def captured(path, cap):
    path = Path(path)
    need(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'ordinary source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'bounded source member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        attrs = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(before, k) == getattr(after, k) == getattr(linked, k) for k in attrs) and
             len(body) == before.st_size, 'stable complete source')
        return body
    finally:
        os.close(fd)


def selected(size, sha):
    here = Path(__file__).absolute().parent
    raw = captured(here / 'SOURCE_MANIFEST.json', 262144)
    need(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha, 'root-selected source manifest')
    manifest = json.loads(raw); need(manifest['schema'] == 'N061_NATIVE_STATE_SOURCE_V1', 'source schema')
    bodies = {}
    for name, pin in manifest['files'].items():
        need(name == Path(name).name and name not in ('.', '..'), 'flat source members')
        body = captured(here / name, 1048576)
        need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'selected member identity')
        bodies[name] = body
    return bodies


def compile_modules(bodies):
    modules = {}
    for name in ('wire', 'enclosure', 'supervisor', 'adapter', 'loader'):
        need(name not in sys.modules, 'fresh transport source namespace')
        module = types.ModuleType(name); module.__file__ = '<selected-source>/' + name + '.py'
        sys.modules[name] = module
        exec(compile(bodies[name + '.py'], module.__file__, 'exec'), module.__dict__)
        # Retain the same actual bytes supplied to compile, not a caller's
        # later path/digest claim. The factory compares these original bodies
        # with its separately selected manifest before any method intake.
        module.__compiled_source_bytes__ = bodies[name + '.py']
        modules[name] = module
    return modules


def main(argv=None):
    need(sys.flags.isolated, 'Run with Python -I')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect',))
    parser.add_argument('--source-bytes', type=int, required=True)
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args(argv)
    bodies = selected(args.source_bytes, args.source_sha256); compile_modules(bodies)
    print(json.dumps({'task': 'NEURAL-061', 'scope': 'complete selected Q0/S0/A0',
          'source_sessions': 423, 'source_animals': 126, 'evaluation_sessions': 29,
          'evaluation_animals': 13, 'matching_seeds': 10, 'regions': 'all original R',
          'reference_arms': 6, 'candidate_arms': ['BR', 'BC'],
          'state': 'original fitted object remains in fresh cell/arm container',
          'adapter': 'loader.make_host -> adapter.construct_prepared -> unchanged n061.production._collect',
          'native_invoked': False, 'targets_opened': False, 'benchmark_ready': False,
          'public_admission': 'unchanged hard holds'}, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
