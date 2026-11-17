"""Prepare or compile THINGS-EEG2 using explicit pinned operator operands.

stage, assemble, prepare-features and run-campaign perform real future work.
The compile commands create plans/argv only. No operation is selected by default.
"""
import time
ORIGINAL_MONOTONIC = time.monotonic()
ORIGINAL_CPU = time.process_time()
import argparse
import json
from pathlib import Path
import sys

def require_fresh_bytecode_prefix():
    prefix = sys.pycache_prefix
    if type(prefix) is not str or not Path(prefix).is_absolute():
        raise ValueError('supply -X pycache_prefix=ABSOLUTE_FRESH_PATH with -B')
    path = Path(prefix)
    if (not sys.dont_write_bytecode or path.exists() or path.is_symlink()
            or '..' in path.parts or any(p.is_symlink() for p in path.parents)):
        raise ValueError('bytecode prefix must remain absent and source execution must use -B')

if __name__ == '__main__':
    require_fresh_bytecode_prefix()

# This reviewed entry and its sibling adapter source are the selected executable.
# The original S8 runtime is separately authenticated before any runtime import.
sys.path.insert(0, str(Path(__file__).absolute().parent))
from source_closure import MANIFEST, absolute, capture_runtime, need, parse, read_exact
from preparation import Session, exact_keys

OPERATIONS = ('stage', 'assemble', 'compile-feature-plan', 'prepare-features',
              'compile-campaign', 'run-campaign')


def perform(session, operation, spec):
    need(operation in OPERATIONS, 'explicit closed operator operation')
    if operation == 'stage':
        return session.stage(spec)
    if operation == 'assemble':
        return session.assemble(spec)
    if operation in ('compile-feature-plan', 'prepare-features'):
        return session.compile_plan('prepare-features', spec, execute=operation == 'prepare-features')
    return session.compile_plan('run', spec, execute=operation == 'run-campaign')


def main(argv=None):
    require_fresh_bytecode_prefix()
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-bytes', required=True, type=int)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args(argv)
    initial = 0
    def charge(n):
        nonlocal initial
        need(initial + n <= 1048577, 'bounded initial operator request')
        initial += n
    raw = read_exact(absolute(args.request), {'bytes': args.request_bytes, 'sha256': args.request_sha256}, 1048576, charge)
    request = parse(raw)
    exact_keys(request, ('schema', 'operation', 'runtime_root', 'operator_root', 'output', 'python', 'limits', 'stream_cap', 'spec'))
    need(request['schema'] == 'neural055-operator-request-v1' and request['operation'] in OPERATIONS, 'closed operator request')
    limits = request['limits']
    exact_keys(limits, ('wall_seconds', 'cpu_seconds', 'read_bytes', 'write_bytes', 'live_bytes', 'files', 'model_calls', 'stream_bytes'))
    need(type(limits['read_bytes']) is int and limits['read_bytes'] > initial, 'explicit complete bootstrap read budget')
    context, source_reads = capture_runtime(request['runtime_root'], MANIFEST, limits['read_bytes'] - initial)
    session = Session(context, request['runtime_root'], request['operator_root'], request['output'], request['python'],
                      limits, ORIGINAL_MONOTONIC, ORIGINAL_CPU, bootstrap_reads=initial + source_reads,
                      stream_cap=request['stream_cap'])
    result = None; first = None; terminal = None
    try:
        result = perform(session, request['operation'], request['spec'])
        session.budget.check('after complete operator operation')
    except BaseException as error:
        first = error
    try:
        terminal = session.finish(result, first)
    except BaseException as error:
        if first is None:
            first = error
        else:
            first.add_note('Operator terminal finalization also failed; partial owned state is retained.')
    if first is not None:
        raise first
    print(json.dumps({'status': terminal['status'], 'operation': request['operation'],
                      'terminal': str(Path(request['output']) / 'TERMINAL.json'),
                      'scientific_qualification_claimed': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
