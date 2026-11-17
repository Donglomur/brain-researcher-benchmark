"""Concrete isolated container source execution and exact original observations.

No provider/native method is executed on import. Source support does not qualify
the image, daemon, host namespace, physical mounts or scientific dependencies.
"""
import hashlib,json,math,os,stat,time
from pathlib import Path
import common as c
from transport.common import AdapterError,CaseBudget,authenticate,file_pin
from transport.process import DockerSandbox

class Bridge:
    MAP={'source_read':'read_bytes','artifact_write':'write_bytes','provider_calls':'provider_requests','provider_tokens':'provider_tokens','stream_bytes':'stream_bytes','tool_calls':'native_processes'}
    def __init__(self,parent):
        self.parent=parent;self.origin_monotonic=parent.origin;self.deadline_monotonic=parent.end
    def check_clock(self):self.parent.check_clock()
    def charge(self,name,amount=1):
        c.need(name in self.MAP,'known adapter budget counter');self.parent.charge(self.MAP[name],amount)
    def snapshot(self):return self.parent.snapshot()

class ObservedDocker(DockerSandbox):
    def __init__(self,config,budget,namespace_root,whole):
        super().__init__(config,budget,namespace_root);self.whole=whole;self.commands=[]
    def command(self,arguments,*,seconds=None,monitor=None):
        self.whole.charge('host_processes',1)
        started=time.monotonic();record={'arguments':list(arguments),'started_monotonic':started,'status':'entered'};self.commands.append(record)
        try:
            result=super().command(arguments,seconds=seconds,monitor=monitor)
            record.update(status='completed',observation=result['observation'],stdout=c.pin(result['stdout']),stderr=c.pin(result['stderr']))
            # Exact original streams retained by the caller's immutable receipt.
            record['stdout_hex']=result['stdout'].hex();record['stderr_hex']=result['stderr'].hex()
            return result
        except BaseException as e:
            record.update(status='failed',failure_type=type(e).__name__,evidence=getattr(e,'evidence',None));raise
        finally:record['ended_monotonic']=time.monotonic()

def validate_config(config):
    expected=('docker_binary','docker_endpoint','image_digest','python','user','pids_limit','memory_bytes','cpus','tmpfs_bytes','tool_seconds','cleanup_seconds','stream_cap_bytes','workspace_cap_bytes','workspace_entry_cap','poll_seconds')
    c.exact(config,expected);c.descriptor(config['docker_binary'])
    c.need(type(config['docker_endpoint'])is str and config['docker_endpoint'].startswith('unix:///'),'selected local daemon endpoint only')
    c.need(type(config['image_digest'])is str and config['image_digest'].startswith('sha256:')and len(config['image_digest'])==71,'immutable already-present image digest')
    c.digest(config['image_digest'][7:]);c.absolute(config['python'])
    c.need(os.geteuid()!=0 and config['user']==str(os.geteuid())+':'+str(os.getegid()),'selected nonroot host/container UID and GID match for owned artifacts')
    for k in('pids_limit','memory_bytes','tmpfs_bytes','stream_cap_bytes','workspace_cap_bytes','workspace_entry_cap'):c.integer(config[k],1)
    for k in('cpus','tool_seconds','cleanup_seconds','poll_seconds'):c.need(c.finite(config[k],0)>0,'positive native limit')
    return config

def durable_workspace(root,config,budget):
    """Bounded complete metadata traversal and flush, with zero body reads."""
    root=c.absolute(str(root));c.need(not any(p.is_symlink()for p in(root,*root.parents)),'ordinary current work root')
    pending=[root];directories=[];entries=files=extent=0
    while pending:
        directory=pending.pop();directories.append(directory);budget.check_clock()
        with os.scandir(directory)as children:
            for child in children:
                entries+=1;c.need(entries<=config['workspace_entry_cap'],'complete namespace entry bound')
                budget.check_clock();s=child.stat(follow_symlinks=False);p=Path(child.path)
                if stat.S_ISDIR(s.st_mode):pending.append(p)
                else:
                    c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary owned output only');files+=1;extent+=s.st_size
                    c.need(extent<=config['workspace_cap_bytes'],'whole output storage bound')
                    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                    try:
                        before=os.fstat(fd);fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
                        c.need(all(getattr(s,k)==getattr(before,k)for k in fields),'same owned output before fsync');os.fsync(fd)
                        after=os.fstat(fd);named=p.lstat();c.need(all(getattr(s,k)==getattr(after,k)==getattr(named,k)for k in fields),'stable owned output after fsync')
                    finally:os.close(fd)
                    budget.check_clock()
    for directory in reversed(directories):c.sync_directory(directory);budget.check_clock()
    return {'schema':'neural010-native-workspace-durability-v1','root':str(root),'entries':entries,'files':files,'directories':len(directories),'bytes':extent,'file_and_directory_fsync_completed':True,'body_bytes_read_for_durability':0,'entry_cap':config['workspace_entry_cap'],'byte_cap':config['workspace_cap_bytes'],'physical_filesystem_guarantees_independently_qualified':False}

