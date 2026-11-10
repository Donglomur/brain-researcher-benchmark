"""Actual CPU-only Linux worker isolation and original process observation.

No arbitrary provider callback is accepted as an isolation receipt. The adapter
uses an independently qualified delegated cgroup-v2 root, a pinned bubblewrap
binary, an immutable minimal runtime, read-only declared inputs and a private
workspace. GPU/provider backends remain unavailable until separately qualified.
The low-level child observer can also exercise explicitly unqualified inert
engineering children; those receipts never satisfy the scientific adapter.
"""
import os
import signal
import stat
import subprocess
import time
from pathlib import Path
from .protocol import HandleCustody,Directory,fields,need,integer,digest,descriptor,identity,encode,observation,Refusal,stream_capture
from .budget import JOB_FIELDS


def _regular_text(path,cap=65536):
    with HandleCustody('original_observer_record') as owned:
        fd=owned.own_fd(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'record')
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode),'ordinary observer control member');raw=os.read(fd,cap+1);need(len(raw)<=cap,'bounded actual observer record');return raw.decode('ascii')


def _control(path,value):
    with HandleCustody('original_observer_control') as owned:
        fd=owned.own_fd(os.open(path,os.O_WRONLY|os.O_NOFOLLOW),'control')
        raw=(str(value)+'\n').encode('ascii');n=os.write(fd,raw);need(n==len(raw),'complete actual cgroup control write')


def _pairs(text):
    out={}
    for line in text.splitlines():
        k,v=line.split();need(k not in out,'unique actual observer field');out[k]=int(v)
    return out


class Cgroup:
    def __init__(self,root,name,limits):
        self.root=None;self.path=Path(root)/name;self.created=False;self.removed=False;self.limits=limits
        with HandleCustody('original_cgroup_acquisition') as owned:
            owned.own(self,'group')
            self.root=Directory(str(root))
            need(name and all(c in '0123456789abcdef-' for c in name),'private cgroup identifier')
            need(os.uname().sysname=='Linux' and {'cpu','memory','pids'}<=set(_regular_text(self.root.path/'cgroup.controllers').split()),'qualified cgroup-v2 delegated CPU/memory/pid controllers')
            os.mkdir(name,mode=0o700,dir_fd=self.root.fd);self.created=True
            _control(self.path/'memory.max',limits['resident_bytes']);_control(self.path/'memory.swap.max',0);_control(self.path/'memory.oom.group',1)
            _control(self.path/'pids.max',limits['threads']);_control(self.path/'cpu.max',str(limits['threads']*100000)+' 100000')
            self.initial=self.sample();need(self.initial['cpu_milliseconds']==0 and self.initial['populated']==0,'fresh original cgroup, no reused worker state')
            owned.release(self)
    def sample(self):
        cpu=_pairs(_regular_text(self.path/'cpu.stat'));events=_pairs(_regular_text(self.path/'cgroup.events'));memory=_pairs(_regular_text(self.path/'memory.events'))
        return {'cpu_milliseconds':(cpu['usage_usec']+999)//1000,'peak_resident_bytes':int(_regular_text(self.path/'memory.peak')),'resident_bytes':int(_regular_text(self.path/'memory.current')),'populated':events['populated'],'oom_kill':memory.get('oom_kill',0)}
    def kill(self):_control(self.path/'cgroup.kill',1)
    def close(self):self.cleanup()
    def cleanup(self):
        with HandleCustody('original_cgroup_cleanup') as owned:
            if self.root is not None:owned.own(self.root,'delegated_root')
            if self.created and not self.removed:
                need(self.sample()['populated']==0,'all original descendants gone before cgroup removal');os.rmdir(self.path);self.removed=True


def tree_usage(root,*,file_limit,per_file_limit,byte_limit):
    """Account writable workspace without following links or device nodes."""
    count=0;total=0;largest=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            s=os.lstat(Path(directory)/name);need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode),'no mutable directory aliases')
        for name in files:
            s=os.lstat(Path(directory)/name);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary unique writable artifacts only')
            count+=1;total+=s.st_size;largest=max(largest,s.st_size)
            need(count<=file_limit and s.st_size<=per_file_limit and total<=byte_limit,'all current output/scratch within selected original ceilings')
    return {'files':count,'bytes':total,'largest':largest}


