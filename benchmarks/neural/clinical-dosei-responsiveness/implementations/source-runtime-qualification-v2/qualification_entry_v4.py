"""One admitted generated Docker qualification; no fallback or automatic retry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
GUARD_SHA256 = 'a7312c92983f55103511e9712d0487fb128ea2f30aca040e0eeeed95be48c5f2'
OPERATION_SECONDS = 480
CLEANUP_SECONDS = 570


def bootstrap(args):
    path = HERE/'qualification_guard_v4.py'
    if path.parent.resolve() != path.parent: raise ValueError('guard source parent changed')
    fd = os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        keys = ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')
        signature = lambda item:tuple(getattr(item,key) for key in keys)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 65536:
            raise ValueError('bounded guard bootstrap source required')
        raw = os.read(fd,65537)
        if len(raw) != before.st_size or signature(before) != signature(os.fstat(fd)) or \
                signature(before) != signature(path.lstat()) or hashlib.sha256(raw).hexdigest() != GUARD_SHA256:
            raise ValueError('pinned guard bootstrap changed')
    finally: os.close(fd)
    args.bootstrap_guard_sha256 = GUARD_SHA256; args.bootstrap_guard_read_bytes = len(raw)
    module = types.ModuleType('dosei_native_qualification_guard'); module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','approval-id','native-run-id'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args(); args.started = time.monotonic()
    context = None; cancelled = False
    def interrupt(signum, frame):
        nonlocal cancelled
        elapsed = time.monotonic()-args.started
        cancelled = True
        if context is not None: context.cancelled = True
        if signum == signal.SIGXCPU:
            # The worker's hard60 cap remains; only cleanup gets a later soft
            # ceiling. This is not a new unbounded CPU grant.
            resource.setrlimit(resource.RLIMIT_CPU,(55,60))
            signal.signal(signal.SIGXCPU,signal.SIG_DFL)
        remaining = CLEANUP_SECONDS-elapsed
        signal.setitimer(signal.ITIMER_REAL,max(.001,remaining) if remaining > 0 else 0)
        raise TimeoutError('qualification operation cancelled; cleanup only')
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM,signal.SIGXCPU):
        signal.signal(sig,interrupt)
    signal.setitimer(signal.ITIMER_REAL,OPERATION_SECONDS)
    code = 1; result = None
    try:
        guard = bootstrap(args)
        context = guard.Context(args)
        context.cancelled = cancelled
        result = context.modules['driver'].run_qualification(context)
        if not (type(result) is dict and result.get('status') == 'succeeded' and result.get('failure') is None
                and type(result.get('report')) is dict and set(result['report']) == {'bytes','sha256'}
                and type(result['report']['bytes']) is int and 0 < result['report']['bytes'] <= 65536
                and type(result['report']['sha256']) is str and len(result['report']['sha256']) == 64
                and all(c in '0123456789abcdef' for c in result['report']['sha256']) and not context.cancelled):
            raise ValueError('complete fixed qualification result required')
        code = 0
        print(json.dumps({'schema':'dosei_native_qualification_entry_v1','complete':True,
                          'native_run_id':args.native_run_id,'report':result.get('report'),
                          'scope':'generated controls only; no model or authentic input'},sort_keys=True),flush=True)
    except BaseException as error:
        if result is None: result = getattr(error,'qualification_summary',None)
        print(json.dumps({'schema':'dosei_native_qualification_entry_v1','complete':False,
                          'failure_type':type(error).__name__,
                          'failure_message':str(error)[:512],
                          'cost_and_cleanup':'use saved driver receipt; absent receipt means unknown/frozen bounds'}),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        if type(result) is dict:
            summary = json.dumps({'schema':'dosei_native_qualification_returned_cost_v1','summary':result},
                                 sort_keys=True,separators=(',',':'),allow_nan=False)
            if len(summary.encode('ascii')) <= 16384:
                print(summary,flush=True)
            else:
                print('{"schema":"dosei_native_qualification_cost_overflow_v1","complete":false}',flush=True)
                code = 1
        if context is not None:
            print(json.dumps({'schema':'dosei_native_qualification_operational_receipt_v1',
                              **context.operational_receipt()},sort_keys=True),flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
