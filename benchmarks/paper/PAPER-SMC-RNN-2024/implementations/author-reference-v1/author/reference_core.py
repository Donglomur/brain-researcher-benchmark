"""Bounded reference metadata and exact original recipe; no scientific imports."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import stat

ROUTE = 'smc_protected_author_reference_v1'
OUTCOME = 'author_reference'
ACCESS = 'paper_data_author_code_and_weights'
PHASES = ('reference_causal', 'reference_noncausal')
ARMS = dict(zip(PHASES, ('causal', 'noncausal')))
SEEDS = {'causal': 20261117, 'noncausal': 20261118}
FIXED_PROFILE = {'wall_seconds': 10800, 'memory_bytes': 8589934592, 'threads': 6}
MAX_CPU_SECONDS = 64800
METRICS = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
META_CAP = 1024 ** 2
FILE_CAP = 512 * 1024 ** 2


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def reference_profile(cpu_seconds):
    """Explicit prospective reference allowance, never a participant default."""
    need(type(cpu_seconds) is int and 1 <= cpu_seconds <= MAX_CPU_SECONDS,
         'Explicit integer reference CPU seconds in 1..64800')
    return {'cpu_seconds': cpu_seconds, **FIXED_PROFILE}


def validate_profile(value):
    need(type(value) is dict and set(value) == {'cpu_seconds', *FIXED_PROFILE}
         and all(type(v) is int for v in value.values()),
         'Exact integer reference resource profile')
    expected = reference_profile(value['cpu_seconds'])
    need(value == expected, 'Fixed reference wall, memory and thread limits')
    return expected


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate reference metadata field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite reference metadata'))


def path(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts
         and not any(x.is_symlink() for x in (p, *p.parents)), 'Unlinked absolute reference path')
    return p


def body(value, expected=None, cap=META_CAP):
    p = path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded ordinary reference file')
        raw = stream.read(cap + 1)
        after, named = os.fstat(stream.fileno()), p.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
         for k in fields), 'Stable complete reference body')
    if expected is not None:
        need(pin(raw) == expected, 'Exact reference content identity')
    return raw


def read(value, expected=None):
    return decode(body(value, expected))


def write_new(value, raw, mode=0o400):
    p = path(value)
    need(type(raw) is bytes and 0 < len(raw) <= META_CAP, 'Bounded new reference metadata/source')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(raw)


def load_module(name, filename, expected):
    raw = body(filename, expected)
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(filename), 'exec'), module.__dict__)
    return module


def source_identity(root, expected_sha=None):
    root = path(root)
    raw = body(root / 'SOURCE.json')
    if expected_sha is not None:
        need(pin(raw)['sha256'] == expected_sha, 'Selected reference source manifest')
    manifest = decode(raw)
    need(set(manifest) == {'schema', 'route', 'files'}
         and manifest['schema'] == 'smc_author_reference_source_v1'
         and manifest['route'] == ROUTE and type(manifest['files']) is dict,
         'Closed reference source manifest')
    required = {'reference_core.py', 'reference_adapter.py', 'reference_worker.py',
                'reference_episode.py', 'reference_overlay.py', 'reference_legacy.py',
                'BINDINGS.json', 'DEPLOYMENT_BINDING.json', 'REFERENCE_TASK.json',
                'original_protocol.json', 'assisted_delivery.json', 'pair.json', 'runtime_lock.json'}
    helpers = {'author_predict.py', 'prepare.py', 'memory_reduction.py', 'particle_reduction.patch',
               'scorer.py', 'source_manifest.json', 'reference_panel.json'}
    need(set(manifest['files']) == required | {'helpers/' + name for name in helpers},
         'Exact reference component roster')
    for name, expected in manifest['files'].items():
        body(root / name, expected)
    return pin(raw)


def recipe(phase):
    need(phase in ARMS, 'Exact original reference arm')
    arm = ARMS[phase]
    return {'arm': arm, 'seed': SEEDS[arm], 'particles': 192, 'repeats': 32,
            'smooth': False, 'device': 'cpu', 'training': False,
            'checkpoint_search': False, 'access_condition': ACCESS}


def method_plan(phase, program_pin, bindings_pin, resource_profile):
    return {'schema': 'smc_author_reference_method_v2', 'route': ROUTE,
            'role': 'author_calibration', 'phase_id': phase, 'outcome': OUTCOME,
            'access_condition': ACCESS, 'recipe': recipe(phase), 'program': program_pin,
            'bindings': bindings_pin, 'resource_profile': validate_profile(resource_profile),
            'AI_attempt': False, 'scientific_improvement': False}


def validate_job(plan, job, program_pin, bindings_pin):
    profile = validate_profile(plan.get('resource_profile'))
    need(plan == method_plan(plan.get('phase_id'), program_pin, bindings_pin, profile),
         'Exact frozen author model recipe and assisted access')
    expected = {'schema', 'route', 'outcome', 'condition', 'phase_id', 'access_condition',
                'source', 'resource_profile', 'submission_keys', 'program_sha256',
                'declaration_sha256', 'method_freeze_sha256', 'bindings', 'max_file_bytes'}
    need(type(job) is dict and set(job) == expected, 'Exact reference execution job fields')
    need(job['schema'] == 'smc_author_reference_execution_job_v2' and job['route'] == ROUTE
         and job['outcome'] == OUTCOME and job['condition'] == job['phase_id'] == plan['phase_id']
         and job['access_condition'] == ACCESS and validate_profile(job['resource_profile']) == profile
         and all(type(v) is int for v in job['resource_profile'].values())
         and job['submission_keys'] == ['offline'] and job['program_sha256'] == program_pin['sha256']
         and job['bindings'] == bindings_pin and job['max_file_bytes'] == FILE_CAP,
         'Exact reference job, source recipe, resource profile and output')
    need(re.fullmatch('[0-9a-f]{64}', job['method_freeze_sha256']) is not None,
         'Frozen reference method required')
    return recipe(plan['phase_id'])