class ProcessCustody:
    """Strong original owner allocated before any launch or fallible accounting.

    Unknown launch/cleanup stays unresolved. Later finalizers may add evidence,
    but cannot turn an attempted unknown launch into a never-launched process.
    """
    def __init__(self,job_id):
        self.actual={**{k:None for k in JOB_FIELDS},'spawned':False,'natural_exit':None,'forced_exit':None,'timed_out':False,'reaped':True,'descendants_closed':True,'observer_complete':False,'peak_resident_bytes':None,'peak_gpu_resident_bytes':None,'artifacts':[],'failures':[]}
        self.record={'observation':self.actual,'original_budget_record':{'id':job_id,'status':'not_started','reserved':None,'observation':None},'original_process':None,'launch_state':'never_attempted','secondary_failures':[]}
        self.child=None
    def attempted(self):
        self.record['launch_state']='attempted_unresolved';self.actual.update(spawned=None,reaped=False,descendants_closed=False)
    def observed(self,result):
        self.record['original_process']=result;self.actual=result['actual'];self.record['observation']=self.actual
        self.record['launch_state']='observed_closed' if self.actual['reaped'] is True and self.actual['descendants_closed'] is True else 'observed_unresolved'


def observe_child(argv,*,cwd,environment,stdout_path,stderr_path,deadline,requested,limits,cgroup=None,preexec=None,pass_fds=(),custody=None):
    """One actual process; original failures survive all cleanup outcomes.

    Without cgroup, CPU/RAM/descendant observation is explicitly unavailable and
    observer_complete is false. That mode is exclusively useful to construction
    controls; it is never promoted to a scientific execution qualification.
    """
    custody=ProcessCustody('low-level-observer') if custody is None else custody
    child=None;out=None;err=None;start=time.monotonic_ns();failures=[];sample=None;natural=None;forced=None;timed=False;reaped=False;closed=False;peak_disk=0;spawned=False
    try:
        need(type(argv) is list and argv and all(type(x) is str and '\x00' not in x for x in argv),'parsed original argv, never shell text')
        need(time.monotonic_ns()<=deadline,'original deadline before observer paths');out=open(stdout_path,'xb',buffering=0);err=open(stderr_path,'xb',buffering=0)
        need(time.monotonic_ns()<=deadline,'original deadline immediately before launch');custody.attempted()
        child=subprocess.Popen(argv,cwd=cwd,env=environment,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,close_fds=True,preexec_fn=preexec,pass_fds=pass_fds)
        spawned=True;custody.child=child;custody.actual['spawned']=True;custody.record['original_pid']=child.pid
        while True:
            value=child.poll()
            if value is not None:
                natural=value;reaped=True
                need(time.monotonic_ns()<=deadline,'original deadline after child poll/wait')
                break
            now=time.monotonic_ns()
            if now>deadline:timed=True;raise Refusal('original call/campaign deadline')
            disk=tree_usage(cwd,file_limit=limits['files'],per_file_limit=limits['per_file_bytes'],byte_limit=requested['scratch_bytes']+requested['output_bytes']);peak_disk=max(peak_disk,disk['bytes'])
            if cgroup is not None:
                sample=cgroup.sample();need(sample['cpu_milliseconds']<=requested['cpu_milliseconds'] and sample['oom_kill']==0,'original total CPU and memory ceiling')
            time.sleep(min(.02,max(0,(deadline-now)/1e9)))
    except BaseException as exc:failures.append(observation(exc))
    finally:
        if child is not None:
            try:
                if child.poll() is None:
                    if cgroup is not None:cgroup.kill()
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    forced=child.wait(timeout=5);reaped=True
                elif not reaped:natural=child.wait();reaped=True
            except BaseException as exc:failures.append({'phase':'original_child_reap',**observation(exc)})
            if cgroup is not None:
                try:
                    sample=cgroup.sample()
                    if sample['populated']:
                        cgroup.kill();failures.append({'kind':'descendant_survived_original_main_exit'})
                        end=time.monotonic_ns()+5_000_000_000
                        while cgroup.sample()['populated'] and time.monotonic_ns()<end:time.sleep(.01)
                    sample=cgroup.sample();closed=sample['populated']==0
                    if not closed:failures.append({'kind':'original_descendants_unreaped'})
                except BaseException as exc:failures.append({'phase':'original_descendant_observer',**observation(exc)})
        for label,handle in (('stdout',out),('stderr',err)):
            if handle is not None:
                try:handle.close()
                except BaseException as exc:failures.append({'phase':label+'_close',**observation(exc)})
        try:disk=tree_usage(cwd,file_limit=limits['files'],per_file_limit=limits['per_file_bytes'],byte_limit=requested['scratch_bytes']+requested['output_bytes']);peak_disk=max(peak_disk,disk['bytes'])
        except BaseException as exc:failures.append({'phase':'final_original_disk_observer',**observation(exc)})
    if custody.record['launch_state']=='never_attempted':reaped=True;closed=True
    if natural is not None and natural!=0:failures.append({'kind':'original_nonzero_exit','exit':natural})
    actual={'read_bytes':None,'output_bytes':None,'scratch_bytes':peak_disk,'cpu_milliseconds':None if sample is None else sample['cpu_milliseconds'],'gpu_milliseconds':0 if cgroup is not None else None,'input_tokens':0,'output_tokens':0,'spawned':spawned if child is not None or custody.record['launch_state']=='never_attempted' else None,'natural_exit':natural,'forced_exit':forced,'timed_out':timed,'reaped':reaped,'descendants_closed':closed,'observer_complete':False,'peak_resident_bytes':None if sample is None else sample['peak_resident_bytes'],'peak_gpu_resident_bytes':0 if cgroup is not None else None,'artifacts':[],'failures':failures}
    # Publish actual cleanup/wait facts to the caller-owned object BEFORE any
    # fallible identity, timestamp or return construction can discard them.
    custody.actual.update(actual);actual=custody.actual
    result={'actual':actual,'original_pid':None if child is None else child.pid,'start_ns':start,'end_ns':None,'argv_identity':None,'environment_identity':None,'cgroup_observed':cgroup is not None,'natural_exit_observed_after_parent_deadline':None}
    custody.observed(result)
    try:
        result['end_ns']=time.monotonic_ns();result['argv_identity']=identity(argv);result['environment_identity']=identity(environment);result['natural_exit_observed_after_parent_deadline']=time.monotonic_ns()>deadline
    except BaseException as exc:
        custody.record['secondary_failures'].append({'phase':'original_observer_return_construction',**observation(exc)});exc.original_process_custody=custody.record;raise
    return result


