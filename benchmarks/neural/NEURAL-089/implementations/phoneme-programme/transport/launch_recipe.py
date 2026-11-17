"""Construct a reviewed captured-entry command; this function never launches it."""
import json
from pathlib import Path

CODE='''import time
_launch_origin=time.monotonic()
import signal
_launch_previous={n:signal.getsignal(n) for n in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM)}
if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('fresh launch timer')
def _launch_expired(*_):raise TimeoutError('original source-capture startup clock')
for _n in _launch_previous:signal.signal(_n,_launch_expired)
signal.setitimer(signal.ITIMER_REAL,max(.001,_launch_origin+120-time.monotonic()))
try:
    import hashlib,os,stat,sys
    from pathlib import Path
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise RuntimeError('isolated no-site bytecode-free launch')
    _path=Path(@PATH@);_expected=@PIN@
    if not _path.is_absolute() or any(p.is_symlink() for p in (_path,*_path.parents)):raise RuntimeError('ordinary executing outer source')
    _fd=os.open(_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        _a=os.fstat(_fd)
        if not stat.S_ISREG(_a.st_mode) or _a.st_nlink!=1 or _a.st_size!=_expected['bytes'] or _a.st_size>65536:raise RuntimeError('bounded exact outer source')
        _raw=os.read(_fd,_a.st_size+1);_b=os.fstat(_fd);_n=_path.lstat()
        _stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
        if _stamp(_a)!=_stamp(_b) or _stamp(_a)!=_stamp(_n) or len(_raw)!=_a.st_size or hashlib.sha256(_raw).hexdigest()!=_expected['sha256']:raise RuntimeError('changed executing outer source')
    finally:os.close(_fd)
    if time.monotonic()>=_launch_origin+120:raise TimeoutError('original source-capture deadline')
    _globals={'__name__':'__main__','__file__':str(_path),'_CAPTURED_LAUNCH_ORIGIN':_launch_origin,'_CAPTURED_OUTER_PIN':_expected,'_EARLY_SOURCE_READ_CHARGE':len(_raw)+1}
    exec(compile(_raw,str(_path),'exec'),_globals)
finally:
    _failures=[]
    for _action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda n=n,h=h:signal.signal(n,h) for n,h in _launch_previous.items()]:
        try:_action()
        except BaseException as _error:_failures.append(type(_error).__name__)
    if _failures:raise RuntimeError('launch signal cleanup uncertainty:'+','.join(_failures))
'''

def recipe(path,pin):
    p=Path(path)
    if not p.is_absolute() or str(p)!=str(path):raise ValueError('exact absolute outer path')
    if type(pin)is not dict or set(pin)!={'bytes','sha256'} or type(pin['bytes'])is not int or not 0<pin['bytes']<=65536:raise ValueError('exact outer pin')
    if type(pin['sha256'])is not str or len(pin['sha256'])!=64 or any(c not in '0123456789abcdef' for c in pin['sha256']):raise ValueError('exact outer digest')
    code=CODE.replace('@PATH@',repr(str(p))).replace('@PIN@',repr(pin))
    return dict(schema='neural089_captured_root_command_proposal_v1',source_only=True,selected=False,executing_outer_source=dict(path=str(p),**pin),early_alarm_seconds=120,original_origin_shared=True,
                argv_template=['<qualified_Python>','-I','-S','-B','-c',code,'--source-pin','<exact_runtime_manifest_pin_JSON>','--selection','<reviewed_selection_path>','--selection-pin','<exact_selection_pin_JSON>','--external-output','<fresh_external_receipt>'],
                requires_root_source_pin_and_separate_operation_authority=True,actual_inputs_opened=False,native_scientific_calls=0)
