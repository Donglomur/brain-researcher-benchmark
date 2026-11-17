"""Explicit authentic execution of the recovered original causal controller.

This is not a source test. The original grant, allocation, receipts, three
original NPZs, native runtime and external whole-command supervision are required.
"""
import time
import signal

ORIGIN = time.monotonic()
if __name__ == '__main__':
    if signal.getitimer(signal.ITIMER_REAL) != (0., 0.):
        raise ValueError('Fresh source entrypoint timer')
    def startup_expired(*_):
        raise TimeoutError('Portable source preflight exceeded 60 seconds')
    signal.signal(signal.SIGALRM, startup_expired)
    signal.setitimer(signal.ITIMER_REAL, 60.)

import argparse
import os
from pathlib import Path
import sys
import types

HERE = Path(__file__).absolute().parent
recovery = types.ModuleType('_neural024_source_recovery')
recovery.__file__ = str(HERE / 'recovery.py')
exec(compile((HERE / 'recovery.py').read_bytes(), recovery.__file__, 'exec'), recovery.__dict__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('operator-root', 'review', 'program', 'method', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--other-reserve-bytes', required=True, type=int)
    args = parser.parse_args()
    recovery.need(sys.flags.isolated == 1, 'Use Python -I for selected source imports')
    remaining = ['--program', args.program, '--method', args.method, '--output', args.output,
                 '--other-reserve-bytes', str(args.other_reserve_bytes)]
    body, argv, environment = recovery.dispatch(args.operator_root, args.review, remaining)
    environment['NEURAL024_ORIGIN'] = repr(ORIGIN)
    os.environ.clear()
    os.environ.update(environment)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(argv[0]).parent))
    sys.argv = argv
    # Main source is the bytes authenticated above; imported source is the fresh
    # selected tree, with no extra Python/cache artifacts. Operator custody is
    # required throughout; this is not protection from a malicious host operator.
    scope = {'__name__': '_neural024_selected_original', '__file__': argv[0], '__package__': None}
    exec(compile(body, argv[0], 'exec'), scope)
    # The same ORIGIN includes all source startup in original START/END. Main
    # arms its unchanged720/780 envelope and refuses insufficient full phases.
    recovery.need(time.monotonic() < ORIGIN + 60, 'Complete source startup within original allowance')
    signal.setitimer(signal.ITIMER_REAL, 0)
    raise SystemExit(scope['main']())


if __name__ == '__main__':
    main()
