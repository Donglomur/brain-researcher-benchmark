"""Operator-owned JSON-lines broker for one context; no model/provider integration."""
import time
import argparse
from pathlib import Path
import signal
import sys


def main(origin):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 86400 or signal.getitimer(signal.ITIMER_REAL) != (0., 0.):
        raise ValueError('Explicit bounded duration and no inherited timer required')
    end = origin + args.seconds

    def tick():
        if time.monotonic() >= end:
            raise TimeoutError('Original broker deadline')

    def timeout(*_):
        raise TimeoutError('Original broker deadline')

    old = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, end - time.monotonic()))
    try:
        tick()
        import source
        from viewer import Session, ROW_BYTES, SESSION_BYTES
        b = source.load(); root = b.io.regular(args.view); output = b.io.regular(args.output)
        b.io.need(output.parent.is_dir() and not output.exists() and
                  not output.is_relative_to(root) and not output.is_relative_to(source.REPOSITORY),
                  'Fresh external operator result, outside view and source checkout')
        session = Session(root, args.context, bundle=b)

        def emit(value):
            tick(); sys.stdout.buffer.write(b.io.canonical(value)); sys.stdout.buffer.flush(); tick()

        emit(session.describe())
        while not session.closed:
            tick(); raw = sys.stdin.buffer.readline(ROW_BYTES + 1); tick()
            b.io.need(raw and raw.endswith(b'\n') and len(raw) <= ROW_BYTES,
                      'Complete bounded newline-terminated action; EOF is not a response')
            emit(session.act(raw))
        tick()
        result = session.result()
        pin = b.io.put(output, result, SESSION_BYTES)
        tick(); emit({'operator_result': pin, 'unscored': True, 'native_study_admission': 'unavailable'})
        tick()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    # External supervision still owns interpreter startup and observed final exit.
    tick()
