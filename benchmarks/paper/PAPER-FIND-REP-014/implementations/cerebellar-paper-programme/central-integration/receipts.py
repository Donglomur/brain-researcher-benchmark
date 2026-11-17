"""Full metadata-only admission of the immutable program-I receipt chain.

The owner supplies an operator-private bounded raw capture and authenticated
parent modules. This module never opens ambient files, reads numeric payloads,
imports candidate code, invokes providers, or reruns scientific grading.
"""
import hashlib
import json
import math
from pathlib import PurePosixPath
import re

TASK='PAPER-FIND-REP-014'


class ReceiptFailure(ValueError):pass


def require(value,message):
    if not value:raise ReceiptFailure(message)


def descriptor(value):
    require(type(value) is dict and set(value)=={'bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0 and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']),'Exact raw byte descriptor')
    return value


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def only_pin(value):return descriptor({k:value[k] for k in ('bytes','sha256')})


def same(left,right):
    if type(left) is not type(right):return False
    if type(left) is dict:return set(left)==set(right) and all(same(left[k],right[k]) for k in left)
    if type(left) is list:return len(left)==len(right) and all(same(a,b) for a,b in zip(left,right))
    return left==right


def equal(left,right,message):require(same(left,right),message)


def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'Duplicate metadata key');out[k]=v
        return out
    def number(value):
        result=float(value);require(math.isfinite(result),'Nonfinite metadata numeric overflow');return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=number,parse_constant=lambda _:(_ for _ in ()).throw(ReceiptFailure('Nonfinite metadata')))


def integer(value,minimum=0):return type(value) is int and value>=minimum


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def relative(name):
    require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*',name) and all(x not in ('.','..') for x in name.split('/')),'Exact source-owned relative locator')
    return name


