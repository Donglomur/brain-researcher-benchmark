"""Pinned shared native ledger controller with finite support CPU allowance."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import types

CONTROLLER = Path('/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2/resource_control.py')
CONTROLLER_SHA256 = 'a99a83ae6638dbae205badf041230260d4d075dfc3b7e50a50c7bdb87293b761'
SOFT_CPU_SECONDS = 20
CLEANUP_CPU_SECONDS = 22


def cpu_limit(signum, frame):
    _,hard = resource.getrlimit(resource.RLIMIT_CPU)
    signal.signal(signal.SIGXCPU,signal.SIG_DFL)
    resource.setrlimit(resource.RLIMIT_CPU,(CLEANUP_CPU_SECONDS,hard))
    raise KeyboardInterrupt('native coordinator CPU limit')


def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'native-run':
        raise ValueError('only the fixed native-run controller action is allowed')
    _,hard = resource.getrlimit(resource.RLIMIT_CPU)
    if hard != resource.RLIM_INFINITY and hard < 60:
        raise ValueError('inherited hard CPU ceiling cannot admit the fixed60-second worker cap')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    signal.signal(signal.SIGXCPU,cpu_limit)
    resource.setrlimit(resource.RLIMIT_CPU,(SOFT_CPU_SECONDS,hard))
    if CONTROLLER.parent.resolve() != CONTROLLER.parent: raise ValueError('native controller parent changed')
    fd = os.open(CONTROLLER,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        before = os.fstat(fd); keys = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        signature = lambda item:tuple(getattr(item,key) for key in keys)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 65536: raise ValueError('bounded native controller required')
        raw = os.read(fd,65537)
        if len(raw) != before.st_size or signature(before) != signature(os.fstat(fd)) or \
                signature(before) != signature(CONTROLLER.lstat()) or hashlib.sha256(raw).hexdigest() != CONTROLLER_SHA256:
            raise ValueError('native controller source identity changed')
    finally:os.close(fd)
    module = types.ModuleType('dosei_qualification_resource_controller');module.__file__ = str(CONTROLLER)
    exec(compile(raw,str(CONTROLLER),'exec'),module.__dict__)
    try:return module.main(sys.argv[1:])
    finally:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        print(json.dumps({'schema':'dosei_qualification_controller_cpu_receipt_v1',
            'controller_sha256':CONTROLLER_SHA256,'source_bytes':len(raw),'coordinator_pid':os.getpid(),
            'cpu_user_seconds':usage.ru_utime,'cpu_system_seconds':usage.ru_stime,
            'soft_CPU_seconds':SOFT_CPU_SECONDS,'cleanup_soft_CPU_seconds':CLEANUP_CPU_SECONDS,
            'missing_receipt_requires_frozen_unknown_charge':True},sort_keys=True),file=sys.stderr,flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
