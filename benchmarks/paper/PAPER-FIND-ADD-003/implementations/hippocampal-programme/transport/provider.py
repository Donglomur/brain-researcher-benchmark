"""Concrete owned local Docker phase provider. Definition is not run authority.

The constructor binds operator-owned exposure approvals and transport source.
Calls launch only locally available immutable images; no pull/install/network.
Actual producer logical I/O and peak RSS are deliberately not invented.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import time
import uuid
from . import archive
from .bounds import Meter, body, publish, fsync_dir, tree, mount_identity, relative, local_metadata
from .contract import validate_request, validate_exposure, output_files
from .engine import (Docker, LABEL, need, pin, encoded, parse, path, descriptor, call,
                     inspect, owned, resource_inventory, retire, mounts_argv,
                     validate_natural_exit, validate_cli_records)

READY_OPTIONS='rw,nosuid,nodev,noexec,size=4096,mode=0700,uid=65534,gid=65534'
HOLDER_MEMORY=134217728
ENGINE_FILES={'__init__.py','engine.py','bounds.py','contract.py','archive.py','holder.py','provider.py'}


def caps(inventory_bytes):
    result={k:131072 for k in ('image','volume_admit','admit_holder','admit_producer','producer_exit','cleanup_inspect')}
    result.update({k:4096 for k in ('volume_create','create_holder','create_producer','holder_start','holder_ready','producer_start','producer_wait','cleanup_kill','cleanup_wait','cleanup_remove')})
    result.update({a+'_'+b+'_'+c:8192 for a in ('before','cleanup','absence') for b in ('container','volume') for c in ('owner','name')})
    result['artifact_inventory']=inventory_bytes
    return result


def scratch_options(size):return 'rw,nosuid,nodev,noexec,size='+str(size)+',mode=0770,uid=65534,gid=65534'


def fixed_environment(holder):
    env={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
    if not holder:env.update(HOME='/work',TMPDIR='/work')
    return env


def environment_map(values):
    need(type(values) is list,'Explicit complete image/container environment')
    out={}
    for value in values:
        need(type(value) is str and '=' in value and '\0' not in value,'Ordinary environment entry')
        key,val=value.split('=',1);need(key and key not in out,'Unique exact environment keys');out[key]=val
    return out


def create_args(item,holder,mounts,request,holder_command):
    r=request['resources'];command=holder_command if holder else request['command']
    memory=HOLDER_MEMORY if holder else r['memory_bytes'];nano=1000000000 if holder else r['cpu_nanos'];pids=64 if holder else r['pids']
    fsize=256 if holder else r['max_file_bytes']
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],
          '--cpus',str(nano//1000000000)+'.'+str(nano%1000000000).zfill(9),'--memory',str(memory),'--memory-swap',str(memory),
          '--pids-limit',str(pids),'--network','none','--cgroupns','private','--ipc','private','--read-only',
          '--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no',
          '--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128',
          '--ulimit','fsize='+str(fsize)+':'+str(fsize),'--init=false','--workdir','/' if holder else '/work']
    args+=['--tmpfs','/ready:'+READY_OPTIONS] if holder else ['--tmpfs','/work:'+scratch_options(r['scratch_bytes'])]
    for key,value in fixed_environment(holder).items():args+=['--env',key+'='+value]
    return args+mounts_argv(mounts)+['--entrypoint',command[0],request['image'],*command[1:]]


def admit_container(v,item,holder,mounts,request,holder_command,image_env):
    owned(v,item,item['owner']);h=v['HostConfig'];cfg=v['Config'];r=request['resources']
    command=holder_command if holder else request['command']
    need(v['Image']==cfg['Image']==request['image'] and cfg['User']=='65534:65534'
         and cfg['Entrypoint']==[command[0]] and cfg['Cmd']==command[1:] and cfg['WorkingDir']==('/' if holder else '/work'),'Exact image/user/argv/cwd')
    need(environment_map(cfg['Env'])=={**environment_map(image_env),**fixed_environment(holder)},'Exact inherited and overridden image environment')
    for k,want in {'Memory':HOLDER_MEMORY if holder else r['memory_bytes'],'MemorySwap':HOLDER_MEMORY if holder else r['memory_bytes'],
                   'NanoCpus':1000000000 if holder else r['cpu_nanos'],'PidsLimit':64 if holder else r['pids'],'ShmSize':16777216}.items():
        need(type(h[k]) is int and h[k]==want,'Exact typed resource '+k)
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['CgroupnsMode']=='private'
         and h['LogConfig']['Type']=='none' and h['IpcMode']=='private' and h.get('PidMode') in ('','private'),'Isolated namespaces/no logs')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests')
         and h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no'
         and h['AutoRemove'] is False and h.get('Init') is False,'No capabilities/restarts/implicit init')
    actual={}
    for row in v['Mounts']:
        need(row['Destination'] not in actual and type(row['RW']) is bool,'Unique strictly typed mounts')
        actual[row['Destination']]=(row['Type'],row['Name'] if row['Type']=='volume' else row['Source'],row['RW'])
    need(actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'Exact complete role mount set')
    need(all(rw is False for kind,_,rw in mounts.values() if kind=='bind'),'No writable host bind')
    tmp={'/ready':READY_OPTIONS} if holder else {'/work':scratch_options(r['scratch_bytes'])}
    need(h.get('Tmpfs')==tmp,'Exact private bounded scratch')
    lim={}
    for row in h['Ulimits']:
        need(row['Name'] not in lim and type(row['Soft']) is int and type(row['Hard']) is int,'Typed ulimits')
        lim[row['Name']]=(row['Soft'],row['Hard'])
    size=256 if holder else r['max_file_bytes']
    need(lim=={'core':(0,0),'nofile':(128,128),'fsize':(size,size)},'Exact prospective file limits')


class Provider:
    def __init__(self,control_root,quarantine_root,docker_binary,docker_socket,engine_source_pin,
                 trusted_exposures,source_read_limit,host_write_limit):
        self.control_root,self.quarantine_root=path(control_root),path(quarantine_root)
        need(self.control_root.is_dir() and self.quarantine_root.is_dir()
             and self.control_root!=self.quarantine_root
             and not self.control_root.is_relative_to(self.quarantine_root) and not self.quarantine_root.is_relative_to(self.control_root),'Private preprovisioned disjoint roots')
        for root in (self.control_root,self.quarantine_root):
            need(stat.S_IMODE(root.stat().st_mode)&0o077==0,'Operator-private roots')
        self.binary,self.socket=str(path(docker_binary)),str(path(docker_socket))
        need(type(trusted_exposures) is dict and trusted_exposures,'Operator-pinned exposure approval registry')
        self.exposures=dict(trusted_exposures);self.engine_pin=descriptor(engine_source_pin)
        self.source_root=Path(__file__).resolve().parent
        self.read_limit,self.write_limit=source_read_limit,host_write_limit
        need(type(source_read_limit) is int and source_read_limit>0 and type(host_write_limit) is int and host_write_limit>0,'Original whole-provider ceilings')
        self.read_used=self.write_used=0

    def engine_auth(self,meter):
        raw=body(self.source_root/'SOURCE_MANIFEST.json',self.engine_pin,meter,262144)
        manifest=parse(raw)
        need(type(manifest) is dict and set(manifest)=={'schema','files'} and manifest['schema']=='h_transport_source_manifest_v1'
             and set(manifest['files'])==ENGINE_FILES,'Closed concrete transport implementation')
        for name,p in sorted(manifest['files'].items()):body(self.source_root/name,p,meter,1048576,False)
        return self.engine_pin

    def observe(self,phase_id,request_sha256,expected_receipt_pin,original_deadline):
        need(re.fullmatch('[A-Za-z0-9_-]{1,96}',phase_id) and re.fullmatch('[0-9a-f]{64}',request_sha256),'Exact observer identity')
        descriptor(expected_receipt_pin)
        # Read-only independent observer path, with an externally retained pin.
        need(expected_receipt_pin['bytes']+1<=self.read_limit-self.read_used,'Prospective observer read allocation')
        meter=Meter(expected_receipt_pin['bytes']+1,1,original_deadline)
        try:
            raw=body(self.control_root/phase_id/'RECEIPT.json',expected_receipt_pin,meter,expected_receipt_pin['bytes'])
            value=parse(raw);need(value['phase_id']==phase_id and value['request_sha256']==request_sha256
                                  and value['timing']['original_deadline']==original_deadline,'Observer phase/request/original-clock join')
            return {'receipt':value,'receipt_pin':pin(raw),'read_bytes':meter.read_bytes,'independent_candidate_channel':True}
        finally:self.read_used+=meter.read_bytes

    def execute_phase(self,request,mounts,original_deadline,journal):
        validate_request(request,mounts,original_deadline);started=time.monotonic();r=request['resources']
        span=sum(r[k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
        end=started+span;need(started>=request['clock']['origin'] and end<=min(original_deadline,request['clock']['phase_deadline']),
                            'Complete phase allowance remains within original clock')
        setup_end=started+r['setup_seconds'];work_end=end-r['cleanup_seconds']
        read_cap=min(r['source_read_bytes'],self.read_limit-self.read_used)
        write_cap=min(r['host_write_bytes'],self.write_limit-self.write_used)
        need(read_cap==r['source_read_bytes'] and write_cap==r['host_write_bytes'],'Full prospective phase I/O grant remains')
        meter=Meter(read_cap,write_cap,end);request_raw=encoded(request);request_pin=pin(request_raw)
        control=self.control_root/request['phase_id'];output=self.quarantine_root/request['phase_id']
        need(not control.exists() and not output.exists(),'No phase reuse or automatic retry')
        control.mkdir(mode=0o700);output.mkdir(mode=0o700);fsync_dir(control.parent);fsync_dir(output.parent)
        journal_index=0
        def record(name,value):
            nonlocal journal_index
            row={'schema':'h_transport_journal_v1','phase_id':request['phase_id'],'request_sha256':request_pin['sha256'],
                 'index':journal_index,'event':name,'value':value}
            raw=encoded(row);p=publish(control/(str(journal_index).zfill(6)+'-'+name+'.json'),raw,meter)
            journal_index+=1;journal(name,{'record':row,'pin':p})
        prefix='h-'+uuid.uuid4().hex[:24]
        planned={label:{'kind':kind,'name':prefix+'-'+label,'owner':prefix+'/'+label,'attempted':False,'acknowledged':False}
                 for label,kind in (('volume','volume'),('holder','container'),('producer','container'))}
        ownership_pin=None
        d=Docker(self.binary,self.socket,max_calls=r['max_cli_calls'],reply_budget=r['max_cli_bytes'],phase_caps=caps(r['inventory_bytes']),
                 publish=record,account_read=meter.read,reserve_read=meter.ensure_read)
        items=[];closures=[];natural=None;capture=None;before=None;after=None;error=None;closed_before=False
        producer=None;producer_end=None;exit_observation_error=None
        def item(label,kind):
            value=planned[label].copy();need(value['kind']==kind,'Exact predeclared resource kind')
            record('RESOURCE-INTENT',{'resource':value.copy(),'creation_obligation_until_closed':True});items.append(value);return value
        def fresh(value):need(resource_inventory(d,value,value['owner'],setup_end,'before_'+value['kind'])==[],'Fresh exact owned namespace')
        def container(value,holder,binding,command):
            fresh(value);value['attempted']=True;record('CREATE-ATTEMPT',value.copy())
            label='holder' if holder else 'producer'
            ident=call(d,create_args(value,holder,binding,request,command),setup_end,'create_'+label,4096,12).decode('ascii').strip()
            need(re.fullmatch('[a-f0-9]{64}',ident),'Exact returned container ID');value.update(id=ident,acknowledged=True)
            record('RESOURCE-ACK',value.copy());admit_container(inspect(d,'container',ident,setup_end,'admit_'+label),value,holder,binding,request,command,image['Config'].get('Env') or [])
        try:
            engine=self.engine_auth(meter)
            ownership={'schema':'h_phase_ownership_v1','phase_id':request['phase_id'],'request_pin':request_pin,
                       'engine_source_pin':self.engine_pin,'original_deadline':original_deadline,'phase_deadline':end,
                       'attempt_prefix':prefix,'resources':planned}
            ownership_pin=publish(control/'OWNERSHIP.json',encoded(ownership),meter)
            record('OWNERSHIP',{'ownership_pin':ownership_pin,'ownership':ownership})
            exposure_path=self.exposures.get(request['exposure']['sha256']);need(exposure_path is not None,'Operator preapproved exposure only')
            exposure=parse(body(exposure_path,request['exposure'],meter,2097152));validate_exposure(exposure,request,mounts)
            before={target:tree(desc,meter) for target,desc in sorted(mounts.items())}
            request_file=control/'REQUEST.json';publish(request_file,request_raw,meter,mode=0o444)
            policy={'schema':'h_holder_policy_v1','phase_id':request['phase_id'],'role':request['role'],
                    'file_cap':r['max_file_bytes'],'total_cap':r['max_output_bytes'],'files':r['max_files'],'directories':r['max_directories']}
            policy_raw=encoded(policy);policy_pin=publish(control/'POLICY.json',policy_raw,meter,mode=0o444)
            need(stat.S_ISSOCK(path(self.socket).stat().st_mode),'Existing local Unix daemon socket')
            image=parse(call(d,['image','inspect',request['image'],'--format','{{json .}}'],setup_end,'image'))
            need(image['Id']==request['image'] and not image['Config'].get('Volumes') and
                 (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),
                 'Existing exact image; no implicit volumes/health process')
            volume=item('volume','volume');fresh(volume);volume['attempted']=True;record('CREATE-ATTEMPT',volume.copy())
            options='size='+str(r['max_output_bytes'])+',uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
            reply=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,volume['name']],setup_end,'volume_create',4096).decode('ascii').strip()
            need(reply==volume['name'],'Exact volume acknowledgement');volume['acknowledged']=True;record('RESOURCE-ACK',volume.copy())
            state=inspect(d,'volume',volume['name'],setup_end,'volume_admit');owned(state,volume,volume['owner'])
            need(state['Driver']=='local' and state['Options']=={'type':'tmpfs','device':'tmpfs','o':options},'Exact bounded private tmpfs volume')
            holder=item('holder','container')
            suffix=['--owner-token',holder['owner'],'--role',request['role'],'--policy','/trusted/POLICY.json','--policy-sha256',policy_pin['sha256']]
            holder_command=['/usr/local/bin/python','-I','-B','/trusted/holder.py','hold',*suffix]
            hm={'/trusted/holder.py':('bind',self.source_root/'holder.py',False),'/trusted/POLICY.json':('bind',control/'POLICY.json',False),'/capture':('volume',volume['name'],False)}
            container(holder,True,hm,holder_command);call(d,['container','start',holder['id']],setup_end,'holder_start',4096)
            while True:
                ready=parse(call(d,['container','exec',holder['id'],'/usr/local/bin/python','-I','-B','/trusted/holder.py','ready',*suffix],setup_end,'holder_ready',4096))
                need(type(ready) is dict and set(ready)=={'ready'} and type(ready['ready']) is bool,'Exact readiness record')
                if ready['ready']:break
                need(time.monotonic()+.1<setup_end,'Readiness inside original setup');time.sleep(.05)
            producer=item('producer','container')
            bindings={target:('bind',path(desc['path']),False) for target,desc in mounts.items()}
            bindings.update({'/request.json':('bind',request_file,False),'/output':('volume',volume['name'],True)})
            container(producer,False,bindings,holder_command)
            producer_end=min(work_end-r['capture_seconds'],time.monotonic()+r['producer_seconds'])
            need(producer_end>time.monotonic()+1,'Producer interval remains')
            call(d,['container','start',producer['id']],setup_end,'producer_start',4096)
            raw=d(['container','wait',producer['id']],producer_end,'producer_wait',4096)
            state=inspect(d,'container',producer['id'],work_end,'producer_exit');owned(state,producer,producer['owner'])
            natural={k:state['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
            need(raw.strip()==str(natural['ExitCode']).encode(),'Wait/inspect exact exit join');validate_natural_exit(natural)
            closure=retire(d,producer,work_end);closures.append(closure);need(closure['closed'] is True,'Producer removed before archive capture')
            items.remove(producer);closed_before=True
            capture_end=min(work_end,time.monotonic()+r['capture_seconds'])
            def inventory():
                value=parse(call(d,['container','exec',holder['id'],'/usr/local/bin/python','-I','-B','/trusted/holder.py','inventory',*suffix],capture_end,'artifact_inventory',r['inventory_bytes']))
                need(value.get('schema')=='h_capture_inventory_v1' and value.get('owner')==holder['owner'] and value.get('role')==request['role'],'Exact holder inventory binding')
                return value
            first=inventory();rows={x['name']:x for x in first['files']}
            need(len(rows)==len(first['files']) and 1<=len(rows)<=r['max_files'] and len(first['directories'])+1<=r['max_directories'],'Bounded inventory cardinality')
            for name,row in rows.items():relative(name);need(type(row['bytes']) is int and 0<=row['bytes']<=r['max_file_bytes'],'Bounded inventoried extent')
            need(sum(x['bytes'] for x in rows.values())==first['total_bytes']<=r['max_output_bytes'],'Exact total inventoried bytes')
            manifest_name=request['output']['manifest'];need(manifest_name in rows and rows[manifest_name]['bytes']<=r['manifest_bytes'],'Bounded complete output envelope present')
            for row in first['directories']:
                relative(row['name']);(output/row['name']).mkdir(parents=True,exist_ok=True,mode=0o700)
            transfers={}
            def transfer(name):
                value=archive.capture(self.socket,holder['id'],name,rows[name]['bytes'],output/name,meter,capture_end)
                transfers[name]=value;return value['file']
            manifest_pin=transfer(manifest_name)
            manifest=parse(body(output/manifest_name,manifest_pin,meter,r['manifest_bytes']))
            declared=output_files(manifest,request,request_pin['sha256'],first)
            for name,want in sorted(declared.items()):need(transfer(name)==want,'Exact complete captured file pin')
            need(encoded(first)==encoded(inventory()),'Unchanged full post-closure inventory before/after archive')
            for directory in sorted((output/x['name'] for x in first['directories']),key=lambda p:len(p.parts),reverse=True):fsync_dir(directory)
            fsync_dir(output)
            capture={'files':{manifest_name:manifest_pin,**declared},'total_bytes':first['total_bytes'],
                     'inventory_pin':pin(encoded(first)),'transfers':transfers,'complete':True}
        except BaseException as exc:
            error={'type':type(exc).__name__,'message':str(exc)[:512],'cleanup_errors':getattr(exc,'cleanup_errors',[])}
        finally:
            if error is not None and producer is not None and producer.get('acknowledged') and natural is None:
                try:
                    state=inspect(d,'container',producer['id'],end,'producer_exit');owned(state,producer,producer['owner'])
                    natural={k:state['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
                except BaseException as exc:exit_observation_error=type(exc).__name__
            for value in reversed(items):
                try:closures.append(retire(d,value,end))
                except BaseException as exc:closures.append({'kind':value['kind'],'name':value['name'],'closed':False,'error_type':type(exc).__name__})
        good=error is None and capture is not None and natural is not None and closed_before and len(closures)==3 and all(x['closed'] is True for x in closures) and d.reaped
        if good:
            try:
                validate_cli_records(d.records,d.phase_caps);after={target:tree(desc,meter) for target,desc in sorted(mounts.items())}
                need(before==after and self.engine_auth(meter)==engine,'All runtime input/source pins unchanged')
                need(pin(body(exposure_path,request['exposure'],meter,2097152))==request['exposure'],'Exposure approval unchanged')
            except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:512],'cleanup_errors':getattr(exc,'cleanup_errors',[])};good=False
        result={'schema':'h_owned_phase_receipt_v1','phase_id':request['phase_id'],'request_sha256':request_pin['sha256'],
                'ownership_pin':ownership_pin,'action':request['action'],'role':request['role'],'image':request['image'],'source':request['source'],'exposure':request['exposure'],
                'status':'captured' if good else 'failed','natural_exit':natural,'producer_closed_before_capture':closed_before,
                'output_inventory':capture if good else None,'quarantine_root':str(output),'retired_resources':closures,
                'all_native_resources_closed':len(closures)==3 and all(x['closed'] is True for x in closures),
                'cli_reaped':d.reaped,'command_metadata':d.records,'input_before':before,'input_after':after,'error':error,'exit_observation_error':exit_observation_error,
                'oom':None if natural is None else natural.get('OOMKilled'),
                'deadline_exceeded':time.monotonic()>=end or (producer_end is not None and natural is not None and natural.get('Running') is True and time.monotonic()>=producer_end),
                'timing':{'origin':request['clock']['origin'],'original_deadline':original_deadline,'phase_deadline':end,'started':started,'finished':time.monotonic()},
                'cost':{'transport_read_bytes':meter.read_bytes,'transport_write_bytes':meter.write_bytes,
                        'transport_write_reserved_bytes':meter.write_reserved_bytes,'elapsed_seconds':time.monotonic()-started,
                        'producer_logical_read_bytes':None,'producer_logical_write_bytes':None,'producer_peak_memory_bytes':None},
                'enforced_resource_limits':r,'transport_auxiliary_limits':{'holder_memory_bytes':HOLDER_MEMORY,'holder_cpu_nanos':1000000000,
                    'holder_pids':64,'holder_ready_tmpfs_bytes':4096,'per_container_shm_bytes':16777216},
                'cost_basis':{'read':'actual owned source/input/metadata file reads plus CLI response and local archive wire bytes',
                              'write':'actual checked host publication writes; reservations reported separately',
                              'excluded':'producer/kernel/daemon/executable-library I/O, external journal writes, exact peak RSS'},
                'external_journal_cost_included':False,'receipt_finalization_cost_included':False,
                'qualification_inherited':False,'scientific_qualification':False,'automatic_retry_authorized':False,
                'forced_stop_independent_host_and_daemon_state':'unknown'}
        try:
            record('PHASE-CLOSURE',result)
            raw=encoded(result);receipt_pin=publish(control/'RECEIPT.json',raw,meter);meter.tick()
            return {'receipt':result,'receipt_pin':receipt_pin,'receipt_path':str(control/'RECEIPT.json'),
                    'final_transport_counters':{'read_bytes':meter.read_bytes,'write_bytes':meter.write_bytes,'write_reserved_bytes':meter.write_reserved_bytes},
                    'finished_after_receipt':time.monotonic()}
        finally:
            self.read_used+=meter.read_bytes;self.write_used+=meter.write_reserved_bytes


    def recover(self,phase_id,request_pin,ownership_pin,original_deadline,journal,limits,controller_closed_proof):
        """Parent-only recovery after separately proven complete controller closure.

        The immutable ownership pin must have reached the parent journal before
        creation. This method never discovers arbitrary resources or clears an
        unknown creation outcome merely because its namespace is now empty.
        """
        need(re.fullmatch('[A-Za-z0-9_-]{1,96}',phase_id),'Exact recovery phase')
        descriptor(request_pin);descriptor(ownership_pin);descriptor(controller_closed_proof)
        required={'max_records','max_record_bytes','max_metadata_bytes','max_cli_calls','max_cli_bytes','source_read_bytes','host_write_bytes'}
        need(type(limits) is dict and set(limits)==required and all(type(v) is int and v>0 for v in limits.values()),'Explicit bounded recovery grant')
        need(limits['source_read_bytes']<=self.read_limit-self.read_used and limits['host_write_bytes']<=self.write_limit-self.write_used,
             'Recovery inside original whole-provider ceilings')
        meter=Meter(limits['source_read_bytes'],limits['host_write_bytes'],original_deadline)
        control=self.control_root/phase_id;started=time.monotonic();sequence=0;recovery_id=uuid.uuid4().hex
        def record(name,value):
            nonlocal sequence
            row={'schema':'h_recovery_event_v1','phase_id':phase_id,'request_pin':request_pin,'recovery_id':recovery_id,
                 'controller_closed_proof':controller_closed_proof,'sequence':sequence,'event':name,'value':value}
            raw=encoded(row);p=publish(control/('RECOVERY-'+recovery_id+'-'+str(sequence).zfill(6)+'.json'),raw,meter)
            sequence+=1;journal(name,{'record':row,'pin':p})
        d=Docker(self.binary,self.socket,max_calls=limits['max_cli_calls'],reply_budget=limits['max_cli_bytes'],phase_caps=caps(4096),
                 publish=record,account_read=meter.read,reserve_read=meter.ensure_read)
        try:
            self.engine_auth(meter)
            ownership=parse(body(control/'OWNERSHIP.json',ownership_pin,meter,65536))
            need(set(ownership)=={'schema','phase_id','request_pin','engine_source_pin','original_deadline','phase_deadline','attempt_prefix','resources'}
                 and ownership['schema']=='h_phase_ownership_v1' and ownership['phase_id']==phase_id and ownership['request_pin']==request_pin
                 and ownership['engine_source_pin']==self.engine_pin and ownership['original_deadline']==original_deadline,
                 'Exact externally pinned recovery ownership and original global clock')
            prefix=ownership['attempt_prefix'];need(re.fullmatch('h-[0-9a-f]{24}',prefix),'Exact owned prefix')
            rows=ownership['resources'];need(set(rows)=={'volume','holder','producer'},'All and only owned phase resources')
            rows={k:dict(v) for k,v in rows.items()}
            for label,row in rows.items():
                need(row=={'kind':'volume' if label=='volume' else 'container','name':prefix+'-'+label,'owner':prefix+'/'+label,
                           'attempted':False,'acknowledged':False},'Immutable original resource plan')
            metadata_bytes=0;record_pins={};history_error=None
            try:
                names=[]
                with os.scandir(control) as scan:
                    count=0
                    for entry in scan:
                        count+=1;need(count<=limits['max_records']+16,'Bounded private control directory')
                        if re.fullmatch('[0-9]{6}-[A-Z-]+\.json',entry.name):names.append(entry.name)
                        else:need(entry.name in ('REQUEST.json','POLICY.json','OWNERSHIP.json','RECEIPT.json') or re.fullmatch('RECOVERY-[0-9a-f]{32}-([0-9]{6}|RECEIPT)\.json',entry.name),'Only source-owned control records')
                need(len(names)<=limits['max_records'],'Bounded lifecycle history')
                for index,name in enumerate(sorted(names)):
                    raw=local_metadata(control/name,limits['max_record_bytes'],meter);metadata_bytes+=len(raw)
                    need(metadata_bytes<=limits['max_metadata_bytes'],'Cumulative recovery history ceiling')
                    value=parse(raw);record_pins[name]=pin(raw)
                    need(value['schema']=='h_transport_journal_v1' and value['phase_id']==phase_id and value['request_sha256']==request_pin['sha256']
                         and value['index']==index and name==str(index).zfill(6)+'-'+value['event']+'.json','Exact contiguous trusted lifecycle history')
                    if value['event'] in ('CREATE-ATTEMPT','RESOURCE-ACK'):
                        v=value['value'];label=v['owner'].rsplit('/',1)[-1];need(label in rows,'Planned resource only')
                        old=rows[label];need(v['name']==old['name'] and v['owner']==old['owner'] and v['kind']==old['kind'],'Exact lifecycle owner/name')
                        old['attempted']=True
                        if value['event']=='RESOURCE-ACK':
                            old['acknowledged']=True
                            if old['kind']=='container':
                                need(re.fullmatch('[0-9a-f]{64}',v['id']),'Exact acknowledged container ID');old['id']=v['id']
            except BaseException as exc:
                history_error={'type':type(exc).__name__,'message':str(exc)[:256]}
                # Incomplete durable history cannot certify creation did not run.
                for row in rows.values():row['attempted']=True;row['acknowledged']=False;row.pop('id',None)
            record('RECOVERY-PLAN',{'ownership_pin':ownership_pin,'resources':rows,'history_error':history_error})
            closures=[]
            for label in ('producer','holder','volume'):
                try:closures.append(retire(d,rows[label],original_deadline))
                except BaseException as exc:closures.append({'kind':rows[label]['kind'],'name':rows[label]['name'],'closed':False,'error_type':type(exc).__name__})
            absence={}
            for label,row in rows.items():
                try:absence[label]={'empty':resource_inventory(d,row,row['owner'],original_deadline,'absence_'+row['kind'])==[]}
                except BaseException as exc:absence[label]={'empty':False,'error_type':type(exc).__name__}
            self.engine_auth(meter);meter.tick();cli_validation_error=None
            try:validate_cli_records(d.records,d.phase_caps)
            except BaseException as exc:cli_validation_error=type(exc).__name__
            result={'schema':'h_independent_phase_recovery_v1','phase_id':phase_id,'request_pin':request_pin,'ownership_pin':ownership_pin,
                    'controller_closed_proof':controller_closed_proof,'original_deadline':original_deadline,'started':started,'finished':time.monotonic(),
                    'retired_resources':closures,'terminal_absence':absence,'all_namespaces_empty':all(x['empty'] for x in absence.values()),
                    'all_resource_custody_closed':all(x['closed'] for x in closures) and history_error is None and d.reaped and cli_validation_error is None,
                    'history_error':history_error,'cli_validation_error':cli_validation_error,'history_pins':record_pins,'cli_reaped':d.reaped,'command_metadata':d.records,
                    'qualification_inherited':False,'child_cost_or_outcome_reconstructed':False,
                    'unknown_creation_outcomes_resolved_by_absence':False}
            record('RECOVERY-CLOSURE',result)
            raw=encoded(result);receipt=publish(control/('RECOVERY-'+recovery_id+'-RECEIPT.json'),raw,meter)
            return {'receipt':result,'receipt_pin':receipt,'final_transport_counters':{'read_bytes':meter.read_bytes,'write_bytes':meter.write_bytes,
                    'write_reserved_bytes':meter.write_reserved_bytes},'finished_after_receipt':time.monotonic()}
        finally:self.read_used+=meter.read_bytes;self.write_used+=meter.write_reserved_bytes
