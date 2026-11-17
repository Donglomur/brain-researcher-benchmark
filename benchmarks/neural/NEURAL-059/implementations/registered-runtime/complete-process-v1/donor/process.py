"""Actual original-process observation; original objects survive publication failures."""
import os
import selectors
import signal
import subprocess
import time
from .common import FailureCarrier, require, pin,diagnostic_type

class ObservedFailure(Exception):
    def __init__(self,observation):
        self.observation=observation
        super().__init__('original process failed or custody unavailable')

class Observation:
    def __init__(self,ident,argv,origin,deadline):
        self.id=ident;self.argv=list(argv);self.origin=origin;self.deadline=deadline
        self.pid=None;self.returncode=None;self.natural=False;self.reaped=False;self.group_absent=False
        self.stdout=bytearray();self.stderr=bytearray();self.cpu_seconds=None;self.end=None
        self.errors=FailureCarrier();self.published=False;self.publication=None
        self.owned_streams=[];self.stream_closure=[];self.owned_selector=None;self.selector_closed=None
    def document(self):
        return dict(id=self.id,argv=self.argv,origin=self.origin,deadline=self.deadline,pid=self.pid,
                    returncode=self.returncode,natural=self.natural,reaped=self.reaped,group_absent=self.group_absent,
                    stdout=pin(self.stdout),stderr=pin(self.stderr),cpu_seconds=self.cpu_seconds,end=self.end,
                    errors=self.errors.document(),published=self.published,publication=self.publication,
                    stream_closure=self.stream_closure,selector_closed=self.selector_closed)

