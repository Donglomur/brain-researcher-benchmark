"""Closed, relocatable source verifier and entrypoint for NEURAL-030.

Trust the bootstrap/interpreter and select the manifest pin independently.
This verifies source identity/closure, not data, native runtime or science.
"""
import sys
if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
    raise RuntimeError('Invoke with Python -I -B')
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

HERE = Path(__file__).absolute().parent
MEMBER_CAP = 1048576
TOTAL_CAP = 16777216
REQUIRED = frozenset(('absence.py','baseline.py','budget.py','executor.py','features.py',
    'grading.py','holder.py','io_utils.py','native.py','packet.py','reference.py','run.py',
    'runtime_contract.py','score.py','source_binding.py','temporal.py','tests.py','views.py',
    'package.py','package_tests.py','README.md','SCIENTIFIC_PROTOCOL.md','EXTERNAL_REQUIREMENTS.json',
    'PROVENANCE.json','REQUEST.example.json','requirements.txt','RUNTIME_RESOURCES.json','SOURCE_RECORD.json'))


def need(value, message):
    if not value:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def capture(path, cap):
    path = Path(path).absolute()
    need(path.anchor == '/' and '..' not in path.parts and
         all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary POSIX source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, 'Bounded single-link ordinary source member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap+1)
        after = os.fstat(fd); linked = path.lstat()
        attrs = ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before,k) == getattr(after,k) ==
            getattr(linked,k) for k in attrs), 'Stable complete source capture')
        return raw
    finally:
        os.close(fd)


def manifest_pin(root=HERE):
    raw = capture(root/'SOURCE_MANIFEST.json', 262144)
    return raw, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify(size, sha, root=HERE):
    need(type(size) is int and 0 < size <= 262144 and type(sha) is str and
         re.fullmatch('[0-9a-f]{64}', sha), 'Explicit bounded source-manifest pin')
    raw, found = manifest_pin(root)
    need(found == {'bytes': size, 'sha256': sha}, 'Selected manifest pin')
    manifest = strict(raw)
    need(type(manifest) is dict and set(manifest) == {'schema','task_id','files'} and
         manifest['schema'] == 'neural030-fixed-adaptive-source-v1' and
         manifest['task_id'] == 'NEURAL-030', 'Closed NEURAL-030 manifest schema')
    rows = manifest['files']
    need(type(rows) is dict and set(rows) == REQUIRED, 'Complete required authored dependency/document set')
    for name, pin in rows.items():
        need(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*', name) and
             name != 'SOURCE_MANIFEST.json', 'Flat non-self-hashing source names')
        need(type(pin) is dict and set(pin) == {'bytes','sha256'} and type(pin['bytes']) is int and
             0 < pin['bytes'] <= MEMBER_CAP and type(pin['sha256']) is str and
             re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'Exact bounded member pin')
    need({p.name for p in root.iterdir()} == set(rows) | {'SOURCE_MANIFEST.json'},
         'Closed source directory: missing/extra/cache/directory members refused')
    need(sum(x['bytes'] for x in rows.values())+len(raw) <= TOTAL_CAP, 'Whole source-size cap')
    bodies = {}
    for name, pin in rows.items():
        body = capture(root/name, MEMBER_CAP)
        need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
             'Pinned member: '+name)
        body.decode('utf8'); need(b'\0' not in body, 'UTF8 text source only')
        bodies[name] = body
    need({p.name for p in root.iterdir()} == set(rows) | {'SOURCE_MANIFEST.json'}, 'Stable closed membership')
    return manifest, bodies


def load(name, bodies, root=HERE):
    module = types.ModuleType(name); module.__file__ = str(root/(name+'.py'))
    sys.modules[name] = module
    exec(compile(bodies[name+'.py'], module.__file__, 'exec'), module.__dict__)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('manifest-pin','check','inspect','self-test','run','grade'))
    parser.add_argument('--source-bytes', type=int)
    parser.add_argument('--source-sha256')
    parser.add_argument('--request')
    args = parser.parse_args(argv)
    if args.operation == 'manifest-pin':
        need(args.source_bytes is None and args.source_sha256 is None and args.request is None,
             'Pin display accepts no operation inputs')
        _, pin = manifest_pin()
        print(json.dumps({'manifest': pin, 'independent_authentication': False,
                          'instruction': 'Compare with independently trusted release/commit before admission.'}))
        return
    _, bodies = verify(args.source_bytes, args.source_sha256)
    if args.operation == 'check':
        need(args.request is None, 'Source-only check has no data request')
        print(json.dumps({'task_id':'NEURAL-030','source_members':len(bodies),
                          'closed_source_verified':True,'scientific_qualification':False,
                          'native_qualification':False,'submission_ready':False}))
    elif args.operation == 'self-test':
        need(args.request is None, 'Generated controls have no data request')
        # Keep one numerical controller process; compile authenticated bodies
        # instead of adding an extra Python wrapper or importing cached pyc.
        for name in ('io_utils','absence','runtime_contract'):
            load(name, bodies)
        os.environ.update({key:'1' for key in sys.modules['runtime_contract'].THREADS})
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        for name in ('native','views','budget','executor',
                     'source_binding','temporal','packet','features','baseline','reference','score',
                     'grading','holder','run'):
            load(name, bodies)
        need(sys.modules['numpy'].__version__ == '2.2.6',
             'Generated source controls require the declared NumPy2.2.6 profile')
        module = types.ModuleType('__main__'); module.__file__ = str(HERE/'tests.py')
        sys.modules['__main__'] = module; sys.argv = [module.__file__]
        exec(compile(bodies['tests.py'], module.__file__, 'exec'), module.__dict__)
    else:
        need((args.request is not None) is (args.operation in ('run','grade')), 'Explicit operator request only for run/grade')
        runtime = load('run', bodies)
        forwarded = [args.operation,'--source-bytes',str(args.source_bytes),
                     '--source-sha256',args.source_sha256]
        if args.request is not None:
            forwarded += ['--request',args.request]
        runtime.main(forwarded)


if __name__ == '__main__':
    main()
