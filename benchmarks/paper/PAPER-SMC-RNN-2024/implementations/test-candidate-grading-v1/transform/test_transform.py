"""Apply an authenticated completed VALID gain to a frozen original TEST baseline.

This route constructs a candidate; it does not recreate historical author
identity or a VALID prediction freeze. All arithmetic and HDF5 transformation
remain in the exact closed gain-transform dependency.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

META_CAP = 1024 * 1024
FILE_CAP = 512 * 1024 * 1024
GAIN_SOURCE_PIN = {'bytes': 604, 'sha256': '34bcd3a7dc56440e58694f3275bbb59d6f46a7ddc0e3a248c10cd98399c1b44c'}
GAIN_TRANSFORM_PIN = {'bytes': 19658, 'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda'}
RATE_KEYS = tuple(f'{split}_rates_{units}{suffix}' for split in ('train', 'eval')
                  for suffix in ('', '_forward') for units in ('heldin', 'heldout'))
TEST_SHAPES = {name: [2295 if name.startswith('train_') else 574,
                     10 if name.endswith('_forward') else 35,
                     137 if 'heldin' in name else 45] for name in RATE_KEYS}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def ordinary(value):
    need(isinstance(value, (str, Path)), 'path text')
    text = str(value)
    p = Path(text)
    need(p.is_absolute() and str(p) == text and '..' not in p.parts
         and not any(c in text for c in ('\0', '\n', '\r')), 'canonical absolute path')
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'no named-path symlink')
    return p


def signature(value):
    return tuple(getattr(value, name) for name in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def validate_pin(value, cap=FILE_CAP):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= cap
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'exact bounded byte identity')
    return value


def descriptor(value, cap=FILE_CAP):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'named byte descriptor')
    ordinary(value['path'])
    validate_pin({key: value[key] for key in ('bytes', 'sha256')}, cap)
    return value


def source_bytes(value):
    p = ordinary(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= META_CAP, 'bounded ordinary source or metadata')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size and signature(before) == signature(after) == signature(p.lstat()),
         'stable complete source or metadata')
    return raw


def checked(value):
    descriptor(value, META_CAP)
    raw = source_bytes(value['path'])
    need(pin(raw) == {key: value[key] for key in ('bytes', 'sha256')}, 'authenticated metadata descriptor')
    return raw


def decoded(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'no duplicate JSON fields')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'finite JSON'))


def module_from_bytes(name, filename, raw):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    exec(compile(raw, str(filename), 'exec'), module.__dict__)
    return module


def load_gain_transform(source_descriptor):
    """Load only the immutable pure transform; never its VALID production route."""
    descriptor(source_descriptor, META_CAP)
    need({key: source_descriptor[key] for key in ('bytes', 'sha256')} == GAIN_SOURCE_PIN,
         'exact previously selected gain kernel manifest')
    source = decoded(checked(source_descriptor))
    need(type(source) is dict and set(source) == {'schema', 'files'}
         and source['schema'] == 'smc_gain_kernel_source_v1'
         and type(source['files']) is dict
         and set(source['files']) == {'gain_core.py', 'gain_selector.py', 'gain_transform.py', 'METHOD.json'}
         and source['files']['gain_transform.py'] == GAIN_TRANSFORM_PIN,
         'fixed closed gain-transform dependency')
    filename = ordinary(source_descriptor['path']).parent / 'gain_transform.py'
    raw = source_bytes(filename)
    need(pin(raw) == GAIN_TRANSFORM_PIN, 'exact unchanged pure gain-transform bytes')
    return module_from_bytes('_smc_test_candidate_frozen_gain_transform', filename, raw)


def authenticated_core():
    root = ordinary(Path(__file__).absolute()).parent.parent
    filename = root / 'SOURCE.json'
    raw = source_bytes(filename)
    manifest = decoded(raw)
    names = {'test_core.py', 'transform/test_transform.py', 'TEST_PROFILE.json'}
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_test_gain_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == names,
         'exact three-leaf TEST candidate source manifest')
    bodies = {}
    for name in sorted(names):
        expected = validate_pin(manifest['files'][name], META_CAP)
        bodies[name] = source_bytes(root / name)
        need(pin(bodies[name]) == expected, 'authenticated TEST candidate source leaf: ' + name)
    need(pin(source_bytes(Path(__file__).absolute())) == manifest['files']['transform/test_transform.py'],
         'current wrapper is the selected TEST candidate source')
    core = module_from_bytes('_smc_test_candidate_authenticated_core', root / 'test_core.py', bodies['test_core.py'])
    return core, {'path': str(filename), **pin(raw)}


def transform_test(test_method_descriptor, output_path):
    """Construct a distinct TEST candidate using a completed authenticated VALID selection.

    The core authenticates the frozen TEST method, genuine completed selector
    result, historical baseline, checkpoint lineage and original TEST order.
    This trusted operator API accepts no target or raw gain and provides no
    physical filesystem-exclusion or inference-owner qualification.
    """
    core, source = authenticated_core()
    admitted = core.admit_test_transform(test_method_descriptor)
    need(type(admitted) is dict
         and set(admitted) == {'gain', 'baseline_descriptor', 'gain_source', 'source', 'method', 'lineage'},
         'exact TEST-transform admission from authenticated core')
    need(encoded(admitted['source']) == encoded(source), 'admitted TEST source is current selected kernel')
    need(encoded(admitted['method']) == encoded(test_method_descriptor), 'same authenticated frozen TEST method')
    baseline = descriptor(admitted['baseline_descriptor'])
    gain_source = descriptor(admitted['gain_source'], META_CAP)
    transform = load_gain_transform(gain_source)
    need(tuple(transform.RATE_KEYS) == RATE_KEYS, 'unchanged eight canonical prediction rate fields')
    transform.validate_gain(admitted['gain'])
    result = transform.transform_h5(
        baseline['path'], output_path, {key: baseline[key] for key in ('bytes', 'sha256')},
        admitted['gain'], expected_shapes=TEST_SHAPES)
    return {'schema': 'smc_test_gain_transform_v1', 'phase': 'test', 'role': 'candidate',
            'source': source, 'method': admitted['method'], 'lineage': admitted['lineage'],
            'gain_source': gain_source, 'baseline': baseline, 'output': result['output'], 'transform': result,
            'historical_author_identity_claim': False, 'target_accessed': False,
            'physical_filesystem_exclusion_qualified': False, 'inference_execution_qualified': False,
            'scientific_improvement': False}
