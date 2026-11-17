"""Explicitly selected original full140 producer, actual outer exit, separate numerics.

This is an authentic execution entrypoint, not a source test or readiness check.
"""
import time
import signal
ORIGIN = time.monotonic()
STARTUP_HANDLER = STARTUP_PREVIOUS = None
if __name__ == '__main__':
    if signal.getitimer(signal.ITIMER_REAL) != (0., 0.):
        raise ValueError('Fresh caller timer')
    STARTUP_PREVIOUS = signal.getsignal(signal.SIGALRM)
    def STARTUP_HANDLER(*_): raise TimeoutError('Original 60-second startup deadline')
    signal.signal(signal.SIGALRM, STARTUP_HANDLER)
    signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN + 60 - time.monotonic()))

import argparse
import json
import os
from pathlib import Path
import sys
import types

HERE = Path(__file__).absolute().parent
lib = types.ModuleType('_neural038_library')
lib.__file__ = str(HERE / 'library.py')
exec(compile((HERE / 'library.py').read_bytes(), lib.__file__, 'exec'), lib.__dict__)
ENV = {'PATH': '/usr/bin:/bin:/usr/local/bin', 'LANG': 'C', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1',
       'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}


def deadlines(origin, launch, seconds):
    if not origin <= launch < origin + 60:
        raise ValueError('Launch remains inside original startup allowance')
    lib.profile(seconds)
    overall = origin + 1860 + 150 + seconds
    producer = launch + 1860 + 30
    if producer + seconds + 60 > overall:
        raise ValueError('Preserved observer and numerical allowances fit original overall clock')
    return producer, overall


def _execute(args, origin, startup_handler):
    c, manifest, bodies, source = lib.runtime(origin + 60)
    selected_raw = c.capture(args.selection, 32768, json.loads(args.selection_pin), lambda: c.before(origin + 60))
    selected_pin = c.pin(selected_raw)
    policy = c.module(bodies, 'policy.py', HERE / 'runtime', c=c)
    selected = policy.selection(c.parse(selected_raw), source)
    operator = c.path(args.operator_repository)
    source_repository = c.path(args.source_repository)
    c.need(str(operator) == selected['repository'] and operator != source_repository,
           'Explicit separate operator input repository and public source checkout')
    identity = lib.source_identity(c)
    authorization_raw = c.capture(args.authority, 65536, json.loads(args.authority_pin), lambda: c.before(origin + 60))
    authorization = lib.authority(c.parse(authorization_raw), selected, identity, args.numerical_seconds)
    c.capture(selected['program']['path'], 131072, c.only_pin(selected['program']), lambda: c.before(origin + 60))
    # Preserve the original exact method/runtime review requirements before dispatch.
    read_count = 0
    def read(count):
        nonlocal read_count
        read_count += count; c.need(read_count <= 2**20, 'Bounded startup review reads')
    review_budget = types.SimpleNamespace(tick=lambda: c.before(origin + 60), read=read)
    policy.reviews(selected, review_budget)
    lib.evaluator(source_repository, c)  # Captured code only; no public arrays.
    output = c.path(args.output)
    original_output = c.path(selected['output'])
    lib.disjoint_roots(c, operator, source_repository, original_output, output)
    c.need(not os.path.lexists(output) and not os.path.lexists(original_output) and output.parent.is_dir(),
           'Fresh original and bridge outputs')
    lib.floor(c, output.parent, selected['other_future_bytes'], legacy_remaining=c.RETAIN)
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    c.need(signal.getsignal(signal.SIGALRM) is startup_handler and 0 < remaining <= 60 and interval == 0,
           'Same original startup timer')
    overall = origin + 1860 + 150 + args.numerical_seconds
    output.mkdir(mode=0o700)
    c.save(output / 'SELECTION.json', selected_raw, 32768, lambda: c.before(origin + 60))
    authority_pin = c.save(output / 'AUTHORITY.json', authorization_raw, 65536, lambda: c.before(origin + 60))
    commitment = {'schema': 'neural038_numerical_bridge_commitment_v1', 'source': source,
                  'selection': selected_pin, 'authority': authority_pin, 'wrapper_sources': identity,
                  'source_repository': str(source_repository), 'operator_repository': str(operator),
                  'profile': lib.profile(args.numerical_seconds), 'origin': origin, 'overall_deadline': overall,
                  'old_grade_handoff_authorized': False, 'automatic_retry': False}
    commit_path = output / 'BRIDGE_COMMITMENT.json'
    commit_pin = c.save(commit_path, c.encoded(commitment), 65536, lambda: c.before(origin + 60))
    proc = c.module(bodies, 'process.py', HERE / 'runtime')
    record = None
    try:
        external = output / 'EXTERNAL.json'
        cache = output / 'UNUSED-PYCACHE'
        c.need(not os.path.lexists(cache), 'Fresh unused outer Python cache')
        argv = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-X', 'pycache_prefix=' + str(cache),
                str(HERE / 'runtime/observe.py'), '--source-pin', json.dumps(source, separators=(',', ':')),
                '--selection', str(output / 'SELECTION.json'), '--selection-pin', json.dumps(selected_pin, separators=(',', ':')),
                '--external-output', str(external)]
        producer_end, confirmed = deadlines(origin, time.monotonic(), args.numerical_seconds)
        c.need(confirmed == overall, 'Original overall envelope')
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Original bridge deadline')))
        signal.setitimer(signal.ITIMER_REAL, overall - time.monotonic())
        raw, record = proc.run(argv, producer_end, producer_end + 10, ENV)
        lib.closed(record); c.before(producer_end)
        c.need(raw == b'' and not os.path.lexists(cache), 'Original observer has no terminal stdout or bytecode cache')
        external_pin = c.pin(c.capture(external, 8192, tick=lambda: c.before(producer_end)))
        c.need(identity == lib.source_identity(c), 'Same bridge code after original production')
        lib.runtime(producer_end)  # Recheck original byte-identical source closure.
        used = c.inventory(original_output, c.RETAIN, 2000)[2]
        bridge_used = c.inventory(output, lib.WRITES, 16)[2]
        lib.floor(c, output, selected['other_future_bytes'], legacy_remaining=max(0, c.RETAIN - used),
                  bridge_remaining=max(0, lib.WRITES - bridge_used))
        proof = {'schema': 'neural038_original_observer_exit_v1', 'source': source, 'commitment': commit_pin,
                 'lifecycle': record, 'argv': argv, 'external_receipt': external_pin,
                 'observed': time.monotonic(), 'deadline': producer_end,
                 'scope': 'Actual owned observer process exit; forced closure does not certify nested native recovery.'}
        proof_path = output / 'OUTER_EXIT.json'
        proof_pin = c.save(proof_path, c.encoded(proof), 65536, lambda: c.before(overall))
        numerical_end = min(overall - 30, time.monotonic() + args.numerical_seconds)
        score_path = output / 'NUMERICAL.json'
        argv = [str(Path(sys.executable).resolve()), '-I', '-B', str(HERE / 'grade.py'),
                '--source-repository', str(source_repository), '--commitment', str(commit_path),
                '--commitment-pin', json.dumps(commit_pin, separators=(',', ':')), '--proof', str(proof_path),
                '--proof-pin', json.dumps(proof_pin, separators=(',', ':')), '--output', str(score_path),
                '--end', str(numerical_end)]
        raw, record = proc.run(argv, numerical_end, min(overall - 10, numerical_end + 10), ENV)
        lib.closed(record); c.before(numerical_end)
        terminal = c.parse(raw)
        c.need(set(terminal) == {'score'}, 'Exact numerical worker terminal')
        c.capture(score_path, 2 * 2**20, terminal['score'], lambda: c.before(overall))
        c.need(identity == lib.source_identity(c), 'Same final bridge source')
        c.need(c.inventory(output, lib.WRITES, 16)[2] + 65536 <= lib.WRITES, 'Complete added retention')
        result = {'schema': 'neural038_full140_numerical_complete_v1', 'commitment': commit_pin,
                  'outer_exit': proof_pin, 'score': terminal['score'], 'numerical_child': record,
                  'requires_observed_caller_natural_exit': True, 'runtime_qualified': False, 'scientific_qualified': False}
        pin = c.save(output / 'COMPLETE.json', c.encoded(result), 65536, lambda: c.before(overall))
        c.before(overall)
        return pin, overall
    except BaseException as error:
        if isinstance(error, proc.ChildFailure): record = error.record
        if time.monotonic() < overall and (record is None or
                record.get('timer_disable_error') is None and record.get('timer_restore_error') is None):
            c.save(output / 'FAILURE.json', c.encoded({'schema': 'neural038_bridge_failure_v1',
                   'error_type': type(error).__name__, 'lifecycle': record, 'automatic_retry': False,
                   'partial_evidence_retained': True, 'nested_native_recovery_may_be_required': True,
                   'numerical_continuation_authorized': False}), 65536, lambda: c.before(overall))
        raise