class LinuxCPUExecutor:
    def __init__(self,deployment,source_root,ledger):
        fields(deployment,('schema','bubblewrap','runtime_root','runtime_inventory','cgroup_root','qualification','environment','workspace_quota','io_observer'),'complete original local CPU executor')
        need(deployment['schema']=='eegpt_linux_cpu_v1' and os.uname().sysname=='Linux','qualified Linux backend; no host escape fallback')
        digest(deployment['qualification']);need(ledger.limits['gpu_milliseconds']==0 and ledger.limits['gpu_resident_bytes']==0,'this concrete backend is CPU-only, no fictional GPU observation')
        # A deployment evidence digest does not establish an implementation:
        # these two selected mechanisms are mandatory physical prerequisites.
        need(deployment['workspace_quota']['kind']=='xfs_project_quota_v1' and deployment['io_observer']['kind']=='qualified_syscall_byte_observer','actual hard workspace quota and read/write syscall accounting must be installed and independently qualified')
        self.deployment=deployment;self.source_root=source_root;self.ledger=ledger
        stream_capture(source_root,deployment['bubblewrap']['path'],expected=deployment['bubblewrap'],ledger=ledger,cap=ledger.limits['per_file_bytes'])
        self.binary=str(source_root.path/deployment['bubblewrap']['path']);self.runtime=Directory(deployment['runtime_root']);self.runtime_identity=identity(deployment['runtime_inventory'])
        try:
            for member in deployment['runtime_inventory']:stream_capture(self.runtime,member['path'],expected=member,ledger=ledger,cap=ledger.limits['per_file_bytes'])
            from .protocol import exact_tree
            exact_tree(self.runtime,deployment['runtime_inventory'])
            from .workspace_quota import ProjectQuota
            self.quota=ProjectQuota(deployment['workspace_quota'],ledger)
        except BaseException:
            self.runtime.close();raise
    def build_argv(self,entry,inputs,workspace,request,response,*,read_only_workspace=False):
        need(type(entry) is list and entry and entry[0].startswith('/runtime/'),'entrypoint executes only pinned selected runtime')
        args=[self.binary,'--die-with-parent','--new-session','--unshare-all','--clearenv','--ro-bind',str(self.runtime.path),'/runtime','--proc','/proc','--dev','/dev','--dir','/tmp','--dir','/inputs','--dir','/source','--dir','/state']
        for binding in inputs:
            fields(binding,('host','guest','identity'),'exact independently admitted capability mount');digest(binding['identity'])
            need(binding['guest'].startswith(('/inputs/','/source/','/state/')) and '..' not in Path(binding['guest']).parts,'only declared input/source/state capabilities')
            args+=['--ro-bind',binding['host'],binding['guest']]
        args+=['--ro-bind' if read_only_workspace else '--bind',str(workspace),'/work','--bind',str(Path(workspace)/'tmp'),'/tmp','--bind',str(Path(workspace)/'shm'),'/dev/shm','--remount-ro','/','--chdir','/work']
        for k,v in self.deployment['environment'].items():need(k in ('LANG','LC_ALL','TZ','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONHASHSEED'),'closed controlled worker environment');args+=['--setenv',k,v]
        args+=['--',*entry,'--request',request,'--response',response];return args
    def close(self):
        failures=[]
        for h in (self.quota,self.runtime):
            try:h.close()
            except BaseException as exc:failures.append(observation(exc))
        need(not failures,'original executor handles closed: '+str(failures))


