"""Reusable trusted summary transport; imports frozen lifecycle implementations."""
from pathlib import Path
import hashlib
import importlib
import importlib.util
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
QUALIFIED = ROOT / 'authoring/shared-program-runner-v2'
OWNERS = ROOT / 'authoring/shared-program-ownership-v3'
for name, base in [('qualified_core', QUALIFIED), ('process_owner', OWNERS), ('trusted_controller', OWNERS)]:
    if name in sys.modules and Path(sys.modules[name].__file__).resolve() != base / (name + '.py'):
        raise ValueError('Trusted module namespace collision')
sys.path.insert(0, str(QUALIFIED))
try:
    qualified = importlib.import_module('qualified_core')
finally:
    sys.path.remove(str(QUALIFIED))
sys.path.insert(0, str(OWNERS))
try:
    owner = importlib.import_module('process_owner')
finally:
    sys.path.remove(str(OWNERS))
BaseEngine = qualified.BaseEngine
HostBudget = qualified.HostBudget


def need(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary(path, cap, empty=False):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked canonical input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             (0 if empty else 1) <= before.st_size <= cap, 'Bounded ordinary single-link input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields),
             'Immutable bounded input')
        return body
    finally:
        os.close(fd)


def pinned(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'Exact input descriptor')
    path = ROOT / value['path']
    need(not Path(value['path']).is_absolute() and path.is_relative_to(ROOT), 'Project relative descriptor')
    body = ordinary(path, value['bytes'])
    need(len(body) == value['bytes'] and hashlib.sha256(body).hexdigest() == value['sha256'], 'Frozen input identity')
    return body


def save(path, value, budget, cap=100_000):
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    need(len(body) <= cap, 'Bounded trusted receipt')
    budget.write(path, body, receipt=True, mode=0o444)


def module_from_pin(value, name):
    pinned(value)
    spec = importlib.util.spec_from_file_location(name, ROOT / value['path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile(path):
    value = json.loads(ordinary(path, 32_768))
    need(value['schema_version'] == 1 and value['operator_only'] is True, 'Frozen operator profile')
    need(value['whole_seconds'] == 60 and value['artifact_limit_bytes'] == 12_000_000,
         'Reviewed stage ceilings')
    need(value['worker_output_bytes'] == 8192 and value['candidate_bytes'] == 200_000,
         'Bounded summary protocol')
    expected = {'/grader/worker.py', '/grader/score_core.py', '/grader/PUBLIC_CONTRACT.json',
                '/grader/worker_inputs.json', '/private/reference.json'}
    need(set(value['fixed_mounts']) == expected, 'Exact declared summary files')
    for item in value['fixed_mounts'].values():
        pinned(item)
    need(1 <= len(value['case_labels']) <= 32 and
         len(set(value['case_labels'])) == value['qualification_case_count'] == len(value['case_labels']) and
         all(type(label) is str and re.fullmatch('[A-Za-z0-9_]{1,64}', label) for label in value['case_labels']),
         'Exact bounded qualification case labels')
    pinned(value['qualification_source'])
    owner.validate_controller(value['controller'], [sys.executable, str(ROOT / value['controller']['path'])])
    return value
