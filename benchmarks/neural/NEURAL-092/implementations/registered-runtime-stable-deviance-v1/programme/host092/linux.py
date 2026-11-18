"""Actual cgroup/runtime consumers with original ordinary error ownership.

No native effects occur on import. Source construction never invokes these
kernel/process functions; actual Linux qualification remains unissued.
"""
import os,time,signal,subprocess,stat,resource
from pathlib import Path
from .storage import Store,ErrorOwner,encode,decode

def write(path,value,errors=None):
    errors=ErrorOwner()if errors is None else errors;start=len(errors.events);stream=None
    def body():
        nonlocal stream
        stream=open(path,'w',encoding='ascii');stream.write(str(value))
    try:errors.call('kernel_write',body)
    except BaseException:pass
    finally:
        if stream is not None:errors.cleanup('kernel_write_close',stream.close)
    errors.finish(start)

def read(path,errors=None):
    errors=ErrorOwner()if errors is None else errors;start=len(errors.events);stream=None;value=None
    def body():
        nonlocal stream,value
        stream=open(path,'r',encoding='ascii');value=stream.read(65537)
        if len(value)>65536:raise ValueError('bounded kernel observation')
    try:errors.call('kernel_read',body)
    except BaseException:pass
    finally:
        if stream is not None:errors.cleanup('kernel_read_close',stream.close)
    errors.finish(start);return value

def populated(path,errors=None):
    fields=dict(x.split()for x in read(path/'cgroup.events',errors).splitlines())
    if 'populated'not in fields:raise RuntimeError('missing actual cgroup populated observation')
    return fields['populated']!='0'
def metrics(path,errors=None):
    names=('cpu.stat','memory.current','memory.peak','memory.events','pids.current','pids.events','io.stat','cgroup.events')
    return {n:read(path/n,errors)for n in names}

class Cgroup:
    def __init__(self,parent,name,limits,errors):
        self.errors=errors;self.path=Path(parent)/name;self.owned=False;self.children=[];self.before=None
        self.path.mkdir(mode=0o700);self.owned=True
        available=set(read(self.path/'cgroup.controllers',errors).split())
        if not {'cpu','memory','pids','io'}<=available:raise RuntimeError('required cgroup-v2 controllers unavailable')
        write(self.path/'memory.max',limits['memory_bytes'],errors);write(self.path/'memory.swap.max',0,errors)
        write(self.path/'pids.max',limits['pids'],errors);write(self.path/'cpu.max',str(limits['cpu_quota_us'])+' '+str(limits['cpu_period_us']),errors)
        write(self.path/'cgroup.subtree_control','+cpu +memory +pids +io',errors);self.before=metrics(self.path,errors)
    def leaf(self,name):
        p=self.path/name;p.mkdir(mode=0o700);self.children.append(p);return p
    def drain(self,seconds):
        write(self.path/'cgroup.kill',1,self.errors);end=time.monotonic()+seconds
        while populated(self.path,self.errors):
            if time.monotonic()>=end:raise TimeoutError('owned cgroup failed to drain')
            time.sleep(.01)
        return metrics(self.path,self.errors)
    def remove_empty(self):
        start=len(self.errors.events)
        if populated(self.path,self.errors):raise RuntimeError('no removal of populated group')
        for p in reversed(self.children):
            def remove_child(p=p):
                if p.exists():p.rmdir()
            self.errors.cleanup('cgroup_child_remove',remove_child)
        def remove_parent():
            self.path.rmdir();self.owned=False
        self.errors.cleanup('cgroup_parent_remove',remove_parent)
        self.errors.finish(start)

def acquire_group(parent,name,limits,owner,errors):
    g=Cgroup.__new__(Cgroup);g.path=Path(parent)/name;g.owned=False;g.children=[];g.errors=errors;owner.append(g)
    errors.call('cgroup_acquire',lambda:Cgroup.__init__(g,parent,name,limits,errors));return g

def stop_process(proc,errors,where,seconds):
    """Independent signal/wait occurrences, retaining an earlier wait failure."""
    errors.cleanup(where+'_kill',lambda:os.killpg(proc.pid,signal.SIGKILL))
    errors.cleanup(where+'_wait',lambda:proc.wait(timeout=seconds))

def control(profile,argv,log,control_leaf,ledger,errors):
    start=len(errors.events);stream=None;proc=None;rc=None
    def body():
        nonlocal stream,proc,rc
        ledger.take('files',1);ledger.take('write_bytes',profile['runtime_output_bytes'])
        stream=open(log,'xb')
        def limits():
            write(Path(control_leaf)/'cgroup.procs',os.getpid())
            resource.setrlimit(resource.RLIMIT_FSIZE,(profile['runtime_output_bytes'],profile['runtime_output_bytes']))
        proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C'},close_fds=True,start_new_session=True,preexec_fn=limits)
        try:rc=errors.call('control_original_wait',lambda:proc.wait(timeout=profile['control_seconds']))
        except BaseException:stop_process(proc,errors,'control_process_stop',profile['control_seconds'])
        if rc is not None and rc!=0:raise RuntimeError('runtime control failed: '+str(rc))
    try:errors.call('runtime_control',body)
    except BaseException:pass
    finally:
        if stream is not None:errors.cleanup('runtime_control_log_close',stream.close)
    errors.finish(start);return rc

