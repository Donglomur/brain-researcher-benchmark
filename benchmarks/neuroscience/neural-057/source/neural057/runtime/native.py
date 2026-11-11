"""Native source with original deadlines, retirement, partial outputs and custody.

Real execution requires a separately qualified local Linux daemon and cgroup.
Invented transport controls do not qualify native or scientific execution.
"""
import base64
import math
import re
import uuid
from pathlib import Path
from .common import require,parse,pin,FailureCarrier,encoded,diagnostic_type
from .cgroup import Cgroup
from .native_providers import NativeProviders

CAPS={'fit':{'model.bin':268435456,'selected_method.json':8388608,'operations.json':8388608},
      'infer':{'prediction.json':4194304,'operations.json':8388608}}

class Phase:
    def __init__(self,cell,kind,origin,deadline):
        self.cell=cell;self.kind=kind;self.origin=origin;self.deadline=deadline
        self.resources=[];self.commands=[];self.outputs={};self.errors=FailureCarrier()
        self.natural=None;self.closed=False;self.cpu=None;self.cgroup=None;self.id=None
        self.durable=False;self.publication=None;self.capture=None;self.capture_wire=None
        self.schedule=None;self.accounting=None;self.accounting_complete=False
        self.deployment=None;self.receipt_attempts=[];self.retirement=None
        self.failure_receipt_durable=False
        self.broker=None
        self.command_manifest=None
        self.resource_policy=None
    def document(self):
        summary=None
        if self.capture is not None:
            if type(self.capture)is dict:
                summary={k:self.capture.get(k)for k in('schema','kind','namespace','errors','complete')}
                files=self.capture.get('files')
                summary['files']={k:({f:v for f,v in d.items()if f!='base64'}if type(d)is dict else {'invalid_record_type':diagnostic_type(d)})for k,d in files.items()}if type(files)is dict else {'invalid_files_type':diagnostic_type(files)}
            else:summary={'invalid_capture_type':diagnostic_type(self.capture)}
        from .resource_policy import states,unobserved
        disposition=states(self.resource_policy,'known_closed'if self.closed else'unresolved','measured_original_complete'if self.accounting_complete else'unavailable','unavailable_before_protected_grade','unavailable_before_independent_semantic_review','unavailable_before_complete_cell')
        return {'resource_dispositions':disposition,'expected_unobserved_native_quantities':unobserved(self.id,self.resource_policy)if self.resource_policy is not None else[],'id':self.id,'cell':self.cell,'kind':self.kind,'origin':self.origin,'deadline':self.deadline,
                'resources':self.resources,'command_count':len(self.commands),'command_manifest':self.command_manifest,
                'all_original_command_objects_retained':True,
                'outputs':self.outputs,'natural':self.natural,'all_native_resources_closed':self.closed,
                'cpu_seconds':self.cpu,'cgroup':self.cgroup,'errors':self.errors.document(),
                'durable_publication':self.publication,'capture':summary,'capture_wire':self.capture_wire,
                'schedule':self.schedule,'accounting':self.accounting,
                'accounting_complete':self.accounting_complete,'retirement':self.retirement,
                'accounting_scope':'selected_measured_vector_only','resource_policy':self.resource_policy,
                'native_total_logical_io_complete':False,
                'deployment':self.deployment,'receipt_attempts':self.receipt_attempts,
                'trusted_broker':None if self.broker is None else self.broker.summary()}

class PhaseCustody:
    """Caller-owned original phase reference, bound by the producer before effects."""
    __slots__=('phase',)
    def __init__(self):self.phase=None
    def bind(self,phase):
        require(type(phase) is Phase and self.phase is None,'one exact original phase custody')
        self.phase=phase

class NativeFailure(Exception):
    def __init__(self,phase):
        self.phase=phase
        super().__init__('original native phase failed')

def one(value):
    require(type(value)is list and len(value)==1 and type(value[0])is dict,'one exact native object')
    return value[0]

