"""Owned future preparation process; all receipt flags remain provisional."""
import time
ORIGIN = time.monotonic()
import argparse
import os
from pathlib import Path
import signal
import sys
import types

from custody import Budget, below, need, read_pinned, write_exclusive
from source_plan import encode, digest
from driver import json_value

WORK, CLEANUP, OUTER = 21600, 21720, 21840
PROCESS_PIN = (8713, 'dc27f7691cff7e4907a9259726628e323dc7af91d26cfce815aa7dd104225d30')


def alarm(*_): raise TimeoutError('original outer preparation deadline')


def lifecycle(record):
    true = ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed', 'streams_eof',
            'spawn_attempted', 'spawn_acknowledged')
    false = ('timed_out', 'term_sent', 'kill_sent', 'unresolved_creation')
    need(type(record) is dict and all(record.get(k) is True for k in true)
         and all(record.get(k) is False for k in false)
         and type(record.get('exit_code')) is int and record['exit_code'] == 0
         and all(k in record and record[k] is None for k in ('error_type', 'timer_disable_error', 'timer_restore_error')),
         'exact complete natural worker lifecycle')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection', required=True)
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--observation-parent', required=True)
    parser.add_argument('--observation-name', required=True)
    args = parser.parse_args(argv)
    previous = None; armed = False
    root = repo = parent = out = worker_dir = capacity_fd = None
    original = None
    try:
        need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'exclusive outer timer custody')
        previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN + 60 - time.monotonic())); armed = True
        budget = Budget(deadline=float(ORIGIN + OUTER), read_cap=272_000_000, write_cap=8_000_000)
        root = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        def absolute(value):
            need(Path(value).is_absolute() and str(Path(value)) == value, 'canonical absolute selected path')
            return value[1:]
        repo = below(root, absolute(args.repo), os.O_RDONLY | os.O_DIRECTORY)
        def capture_at(root_fd, path, cap, sha):
            fd = below(root_fd, path, os.O_RDONLY)
            try: n = os.fstat(fd).st_size
            finally: os.close(fd)
            return read_pinned(root_fd, {'path': path, 'bytes': n, 'sha256': sha}, budget, cap)
        selected_raw = capture_at(root, absolute(args.selection), 1_048576, args.selection_sha256)
        selection = json_value(selected_raw)
        need(selection.get('enabled') is True and selection.get('schema') == 'neural098-full33-preparation-selection-v1',
             'selected complete preparation route')
        source_dir = Path(__file__).absolute().parent
        base = str(source_dir.relative_to(Path(args.repo)))
        manifest_raw = capture_at(repo, base + '/SOURCE_MANIFEST.json', 65536, selection['source_manifest_sha256'])
        manifest = json_value(manifest_raw)
        from source_plan import source_manifest
        source_manifest(manifest, base)
        captured = {}
        for pin in manifest['files']: captured[pin['path']] = read_pinned(repo, pin, budget, 1_000_000)
        lock = json_value(captured[base + '/SOURCE_LOCK.json'])
        pin = lock['dependencies']['process']
        process_raw = read_pinned(repo, pin, budget, 16384)
        need((len(process_raw), digest(process_raw)) == PROCESS_PIN, 'unchanged owned process helper')
        q = json_value(read_pinned(repo, selection['runtime_qualification'], budget, 1_048576))
        from runtime import envelope
        interpreter = envelope(q, selection=selection, manifest_sha256=digest(manifest_raw))
        python = interpreter['path']; absolute(python)
        read_pinned(root, dict(interpreter, path=python[1:]), budget, 256_000_000)
        # Worker verifies interpreter and all selected native module pins before
        # opening original assets; observer has authenticated its exact source.
        parent = below(root, absolute(args.observation_parent), os.O_RDONLY | os.O_DIRECTORY)
        from source_plan import capacity
        capacity_fd = below(root, absolute(selection['output_parent']), os.O_RDONLY | os.O_DIRECTORY)
        need(os.fstat(capacity_fd).st_dev == os.fstat(parent).st_dev, 'selected single output filesystem')
        protected = capacity(selection['capacity'], capacity_fd, initial=True)
        budget.space = (capacity_fd, protected)
        from custody import relative
        need(len(relative(args.observation_name)) == 1, 'fresh observer directory name')
        os.mkdir(args.observation_name, 0o700, dir_fd=parent)
        out = below(parent, args.observation_name, os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(parent)
        module = types.ModuleType('owned_preparation_process')
        exec(compile(process_raw, '<exact owned process helper>', 'exec'), module.__dict__)
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONHASHSEED': '0',
               'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
               'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}
        command = [python, '-B', str(source_dir / 'worker.py'), '--repo', args.repo,
                   '--selection', args.selection, '--selection-sha256', args.selection_sha256, '--origin', str(ORIGIN)]
        need(time.monotonic() < ORIGIN + 60, 'original startup deadline before launch')
        signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN + WORK - time.monotonic()))
        record = None; failure = None; streams = None
        try:
            streams, record = module.run(command, ORIGIN + WORK, ORIGIN + CLEANUP, env,
                                         cwd=args.repo, cap=65536, accepted=(0,), retain_failure_tail=True)
            lifecycle(record)
        except module.ChildFailure as exc:
            record = exc.record; failure = type(exc).__name__
        need(time.monotonic() < ORIGIN + CLEANUP, 'original child cleanup cutoff')
        # No helper timer error can be converted into a successful observation.
        need(record is not None and record.get('timer_disable_error') is None
             and record.get('timer_restore_error') is None, 'helper timer custody established')
        signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN + OUTER - time.monotonic()))
        completion_pin = completion = None
        if failure is None:
            need(streams is not None and streams['stderr'] == b'', 'clean bounded worker terminal publication')
            terminal = json_value(streams['stdout'])
            need(terminal['original_origin'] == ORIGIN and terminal['selection_sha256'] == args.selection_sha256
                 and terminal['complete_preparation_provisional'] is True, 'same-origin worker completion terminal')
            completion_pin = terminal['completion']
            need(completion_pin['path'] == 'COMPLETION.json', 'fixed completion receipt name')
            worker_dir = below(root, absolute(str(Path(selection['output_parent']) / selection['output_name'])),
                               os.O_RDONLY | os.O_DIRECTORY)
            completion_raw = read_pinned(worker_dir, completion_pin, budget, 4_000_000)
            completion = json_value(completion_raw)
            need(completion['complete_preparation'] is True and completion['all33_people_preserved'] is True
                 and completion['all_retained_bindings_preserved'] is True
                 and completion['scientific_qualification'] is False
                 and completion['candidate_or_model_or_reference_or_scorer_executed'] is False,
                 'complete metadata claim without model/scoring qualification')
        observation = {'schema': 'neural098-preparation-owned-observation-v1', 'origin': ORIGIN,
            'selection_sha256': args.selection_sha256, 'source_manifest_sha256': digest(manifest_raw),
            'argv': command, 'worker_lifecycle': record, 'failure': failure, 'completion_pin': completion_pin,
            'worker_claim_not_independently_value_validated': True, 'provisional_complete_preparation': failure is None,
            'original_limits': [WORK, CLEANUP, OUTER], 'capacity': selection['capacity'], 'scientific_qualification': False,
            'independent_outer_natural_exit_required': True, 'public_output_admitted': False}
        published = write_exclusive(out, 'OBSERVATION.json', encode(observation), budget, 4_000_000)
        os.fsync(parent); budget.check()
        sys.stdout.buffer.write(encode({'observation': published, 'provisional': True})); sys.stdout.buffer.flush()
        budget.check()
        need(failure is None, 'worker did not complete; retained failure observation')
    except BaseException as exc: original = exc
    errors = []
    for fd in (worker_dir, out, parent, capacity_fd, repo, root):
        if fd is not None:
            try: os.close(fd)
            except BaseException as exc: errors.append(exc)
    if armed:
        try: signal.setitimer(signal.ITIMER_REAL, 0)
        except BaseException as exc: errors.append(exc)
    if previous is not None:
        try: signal.signal(signal.SIGALRM, previous)
        except BaseException as exc: errors.append(exc)
    if original is not None and not isinstance(original, Exception): raise original
    if errors: raise errors[0] from original
    if original is not None: raise original
    need(time.monotonic() < ORIGIN + OUTER, 'original outer deadline through publication and restoration')
    return 0


if __name__ == '__main__': raise SystemExit(main())