def admit_durability(record,config):
    d=record['workspace_durability'];c.exact(d,('schema','root','entries','files','directories','bytes','file_and_directory_fsync_completed','body_bytes_read_for_durability','entry_cap','byte_cap','physical_filesystem_guarantees_independently_qualified'))
    c.need(d['schema']=='neural010-native-workspace-durability-v1'and d['root']==record['work_root'],'same complete native work root')
    c.need(type(d['entry_cap'])is int and d['entry_cap']==config['workspace_entry_cap']and type(d['byte_cap'])is int and d['byte_cap']==config['workspace_cap_bytes'],'original complete namespace bounds')
    c.integer(d['entries'],0,config['workspace_entry_cap']);c.integer(d['files'],0,d['entries']);c.integer(d['directories'],1,d['entries']+1);c.integer(d['bytes'],0,config['workspace_cap_bytes'])
    c.need(d['files']+d['directories']==d['entries']+1 and d['file_and_directory_fsync_completed']is True and type(d['body_bytes_read_for_durability'])is int and d['body_bytes_read_for_durability']==0 and d['physical_filesystem_guarantees_independently_qualified']is False,'complete source-owned flush metadata without creating deployment qualification')
    return d

def natural(observed):
    c.need(type(observed)is dict,'actual native observation')
    o=observed['observation'];container=observed['container_observation']
    c.need(type(o['natural_exit_code'])is int and o['natural_exit_code']==0 and type(o['observed_leader_exit_code'])is int and o['observed_leader_exit_code']==0,'strict natural host integer zero')
    c.need(o['process_reaped']is True and o['process_group_absent']is True and o['streams_closed']is True and o['observer_selector_closed']is True,'complete original host closure')
    c.need(o['child_mutation_attempted']is False and o['failure']is None and o['quarantine_token']is None and o['separate_authorized_inspection_required']is False,'no cleanup-to-success/unknown host survivor')
    c.need(o['ended_monotonic']<=o['normal_deadline_monotonic']<=o['original_deadline_monotonic'],'original normal and parent deadline')
    c.need(container['failure']is None and container['owned_container_absent']is True,'independently observed exact owned-container retirement')
    state=container['final_inspection']['State']
    c.need(state.get('Status')=='exited'and state['Running']is False and state['OOMKilled']is False and type(state['ExitCode'])is int and state['ExitCode']==0,'container naturally exited, not merely created or stopped')
    return True

