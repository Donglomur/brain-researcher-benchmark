"""NEURAL067 control CLI capture, narrowly derived from repaired NEURAL032."""
import os,selectors,signal,subprocess,time
from .io_guard import need

def bounded_call(binary,env,args,deadline,cap):
    """Bound capture before append; successful return requires closed client resources."""
    need(type(cap)is int and 0<cap<=131072,'Bounded Docker capture cap')
    need(deadline-time.monotonic()>0,'Docker client deadline')
    sel=None;failure=None;result=None;cleanup_errors=[]
    p=subprocess.Popen([binary,*args],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    try:
        sel=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()};total=0
        for key,f in [('stdout',p.stdout),('stderr',p.stderr)]:
            os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,key)
        while sel.get_map():
            left=deadline-time.monotonic();need(left>0,'Bounded Docker client time')
            for key,_ in sel.select(min(.05,left)):
                try:b=os.read(key.fileobj.fileno(),min(32768,cap-total+1))
                except BlockingIOError:continue
                if not b:sel.unregister(key.fileobj);continue
                need(total+len(b)<=cap,'Preventive Docker total stream cap')
                buffers[key.data].extend(b);total+=len(b)
        rc=p.wait(timeout=max(.001,deadline-time.monotonic()))
        need(type(rc)is int and time.monotonic()<deadline,'Docker wait finished within deadline')
        result=subprocess.CompletedProcess(args,rc,bytes(buffers['stdout']),bytes(buffers['stderr']))
    except BaseException as error:failure=error
    finally:
        # Every cleanup operation is independent, including setup and close failures.
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        except BaseException as error:cleanup_errors.append(('group_kill',type(error).__name__))
        try:
            reaped=p.wait(timeout=max(.001,min(1,deadline-time.monotonic())))
            need(type(reaped)is int,'Client reap must be observed')
        except BaseException as error:cleanup_errors.append(('reap',type(error).__name__))
        try:
            os.killpg(p.pid,0)
            cleanup_errors.append(('group_absence','StillPresent'))
        except ProcessLookupError:pass
        except BaseException as error:cleanup_errors.append(('group_absence',type(error).__name__))
        if sel is not None:
            try:sel.close()
            except BaseException as error:cleanup_errors.append(('selector_close',type(error).__name__))
        for name,stream in [('stdout',p.stdout),('stderr',p.stderr)]:
            if stream is not None:
                try:
                    stream.close()
                    need(stream.closed is True,'Closed client pipe must be observed')
                except BaseException as error:cleanup_errors.append((name+'_close',type(error).__name__))
    if cleanup_errors:raise RuntimeError('Unconfirmed Docker client closure: '+repr(cleanup_errors))from failure
    need(time.monotonic()<deadline,'Docker client cleanup finished within deadline')
    if failure is not None:raise failure
    return result
