"""NEURAL039 compatible child observer; explicit cleanup safety successor."""
import os,signal,subprocess,selectors,time
PIPE_CAP=65536
def need(v,m):
    if not v:raise ValueError(m)
class ChildFailure(RuntimeError):
    def __init__(self,record):super().__init__('Executor child failed');self.record=record

def group_absent(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return True
    return False

def child(argv,end,env):
    """Stream from launch, then reap on every setup/read/timeout failure.

Only this process group is signalled. Docker client/container recovery remains
unqualified if the reviewed executor is forcibly terminated before closure.
"""
    p=None;sel=None;buf={'out':bytearray(),'err':bytearray()};record={'natural_exit':False,'process_reaped':False,'timed_out':False,'exit_code':None,'kill_sent':False,'error_type':None,'process_group_absent':False,'timer_disable_error':None,'timer_restore_error':None};start=time.monotonic()
    try:
        need(end-start>5,'Child deadline and reap reserve')
        need(start<end-40,'Child positive normal interval')
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
        need(group_absent(p.pid),'Executor owned group absent after natural exit')
    except BaseException as e:
        record['error_type']=type(e).__name__
        if isinstance(e,(TimeoutError,subprocess.TimeoutExpired)):record['timed_out']=True
    finally:
        # Cancel the enclosing alarm only during bounded emergency reaping.
        # Timer failures are refusals, but must not skip owned-child cleanup.
        cleanup_start=time.monotonic();previous_alarm=(0.,0.)
        try:
            try:previous_alarm=signal.setitimer(signal.ITIMER_REAL,0)
            except BaseException as e:
                record['timer_disable_error']=type(e).__name__
                if record['error_type'] is None:record['error_type']=type(e).__name__
                record['timed_out']=record['timed_out'] or isinstance(e,(TimeoutError,subprocess.TimeoutExpired))
            if p is not None:
                try:absent=group_absent(p.pid)
                except BaseException:absent=False
                if not record['process_reaped'] or not absent:
                    if not record['process_reaped']:
                        try:
                            # Preserve the executor's original SIGALRM grace.
                            os.kill(p.pid,signal.SIGALRM)
                            wait=max(.001,min(35,end-time.monotonic()-5))
                            record['exit_code']=p.wait(timeout=wait);record['process_reaped']=True
                        except ProcessLookupError:
                            try:record['exit_code']=p.wait(timeout=max(.001,min(5,end-time.monotonic())));record['process_reaped']=True
                            except BaseException:pass
                        except BaseException:pass
                    try:absent=group_absent(p.pid)
                    except BaseException:absent=False
                    if not record['process_reaped'] or not absent:
                        try:os.killpg(p.pid,signal.SIGKILL);record['kill_sent']=True
                        except ProcessLookupError:pass
                        except BaseException:pass
                        if not record['process_reaped']:
                            try:record['exit_code']=p.wait(timeout=max(.001,min(5,end-time.monotonic())));record['process_reaped']=True
                            except BaseException:pass
                try:record['process_group_absent']=group_absent(p.pid)
                except BaseException:record['process_group_absent']=False
        finally:
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
            if previous_alarm[0]>0:
                try:signal.setitimer(signal.ITIMER_REAL,max(.001,previous_alarm[0]-(time.monotonic()-cleanup_start)))
                except BaseException as e:
                    record['timer_restore_error']=type(e).__name__
                    if record['error_type'] is None:record['error_type']=type(e).__name__
                    record['timed_out']=record['timed_out'] or isinstance(e,(TimeoutError,subprocess.TimeoutExpired))
    if not time.monotonic()<end:
        if record['error_type'] is None:record['error_type']='TimeoutError'
        record['timed_out']=True
    if record['error_type'] is not None or not(record['natural_exit'] and record['process_reaped'] and record['process_group_absent'] and record['streams_closed'] and record['exit_code']==0):raise ChildFailure(record)
    return bytes(buf['out']),record