def traced_read_bytes(lines):
    """All observed successful read bytes and full mmap extents, once.

    This is a conservative logical-access measure, not physical I/O or RSS.
    Unknown/unfinished original syntax prevents observer qualification.
    """
    import re
    done=re.compile(r'^(?:\[pid\s+(\d+)\]\s+|(?:(\d+)\s+))?(read|pread64|readv|preadv|preadv2|mmap)\(.*\)\s+=\s+(-?\d+|0x[0-9a-f]+)(?:\s.*)?$')
    pending={};unknown=[];total=0
    for original in lines:
        line=original.strip()
        if not line:continue
        pm=re.match(r'^(?:\[pid\s+(\d+)\]|(\d+))\s+',line);pid=next((x for x in pm.groups() if x is not None),'main') if pm else 'main';normalized=line[pm.end():] if pm else line
        if normalized.startswith(('+++ exited with ','+++ killed by ','--- SIG')):continue
        if '<unfinished ...>' in line:
            need(pid not in pending,'one original pending syscall per thread');pending[pid]=line.split('<unfinished ...>')[0];continue
        if '<... ' in line and ' resumed>' in line:
            prefix=pending.pop(pid,None)
            if prefix is None:unknown.append(original);continue
            line=prefix+line.split(' resumed>',1)[1]
        match=done.match(line)
        if match is None:unknown.append(original);continue
        call=match.group(3);value=match.group(4)
        if call=='mmap':
            size=re.search(r'mmap\([^,]+,\s*(\d+),',line)
            if size is None:unknown.append(original)
            elif value!='-1':total+=int(size.group(1))
        elif not value.startswith('0x'):total+=max(0,int(value))
        else:unknown.append(original)
    return {'known_logical_read_bytes':total,'pending':pending,'unknown':unknown,'complete':not pending and not unknown,'mapping_measure':'full successful mmap grant extent, not physical I/O or RSS'}