def execute(args, origin=None, startup_handler=None, previous=None):
    origin = time.monotonic() if origin is None else origin
    if startup_handler is None:
        if signal.getitimer(signal.ITIMER_REAL) != (0., 0.) or time.monotonic() >= origin + 60:
            raise ValueError('Fresh unexpired wrapper startup')
        previous = signal.getsignal(signal.SIGALRM)
        def startup_handler(*_): raise TimeoutError('Original startup deadline')
        signal.signal(signal.SIGALRM, startup_handler)
        signal.setitimer(signal.ITIMER_REAL, origin + 60 - time.monotonic())
    end = None
    try:
        pin, end = _execute(args, origin, startup_handler)
        if time.monotonic() >= end: raise TimeoutError('Caller terminal deadline')
        print(json.dumps({'complete': pin, 'runtime_qualified': False, 'scientific_qualified': False}), flush=True)
        if time.monotonic() >= end: raise TimeoutError('Caller deadline after final flush')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    if end is not None and time.monotonic() >= end: raise TimeoutError('Caller timer restoration deadline')
    return pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-repository', 'operator-repository', 'selection', 'selection-pin', 'authority', 'authority-pin', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--numerical-seconds', type=int, required=True)
    args = parser.parse_args()
    execute(args, ORIGIN, STARTUP_HANDLER, STARTUP_PREVIOUS)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
