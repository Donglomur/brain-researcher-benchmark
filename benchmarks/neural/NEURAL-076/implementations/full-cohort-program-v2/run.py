"""Explicitly selected original 650-context execution, observed exit, then current grading.

Not a source-control entrypoint: invoking this command performs authentic work.
Use test_bridge.py for generated software controls only.
"""
import time
import signal

ORIGIN = time.monotonic()
STARTUP_HANDLER = STARTUP_PREVIOUS = None
if __name__ == '__main__':
    if signal.getitimer(signal.ITIMER_REAL) != (0., 0.):
        raise ValueError('Fresh caller startup timer')
    STARTUP_PREVIOUS = signal.getsignal(signal.SIGALRM)
    def STARTUP_HANDLER(*_):
        raise TimeoutError('Original caller startup deadline')
    signal.signal(signal.SIGALRM, STARTUP_HANDLER)
    signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN + 60 - time.monotonic()))

import argparse
from pathlib import Path
import os
import sys
import types

HERE = Path(__file__).absolute().parent
support = types.ModuleType('_neural076_bridge_support')
support.__file__ = str(HERE / 'support.py')
exec(compile((HERE / 'support.py').read_bytes(), support.__file__, 'exec'), support.__dict__)
ENV = {'PATH': '/usr/bin:/bin:/usr/local/bin', 'LANG': 'C', 'LC_ALL': 'C', 'PYTHONNOUSERSITE': '1',
       'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}


def execution_deadlines(origin, launch, whole_seconds, score_seconds):
    if not origin <= launch < origin + 60:
        raise ValueError('Launch remains inside original 60-second startup allowance')
    overall = origin + whole_seconds + score_seconds + 120
    collection = launch + whole_seconds + 30
    if collection + score_seconds + 30 > overall:
        raise ValueError('Complete collection and score allowances fit original whole envelope')
    return collection, overall


def _execute(args, origin, startup_handler):
    loader, bodies, _, source = support.runtime()
    common, coordinator, process = loader('common'), loader('coordinator'), loader('process')
    raw, selection_pin = common.capture(args.selection, 131072)
    common.need(selection_pin['sha256'] == args.selection_sha256, 'Explicit original selection pin')
    selection = common.decode(raw)
    coordinator.validate_selection(selection, source, bodies)
    sources = support.source_identity(common)
    common.need(args.instructions_sha256 == sources['INSTRUCTIONS.md']['sha256'], 'Acknowledge exact current instructions')
    _, program = common.capture(selection['program']['path'], 131072, selection['program'])
    support.current_scorer(args.repository, common)  # Source only, before candidate/query execution.
    budget = support.score_budget(args.score_seconds)
    common.need(args.external_scoring_memory_bytes == budget['memory_bytes'], 'Explicit external score memory selection')
    common.need(selection['other_future_bytes'] >= budget['write_and_retained_cap'],
                'Original disk envelope must reserve the added scoring output as OTHER')
    output = common.path(args.output)
    roots = [common.path(selection[k]) for k in ('output', 'collection')]
    roots.append(roots[0].with_name(roots[0].name + '.observer'))
    common.need(not os.path.lexists(output) and output.parent.is_dir()
                and all(output != root and output not in root.parents and root not in output.parents for root in roots),
                'Fresh disjoint bridge output; no overwrite or private collection nesting')
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    common.need(signal.getsignal(signal.SIGALRM) is startup_handler and 0 < remaining <= 60
                and interval == 0 and time.monotonic() < origin + 60, 'Same active original startup clock')
    overall_end = origin + selection['whole_seconds'] + budget['seconds'] + 120
    output.mkdir(mode=0o700)
    binding = {'schema': 'neural076_current_instructions_binding_v2', 'source': source,
               'selection': selection_pin, 'program': program, 'execution_files': sources,
               'collection': selection['collection'], 'collection_output': selection['output'],
               'current_instructions_acknowledged_before_execution': True, 'score_budget': budget,
               'separate_scoring_explicitly_selected': True, 'origin': origin, 'deadline': overall_end,
               'repository': str(common.path(args.repository)), 'automatic_retry': False}
    binding_path = output / 'BINDING.json'
    binding_pin = common.write(binding_path, common.encode(binding), 262144)
    record = None
    try:
        argv = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', str(HERE / 'runtime/observe.py'),
                '--source-sha256', source['sha256'], '--selection', str(common.path(args.selection)),
                '--selection-sha256', selection_pin['sha256']]
        collection_end, confirmed_end = execution_deadlines(origin, time.monotonic(),
                                                             selection['whole_seconds'], budget['seconds'])
        common.need(confirmed_end == overall_end, 'Original complete caller envelope')
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Original bridge deadline')))
        signal.setitimer(signal.ITIMER_REAL, overall_end - time.monotonic())
        streams, record = process.run(argv, collection_end, collection_end + 10, ENV,
                                      cwd=str(HERE / 'runtime'), cap=8192, accepted=(0,))
        coordinator.child_closed(record)
        common.before(collection_end)
        terminal = common.decode(streams['stdout'])
        proof = {'schema': 'neural076_observed_outer_exit_v2', 'source': source, 'binding': binding_pin,
                 'lifecycle': record, 'terminal': terminal, 'observed': time.monotonic(), 'deadline': collection_end,
                 'scope': 'Actual owned observer child, not a file-only completion assertion.'}
        proof_path = output / 'OUTER_EXIT.json'
        proof_pin = common.write(proof_path, common.encode(proof), 262144)
        common.need(sources == support.source_identity(common), 'Bridge source unchanged after collection')
        score_end = min(overall_end - 10, time.monotonic() + budget['seconds'])
        score_path = output / 'SCORE.json'
        argv = [str(Path(sys.executable).resolve()), '-I', '-B', str(HERE / 'score_closed.py'),
                '--repository', str(common.path(args.repository)), '--binding', str(binding_path),
                '--binding-sha256', binding_pin['sha256'], '--proof', str(proof_path),
                '--proof-sha256', proof_pin['sha256'], '--output', str(score_path), '--end', str(score_end)]
        streams, record = process.run(argv, score_end, min(overall_end, score_end + 10), ENV,
                                      cwd=str(HERE), cap=8192, accepted=(0,))
        coordinator.child_closed(record)
        common.before(score_end)
        terminal = common.decode(streams['stdout'])
        common.need(set(terminal) == {'report'}, 'Exact scoring terminal')
        _, report_pin = common.capture(score_path, 16 * common.MIB, terminal['report'])
        common.need(sources == support.source_identity(common), 'Final same bridge source')
        common.need(common.inventory(output, 8)[2] + 65536 <= support.SCORE_WRITES, 'Added retained/write allowance')
        result = {'schema': 'neural076_observed_scoring_complete_v2', 'binding': binding_pin,
                  'outer_exit': proof_pin, 'score': report_pin, 'scoring_lifecycle': record,
                  'runtime_qualified': False, 'scientific_qualified': False,
                  'requires_natural_caller_exit': True, 'observed': time.monotonic(), 'deadline': overall_end}
        common.before(overall_end)
        final = common.write(output / 'COMPLETE.json', common.encode(result), 262144)
        common.before(overall_end)
        return final, overall_end
    except BaseException as error:
        if isinstance(error, process.ChildFailure):
            record = error.record
        # A timer failure or expired envelope grants no additional blocking write.
        if time.monotonic() < overall_end and (record is None or
                record.get('timer_disable_error') is None and record.get('timer_restore_error') is None):
            common.write(output / 'FAILURE.json', common.encode({'schema': 'neural076_bridge_failure_v2',
                         'error': type(error).__name__, 'lifecycle': record, 'partial_evidence_retained': True,
                         'automatic_retry': False, 'scientific_qualified': False}), 262144)
        raise


