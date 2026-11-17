"""FIND032 captured GCaMP8 CLI and exact resource retirement primitives.

Only Docker.last_original retention and its description differ from the selected
donor definitions. No programme, model, data or container executes on import.
"""
import hashlib,json,os,re,selectors,signal,stat,subprocess,time
from pathlib import Path
LABEL='org.neurobench.slicetca-program-owner'

def need(ok,msg):
    if not ok:raise ValueError(msg)

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
    """Streaming-capped CLI; callers retain each strong original before next call."""
    def __init__(self,binary,socket):
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.last_original=None
        # GCaMP8's aborting case has one failing command plus at most six
        # independent retirement commands. Recovery has at most six failures.
        self.original_failures=[];self.failure_bound_refusal=None
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        if len(self.original_failures)>=7:
            if self.failure_bound_refusal is None:
                self.failure_bound_refusal=CommandError('GCaMP8 original failure bound; no further command started')
            raise self.failure_bound_refusal
        start=time.monotonic()
        p=None;s=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None
        original=None;secondary=[];original_result=None;wait_returns=[]
        eof={'out':False,'err':False};command=tuple(self.prefix+args)
        failure={'exception':None,'rawstdout':bufs['out'],'rawstderr':bufs['err'],
                 'record':None,'secondary_exceptions':secondary,'command':command,
                 'original_result':None,'wait_returns':wait_returns,'eof':eof}
        failure_retained=False
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            need(end-start>1,'Command deadline')
            p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    if not raw:eof[k.data]=True;s.unregister(k.fileobj);continue
                    # Preserve the actual overflow byte before admission fails.
                    bufs[k.data].extend(raw)
                    need(sum(map(len,bufs.values()))<=cap,'Streaming CLI cap')
            rc=p.wait(timeout=max(.01,end-time.monotonic()));wait_returns.append(rc);child_reaped=True
            need(rc==0,'Docker command failure')
            try:os.killpg(p.pid,0)
            except ProcessLookupError:group_absent=True
            else:
                survivor_observed=True
                raise CommandError('Owned CLI group survives leader exit')
            need(time.monotonic()<end,'CLI group observation before original deadline')
            original_result=bytes(bufs['out'])
            return original_result
        except BaseException as e:
            original=e;error=type(e).__name__
            failure['exception']=e
            self.original_failures.append(failure);failure_retained=True
            raise
        finally:
            # One shared cleanup interval, never a new per-descendant allowance.
            cleanup_end=end;cleanup_in_time=False;elapsed=None
            try:
                cleanup_end=min(end,time.monotonic()+1)
                if p is not None and not group_absent:
                    live=False
                    try:os.killpg(p.pid,0);live=True
                    except ProcessLookupError:group_absent=True
                    except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__
                    if live:
                        try:os.killpg(p.pid,signal.SIGKILL)
                        except ProcessLookupError:group_absent=True
                        except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__
                if p is not None and not child_reaped:
                    try:rc=p.wait(timeout=max(0,cleanup_end-time.monotonic()));wait_returns.append(rc);child_reaped=True
                    except BaseException as e:secondary.append(e);cleanup_ok=False
                if p is not None and not group_absent:
                    while True:
                        try:os.killpg(p.pid,0)
                        except ProcessLookupError:group_absent=True;break
                        except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__;break
                        left=cleanup_end-time.monotonic()
                        if left<=0:break
                        time.sleep(min(.01,left))
                if p is not None and not group_absent:cleanup_ok=False
            except BaseException as e:
                secondary.append(e);cleanup_ok=False
            finally:
                # A probe/clock interruption must not skip independent handles.
                if s is not None:
                    try:s.close()
                    except BaseException as e:secondary.append(e);cleanup_ok=False
                if p is not None:
                    for stream in (p.stdout,p.stderr):
                        if stream is not None:
                            try:stream.close()
                            except BaseException as e:secondary.append(e);cleanup_ok=False
                try:
                    elapsed=time.monotonic()-start
                    cleanup_in_time=time.monotonic()<cleanup_end
                except BaseException as e:secondary.append(e);cleanup_ok=False
                cleanup_ok=cleanup_ok and cleanup_in_time
                self.reaped=previous_reaped and child_reaped and cleanup_ok and group_absent
                record={'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':elapsed,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok,'cleanup_before_original_cutoff':cleanup_in_time,'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,'group_probe_or_cleanup_error':group_error}
                self.records.append(record)
                try:
                    if time.monotonic()>=cleanup_end:
                        cleanup_ok=False;self.reaped=False
                        record['cleanup_complete']=False;record['cleanup_before_original_cutoff']=False
                except BaseException as e:
                    secondary.append(e);cleanup_ok=False;self.reaped=False
                    record['cleanup_complete']=False;record['cleanup_before_original_cutoff']=False
                if not cleanup_ok and original is None:
                    original=secondary[0] if secondary else CommandError('CLI cleanup incomplete')
                failure.update(exception=original,record=record,secondary_exceptions=tuple(secondary),
                               original_result=original_result,wait_returns=tuple(wait_returns),eof=dict(eof))
                self.last_original=failure
                if original is not None and not failure_retained:
                    self.original_failures.append(failure)
            if not cleanup_ok and error is None:raise original

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('slicetca-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

def inspect(d,kind,name,end,phase):
    rows=parse(call(d,[kind,'inspect',name],end,phase));need(type(rows)is list and len(rows)==1,'One inspected resource');return rows[0]

def owned(v,item,owner):
    need(v['Name']==(item['name'] if item['kind']=='volume' else '/'+item['name']),'Exact resource name')
    labels=v.get('Labels') if item['kind']=='volume' else v['Config'].get('Labels')
    need(labels is not None and labels.get(LABEL)==owner,'Exact owner label')
    if item.get('id') is not None:need(v['Id']==item['id'],'Exact returned container ID')

def resource_inventory(d,item,owner,end,prefix):
    a=inventory(d,item['kind'],'label='+LABEL+'='+owner,end,prefix+'_owner')
    # The owner is unique per resource (same panel/case suffix plus role).
    b=inventory(d,item['kind'],'name=^'+('/' if item['kind']=='container' else '')+item['name']+'$',end,prefix+'_name')
    need(a==b and len(a)<=1,'Exact owner/name join');return a

def retire(d,item,end):
    owner=item['owner'];rows=resource_inventory(d,item,owner,end,'cleanup_'+item['kind']);removed=False
    if not item.get('attempted',False):
        return {'kind':item['kind'],'name':item['name'],'create_not_attempted':True,'collision_preserved':bool(rows),'observed_namespace_empty':rows==[],'removed':False,'closed':rows==[]}
    if rows:
        value=inspect(d,item['kind'],rows[0],end,'cleanup_inspect');owned(value,item,owner)
        if item['kind']=='container' and value['State']['Running']:
            call(d,['container','kill','--signal','KILL',rows[0]],end,'cleanup_kill',4096)
            call(d,['container','wait',rows[0]],end,'cleanup_wait',4096)
        call(d,[item['kind'],'rm',rows[0]],end,'cleanup_remove',4096);removed=True
    after=resource_inventory(d,item,owner,end,'absence_'+item['kind'])
    unknown=item.get('attempted',False) and not item.get('acknowledged',False) and not removed
    return {'kind':item['kind'],'name':item['name'],'removed':removed,'absence_observed':after==[],'creation_outcome_unknown':unknown,'closed':after==[] and not unknown}

def mounts_argv(mounts):
    result=[]
    for target,(kind,source,rw) in mounts.items():
        value='type='+kind+',src='+str(source)+',dst='+target+(',volume-nocopy' if kind=='volume' else '')+('' if rw else ',readonly')
        result+=['--mount',value]
    return result