def full_id(value):
    require(type(value)is str and re.fullmatch('[0-9a-f]{64}',value),'full original native ID')
    return value

def admitted_container(value,record,profile,parent,mounts,volume,destination,command,extra_volumes=None):
    """The participant and trusted holder have the same complete admission."""
    require(value['Id']==record['id'] and value['Name']=='/'+record['name'],'original container ID/name')
    h=value['HostConfig'];c=value['Config']
    require(c['Labels'].get('org.neurobench.n057')==record['owner'],'original ownership label')
    require(c['Image']==profile['image'] and c['User']=='65534:65534','exact image/user')
    require(c['Entrypoint']==['python'] and c['Cmd']==command,'exact entrypoint/arguments')
    require(not c.get('Volumes'),'no image-declared volumes')
    require(not c.get('Healthcheck') or c['Healthcheck'].get('Test')==['NONE'],'no implicit health process')
    require(h['NetworkMode']=='none' and h['ReadonlyRootfs'] and not h['Privileged'],'actual isolation')
    require(h['CgroupParent']==parent and h['CgroupnsMode']=='private' and h['IpcMode']=='private'
            and h.get('PidMode','')=='' and h.get('UTSMode','')=='','private namespaces')
    require(not h.get('Devices') and not h.get('DeviceRequests') and not h.get('CapAdd'),'no extra devices/capabilities')
    require(h['CapDrop']==['ALL'] and h['SecurityOpt'] in
            (['no-new-privileges'],['no-new-privileges:true']),'privilege restrictions')
    require(h['Memory']==h['MemorySwap']==profile['memory_bytes'] and h['PidsLimit']==profile['pids']
            and h['NanoCpus']==1000000000,'actual native quotas')
    require(h['RestartPolicy']=={'Name':'no','MaximumRetryCount':0}
            and h['LogConfig']=={'Type':'none','Config':{}} and not h.get('AutoRemove'),'no restart/log/implicit removal')
    require(not h.get('PortBindings'),'no published ports')
    require(h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size='+str(profile['scratch_bytes'])},'exact scratch')
    limits={x['Name']:(x['Soft'],x['Hard'])for x in h['Ulimits']}
    require(len(h['Ulimits'])==3 and limits=={'core':(0,0),'nofile':(128,128),'fsize':(536870912,536870912)},'finite original ulimits')
    rows=value['Mounts'];require(len({m['Destination']for m in rows})==len(rows),'unique destinations')
    binds={m['Destination']:(m['Source'],m['RW'])for m in rows if m['Type']=='bind'}
    volumes=[m for m in rows if m['Type']=='volume']
    selected={} if volume is None else {destination:(volume,destination=='/output')}
    selected.update(extra_volumes or {})
    require(len(rows)==len(mounts)+len(selected) and binds=={k:(str(v),w)for k,(v,w)in mounts.items()},'exact readonly binds')
    require(len(volumes)==len(selected) and {m['Destination']:(m['Name'],m['RW']) for m in volumes}==selected,'only original bounded phase volumes')
    return value

class DockerHost:
    def __init__(self,profile,runner,journal,budget,carrier):
        self.profile=profile;self.runner=runner;self.journal=journal;self.budget=budget;self.carrier=carrier
        self.counter=0;self.originals=[]
        require(profile['schema']=='neural057-linux-cgroupfs-no-service-profile-v1'and profile['resource_policy']==budget.resource_policy and budget.resource_policy is not None,'exact selected prospective measured native profile')
        require(re.fullmatch(r'sha256:[0-9a-f]{64}',profile['image']),'exact cached image')
        require(profile['pull']=='never' and profile['network']=='none','no network or installation')
        require(type(profile['daemon_id'])is str and bool(profile['daemon_id']),'selected daemon ID')
        require(type(profile['docker_host'])is str and profile['docker_host'].startswith('unix:///')
                and not any(c in profile['docker_host']for c in '\n\r\0'),'local daemon socket')
        require(Path(profile['docker_binary']).is_absolute(),'literal qualified Docker binary')
        reserve=profile['closure_reserve_seconds']
        require(type(reserve)in(int,float) and math.isfinite(reserve) and reserve>0,'original closure reserve')
        for name in('memory_bytes','pids','scratch_bytes'):
            require(type(profile[name])is int and profile[name]>0,'positive native bound')
        require(profile['services']=='none','N057 no provider/tool capability or broker-volume allocation')

    def phase(self,cell,kind,programme,view,model,output,source_root,deadline,action_origin,role='participant',bank=None,broker=None,custody=None):
        observed=Phase(cell,kind,action_origin,deadline)
        if custody is not None:
            require(type(custody) is PhaseCustody,'exact caller-owned phase custody')
            custody.bind(observed)
        self.originals.append(observed);self.carrier.retain(observed)
        observed.resource_policy=self.budget.resource_policy
        owner='n057-'+uuid.uuid4().hex;observed.id=owner
        scope=None;scope_record=None;actor=None;holder=None;volume=None;counter=0
        receipt_reservation=None;output_capacity=None;output=Path(output);actor_end=None;actor_ok=False
        requests=None;request_reservation=None;request_bytes=0;request_files=0;provider_runtime=None;observed.broker=broker
        def fail(exc,stage):
            observed.errors.fail(exc,stage);self.carrier.fail(exc,stage+':'+owner)
        def command(args,cap=131072,end=None,poll_service=None):
            nonlocal counter
            limit=deadline if end is None else end
            require(limit<=deadline,'no extension of original phase deadline')
            ident=owner+'-'+str(counter);counter+=1;before=len(self.runner.originals)
            try:
                result=self.runner.run(ident,[self.profile['docker_binary'],'--host',self.profile['docker_host'],*args],limit,cap,poll_service=poll_service)
                self.budget.check('after native original control publication',limit)
                return bytes(result.stdout)
            finally:
                for result in self.runner.originals[before:]:
                    if not any(result is x for x in observed.commands):observed.commands.append(result)
        def record(kind_,name):
            row={'kind':kind_,'name':name,'owner':owner,'attempted':False,'acknowledged':False,
                 'id':None,'closed':True,'disposition':'not_dispatched','observations':[]}
            observed.resources.append(row);return row
        def inspect_original(row):
            value=one(parse(command(['container','inspect',row['id'] or row['name']])))
            full_id(value['Id'])
            require(value['Name']=='/'+row['name'] and value['Config']['Labels'].get('org.neurobench.n057')==owner,'only original named/labelled resource')
            require(row['id'] is None or row['id']==value['Id'],'same original ID')
            row['id']=value['Id'];row['observations'].append({'id':value['Id'],'state':dict(value['State'])})
            return value
        def retire(row):
            if row is None or not row['attempted']:return True
            try:
                state=inspect_original(row)['State']
                if state['Running']:
                    command(['container','kill','--signal','KILL',row['id']],4096);row['forced']=True
                if state['Status']=='created' and not state['Running']:
                    row['wait_disposition']='created_no_original_process_to_wait'
                else:
                    waited=command(['container','wait',row['id']],4096).strip()
                    require(re.fullmatch(b'[0-9]+',waited),'original wait acknowledgment')
                    row['wait_exit']=int(waited)
                state=inspect_original(row)['State']
                require(not state['Running'] and state['Pid']==0 and state['Status']in('exited','dead','created'),'retired before removal')
                if 'wait_exit'in row:require(row['wait_exit']==state['ExitCode'],'original wait agrees with exact terminal state')
                if row is actor and observed.natural is not None:
                    require(all(state[k]==observed.natural[k]for k in('Status','Running','Dead','Pid','ExitCode','OOMKilled','Error')),'same original actor terminal before removal')
                row['terminal_state']=dict(state)
                require(command(['container','rm',row['id']],4096).strip()==row['id'].encode(),'original removal acknowledgment')
                absent=command(['container','ls','-a','--no-trunc','--filter','name=^/'+row['name']+'$','--format','{{.ID}}'],4096).strip()
                require(absent==b'','absent after acknowledged original removal')
                row.update(closed=True,disposition='original_retired_removed_absent');return True
            except BaseException as exc:
                # Lost create acknowledgment plus an empty listing cannot prove
                # that a still-pending original daemon request cannot create later.
                row['disposition']='unresolved_original_creation_or_retirement';fail(exc,'retire-'+row['kind']);return False
        try:
            require(kind in CAPS and role in('participant','reference'),'literal phase/role')
            self.budget.admit('before next original native phase',deadline)
            require(broker is None and bank is None,'N057 fixed no-service profile: no broker, provider or tool bank for either role')
            now=self.budget.clock()
            require(self.budget.origin<=action_origin<=now<deadline<=self.budget.deadline,'original action clock')
            reserve=self.profile['closure_reserve_seconds'];actor_end=deadline-reserve
            require(action_origin<actor_end and now<actor_end,'reserve carved from original action span')
            observed.schedule={'origin':action_origin,'actor_deadline':actor_end,'closure_deadline':deadline,
                               'closure_reserve_seconds':reserve,'extra_allowance':0}
            require(not any(not p.accounting_complete for p in self.originals[:-1]),'unresolved native accounting blocks further launches')
            receipt_reservation=owner+'-native-receipt';self.budget.reserve(receipt_reservation,131072,2)
            require(not output.exists() and output.parent.is_dir() and output.is_relative_to(self.journal.root),'fresh trusted output')
            output.mkdir(mode=0o700)
            info=parse(command(['info','--format','{{json .}}'],end=actor_end))
            require(info['ID']==self.profile['daemon_id'] and info['OSType']=='linux'
                    and info['CgroupVersion']=='2' and info['CgroupDriver']=='cgroupfs','exact qualified local Linux daemon')
            observed.deployment={'daemon_id':info['ID'],'endpoint':self.profile['docker_host'],'image':self.profile['image']}
            image=one(parse(command(['image','inspect',self.profile['image']],end=actor_end)))
            require(image['Id']==self.profile['image'] and not image['Config'].get('Volumes'),'cached image without implicit volumes')
            require(not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE'],'no health process')
            scope=Cgroup(self.profile['delegated_cgroup_root'],owner,self.budget,deadline);observed.errors.retain(scope)
            scope_record=record('cgroup',str(scope.path));scope_record.update(attempted=True,closed=False,disposition='creation_pending')
            scope.create(self.profile['memory_bytes'],self.profile['pids'])
            scope_record.update(acknowledged=True,disposition='created')
            parent=str(scope.path.relative_to('/sys/fs/cgroup'))
            volume=record('volume',owner+'-output')
            require(command(['volume','ls','--filter','name=^'+volume['name']+'$','--format','{{.Name}}'],end=actor_end).strip()==b'','fresh volume')
            extent=301989888 if kind=='fit' else 16777216
            output_capacity=owner+'-output-live-capacity';self.budget.reserve_capacity(output_capacity,extent,16)
            options='size='+str(extent)+',nr_inodes=16,uid=65534,gid=65534,mode=0770,nosuid,nodev,noexec'
            volume.update(attempted=True,closed=False,disposition='creation_pending')
            answer=command(['volume','create','--driver','local','--label','org.neurobench.n057='+owner,
                            '--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,volume['name']],4096,actor_end).decode().strip()
            require(answer==volume['name'],'original volume acknowledgment');volume['acknowledged']=True
            vi=one(parse(command(['volume','inspect',volume['name']],end=actor_end)))
            require(vi['Name']==volume['name'] and vi['Driver']=='local' and vi['Labels'].get('org.neurobench.n057')==owner
                    and vi['Options']=={'type':'tmpfs','device':'tmpfs','o':options},'bounded original output volume')
            if broker is not None:
                requests=record('volume',owner+'-requests')
                require(command(['volume','ls','--filter','name=^'+requests['name']+'$','--format','{{.Name}}'],end=actor_end).strip()==b'','fresh original broker request volume')
                request_bytes=self.profile['broker_request_volume_bytes'];request_files=self.profile['broker_request_inode_limit']
                # Only live extent/inodes are bounded. Repeated native writes
                # are unobserved and never inferred from this capacity.
                request_reservation=owner+'-request-capacity';self.budget.reserve_capacity(request_reservation,request_bytes,request_files)
                options='size='+str(request_bytes)+',nr_inodes='+str(request_files)+',uid=65534,gid=65534,mode=0770,nosuid,nodev,noexec'
                requests.update(attempted=True,closed=False,disposition='creation_pending')
                answer=command(['volume','create','--driver','local','--label','org.neurobench.n057='+owner,'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,requests['name']],4096,actor_end).decode().strip()
                require(answer==requests['name'],'original broker volume acknowledgment');requests['acknowledged']=True
                vi=one(parse(command(['volume','inspect',requests['name']],end=actor_end)))
                require(vi['Name']==requests['name'] and vi['Driver']=='local' and vi['Labels'].get('org.neurobench.n057')==owner and vi['Options']=={'type':'tmpfs','device':'tmpfs','o':options},'exact original request bounds')
            mounts={'/submission/program.py':(Path(programme),False),'/input':(Path(view),False),'/runtime':(Path(source_root),False)}
            if model is not None:mounts['/model/model.bin']=(Path(model),False)
            if bank is not None:mounts['/tool-bank']=(Path(bank),False)
            holder_mounts={'/capture_entry.py':(Path(source_root)/'capture_entry.py',False)}
            if broker is not None:
                mounts['/broker/replies']=(broker.replies,False);mounts['/broker/LEASE.json']=(broker.visible_path,False)
            for path,_ in [*mounts.values(),*holder_mounts.values()]:
                require(path.is_absolute() and not any(x.is_symlink()for x in(path,*path.parents)),'literal mount')
                require(not any(c in str(path)for c in ',\n\r\0'),'unambiguous mount operand')
            def argv_for(row,binds,destination,args,extras=None):
                argv=['container','create','--pull','never','--name',row['name'],'--label','org.neurobench.n057='+owner,
                      '--cgroup-parent',parent,'--cpus','1','--memory',str(self.profile['memory_bytes']),
                      '--memory-swap',str(self.profile['memory_bytes']),'--pids-limit',str(self.profile['pids']),
                      '--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534',
                      '--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none',
                      '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size='+str(self.profile['scratch_bytes']),
                      '--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize=536870912:536870912']
                for dest,(path,writable)in binds.items():argv+=['--mount','type=bind,src='+str(path)+',dst='+dest+(''if writable else ',readonly')]
                selected={} if destination is None else {destination:(volume['name'],destination=='/output')}
                selected.update(extras or {})
                for dest,(vol,writable) in selected.items():argv+=['--mount','type=volume,src='+vol+',dst='+dest+('' if writable else ',readonly')+',volume-nocopy']
                for key in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):argv+=['--env',key+'=1']
                return argv+['--entrypoint','python',self.profile['image'],*args]
            holder=record('container',owner+'-holder');holder.update(attempted=True,closed=False,disposition='creation_pending')
            holder_cmd=['-I','-B','/capture_entry.py','hold',kind]
            holder_extra={} if requests is None else {'/requests':(requests['name'],False)}
            actor_extra={} if requests is None else {'/broker/requests':(requests['name'],True)}
            holder['id']=full_id(command(argv_for(holder,holder_mounts,'/capture',holder_cmd,holder_extra),4096,actor_end).decode().strip());holder['acknowledged']=True
            admitted_container(one(parse(command(['container','inspect',holder['id']],end=actor_end))),holder,self.profile,parent,holder_mounts,volume['name'],'/capture',holder_cmd,holder_extra)
            require(command(['container','start',holder['id']],4096,actor_end).strip()==holder['id'].encode(),'original holder start acknowledgment')
            actor=record('container',owner);actor.update(attempted=True,closed=False,disposition='creation_pending')
            actor_cmd=['-I','-B','/runtime/phase_entry.py',kind,role]
            actor['id']=full_id(command(argv_for(actor,mounts,'/output',actor_cmd,actor_extra),4096,actor_end).decode().strip());actor['acknowledged']=True
            admitted_container(one(parse(command(['container','inspect',actor['id']],end=actor_end))),actor,self.profile,parent,mounts,volume['name'],'/output',actor_cmd,actor_extra)
            require(command(['container','start',actor['id']],4096,actor_end).strip()==actor['id'].encode(),'original actor start acknowledgment')
            if broker is not None:provider_runtime=NativeProviders(self,observed,scope,parent,actor_end,command,record,retire,argv_for,admitted_container)
            while True:
                self.budget.check('actor poll before reserved closure',actor_end);cpu=scope.sample()
                require(self.budget.cpu+self.budget.own_cpu()+cpu<=self.budget.limits['cpu_seconds'],'whole native CPU allowance')
                value=one(parse(command(['container','inspect',actor['id']],end=actor_end)))
                require(value['Id']==actor['id'] and value['Config']['Labels'].get('org.neurobench.n057')==owner,'same polled actor')
                if not value['State']['Running']:break
                if broker is not None:
                    wire=command(['exec',holder['id'],'python','-I','-B','/capture_entry.py','request',str(broker.sequence)],2097152,actor_end)
                    captured=parse(wire);require(captured['schema']=='n057-broker-request-capture-v3' and captured['sequence']==broker.sequence,'actual holder request identity')
                    require(not captured['errors'],'bounded original request namespace')
                    if captured['status']=='complete':
                        raw=base64.b64decode(captured['base64'],validate=True);require(pin(raw)==captured['pin'],'actual complete original request bytes')
                        broker.dispatch(raw,provider_runtime)
                    else:require(captured['status']=='pending','no unstable or partial request admitted')
            state=value['State'];observed.natural={k:state[k]for k in('Status','Running','Dead','Pid','ExitCode','OOMKilled','Error')}
            actor_ok=(state['Status']=='exited' and not state['Dead'] and not state['OOMKilled'] and not state['Error'] and state['ExitCode']==0 and state['Pid']==0)
            require(actor_ok,'original natural actor zero')
        except BaseException as exc:fail(exc,'native')
        finally:
            retired=retire(actor);observed.retirement={'actor_retired':retired,'before_trusted_capture':True}
            if broker is not None:
                pending={'no_unprocessed_request':False,'reason':'original_holder_or_actor_retirement_unavailable'}
                if retired and holder is not None and holder['acknowledged']:
                    try:
                        raw=command(['exec',holder['id'],'python','-I','-B','/capture_entry.py','request',str(broker.sequence)],2097152)
                        pending=parse(raw);pending['no_unprocessed_request']=pending['status']=='pending' and not pending['errors'] and not pending['partial_names']
                        self.journal.write(owner+'-BROKER_FINAL_REQUEST_CAPTURE.json',raw)
                    except BaseException as exc:fail(exc,'broker-final-request-capture')
                try:broker.close(pending)
                except BaseException as exc:fail(exc,'broker-original-retirement')
            if actor is not None and actor['attempted'] and retired and holder is not None and holder['acknowledged']:
                before=len(observed.commands);wire=None
                try:
                    self.budget.check('before post-retirement capture',deadline)
                    cap=402653184 if kind=='fit'else 25165824
                    wire=command(['exec',holder['id'],'python','-I','-B','/capture_entry.py','capture',kind],cap)
                    observed.capture_wire={**pin(wire),'original_command_id':observed.commands[-1].id,'transport_complete':True}
                    observed.capture=parse(wire);observed.errors.retain(observed.capture)
                    require(type(observed.capture)is dict and set(observed.capture)=={'schema','kind','files','namespace','errors','complete','partial_bytes_are_not_valid_outputs'},'closed trusted capture transport')
                    require(observed.capture['schema']=='n057-phase-capture-v3' and observed.capture['kind']==kind,'trusted capture identity')
                except BaseException as exc:
                    fail(exc,'native-capture')
                    if len(observed.commands)>before:
                        original=observed.commands[-1]
                        observed.capture_wire={'original_command_id':original.id,'stdout':pin(original.stdout),'stderr':pin(original.stderr),
                                               'transport_complete':True if wire is not None else None,'reply_admitted':False,'prefix_retained_in_original_process':True}
            retire(holder)
            output_volume=volume
            for volume in (volume,requests):
              if volume is not None and volume['attempted']:
                try:
                    vi=one(parse(command(['volume','inspect',volume['name']])))
                    require(vi['Name']==volume['name'] and vi['Labels'].get('org.neurobench.n057')==owner,'only owned original volume')
                    command(['volume','rm',volume['name']],4096)
                    require(command(['volume','ls','--filter','name=^'+volume['name']+'$','--format','{{.Name}}'],4096).strip()==b'','original volume absent')
                    volume.update(closed=True,disposition='original_owned_removed_absent')
                except BaseException as exc:volume['disposition']='unresolved_original_creation_or_removal';fail(exc,'volume-cleanup')
            if request_reservation in self.budget.capacity_reservations and requests is not None and requests['closed']:
                try:self.budget.release_capacity(request_reservation)
                except BaseException as exc:fail(exc,'request-volume-accounting')
            if output_capacity in self.budget.capacity_reservations and output_volume is not None and output_volume['closed']:
                try:self.budget.release_capacity(output_capacity)
                except BaseException as exc:fail(exc,'output-volume-accounting')
            if scope is not None and scope.created:
                try:
                    observed.cgroup=scope.finish();observed.cpu=observed.cgroup['cpu_seconds']
                    scope_record.update(closed=True,disposition='original_subtree_empty_removed')
                except BaseException as exc:
                    fail(exc,'native-final-counters');observed.cgroup=scope.final
                    if scope.final is not None and scope.final.get('cpu_complete'):observed.cpu=scope.final['cpu_seconds']
                    try:scope.emergency_kill()
                    except BaseException as secondary:fail(secondary,'native-emergency')
            elif not any(r['attempted']for r in observed.resources):observed.cpu=0.0
            observed.closed=all(r['closed']for r in observed.resources);end=None
            try:end=self.budget.clock()
            except BaseException as exc:fail(exc,'native-final-clock')
            costs={'kind':role,'cpu_seconds':observed.cpu,'wall_seconds':None if end is None else end-action_origin,
                   'wall_scope':'original_native_resource_lifetime_before_host_capture_publication',
                    'native_final':observed.cgroup,'all_native_resources_closed':observed.closed,'resource_policy':self.budget.resource_policy,
                    'memory_peak_bytes':observed.cgroup.get('memory_peak_bytes')if observed.cgroup is not None else 0 if not any(r['attempted']for r in observed.resources)else None,
                    'native_logical_io':{'scope':'complete actor/holder/provider logical I/O',
                                         'read_bytes':None,'write_bytes':None,'files':None,'complete':False,
                                         'reason':'CPU, closure and live storage capacity do not observe cumulative native I/O'}};observed.accounting=costs
            try:
                self.budget.physical(owner,costs)
                observed.accounting_complete=(observed.cpu is not None and end is not None and costs['memory_peak_bytes']is not None and observed.closed and self.budget.resource_policy is not None and not self.budget.unknown)
                if end is None:self.budget.unknown.append({'operation':owner,'quantity':'wall_seconds'})
                self.budget.check('after original final counters/removal',deadline)
            except BaseException as exc:fail(exc,'native-final-accounting')
            if not actor_ok:fail(ValueError('no complete natural original actor'),'native-actor-disposition')
            if not observed.closed:fail(ValueError('unresolved original native resource custody'),'native-containment')
        if observed.capture is not None:
            try:
                expected=CAPS[kind];files=observed.capture['files']
                require(type(files)is dict and set(files)<=set(expected),'only original capture names')
                for name,d in files.items():
                    self.budget.check('before opaque prefix decoding',deadline)
                    require(type(d['bytes'])is int and 0<=d['bytes']<=expected[name],'bounded captured prefix')
                    require(type(d['base64'])is str and len(d['base64'])<=4*((d['bytes']+2)//3),'bounded base64 extent')
                    body=base64.b64decode(d['base64'],validate=True)
                    require(pin(body)=={'bytes':d['bytes'],'sha256':d['sha256']},'exact original captured prefix')
                    good=d.get('complete')is True
                    require(not good or len(body)>0,'nonempty complete output')
                    dest=output/(name if good else name+'.partial')
                    row={'path':str(dest),'bytes':len(body),'sha256':d['sha256'],'complete':good,'usable':False,
                         'source_status':d.get('status'),'capture':None,'original_prefix':True};observed.outputs[name]=row
                    previous=len(self.journal.records)
                    try:row['capture']=self.journal.write(str(dest.relative_to(self.journal.root)),body)
                    finally:
                        if row['capture']is None and len(self.journal.records)>previous:row['capture']=self.journal.records[-1]
                require(observed.capture.get('complete')is True and set(files)==set(expected)
                        and all(r['complete']for r in observed.outputs.values()),'complete original output ABI')
            except BaseException as exc:fail(exc,'native-captured-output-publication')
        else:fail(ValueError('original capture unavailable'),'native-output-disposition')
        try:self.budget.check('before native receipt construction',deadline)
        except BaseException as exc:fail(exc,'native-final-admission')
        try:
            observed.command_manifest=self.journal.json(owner+'-ORIGINAL_COMMANDS.json',
                {'original_phase':owner,'commands':[x.document() for x in observed.commands],
                 'no_command_reconstructed_from_claims':True})
        except BaseException as exc:fail(exc,'native-command-manifest')
        if receipt_reservation is not None:
            try:
                body=encoded(observed.document());require(len(body)<=65536,'reserved native receipt extent')
                observed.receipt_attempts.append({'name':owner+'-NATIVE.json','expected_bytes':len(body)})
                observed.publication=self.journal.write(owner+'-NATIVE.json',body,reservation=receipt_reservation,emergency=observed.errors.first is not None)
                observed.durable=True
            except BaseException as exc:
                fail(exc,'native-receipt')
                try:
                    minimal={'id':owner,'status':'failed_native_receipt','closed':observed.closed,
                             'original_first_error_type':diagnostic_type(observed.errors.first[1]),'command_count':len(observed.commands),
                             'full_original_phase_retained_in_host':True,'resources':observed.resources}
                    body=encoded(minimal);require(len(body)<=65536,'bounded failure receipt')
                    observed.receipt_attempts.append({'name':owner+'-NATIVE_FAILURE.json','expected_bytes':len(body)})
                    observed.publication=self.journal.write(owner+'-NATIVE_FAILURE.json',body,reservation=receipt_reservation,emergency=True)
                    observed.failure_receipt_durable=True
                except BaseException as secondary:fail(secondary,'native-failure-receipt')
            finally:
                # Unused reserved capacity is released, incurred counters never reset.
                self.budget.reservations.pop(receipt_reservation,None)
        try:self.budget.check('after complete native publication',deadline)
        except BaseException as exc:fail(exc,'native-post-publication')
        for row in observed.outputs.values():
            row['usable']=observed.errors.first is None and observed.closed and observed.durable and row['complete']
        if observed.errors.first is not None or not observed.durable:raise NativeFailure(observed)
        return observed
