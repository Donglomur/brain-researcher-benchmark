"""Source-only inspection and a trusted-host bridge to the unchanged grader.

Load this entry under a unique trusted name, never as stdlib `operator`. The
calling process must authenticate this entrypoint and selected manifest before
executing it. Internal source checks are not self-authentication or authority.
"""
import sys

if __name__ == '__main__' and not sys.flags.isolated:
    raise SystemExit('Use an isolated interpreter: python -I -S -B operator.py inspect ...')

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
import types

_SCHEMA = 'neural035_installed_captured_grading_source_v1'
_FILES = frozenset(('operator.py', 'capture_io.py', 'source_loader.py', 'grade_closed.py',
                    'paired_report.py', 'DEPENDENCIES.json', 'README.md',
                    'COMPLETION_STATE.json', 'INSTALLED_INTERFACE.md'))
_ALIASES = {
    'capture_io': 'capture_io.py',
    'paired_report': 'paired_report.py',
    'source_loader': 'source_loader.py',
    '_neural035_installed_grade': 'grade_closed.py',
}
_ACCEPTED = {'DEPENDENCIES.json': (7068, 'd0f7081fe63a5b019dd3764bfbf4a1f1ece4376b4a20c9caa311e36ef56c3e13'), 'capture_io.py': (5660, 'cdb124aa285ca164b33a4eadfb6a0b6634365355f6d0ecd4e6ed28aeeeafc730'), 'source_loader.py': (3096, '46e709f0ff60f80df667f64fc0a391614c540e563ea898fbf060bacaacb952d1'), 'grade_closed.py': (14134, 'd3c806bfa072ad0fa7fc7605adc33628efe6a178d919b9e50b826031b4bdf66e'), 'paired_report.py': (14323, '2b68993e15bc52cacb59a534abe5e7e8a300552ea6a9f8a9c43d03dc71759684'), 'README.md': (3523, 'c4347e90c6d26afff2314d72835589417b5e7e3f47660254d8fab45590233a15'), 'COMPLETION_STATE.json': (987, 'd6325f9525c6f0dddc25dd40e58fab00c4f7a0c67c5984c6ff01b28a6c7bba64')}
_ACCEPTED_SOURCE_COMMIT = '1f4e9ad7bcaa08322e1ad963c56d3010cf2f4ec8'
_MANIFEST_CAP = 65536
_MEMBER_CAP = 2**20
_INSPECTION_OUTPUT_RESERVATION = 32768
_LOCK = threading.RLock()
_MISSING = object()


def _need(value, message):
    if not value:
        raise ValueError(message)


def _pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def _descriptor(value, cap):
    _need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
          type(value['bytes']) is int and 0 < value['bytes'] <= cap and
          type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']) is not None,
          'Exact positive bounded source descriptor')
    return value


