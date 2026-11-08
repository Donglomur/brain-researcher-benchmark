"""Adapted bounded Docker CLI/resource custody from reviewed paper-program-b.

Local daemon only; no candidate stdout or numeric artifact bytes through CLI.
No runtime qualification is inherited.
"""
import hashlib, json, math, os, re, selectors, signal, stat, subprocess, sys, time
from pathlib import Path, PurePosixPath
LABEL='org.neurobench.osl-program-owner'

def need(ok,message):
    if not ok:raise ValueError(message)


def cleanup_note(primary,action,error):
    detail={'action':action,'type':type(error).__name__,'message':str(error)[:2000]}
    primary.cleanup_errors=[*getattr(primary,'cleanup_errors',[]),detail]
    if hasattr(primary,'add_note'):primary.add_note('Cleanup uncertainty: '+str(detail))


def cleanup_all(actions,primary=None):
    """Attempt every independent cleanup; keep the original failure identity."""
    failure=primary
    for label,action in actions:
        try:action()
        except BaseException as error:
            if failure is None:failure=error
            else:cleanup_note(failure,label,error)
    return failure


def finish_cleanup(actions,primary):
    failure=cleanup_all(actions,primary)
    if primary is None and failure is not None:raise failure

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def path(p):
    p=Path(p);need(p.is_absolute(),'absolute custody path')
    need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unlinked canonical path')
    need(not any(x in str(p) for x in (',','\n','\r','\0')),'unambiguous mount path');return p

def descriptor(p,allow_empty=False):
    need(type(p)is dict and set(p)=={'bytes','sha256'} and type(p['bytes'])is int and p['bytes']>=(0 if allow_empty else 1) and type(p['sha256'])is str and re.fullmatch('[0-9a-f]{64}',p['sha256']),'exact source descriptor');return p

def validate_natural_exit(v):
    need(type(v)is dict and set(v)=={'Status','Running','Dead','Pid','ExitCode','OOMKilled'},'exact natural-six state')
    need(type(v['Status'])is str and v['Status']=='exited','natural exit status')
    for k in ('Running','Dead','OOMKilled'):need(v[k]is False,'strict false stopped/OOM flags')
    for k in ('Pid','ExitCode'):need(type(v[k])is int and v[k]==0,'strict natural integer zero')
    return v

def validate_cli_records(records, caps):
    keys={'phase','returncode','error_type','observed_retained_bytes','seconds','client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed','leader_exited_with_group_alive','group_probe_or_cleanup_error'}
    need(type(records)is list and len(records)>0,'nonempty CLI record list')
    for v in records:
        need(type(v)is dict and set(v)==keys,'strict eleven CLI fields')
        cap=caps[v['phase']]
        need(type(v['returncode'])is int and v['returncode']==0 and v['error_type']is None and v['group_probe_or_cleanup_error']is None,'successful CLI')
        need(type(v['observed_retained_bytes'])is int and 0<=v['observed_retained_bytes']<=cap,'actual phase-specific CLI bytecap')
        need(type(v['seconds'])in (int,float) and math.isfinite(v['seconds']) and v['seconds']>=0,'finite actual CLI duration')
        for k in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'):need(v[k]is True,'literal completed CLI custody')
        need(v['leader_exited_with_group_alive']is False,'no surviving owned CLI group')
    return records


BOOTSTRAP = "import os,sys\ntry:\n    allowed=os.read(0,1)==b'G' and os.read(0,1)==b''\n    if not allowed:os._exit(125)\n    os.close(0)\n    fd=os.open('/dev/null',os.O_RDONLY)\n    if fd!=0:os.dup2(fd,0);os.close(fd)\n    os.execv(sys.argv[1],sys.argv[1:])\nexcept BaseException:\n    os._exit(126)\n"


