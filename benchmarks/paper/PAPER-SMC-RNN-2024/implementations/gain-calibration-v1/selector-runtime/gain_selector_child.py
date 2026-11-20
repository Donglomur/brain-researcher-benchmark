"""One bounded child for all nine fixed VALID gain scores.

The selected host supplies 2 GiB hard container memory and one 720-second work
plus 60-second cleanup envelope. CPU limits are established once for all gains.
The original baseline and method are frozen before any protected target access.
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
KERNEL_PIN = {'bytes': 604, 'sha256': '34bcd3a7dc56440e58694f3275bbb59d6f46a7ddc0e3a248c10cd98399c1b44c'}
EVALUATOR_PIN = {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}
TARGET_SHA256 = 'e49d7ba5ab99adc1ab8a065b425051446c6a320a50fcbe646fe8ce54335baf48'
SOURCE_FILES = {'gain_core.py', 'gain_selector.py', 'gain_transform.py', 'METHOD.json'}


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



def load_selector(source):
    descriptor(source)
    need({k: source[k] for k in ('bytes', 'sha256')} == KERNEL_PIN,
         'fixed selected gain kernel manifest')
    manifest = decode(checked(source))
    root = absolute(source['path']).parent
    need(absolute(source['path']).name == 'SOURCE.json'
         and type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_gain_kernel_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == SOURCE_FILES,
         'exact finite gain kernel source roster')
    admitted = {}
    for name in sorted(SOURCE_FILES):
        expected = validate_pin(manifest['files'][name])
        raw = body(root / name)
        need(pin(raw) == expected, 'complete authenticated selected kernel body')
        admitted[name] = raw
    need(Path(__file__).name == 'gain_selector_child.py', 'fixed host-authenticated child entrypoint')
    module = types.ModuleType('_smc_bounded_gain_selector')
    module.__file__ = str(root / 'gain_selector.py')
    exec(compile(admitted['gain_selector.py'], module.__file__, 'exec'), module.__dict__)
    return module


def validate_request(value):
    need(type(value) is dict
         and set(value) == {'schema', 'source', 'method', 'baseline_freeze', 'target', 'evaluator', 'output_root'}
         and value['schema'] == 'smc_gain_selection_request_v1',
         'exact one-baseline gain selection request')
    for key in ('source', 'method', 'baseline_freeze', 'evaluator'):
        descriptor(value[key])
    descriptor(value['target'], FILE_CAP)
    need(value['target']['sha256'] == TARGET_SHA256
         and {k: value['evaluator'][k] for k in ('bytes', 'sha256')} == EVALUATOR_PIN,
         'exact original VALID target and canonical evaluator')
    output = absolute(value['output_root'])
    need(output.name == 'selection' and output.parent.name == 'report',
         'fixed fresh bounded report/selection output')
    return value


def run(request_path, request_sha256):
    # Docker bounds already apply at interpreter startup. These limits apply
    # once before the kernel loads scientific modules, never once per gain.
    apply_limits()
    raw = body(request_path)
    need(type(request_sha256) is str and pin(raw)['sha256'] == request_sha256,
         'selected exact gain selection request hash')
    request = validate_request(decode(raw))
    selector = load_selector(request['source'])
    # No prediction, target or evaluator body was opened above. Core performs
    # original freeze admission and the full baseline snapshot before target.
    report = selector.select(str(absolute(str(request_path))), request_sha256)
    descriptor(report)
    need(report['path'] == str(absolute(request['output_root']) / 'SELECTION.json'),
         'exact final selection report path')
    result = decode(checked(report))
    need(result['schema'] == 'smc_gain_selection_report_v1'
         and result['request_sha256'] == request_sha256
         and result['source'] == request['source'] and result['method'] == request['method']
         and result['baseline_freeze'] == request['baseline_freeze']
         and result['target'] == request['target'] and result['evaluator'] == request['evaluator'],
         'completed report preserves exact method, baseline and target joins')
    return {'schema': 'smc_gain_selector_child_completion_v1',
            'request_sha256': request_sha256, 'source': request['source'], 'report': report,
            'all_nine_gains_share_one_child_and_budget': True,
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