def oci_config(p,leaf,view,code,out,argv):
    limits=p['candidate_limits']
    return {'ociVersion':'1.0.2','root':{'path':p['rootfs'],'readonly':True},'hostname':'neural092','process':{'terminal':False,'user':{'uid':65534,'gid':65534},'args':argv,'env':['PATH=/usr/bin:/bin','LANG=C','PYTHONDONTWRITEBYTECODE=1','HOME=/tmp'],'cwd':'/candidate','noNewPrivileges':True,'capabilities':{'bounding':[],'effective':[],'inheritable':[],'permitted':[],'ambient':[]},'rlimits':[{'type':'RLIMIT_FSIZE','hard':p['runtime_output_bytes'],'soft':p['runtime_output_bytes']},{'type':'RLIMIT_NOFILE','hard':256,'soft':256}]},'mounts':[{'destination':'/proc','type':'proc','source':'proc','options':['nosuid','noexec','nodev']},{'destination':'/tmp','type':'tmpfs','source':'tmpfs','options':['nosuid','nodev','noexec','size='+str(p['runtime_output_bytes'])]},{'destination':'/packet','type':'bind','source':str(view),'options':['rbind','ro','nosuid','nodev','noexec']},{'destination':'/candidate','type':'bind','source':str(code),'options':['rbind','ro','nosuid','nodev']},{'destination':'/output','type':'bind','source':str(out),'options':['rbind','rw','nosuid','nodev','noexec']}],'linux':{'namespaces':[{'type':x}for x in ('pid','network','ipc','uts','mount','cgroup')],'cgroupsPath':'/'+str(leaf.relative_to('/sys/fs/cgroup')),'resources':{'memory':{'limit':limits['memory_bytes'],'swap':limits['memory_bytes']},'pids':{'limit':limits['pids']},'cpu':{'quota':limits['cpu_quota_us'],'period':limits['cpu_period_us']},'devices':[{'allow':False,'access':'rwm'}]},'maskedPaths':['/proc/kcore','/proc/keys','/proc/timer_list','/proc/sysrq-trigger'],'readonlyPaths':['/proc/sys','/proc/irq','/proc/bus']}}


class Runtime:
    def __init__(self,profile,work,group,ledger,errors):
        self.profile=profile;self.work=Path(work);self.group=group;self.ledger=ledger;self.errors=errors;self.records=[];self.pending=[]
        self.state=self.work/'runc-state';self.state.mkdir(mode=0o700)
    def run(self,name,view,code,output,argv):
        p=self.profile;errors=self.errors;start=len(errors.events)
        rid=p['run_id']+'-'+name;leaf=self.group.path/name
        if leaf not in self.group.children:raise RuntimeError('leaf must be parent-owned before run')
        rec={'name':name,'runtime_id':rid,'entered':False,'returncode':None,'stopped':False,'observation':None,'failure_start':start}
        self.records.append(rec);self.pending.append(rid)
        bundle=self.work/('bundle-'+name);config_store=stream=proc=None
        def body():
            nonlocal config_store,stream,proc
            bundle.mkdir(mode=0o700);out=Path(output)
            if not out.is_mount():raise RuntimeError('original supervisor bounded output mount required')
            config=oci_config(p,leaf,view,code,out,argv)
            config_store=Store(str(bundle),self.ledger,True,errors)
            config_store.put('config.json',encode(config))
            # Explicit owner covers config readback and close as well as log.
            errors.call('runtime_config_close',config_store.close)
            self.ledger.take('files',1);self.ledger.take('write_bytes',p['runtime_output_bytes'])
            stream=(self.work/(name+'-runtime.log')).open('xb')
            def fsize():resource.setrlimit(resource.RLIMIT_FSIZE,(p['runtime_output_bytes'],p['runtime_output_bytes']))
            proc=subprocess.Popen([p['runc']['path'],'--root',str(self.state),'run','--keep','--bundle',str(bundle),rid],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C'},close_fds=True,start_new_session=True,preexec_fn=fsize)
            rec['entered']=True;rec['pid']=proc.pid
            try:rec['returncode']=errors.call('runtime_original_wait',lambda:proc.wait(timeout=p['wall_seconds']))
            except BaseException:stop_process(proc,errors,'runtime_process_stop',p['control_seconds'])
            if rec['returncode']is not None and rec['returncode']!=0:raise RuntimeError('candidate failed; stopped partial output retained separately')
        try:errors.call('runtime_run',body)
        except BaseException:pass
        finally:
            # Leaf belongs to the parent even if log/Popen fails. Drain does not
            # manufacture a successful process; rec.entered remains separate.
            def drain():
                write(leaf/'cgroup.kill',1,errors);deadline=time.monotonic()+p['control_seconds']
                while populated(leaf,errors):
                    if time.monotonic()>deadline:raise TimeoutError('candidate stop unknown')
                    time.sleep(p['poll_seconds'])
                rec['observation']=metrics(leaf,errors);rec['stopped']=True
            errors.cleanup('candidate_drain_observation',drain)
            if stream is not None:errors.cleanup('runtime_log_close',stream.close)
            if config_store is not None:errors.cleanup('runtime_config_store_retirement',config_store.close)
        rec['failures']=errors.events[start:]
        errors.finish(start)
        if not rec['entered']or rec['returncode']!=0 or not rec['stopped']:raise RuntimeError('incomplete original runtime disposition')
        return rec

def delete_owned_runtimes(profile,work,ids,errors,control_leaf,ledger):
    state=Path(work)/'runc-state'
    for name in ids:
        def retire(name=name):
            rid=profile['run_id']+'-'+name
            if not(state/rid).exists():return
            control(profile,[profile['runc']['path'],'--root',str(state),'delete',rid],Path(work)/('delete-'+name+'.log'),control_leaf,ledger,errors)
        errors.cleanup('runtime_delete_'+name,retire)