class Native:
    def __init__(self,config,phase_limits,whole,output_root,source_files):
        self.config=validate_config(config);self.phase_limits=phase_limits;self.whole=whole;self.root=c.absolute(str(output_root));self.source_files=source_files;self.records=[]
        c.need(type(source_files)is list and source_files,'literal approved source closure')
        for d in source_files:c.descriptor(d)
        c.need(len({d['path']for d in source_files})==len(source_files),'unique source mount identities')
    def run(self,job_id,script,args,input_files,*,kind='reference',opaque_inputs=(),workspace=(),worker_io=None):
        c.need(type(job_id)is str and job_id and type(args)is list and all(type(v)is str for v in args),'literal native job command')
        c.need(kind in('reference','tool','fixed','clock'),'known source native role')
        if kind=='reference':
            c.exact(worker_io,('read_bytes','write_bytes'))
            for key in('read_bytes','write_bytes'):self.whole.charge(key,c.integer(worker_io[key],1))
        else:c.need(worker_io is None,'arbitrary candidate I/O has no false source-instrumented measurement')
        if kind=='tool':self.whole.charge('tool_processes',1)
        self.whole.charge('native_cpu_seconds',math.ceil(self.config['cpus']*(self.config['tool_seconds']+3*self.config['cleanup_seconds'])))
        ordinal=len(self.records);directory=c.new_directory(self.root/('%06d'%ordinal),self.whole)
        work=c.new_directory(directory/'work',self.whole)
        c.need(type(workspace)in(list,tuple),'explicit prior tool artifact roster')
        copied=[];seen=set()
        for item in workspace:
            c.exact(item,('relative_path','source'));relative=item['relative_path']
            c.need(type(relative)is str and relative and not relative.startswith('/')and all(q not in('','.','..')for q in relative.split('/'))and relative not in seen,'unique ordinary relative workspace artifact')
            seen.add(relative);target=work/relative
            for parent in reversed(target.parents):
                if parent!=work and parent.is_relative_to(work)and not parent.exists():c.new_directory(parent,self.whole)
            copied.append(c.copy_stream(item['source'],target,self.whole,[Path(item['source']['path']).parent]))
        child_budget=CaseBudget(Bridge(self.whole),self.phase_limits,self.config['tool_seconds']+3*self.config['cleanup_seconds'])
        selected={}
        for d in [*self.source_files,*input_files]:
            c.descriptor(d);c.need(d['path']not in selected or c.typed_equal(selected[d['path']],d),'consistent same input pin')
            selected[d['path']]=d
        c.need(script in selected and script.endswith('.py'),'literal source-owned or sealed candidate script')
        # Only exact files are exposed, never a private ancestor directory.
        # Identical host/container spelling keeps immutable receipt paths valid.
        opaque=set(opaque_inputs);c.need(opaque<=set(selected),'declared worker-only label operands')
        opaque_stamps={}
        def stamp(d):
            p=c.absolute(d['path']);c.need(not any(x.is_symlink()for x in(p,*p.parents)),'ordinary worker-only label view')
            s=p.stat();c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==d['bytes'],'exact worker-only label extent')
            return tuple(getattr(s,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink'))
        for d in selected.values():
            if d['path']in opaque:opaque_stamps[d['path']]=stamp(d)
            else:authenticate(d,child_budget)
        mounts=[(d['path'],d['path'],True)for d in selected.values()]+[(str(work),'/work',False),(str(work),str(work),False)]
        record={'schema':'neural010-native-job-v1','job_id':job_id,'kind':kind,'ordinal':ordinal,'source_files':self.source_files,'inputs':list(selected.values()),'worker_only_label_inputs':sorted(opaque),'host_prepared_label_body_reads':0,'work_root':str(work),'workspace_inputs':copied,'script':script,'args':list(args),'status':'entered','original_origin':self.whole.origin,'phase_original_deadline':child_budget.deadline_monotonic,'cpu_reservation_is_not_unknown_survivor_cost_bound':True}
        record['workspace_origin']=list(workspace)
        record['worker_io_reservation']=worker_io;record['worker_io_reservation_refunded']=False
        record['arbitrary_native_io_measured']=False
        self.records.append(record);record['intent']=c.publish_json(directory/'INTENT.json',record,self.whole)
        docker=ObservedDocker(self.config,child_budget,directory,self.whole)
        try:
            actual_args=[a.replace('{WORK}',str(work))for a in args]
            observed=docker.run_python(script,mounts=mounts,work_root=work,args=actual_args);natural(observed)
            for d in selected.values():
                if d['path']in opaque:c.need(stamp(d)==opaque_stamps[d['path']],'worker-only view metadata unchanged; worker authenticates body')
                else:authenticate(d,child_budget)
            record['workspace_durability']=durable_workspace(work,self.config,self.whole)
            record.update(status='completed',observation=observed['observation'],container_observation=observed['container_observation'],returncode=0,natural_completion=True,unknown_survivors=False)
            c.publish(directory/'stdout.bin',observed['stdout'],self.whole);c.publish(directory/'stderr.bin',observed['stderr'],self.whole)
            self.whole.check_clock()
        except BaseException as error:
            record.update(status='failed',failure_type=type(error).__name__,failure_message=str(error)[:2000],failure_evidence=getattr(error,'evidence',None),natural_completion=False,unknown_survivors=True)
            raise
        finally:
            record['host_commands']=docker.commands;record['resources']=docker.resources;record['budget']=child_budget.snapshot()
            # A failed deadline can prevent this write. The earlier durable
            # intent remains; independent observer must preserve uncertainty.
            try:record['receipt']=c.publish_json(directory/'NATIVE.json',record,self.whole)
            except BaseException:
                record['receipt_publication_uncertain']=True
                if record['status']=='completed':raise
        self.whole.check_clock();return record
