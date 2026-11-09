"""Qualified Linux cgroup-v2 containment and an independent finite guardian.

No host probe or mutation occurs on import. The operator must provide an existing
exclusive delegated cgroup root and finite guardian reserves. A fresh child
cgroup is created once per invocation; only that exact inode is controlled.
The guardian stays outside it, watches a parent-only liveness FD, kills/reaps
membership on parent death or deadline, and preserves measured closure. Neither
setsid nor a child fork escapes cgroup membership. This is trusted-stage
containment; the separate runtime layer isolates candidate/model/report roles.
"""
from __future__ import annotations
import hashlib
import hmac
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
from .io import ByteMeter, ContractError, canonical, capture, decode, ordinary


CG_FILES = {'cgroup.procs', 'cgroup.events', 'cgroup.kill', 'cpu.max', 'cpu.stat',
            'memory.max', 'memory.swap.max', 'memory.peak', 'memory.events', 'pids.max', 'pids.peak'}


def profile(limits):
    value=limits['device_manifest'].get('trusted_worker_containment')
    required={'cgroup_root','guardian_read_bytes','guardian_write_bytes','guardian_ram_bytes',
              'guardian_cpu_seconds','guardian_wall_seconds','pids_max'}
    if not isinstance(value,dict) or set(value)!=required:
        raise ContractError('exact qualified trusted-worker containment profile required')
    if not isinstance(value['cgroup_root'],str) or not Path(value['cgroup_root']).is_absolute():
        raise ContractError('existing explicit absolute delegated cgroup root required')
    for key in required-{'cgroup_root'}:
        if type(value[key]) is not int or value[key]<=0:
            raise ContractError('finite positive guardian allocation required')
    if value['guardian_ram_bytes'] < 64*(1024**2) or value['guardian_cpu_seconds'] < 5:
        raise ContractError('complete guardian needs at least64MiB virtual memory and5CPU seconds; actual sufficiency remains qualified')
    if value['pids_max']<16 or value['pids_max']>4096:
        raise ContractError('complete trusted stage needs16..4096 bounded tasks')
    if value['guardian_wall_seconds']<5:
        raise ContractError('separate finite closure reserve of at least5seconds required')
    # One bounded cpu/events sample per second plus setup and final closure.
    if value['guardian_read_bytes']<4*(262144+4096*(limits['wall_seconds']+value['guardian_wall_seconds'])):
        raise ContractError('guardian read reserve cannot cover complete admitted wall interval')
    if value['guardian_write_bytes']<65536:
        raise ContractError('complete guardian closure journal reserve required')
    return value


def _read(path,cap,meter):
    p=ordinary(path)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        body=os.read(fd,cap+1)
        if len(body)>cap:
            raise ContractError('bounded virtual kernel record exceeded')
        meter.read(len(body))
        return body.decode('ascii')
    finally: os.close(fd)


