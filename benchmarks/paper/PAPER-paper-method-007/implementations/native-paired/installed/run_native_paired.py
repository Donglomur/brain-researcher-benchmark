"""Inactive UnitMatch installed interface to the exact accepted complete study.

source-check is ordinary-source-only and works with -I -S -B. An explicitly
selected future run needs the accepted scientific dependencies and -I -B.
Presence of this interface grants no scientific or native execution authority.
The trusted launcher must authenticate this caller itself from its installed API.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BUNDLE = HERE/'native-paired'
ACCEPTED_COMPONENT_COMMIT = '2898bc0ff3d0eb98dcae3df1cf72e53c2f54af58'
BINDING_PIN = {'bytes': 6791, 'sha256': '3971cca5d861c3b76714a7cd19b8bbdbab06d2eb8e51ffae93c1fda122d35f83'}
PREFLIGHT_READ_CAP = 1048576
PREFLIGHT_SECONDS = 30


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ordinary(path):
    p = Path(path).absolute()
    require('..' not in p.parts and not any(q.is_symlink() for q in (p, *p.parents)), 'Unlinked literal source path')
    return p


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite source metadata'))


class Preflight:
    """Finite read-only source preflight; run debits this cost and elapsed time."""
    def __init__(self):
        self.origin = time.monotonic()
        self.reads = 0

    def charge(self, read=0, write=0, retained=0):
        require(type(read) is int and read >= 0 and write == retained == 0, 'Read-only source preflight')
        require(self.reads+read <= PREFLIGHT_READ_CAP and time.monotonic()-self.origin < PREFLIGHT_SECONDS,
                'Bounded installed source preflight')
        self.reads += read


def capture(path, pin, preflight):
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin['bytes']
                and before.st_size <= 1048576, 'Exact bounded ordinary source')
        preflight.charge(read=before.st_size+1)
        with os.fdopen(fd, 'rb', closefd=False) as f:
            raw = f.read(before.st_size+1)
        after = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')
        require(len(raw) == before.st_size and all(getattr(before,k) == getattr(after,k) for k in keys)
                and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Stable exact source bytes')
        return raw
    finally:
        os.close(fd)


def capture_bundle(preflight):
    binding = parse(capture(BUNDLE/'SOURCE_BINDING.json', BINDING_PIN, preflight))
    rows = {r['path']: r for r in binding['own']}
    require(len(rows) == len(binding['own']) == 7, 'Complete accepted owned source selection')
    bodies = {}
    for name, pin in rows.items():
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == name, 'Exact source-relative role')
        bodies[name] = capture(BUNDLE/rel, pin, preflight)
    require({'support.py', 'functional.py', 'study.py'} <= set(bodies), 'Complete real study entry and grader')
    return binding, bodies


def loaded(name, body, path):
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    mod.__package__ = ''
    sys.modules[name] = mod
    exec(compile(body, str(path), 'exec'), mod.__dict__)
    return mod


@contextmanager
def captured_study(preflight):
    """Compile the real accepted producer/grader from captured bytes, once.

    Module-name/path changes are temporary in this serialized host operation.
    No function or metric body is rewritten and no score callback is installed.
    """
    binding, bodies = capture_bundle(preflight)
    names = ('support', 'functional', '_unitmatch_installed_study', 'io_utils',
             '_unitmatch_original_interface', '_unitmatch_original_metrics',
             '_unitmatch_independent_bank', '_unitmatch_native_component')
    missing = object()
    old_modules = {name: sys.modules.get(name, missing) for name in names}
    old_path = list(sys.path)
    old_argv = list(sys.argv)
    try:
        loaded('support', bodies['support.py'], BUNDLE/'support.py')
        loaded('functional', bodies['functional.py'], BUNDLE/'functional.py')
        study = loaded('_unitmatch_installed_study', bodies['study.py'], BUNDLE/'study.py')
        yield study, binding
    finally:
        sys.path[:] = old_path
        sys.argv[:] = old_argv
        for name, old in old_modules.items():
            if old is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def source_check(repository):
    """Only source capture/import joins; no cohort, packet, data or model read."""
    preflight = Preflight()
    with captured_study(preflight) as (study, binding):
        # The actual accepted loader verifies/compiles all seven owned and 24
        # external bodies. Its function definitions do not open scientific data.
        study.source_closure(ordinary(repository), BINDING_PIN['sha256'], preflight)
        result = {'schema': 'unitmatch_installed_source_check_v1', 'owned_source_files': len(binding['own']),
                  'external_source_files': len(binding['dependencies']), 'source_binding': BINDING_PIN,
                  'accepted_component_commit': ACCEPTED_COMPONENT_COMMIT,
                  'source_read_bytes': preflight.reads, 'source_read_ceiling': PREFLIGHT_READ_CAP,
                  'scientific_execution': False, 'native_execution': False, 'runtime_qualified': False}
    return result


def invoke(arguments):
    """Reach the actual complete native/A/B programme with its original CLI.

    The only execution binding is resource accounting: source-preflight reads
    and time are charged into the original study Budget. All limits, inputs,
    methods, process constructors, arithmetic and grading remain unchanged.
    """
    require(type(arguments) is list and all(type(x) is str for x in arguments), 'Literal CLI argument vector')
    preflight = Preflight()
    with captured_study(preflight) as (study, _):
        original_budget = study.Budget
        class BudgetIncludingPreflight(original_budget):
            def __init__(self, limits):
                super().__init__(limits)
                self.end = min(self.end, preflight.origin+limits['whole_seconds'])
                self.charge(read=preflight.reads)
        study.Budget = BudgetIncludingPreflight
        # Appending last keeps even argparse abbreviations from overriding the
        # one fixed accepted source binding. All other CLI operands are unchanged.
        sys.argv[:] = [str(BUNDLE/'study.py'), *arguments, '--source-sha256', BINDING_PIN['sha256']]
        return study.main()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    require(argv and argv[0] in ('source-check', 'run'), 'Choose explicit source-check or separately selected run')
    if argv[0] == 'source-check':
        parser = argparse.ArgumentParser(description='Inactive UnitMatch ordinary-source inspection only')
        parser.add_argument('--repository', type=Path, required=True)
        args = parser.parse_args(argv[1:])
        print(json.dumps(source_check(args.repository), sort_keys=True))
        return 0
    return invoke(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
