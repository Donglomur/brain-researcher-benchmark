"""Template executed by qualified Python -I -S -B -c; not a standalone launcher.

Root freezes the placeholders into ROOT_COMMAND.json and authenticates that
command before execution. The executing outer source is captured and hashed
before compile under the same original clock used by the worker and observer.
"""
import time
_launch_origin=time.monotonic()
import signal
_launch_previous={n:signal.getsignal(n) for n in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM)}
if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('fresh launch timer')
def _launch_expired(*_):raise TimeoutError('original source-capture startup clock')
signal.signal(signal.SIGALRM,_launch_expired)
signal.setitimer(signal.ITIMER_REAL,max(.001,_launch_origin+120-time.monotonic()))
try:
    import hashlib
    import os
    from pathlib import Path
    import stat
    import sys
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise RuntimeError('qualified isolated no-site bytecode-free launcher')
    _launch_path=Path('__RUN_PATH__')
    _launch_expected={'bytes':__RUN_BYTES__,'sha256':'__RUN_SHA256__'}
    if not _launch_path.is_absolute() or any(p.is_symlink() for p in (_launch_path,*_launch_path.parents)):raise RuntimeError('ordinary outer source path')
    _fd=os.open(_launch_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        _a=os.fstat(_fd)
        if not stat.S_ISREG(_a.st_mode) or _a.st_nlink!=1 or _a.st_size!=_launch_expected['bytes'] or _a.st_size>65536:raise RuntimeError('exact bounded outer source')
        _raw=os.read(_fd,_a.st_size+1);_b=os.fstat(_fd);_n=_launch_path.lstat()
        _sig=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
        if _sig(_a)!=_sig(_b) or _sig(_a)!=_sig(_n) or len(_raw)!=_a.st_size or hashlib.sha256(_raw).hexdigest()!=_launch_expected['sha256']:raise RuntimeError('changed executing outer source')
    finally:os.close(_fd)
    if time.monotonic()>=_launch_origin+120:raise TimeoutError('original source-capture deadline')
    _globals={'__name__':'__main__','__file__':str(_launch_path),'_CAPTURED_LAUNCH_ORIGIN':_launch_origin,'_CAPTURED_LAUNCH_ALARM':_launch_expired,'_CAPTURED_LAUNCH_HANDLERS':_launch_previous,'_EARLY_SOURCE_READ_CHARGE':len(_raw)+1}
    exec(compile(_raw,str(_launch_path),'exec'),_globals)
finally:
    _failures=[]
    for _action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda n=n,h=h:signal.signal(n,h) for n,h in _launch_previous.items()]:
        try:_action()
        except BaseException as _error:_failures.append(type(_error).__name__)
    if _failures:raise RuntimeError('independent launch alarm cleanup uncertainty:'+','.join(_failures))