def _executor_run(self,job,*,entry,inputs,workspace,observer_root,request,response,custody):
    """Concrete actual launch-to-reap path; never consumes caller observations."""
    import resource
    from .protocol import read_metadata
    fields(job,('id','reservation','development','source_identity','input_identity'),'original concrete job')
    need(isinstance(custody,ProcessCustody),'strong caller-owned original process custody before executor');need(all(c in '0123456789abcdef-' for c in job['id']),'private unique job id');record=self.ledger.begin(job['id'],job['reservation'],development=job['development']);custody.record['original_budget_record']=record
    cgroup=None;result=None;failures=[];original_capture=[];seccomp_fd=None;actual=custody.actual;primary=None
    try:
        self.ledger.guard('after_original_reservation_before_paths')
        # Revalidate the exact complete immutable deployment before EACH launch.
        # Protection against concurrent privileged host mutation is a separate
        # independent deployment qualification, not inferred from these hashes.
        from .protocol import exact_tree
        exact_tree(self.runtime,self.deployment['runtime_inventory'])
        for member in self.deployment['runtime_inventory']:stream_capture(self.runtime,member['path'],expected=member,ledger=self.ledger,cap=self.ledger.limits['per_file_bytes'])
        workspace=Directory(str(workspace));observer=Directory(str(observer_root))
        need(workspace.path!=observer.path and not any(observer.path==workspace.path/p for p in ('observer','output')),'private observation is not a candidate capability')
        self.quota.budget=self.ledger;self.quota.acquire(job['id'],workspace,job['reservation'],self.ledger.limits);self.quota.assign_observer(job['id'],observer)
        for name in ('tmp','shm'):os.mkdir(name,0o700,dir_fd=workspace.fd)
        profile=self.deployment['io_observer'];fields(profile,('kind','strace','seccomp','qualification'),'concrete qualified syscall observer')
        for key in ('strace','seccomp'):stream_capture(self.source_root,profile[key]['path'],expected=profile[key],ledger=self.ledger,cap=self.ledger.limits['per_file_bytes'])
        digest(profile['qualification']);cgroup=Cgroup(self.deployment['cgroup_root'],job['id'],self.ledger.limits)
        seccomp_fd=os.open(self.source_root.path/profile['seccomp']['path'],os.O_RDONLY|os.O_NOFOLLOW)
        args=self.build_argv(entry,inputs,workspace.path,request,response)
        split=args.index('--');args[split:split]=['--seccomp',str(seccomp_fd)]
        trace=observer.path/'trace.txt';args=[str(self.source_root.path/profile['strace']['path']),'-f','-qq','-s','0','-e','trace=read,pread64,readv,preadv,preadv2,mmap','-o',str(trace),*args]
        def enter():
            _control(cgroup.path/'cgroup.procs',os.getpid())
            cpu=max(1,(job['reservation']['cpu_milliseconds']+999)//1000);resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_FSIZE,(self.ledger.limits['per_file_bytes'],self.ledger.limits['per_file_bytes']));resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
            os.set_inheritable(seccomp_fd,True)
        result=observe_child(args,cwd=str(workspace.path),environment={'LANG':'C','LC_ALL':'C','PATH':'/nonexistent'},stdout_path=observer.path/'stdout.txt',stderr_path=observer.path/'stderr.txt',deadline=self.ledger.deadline,requested=job['reservation'],limits=self.ledger.limits,cgroup=cgroup,preexec=enter,pass_fds=(seccomp_fd,),custody=custody)
        custody.observed(result);actual=custody.actual;self.ledger.guard('after_actual_original_reap_before_capture')
    except BaseException as exc:primary=exc;failures.append({'phase':'original_worker_lifecycle',**observation(exc)})
    finally:
        # Every actual observer file gets an original prefix/pin even when one
        # later capture fails. We never replace it with a retry's output.
        if isinstance(locals().get('observer'),Directory):
            for name in ('trace.txt','stdout.txt','stderr.txt'):
                try:
                    path=observer.path/name
                    if not path.exists():continue
                    size=path.stat(follow_symlinks=False).st_size
                    capture=stream_capture(observer,name,size=size,cap=self.ledger.limits['per_file_bytes'],ledger=self.ledger);original_capture.append({'name':name,'disposition':'retained_original','capture':capture})
                    if name=='trace.txt':
                        member=capture['source'];raw=read_metadata(observer,member,cap=self.ledger.limits['metadata_bytes'],ledger=self.ledger);parsed=traced_read_bytes(raw.decode('utf8').splitlines());actual['read_bytes']=parsed['known_logical_read_bytes'];actual['observer_complete']=parsed['complete'] and result is not None and actual['descendants_closed']
                        if not parsed['complete']:failures.append({'kind':'incomplete_original_syscall_observation','original':parsed})
                except BaseException as exc:original_capture.append({'name':name,'disposition':'capture_failed_original_retained','failure':observation(exc)});failures.append({'phase':'original_observer_capture',**observation(exc)})
        if isinstance(locals().get('workspace'),Directory):
            try:
                if job['id'] in self.quota.jobs and self.quota.jobs[job['id']]['phase']=='admitted':
                    quota_observation=self.quota.observe(job['id'],workspace);original_capture.append({'role':'actual_kernel_project_quota','observation':quota_observation})
                else:failures.append({'kind':'original_project_quota_not_admitted'})
                disk=tree_usage(workspace.path,file_limit=self.ledger.limits['files'],per_file_limit=self.ledger.limits['per_file_bytes'],byte_limit=job['reservation']['scratch_bytes']+job['reservation']['output_bytes']);actual['output_bytes']=disk['bytes']+sum(r['capture']['source']['bytes'] for r in original_capture if 'capture' in r)
                # Workspace output and temporary extents are conservatively
                # both charged; this does not claim two physical copies.
                actual['scratch_bytes']=max(actual['scratch_bytes'] or 0,disk['bytes'])
            except BaseException as exc:failures.append({'phase':'final_original_extent',**observation(exc)})
        if cgroup is not None:
            try:
                sample=cgroup.sample()
                if sample['populated']:cgroup.kill();failures.append({'kind':'original_cgroup_still_populated'});actual['descendants_closed']=False
                actual['cpu_milliseconds']=sample['cpu_milliseconds'];actual['peak_resident_bytes']=sample['peak_resident_bytes'];actual['gpu_milliseconds']=0;actual['peak_gpu_resident_bytes']=0
                cgroup.cleanup()
            except BaseException as exc:failures.append({'phase':'original_cgroup_final_custody',**observation(exc)})
        for label,handle in (('workspace',locals().get('workspace')),('observer',locals().get('observer'))):
            if isinstance(handle,Directory):
                try:handle.close()
                except BaseException as exc:failures.append({'phase':label+'_original_close',**observation(exc)})
        if seccomp_fd is not None:
            try:os.close(seccomp_fd)
            except BaseException as exc:failures.append({'phase':'original_seccomp_close',**observation(exc)})
        actual['artifacts']=original_capture;actual['failures']+=failures
        if result is None:actual['observer_complete']=False
        custody.record.update(observation=actual,original_process=result if result is not None else custody.record['original_process'],source_identity=job['source_identity'],input_identity=job['input_identity'],original_capture_dispositions=original_capture,scientific_qualification_claim=False,original_kernel_quota=self.quota.jobs.get(job['id']))
        try:custody.record['original_budget_record']=self.ledger.end(record,actual)
        except BaseException as exc:
            custody.record['secondary_failures'].append({'phase':'original_final_accounting',**observation(exc)})
            if primary is None:primary=exc
        custody.record['primary_failure']=None if primary is None else observation(primary)
    if primary is not None:
        primary.original_process_custody=custody.record
        raise primary
    self.ledger.guard('after_original_executor_close_accounting_before_return')
    return custody.record


LinuxCPUExecutor.run=_executor_run
