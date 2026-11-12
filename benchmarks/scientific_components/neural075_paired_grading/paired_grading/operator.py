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

_SCHEMA = 'neural075_installed_captured_grading_source_v1'
_FILES = frozenset(('operator.py', 'paired_grade.py', 'pinned_scorer.py',
                    'closure-work-v1/closed_pair.py', 'contrast-work-v1/paired_contrasts.py',
                    'DEPENDENCIES.json', 'README.md', 'INSTALLED_INTERFACE.md'))
_ALIASES = {
    'closed_pair': 'closure-work-v1/closed_pair.py',
    'paired_contrasts': 'contrast-work-v1/paired_contrasts.py',
    'pinned_scorer': 'pinned_scorer.py',
    '_neural075_installed_paired_grade': 'paired_grade.py',
}
_ACCEPTED = {
    'paired_grade.py': (12878, 'ef9f5f2a13a3ae034b967e56630eb920dfaa72f347a48b25bd1fd1f1082803da'),
    'pinned_scorer.py': (3318, 'b445bf5e2b4028b69edbdade9c53ef7cca340f01ee6d63aaed14d07df736c0a8'),
    'closure-work-v1/closed_pair.py': (23132, 'b6ad8b96850196b4569fac5463748f7ca4fef029281db5b73021517b1861ce3c'),
    'contrast-work-v1/paired_contrasts.py': (9846, '176664fed3fbd34560e7b72b7ae9a1c4cb3872b95431d973ef2efbeffacdd8d4'),
    'DEPENDENCIES.json': (4258, '78cce51a8ef971cb65604fea473c32c246ca930492f17a55eef4861d36dea755'),
    'README.md': (10527, '59dc4e6065590416b74c18fef8f689f0b6a871742171d3ebbf7d90f024bc1a40'),
}
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
    budget.read(expected['bytes'] + 1, 'NEURAL075 installed source capture')
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
    expected_root = {n for n in _FILES if '/' not in n} | {'SOURCE_MANIFEST.json', 'closure-work-v1', 'contrast-work-v1'}
    _need(_children(root, budget) == expected_root and
          _children(root/'closure-work-v1', budget) == {'closed_pair.py'} and
          _children(root/'contrast-work-v1', budget) == {'paired_contrasts.py'},
          'Exact closed nine-file installed source inventory')
    manifest_body = _read(root/'SOURCE_MANIFEST.json', source_pin, budget, _MANIFEST_CAP)
    manifest = _parse(manifest_body)
    _need(type(manifest) is dict and set(manifest) == {'schema', 'task_id', 'files', 'module_aliases',
                                                     'accepted_source_commit', 'status'} and
          manifest['schema'] == _SCHEMA and manifest['task_id'] == 'NEURAL-075' and
          manifest['status'] == 'inactive_source_only' and
          manifest['accepted_source_commit'] == '8f1c65894fc9a3d699e7376d7474617bac310111' and
          manifest['module_aliases'] == _ALIASES and type(manifest['files']) is dict and
          set(manifest['files']) == _FILES, 'Exact selected installed source schema')
    for name, (size, sha) in _ACCEPTED.items():
        _need(manifest['files'][name] == {'bytes': size, 'sha256': sha}, 'Unchanged accepted source member')
    bodies = {name: _read(root/name, manifest['files'][name], budget, _MEMBER_CAP) for name in sorted(_FILES)}
    dependencies = _parse(bodies['DEPENDENCIES.json'])
    _need(dependencies['file_count'] == 18 and dependencies['total_bytes'] == 141576 and
          dependencies['private_authentic_design_or_payload_selected'] is False,
          'Original declared external source dependency summary')
    budget.tick()
    return root, manifest, bodies


def inspect(source_pin, budget):
    """Return source metadata only; no modules, NumPy or external assets opened.

    The API returns a Python object and performs no output serialization. Its
    caller must charge any serialization it performs. The isolated CLI below
    reserves its exact bounded output operation in this same budget.
    """
    _, manifest, bodies = _capture(source_pin, budget)
    inventory = {'SOURCE_MANIFEST.json': dict(source_pin), **manifest['files']}
    result = {'schema': 'neural075_installed_source_inspection_v1', 'task_id': 'NEURAL-075',
              'source_manifest': dict(source_pin), 'complete_inventory': inventory,
              'source_files': 9, 'source_bytes': sum(p['bytes'] for p in inventory.values()),
              'minimum_loader_read_bytes': sum(p['bytes'] + 1 for p in inventory.values()),
              'inspect_cli_output_write_reservation': _INSPECTION_OUTPUT_RESERVATION,
              'fixed_module_aliases': dict(_ALIASES),
              'external_dependencies': {'descriptor': _pin(bodies['DEPENDENCIES.json']),
                                        'files': 18, 'bytes': 141576, 'external_bodies_read': False},
              'declared_scope': {'people': 5, 'arms': 3, 'phases': 2, 'accesses': 2, 'cases': 60},
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
                loaded[name] = _execute_module(name, bodies[relative], root/relative)
                budget.tick()
            yield loaded['_neural075_installed_paired_grade']
        finally:
            for name, prior in saved.items():
                if prior is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = prior


def grade_pair(source_pin, repository, producer_root, complete_pin, commits,
               prepared_root, enclosing_observation, authority, budget):
    """Call the unchanged grade_selected with genuine caller-owned operands.

    Dedicated trusted, serialized host process only. External selection must
    bind this entrypoint/manifest as well as the original authority's operands.
    The source capture/compilation here precedes the original authority hook;
    no producer, design or target is read by this loader. Original grade_selected
    retains its own authority and closure barriers. No approval factory exists.
    """
    root, _, bodies = _capture(source_pin, budget)
    with _modules(root, bodies, budget) as grader:
        budget.tick()
        result = grader.grade_selected(repository, producer_root, complete_pin, commits,
                                       prepared_root, enclosing_observation, authority, budget)
        budget.tick()
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
    parser = argparse.ArgumentParser(description='Inspect inactive NEURAL-075 installed source only')
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
