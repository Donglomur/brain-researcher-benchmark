"""Bounded trusted-operator I/O and exact source capture; no operation on import."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import types

HERE = Path(__file__).absolute().parent
CONDITION = 'neural031_direct_numeric_context_v1'
OBS_CAP = 524288
ANSWER_CAP = 131072
RAW_CAP = 524288
REQUEST_CAP = 8388608
META_CAP = 65536
ROSTER = tuple((fold, view) for fold in range(20) for view in ('baseline', 'neural'))


def need(ok, code):
    if not ok:
        raise ValueError(code)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def decode(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'exact_content_descriptor')


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary_absolute_path')
    return path


def read(path, cap, expected=None, budget=None, empty=False):
    path = ordinary(path)
    if expected is not None:
        descriptor(expected, cap)
    if budget is not None:
        budget.input(cap)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and (0 if empty else 1) <= before.st_size <= cap,
             'bounded_regular_file')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k)
             for k in fields), 'stable_complete_file')
    need(expected is None or pin(body) == expected, 'content_identity')
    return body


def write(path, body, budget=None):
    path = ordinary(path)
    need(type(body) is bytes, 'write_bytes')
    if budget is not None:
        budget.output(len(body))
    with path.open('xb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def fresh(path, protected=()):
    path = ordinary(path)
    for root in protected:
        root = ordinary(root)
        need(not path.is_relative_to(root) and not root.is_relative_to(path), 'disjoint_output')
    need(path.parent.is_dir() and not path.exists(), 'fresh_output')
    path.mkdir(mode=0o700)
    return path


class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.deadline = time.monotonic() + limits['arm_seconds']
        self.read = self.written = 0

    def tick(self):
        need(time.monotonic() < self.deadline, 'arm_deadline')

    def input(self, count):
        self.tick()
        need(type(count) is int and count >= 0 and self.read + count <= self.limits['read_bytes'],
             'read_budget')
        self.read += count

    def output(self, count):
        self.tick()
        need(type(count) is int and count >= 0 and self.written + count <= self.limits['write_bytes'],
             'write_budget')
        self.written += count


def module(body, path):
    value = types.ModuleType('n031_pinned_' + Path(path).stem)
    value.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), value.__dict__)
    return value


def load(source_sha256):
    raw = read(HERE / 'SOURCE.json', META_CAP)
    need(pin(raw)['sha256'] == source_sha256, 'selected_source_manifest')
    source = decode(raw)
    need(type(source) is dict and set(source) == {'schema', 'files', 'dependencies', 'scope'} and
         source['schema'] == 'neural031_direct_provider_source_v1' and
         set(source['files']) == {'common.py', 'bridge.py', 'client.py', 'provider.py',
                                  'test_provider.py', 'README.md'}, 'source_closure')
    root = HERE.parents[4]
    bodies = {}
    for name, expected in source['files'].items():
        bodies[name] = read(HERE / name, 262144, expected)
    expected_paths = {
        'numeric': 'benchmarks/neural/NEURAL-031/implementations/numerical-observation-v1/observation.py',
        'numeric_source': 'benchmarks/neural/NEURAL-031/implementations/numerical-observation-v1/SOURCE.json',
        'numeric_tests': 'benchmarks/neural/NEURAL-031/implementations/numerical-observation-v1/test_observation.py',
        'numeric_readme': 'benchmarks/neural/NEURAL-031/implementations/numerical-observation-v1/README.md',
        'io': 'benchmarks/neural/NEURAL-031/implementations/paired-delivery-v1/io031.py',
        'inputs': 'benchmarks/neural/NEURAL-031/implementations/paired-delivery-v1/SOURCE_INPUTS.json',
        'endpoint': 'benchmarks/neural/NEURAL-031/implementations/ratio-scoring-v1/endpoint.py',
        'http': 'benchmarks/neural/NEURAL-077/implementations/waveform-provider-v1/client.py',
        'owned': 'benchmarks/shared/viewer-process-ownership-v1/owned_exit.py',
    }
    need(set(source['dependencies']) == set(expected_paths), 'dependency_closure')
    modules = {'source': source, 'source_pin': pin(raw), 'root': root}
    for name, relative in expected_paths.items():
        row = source['dependencies'][name]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
             row['path'] == relative, 'dependency_path')
        body = read(root / relative, 262144, {k: row[k] for k in ('bytes', 'sha256')})
        if name in ('numeric', 'http', 'owned'):
            modules[name] = module(body, root / relative)
    modules['bridge'] = module(bodies['bridge.py'], HERE / 'bridge.py')
    modules['engine'] = modules['numeric'].Engine(source['dependencies']['numeric_source']['sha256'])
    return modules


def policy(provider, limits, interpreter):
    need(type(provider) is dict and set(provider) == {'model', 'max_output_tokens'} and
         type(provider['model']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', provider['model']) and
         type(provider['max_output_tokens']) is int and 1 <= provider['max_output_tokens'] <= 32768,
         'selected_model_output_policy')
    need(type(limits) is dict and set(limits) == {'episode_seconds', 'cleanup_seconds',
         'arm_seconds', 'read_bytes', 'write_bytes'}, 'finite_resource_policy')
    for key in ('episode_seconds', 'cleanup_seconds', 'arm_seconds'):
        need(type(limits[key]) in (int, float) and math.isfinite(limits[key]) and limits[key] > 0,
             'finite_clock')
    need(5 < limits['episode_seconds'] <= 3600 and 0 < limits['cleanup_seconds'] <= 30 and
         limits['episode_seconds'] + limits['cleanup_seconds'] + 5 < limits['arm_seconds'] <= 2**31,
         'complete_episode_and_finalization_budget')
    for key in ('read_bytes', 'write_bytes'):
        need(type(limits[key]) is int and 0 < limits[key] <= 1024**4, 'finite_byte_limit')
    need(type(interpreter) is dict and set(interpreter) == {'path', 'bytes', 'sha256'}, 'interpreter_pin')
    ordinary(interpreter['path'])
    descriptor({k: interpreter[k] for k in ('bytes', 'sha256')}, 64 * 1024**2)