def _write(path,text,meter):
    p=ordinary(path);body=text.encode('ascii');meter.write(len(body))
    fd=os.open(p,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if os.write(fd,body)!=len(body): raise ContractError('short cgroup control write')
    finally: os.close(fd)


def _fields(text):
    answer={}
    for line in text.splitlines():
        key,value=line.split()
        if key in answer or not value.isdecimal(): raise ContractError('invalid kernel counter record')
        answer[key]=int(value)
    return answer


def _identity(path,identity):
    st=ordinary(path,directory=True).stat()
    if [st.st_dev,st.st_ino]!=identity: raise ContractError('owned cgroup identity changed')


def create(spec,limits,meter):
    if sys.platform!='linux': raise ContractError('qualified Linux cgroup-v2 host required')
    plan=profile(limits)
    root=ordinary(plan['cgroup_root'],directory=True)
    # Authenticate actual mount type; a same-named ordinary directory is not a
    # cgroup boundary. Refuse escaped mount paths in this finite host profile.
    mounts=_read('/proc/'+str(os.getpid())+'/mountinfo',262144,meter)
    cgroup_mounts=[]
    for line in mounts.splitlines():
        fields=line.split()
        sep=fields.index('-')
        if fields[sep+1]=='cgroup2' and '\\' not in fields[4]: cgroup_mounts.append(Path(fields[4]))
    if not any(root==m or m in root.parents for m in cgroup_mounts):
        raise ContractError('declared root is not on an authenticated cgroup2 mount')
    controllers=set(_read(root/'cgroup.subtree_control',4096,meter).split())
    if not {'cpu','memory','pids'}<=controllers:
        raise ContractError('cpu/memory/pids must already be delegated and enabled')
    name='neural063-'+hashlib.sha256(canonical({'attempt':spec['attempt'],'stage':spec['stage'],'root':spec['output_root']})).hexdigest()
    group=root/name
    group.mkdir(mode=0o700)  # no reuse, overwrite, or unrelated group adoption
    st=group.stat();ident=[st.st_dev,st.st_ino]
    if not CG_FILES<={p.name for p in group.iterdir()}:
        raise ContractError('required kill/peak/swap/controller interfaces unavailable')
    _write(group/'memory.max',str(limits['ram_bytes']),meter)
    _write(group/'memory.swap.max','0',meter)
    _write(group/'pids.max',str(plan['pids_max']),meter)
    cores=len(set(limits['device_manifest']['trusted_worker_cpu_ids']))
    _write(group/'cpu.max',str(cores*100000)+' 100000',meter)
    return {'path':str(group),'identity':ident,'profile':plan,'attempt':spec['attempt'],'stage':spec['stage']}


def _owned_directory(group):
    # Pin the directory FD before using controls. A later path rename/reuse
    # cannot redirect openat() to a different group's kernel control files.
    path=ordinary(group['path'],directory=True)
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    st=os.fstat(fd)
    if [st.st_dev,st.st_ino]!=group['identity']:
        os.close(fd);raise ContractError('owned cgroup identity changed before control open')
    return fd


def _control(fd,name,meter,*,text=None,cap=4096):
    if name not in CG_FILES:raise ContractError('unknown cgroup control')
    child=os.open(name,(os.O_WRONLY if text is not None else os.O_RDONLY)|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    try:
        if text is not None:
            body=text.encode('ascii');meter.write(len(body))
            if os.write(child,body)!=len(body):raise ContractError('short owned cgroup write')
            return None
        body=os.read(child,cap+1)
        if len(body)>cap:raise ContractError('owned kernel record exceeds bounded read')
        meter.read(len(body));return body.decode('ascii')
    finally:os.close(child)


def enter(group):
    fd=_owned_directory(group)
    try:_control(fd,'cgroup.procs',ByteMeter(0,64),text=str(os.getpid()))
    finally:os.close(fd)


def _shutdown(group,meter,deadline):
    fd=_owned_directory(group)
    try:
        _control(fd,'cgroup.kill',meter,text='1')
        while True:
            events=_fields(_control(fd,'cgroup.events',meter))
            if events.get('populated')==0:break
            if time.monotonic()>=deadline:raise ContractError('own cgroup membership did not reach empty before closure deadline')
            time.sleep(min(0.05,max(0,deadline-time.monotonic())))
        return {'populated':0,'cpu':_fields(_control(fd,'cpu.stat',meter)),
                'memory_peak_bytes':int(_control(fd,'memory.peak',meter,cap=128).strip()),
                'memory_events':_fields(_control(fd,'memory.events',meter)),
                'pids_peak':int(_control(fd,'pids.peak',meter,cap=128).strip())}
    finally:os.close(fd)


def guardian_main(args):
    started=time.monotonic()
    # A one-use parent capability authenticates exactly the fresh cgroup inode.
    secret=os.read(args.key_fd,33);os.close(args.key_fd)
    signed=decode(capture(args.context,args.context_bytes))
    if len(secret)!=32 or not hmac.compare_digest(signed['mac'],hmac.new(secret,canonical(signed['context']),hashlib.sha256).hexdigest()):
        raise ContractError('invalid guardian transport authority')
    ctx=signed['context'];group=ctx['group'];plan=group['profile']
    _identity(group['path'],group['identity'])
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(plan['guardian_cpu_seconds']-2,plan['guardian_cpu_seconds']))
    resource.setrlimit(resource.RLIMIT_AS,(plan['guardian_ram_bytes'],plan['guardian_ram_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    meter=ByteMeter(plan['guardian_read_bytes']*3//4,plan['guardian_write_bytes']//2)
    meter.read(args.context_bytes+32)
    monitor=selectors.DefaultSelector();monitor.register(args.live_fd,selectors.EVENT_READ)
    os.write(args.ready_fd,b'R');os.close(args.ready_fd)
    reason='parent_closed_or_exited';failure=None;observations=None
    def interrupted(signum, frame):
        raise ContractError('guardian interrupted by signal '+str(signum))
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGXCPU):
        signal.signal(sig, interrupted)
    try:
        while True:
            if monitor.select(1.0):
                if os.read(args.live_fd,1)==b'': break
                raise ContractError('liveness channel admits no payload')
            if time.monotonic()>=ctx['deadline'] or time.time()>=ctx['attempt_expires_at']:
                reason='wall_expired';break
            cpu=_fields(_read(Path(group['path'])/'cpu.stat',4096,meter))
            if cpu.get('usage_usec',0)>ctx['cpu_core_seconds']*1000000:
                reason='aggregate_cpu_exceeded';break
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc)[:2048]};reason='guardian_monitor_failed'
    finally:
        monitor.close();os.close(args.live_fd)
        try:
            observations=_shutdown(group,meter,time.monotonic()+plan['guardian_wall_seconds'])
        except BaseException as exc:
            failure={'type':type(exc).__name__,'message':str(exc)[:2048],'prior':failure}
    usage=resource.getrusage(resource.RUSAGE_SELF)
    result={'schema':'neural063_cgroup_guardian_result_v1','attempt':group['attempt'],'stage':group['stage'],
            'cgroup':group,'reason':reason,'observations':observations,'failure':failure,'usage':meter.snapshot(),
            'source_context_sha256':hashlib.sha256(canonical(ctx)).hexdigest(),
            'process_usage':{'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime,
                             'linux_peak_rss_bytes':usage.ru_maxrss*1024,'wall_seconds':time.monotonic()-started}}
    body=canonical(result);meter.write(len(body))
    fd=os.open(ctx['result_path'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as stream: stream.write(body);stream.flush();os.fsync(stream.fileno())
    return 0 if failure is None else 1


class Guardian:
    def __init__(self,spec,limits,transport):
        self.plan=profile(limits)
        self.terminations=[]
        self.meter=ByteMeter(self.plan['guardian_read_bytes']//4,self.plan['guardian_write_bytes']//2)
        self.group=create(spec,limits,self.meter)
        self.result=Path(spec['output_root'])/'transport'/(spec['stage']+'.guardian-result.json')
        ctx={'group':self.group,'deadline':min(time.monotonic()+limits['wall_seconds'],limits['monotonic_deadline']),
             'attempt_expires_at':limits['attempt_expires_at'],
             'cpu_core_seconds':limits['cpu_core_seconds'],'result_path':str(self.result)}
        secret=os.urandom(32)
        body={'context':ctx,'mac':hmac.new(secret,canonical(ctx),hashlib.sha256).hexdigest()}
        ref=transport.json('transport/'+spec['stage']+'.guardian-context.json',body,role='guardian_context',visibility='operator',producer=spec['stage'])
        kr,kw=os.pipe();lr,lw=os.pipe();rr,rw=os.pipe()
        self.live=lw;self.process=None
        try:
            os.write(kw,secret);os.close(kw);kw=-1
            cmd=[sys.executable,'-I','-B',str(Path(__file__).parent.parent/'neural063.py'),'_cgroup-guardian',
                 '--context',ref.path,'--context-bytes',str(ref.bytes),'--key-fd',str(kr),'--live-fd',str(lr),'--ready-fd',str(rw)]
            self.process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    close_fds=True,pass_fds=(kr,lr,rw),env={'PATH':os.defpath,'LANG':'C.UTF-8'},start_new_session=True)
            os.close(kr);kr=-1;os.close(lr);lr=-1;os.close(rw);rw=-1
            select=selectors.DefaultSelector();select.register(rr,selectors.EVENT_READ)
            try:
                if not select.select(5) or os.read(rr,1)!=b'R': raise ContractError('independent guardian readiness absent')
            finally: select.close()
        except BaseException:
            os.close(self.live);self.live=-1
            # No worker has entered the fresh cgroup before readiness.
            _shutdown(self.group,self.meter,time.monotonic()+self.plan['guardian_wall_seconds'])
            if self.process is not None:
                try:self.process.wait(timeout=self.plan['guardian_wall_seconds']+2)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
            raise
        finally:
            for fd in (kr,kw,lr,rr,rw):
                if fd>=0:os.close(fd)

    def terminate(self, reason):
        """Stop only the authenticated fresh cgroup, never a numeric PGID."""
        record={"reason":reason,"cgroup":self.group,"started_ns":time.time_ns()}
        self.terminations.append(record)
        try:
            record["observations"]=_shutdown(self.group,self.meter,time.monotonic()+self.plan["guardian_wall_seconds"])
        except BaseException as exc:
            record["unresolved"]={"class":type(exc).__name__,"message":str(exc)[:2048]}
            raise
        finally:
            record["ended_ns"]=time.time_ns()
        return record

    def finish(self):
        if self.live>=0:os.close(self.live);self.live=-1
        try:self.process.wait(timeout=self.plan['guardian_wall_seconds']+2)
        except subprocess.TimeoutExpired:
            observations=_shutdown(self.group,self.meter,time.monotonic()+self.plan['guardian_wall_seconds'])
            self.process.kill();self.process.wait(timeout=2)
            raise ContractError('guardian failed to close; own group explicitly killed: '+str(observations))
        try:
            body=capture(self.result,self.plan['guardian_write_bytes']//2,meter=self.meter)
            result=decode(body)
            if (result.get('cgroup')!=self.group or result.get('failure') is not None or
                    self.process.returncode!=0 or result.get('observations',{}).get('populated')!=0):
                raise ContractError('guardian closure not independently established')
        except BaseException as exc:
            # Unexpected guardian death must never leave an owned group alive.
            # The failure remains a failure even after parent recovery succeeds.
            observed=_shutdown(self.group,self.meter,time.monotonic()+self.plan['guardian_wall_seconds'])
            failure=ContractError('guardian failed; parent explicitly emptied own cgroup: '+str(exc))
            failure.usage={'cgroup':self.group,'parent_recovery_observations':observed,'parent_setup_usage':self.meter.snapshot(),'parent_terminations':self.terminations}
            raise failure from exc
        result['parent_setup_usage']=self.meter.snapshot()
        result['parent_terminations']=self.terminations
        # Counters include all trusted stage descendants; do not add child CPU a
        # second time. A timeout/aggregate overrun remains a failed stage.
        return result