def phase_id(value):
    require(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',value),'Exact admitted opaque phase token')
    return value


class Reader:
    def __init__(self,capture,metadata_cap):
        self.capture=capture;self.cap=metadata_cap;self.cache={};self.canonical_bytes=0;self.raw_bytes=0
    def raw(self,name,expected,cap=None):
        relative(name);descriptor(expected);cap=self.cap if cap is None else cap
        require(integer(cap,1) and expected['bytes']<=cap,'Complete metadata fits qualified cap; no truncation')
        if name in self.cache:
            old,raw,value=self.cache[name];equal(old,expected,'A locator cannot change immutable identity');return raw
        raw=self.capture.read(name,expected,cap)
        require(type(raw) is bytes and len(raw)<=cap and pin(raw)==expected,'Raw complete body matches upstream descriptor')
        self.raw_bytes+=len(raw);self.cache[name]=(dict(expected),raw,None);return raw
    def obj(self,name,expected,cap=None):
        raw=self.raw(name,expected,cap);entry=self.cache[name]
        if entry[2] is None:self.cache[name]=(entry[0],raw,strict(raw))
        return self.cache[name][2]
    def observed(self,name,cap=None):
        require(name=='work/ENCODING_SEAL.json','Only seal has caller-observed rather than upstream pin')
        cap=self.cap if cap is None else cap;raw,p=self.capture.observe(name,cap);descriptor(p)
        require(type(raw) is bytes and len(raw)<=cap and pin(raw)==p,'Exact newly observed seal bytes')
        require(name not in self.cache,'Seal observed once');self.raw_bytes+=len(raw);value=strict(raw);self.cache[name]=(p,raw,value);return value,p
    def names(self,name,limit):
        relative(name);require(integer(limit,1),'Explicit finite directory extent')
        values=self.capture.names(name,limit)
        require(type(values) is list and len(values)<=limit and all(type(n) is str and re.fullmatch('[A-Za-z0-9_.-]+',n) and n not in ('.','..') for n in values) and len(set(values))==len(values),'Complete ordinary unique directory names')
        return sorted(values)
    def canonical(self,value,cap=None):
        """Stream only source-defined small/qualified metadata, never outer."""
        cap=self.cap if cap is None else cap;digest=hashlib.sha256();count=0
        for text in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(value):
            part=text.encode('utf-8');count+=len(part);require(count<=cap,'Complete reconstructed metadata extent');digest.update(part)
        count+=1;require(count<=cap,'Complete canonical newline extent');digest.update(b'\n');self.canonical_bytes+=count
        return {'bytes':count,'sha256':digest.hexdigest()}


def budget_events(reader,budget,directory,origin,end,limits,max_events,final_bytes):
    require(type(budget) is dict and budget['origin']==origin and budget['deadline']==end and finite(budget['observed']) and origin<=budget['observed']<end,'Original immutable budget clock')
    for key,limit_key in (('logical_read_charge','read_bytes'),('logical_write_charge','write_bytes'),('retained_charge','retained_bytes')):
        require(integer(budget[key]) and budget[key]+(final_bytes if key!='logical_read_charge' else 0)<=limits[limit_key],'Full final publication remains in original budget partition')
    require(budget['kernel_native_IO_or_RSS_certified'] is False,'Logical counters never promoted to physical measurement')
    entries=budget['events'];require(type(entries) is list and len(entries)<=max_events,'Complete bounded source-owned event list')
    names=[];events=[];previous=origin
    for index,entry in enumerate(entries):
        require(type(entry) is dict and set(entry)=={'path','bytes','sha256'} and entry['path']==f'{index:07d}.json','Exact contiguous upstream journal descriptors')
        name=entry['path'];names.append(name);p=only_pin(entry);row=reader.obj(directory+'/'+name,p)
        require(row['index']==index and row['ledger_clock']['origin']==origin and row['ledger_clock']['deadline']==end,'Exact journal index and original clock')
        t=row['ledger_clock']['observed'];require(finite(t) and previous<=t<=budget['observed'],'Monotonic fully captured event history');previous=t;events.append((row,p))
    equal(reader.names(directory,max(1,max_events)),names,'No omitted or undisclosed later journal file')
    return events


def executed_modules(value,files):
    require(type(value) is dict and {'supervisor','core','budget','operation','planner','safe_io','transport.engine'}<=set(value),'Actual executing supervisor and required dependencies')
    for name,item in value.items():
        require(type(name) is str and all(p.isidentifier() for p in name.split('.')),'Ordinary authenticated module identity')
        rel=name.replace('.','/')
        if item is None:
            require(rel+'/__init__.py' not in files and any(p.startswith(rel+'/') for p in files),'Only declared source namespace package');continue
        require(type(item) is dict and set(item)=={'path','bytes','sha256'} and item['path'] in (rel+'.py',rel+'/__init__.py'),'Executed module exact source locator')
        equal(only_pin(item),files[item['path']],'Executed local code bytes belong to exact frozen manifest')


def birth(token):
    require(type(token) is dict and set(token)=={'schema','pid','pgid','session_id','uid','start_time_ticks','boot_id'} and token['schema']=='osl_linux_process_identity_v1','Complete Linux birth identity')
    require(integer(token['pid'],2) and token['pid']==token['pgid']==token['session_id'] and integer(token['uid']) and integer(token['start_time_ticks'],1) and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',token['boot_id']),'Exact independent process/session birth token')


def controller_close(reader,outer,parent_root,op,operation_pin,origin,end):
    p=descriptor(outer['controller_close']);value=reader.obj('CONTROLLER_CLOSE.json',p)
    equal(value,outer['controller_close_independently_observed_in_memory'],'Raw controller closure equals independently observed in-memory record')
    require(value['schema']=='paper_i_independent_controller_close_v1' and value['exit_code']==0 and type(value['exit_code']) is int and value['natural_exit'] is True and value['forced'] is False and value['reaped'] is True and value['process_group_absent'] is True and value['error_type'] is None and value['cleanup_errors']==[],'Independent natural zero/reaped/absent controller, no cleanup uncertainty')
    birth(value['process_identity']);work_end=end-op['host']['cleanup_seconds']
    require(value['work_deadline']==work_end and value['global_deadline']==end and finite(value['started']) and finite(value['finished']) and origin<=value['started']<work_end and value['started']<=value['finished']<end,'Controller closes inside unchanged original clock')
    loader='import sys,runpy;p=sys.argv.pop(1);sys.path.insert(0,p);runpy.run_path(p+"/controller.py",run_name="__main__")'
    pin_arg=json.dumps(operation_pin,sort_keys=True,separators=(',',':'),allow_nan=False)
    expected=[op['host']['python']['path'],'-I','-B','-c',loader,parent_root+'/host_source','--operation',parent_root+'/OPERATION.json','--operation-pin',pin_arg,'--output',parent_root+'/work','--origin',repr(origin),'--global-deadline',repr(end),'--work-deadline',repr(work_end)]
    equal(value['argv'],expected,'Exact immutable controller command and original clocks')
    require(set(value['logs'])=={'stdout','stderr'},'Both complete controller logs')
    require(sum(descriptor(p)['bytes'] for p in value['logs'].values())<=op['host']['log_bytes'],'Combined original controller log bound')
    for name,p in value['logs'].items():reader.raw(name+'.log',descriptor(p),op['host']['log_bytes'])
    return value


def cli_caps(inventory):
    result={k:131072 for k in ('image','volume_admit','admit_holder','admit_producer','producer_exit','cleanup_inspect')}
    result.update({k:4096 for k in ('volume_create','create_holder','create_producer','holder_start','holder_ready','producer_start','producer_wait','cleanup_kill','cleanup_wait','cleanup_remove')})
    result.update({a+'_'+b+'_'+c:8192 for a in ('before','cleanup','absence') for b in ('container','volume') for c in ('owner','name')});result['artifact_inventory']=inventory;return result


def cli_records(records,caps,max_calls,max_bytes):
    keys={'phase','returncode','error_type','observed_retained_bytes','seconds','client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed','leader_exited_with_group_alive','group_probe_or_cleanup_error'}
    require(type(records) is list and 0<len(records)<=max_calls,'Complete finite CLI outcome history')
    for v in records:
        require(type(v) is dict and set(v)==keys and v['phase'] in caps,'Exact source CLI record fields/phase')
        require(type(v['returncode']) is int and v['returncode']==0 and v['error_type'] is None and v['group_probe_or_cleanup_error'] is None,'Every CLI returned successful and error-free')
        require(integer(v['observed_retained_bytes']) and v['observed_retained_bytes']<=caps[v['phase']] and finite(v['seconds']) and v['seconds']>=0,'Bounded actual CLI bytes/time')
        require(all(v[k] is True for k in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed')) and v['leader_exited_with_group_alive'] is False,'Every CLI has complete original-deadline custody')
    require(sum(v['observed_retained_bytes'] for v in records)<=max_bytes,'Cumulative bounded CLI response history')


def cli_births(records,commands,end):
    intents={};children={}
    for row,p in records:
        if row['event'] not in ('CLI-INTENT','CLI-CHILD'):continue
        v=row['value'];i=v['index'];require(integer(i) and i<len(commands),'Exact CLI index')
        require(v['phase']==commands[i]['phase'] and finite(v['original_end']) and 0<v['original_end']<=end,'CLI phase and original deadline join')
        if row['event']=='CLI-INTENT':require(i not in intents,'One CLI intent');intents[i]=(v,p)
        else:
            require(i not in children and v['docker_exec_still_gated'] is True and v['independent_group'] is True,'One gated CLI birth');birth(v['process_identity'])
            require(v['pid']==v['pgid']==v['process_identity']['pid'],'Exact CLI process identity');children[i]=(v,p)
    require(set(intents)==set(children)==set(range(len(commands))),'No unrecorded CLI startup window')
    for i in intents:require(intents[i][0]['phase']==children[i][0]['phase'] and intents[i][0]['original_end']==children[i][0]['original_end'],'Intent/birth exact join')
    return children

def phase_route(slot):
    stage=slot['stage']
    if stage=='prepare_originals':return 'prepare_originals','operator'
    if stage in ('prepare_support','prepare_inner','prepare_final'):return 'prepare_views','operator'
    if stage in ('inner_fit','final_fit'):return 'fit',slot['producer_role']
    if stage in ('inner_query','outer_query'):return 'query',slot['producer_role']
    if stage in ('inner_admit','final_admit','inner_error','selection'):return 'selection_evaluate','operator'
    if stage=='reconstruct':return 'reconstruct',slot['producer_role']
    if stage in ('grade_encoding','grade_native'):return 'final_evaluate','operator'
    require(stage=='report','Known complete source stage');return 'report','operator'


def inventory_names(reader,root,files,resources):
    require(type(files) is dict and 0<len(files)<=resources['max_files'],'Complete finite captured inventory')
    children={'':set()};directories=set()
    for name,d in files.items():
        relative(name);descriptor(d);require(d['bytes']<=resources['max_file_bytes'],'Whole captured member extent')
        parts=name.split('/')
        for i,part in enumerate(parts):
            parent='/'.join(parts[:i]);children.setdefault(parent,set()).add(part)
            if i<len(parts)-1:
                directory='/'.join(parts[:i+1]);require(directory not in files,'A captured file cannot also be a directory');directories.add(directory)
    require(len(directories)<=resources['max_directories'] and sum(d['bytes'] for d in files.values())<=resources['max_output_bytes'],'Full captured tree resource ceiling')
    for directory,names in children.items():
        got=reader.names(root+('/'+directory if directory else ''),resources['max_files']+resources['max_directories'])
        equal(got,sorted(names),'Exact complete captured membership; no extra numeric/file bodies opened')


def retired(rows,resources):
    require(type(rows) is list and len(rows)==3,'Every owned producer/holder/volume retired')
    by_name={r['name']:r for r in rows};require(len(by_name)==3 and set(by_name)=={r['name'] for r in resources.values()},'Exact owned retirement namespace')
    for name,row in by_name.items():
        original=next(v for v in resources.values() if v['name']==name)
        require(row['kind']==original['kind'] and row['closed'] is True and row.get('creation_outcome_unknown') is not True and row.get('create_not_attempted') is not True and 'error_type' not in row,'Successful scientific phase requires known created and closed resources')


def phase_admit(reader,parent_root,op,files,source_pin,start,finish,transport_events,origin,end):
    key=phase_id(start['phase_id']);base='work/control/'+key;slot=start['slot'];action,role=phase_route(slot)
    require(start['action']==action and start['role']==role and start['job_id']==slot['job_id'],'Source-defined stage/action/role/job')
    require(finish['status']=='captured' and finish['resources_closed'] is True,'Every required phase has closed complete capture')
    request=reader.obj(base+'/REQUEST.json',start['request_pin']);resources=op['phase_resources'][action]
    require(request['schema']=='paper_i_owned_phase_request_v1' and request['phase_id']==key and request['action']==action and request['role']==role and request['workdir']=='/work','Exact immutable phase request')
    equal(request['resources'],resources,'Original full per-phase resource envelope');equal(request['output'],{'kind':'generic','manifest':'OUTPUTS.json'},'Original generic manifest-guided capture')
    require(request['clock']['origin']==origin and finite(request['clock']['phase_deadline']) and origin<request['clock']['phase_deadline']<=end-op['host']['cleanup_seconds'],'Request original work/attempt cutoff')
    require(request['image']==op['images'][role]['digest'],'Exact admitted immutable role image')
    equal(request['exposure'],start['exposure_pin'],'Request exposure pin from original nested_start')
    exposure=reader.obj('work/'+start['exposure_path'],start['exposure_pin']);mounts=exposure['mounts']
    require(exposure['schema']=='osl_transport_exposure_v1' and exposure['role_boundary_verified'] is True and exposure['role']==role and exposure['image']==request['image'],'Complete independently approved role exposure')
    equal(exposure['command'],request['command'],'Exact source command exposure');equal(exposure['source'],request['source'],'Exact source identity exposure')
    equal(exposure['boundary_audit'],only_pin(op['images'][role]['boundary_audit']),'Exact independent boundary audit');require(exposure['approved_image_inventory_sha256']==op['images'][role]['inventory']['sha256'],'Exact complete image inventory')
    require(type(mounts) is dict and '/input' in mounts,'Complete actual mount inventory')
    for target,m in mounts.items():
        require(type(target) is str and target.startswith('/') and type(m) is dict and set(m)=={'kind','purpose','files'} and m['kind'] in ('file','directory') and type(m['files']) is dict and m['files'],'Complete immutable mounted source/input inventory')
        for n,p in m['files'].items():relative(n);descriptor(p)
    if role in ('A','B'):
        equal(request['command'],op['programs'][role]['commands'][action],'Frozen candidate argv')
        candidate_files=op['programs'][role]['source']['files'];equal(request['source'],reader.canonical(candidate_files),'Exact committed candidate package identity')
        equal(mounts['/program']['files'],candidate_files,'Full actual candidate source package')
        equal(mounts['/contract']['files'],{'PUBLIC_CONTRACT.md':files['PUBLIC_CONTRACT.md']},'Same complete public contract')
        equal(mounts['/paper/article.xml']['files'],{'article.xml':only_pin(op['paper'])},'Same original paper edition')
        expected={'/input','/program','/contract','/paper/article.xml'}
        if role=='B':expected.add('/author');equal(mounts['/author']['files'],op['author_source']['files'],'B exact historical author source')
        if action=='reconstruct':expected.add('/originals')
        if action=='query':expected.add('/models')
        require(set(mounts)==expected,'No extra candidate mount or early raw native exposure')
    else:
        equal(request['source'],source_pin,'Exact operator/reference complete source closure');equal(mounts['/source']['files'],files,'Actual complete immutable operator source mount')
        payload=descriptor(mounts['/input']['files']['PAYLOAD.json'])
        expected_command=['/usr/local/bin/python','-I','-B','/source/worker.py','--payload','/input/PAYLOAD.json','--payload-bytes',str(payload['bytes']),'--payload-sha256',payload['sha256']]
        equal(request['command'],expected_command,'Exact source-bound worker command')
        expected={'/input','/source'}
        if slot['stage']=='prepare_originals':expected|={'/native','/originals'}
        elif slot['stage'] in ('prepare_support','prepare_inner','prepare_final'):expected.add('/prepared')
        elif slot['stage']=='reconstruct':expected|={'/native','/originals'}
        elif slot['stage'] in ('inner_admit','final_admit','inner_query','outer_query'):expected.add('/models')
        require(set(mounts)==expected,'Exact source-defined trusted phase mount set')
    if '/originals' in mounts:equal(mounts['/originals']['files'],{n:only_pin(d) for n,d in op['originals']['files'].items()},'Every complete original publisher input')
    records=[];history={};ownership_pin=None;ownership_body=None
    require(type(transport_events) is list and 0<len(transport_events)<=op['host']['recovery']['max_records'],'Complete bounded phase lifecycle history')
    for index,event in enumerate(transport_events):
        embedded=event['record'];name=f"{index:06d}-{embedded['event']}.json"
        require(embedded['index']==index and re.fullmatch('[0-9]{6}-[A-Z-]+.json',name),'Contiguous source lifecycle record')
        row=reader.obj(base+'/'+name,event['pin'],min(reader.cap,op['host']['recovery']['max_record_bytes']));equal(row,embedded,'Raw lifecycle file equals upstream controller-journal record')
        require(row['schema']=='osl_transport_journal_v1' and row['phase_id']==key and row['request_sha256']==start['request_pin']['sha256'] and row['event']==event['name'],'Exact lifecycle current phase/request')
        records.append((row,event['pin']));history[name]=event['pin']
        if row['event']=='OWNERSHIP':
            require(ownership_pin is None,'One ownership declaration');ownership_pin=descriptor(row['value']['ownership_pin']);ownership_body=row['value']['ownership']
    require(sum(p['bytes'] for p in history.values())<=op['host']['recovery']['max_metadata_bytes'],'Full lifecycle metadata aggregate fits original ceiling')
    require(ownership_pin is not None,'Ownership pin must precede every resource operation')
    owner=reader.obj(base+'/OWNERSHIP.json',ownership_pin,min(reader.cap,65536));equal(owner,ownership_body,'Exact source-owned resource plan')
    require(owner['schema']=='osl_phase_ownership_v1' and owner['phase_id']==key and owner['original_deadline']==end,'Original global ownership clock')
    equal(owner['request_pin'],start['request_pin'],'Ownership request pin');equal(owner['engine_source_pin'],files['transport/SOURCE_MANIFEST.json'],'Frozen concrete engine source')
    prefix=owner['attempt_prefix'];require(re.fullmatch('osl-[0-9a-f]{24}',prefix) and set(owner['resources'])=={'producer','holder','volume'},'All and only exact owned resources')
    for label,r in owner['resources'].items():equal(r,{'kind':'volume' if label=='volume' else 'container','name':prefix+'-'+label,'owner':prefix+'/'+label,'attempted':False,'acknowledged':False},'Original exact resource identity')
    receipt_pin=descriptor(finish['receipt_pin']);receipt=reader.obj(base+'/RECEIPT.json',receipt_pin)
    require(receipt['schema']=='osl_owned_phase_receipt_v1' and receipt['phase_id']==key and receipt['request_sha256']==start['request_pin']['sha256'] and receipt['status']=='captured','Exact captured phase receipt')
    for k in ('action','role','image','source','exposure'):equal(receipt[k],request[k],'Captured request identity '+k)
    equal(receipt['ownership_pin'],ownership_pin,'Captured exact ownership');equal(receipt['enforced_resource_limits'],resources,'Original enforced resource limits')
    require(receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True and receipt['producer_closed_before_capture'] is True and receipt['error'] is None and receipt['exit_observation_error'] is None and receipt['oom'] is False and receipt['deadline_exceeded'] is False,'Natural closed capture without OOM/deadline/error uncertainty')
    require(receipt['qualification_inherited'] is False and receipt['scientific_qualification'] is False and receipt['automatic_retry_authorized'] is False,'No source-derived qualification or retry')
    natural=receipt['natural_exit'];require(type(natural) is dict and set(natural)=={'Status','Running','Dead','Pid','ExitCode','OOMKilled'} and type(natural['Pid']) is int and natural['Running'] is False and natural['Dead'] is False and type(natural['ExitCode']) is int and natural['ExitCode']==0 and natural['OOMKilled'] is False and natural['Status']=='exited' and natural['Pid']==0,'Actual natural zero native exit observation')
    timing=receipt['timing'];span=sum(resources[k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
    require(timing['origin']==origin and timing['original_deadline']==end and owner['phase_deadline']==timing['phase_deadline'] and timing['phase_deadline']==timing['started']+span and origin<=timing['started']<=timing['finished']<timing['phase_deadline']<=request['clock']['phase_deadline'],'Provider actual full-span deadline, distinct from request cutoff')
    equal(receipt['input_before'],mounts,'All original input/source identities before execution');equal(receipt['input_after'],mounts,'All original input/source identities unchanged after execution')
    require(receipt['quarantine_root']==parent_root+'/work/quarantine/'+key,'Exact private quarantine location')
    retired(receipt['retired_resources'],owner['resources'])
    cli_records(receipt['command_metadata'],cli_caps(resources['inventory_bytes']),resources['max_cli_calls'],resources['max_cli_bytes'])
    births=cli_births(records,receipt['command_metadata'],end)
    ack={};attempt=set();closure=[]
    for row,p in records:
        if row['event'] in ('CREATE-ATTEMPT','RESOURCE-ACK'):
            v=row['value'];label=v['owner'].rsplit('/',1)[-1];require(label in owner['resources'],'Only original owned resources')
            for k in ('kind','name','owner'):equal(v[k],owner['resources'][label][k],'Exact resource creation identity')
            if row['event']=='CREATE-ATTEMPT':require(label not in attempt,'No hidden creation retry');attempt.add(label)
            else:require(label in attempt and label not in ack and v['acknowledged'] is True,'Known creation acknowledgment');ack[label]=v
        elif row['event']=='PHASE-CLOSURE':closure.append(row['value'])
    require(attempt==set(ack)==set(owner['resources']) and len(closure)==1,'Every successful resource creation and final closure accounted')
    equal(closure[0],receipt,'Original transport final closure matches raw execution receipt')
    inventory=receipt['output_inventory'];require(inventory['complete'] is True,'Complete captured output inventory')
    outputs=inventory['files'];require('OUTPUTS.json' in outputs and 'RESULT.json' in outputs,'Complete transport/result metadata files')
    require(inventory['total_bytes']==sum(p['bytes'] for p in outputs.values()) and set(inventory['transfers'])==set(outputs),'Exact total capture and all transfers')
    for n,d in outputs.items():equal(inventory['transfers'][n]['file'],d,'Every captured file identity')
    envelope=reader.obj('work/quarantine/'+key+'/OUTPUTS.json',outputs['OUTPUTS.json'],min(reader.cap,resources['manifest_bytes']))
    equal(envelope,{'schema':'osl_transport_output_manifest_v1','phase_id':key,'request_sha256':start['request_pin']['sha256'],'files':{n:d for n,d in outputs.items() if n!='OUTPUTS.json'}},'Full immutable output envelope')
    inventory_names(reader,'work/quarantine/'+key,outputs,resources)
    policy={'schema':'osl_holder_policy_v1','phase_id':key,'role':role,'file_cap':resources['max_file_bytes'],'total_cap':resources['max_output_bytes'],'files':resources['max_files'],'directories':resources['max_directories']}
    reader.obj(base+'/POLICY.json',reader.canonical(policy))
    return {'phase_id':key,'slot':slot,'start':start,'finish':finish,'request':request,'exposure':exposure,'owner':owner,'ownership_pin':ownership_pin,'receipt':receipt,'receipt_pin':receipt_pin,'outputs':outputs,'history':history,'births':births,'records':records}


def recoveries(reader,outer,outer_events,phases,op,controller_pin,origin,end):
    recovery=outer['independent_recovery'];require(recovery['inventory_error'] is None and recovery['independent_terminal_absence_complete'] is True and recovery['unknown_creation_outcomes_resolved_by_absence'] is False,'Complete independent owned-resource custody')
    rows=recovery['phases'];require(type(rows) is list and len(rows)==len(phases),'Every observed phase has independent recovery')
    lookup={r['phase_id']:r for r in rows};require(set(lookup)==set(phases) and len(lookup)==len(rows),'Exact independent recovery phase set')
    grouped={k:[] for k in phases}
    for event,_ in outer_events:
        if event['event']!='outer_recovery':continue
        wrapper=event['value'];record=wrapper['record'];key=record['phase_id'];require(key in grouped and event['name']==record['event'],'Exact recovery callback source event')
        grouped[key].append(wrapper)
    for key,phase in phases.items():
        row=lookup[key];require(row['recovery_complete'] is True and row.get('resource_creation_not_started') is not True and 'error_type' not in row,'Successful science cannot use no-creation or failed recovery shortcut')
        receipt=row['receipt'];require(receipt['schema']=='osl_independent_phase_recovery_v1' and receipt['phase_id']==key and receipt['original_deadline']==end,'Exact independent recovery receipt')
        equal(receipt['request_pin'],phase['start']['request_pin'],'Recovery request identity');equal(receipt['ownership_pin'],phase['ownership_pin'],'Recovery ownership identity');equal(receipt['controller_closed_proof'],controller_pin,'Recovery follows independent controller closure')
        require(all(receipt[k] is True for k in ('all_namespaces_empty','all_resource_custody_closed','cli_reaped')) and receipt['history_error'] is None and receipt['cli_validation_error'] is None and receipt['qualification_inherited'] is False and receipt['unknown_creation_outcomes_resolved_by_absence'] is False,'Independent recovery has no history/CLI/custody uncertainty')
        require(origin<=receipt['started']<=receipt['finished']<end,'Recovery inside original global clock');retired(receipt['retired_resources'],phase['owner']['resources'])
        require(set(receipt['terminal_absence'])=={'producer','holder','volume'} and all(same(v,{'empty':True}) for v in receipt['terminal_absence'].values()),'All exact owned namespaces independently absent')
        equal(receipt['history_pins'],phase['history'],'Every original lifecycle record independently authenticated by recovery')
        limits=op['host']['recovery'];cli_records(receipt['command_metadata'],cli_caps(4096),limits['max_cli_calls'],limits['max_cli_bytes'])
        wrappers=grouped[key];require(0<len(wrappers)<=2*limits['max_cli_calls']+3,'Complete bounded recovery event history')
        recovery_id=None;records=[];names=[];closures=[]
        for index,wrapper in enumerate(wrappers):
            r=wrapper['record'];rid=r['recovery_id'];require(re.fullmatch('[0-9a-f]{32}',rid) and (recovery_id is None or rid==recovery_id),'One immutable recovery attempt, no hidden retry');recovery_id=rid
            require(r['schema']=='osl_recovery_event_v1' and r['sequence']==index and r['controller_closed_proof']==controller_pin and r['request_pin']==phase['start']['request_pin'],'Contiguous exact recovery history')
            name=f'RECOVERY-{rid}-{index:06d}.json';names.append(name)
            actual=reader.obj('work/control/'+key+'/'+name,wrapper['pin'],min(reader.cap,limits['max_record_bytes']));equal(actual,r,'Raw recovery journal matches outer upstream event')
            records.append((r,wrapper['pin']))
            if r['event']=='RECOVERY-CLOSURE':closures.append(r['value'])
            if r['event']=='RECOVERY-PLAN':require(r['value']['history_error'] is None and r['value']['ownership_pin']==phase['ownership_pin'],'Known owned recovery plan')
        require(len(closures)==1,'Exactly one recovery closure');equal(closures[0],receipt,'Recovery closure and returned receipt match')
        cli_births(records,receipt['command_metadata'],end)
        final_name='RECOVERY-'+recovery_id+'-RECEIPT.json';names.append(final_name)
        actual=reader.obj('work/control/'+key+'/'+final_name,row['receipt_pin']);equal(actual,receipt,'Raw source-defined recovery receipt')
        prior=row['prior_cli_custody'];require(prior['all_recorded_cli_groups_absent'] is True and prior['errors']==[] and prior['unmatched_intents']==[],'All original gated CLI births independently closed')
        expected={p['sha256']:(v,p) for v,p in phase['births'].values()};observed=set()
        for r in prior['records']:
            p=r['record'];require(p['sha256'] in expected and p['sha256'] not in observed,'Every prior CLI birth closed once');observed.add(p['sha256']);v,want=expected[p['sha256']];equal(p,want,'Exact prior birth record pin')
            close=r['closure'];equal(close['process_identity'],v['process_identity'],'Independent closure uses exact birth token');require(close['closed'] is True and close['group_absent'] is True and 'error_type' not in close and 'close_error' not in close,'Known independent CLI group absence')
            require(close['leader_signalled'] is False or close['identity_match'] is True,'No reused bare PID signal')
        require(observed==set(expected),'No prior birth omitted from independent closure')
        expected_names=sorted(['REQUEST.json','POLICY.json','OWNERSHIP.json','RECEIPT.json',*phase['history'],*names])
        equal(reader.names('work/control/'+key,len(expected_names)+1),expected_names,'No omitted/extra source-owned lifecycle or recovery record')
    return {'phase_count':len(phases),'all_independent_owned_resources_absent':True,'all_creation_and_cli_custody_known':True}

def selected_result(reader,phase):
    p=descriptor(phase['outputs']['RESULT.json']);value=reader.obj('work/quarantine/'+phase['phase_id']+'/RESULT.json',p)
    require(value['phase_id']==phase['phase_id'],'Exact source worker RESULT phase')
    equal(value['original_clock'],phase['request']['clock'],'Source worker original request clock')
    io=value['worker_io_before_envelope'];r=phase['request']['resources']
    require(set(io)=={'read_bytes','write_bytes'} and integer(io['read_bytes']) and integer(io['write_bytes']) and io['read_bytes']<=r['source_read_bytes'] and io['write_bytes']<=r['max_output_bytes'],'Original worker metadata I/O before envelope')
    return value,p


def encoding_seal(reader,events,jobs,job_values,phases):
    encoding={j['job_id']:j for j in jobs if j['kind']=='encoding'};native={j['job_id']:j for j in jobs if j['kind']=='reconstruction'}
    begins=[(i,row) for i,(row,_) in enumerate(events) if row.get('event')=='high_level_start']
    equal([r['job'] for _,r in begins],jobs,'Every original high-level producer starts exactly once in source order')
    native_index=next(i for i,row in begins if row['job_id'] in native)
    terminal={row['job_id']:i for i,(row,_) in enumerate(events) if row.get('event')=='high_level_disposition'}
    require(set(terminal)=={j['job_id'] for j in jobs} and all(terminal[k]<native_index for k in encoding),'All60 terminal encoding producers before full native exposure')
    pre=[];last_close=-1;active=None
    encoding_stages={'prepare_inner','inner_fit','inner_admit','inner_query','inner_error','selection','prepare_final','final_fit','final_admit','outer_query'}
    for index,(row,_) in enumerate(events):
        if row.get('event')=='nested_start':
            require(active is None,'One original sequential concrete phase at a time');active=row['phase_id']
            stage=row['slot']['stage']
            if index<native_index:require(stage in encoding_stages|{'prepare_originals','prepare_support'},'No grade/native phase before encoding seal')
            else:require(stage not in encoding_stages and row['job_id'] not in encoding,'No encoding dispatch after full-native barrier')
        elif row.get('event')=='nested_disposition':
            require(active==row['phase_id'] and row['status']=='captured' and row['resources_closed'] is True,'Matching sequential closed disposition')
            if index<native_index:pre.append(row['receipt_pin'])
            active=None;last_close=index
    require(active is None,'No unfinished phase across seal or finalreport')
    observed,p=reader.observed('work/ENCODING_SEAL.json')
    expected={'schema':'paper_i_encoding_irreversible_seal_v1','jobs':{k:job_values[k] for k in encoding},'closed_phases':pre,'no_more_encoding_dispatch':True}
    equal(observed,expected,'Complete caller-observed seal reconstructed from authenticated journal/jobs')
    return {'pin':p,'provenance':'caller_observed_after_worker_close_no_upstream_pin_or_seal_timestamp','encoding_jobs':60,'closed_pre_native_phases':len(pre),'chronology_basis':'immutable controller375-378 flow plus exact encoding/reconstruct event order'}


def ordering(plan,phases,selections):
    """Metadata dependency checks; counts never replace required predecessor slots."""
    jobs={j['job_id']:j for j in plan['high_level_jobs']};units={u['unit_id']:u for u in plan['units']}
    chosen={(s['job_id'],s['unit_id']):{g['configuration_id'] for g in s['groups']} for s in selections}
    prepared=set();fits=set();admitted=set();queries={};errors=set();selected=set();final_prepared=set();final_fits=set();final_admitted=set()
    for p in phases.values():
        s=p['slot'];stage=s['stage']
        if s['job_id'] is None or jobs[s['job_id']]['kind']!='encoding':continue
        pair=(s['job_id'],s['unit_id']);inner=(*pair,s['inner_fold']);cfg=(*inner,s['configuration_id']);final=(*pair,s['configuration_id'])
        if stage=='prepare_inner':prepared.add(inner)
        elif stage=='inner_fit':require(inner in prepared,'Inner fit follows training-only view');fits.add(cfg)
        elif stage=='inner_admit':require(cfg in fits,'Passive admission follows exact fit');admitted.add(cfg)
        elif stage=='inner_query':require(cfg in admitted,'Every query follows trusted model admission');queries[cfg]=queries.get(cfg,0)+1
        elif stage=='inner_error':
            unit=units[s['unit_id']];job=jobs[s['job_id']];part=next(x for x in unit['outer'][job['fold']]['inner'] if x['fold']==s['inner_fold'])
            require(queries.get(cfg,0)==len(part['validation'])*unit['time_count'],'Every original inner query precedes error aggregation');errors.add(cfg)
        elif stage=='selection':
            unit=units[s['unit_id']];job=jobs[s['job_id']]
            required={(*pair,i['fold'],c['id']) for i in unit['outer'][job['fold']]['inner'] for c in plan['configurations'][job['role']][job['profile']]}
            require(required<=errors,'All declared inner configurations/folds precede selection');selected.add(pair)
        elif stage=='prepare_final':require(pair in selected,'Final training view follows complete training selection');final_prepared.add(pair)
        elif stage=='final_fit':require(pair in final_prepared and s['configuration_id'] in chosen[pair],'Only authenticated selected final fits');final_fits.add(final)
        elif stage=='final_admit':require(final in final_fits,'Selected final admission follows its exactfit');final_admitted.add(final)
        elif stage=='outer_query':require({(*pair,c) for c in chosen[pair]}<=final_admitted,'Full-vector outer query follows every selected model admission')


def support_metadata(reader,phases,plan,op):
    prep=[p for p in phases.values() if p['slot']['stage']=='prepare_originals'];admit=[p for p in phases.values() if p['slot']['stage']=='prepare_support']
    require(len(prep)==len(admit)==1,'Exact full original and support preparation')
    a,b=prep[0],admit[0];outputs=b['outputs'];require('SUPPORT.json' in outputs,'Complete private source-support artifact')
    support=reader.obj('work/quarantine/'+b['phase_id']+'/SUPPORT.json',outputs['SUPPORT.json'])
    require(support['schema']=='paper_i_full_support_v1' and support['model_unit']=='authenticated_physical_acquisition_and_modality' and support['scientific_qualification'] is False,'Original fully admitted physical support estimand')
    equal(support['units'],plan['units'],'Plan contains every original admitted unit/fold/row/cell/grid')
    equal(support['certificate'],only_pin(op['lineage']),'Original lineage certificate');equal(support['review'],only_pin(op['lineage_review']),'Independent original lineage review')
    equal(support['prepared'],a['outputs']['native/PREPARED.json'],'Full native preparation identity')
    expected_prepared={n[len('native/'):]:p for n,p in a['outputs'].items() if n.startswith('native/')}
    equal(b['exposure']['mounts']['/prepared']['files'],expected_prepared,'All full native preparation members, no subset')
    require(type(support['original_source_acquisitions']) is list and support['original_source_acquisitions'] and type(support['all_original_row_dispositions']) is dict and support['all_original_row_dispositions'] and type(support['aliases']) is list,'Original row dispositions and aliases retained')
    acquisitions={a['key']:a for a in support['acquisitions']};require(len(acquisitions)==len(support['acquisitions']),'Unique complete source acquisition joins')
    expected={'GrC':{},'CF':{}};views={name:{'GrC':{},'CF':{}} for name in ('Water','1-s DA','DA-first','2-s DA')}
    for u in plan['units']:
        a=acquisitions[u['source_key']];meta=a['private_unit_metadata'][u['modality']];key=meta['acquisition'];require(key not in expected[u['modality']],'No duplicate physical acquisition/modality through aliases')
        row={'session':meta['session'],'animal':meta['animal'],'cell_tokens':u['cell_tokens'],'trials':{}}
        for outer in u['outer']:
            for source_row in outer['query']:
                trial=meta['trials'][source_row];require(type(trial) is str and trial not in row['trials'],'Exact original physical trial once permodality')
                value={'time_count':u['time_count'],'fold':outer['fold']};row['trials'][trial]=value
                for label in meta['trial_views'][str(source_row)]:
                    require(label in views,'Original native diagnostic view only');v=views[label][u['modality']].setdefault(key,{'session':meta['session'],'animal':meta['animal'],'cell_tokens':u['cell_tokens'],'trials':{}});v['trials'][trial]=value
        expected[u['modality']][key]=row
    require(all(expected.values()),'Both complete selected modalities retained')
    unique=sum(t['time_count'] for m in expected.values() for a in m.values() for t in a['trials'].values())
    require(support['unique_outer_queries']==unique,'Full physical query support count')
    return support,outputs['SUPPORT.json'],expected,views


def grade_metrics(value,expected,require_both):
    require(value['schema']=='filio_i_hierarchical_grade_v1' and set(value['modalities'])=={'GrC','CF'} and value['combined_modality_scalar'] is None,'Original separate-modality score metadata')
    queries=0
    for modality,want in expected.items():
        got=value['modalities'][modality]
        if not want:
            equal(got,{'available':False,'reason':'empty complete modality denominator'},'Explicit structural empty modality denominator');continue
        require(got['available'] is True and finite(got['mse']) and got['mse']>=0 and finite(got['rmse']) and got['rmse']>=0,'Full finite proper-error result, no quality threshold')
        nqueries=sum(t['time_count'] for a in want.values() for t in a['trials'].values());queries+=nqueries
        counts={'queries':nqueries,'trials':sum(len(a['trials']) for a in want.values()),'cells_within_acquisitions':sum(len(a['cell_tokens']) for a in want.values()),'acquisitions':len(want),'sessions':len({a['session'] for a in want.values()}),'animals':len({a['animal'] for a in want.values()})}
        equal(got['counts'],counts,'Full original biological/time/cell denominators')
        details=got['acquisition_details'];require(set(details)==set(want),'Every original physical acquisition in grade')
        for key,a in want.items():
            b=details[key]
            for field in ('session','animal','cell_tokens'):equal(b[field],a[field],'Exact original biological/cell identity')
            require(set(b['trials'])==set(a['trials']) and set(b['cell_mse'])==set(a['cell_tokens']) and set(b['cell_r2'])==set(a['cell_tokens']),'Every original trial and cell metric')
            require(all(finite(x) and x>=0 for x in b['cell_mse'].values()) and all(x is None or finite(x) for x in b['cell_r2'].values()),'Finite proper cell error and nullable signed diagnostic')
            for trial,t in a['trials'].items():
                observed=b['trials'][trial]
                require(observed['time_count']==t['time_count'] and observed['fold']==t['fold'],'Original query grid and held-out trial fold')
                for field in ('mse','squared_error_sum','training_baseline_squared_error_sum'):
                    v=observed[field];require(type(v) is list and len(v)==len(a['cell_tokens']) and all(finite(x) and x>=0 for x in v),'Complete reported per-cell error metadata; no numeric arrays reread')
        hierarchy=got['mse_hierarchy'];require(hierarchy['available'] is True and hierarchy['unavailable_acquisitions']==[],'Complete primary cell/acquisition/session/animal hierarchy')
        for field,keys in (('acquisitions',set(want)),('sessions',{a['session'] for a in want.values()}),('animals',{a['animal'] for a in want.values()})):
            require(set(hierarchy[field])==keys and all(finite(x) and x>=0 for x in hierarchy[field].values()),'Complete reported hierarchy membership')
    require(value['query_count']==queries and value['complete_two_modality_primary_available'] is all(bool(x) for x in expected.values()),'Complete original modality/query status')
    if require_both:require(value['complete_two_modality_primary_available'] is True,'Both full original modalities required')


def grade_chain(reader,phases,plan,core,controller,report,support,expected,views,source_pin):
    encoding=[];native=[];grades=[]
    for role in core.ROLES:
        for profile in core.PROFILES:
            matches=[p for p in phases.values() if p['slot']['stage']=='grade_encoding' and p['slot']['producer_role']==role and p['slot']['profile']==profile];require(len(matches)==1,'Every exact role/profile encoding grade')
            phase=matches[0];value,p=selected_result(reader,phase)
            require(value['schema']=='paper_i_final_result_v1' and value['operator_private'] is True and value['native_views_are_overlapping_diagnostics_only'] is True,'Original private full encoding grade')
            grade_metrics(value['metrics'],expected,True);require(set(value['native_view_diagnostics'])==set(views),'Every original native-view diagnostic disposition')
            for name,want in views.items():
                d=value['native_view_diagnostics'][name];count=sum(t['time_count'] for m in want.values() for a in m.values() for t in a['trials'].values())
                if count==0:equal(d,{'status':'unavailable','reason':'no_query_support_for_native_view','query_count':0},'Explicit empty source view')
                else:require(d['status']=='available' and d['query_count']==count,'Complete original view support');grade_metrics(d['metrics'],want,False)
            encoding.append({'role':role,'profile':profile,'pin':p,'phase_id':phase['phase_id']});grades.append((phase,value,p))
    for branch in core.BRANCHES:
        matches=[p for p in phases.values() if p['slot']['stage']=='grade_native' and p['slot']['branch']==branch];require(len(matches)==1,'Every original native branch grade')
        phase=matches[0];value,p=selected_result(reader,phase);require(value['schema']=='paper_i_native_branch_grade_v1' and value['complete'] is True and value['branch']==branch and value['biological_truth'] is False and set(value['arms'])=={'A','B'},'Original complete native three-arm grade')
        inputs=phase['exposure']['mounts']['/input']['files'];expected_inputs={'PAYLOAD.json':inputs['PAYLOAD.json']}
        payload={'schema':'paper_i_worker_native_grade_v1','branch':branch}
        for role in core.ROLES:
            producer=[p for p in phases.values() if p['slot']['stage']=='reconstruct' and p['slot']['producer_role']==role and p['slot']['branch']==branch];require(len(producer)==1,'Every exact native producer')
            name='native/NATIVE.json' if role=='reference' else 'NATIVE.json';d=producer[0]['outputs'][name];expected_inputs[role+'.json']=d;payload[role]={'path':role+'.json','pin':d}
        equal(inputs,expected_inputs,'Native grade consumes all three full closed original-tree exports')
        equal(reader.canonical(payload),inputs['PAYLOAD.json'],'Exact source-bound native grade request, no numeric regrading')
        for role,a in value['arms'].items():
            require(a['branch']==branch and a['all_roots_present'] is True and integer(a['elements'],1) and integer(a['matched']) and a['matched']<=a['elements'] and finite(a['fraction']) and 0<=a['fraction']<=1,'All original root/status/membership checks retained in qualified native grader')
            leaves=a['leaves'];require(type(leaves) is list and len({x['key'] for x in leaves})==len(leaves),'Complete unique native leaf summaries')
            for leaf in leaves:require(leaf['key'].split('/')[0] in core.BRANCHES[branch]['targets'] and integer(leaf['elements']) and integer(leaf['matched']) and leaf['matched']<=leaf['elements'] and type(leaf['exact_discrete']) is bool,'Original native leaf/status summary')
            require(set(a['matlab_versions'])=={'reference','candidate'},'Native producer version provenance')
        native.append({'branch':branch,'pin':p,'phase_id':phase['phase_id']});grades.append((phase,value,p))
    report_phases=[p for p in phases.values() if p['slot']['stage']=='report'];require(len(report_phases)==1,'Exactly one complete final report')
    phase=report_phases[0];value,report_pin=selected_result(reader,phase);equal(value,report,'Raw final report is exact operator phase result')
    require(report['schema']=='paper_i_closed_report_v1' and report['operator_private'] is True and report['source_pins_authenticated'] is True and report['scientific_completeness']=='controller-admitted status','Original source-private closed report')
    closed=report['closed_results'];require(type(closed) is list and len(closed)==21,'All12 encoding plus9 native results')
    refs=[];input_files=phase['exposure']['mounts']['/input']['files'];want_files={'PAYLOAD.json':input_files['PAYLOAD.json']}
    for i,(actual,(g,value,p)) in enumerate(zip(closed,grades)):
        ref={'path':'/input/'+str(i)+'.json','pin':p};equal(actual,{'source':ref,'result':value},'Exact original21-result controller order/body/pin');refs.append(ref);want_files[str(i)+'.json']=p
    equal(input_files,want_files,'Report has exactly all original authenticated grade inputs')
    status=report['status'];equal(status['jobs'],controller['jobs'],'Report all87 terminal jobs');equal(status['source'],source_pin,'Original scientific runtime manifest')
    require(status['complete_required_grades'] is True and status['candidate_internal_fit_counts_observed'] is False and status['actual_native_memory_IO_unknown'] is True and status['released_processed_target_estimand'] is True,'Original completeness and explicit resource/estimand limits')
    require(status['reference_scheduled_logical_fits']==plan['counts']['reference_total_cell_fits'] and status['actual_queries_completed']==sum(p['slot']['stage'] in ('inner_query','outer_query') for p in phases.values()),'Original full fit/query workload, not high-level producer count')
    equal(status['upstream_processing'],support['processing'],'Original processed-target/transductive lineage retained')
    equal(reader.canonical({'schema':'paper_i_worker_report_v1','closed_results':refs,'status':status}),input_files['PAYLOAD.json'],'Entire report status and comparisons bind to original controller payload pin')
    pairs=status['paired_comparisons'];require(pairs['schema']=='paper_i_paired_comparisons_v1' and pairs['causal_code_effect_claim'] is False and pairs['combined_modality_scalar'] is None and len(pairs['comparisons'])==12,'Exact original descriptive paired comparison family, no new scientific metric')

    pair_specs=[(r,'CM','reference','CM','primary_candidate_minus_reference') for r in ('A','B')]
    pair_specs += [(r,'CM',r,p,'same_method_information_or_null_control') for r in core.ROLES for p in ('C','M','CM-shuffled')]
    pair_specs += [('B','CM','A','CM','paired_code_access_descriptive_difference')]
    for row,(left,lp,right,rp,kind) in zip(pairs['comparisons'],pair_specs):
        equal(row['left'],{'role':left,'profile':lp},'Exact original left comparison role/profile');equal(row['right'],{'role':right,'profile':rp},'Exact original right comparison role/profile')
        require(row['kind']==kind and row['available'] is True and set(row['modalities'])=={'GrC','CF'},'Every complete original descriptive contrast')
        for modality,summary in row['modalities'].items():
            animals={a['animal'] for a in expected[modality].values()};differences=summary['paired_animal_mse_differences']
            require(set(differences)==animals and all(finite(v) for v in differences.values()) and summary['animals']==len(animals) and finite(summary['mean_difference']) and summary['lower_is_better'] is True and summary['uncertainty_or_significance_claim'] is None,'Full original paired-animal comparison support; no recomputation or new significance')
    require(set(status['native_equal_branch_fraction'])=={'A','B'} and all(finite(x) and 0<=x<=1 for x in status['native_equal_branch_fraction'].values()),'All-nine equal-branch descriptive metadata retained')
    return {'encoding':encoding,'native':native,'report_pin':report_pin,'report_phase_id':phase['phase_id'],'paired_comparisons_bound_to_original_payload':True}

def validate(parent_root,outer_pin,operation,operation_pin,origin,verified_modules,capture):
    """Admit full immutable receipt graph or raise ReceiptFailure.

    capture.read(relative, expected_pin, cap), capture.names(relative,max_entries)
    and capture.observe(seal_relative,cap) are the owner's bounded raw store.
    No fallback filesystem access exists. Caller must first establish natural
    worker closure, root authority and exclusive operator custody.
    """
    try:return _validate(parent_root,outer_pin,operation,operation_pin,origin,verified_modules,capture)
    except ReceiptFailure:raise
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,StopIteration) as error:
        raise ReceiptFailure('Incomplete or incompatible source receipt chain: '+type(error).__name__+': '+str(error)[:300]) from error


def _validate(parent_root,outer_pin,op,operation_pin,origin,modules,capture):
    require(type(parent_root) is str and PurePosixPath(parent_root).is_absolute() and '..' not in PurePosixPath(parent_root).parts,'Exact qualified absolute parent-output root')
    parent_root=str(PurePosixPath(parent_root));descriptor(outer_pin);descriptor(operation_pin)
    core,planner,supervisor=(modules[k] for k in ('core','planner','supervisor'));files=modules['files'];manifest_pin=descriptor(modules['manifest'])
    require(core.TASK==TASK and len(files)==38 and sum(d['bytes'] for d in files.values())==437883,'Exactly the immutable accepted38-member runtime')
    equal(manifest_pin,{'bytes':6012,'sha256':'198aff81c325e3cd56414dbff3e6af5bcc1161995196abb94370340b9a3a2e12'},'Accepted immutable executable manifest identity')
    equal(only_pin(op['source_manifest']),manifest_pin,'Literal unchanged operation source manifest')
    require(op['schema']=='paper_i_operation_v1' and op['task']==TASK and op['scientific_authorization'] is True,'Separately admitted complete operation authority')
    require(finite(origin),'Finite original observer clock');end=origin+op['global_limits']['wall_seconds'];work_end=end-op['host']['cleanup_seconds']
    host=op['host'];reader=Reader(capture,host['max_metadata_bytes'])
    require(integer(capture.outer_cap,1) and capture.outer_cap<=host['parent_limits']['write_bytes'],'Qualified complete outer cap within original parent write allocation')
    outer=reader.obj('OUTER_RECEIPT.json',outer_pin,capture.outer_cap)
    require(outer['schema']=='paper_i_complete_program_outer_receipt_v1' and outer['task']==TASK,'Exact full parent outer receipt schema/task')
    equal(outer['operation'],operation_pin,'Original operation raw identity');equal(reader.obj('OPERATION.json',operation_pin,1048576),op,'Literal unchanged operation body and paths')
    require(outer['origin']==origin and outer['deadline']==end and outer['work_deadline']==work_end,'Original observer/parent/controller global clock')
    equal(outer['global_limits'],op['global_limits'],'Unchanged original global resources');equal(outer['controller_partition_limits'],host['controller_limits'],'Disjoint unchanged controller partition')
    require(outer['source_full_program_complete'] is True and outer['controller_natural_exit'] is True and outer['inner_result_error'] is None and outer['publication_errors']==[],'Full parent result with no hidden failure/publication uncertainty')
    require(all(outer[k] is False for k in ('actual_whole_producer_resources_measured','runtime_qualified','scientific_qualification','whole_paper_reproduced')),'No promotion of source/result into biological or runtime qualification')
    boot=outer['authenticated_bootstrap'];equal(boot['source_manifest'],manifest_pin,'Actually executed source manifest');executed_modules(boot['executed_local_modules'],files)
    require(boot['cached_bytes_used_for_source_copy'] is True and boot['physical_read_bytes']==operation_pin['bytes']+manifest_pin['bytes']+sum(d['bytes'] for d in files.values()),'Exact once-charged operation/manifest/source bootstrap')
    close=controller_close(reader,outer,parent_root,op,operation_pin,origin,end)
    controller_entry=outer['controller_result'];report_entry=outer['controller_report']
    require(set(controller_entry)==set(report_entry)=={'pin','value'},'Pinned embedded controller/report values')
    controller=reader.obj('work/CONTROLLER_RESULT.json',controller_entry['pin']);equal(controller,controller_entry['value'],'Raw controller result equals embedded outer value')
    report=reader.obj('work/report.json',report_entry['pin']);equal(report,report_entry['value'],'Raw report equals embedded outer value')
    require(controller['schema']=='paper_i_controller_result_v1' and controller['complete'] is True and controller['failure'] is None and controller['custody_known'] is True and controller['scientific_qualification'] is False and controller['runtime_qualified_by_external_gate_only'] is True and controller['outer_natural_exit_and_terminal_absence_required'] is True,'Complete controller with independent external closure requirement retained')
    c_events=budget_events(reader,controller['budget'],'work/journal',origin,end,host['controller_limits'],host['max_events'],controller_entry['pin']['bytes'])
    maximum_outer=2+host['max_phases']*(3+2*host['recovery']['max_cli_calls'])
    o_events=budget_events(reader,outer['parent_partition'],'journal',origin,end,host['parent_limits'],maximum_outer,outer_pin['bytes'])
    require(len(o_events)>=2 and o_events[0][0]['event']=='outer_launch_plan' and o_events[1][0]['event']=='CONTROLLER-CHILD' and all(r['event']=='outer_recovery' for r,_ in o_events[2:]),'Exact source-defined terminal outer history')
    launch=o_events[0][0];equal(launch['operation'],operation_pin,'Outer launch operation');equal(launch['source_manifest'],op['source_manifest'],'Literal launch manifest reference');equal(launch['parent_limits'],host['parent_limits'],'Original parent partition');equal(launch['controller_limits'],host['controller_limits'],'Original controller partition')
    require(launch['origin']==origin and launch['global_deadline']==end and launch['work_deadline']==work_end and launch['authenticated_bootstrap_read_bytes']==boot['physical_read_bytes'],'Original launch clock and bootstrap charge')
    executed_modules(launch['executed_local_modules'],files)
    require(all(k in boot['executed_local_modules'] and same(v,boot['executed_local_modules'][k]) for k,v in launch['executed_local_modules'].items()),'Executing local bytes remain identical through closure')
    equal(reader.obj('host_source/VIEW.json',launch['source_view']),{'schema':'osl_closed_role_view_v1','files':files},'Exact complete copied source view membership')
    child=o_events[1][0];equal(child['process_identity'],close['process_identity'],'Actual durable gated controller birth');equal(child['argv'],close['argv'],'Actual gated controller argv');require(child['exec_still_gated'] is True,'Durable controller ownership precedes release')
    allowed={'all_source_images_programs_committed_before_data','plan_admitted','high_level_start','high_level_disposition','nested_start','nested_disposition','transport_event','selection_admitted'}
    require(all(row.get('event') in allowed for row,_ in c_events),'No unadmitted failure/event behind complete report')
    precommits=[r for r,_ in c_events if r['event']=='all_source_images_programs_committed_before_data'];require(len(precommits)==1 and c_events[0][0] is precommits[0],'Complete source/program/image precommit before data')
    commit=precommits[0];equal(commit['source'],op['source_manifest'],'Precommitted literal runtime source');equal(commit['qualification'],only_pin(op['qualification']),'Precommitted external runtime qualification')
    equal(commit['programs'],{r:reader.canonical(op['programs'][r]['source']['files']) for r in ('A','B')},'Both complete committed candidate packages')
    plans=[r for r,_ in c_events if r['event']=='plan_admitted'];require(len(plans)==1 and plans[0]['plan']['path']=='PLAN.json','One complete admitted private plan')
    plan_pin=only_pin(plans[0]['plan']);plan=reader.obj('work/PLAN.json',plan_pin);planner.validate_plan(plan)
    configurations={r:({p:planner.reference_configurations(p) for p in core.PROFILES} if r=='reference' else op['programs'][r]['configurations']) for r in core.ROLES}
    equal(plan['configurations'],configurations,'Original complete candidate and strong reference searches')
    require(plan['counts']['maximum_phase_slots']<=host['max_phases'] and plan['counts']['total_vector_query_process_phases']<=host['max_queries'],'Entire actual parametric roster fits prospective dispatch ceilings')
    starts={};finishes={};transport={}
    for row,_ in c_events:
        event=row['event']
        if event=='nested_start':
            key=phase_id(row['phase_id']);require(key not in starts and planner.valid_slot(plan,row['slot']),'Unique exact nested slot');starts[key]=row;transport[key]=[]
        elif event=='nested_disposition':require(row['phase_id'] in starts and row['phase_id'] not in finishes,'One known phase disposition');finishes[row['phase_id']]=row
        elif event=='transport_event':require(row['phase_id'] in starts,'Known lifecycle phase');transport[row['phase_id']].append(row)
    require(set(starts)==set(finishes) and len(starts)<=host['max_phases'],'Every original dispatched phase terminal')
    equal(reader.names('work/control',host['max_phases']),sorted(starts),'Exact source-owned control-root set')
    equal(reader.names('work/quarantine',host['max_phases']),sorted(starts),'Exact source-owned quarantine-root set')
    equal(reader.names('work/exposures',host['max_phases']),sorted(k+'.json' for k in starts),'No omitted or extra immutable phase exposure')
    source_identity=reader.canonical(files);phases={}
    for key,start in starts.items():phases[key]=phase_admit(reader,parent_root,op,files,source_identity,start,finishes[key],transport[key],origin,end)
    def load_plan(entry):equal(entry,plans[0]['plan'],'Replay exact authenticated plan locator');return plan
    def load_selection(row,observed_starts,observed_done):
        entry=row['selection'];require(set(entry)=={'path','bytes','sha256'},'Exact selection artifact locator')
        match=re.fullmatch(r'quarantine/([A-Za-z0-9_-]{1,96})/RESULT\.json',entry['path']);require(match is not None,'Only source-owned captured selection result')
        key=match.group(1);require(key in phases and key in observed_starts and key in observed_done,'Selection follows observed captured phase')
        phase=phases[key];s=phase['slot'];require(s['stage']=='selection' and s['job_id']==row['job_id'] and s['unit_id']==row['unit_id'],'Exact source-bound training selection slot')
        equal(only_pin(entry),phase['outputs']['RESULT.json'],'Selection in complete authenticated output inventory')
        value,p=selected_result(reader,phase);equal(value['groups'],row['groups'],'Exact captured selected group body')
        selected={'job_id':row['job_id'],'unit_id':row['unit_id'],'groups':value['groups'],'selection_pin':p};planner.validate_selection(plan,selected);return selected
    replay=supervisor.replay_events(c_events,load_plan,origin,end,load_selection,host['max_phases'])
    require(replay['journal_error'] is None and replay['all_high_level_complete'] is True and replay['all_observed_nested_closed'] is True and replay['nested_workload_unknown_without_admitted_plan'] is False and replay['nested_coverage']['complete'] is True,'Raw-authenticated pure source replay has full support and no unresolved work')
    replay.pop('_phase_starts');replay.pop('_ownership_pins');equal(replay,outer['independent_attempt_ledger'],'Exact original independent producer/nested ledger')
    equal(replay['nested_coverage'],controller['nested_coverage'],'Controller and independent full parametric coverage agree')
    jobs=core.high_level_jobs();require(len(jobs)==87 and len(controller['jobs'])==87,'Every exact original producer')
    expected_jobs={j['job_id']:{'job':j,'status':'complete','reason':None,'artifact_pins':[p['receipt_pin'] for p in phases.values() if p['slot']['job_id']==j['job_id']]} for j in jobs}
    equal(controller['jobs'],expected_jobs,'No duplicate, dropped or invented high-level job or phase capture')
    c_reservations=controller['budget']['producer_reservations'];require(set(c_reservations)==set(phases),'All original complete phase reservations')
    for key,p in phases.items():
        r=p['request']['resources'];v=c_reservations[key]
        require(v['read_upper']==2*r['source_read_bytes']+r['inventory_bytes'] and v['write_upper']==v['retained_upper']==r['host_write_bytes']+r['max_output_bytes']+r['scratch_bytes'] and v['settled'] is True and integer(v['retained_exact']) and p['receipt']['cost']['transport_write_bytes']<=v['retained_exact']<=v['retained_upper'],'Original conservative complete phase reservation and closed settlement')
    parent_reservations=outer['parent_partition']['producer_reservations'];require(set(parent_reservations)=={'outer_recovery_'+k for k in phases},'Every independent recovery charged to original parent share')
    for v in parent_reservations.values():require(v['read_upper']==host['recovery']['source_read_bytes'] and v['write_upper']==v['retained_upper']==host['recovery']['host_write_bytes'] and v['settled'] is False,'No hidden refreshed or refunded independent recovery budget')
    recovery=recoveries(reader,outer,o_events,phases,op,outer['controller_close'],origin,end)
    ordering(plan,phases,replay['authenticated_selections'])
    seal=encoding_seal(reader,c_events,jobs,controller['jobs'],phases)
    support,support_pin,expected,views=support_metadata(reader,phases,plan,op)
    grades=grade_chain(reader,phases,plan,core,controller,report,support,expected,views,manifest_pin)
    equal(grades['report_pin'],report_entry['pin'],'Same exact report phase/file/outer identity')
    return {'schema':'paper_i_central_admitted_receipt_chain_v1','task':TASK,'complete_receipt_chain':True,'operation':operation_pin,
        'parent_source_manifest':manifest_pin,'origin':origin,'original_deadline':end,'parent_root':parent_root,
        'pins':{'outer':outer_pin,'controller_close':outer['controller_close'],'controller_result':controller_entry['pin'],'plan':plan_pin,'support':support_pin,'report':report_entry['pin'],'observed_seal_pin':seal['pin']},
        'seal':seal,'jobs':{'total':87,'encoding':60,'native':27,'all_terminal_complete':True},
        'nested':{'observed_phases':len(phases),'counts':plan['counts'],'coverage':replay['nested_coverage']},
        'grades':grades,'independent_recovery':recovery,
        'raw_journal_authority':{'controller':'CONTROLLER_RESULT.budget.events','parent':'OUTER_RECEIPT.parent_partition.events','controller_events':len(c_events),'parent_events':len(o_events),'no_undisclosed_later_events':True},
        'metadata_admission_cost':{'unique_captured_bytes':reader.raw_bytes,'source_defined_canonical_metadata_bytes':reader.canonical_bytes,'no_outer_reserialization':True},
        'original_logical_costs':{'parent_snapshot_read':outer['parent_partition']['logical_read_charge'],'parent_snapshot_write':outer['parent_partition']['logical_write_charge'],'parent_final_outer_publication_bytes':outer_pin['bytes'],'controller_snapshot_read':controller['budget']['logical_read_charge'],'controller_snapshot_write':controller['budget']['logical_write_charge'],'controller_final_result_publication_bytes':controller_entry['pin']['bytes'],'candidate_internal_operations_observed':False,'kernel_IO_or_RSS_measured':False},
        'limits':{'scientific_regrading_performed':False,'numeric_array_bodies_read':False,'seal_has_upstream_pin_or_timestamp':False,'worker_custody_must_be_admitted_by_caller':True,'observer_natural_exit_remains_required':True,'runtime_qualification_inherited':False,'scientific_qualification':False,'whole_paper_reproduced':False}}
