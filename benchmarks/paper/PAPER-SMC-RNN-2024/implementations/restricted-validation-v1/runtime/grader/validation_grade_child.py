"""One bounded-owner child for the original paired VALID numerical grader.

The selected host supplies the hard 2GiB container bound and the single
720-second work plus 60-second cleanup envelope. This child sets one CPU limit
for both arms. It neither creates an inference owner nor qualifies a pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
import types

META_CAP = 128 * 1024
FILE_CAP = 512 * 1024 * 1024
CPU_SOFT = 600
CPU_HARD = 605
THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')
GRADE_PIN = {'bytes': 24571, 'sha256': 'd794e972069784833093b32f03e74345cd41d6f19d4a82c1e08dc88875819a38'}
PANEL_PIN = {'bytes': 5047, 'sha256': '773a54ed1cfd1083b6d08fee17c7bcb416088a35b5e65a01d9485a3c7c58158a'}
EVALUATOR_PIN = {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}
TARGET_SHA256 = 'e49d7ba5ab99adc1ab8a065b425051446c6a320a50fcbe646fe8ce54335baf48'
SOURCE_FILES = {'validation_grade.py', 'validation_grade_child.py', 'VALID_PANEL.json'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def absolute(value):
    need(type(value) is str and not any(c in value for c in ('\0', '\n', '\r')),
         'unambiguous path string')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value,
         'canonical absolute path')
    return path


def validate_pin(value, cap=META_CAP):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= cap
         and type(value['sha256']) is str
         and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
         'bounded exact content pin')
    return value


def descriptor(value, cap=META_CAP):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'},
         'exact file descriptor')
    absolute(value['path'])
    validate_pin({k: value[k] for k in ('bytes', 'sha256')}, cap)
    return value


def signature(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def body(value):
    path = absolute(str(value))
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no metadata/source path symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= META_CAP, 'bounded ordinary single-link metadata/source')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size
         and signature(before) == signature(after) == signature(path.lstat()),
         'stable complete metadata/source read')
    return raw


def checked(value):
    descriptor(value)
    raw = body(value['path'])
    need(pin(raw) == {k: value[k] for k in ('bytes', 'sha256')}, 'authenticated named metadata/source')
    return raw


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate JSON field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'finite JSON'))


def apply_limits():
    # One limit is established before loading scientific packages, not per arm.
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SOFT, CPU_HARD))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for name in THREAD_ENV:
        os.environ[name] = '1'


def load_grader(source):
    manifest = decode(checked(source))
    root = absolute(source['path']).parent
    need(absolute(source['path']).name == 'SOURCE.json'
         and root == Path(__file__).absolute().parent, 'adjacent selected source manifest')
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_restricted_validation_grade_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == SOURCE_FILES,
         'exact bounded VALID child source roster')
    need(manifest['files']['validation_grade.py'] == GRADE_PIN
         and manifest['files']['VALID_PANEL.json'] == PANEL_PIN,
         'unchanged reviewed numerical grader and original VALID panel')
    admitted = {}
    for name in sorted(SOURCE_FILES):
        expected = validate_pin(manifest['files'][name])
        raw = body(root / name)
        need(pin(raw) == expected, 'exact complete selected source body')
        admitted[name] = raw
    need(Path(__file__).name == 'validation_grade_child.py', 'fixed selected child entrypoint')
    module = types.ModuleType('_smc_bounded_validation_grade')
    module.__file__ = str(root / 'validation_grade.py')
    exec(compile(admitted['validation_grade.py'], module.__file__, 'exec'), module.__dict__)
    return module


def validate_request(value):
    need(type(value) is dict
         and set(value) == {'schema', 'source', 'freezes', 'target', 'evaluator', 'output_root'}
         and value['schema'] == 'smc_restricted_validation_bounded_grade_request_v1',
         'exact bounded VALID request')
    descriptor(value['source'])
    need(type(value['freezes']) is dict and set(value['freezes']) == {'reference', 'candidate'},
         'one complete reference/candidate pair')
    for frozen in value['freezes'].values():
        descriptor(frozen)
    descriptor(value['target'], FILE_CAP)
    descriptor(value['evaluator'])
    need(value['target']['sha256'] == TARGET_SHA256
         and {k: value['evaluator'][k] for k in ('bytes', 'sha256')} == EVALUATOR_PIN,
         'exact original VALID target and unchanged canonical evaluator pins')
    output = absolute(value['output_root'])
    need(output.name == 'validation' and output.parent.name == 'report',
         'fixed fresh bounded host report/validation child output')
    return value


def run(request_path, request_sha256):
    # The host authenticates this entrypoint and supplies the real hard memory
    # and wall bounds. No claim about those bounds is accepted from a request.
    apply_limits()
    raw = body(request_path)
    need(type(request_sha256) is str and pin(raw)['sha256'] == request_sha256,
         'selected exact bounded VALID request hash')
    request = validate_request(decode(raw))
    grader = load_grader(request['source'])
    # No target/evaluator body has been opened above. The unchanged grader
    # authenticates both freezes and both full snapshots before protected access.
    report = grader.score_pair(request['freezes'], request['target']['path'],
                               request['evaluator']['path'], request['output_root'])
    descriptor(report)
    need(report['path'] == str(absolute(request['output_root']) / 'REPORT.json'),
         'exact final paired report path')
    result = decode(checked(report))
    need(result['target'] == request['target']
         and result['freezes'] == request['freezes']
         and result['source'] == GRADE_PIN
         and result['evaluator'] == EVALUATOR_PIN,
         'completed report preserves selected target, freeze and numerical-source joins')
    return {'schema': 'smc_restricted_validation_bounded_child_completion_v1',
            'request_sha256': request_sha256, 'source': request['source'], 'report': report,
            'inference_execution_qualified': False, 'physical_owner_qualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args(argv)
    result = run(args.request, args.sha256)
    print(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False), flush=True)
    return result


if __name__ == '__main__':
    main()
