"""Exact bounded child observation from reviewed SliceTCA supervisor."""
import os,signal,subprocess,selectors,time
PIPE_CAP=65536
def need(v,m):
    if not v:raise ValueError(m)
class ChildFailure(RuntimeError):
    def __init__(self,record):super().__init__('Executor child failed');self.record=record

def child(argv,end,env):
    """Stream from launch, then reap on every setup/read/timeout failure.

Only this process group is signalled. Docker client/container recovery remains
unqualified if the reviewed executor is forcibly terminated before closure.
"""
    p=None;sel=None;buf={'out':bytearray(),'err':bytearray()};record={'natural_exit':False,'process_reaped':False,'timed_out':False,'exit_code':None,'kill_sent':False,'error_type':None};start=time.monotonic()
    try:
        need(end-start>5,'Child deadline and reap reserve')
        p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,bufsize=0,start_new_session=True)
        record['pid']=p.pid
        sel=selectors.DefaultSelector()
        for k,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,k)
        while sel.get_map():
            left=end-time.monotonic()-40
            if left<=0:record['timed_out']=True;raise TimeoutError('Executor duration')
            for key,_ in sel.select(min(left,.1)):
                try:b=os.read(key.fileobj.fileno(),min(8192,PIPE_CAP+1-sum(map(len,buf.values()))))
                except BlockingIOError:continue
                if not b:sel.unregister(key.fileobj);continue
                need(sum(map(len,buf.values()))+len(b)<=PIPE_CAP,'Executor stream cap');buf[key.data].extend(b)
        left=end-time.monotonic()-40
        if left<=0:record['timed_out']=True;raise TimeoutError('Executor exit deadline')
        record['exit_code']=p.wait(timeout=left);record['process_reaped']=True;record['natural_exit']=True
        need(record['exit_code']==0,'Executor natural zero exit')
    except BaseException as e:
        record['error_type']=type(e).__name__
        if isinstance(e,(TimeoutError,subprocess.TimeoutExpired)):record['timed_out']=True
    finally:
        # Cancel the enclosing alarm only during bounded emergency reaping.
        # Its elapsed-time admission is checked again before any publication.
        cleanup_start=time.monotonic();previous_alarm=signal.setitimer(signal.ITIMER_REAL,0)
        if p is not None and not record['process_reaped']:
            try:
                # Give the executor's SIGALRM handler a chance to close Docker.
                os.kill(p.pid,signal.SIGALRM)
                wait=max(.001,min(35,end-time.monotonic()-5))
                record['exit_code']=p.wait(timeout=wait);record['process_reaped']=True
            except ProcessLookupError:
                try:record['exit_code']=p.wait(timeout=max(.001,min(5,end-time.monotonic())));record['process_reaped']=True
                except BaseException:pass
            except BaseException:pass
            if not record['process_reaped']:
                try:os.killpg(p.pid,signal.SIGKILL);record['kill_sent']=True
                except ProcessLookupError:pass
                except BaseException:pass
                try:record['exit_code']=p.wait(timeout=max(.001,min(5,end-time.monotonic())));record['process_reaped']=True
                except BaseException:pass
        close_ok=True
        if sel is not None:
            try:sel.close()
            except BaseException:close_ok=False
        if p is not None:
            for f in (p.stdout,p.stderr):
                if f is not None:
                    try:f.close()
                    except BaseException:close_ok=False
        record.update(streams_closed=close_ok,stdout_bytes=len(buf['out']),stderr_bytes=len(buf['err']),seconds=time.monotonic()-start)
        if previous_alarm[0]>0:signal.setitimer(signal.ITIMER_REAL,max(.001,previous_alarm[0]-(time.monotonic()-cleanup_start)))
    if record['error_type'] is not None or not(record['natural_exit'] and record['process_reaped'] and record['streams_closed'] and record['exit_code']==0):raise ChildFailure(record)
    need(time.monotonic()<end,'Child whole bound')
    return bytes(buf['out']),record