def _parse(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, 'Duplicate source metadata key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('Nonfinite source metadata')
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def _budget(budget):
    _need(type(budget.max_read_bytes) is int and budget.max_read_bytes > 0 and
          type(budget.max_write_bytes) is int and budget.max_write_bytes > 0 and
          type(budget.deadline) in (int, float) and math.isfinite(budget.deadline) and
          budget.deadline > time.monotonic() and all(callable(getattr(budget, k, None))
                                                    for k in ('read', 'write', 'tick')),
          'Concrete caller-owned read/write/deadline budget')
    budget.tick()


def _ordinary(path, directory=False):
    path = Path(path)
    _need(path.is_absolute() and str(path) == os.path.abspath(str(path)), 'Canonical absolute source path')
    for parent in (path, *path.parents):
        _need(not parent.is_symlink(), 'No source symlink component')
    observed = path.lstat()
    _need(stat.S_ISDIR(observed.st_mode) if directory else
          stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1, 'Ordinary source member')
    return observed


def _read(path, expected, budget, cap):
    _descriptor(expected, cap)
    _ordinary(path)
    budget.read(expected['bytes'] + 1, 'NEURAL035 installed source capture')
    budget.write(expected['bytes'], 'NEURAL035 immutable source buffer')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
              before.st_size == expected['bytes'], 'Exact source member extent')
        body = stream.read(expected['bytes'] + 1)
        after = os.fstat(stream.fileno())
        named = Path(path).lstat()
    _need(all(getattr(before, key) == getattr(after, key) == getattr(named, key)
              for key in ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')) and
          _pin(body) == expected, 'Stable exact captured source')
    budget.tick()
    return body


def _children(path, budget):
    before = _ordinary(path, directory=True)
    names = set()
    with os.scandir(path) as entries:
        for entry in entries:
            _need(len(names) < 16, 'Bounded installed source inventory')
            names.add(entry.name)
    after = Path(path).lstat()
    _need(all(getattr(before, key) == getattr(after, key)
              for key in ('st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns')), 'Stable source directory census')
    budget.tick()
    return names


def _capture(source_pin, budget):
    _budget(budget)
    root = Path(__file__).absolute().parent
    _need(_children(root, budget) == _FILES | {'SOURCE_MANIFEST.json'},
          'Exact closed ten-file installed source inventory')
    manifest_body = _read(root/'SOURCE_MANIFEST.json', source_pin, budget, _MANIFEST_CAP)
    manifest = _parse(manifest_body)
    _need(type(manifest) is dict and set(manifest) == {'schema', 'task_id', 'files', 'module_aliases',
                                                     'accepted_source_commit', 'status'} and
          manifest['schema'] == _SCHEMA and manifest['task_id'] == 'NEURAL-035' and
          manifest['status'] == 'inactive_source_only' and
          re.fullmatch('[0-9a-f]{40}', _ACCEPTED_SOURCE_COMMIT) is not None and
          manifest['accepted_source_commit'] == _ACCEPTED_SOURCE_COMMIT and
          manifest['module_aliases'] == _ALIASES and type(manifest['files']) is dict and
          set(manifest['files']) == _FILES, 'Exact genuinely bound installed source schema')
    for name, (size, sha) in _ACCEPTED.items():
        _need(manifest['files'][name] == {'bytes': size, 'sha256': sha}, 'Exact selected public source member')
    bodies = {name: _read(root/name, manifest['files'][name], budget, _MEMBER_CAP) for name in sorted(_FILES)}
    dependencies = _parse(bodies['DEPENDENCIES.json'])
    _need(dependencies['schema'] == 'neural035_closed_grading_dependencies_v1' and
          type(dependencies['files']) is dict and len(dependencies['files']) == 31 and
          sum(row['bytes'] for row in dependencies['files'].values()) == 201827 and
          dependencies['authentic_assets_followed'] is False,
          'Declared31-source public profile dependency summary')
    completion = _parse(bodies['COMPLETION_STATE.json'])
    _need(completion['disposition'] == 'ACCEPT_INACTIVE_SOURCE_CONSTRUCTION_WITH_FULL_INVENTED_CALLER_WITNESS'
          and completion['full_positive_caller_witness_passed'] is True
          and completion['engineering_only'] is True and completion['native_qualified'] is False
          and completion['scientific_qualified'] is False and completion['old_route_activated'] is False,
          'Accepted engineering construction only; no inherited scientific authority')
    budget.tick()
    return root, manifest, bodies



def inspect(source_pin, budget):
    """Read only selected local source; no producer, dependency or target body."""
    _, manifest, bodies = _capture(source_pin, budget)
    inventory = {'SOURCE_MANIFEST.json': dict(source_pin), **manifest['files']}
    total = sum(p['bytes'] for p in inventory.values())
    result = {'schema': 'neural035_installed_source_inspection_v1', 'task_id': 'NEURAL-035',
              'source_manifest': dict(source_pin), 'complete_inventory': inventory,
              'source_files': 10, 'source_bytes': total,
              'minimum_loader_read_bytes': total + 10,
              'minimum_loader_write_bytes': total,
              'inspect_cli_output_write_reservation': _INSPECTION_OUTPUT_RESERVATION,
              'fixed_module_aliases': dict(_ALIASES),
              'external_dependencies': {'descriptor': _pin(bodies['DEPENDENCIES.json']),
                                        'files': 31, 'bytes': 201827, 'external_bodies_read': False},
              'declared_scope': {'sessions': 14, 'mice': 7, 'session_local_cells': 1012,
                                 'queries_per_role': 28, 'surrogate_draws': 99},
              'source_engineering_witness_passed': True,
              'runtime_qualified': False, 'scientific_qualified': False, 'execution_authorized': False,
              'new_assignments': 0, 'module_code_executed': False, 'authentic_inputs_read': False}
    budget.tick()
    return result



def _execute_module(alias, body, filename):
    module = types.ModuleType(alias)
    module.__file__ = str(filename)
    module.__package__ = ''
    sys.modules[alias] = module  # Required before dataclass decorators execute.
    exec(compile(body, str(filename), 'exec'), module.__dict__)
    return module


@contextmanager
def _modules(root, bodies, budget):
    # This lock serializes calls through this one loaded operator instance. It
    # does not control other code/loader instances sharing this host process.
    with _LOCK:
        saved = {name: sys.modules.get(name, _MISSING) for name in _ALIASES}
        try:
            loaded = {}
            for name, relative in _ALIASES.items():
                budget.tick()
                budget.read(len(bodies[relative]), 'captured installed source compilation')
                loaded[name] = _execute_module(name, bodies[relative], root/relative)
                budget.tick()
            yield loaded
        finally:
            for name, prior in saved.items():
                if prior is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = prior


def grade_pair(source_pin, repository, producer_root, selection_operand, terminal_raw,
               enclosing_observation, prepared_root, authority, *, max_read_bytes,
               max_write_bytes, deadline):
    """Trusted explicit-resource bridge; never a grading CLI or authority factory.

    Capture and compile only selected source first. Create the exact Budget
    class captured alongside the unchanged grader, carry all preceding debits,
    and preserve the original absolute deadline. No producer/target body is
    opened before unchanged grade_selected checks separate operator authority.
    Dedicated serialized host process required; the lock does not protect
    unrelated loaders or untrusted concurrent host Python.
    """
    budget = _InspectBudget.absolute(max_read_bytes, max_write_bytes, deadline)
    root, _, bodies = _capture(source_pin, budget)
    with _modules(root, bodies, budget) as modules:
        original = modules['capture_io'].Budget(max_read_bytes, max_write_bytes, deadline)
        original.read(budget.read_bytes, 'carry installed source capture/compilation debits')
        original.write(budget.write_bytes, 'carry installed source buffer debits')
        result = modules['_neural035_installed_grade'].grade_selected(
            repository, producer_root, selection_operand, terminal_raw,
            enclosing_observation, prepared_root, authority, original)
    original.tick()
    return result



class _InspectBudget:
    """CLI source-transport budget only; never a grading authority or profile."""
    def __init__(self, reads, writes, seconds):
        _need(type(reads) is int and reads > 0 and type(writes) is int and writes > 0 and
              type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0,
              'Explicit positive inspect read/write/time operands')
        self.max_read_bytes, self.max_write_bytes = reads, writes
        self.read_bytes = self.write_bytes = 0
        self.deadline = time.monotonic() + seconds

    @classmethod
    def absolute(cls, reads, writes, deadline):
        _need(type(reads) is int and reads > 0 and type(writes) is int and writes > 0 and
              type(deadline) in (int, float) and math.isfinite(deadline) and deadline > time.monotonic(),
              'Explicit positive installed-source grading operands')
        out = cls.__new__(cls)
        out.max_read_bytes, out.max_write_bytes = reads, writes
        out.read_bytes = out.write_bytes = 0
        out.deadline = deadline
        return out

    def tick(self):
        _need(time.monotonic() < self.deadline, 'Inspect deadline')

    def read(self, extent, label='source'):
        self.tick()
        _need(type(extent) is int and extent >= 0 and self.read_bytes + extent <= self.max_read_bytes,
              'Inspect read ceiling: ' + label)
        self.read_bytes += extent

    def write(self, extent, label='output'):
        self.tick()
        _need(type(extent) is int and extent >= 0 and self.write_bytes + extent <= self.max_write_bytes,
              'Inspect write ceiling: ' + label)
        self.write_bytes += extent


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect inactive NEURAL-035 installed source only')
    parser.add_argument('operation', choices=['inspect'])
    parser.add_argument('--source-bytes', type=int, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--read-bytes', type=int, required=True)
    parser.add_argument('--write-bytes', type=int, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    args = parser.parse_args(argv)
    budget = _InspectBudget(args.read_bytes, args.write_bytes, args.seconds)
    result = inspect({'bytes': args.source_bytes, 'sha256': args.source_sha256}, budget)
    budget.write(_INSPECTION_OUTPUT_RESERVATION, 'precharged inspect JSON serialization/output')
    raw = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    _need(len(raw) <= _INSPECTION_OUTPUT_RESERVATION, 'Bounded inspect output')
    budget.tick()
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    budget.tick()


if __name__ == '__main__':
    main()