def parse_process_identity(raw,pid,uid,boot_id):
    need(type(pid) is int and pid>1 and type(uid) is int and uid>=0,'Typed process ownership')
    need(type(raw) is bytes and 0<len(raw)<=4096,'Bounded Linux proc stat')
    opening=raw.find(b'(');closing=raw.rfind(b')')
    need(opening>0 and closing>opening and int(raw[:opening].strip())==pid,'Exact proc PID/comm boundary')
    fields=raw[closing+1:].split();need(len(fields)>=20 and fields[0] not in (b'Z',b'X',b'x'),'Live gated process')
    pgid,session,start=int(fields[2]),int(fields[3]),int(fields[19])
    need(pgid==session==pid and start>0,'Fresh independent gated session identity')
    need(type(boot_id) is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',boot_id),'Exact Linux boot identity')
    return {'schema':'osl_linux_process_identity_v1','pid':pid,'pgid':pgid,'session_id':session,'uid':uid,
            'start_time_ticks':start,'boot_id':boot_id}


def process_identity(pid,end,account_read,reserve_read):
    """Observe an anchored Linux /proc token before any Docker command release."""
    need(sys.platform.startswith('linux'),'Future operator requires Linux procfs')
    def read(name,cap,directory=None):
        need(time.monotonic()<end,'Identity before original cutoff');reserve_read(cap+1)
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        primary=None
        try:
            pieces=[];total=0
            while total<=cap:
                need(time.monotonic()<end,'Bounded identity deadline')
                raw=os.read(fd,min(4096,cap+1-total));account_read(len(raw))
                if not raw:break
                pieces.append(raw);total+=len(raw)
            need(total<=cap,'Bounded proc metadata');return b''.join(pieces)
        except BaseException as error:primary=error;raise
        finally:finish_cleanup([('proc_metadata.close',lambda:os.close(fd))],primary)
    boot=read('/proc/sys/kernel/random/boot_id',64).decode('ascii').strip()
    root=os.open('/proc',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    process=None;primary=None
    try:
        process=os.open(str(pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
        before=os.fstat(process);need(before.st_uid==os.geteuid(),'Exact operator UID while gated')
        raw=read('stat',4096,process)
        after=os.stat(str(pid),dir_fd=root,follow_symlinks=False)
        need((before.st_dev,before.st_ino,before.st_uid)==(after.st_dev,after.st_ino,after.st_uid),'Same anchored process instance')
        token=parse_process_identity(raw,pid,before.st_uid,boot)
        need(time.monotonic()<end,'Identity captured before original cutoff');return token
    except BaseException as error:primary=error;raise
    finally:
        actions=[]
        if process is not None:actions.append(('proc_process.close',lambda:os.close(process)))
        actions.append(('proc_root.close',lambda:os.close(root)))
        finish_cleanup(actions,primary)

def release_bootstrap(process,token,publish,index,phase,end):
    """Only durable ownership followed by exactly one checked gate byte."""
    need(token['pid']==token['pgid']==token['session_id']==process.pid,'Exact gated child identity')
    publish('CLI-CHILD',{'index':index,'phase':phase,'pid':process.pid,'pgid':process.pid,'original_end':end,
                         'independent_group':True,'process_identity':token,'docker_exec_still_gated':True})
    need(time.monotonic()<end,'Journal committed before original cutoff')
    need(os.write(process.stdin.fileno(),b'G')==1,'Exactly one gate byte')
    process.stdin.close()

class CommandError(RuntimeError):pass

class Docker:
    """Streaming-capped local CLI with pidfd-bound leader cleanup, never killpg."""
    def __init__(self,binary,socket,*,max_calls,reply_budget,phase_caps,publish,account_read,reserve_read):
        self.account_read=account_read;self.reserve_read=reserve_read;self.phase_caps=dict(phase_caps)
        self.max_calls=max_calls;self.reply_budget=reply_budget;self.reserved=0;self.publish=publish
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        start=time.monotonic();need(end-start>1,'Command deadline')
        need(type(cap)is int and cap==self.phase_caps.get(phase) and len(self.records)<self.max_calls,'exact source-selected command cap/count')
        need(self.reserved+cap<=self.reply_budget,'cumulative CLI response reservation')
        need(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'Identity-bound Linux process signaling')
        self.reserve_read(cap);self.reserved+=cap
        self.publish('CLI-INTENT',{'index':len(self.records),'phase':phase,'cap':cap,'original_end':end})
        p=None;s=None;pidfd=None;bufs={'out':bytearray(),'err':bytearray()};primary=None;rc=None
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;cleanup_errors=[];cleanup_failure=None
        self.reaped=False
        def probe():
            try:os.killpg(p.pid,0)
            except ProcessLookupError:return True
            return False
        try:
            p=subprocess.Popen([sys.executable,'-I','-S','-B','-c',BOOTSTRAP,*self.prefix,*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True,close_fds=True)
            # This exact Popen child has not been reaped. The pidfd remains
            # identity-bound after leader exit/reap or numeric PID reuse.
            pidfd=os.pidfd_open(p.pid,0)
            token=process_identity(p.pid,end,self.account_read,self.reserve_read)
            release_bootstrap(p,token,self.publish,len(self.records),phase,end)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    self.account_read(len(raw))
                    if not raw:s.unregister(k.fileobj);continue
                    need(sum(map(len,bufs.values()))+len(raw)<=cap,'Streaming CLI cap');bufs[k.data].extend(raw)
            rc=p.wait(timeout=max(0,end-time.monotonic()));child_reaped=True
            need(rc==0,'Docker command failure')
            group_absent=probe()
            if not group_absent:
                survivor_observed=True;raise CommandError('Owned CLI group survives leader exit')
            need(time.monotonic()<end,'CLI group observation before original deadline')
            return bytes(bufs['out'])
        except BaseException as error:primary=error;raise
        finally:
            cleanup_end=min(end,time.monotonic()+1)
            def clean(label,action):
                nonlocal cleanup_ok,cleanup_failure
                try:action()
                except BaseException as error:
                    cleanup_ok=False;cleanup_errors.append({'action':label,'type':type(error).__name__,'message':str(error)[:2000]})
                    if primary is not None:cleanup_note(primary,label,error)
                    elif cleanup_failure is None:cleanup_failure=error
                    else:cleanup_note(cleanup_failure,label,error)
            # EOF closes an unreleased gate. Failure of one close does not skip
            # identity-bound signaling, reaping, other streams or the pidfd.
            if p is not None and p.stdin is not None:clean('stdin.close',p.stdin.close)
            if p is not None and not group_absent:
                try:group_absent=probe()
                except BaseException as error:clean('group.probe',lambda:(_ for _ in ()).throw(error))
                if not group_absent:
                    if pidfd is None:
                        clean('pidfd.missing',lambda:need(False,'No identity-bound signal authority'))
                    else:
                        def kill_leader():
                            try:signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
                            except ProcessLookupError:pass
                        clean('pidfd.kill',kill_leader)
            if p is not None and not child_reaped:
                def reap():
                    nonlocal rc,child_reaped
                    rc=p.wait(timeout=max(0,cleanup_end-time.monotonic()));child_reaped=True
                clean('client.wait',reap)
            if p is not None and not group_absent:
                def observe_group():
                    nonlocal group_absent
                    while True:
                        group_absent=probe()
                        if group_absent:return
                        left=cleanup_end-time.monotonic()
                        if left<=0:return
                        time.sleep(min(.01,left))
                clean('group.absence',observe_group)
                if not group_absent:clean('group.unclosed',lambda:need(False,'Surviving or reused group remains unknown; no group signal authorized'))
            if s is not None:clean('selector.close',s.close)
            if p is not None:
                for name,stream in (('stdout',p.stdout),('stderr',p.stderr)):
                    if stream is not None:clean(name+'.close',stream.close)
            if pidfd is not None:clean('pidfd.close',lambda:os.close(pidfd))
            cleanup_in_time=time.monotonic()<cleanup_end
            if not cleanup_in_time:clean('original_cutoff',lambda:need(False,'CLI cleanup exceeded original cutoff'))
            self.reaped=previous_reaped and child_reaped and cleanup_ok and group_absent and cleanup_in_time
            self.records.append({'phase':phase,'returncode':rc,'error_type':None if primary is None else type(primary).__name__,
                'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':time.monotonic()-start,'client_reaped':child_reaped,
                'cleanup_complete':cleanup_ok and group_absent and cleanup_in_time,'cleanup_before_original_cutoff':cleanup_in_time,
                'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,
                'group_probe_or_cleanup_error':cleanup_errors or None})
            if primary is None and cleanup_failure is not None:raise cleanup_failure

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('osl-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

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