def execute(args, origin=None, startup_handler=None, startup_previous=None):
    """Enclose source preflight through final flush; tests use the same entrypoint."""
    origin = time.monotonic() if origin is None else origin
    if startup_handler is None:
        if signal.getitimer(signal.ITIMER_REAL) != (0., 0.) or time.monotonic() >= origin + 60:
            raise ValueError('Fresh unexpired caller startup')
        startup_previous = signal.getsignal(signal.SIGALRM)
        def startup_handler(*_):
            raise TimeoutError('Original caller startup deadline')
        signal.signal(signal.SIGALRM, startup_handler)
        signal.setitimer(signal.ITIMER_REAL, origin + 60 - time.monotonic())
    end = None
    try:
        final, end = _execute(args, origin, startup_handler)
        if time.monotonic() >= end:
            raise TimeoutError('Caller terminal deadline')
        print(__import__('json').dumps({'complete': final, 'runtime_qualified': False,
                                      'scientific_qualified': False}), flush=True)
        if time.monotonic() >= end:
            raise TimeoutError('Caller deadline after final flush')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, startup_previous)
    if end is not None and time.monotonic() >= end:
        raise TimeoutError('Caller deadline after timer restoration')
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'selection', 'selection-sha256', 'instructions-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--score-seconds', type=int, required=True)
    parser.add_argument('--external-scoring-memory-bytes', type=int, required=True)
    args = parser.parse_args()
    execute(args, ORIGIN, STARTUP_HANDLER, STARTUP_PREVIOUS)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
