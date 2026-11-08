"""Adapted reviewed capped Docker CLI primitives; no task-specific phase execution."""
import hashlib,json,os,re,selectors,signal,stat,subprocess,time
from pathlib import Path
def need(ok,msg):
    if not ok:raise ValueError(msg)


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))


def path(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'Unlinked canonical path')
    need(not any(c in str(p) for c in ',\n\r\0'),'Unambiguous mount path');return p


class CommandError(RuntimeError):pass


class Docker:
    """Streaming-capped CLI, no attachment to candidate stdout or log retrieval."""
    def __init__(self,binary,socket,budget):
        self.budget=budget;self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        start=time.monotonic();need(end-start>1,'Command deadline')
        p=None;s=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None;materialized=0
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            p=subprocess.Popen(self.prefix+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    materialized+=len(raw);self.budget.reading(len(raw))
                    if not raw:s.unregister(k.fileobj);continue
                    need(sum(map(len,bufs.values()))+len(raw)<=cap,'Streaming CLI cap');bufs[k.data].extend(raw)
            rc=p.wait(timeout=max(.01,end-time.monotonic()));child_reaped=True
            need(rc==0,'Docker command failure')
            try:os.killpg(p.pid,0)
            except ProcessLookupError:group_absent=True
            else:
                survivor_observed=True
                raise CommandError('Owned CLI group survives leader exit')
            need(time.monotonic()<end,'CLI group observation before original deadline')
            return bytes(bufs['out'])
        except BaseException as e:
            error=type(e).__name__;raise
        finally:
            # One shared cleanup interval, never a new per-descendant allowance.
            cleanup_end=min(end,time.monotonic()+1)
            if p is not None and not group_absent:
                live=False
                try:os.killpg(p.pid,0);live=True
                except ProcessLookupError:group_absent=True
                except BaseException as e:cleanup_ok=False;group_error=type(e).__name__
                if live:
                    try:os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError:group_absent=True
                    except BaseException as e:cleanup_ok=False;group_error=type(e).__name__
            if p is not None and not child_reaped:
                try:rc=p.wait(timeout=max(0,cleanup_end-time.monotonic()));child_reaped=True
                except BaseException:cleanup_ok=False
            if p is not None and not group_absent:
                while True:
                    try:os.killpg(p.pid,0)
                    except ProcessLookupError:group_absent=True;break
                    except BaseException as e:cleanup_ok=False;group_error=type(e).__name__;break
                    left=cleanup_end-time.monotonic()
                    if left<=0:break
                    time.sleep(min(.01,left))
            if p is not None and not group_absent:cleanup_ok=False
            if s is not None:
                try:s.close()
                except BaseException:cleanup_ok=False
            if p is not None:
                for stream in (p.stdout,p.stderr):
                    if stream is not None:
                        try:stream.close()
                        except BaseException:cleanup_ok=False
            cleanup_in_time=time.monotonic()<cleanup_end
            cleanup_ok=cleanup_ok and cleanup_in_time
            self.reaped=previous_reaped and child_reaped and cleanup_ok and group_absent
            self.records.append({'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'materialized_pipe_bytes':materialized,'seconds':time.monotonic()-start,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok,'cleanup_before_original_cutoff':cleanup_in_time,'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,'group_probe_or_cleanup_error':group_error})
            if time.monotonic()>=cleanup_end:
                cleanup_ok=False;self.reaped=False
                self.records[-1]['cleanup_complete']=False;self.records[-1]['cleanup_before_original_cutoff']=False
            if not cleanup_ok and error is None:raise CommandError('CLI cleanup incomplete')


def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)


