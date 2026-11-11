"""Owned stopped-child admission, bounded original streams, full descendant cleanup."""
import errno
import os
import selectors
import signal
import time
from .strict import require, digest, canonical_bytes
from .errors import DeadlineExceeded

def launch_observe(argv, keep_fds, cgroup, limits, clock, evidence, attempt):
    require(type(argv) is list and argv and all(type(x)is str and "\x00"not in x for x in argv),"argv")
    observation={"schema":"jaxley_original_process_observation_v1","attempt":attempt,
                 "argv":argv,"original_start_ns":clock.start_ns,"deadline_ns":clock.end_ns,
                 "cleanup_deadline_ns":clock.cleanup_end_ns,"status":"failed",
                 "root_exit":None,"root_wait_observed":False,"stdout_EOF":False,"stderr_EOF":False,
                 "owned_subtree_empty":False,"stdout_persisted":False,"stderr_persisted":False,
                 "source_execution":"no_child_started","auto_retry":False}
    pipes={};pid=None;buffers={"stdout":bytearray(),"stderr":bytearray()};issues=[]
    observed_bytes={"stdout":0,"stderr":0}
    selector=selectors.DefaultSelector()
    try:
        clock.check()
        for name in buffers:pipes[name]=os.pipe()
        pid=os.fork()
        if pid==0:
            try:
                os.setsid()
                null=os.open("/dev/null",os.O_RDONLY);os.dup2(null,0)
                if null>2:os.close(null)
                for name,dst in (("stdout",1),("stderr",2)):
                    os.dup2(pipes[name][1],dst)
                preserve={0,1,2,*keep_fds}
                for fd in keep_fds:os.set_inheritable(fd,True)
                maxfd=int(os.sysconf("SC_OPEN_MAX"))
                cursor=3
                for fd in sorted(x for x in preserve if x>=3):
                    if cursor<fd:os.closerange(cursor,fd)
                    cursor=fd+1
                os.closerange(cursor,maxfd)
                # No producer/bwrap instruction executes before cgroup admission.
                os.kill(os.getpid(),signal.SIGSTOP)
                os.execve(argv[0],argv,{"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"})
            except BaseException:
                os._exit(126)
        observation["root_pid"]=pid
        observation["source_execution"]="actual_os_child"
        for name,(readfd,writefd) in pipes.items():
            os.close(writefd);pipes[name]=(readfd,None)
            os.set_blocking(readfd,False);selector.register(readfd,selectors.EVENT_READ,name)
        stopped=False
        while not stopped:
            clock.check()
            got,status=os.waitpid(pid,os.WNOHANG|os.WUNTRACED)
            if got:
                if os.WIFSTOPPED(status):stopped=True
                else:
                    observation["root_wait_observed"]=True
                    observation["root_exit"]=os.waitstatus_to_exitcode(status)
                    raise RuntimeError("child ended before cgroup admission")
            else:time.sleep(min(.005,clock.remaining()))
        cgroup.write("cgroup.procs",str(pid))
        clock.check();os.kill(pid,signal.SIGCONT)
        observation["admitted_start_ns"]=time.monotonic_ns()
        while not observation["root_wait_observed"] or selector.get_map():
            clock.check()
            for key,_ in selector.select(min(.05,clock.remaining())):
                name=key.data
                try:b=os.read(key.fd,65536)
                except BlockingIOError:continue
                if not b:
                    observation[name+"_EOF"]=True;selector.unregister(key.fd);os.close(key.fd);pipes[name]=(None,None)
                else:
                    observed_bytes[name]+=len(b)
                    cap=limits[name+"_bytes"]
                    remaining=cap-len(buffers[name])
                    buffers[name].extend(b[:max(0,remaining)])
                    if len(b)>remaining:raise RuntimeError(name+" cap exceeded; captured prefix retained")
            if not observation["root_wait_observed"]:
                got,status=os.waitpid(pid,os.WNOHANG)
                if got:
                    observation["root_wait_observed"]=True
                    observation["root_exit"]=os.waitstatus_to_exitcode(status)
            observation["latest_resource_snapshot"]=cgroup.snapshot()
        require(observation["root_exit"]==0,"producer nonzero exit")
        require(not cgroup.populated(),"root ended with live descendants")
        observation["owned_subtree_empty"]=True
        clock.check()
        observation["status"]="complete"
    except BaseException as exc:
        issues.append({"type":type(exc).__name__,"message":str(exc)[:600]})
        observation["status"]="failed"
    finally:
        # Descendant cleanup is independent of root wait and stream EOF.
        try:
            if cgroup.populated(True):cgroup.kill()
        except BaseException as exc:issues.append({"cleanup":"cgroup_kill","type":type(exc).__name__})
        if pid is not None and not observation["root_wait_observed"]:
            try:os.killpg(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as exc:issues.append({"cleanup":"killpg","type":type(exc).__name__})
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as exc:issues.append({"cleanup":"kill_root","type":type(exc).__name__})
        try:
            while pid is not None and (not observation["root_wait_observed"] or selector.get_map() or cgroup.populated(True)):
                clock.check(True)
                for key,_ in selector.select(min(.02,clock.remaining(True))):
                    name=key.data
                    try:b=os.read(key.fd,65536)
                    except BlockingIOError:continue
                    if not b:
                        observation[name+"_EOF"]=True;selector.unregister(key.fd);os.close(key.fd);pipes[name]=(None,None)
                    else:
                        observed_bytes[name]+=len(b)
                        room=max(0,limits[name+"_bytes"]-len(buffers[name]));buffers[name].extend(b[:room])
                        if len(b)>room:issues.append({"cleanup":name,"overflow":True})
                if not observation["root_wait_observed"]:
                    got,status=os.waitpid(pid,os.WNOHANG)
                    if got:
                        observation["root_wait_observed"]=True
                        observation["root_exit"]=os.waitstatus_to_exitcode(status)
            observation["owned_subtree_empty"]=not cgroup.populated(True)
            observation["final_resource_snapshot"]=cgroup.snapshot(True)
        except BaseException as exc:issues.append({"cleanup":"terminal_observation","type":type(exc).__name__})
        for name,(r,w) in pipes.items():
            for fd in (r,w):
                if fd is not None:
                    try:os.close(fd)
                    except OSError:pass
        selector.close()
        # Both streams are attempted even if one evidence publication fails.
        for name,body in buffers.items():
            raw=bytes(body);observation[name+"_bytes"]=len(raw);observation[name+"_sha256"]=digest(raw)
            try:
                row=evidence.write_new(attempt+"."+name+".txt",raw,limits[name+"_bytes"],clock=clock,cleanup=True)
                observation[name+"_record"]=row;observation[name+"_persisted"]=True
            except BaseException as exc:issues.append({"persistence":name,"type":type(exc).__name__})
        observation["issues"]=issues
        observation["observed_stream_bytes"]=observed_bytes
        observation["stream_discarded_bytes"]={k:observed_bytes[k]-len(buffers[k]) for k in buffers}
        if issues or not all(observation[x] for x in ("root_wait_observed","stdout_EOF","stderr_EOF","owned_subtree_empty","stdout_persisted","stderr_persisted")):
            observation["status"]="failed"
        observation["observed_end_ns"]=time.monotonic_ns()
        try:
            clock.check(True)
            row=evidence.write_new(attempt+".observation.json",canonical_bytes(observation),2*1024*1024,clock=clock,cleanup=True)
            observation["observation_record"]=row
        except BaseException as exc:
            observation["status"]="failed";observation["observation_evidence_lost"]=type(exc).__name__
        # Return metadata only; raw private stream bytes stay in the admitted custody.
    return observation