def absent(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return True
    return False

class ProcessRunner:
    def __init__(self,budget,journal,carrier):
        self.budget=budget;self.journal=journal;self.carrier=carrier;self.originals=[]
    def run(self,ident,argv,deadline,stream_cap,kind='host_control',cwd=None,env=None,poll_service=None):
        origin=self.budget.clock();deadline=min(deadline,self.budget.deadline)
        obs=Observation(ident,argv,origin,deadline)
        self.originals.append(obs);self.carrier.retain(obs)
        proc=None;selector=None;forced=False;raw_status=None;usage=None
        def boundary(stage):self.budget.check(stage,deadline)
        try:
            self.budget.admit('before original launch',deadline)
            self.journal.json(ident+'-INTENT.json',{'id':ident,'argv':list(argv),'origin':origin,'deadline':deadline})
            boundary('after durable intent before dispatch')
            proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  start_new_session=True,bufsize=0,cwd=cwd,env=env)
            obs.owned_streams=[proc.stdout,proc.stderr];obs.pid=proc.pid
            selector=selectors.DefaultSelector();obs.owned_selector=selector;obs.selector_closed=False
            for name,stream in [('stdout',proc.stdout),('stderr',proc.stderr)]:
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
            while selector.get_map() or not obs.reaped:
                boundary('before original observation poll')
                if poll_service is not None:
                    poll_service(deadline)
                    boundary('after original service poll')
                for key,_ in selector.select(min(.02,max(0,deadline-self.budget.clock()))):
                    try:chunk=os.read(key.fileobj.fileno(),65536)
                    except BlockingIOError:continue
                    if not chunk:selector.unregister(key.fileobj);continue
                    # Preserve every returned byte before any fallible accounting/check.
                    getattr(obs,key.data).extend(chunk)
                    self.budget.stream(len(chunk))
                    require(len(obs.stdout)+len(obs.stderr)<=stream_cap,'original received-stream cap')
                    boundary('after original stream return')
                if not obs.reaped:
                    pid,status,ru=os.wait4(proc.pid,os.WNOHANG)
                    if pid:
                        obs.reaped=True;raw_status=status;usage=ru
                        obs.returncode=os.waitstatus_to_exitcode(status);proc.returncode=obs.returncode
                        obs.cpu_seconds=ru.ru_utime+ru.ru_stime
                        obs.natural=True
                boundary('after original wait/sample')
            obs.group_absent=absent(proc.pid)
            require(obs.group_absent,'original group outlived leader')
            require(obs.returncode==0,'original nonzero exit')
        except BaseException as exc:
            obs.errors.fail(exc,'process');self.carrier.fail(exc,'process:'+ident)
        finally:
            if proc is not None:
                try:
                    if not absent(proc.pid):
                        forced=True;os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except BaseException as exc:obs.errors.fail(exc,'group-kill');self.carrier.fail(exc,'group-kill:'+ident)
                if not obs.reaped:
                    try:
                        # Original deadline covers waiting; no fresh cleanup allowance.
                        while self.budget.clock()<deadline:
                            pid,status,ru=os.wait4(proc.pid,os.WNOHANG)
                            if pid:
                                obs.reaped=True;raw_status=status;usage=ru;obs.returncode=os.waitstatus_to_exitcode(status)
                                proc.returncode=obs.returncode;obs.cpu_seconds=ru.ru_utime+ru.ru_stime;break
                            time.sleep(.005)
                    except BaseException as exc:obs.errors.fail(exc,'original-reap');self.carrier.fail(exc,'original-reap:'+ident)
                try:obs.group_absent=absent(proc.pid)
                except BaseException as exc:obs.errors.fail(exc,'group-final');self.carrier.fail(exc,'group-final:'+ident)
                for role,stream in zip(('stdout','stderr'),obs.owned_streams):
                    closure={'role':role,'closed':False};obs.stream_closure.append(closure)
                    try:stream.close();closure['closed']=True
                    except BaseException as exc:
                        obs.errors.fail(exc,'pipe-close');self.carrier.fail(exc,'pipe-close:'+ident)
                        closure['error_type']=diagnostic_type(exc)
                        self.budget.uncertain(ident+':'+role,'managed_descriptor_closure',exc)
            if selector is not None:
                try:selector.close();obs.selector_closed=True
                except BaseException as exc:
                    obs.errors.fail(exc,'selector-close');self.carrier.fail(exc,'selector-close:'+ident)
                    self.budget.uncertain(ident+':selector','managed_descriptor_closure',exc)
            obs.natural=obs.natural and not forced
            try:obs.end=self.budget.clock()
            except BaseException as exc:
                obs.errors.fail(exc,'final-clock');self.carrier.fail(exc,'final-clock:'+ident)
                self.budget.unknown.append({'operation':ident,'quantity':'wall_seconds'})
            try:
                # Final CPU from original wait is charged before admission, not last running sample.
                self.budget.physical(ident,{'kind':kind,'cpu_seconds':obs.cpu_seconds,'wall_seconds':None if obs.end is None else obs.end-origin,
                                           'returncode':obs.returncode,'natural':obs.natural,'reaped':obs.reaped,
                                           'group_absent':obs.group_absent,'stdout_bytes':len(obs.stdout),'stderr_bytes':len(obs.stderr)})
                boundary('after final CPU/closure')
                require(proc is not None and obs.reaped and obs.group_absent,'original closure established')
            except BaseException as exc:obs.errors.fail(exc,'final-cost-admission');self.carrier.fail(exc,'final-cost-admission:'+ident)
        try:
            self.journal.write(ident+'-stdout.txt',bytes(obs.stdout))
            self.journal.write(ident+'-stderr.txt',bytes(obs.stderr))
            obs.publication=self.journal.json(ident+'-PROCESS.json',obs.document());obs.published=True
            boundary('after original process publication')
        except BaseException as exc:
            obs.errors.fail(exc,'process-publication');self.carrier.fail(exc,'process-publication:'+ident)
        try:obs.end=self.budget.clock()
        except BaseException as exc:
            obs.errors.fail(exc,'post-publication-clock');self.carrier.fail(exc,'post-publication-clock:'+ident)
            self.budget.unknown.append({'operation':ident,'quantity':'whole_wall_seconds'})
        if obs.errors.first is not None or not obs.published:raise ObservedFailure(obs)
        return obs
