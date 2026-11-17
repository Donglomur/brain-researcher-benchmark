# Concatenated after common/build/route. No sibling-file import or producer call.
import builtins as _s_builtins
import types as _s_types
import math as _s_math
import re as _s_re
import time as _s_time
from contextlib import contextmanager as _s_contextmanager
from pathlib import Path as _SPath

_S_TASK = 'NEURAL-049'
_S_PROFILE = 'curated_retrospective_full_v1'
_S_ACTIONS = {
    'select-run': {'profile'}, 'request-prepare': {'run','payload'},
    'bind-prepare': {'request','qualifications','launcher'},
    'request-bank': {'run','payload','preparation_completion'},
    'bind-bank': {'request','qualification','launcher'},
    'request-execution': {'run','payload','preparation_completion','bank_completion','bank_qualification'},
    'bind-execution': {'request','qualifications'},
    'request-review': {'run','authority','selection'},
    'bind-request': {'request','approval'},
    'bind-review': {'review_plan','request_bundle','qualification'},
    'admit-approved-review': {'review','approval_registry'},
    'bind-collection-completion': {'run','authority','collection','completion'},
    'request-late-grade': {'run','authority','collection_bundle','payload'},
    'bind-late-grade': {'request','declaration'},
}
_S_RUN_FIELDS = {'schema','task_id','profile','instance','original_clock','modules','cache','roots',
    'execution_fields','preparation_fields','bank_fields','resource_selection','observer_selection',
    'operator_identity','unresolved','status'}
_S_PREP_FIELDS = {'schema','status','origin','deadline','limits','source_root','output_root','metadata_root',
    'protected_roots','source_closure','roster','sources','axes','environment','module_D'}
_S_BANK_FIELDS = {'schema','active','source_manifest','backend','context','operator_identity','evidence_cap',
    'preparation_context','packet','copy_bytes','root','packet_root','source_root','output_root','operator_root',
    'secrets_root','kernel_read_per_file','kernel_write_per_file','array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'}
_S_EXEC_FIELDS = {'schema','active','task_id','profile','source_manifest','modules','cache','roots','clock',
    'resources','profiles','provider_profiles','episode_limits','native_public','native_private','grading',
    'method_admissions','operator_identity','packet','bank','preparation_context','provider','host_python',
    'host_environment','actor_environment_inventory','reference_tolerance','seed_contract','numerical_contract',
    'base_generation','numerical_environments'}
_S_REVIEW_FIELDS = {'schema','task_id','selected','operation','panel','condition','selected_modules','cache',
    'central_source','parent_source','registry','authority','instance_request','instance_declaration','original_origin',
    'central_observation_deadline','central_validation_deadline','other_reserve_bytes','limits',
    'collection','collection_completion','grading_selection','roots'}
_S_REVIEW_LIMITS = {'read_bytes','write_bytes','host_memory_bytes','parent_retained_storage_bytes','free_floor_bytes',
    'qualification_read_bytes','validation_read_bytes','validation_cpu_ns','validation_numeric'}
_S_CENTRAL_FINDINGS = {'complete_panel','inherited_clock','central_resources','public_array_validation_resources',
    'actual_caller_observation','physical_root_custody','interpreter_environment','protected_scoring_boundary'}
_S_ROOTS = {'source','packet','targets','reference','output','operator','observation','secrets','store'}
_S_CAP = 2097152
_S_BANK_RESOURCE_KEYS = {'context','evidence_cap','copy_bytes','kernel_read_per_file','kernel_write_per_file',
                        'array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'}
_S_EXEC_RESOURCE_KEYS = {'resources','profiles','provider_profiles','episode_limits','preparation_context'}
_S_CENTRAL_SELECTION_KEYS = {'central_observation_deadline','central_validation_deadline','limits','other_reserve_bytes'}
_S_PORTABLE_CLOCK_KEYS = ('original_origin','central_observation_deadline','central_validation_deadline')


def _s_equal(a, b):
    if type(a) is not type(b): return False
    if type(a) is dict: return set(a) == set(b) and all(_s_equal(a[k],b[k]) for k in a)
    if type(a) is list: return len(a) == len(b) and all(_s_equal(x,y) for x,y in zip(a,b))
    return a == b


def _s_pos(value, zero=False):
    need(type(value) is int and value >= (0 if zero else 1), 'stage ordinary integer')
    return value


def _s_finite(value):
    need(type(value) in (int,float) and _s_math.isfinite(value), 'stage finite clock')
    return value


def _s_portable_clock(value):
    """Exactly the consumer's finite-float projection; never samples a clock."""
    return float(_s_finite(value))


def _s_portable_clock_projection(values):
    return {k:_s_portable_clock(values[k]) for k in _S_PORTABLE_CLOCK_KEYS}


def _s_require_portable_clocks(value):
    for k in _S_PORTABLE_CLOCK_KEYS:
        need(type(value[k]) is float,'issued portable clock must already be canonical float: '+k)
        _s_portable_clock(value[k])


def _s_central_selection_projection(value):
    return {k:(_s_portable_clock(value[k]) if k in _S_PORTABLE_CLOCK_KEYS else value[k])
            for k in _S_CENTRAL_SELECTION_KEYS}


def _s_approval_entries(entries):
    need(type(entries) is list and 1<=len(entries)<=32,'bounded final approval entries')
    return entries


def _s_under(path, root, direct=False):
    path,root=canonical_path(str(path)),canonical_path(str(root))
    need(path.parent == root if direct else root in path.parents, 'fixed stage metadata namespace')
    return path


def _s_disjoint(a,b):
    a,b=canonical_path(str(a)),canonical_path(str(b))
    return a != b and a not in b.parents and b not in a.parents


def _s_descriptor(value):
    descriptor(value);canonical_path(value['path']);return value


def _s_read(io, d, root=None, cap=_S_CAP):
    _s_descriptor(d)
    path=canonical_path(d['path'])
    need(path.suffix == '.json', 'constructor accepts bounded JSON metadata only')
    if root is not None: _s_under(path,root)
    held=getattr(io,'_neural049_stage_retained',None)
    if held is not None:
        reservation=io.hold(14*(d['pin']['bytes']+1)+4096,'retained stage metadata until terminal result')
        reservation.__enter__();held.append(reservation)
    return io.json(path,expected=d['pin'],cap=cap,readonly=True)


def _s_put(io, root, name, value, cap=_S_CAP):
    need(type(name) is str and _s_re.fullmatch('[A-Z][A-Z0-9_]*[.]json',name), 'fixed source-owned stage output name')
    return io.put(root/name,value,cap=cap)


@_s_contextmanager
def _s_capsule(io, instance):
    """Private captured metadata definitions; no sys.modules mutation or producer import."""
    names={'core':'program/core.py','contracts':'program/contracts.py','configuration':'program/configuration.py',
           'prep_contracts':'preparation/contracts.py','authority':'program/authority.py'}
    bodies={}
    size=sum(instance['immutable']['parent/'+v]['bytes']+1 for v in names.values())
    with io.hold(size*16+65536,'captured metadata-only definitions'):
        for name,relative in names.items():
            expected=instance['immutable']['parent/'+relative]
            bodies[name]=io.read(instance['parent']/relative,expected=expected,cap=_S_CAP,readonly=True)
        modules={}
        def imported(name,globals=None,locals=None,fromlist=(),level=0):
            need(level == 0,'no relative capsule import')
            if name in names:
                need(name in modules,'capsule dependency order')
                return modules[name]
            need(name.split('.')[0] in {'hashlib','json','math','os','stat','sys','time','pathlib','re'},
                 'metadata-only standard library import')
            return _s_builtins.__import__(name,globals,locals,fromlist,level)
        for name in names:
            module=_s_types.ModuleType('_neural049_metadata_'+name)
            module.__dict__['__builtins__']={**vars(_s_builtins),'__import__':imported}
            io.tick();exec(compile(bodies[name],str(instance['parent']/names[name]),'exec',dont_inherit=True),module.__dict__);io.tick()
            modules[name]=module
        yield modules


def _s_route_admission(io,instance,registry,operation,condition):
    """Invoke actual captured routing, including its selected generic/scoring checks."""
    need(operation in ('collect','grade') and condition in (None,_S_PROFILE)
         and (operation!='grade' or condition is None),'exact selected operation and condition')
    names=('central/io.py','central/routing.py','shared/qualification.py','shared/launch_parser.py')
    retained=sum(instance['immutable'][n]['bytes']+1 for n in names)*16+65536
    with io.hold(retained,'complete source-bound routing and generic metadata definitions'):
        modules={}
        for name in ('io','routing'):
            relative='central/'+name+'.py';expected=instance['immutable'][relative]
            body=io.read(instance['root']/relative,expected=expected,cap=_S_CAP,readonly=True)
            module=_s_types.ModuleType('_neural049_stage_route_'+name)
            module.__file__=str(instance['root']/relative)
            io.tick();exec(compile(body,module.__file__,'exec',dont_inherit=True),module.__dict__);io.tick()
            modules[name]=module
        modules['routing'].u=modules['io']
        base,parser=_generic(io,instance)
        class MetadataHost:
            def read(self,path,cap,expected=None,readonly=False,retain=True):
                return io.read(path,expected=expected,cap=cap,readonly=readonly)
            def reserve(self,n):
                io.reserve_read(n,'actual selected route generic maximum')
                io.unobserved_external_read_reservations=getattr(io,'unobserved_external_read_reservations',0)+n
            def tick(self):return io.tick()
        env={'repo':instance['root'],'here':instance['central'],'freeze_files':instance['source_freeze']['files'],
             'manifest':instance['central_manifest'],'base':base,'gate':parser}
        return modules['routing'].qualify(registry,{'operation':operation,'condition':condition},env,MetadataHost())


def _s_roots(instance, roots):
    exact(roots,_S_ROOTS,'exact complete parent roots')
    need(canonical_path(roots['source']) == instance['parent'],'unchanged parent source root')
    need(canonical_path(roots['targets']) == canonical_path(roots['packet'])/'private','fixed protected target subtree')
    names=[k for k in roots if k != 'targets']
    need(all(_s_disjoint(roots[a],roots[b]) for i,a in enumerate(names) for b in names[i+1:]),'pairwise disjoint parent roots')
    need(all(_s_disjoint(instance['root'],roots[k]) for k in names if k != 'source'),'external roots outside entire instance')
    _s_under(instance['operator_metadata'],roots['operator'])


def _s_run(io, instance, desc):
    run=_s_read(io,desc,instance['operator_metadata'])
    exact(run,_S_RUN_FIELDS,'exact run selection')
    need(run['schema']=='neural049_portable_run_selection_v1' and run['task_id']==_S_TASK
         and run['profile']==_S_PROFILE and _s_equal(run['instance'],instance['instance'])
         and run['status']=='selected_not_qualified','same selected source-only run')
    clock=run['original_clock'];exact(clock,{'origin','production_end','observation_end','readback_end'},'original run clock')
    times=[_s_finite(clock[k]) for k in ('origin','production_end','observation_end','readback_end')]
    need(all(x<y for x,y in zip(times,times[1:])) and io.origin==times[0] and io.deadline<=times[-1],
         'same original clock, never extend parent grading')
    need(type(run['modules']) is list and run['modules'] and run['modules']==[x for x in ('core','T1','D') if x in run['modules']]
         and run['modules'][0]=='core' and len(run['modules'])==len(set(run['modules'])) and type(run['cache']) is bool,'complete modules/cache')
    need(type(run['operator_identity']) is str and run['operator_identity'],'selected independent external operator')
    need(type(run['unresolved']) is list,'explicit unresolved inventory')
    for row in run['unresolved']:
        exact(row,{'name','status','reason','role'},'unresolved slot')
        need(row['status']=='missing' and all(type(row[k]) is str and row[k] for k in ('name','reason','role')),'truthful missing slot')
    _s_roots(instance,run['roots']);_s_selected_fields(run);io.tick();return run


def _s_selected_fields(run):
    """Positive stable projections; no future completion or proof hash placeholders."""
    names=('preparation_fields','bank_fields','execution_fields','resource_selection','observer_selection')
    if run['unresolved']:
        need(all(run[k] is None or type(run[k]) is dict for k in names),'unresolved maps are not admissible')
        return
    prep,bank,execution=(run[k] for k in names[:3])
    exact(prep,_S_PREP_FIELDS,'all stable preparation settings selected')
    exact(bank,_S_BANK_FIELDS-{'packet'},'all stable bank settings selected')
    exact(execution,_S_EXEC_FIELDS-{'packet','bank'},'all stable execution settings selected')
    expected={'preparation':prep['limits'],'bank':{k:bank[k] for k in _S_BANK_RESOURCE_KEYS},
              'execution':{k:execution[k] for k in _S_EXEC_RESOURCE_KEYS}}
    need(_s_equal(run['resource_selection'],expected),'one exact typed resource selection')
    obs=run['observer_selection']
    exact(obs,{'host_python','host_environment','native_public','native_private','central','prepare_launcher',
               'bank_launcher','execution_bank_qualification_path'},'positive observer selection')
    for k in ('host_python','host_environment','native_public','native_private'):
        need(_s_equal(obs[k],execution[k]),'exact preselected observer '+k)
    exact(obs['central'],_S_CENTRAL_SELECTION_KEYS,'preselected central limits and capture clocks')
    for k in ('prepare_launcher','bank_launcher'):
        exact(obs[k],{'python','context','operation_live_bytes'},'preselected complete original launcher')
        canonical_path(obs[k]['python']);need(type(obs[k]['context']) is dict,'explicit complete launcher context')
    proof=_s_under(obs['execution_bank_qualification_path'],run['roots']['operator'])
    need(proof.suffix=='.json','preselected bank proof metadata slot')


def _s_packet_operand(run,packet):
    exact(packet,{'root','complete'},'only actual complete packet operands')
    need(packet['root']==run['roots']['packet'],'fixed selected packet root')
    exact(packet['complete'],{'path','pin'},'fixed actual packet completion')
    need(packet['complete']['path']=='COMPLETE.json','only actual fixed packet completion')
    _s_descriptor({'path':str(canonical_path(packet['root'])/'COMPLETE.json'),'pin':packet['complete']['pin']})


def _s_stable(run,kind,payload,allow_unresolved_bank=False):
    deferred={'prepare':set(),'bank':{'packet'},'execution':{'packet','bank'}}[kind]
    selected=run[{'prepare':'preparation_fields','bank':'bank_fields','execution':'execution_fields'}[kind]]
    need(_s_equal({k:v for k,v in payload.items() if k not in deferred},selected),
         'no drift from selected stable '+kind+' fields')
    if kind in ('bank','execution'):_s_packet_operand(run,payload['packet'])
    if kind=='execution':
        bank=payload['bank'];exact(bank,{'manifest','manifest_kernel','qualification'},'only named future bank operands')
        exact(bank['manifest'],{'path','pin'},'actual immutable STORE descriptor')
        need(bank['manifest']['path']=='STORE.json','fixed STORE metadata')
        _s_descriptor({'path':str(canonical_path(run['roots']['store'])/'STORE.json'),'pin':bank['manifest']['pin']})
        exact(bank['qualification'],{'path','pin'},'explicit fixed bank proof slot')
        if allow_unresolved_bank and bank['qualification']['pin'] is None:
            canonical_path(bank['qualification']['path'])
        else:_s_descriptor(bank['qualification'])
        need(bank['qualification']['path']==run['observer_selection']['execution_bank_qualification_path']
             and type(bank['manifest_kernel']) is dict and bank['manifest_kernel'],'preselected proof path and actual kernel metadata')


def _s_ready(run):
    need(not run['unresolved'],'dependent authentic fields unresolved; no binding')


def _s_evidence(io, rows, run):
    need(type(rows) is list and 1<=len(rows)<=32,'bounded nonempty independent metadata evidence')
    for d in rows:
        _s_read(io,d,run['roots']['operator'],cap=1048576)


def _s_original_evidence(io,rows,run):
    need(type(rows) is list and 1<=len(rows)<=32,'bounded original relative evidence set')
    for row in rows:
        exact(row,{'path','pin'},'original relative evidence descriptor')
        relative=relative_path(row['path'])
        _s_read(io,{'path':str(canonical_path(run['roots']['operator'])/relative),'pin':row['pin']},
                run['roots']['operator'],cap=1048576)


def _s_projection(kind, payload):
    proof='qualification' if kind=='bank' else 'qualifications'
    other='qualifications' if proof=='qualification' else 'qualification'
    need(type(payload) is dict and proof not in payload and other not in payload,'exact original proof omission; no singular/plural substitution')
    raw=encode(payload);need(raw.endswith(b'\n'),'new metadata encoding has exactly final newline')
    # Original prep.canonical/core.encoded selection predicates exclude that newline.
    return pin_bytes(raw[:-1])


def _s_prepare_fields(io, instance, run, payload, capsule):
    _s_stable(run,'prepare',payload)
    exact(payload,_S_PREP_FIELDS,'full preparation projection')
    c=capsule['prep_contracts']
    need(payload['schema']=='neural049_prepare_authority_v1' and payload['status']=='selected_qualified_prepare'
         and payload['module_D'] is ('D' in run['modules']),'planned original preparation values')
    need(payload['origin']==run['original_clock']['origin'] and payload['deadline']==run['original_clock']['readback_end'], 'preparation original clock')
    exact(payload['limits'],c.BASE_LIMITS|c.EXTRA_LIMITS,'complete original preparation caps')
    for x in payload['limits'].values():_s_pos(x)
    need(payload['limits']['files']==payload['limits']['output_files'],'original output-file cap alias')
    need(canonical_path(payload['output_root'])==canonical_path(run['roots']['packet']),'prepared complete packet destination')
    need(canonical_path(payload['metadata_root'])==instance['operator_metadata'],'original authority base is selected external P')
    paths=[payload['source_root'],payload['output_root'],payload['metadata_root'],*payload['protected_roots']]
    need(all(_s_disjoint(a,b) for i,a in enumerate(paths) for b in paths[i+1:]),'exact preparation disjoint roots')
    need(_s_disjoint(payload['source_root'],instance['root']),'RAW recording root is not code root')
    exact(payload['environment'],{'numpy','h5py','memory_profile'},'preparation environment')
    for k in ('source_closure','roster'):c.artifact(payload[k])
    c.artifact(payload['environment']['memory_profile'])
    for k in ('numpy','h5py'):need(type(payload['environment'][k]) is str and payload['environment'][k],'pinned preparation libraries')
    roster_pin={'bytes':15248,'sha256':'d40b7d1e197d30c8e895d35d86dd567e7927bb16e72a9e136ade168784b09a51'}
    need(payload['roster']['pin']==roster_pin,'exact original55 source roster')
    roster=_s_read(io,{'path':str(canonical_path(payload['metadata_root'])/c.relative(payload['roster']['path'])),'pin':roster_pin},payload['metadata_root'])
    need(roster.get('schema')=='neural049_held_roster_v1' and type(roster.get('sources')) is list and len(roster['sources'])==55,'complete roster metadata')
    sources=payload['sources'];need(type(sources) is list and len(sources)==55,'all55 source descriptors; no bodies read')
    for original,row in zip(roster['sources'],sources):
        exact(row,{'person','day','path','pin','geometry'},'source metadata fields')
        need((row['person'],row['day'],row['path'],row['pin'])==(original['person'],original['day'],original['source_path'],
             {'bytes':original['advertised_bytes'],'sha256':original['held_metadata_payload_sha256_not_reverified']}),'exact55 identity ordering')
        need(type(row['geometry']) is dict and row['geometry'].get('schema')==c.SCHEMA,'authentic selected schema declaration')
    need(set(payload['axes'])==set(capsule['contracts'].PEOPLE),'all12 channel unions')
    for person,axis in payload['axes'].items():
        need(type(axis) is list and 0<len(axis)<=payload['limits']['channels'] and len(axis)==len(set(axis)),'complete unique channel axis')
        for item in axis:c.opaque(item)
        union={item['axis_id'] for row in sources if row['person']==person for item in row['geometry']['channel_map']}
        need(union==set(axis),'complete authentic within-person channel union')


def _s_bank_fields(instance,run,payload):
    _s_stable(run,'bank',payload)
    exact(payload,_S_BANK_FIELDS,'full original bank projection')
    need(payload['schema']=='neural049_bank_build_authority_v1' and payload['active'] is True
         and payload['source_manifest']==instance['parent_source'] and payload['backend']=='linux-x86_64-fsverity-sha256-4096-v1'
         and payload['operator_identity']==run['operator_identity'],'actual source-bound planned bank')
    context=payload['context'];exact(context,{'origin','deadline','read_cap','write_cap'},'original bank context')
    need(context['origin']==run['original_clock']['origin'] and context['deadline']==run['original_clock']['readback_end'],'bank original clock')
    for k in ('read_cap','write_cap'):_s_pos(context[k])
    for k in ('evidence_cap','copy_bytes','kernel_read_per_file','kernel_write_per_file','array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'):_s_pos(payload[k])
    mapping={'root':'store','packet_root':'packet','source_root':'source','output_root':'output','operator_root':'operator','secrets_root':'secrets'}
    for key,r in mapping.items():need(canonical_path(payload[key])==canonical_path(run['roots'][r]),'bank root correspondence')
    need(payload['packet']['root']==run['roots']['packet'],'bank complete packet identity')
    need(payload['preparation_context']['origin']==context['origin'] and payload['preparation_context']['deadline']==context['deadline'],'same original preparation subcontext')


def _s_execution_fields(instance,run,payload,allow_unresolved_bank=False):
    _s_stable(run,'execution',payload,allow_unresolved_bank)
    exact(payload,_S_EXEC_FIELDS,'complete original execution projection')
    need(payload['schema']=='neural049_execution_authority_v1' and payload['active'] is True
         and payload['task_id']==_S_TASK and payload['profile']==_S_PROFILE
         and payload['source_manifest']==instance['parent_source'],'original source execution schema')
    for key,expected in [('roots',run['roots']),('clock',run['original_clock']),('modules',run['modules']),('cache',run['cache']),('operator_identity',run['operator_identity'])]:
        need(_s_equal(payload[key],expected),'same run execution '+key)
    need(payload['grading']=={'selected':False},'no future completion/grade authority')


def _s_request(io,instance,d,kind):
    request=_s_read(io,d,instance['operator_metadata'])
    exact(request,{'schema','kind','run','source','payload','payload_pin'},'authority request schema')
    need(request['schema']=='neural049_portable_authority_request_v1' and request['kind']==kind
         and request['source']==instance['parent_source'],'same original authority request')
    need(request['payload_pin']==_s_projection(kind,request['payload']),'unmodified original selection projection')
    run=_s_run(io,instance,request['run']);_s_ready(run)
    return request,run


def _s_external_completion(io,instance,run,run_desc,descriptor_,kind):
    doc=_s_read(io,descriptor_,run['roots']['operator'])
    required={'schema','issuer','realm','instance','source_manifest','run','kind','result','natural_exit','exit_code',
              'streams_complete','capture_completed','provisional','original_origin','evidence'}
    exact(doc,required,'portable original-operation completion metadata')
    need(doc['schema']=='neural049_portable_external_operation_completion_v1' and doc['issuer']==run['operator_identity']
         and doc['realm']=='actual_original_tool_capture' and _s_equal(doc['instance'],instance['instance'])
         and doc['source_manifest']==instance['parent_source'] and doc['kind']==kind
         and _s_equal(doc['run'],run_desc)
         and doc['natural_exit'] is True and type(doc['exit_code']) is int and doc['exit_code']==0
         and doc['streams_complete'] is True and doc['capture_completed'] is True and doc['provisional'] is False
         and doc['original_origin']==run['original_clock']['origin'],'actual externally observed operation closure')
    _s_evidence(io,doc['evidence'],run)
    result_root=canonical_path(run['roots']['packet' if kind=='prepare' else 'store'])
    need(canonical_path(doc['result']['path'])==result_root/'COMPLETE.json','fixed original complete metadata path')
    result=_s_read(io,doc['result'],result_root)
    if kind=='prepare':
        need(result.get('schema')=='neural049_prepare_complete_v1' and result.get('status')=='complete_core_bank'
             and result.get('source_count')==55 and result.get('person_count')==12,'actual full preparation completion')
        if 'D' in run['modules']:need(result.get('assignment_status')=='complete','full selected assignment feasibility')
    else:
        need(result.get('schema')=='neural049_bank_build_result_v1' and result.get('status')=='complete'
             and result.get('source')==instance['parent_source'] and result.get('external_natural_closure_required') is True,
             'actual complete immutable bank metadata')
    return doc,result


def _s_execution_request_payload(io,instance,run,params,capsule,root,outputs):
    """Two explicit request passes; unresolved self-pin never enters a full request."""
    payload=params['payload']
    _s_execution_fields(instance,run,payload,allow_unresolved_bank=True)
    need(payload['bank']['qualification']['pin'] is None,'base-only explicit unresolved bank proof pin')
    pc,pr=_s_external_completion(io,instance,run,params['run'],params['preparation_completion'],'prepare')
    bc,br=_s_external_completion(io,instance,run,params['run'],params['bank_completion'],'bank')
    need(payload['packet']['complete']['pin']==pc['result']['pin'] and payload['bank']['manifest']==br['manifest']
         and payload['bank']['manifest_kernel']==br['manifest_kernel'],'actual complete packet/store before either execution request')
    selected=capsule['authority'].bank_selection_pin(payload,allow_unresolved=True)
    bank={k:v for k,v in payload['bank'].items() if k!='qualification'}
    proof=params['bank_qualification']
    if proof is None:
        outputs['bank_qualification_request']=_s_put(io,root,'BANK_QUALIFICATION_REQUEST.json',{
            'schema':'neural049_portable_bank_qualification_request_v1','run':params['run'],
            'source':instance['parent_source'],'base_payload':payload,'bank_selection':selected,
            'bank':bank,'proof_path':payload['bank']['qualification']['path'],
            'required_proof_schema':'neural049_bank_qualification_v2',
            'status':'bank_prequalification_only_not_executable','executable_authority':False,
            'general_qualification_requests_emitted':False})
        return None
    _s_descriptor(proof)
    need(proof['path']==payload['bank']['qualification']['path'],'exact preselected bank proof path')
    q=_s_read(io,proof,run['roots']['operator'],cap=1048576)
    flags={'natural_build_closure','kernel_enforcement','physical_namespace','individual_mount_custody','complete_packet_join'}
    exact(q,{'schema','qualified','realm','issuer','selection','bank','evidence'}|flags,'exact acyclic bank-consumption proof')
    need(q['schema']=='neural049_bank_qualification_v2' and q['qualified'] is True
         and q['realm']=='actual_external_evidence' and q['issuer']==run['operator_identity']
         and q['selection']==selected and _s_equal(q['bank'],bank) and all(q[k] is True for k in flags),
         'independent bank proof before full authority selection')
    _s_original_evidence(io,q['evidence'],run)
    complete={**payload,'bank':{**payload['bank'],'qualification':proof}}
    _s_execution_fields(instance,run,complete)
    need(capsule['authority'].bank_selection_pin(complete)==selected,'same acyclic domain after exact proof pin attachment')
    return complete


def _s_launcher(io,instance,run,kind,launcher,request_desc):
    need(_s_equal(launcher,run['observer_selection'][kind+'_launcher']),'exact preselected original launcher settings')
    exact(launcher,{'python','context','operation_live_bytes'},'explicit stage launcher selection')
    python=str(canonical_path(launcher['python']));context=launcher['context']
    exact(context,{'schema','operation','origin','deadline','source_read_cap','request_read_cap','outer_read_cap',
        'outer_write_cap','outer_live_cap','failure_write_reserve','operation_context'},'exact stage context')
    need(context['schema']=='neural049_portable_stage_context_v1' and context['operation']==kind
         and context['origin']==run['original_clock']['origin'] and context['deadline']==run['original_clock']['readback_end'],'original stage envelope')
    for k in ('source_read_cap','request_read_cap','outer_read_cap','outer_write_cap','outer_live_cap','failure_write_reserve'):_s_pos(context[k])
    op=context['operation_context']
    need(op['origin']==context['origin'] and op['deadline']==context['deadline'],'no child clock reset')
    if kind=='prepare':
        exact(op,{'origin','deadline','limits'},'preparation operation context')
        need(launcher['operation_live_bytes'] is None,'prepare live bound comes from original limits')
    else:
        exact(op,{'origin','deadline','read_cap','write_cap'},'bank operation context')
        _s_pos(launcher['operation_live_bytes'])
    _s_launch_bounds(instance,kind,launcher,request_desc)
    boot=instance['immutable']['parent/program/bootstrap.py'];source=instance['parent_source']
    argv=[python,'-I','-S','-B',str(instance['root']/'shared/stage_launcher.py'),'--operation',kind,
          '--parent-root',str(instance['parent']),'--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],
          '--bootstrap-bytes',str(boot['bytes']),'--bootstrap-sha256',boot['sha256'],'--request',request_desc['path'],
          '--request-bytes',str(request_desc['pin']['bytes']),'--request-sha256',request_desc['pin']['sha256'],
          '--context-json',encode(context).decode('ascii')]
    return {'schema':'neural049_portable_stage_command_v1','instance':instance['instance'],'operation':kind,
            'argv':argv,'cwd':str(instance['root']),'launcher':{'path':str(instance['root']/'shared/stage_launcher.py'),
            'pin':instance['immutable']['shared/stage_launcher.py']},'request':request_desc,'context':context,
            'status':'bound_external_launch_required','own_future_exit_not_self_certified':True}


def _s_launch_bounds(instance,kind,launcher,request_desc):
    """Same conservative source/request/child/stdout envelope as dormant launcher."""
    c=launcher['context'];op=c['operation_context'];sc=c['source_read_cap'];rc=c['request_read_cap']
    rows=instance['parent_manifest']['files'];source=instance['parent_source']
    boot=instance['immutable']['parent/program/bootstrap.py']
    need(len(rows)==70 and rows.get('program/bootstrap.py')==boot,'full source schedule and bootstrap join')
    exact_source_reads=boot['bytes']+2*source['bytes']+3+sum(v['bytes']+1 for v in rows.values())
    need(sc>=exact_source_reads and rc>=request_desc['pin']['bytes']+1,'complete prospective source/request captures')
    if kind=='prepare':
        limits=op['limits']
        exact(limits,{'read_bytes','write_bytes','array_bytes','metadata_bytes','files','array_elements','live_bytes',
                      'rows','channels','source_files','output_files'},'all original preparation limits')
        for v in limits.values():_s_pos(v)
        need(limits['files']==limits['output_files'],'original output count alias')
        r,w,live=limits['read_bytes'],limits['write_bytes'],limits['live_bytes']
        stdout=12*limits['metadata_bytes']+65536
    else:
        r,w,live=_s_pos(op['read_cap']),_s_pos(op['write_cap']),_s_pos(launcher['operation_live_bytes']);stdout=0
    paths=[str(instance['parent']/relative_path(n)) for n in rows]
    paths += [str(instance['parent']/'program/bootstrap.py'),str(instance['parent']/'RUNTIME_SOURCE_V3.json'),request_desc['path']]
    failure_floor=65536+12*sum(len(n)+32 for n in paths)
    need(c['failure_write_reserve']>=failure_floor,'full source and outer path accounting publication reserve')
    need(c['outer_read_cap']>=sc+rc+r,'whole source/request/child read allowance')
    need(c['outer_write_cap']>=c['failure_write_reserve']+w+16*stdout,'whole child and escaped stdout allowance')
    need(c['outer_live_cap']>=16*(sc+rc)+65536+live+80*stdout+4*c['failure_write_reserve'],
         'whole source/child/escaped-output declared live allowance')


def _s_exec_proofs(io,instance,run,payload,proofs,capsule):
    exact(proofs,set(capsule['contracts'].GATES),'all20 execution gate dispositions')
    selected=_s_projection('execution',payload);bound={}
    for kind in capsule['contracts'].GATES:
        optional=(kind=='tool_custody' and 'T1' not in run['modules']) or (kind=='assignment_feasibility' and 'D' not in run['modules']) or (kind=='reference_cache_custody' and not run['cache'])
        if optional:
            need(proofs[kind]=={'status':'not_selected'},'explicit unselected optional gate')
            bound[kind]=proofs[kind];continue
        d=proofs[kind];q=_s_read(io,d,run['roots']['operator'],cap=1048576)
        exact(q,{'schema','qualified','realm','issuer','kind','task_id','profile','selection','source_manifest','evidence'},'positive actual execution proof')
        need(q['schema']=='neural049_actual_qualification_v1' and q['qualified'] is True
             and q['realm']=='actual_external_evidence' and q['issuer']==run['operator_identity'] and q['kind']==kind
             and q['task_id']==_S_TASK and q['profile']==_S_PROFILE and q['selection']==selected
             and q['source_manifest']==instance['parent_source'],'exact independent execution proof')
        _s_original_evidence(io,q['evidence'],run)
        bound[kind]={'path':str(canonical_path(d['path']).relative_to(canonical_path(run['roots']['operator']))),'pin':d['pin']}
    a={**payload,'qualifications':bound}
    capsule['configuration'].validate(a,instance['parent_source']);io.tick();return a


def _s_authority(io,instance,run,d,capsule):
    a=_s_read(io,d,run['roots']['operator'])
    exact(a,_S_EXEC_FIELDS|{'qualifications'},'bound original execution authority')
    _s_execution_fields(instance,run,{k:v for k,v in a.items() if k!='qualifications'})
    capsule['configuration'].validate(a,instance['parent_source'])
    return a


def _s_request_body(io,instance,d):
    request=_s_read(io,d,instance['operator_metadata'],cap=131072)
    fields={'schema','task_id','profile','instance_declaration','central_source','parent_source','source_freeze','registry',
        'run','authority','operation','condition','program','output','review_slot','original_origin','parent_clock',
        'central_observation_deadline','central_validation_deadline','selected_modules','cache','limits','other_reserve_bytes'}
    exact(request,fields,'positive portable request')
    _s_require_portable_clocks(request)
    need(request['schema']=='neural049_portable_request_v1' and request['task_id']==_S_TASK and request['profile']==_S_PROFILE
         and _s_equal(request['instance_declaration'],instance['selection']) and request['central_source']==instance['central_source']
         and request['parent_source']==instance['parent_source'] and _s_equal(request['source_freeze'],instance['freeze'])
         and request['registry']==instance['registry_state']['current_registry'],'current exact instance/source/request generation')
    _s_under(request['review_slot'],instance['central']/'operator-selections',direct=True)
    need(_SPath(request['review_slot']).suffix=='.json','sealed named review slot')
    return request


def _s_request_approval(io,instance,run,request_desc,d):
    q=_s_read(io,d,run['roots']['operator'],cap=131072)
    exact(q,{'schema','issuer','realm','approved','instance','request','source_freeze','evidence'},'request approval fields')
    need(q['schema']=='neural049_portable_request_approval_v1' and q['issuer']==run['operator_identity']
         and q['realm']=='actual_external_evidence' and q['approved'] is True
         and _s_equal(q['instance'],instance['instance']) and _s_equal(q['request'],request_desc)
         and _s_equal(q['source_freeze'],instance['freeze']),'independent current request approval')
    _s_evidence(io,q['evidence'],run);return q


def _s_review_from_request(instance,request,a,pair):
    _s_require_portable_clocks(request)
    review={'schema':'neural049_portable_central_review_v1','task_id':_S_TASK,'selected':True,
        'operation':request['operation'],'panel':_S_PROFILE,'condition':request['condition'],
        'selected_modules':request['selected_modules'],'cache':request['cache'],'central_source':instance['central_source'],
        'parent_source':instance['parent_source'],'registry':request['registry'],'authority':request['authority'],
        'instance_request':pair,'instance_declaration':instance['selection'],'original_origin':request['original_origin'],
        'central_observation_deadline':request['central_observation_deadline'],
        'central_validation_deadline':request['central_validation_deadline'],'other_reserve_bytes':request['other_reserve_bytes'],
        'limits':request['limits'],'roots':a['roots'],'collection':None,'collection_completion':None,'grading_selection':None}
    return review


def _s_review(io,instance,d,capsule):
    need(canonical_path(d['path']).parent==instance['central']/'operator-selections','fixed final review namespace')
    review=_s_read(io,d,instance['central']/'operator-selections',cap=32768)
    exact(review,_S_REVIEW_FIELDS|{'qualification'},'exact portable final review')
    _s_require_portable_clocks(review)
    pair=review['instance_request'];exact(pair,{'request','approval'},'embedded request/approval pair; no seventh capture')
    request=_s_request_body(io,instance,pair['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
    a=_s_authority(io,instance,run,request['authority'],capsule)
    _s_request_approval(io,instance,run,pair['request'],pair['approval'])
    expected=_s_review_from_request(instance,request,a,pair)
    for k in ('collection','collection_completion','grading_selection'):expected[k]=review[k]
    need(_s_equal({k:v for k,v in review.items() if k!='qualification'},expected)
         and request['review_slot']==d['path'],'review binds exact preceding request and immutable slot')
    _s_review_scope(io,instance,run,a,request,review)
    _s_central_proof(io,instance,run,review,review['qualification'])
    return review,request,run,a


def _s_review_scope(io,instance,run,a,request,review):
    _s_require_portable_clocks(request);_s_require_portable_clocks(review)
    need(_s_equal({k:request[k] for k in _S_CENTRAL_SELECTION_KEYS},
         _s_central_selection_projection(run['observer_selection']['central'])),'exact projected central resource/clock settings')
    need(request['operation'] in ('collect','grade') and request['condition'] in (None,_S_PROFILE)
         and request['original_origin']==_s_portable_clock(a['clock']['origin']) and _s_equal(request['parent_clock'],a['clock'])
         and _s_equal(request['selected_modules'],a['modules']) and request['cache'] is a['cache'],
         'request preserves exact parent operation/clock/modules/cache')
    need(a['clock']['readback_end']<_s_finite(request['central_observation_deadline'])
         <_s_finite(request['central_validation_deadline']), 'capture deadlines cannot extend parent work')
    output=canonical_path(request['output'])
    need(all(_s_disjoint(output,p) for p in [instance['root'],*a['roots'].values()]),'external central output')
    exact(request['limits'],_S_REVIEW_LIMITS,'central limit fields')
    for k,v in request['limits'].items():
        if k!='validation_numeric':_s_pos(v)
    exact(request['limits']['validation_numeric'],{'allocation_bytes','elements','serialized_bytes','files','work'},'validation resources')
    for v in request['limits']['validation_numeric'].values():_s_pos(v)
    _s_pos(request['other_reserve_bytes'],zero=True)
    if request['operation']=='collect':
        need(request['program']==request['authority']['path']
             and all(review[k] is None for k in ('collection','collection_completion','grading_selection')),
             'collection has no invented future grading completion')
    else:
        need(request['condition'] is None and request['program']==review['collection']['path'],'grade uses completed collection')
        doc,end=_s_collection(io,instance,run,a,request['authority'],review['collection'],review['collection_completion'])
        bundle={'collection':review['collection'],'completion':review['collection_completion'],
                'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json']}
        late=_s_read(io,review['grading_selection'],run['roots']['operator'])
        _s_late_fields(instance,run,a,request['authority'],bundle,late)
        _s_late_proof(io,instance,run,a,bundle,late)


def _s_central_proof(io,instance,run,review,d):
    _s_require_portable_clocks(review)
    q=_s_read(io,d,run['roots']['operator'],cap=1048576)
    exact(q,{'schema','realm','qualified','issuer','task_id','central_source','parent_source','selection',
             'authority','original_origin','findings','evidence'},'central qualification schema')
    selected=pin_bytes(encode({k:v for k,v in review.items() if k not in ('qualification','grading_document')}))
    need(q['schema']=='neural049_actual_central_qualification_v1' and q['realm']=='actual_external_evidence'
         and q['qualified'] is True and q['issuer']==run['operator_identity'] and q['task_id']==_S_TASK
         and q['central_source']==instance['central_source'] and q['parent_source']==instance['parent_source']
         and q['selection']==selected and q['authority']==review['authority']['pin']
         and q['original_origin']==review['original_origin'],'exact actual central qualification')
    exact(q['findings'],_S_CENTRAL_FINDINGS,'all8 central findings')
    need(all(v is True for v in q['findings'].values()),'actual external central findings, never constructor-issued')
    _s_evidence(io,q['evidence'],run)


def _s_command(instance,request,a):
    key='grade' if request['operation']=='grade' else ('named' if request['condition']==_S_PROFILE else 'default')
    template=instance['selection_body']['registered_templates'][key]
    need(type(template) is list and template and all(type(x) is str for x in template),'registered literal argv')
    replacements={'{python}':a['host_python'],'{program}':request['program'],'{output}':request['output'],
                  '{review}':request['review_slot'],'{other_reserve_bytes}':str(request['other_reserve_bytes'])}
    argv=[replacements.get(x,x) for x in template]
    need(argv[0]==a['host_python'] and not any('{' in x or '}' in x for x in argv),'whole-token exact registered substitution')
    argv[1]=str(instance['root']/relative_path(template[1]))
    return argv


def _s_collection(io,instance,run,a,authority,collection,completion):
    path=canonical_path(collection['path']);need(path.name=='RESULT.json','original central RESULT only')
    need(_s_disjoint(path.parent,instance['root']) and all(_s_disjoint(path.parent,r) for r in a['roots'].values()),'central output outside source/every parent root')
    doc=_s_read(io,collection,cap=131072)
    need(doc.get('schema')=='neural049_central_result_v1' and doc.get('status')=='complete' and doc.get('operation')=='collect'
         and doc.get('panel')==_S_PROFILE and doc.get('central_source')==instance['central_source']
         and doc.get('parent_source')==instance['parent_source'] and doc.get('authority')==authority['pin']
         and doc.get('original_origin')==a['clock']['origin'] and doc.get('selected_modules')==a['modules']
         and doc.get('cache') is a['cache'] and doc.get('private_grading_performed') is False
         and doc.get('actual_parent_operation_observed') is True and doc.get('own_future_exit_not_self_certified') is True,'original complete collection is not its future-exit witness')
    end=_s_read(io,completion,run['roots']['operator'],cap=1048576)
    fields={'schema','realm','issuer','central_source','parent_source','authority','collection','review','provisional',
            'exit_code','natural_exit','streams_complete','observed_after_central_return','completed_at','argv','cwd','capture_artifacts'}
    exact(end,fields,'external original central completion')
    need(end['schema']=='neural049_external_central_completion_v1' and end['realm']=='actual_original_tool_capture'
         and end['issuer']==run['operator_identity'] and end['central_source']==instance['central_source']
         and end['parent_source']==instance['parent_source'] and end['authority']==authority['pin']
         and _s_equal(end['collection'],collection) and end['review']==doc['review']
         and end['provisional'] is False and type(end['exit_code']) is int and end['exit_code']==0
         and end['natural_exit'] is True and end['streams_complete'] is True and end['observed_after_central_return'] is True
         and _s_finite(doc['observed_end'])<=_s_finite(end['completed_at'])<run['original_clock']['readback_end']
         and end['completed_at']<=_s_time.monotonic(),
         'actual central wait/stream/chronology witness before original late-grade deadline')
    intent=_s_read(io,{'path':str(path.parent/'INTENT.json'),'pin':doc['receipts']['intent']},cap=131072)
    need(end['argv']==intent['central_argv'] and end['cwd']==str(instance['root'])
         and intent['review']==doc['review'] and intent['authority']==authority['pin'],'same original argv/cwd/review/authority')
    _s_evidence(io,end['capture_artifacts'],run);io.tick();return doc,end


def _s_late_fields(instance,run,a,authority,collection_bundle,payload):
    exact(payload,{'schema','active','issuer','selection','source_manifest','original_origin','observation','external_completion','output'},'original late-grading declaration fields')
    selected=_s_projection('execution',{k:v for k,v in a.items() if k!='qualifications'})
    need(payload['schema']=='neural049_late_grading_authority_v1' and payload['active'] is True
         and payload['issuer']==run['operator_identity'] and payload['selection']==selected
         and payload['source_manifest']==instance['parent_source'] and payload['original_origin']==a['clock']['origin']
         and payload['observation']==collection_bundle['observation'],'exact original late target-last declaration')
    need(canonical_path(payload['output']).parent==canonical_path(a['roots']['observation']),'fixed protected score output leaf')


def _s_late_proof(io,instance,run,a,bundle,payload):
    rel=payload['external_completion'];exact(rel,{'path','pin'},'original relative outer-completion proof')
    p=canonical_path(run['roots']['operator'])/relative_path(rel['path'])
    end=_s_read(io,{'path':str(p),'pin':rel['pin']},run['roots']['operator'],cap=1048576)
    need(end.get('schema')=='neural049_external_outer_completion_v1' and end.get('natural') is True
         and type(end.get('exit_code')) is int and end['exit_code']==0 and end.get('source_manifest')==instance['parent_source']
         and end.get('observation')==payload['observation'] and end.get('original_origin')==a['clock']['origin']
         and end.get('issuer')==run['operator_identity'] and end.get('streams_closed') is True
         and end.get('capture_completed') is True and end.get('provisional') is False
         and end.get('central_collection')==bundle['collection'] and end.get('central_external_completion')==bundle['completion']
         and end.get('nested_caller')==bundle['nested_caller'],'independent nested/original central outer completion join')
    _s_evidence(io,[{'path':str(canonical_path(run['roots']['operator'])/relative_path(d['path'])),'pin':d['pin']} for d in end['evidence']],run)


def assemble_stage(io, action, build_descriptor, input_descriptor):
    need(not hasattr(io,'_neural049_stage_retained'),'no nested stage retention scope')
    held=[];io._neural049_stage_retained=held
    try:return _s_assemble_stage(io,action,build_descriptor,input_descriptor)
    finally:
        for reservation in reversed(held):reservation.__exit__(None,None,None)
        del io._neural049_stage_retained


def _s_assemble_stage(io, action, build_descriptor, input_descriptor):
    """All14 finite metadata stages. No scientific producer or subprocess call."""
    need(action in _S_ACTIONS,'selected finite metadata action')
    inp=_s_read(io,input_descriptor)
    exact(inp,{'schema','action','registry_state','name','parameters'},'stage input wrapper')
    need(inp['schema']=='neural049_portable_stage_input_v1' and inp['action']==action,'explicit selected stage')
    name=inp['name'];need(type(name) is str and _s_re.fullmatch('[A-Za-z0-9_-]{1,64}',name),'fixed fresh stage token')
    params=inp['parameters'];exact(params,_S_ACTIONS[action],'positive action parameters')
    instance=load_instance(io,build_descriptor,inp['registry_state'])
    _s_under(input_descriptor['path'],instance['operator_metadata'])
    with _s_capsule(io,instance) as capsule:
        root=instance['operator_metadata']/(action+'--'+name)
        io.claim_root(root)
        outputs={};status='metadata_bound_external_execution_required'
        if action=='select-run':
            profile=_s_read(io,params['profile'],instance['operator_metadata'])
            fields=(_S_RUN_FIELDS-{'task_id','profile','instance','status'})
            exact(profile,fields,'exact source-only run profile')
            need(profile['schema']=='neural049_portable_run_profile_v1','run profile schema')
            run={**profile,'schema':'neural049_portable_run_selection_v1','task_id':_S_TASK,'profile':_S_PROFILE,
                 'instance':instance['instance'],'status':'selected_not_qualified'}
            outputs['run']=_s_put(io,root,'RUN.json',run)
            _s_run(io,instance,outputs['run']);status='selected_not_qualified'
        elif action in ('request-prepare','request-bank','request-execution'):
            kind=action[len('request-'):];run=_s_run(io,instance,params['run'])
            if run['unresolved']:
                outputs['plan']=_s_put(io,root,'PLAN.json',{'schema':'neural049_portable_unresolved_stage_plan_v1',
                    'action':action,'run':params['run'],'status':'selected_not_qualified','unresolved':run['unresolved'],
                    'no_authority_or_admissible_payload_pin':True})
            else:
                payload=params['payload']
                if kind=='prepare':_s_prepare_fields(io,instance,run,payload,capsule)
                elif kind=='bank':
                    _s_bank_fields(instance,run,payload)
                    completion,result=_s_external_completion(io,instance,run,params['run'],params['preparation_completion'],'prepare')
                    need(payload['packet']['complete']['pin']==completion['result']['pin'],'bank exact actual complete packet')
                else:payload=_s_execution_request_payload(io,instance,run,params,capsule,root,outputs)
                if payload is not None:
                    selected=_s_projection(kind,payload)
                    request={'schema':'neural049_portable_authority_request_v1','kind':kind,'run':params['run'],
                             'source':instance['parent_source'],'payload':payload,'payload_pin':selected}
                    outputs['request']=_s_put(io,root,'REQUEST.json',request)
                    kinds=capsule['prep_contracts'].QUALIFICATIONS if kind=='prepare' else capsule['contracts'].GATES if kind=='execution' else ('immutable_bank_build',)
                    rows=[]
                    for gate in kinds:
                        off=kind=='execution' and ((gate=='tool_custody' and 'T1' not in run['modules']) or
                            (gate=='assignment_feasibility' and 'D' not in run['modules']) or (gate=='reference_cache_custody' and not run['cache']))
                        rows.append({'kind':gate,'selection':selected,'source_manifest':instance['parent_source'],
                            'issuer':run['operator_identity'],'status':'not_selected' if off else 'external_actual_evidence_required'})
                    outputs['qualification_requests']=_s_put(io,root,'QUALIFICATION_REQUESTS.json',{'schema':'neural049_portable_qualification_requests_v1',
                        'request':outputs['request'],'requests':rows,'method_admissions':payload.get('method_admissions',{}),
                        'status':'selected_not_qualified','no_verdicts_generated':True})
            status='selected_not_qualified'
        elif action=='bind-prepare':
            request,run=_s_request(io,instance,params['request'],'prepare');a=request['payload']
            _s_prepare_fields(io,instance,run,a,capsule)
            qmap=params['qualifications'];exact(qmap,set(capsule['prep_contracts'].QUALIFICATIONS),'all10 original preparation proofs')
            bound={}
            for kind,d in qmap.items():
                q=_s_read(io,d,instance['operator_metadata'],cap=1048576)
                exact(q,{'schema','status','check','selection','independent_producer','evidence','external_completion'},'preparation proof schema')
                need(q['schema']=='neural049_independent_qualification_v1' and q['status']=='qualified'
                     and q['check']==kind and q['selection']==request['payload_pin']
                     and q['independent_producer']==run['operator_identity'],'same independently issued preparation selection')
                rows=[q['external_completion'],*q['evidence']]
                need(type(q['evidence']) is list and 1<=len(q['evidence'])<=32,'actual preparation evidence')
                for row in rows:
                    capsule['prep_contracts'].artifact(row)
                    _s_read(io,{'path':str(instance['operator_metadata']/row['path']),'pin':row['pin']},instance['operator_metadata'],cap=1048576)
                bound[kind]={'path':str(canonical_path(d['path']).relative_to(instance['operator_metadata'])),'pin':d['pin']}
            for key,d in [('source_closure',a['source_closure']),('memory_profile',a['environment']['memory_profile'])]:
                value=_s_read(io,{'path':str(instance['operator_metadata']/d['path']),'pin':d['pin']},instance['operator_metadata'])
                if key=='source_closure':need(value.get('schema')=='neural049_preparation_source_closure_v1' and value.get('files')
                    and _s_equal(value.get('environment'),a['environment']),'real preparation source/environment closure')
            authority={**a,'qualifications':bound}
            need(_s_projection('prepare',{k:v for k,v in authority.items() if k!='qualifications'})==request['payload_pin'],'unchanged prepare projection')
            # The ONLY extra selected P leaf; original authority bootstrap fixes its parent.
            outputs['authority']=io.put(instance['operator_metadata']/('prepare-authority-'+name+'.json'),authority,cap=_S_CAP)
            worker={'schema':'neural049_preparation_worker_request_v1','operation':'prepare',
                    'authority_path':outputs['authority']['path'],'authority_pin':outputs['authority']['pin']}
            need(_s_equal(params['launcher']['context']['operation_context'],{'origin':a['origin'],'deadline':a['deadline'],'limits':a['limits']}),'exact original preparation subcontext')
            outputs['worker_request']=_s_put(io,root,'WORKER_REQUEST.json',worker)
            outputs['command']=_s_put(io,root,'COMMAND.json',_s_launcher(io,instance,run,'prepare',params['launcher'],outputs['worker_request']))
        elif action=='bind-bank':
            request,run=_s_request(io,instance,params['request'],'bank');a=request['payload'];_s_bank_fields(instance,run,a)
            q=_s_read(io,params['qualification'],run['roots']['operator'],cap=1048576)
            flags={'backend','exclusive_namespace','source_completion','full_resource_plan','external_observer'}
            exact(q,{'qualified','realm','selection','source_manifest','issuer','evidence'}|flags,'original bank proof positive fields')
            need(q['qualified'] is True and q['realm']=='actual_external_evidence' and q['selection']==request['payload_pin']
                 and q['source_manifest']==instance['parent_source'] and q['issuer']==run['operator_identity']
                 and all(q[k] is True for k in flags),'actual independently issued bank proof')
            _s_evidence(io,q['evidence'],run)
            authority={**a,'qualification':params['qualification']}
            need(_s_projection('bank',{k:v for k,v in authority.items() if k!='qualification'})==request['payload_pin'],'unchanged bank projection')
            need(_s_equal(params['launcher']['context']['operation_context'],a['context']),'exact original bank context')
            outputs['authority']=_s_put(io,root,'AUTHORITY.json',authority)
            worker={'schema':'neural049_portable_bank_stage_request_v1','authority':outputs['authority'],
                    'source_manifest':instance['parent_source'],'operation_live_bytes':_s_pos(params['launcher']['operation_live_bytes'])}
            outputs['worker_request']=_s_put(io,root,'WORKER_REQUEST.json',worker)
            outputs['command']=_s_put(io,root,'COMMAND.json',_s_launcher(io,instance,run,'bank',params['launcher'],outputs['worker_request']))
        elif action=='bind-execution':
            request,run=_s_request(io,instance,params['request'],'execution');payload=request['payload']
            _s_execution_fields(instance,run,payload)
            authority=_s_exec_proofs(io,instance,run,payload,params['qualifications'],capsule)
            need(_s_projection('execution',{k:v for k,v in authority.items() if k!='qualifications'})==request['payload_pin'],'original execution projection unchanged')
            outputs['authority']=_s_put(io,root,'AUTHORITY.json',authority)
        elif action=='request-review':
            run=_s_run(io,instance,params['run']);_s_ready(run);a=_s_authority(io,instance,run,params['authority'],capsule)
            registry=io.json(instance['registry'],expected=instance['registry_state']['current_registry'],cap=131072,readonly=True)
            s=params['selection'];exact(s,{'operation','condition','output','review_slot','central_observation_deadline',
                 'central_validation_deadline','limits','other_reserve_bytes','collection','collection_completion','grading_selection'},'central selection fields')
            need(_s_equal(_s_central_selection_projection(s),_s_central_selection_projection(run['observer_selection']['central'])),'exact projected preselected central settings')
            need(s['operation'] in ('collect','grade') and s['condition'] in (None,_S_PROFILE),'registered operation/alias')
            _s_route_admission(io,instance,registry,s['operation'],s['condition'])
            if s['operation']=='collect':need(all(s[k] is None for k in ('collection','collection_completion','grading_selection')),'no future grade placeholders')
            else:
                need(s['condition'] is None,'grade default alias')
                doc,end=_s_collection(io,instance,run,a,params['authority'],s['collection'],s['collection_completion'])
                late=_s_read(io,s['grading_selection'],run['roots']['operator'])
                bundle={'collection':s['collection'],'completion':s['collection_completion'],'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json']}
                _s_late_fields(instance,run,a,params['authority'],bundle,late);_s_late_proof(io,instance,run,a,bundle,late)
            output=canonical_path(s['output']);need(all(_s_disjoint(output,p) for p in [instance['root'],*a['roots'].values()]),'central output disjoint from every source/parent root')
            slot=_s_under(s['review_slot'],instance['central']/'operator-selections',direct=True)
            need(slot.suffix=='.json' and _s_re.fullmatch('[A-Za-z0-9_-]{1,64}',slot.stem) and not slot.exists(),'fresh named final review slot')
            exact(s['limits'],_S_REVIEW_LIMITS,'full central selected limits')
            for k,v in s['limits'].items():
                if k!='validation_numeric':_s_pos(v)
            exact(s['limits']['validation_numeric'],{'allocation_bytes','elements','serialized_bytes','files','work'},'full central public validation resources')
            for v in s['limits']['validation_numeric'].values():_s_pos(v)
            _s_pos(s['other_reserve_bytes'],zero=True)
            need(a['clock']['readback_end']<_s_finite(s['central_observation_deadline'])<_s_finite(s['central_validation_deadline']),'later capture bounds never extend parent grade')
            request={'schema':'neural049_portable_request_v1','task_id':_S_TASK,'profile':_S_PROFILE,'instance_declaration':instance['selection'],
                'central_source':instance['central_source'],'parent_source':instance['parent_source'],'source_freeze':instance['freeze'],
                'registry':instance['registry_state']['current_registry'],'run':params['run'],'authority':params['authority'],
                'operation':s['operation'],'condition':s['condition'],'program':params['authority']['path'] if s['operation']=='collect' else s['collection']['path'],
                'output':str(output),'review_slot':str(slot),'original_origin':a['clock']['origin'],'parent_clock':a['clock'],
                'central_observation_deadline':s['central_observation_deadline'],'central_validation_deadline':s['central_validation_deadline'],
                'selected_modules':a['modules'],'cache':a['cache'],'limits':s['limits'],'other_reserve_bytes':s['other_reserve_bytes']}
            request.update(_s_portable_clock_projection(request))
            outputs['request']=_s_put(io,root,'REQUEST.json',request,131072)
            review=_s_review_from_request(instance,request,a,None)
            for k in ('collection','collection_completion','grading_selection'):review[k]=s[k]
            outputs['review_plan']=_s_put(io,root,'REVIEW_PLAN.json',{'schema':'neural049_portable_review_plan_v1','request':outputs['request'],
                'review':review,'status':'selected_not_qualified','request_approval_and_central_qualification_absent':True})
            status='selected_not_qualified'
        elif action=='bind-request':
            request=_s_request_body(io,instance,params['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
            _s_request_approval(io,instance,run,params['request'],params['approval'])
            bundle={'schema':'neural049_portable_request_bundle_v1','request':params['request'],'approval':params['approval']}
            outputs['request_bundle']=_s_put(io,root,'REQUEST_BUNDLE.json',bundle)
            outputs['qualification_next_step']=_s_put(io,root,'QUALIFICATION_NEXT_STEP.json',{'schema':'neural049_portable_review_qualification_next_step_v1',
                'request_bundle':outputs['request_bundle'],'required':'independently issue central qualification over the full review plan plus this pair, excluding qualification only',
                'no_qualification_verdict_generated':True})
        elif action=='bind-review':
            plan=_s_read(io,params['review_plan'],instance['operator_metadata'])
            exact(plan,{'schema','request','review','status','request_approval_and_central_qualification_absent'},'earlier review plan')
            need(plan['schema']=='neural049_portable_review_plan_v1' and plan['status']=='selected_not_qualified'
                 and plan['request_approval_and_central_qualification_absent'] is True,'unqualified earlier review projection')
            bundle=_s_read(io,params['request_bundle'],instance['operator_metadata']);exact(bundle,{'schema','request','approval'},'request bundle')
            need(bundle['schema']=='neural049_portable_request_bundle_v1' and _s_equal(bundle['request'],plan['request']),'same approved request')
            request=_s_request_body(io,instance,bundle['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
            a=_s_authority(io,instance,run,request['authority'],capsule);_s_request_approval(io,instance,run,bundle['request'],bundle['approval'])
            pair={k:bundle[k] for k in ('request','approval')};review=_s_review_from_request(instance,request,a,pair)
            for k in ('collection','collection_completion','grading_selection'):review[k]=plan['review'][k]
            expected={**review,'instance_request':None};need(_s_equal(plan['review'],expected),'exact untouched earlier review plan')
            _s_review_scope(io,instance,run,a,request,review)
            _s_central_proof(io,instance,run,review,params['qualification']);review['qualification']=params['qualification']
            need(pin_bytes(encode(review))['bytes']<=32768,'original final review ceiling')
            outputs['review']=io.put(canonical_path(request['review_slot']),review,cap=32768)
            outputs['approval_request']=_s_put(io,root,'APPROVAL_REQUEST.json',{'schema':'neural049_portable_final_approval_request_v1',
                'instance':instance['instance'],'source_freeze':instance['freeze'],'review':outputs['review'],'request':bundle['request'],
                'registry':request['registry'],'actual_argv':_s_command(instance,request,a),'cwd':str(instance['root']),
                'environment_pin':pin_bytes(encode(a['host_environment'])),'status':'external_actual_approval_required'})
        elif action=='admit-approved-review':
            review,request,run,a=_s_review(io,instance,params['review'],capsule)
            expected_path=instance['central']/'operator-selections'/'APPROVAL_REGISTRY.json'
            need(canonical_path(params['approval_registry']['path'])==expected_path,'fixed independent final approval registry')
            q=_s_read(io,params['approval_registry'],instance['central']/'operator-selections',cap=131072)
            exact(q,{'schema','instance','issuer','source_freeze','entries','evidence_set'},'final review approvals')
            need(q['schema']=='neural049_portable_review_approvals_v1' and _s_equal(q['instance'],instance['instance'])
                 and q['issuer']==run['operator_identity'] and _s_equal(q['source_freeze'],instance['freeze']),'same actual external final approvals')
            _s_approval_entries(q['entries'])
            matches=[]
            for entry in q['entries']:
                exact(entry,{'review','request','registry','actual_argv','cwd','environment_pin','approved','evidence'},'positive final approval entry')
                if _s_equal(entry['review'],params['review']):matches.append(entry)
            need(len(matches)==1,'exactly one matching final review approval')
            entry=matches[0];argv=_s_command(instance,request,a)
            need(entry['approved'] is True and _s_equal(entry['request'],review['instance_request']['request'])
                 and entry['registry']==instance['registry_state']['current_registry'] and entry['actual_argv']==argv
                 and entry['cwd']==str(instance['root']) and entry['environment_pin']==pin_bytes(encode(a['host_environment'])),'exact original argv/cwd/environment/current-J approval')
            _s_evidence(io,entry['evidence'],run)
            evidence=_s_read(io,q['evidence_set'],run['roots']['operator'],cap=131072)
            exact(evidence,{'schema','instance','issuer','realm','approved_entries_pin','evidence','independent_producer'},'complete approval evidence set')
            need(evidence['schema']=='neural049_portable_approval_evidence_set_v1' and _s_equal(evidence['instance'],instance['instance'])
                 and evidence['issuer']==run['operator_identity'] and evidence['realm']=='actual_external_evidence'
                 and evidence['approved_entries_pin']==pin_bytes(encode(q['entries'])) and type(evidence['independent_producer']) is str
                 and evidence['independent_producer'],'exact full approved entry set binding')
            _s_evidence(io,evidence['evidence'],run)
            outputs['command']=_s_put(io,root,'COMMAND.json',{'schema':'neural049_portable_approved_command_v1','instance':instance['instance'],
                'review':params['review'],'approval_registry':params['approval_registry'],'argv':argv,'cwd':str(instance['root']),
                'environment':a['host_environment'],'environment_pin':entry['environment_pin'],'status':'external_launch_required',
                'own_future_exit_not_self_certified':True})
        elif action=='bind-collection-completion':
            run=_s_run(io,instance,params['run']);_s_ready(run);a=_s_authority(io,instance,run,params['authority'],capsule)
            doc,end=_s_collection(io,instance,run,a,params['authority'],params['collection'],params['completion'])
            outputs['collection_bundle']=_s_put(io,root,'COLLECTION_BUNDLE.json',{'schema':'neural049_portable_collection_completion_bundle_v1',
                'instance':instance['instance'],'run':params['run'],'authority':params['authority'],'collection':params['collection'],
                'completion':params['completion'],'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json'],
                'original_origin':a['clock']['origin'],'observed_completion_at':end['completed_at'],'status':'external_original_completion_bound'})
        elif action in ('request-late-grade','bind-late-grade'):
            if action=='request-late-grade':
                run_desc=params['run'];authority_desc=params['authority'];bundle_desc=params['collection_bundle'];payload=params['payload']
            else:
                req=_s_read(io,params['request'],instance['operator_metadata'])
                exact(req,{'schema','run','authority','collection_bundle','payload','payload_pin','status'},'late-grade request')
                need(req['schema']=='neural049_portable_late_grade_request_v1' and req['status']=='external_actual_declaration_required'
                     and req['payload_pin']==pin_bytes(encode(req['payload'])),'unchanged late-grade request')
                run_desc=req['run'];authority_desc=req['authority'];bundle_desc=req['collection_bundle'];payload=req['payload']
            run=_s_run(io,instance,run_desc);_s_ready(run);a=_s_authority(io,instance,run,authority_desc,capsule)
            bundle=_s_read(io,bundle_desc,instance['operator_metadata'])
            exact(bundle,{'schema','instance','run','authority','collection','completion','observation','nested_caller','original_origin','observed_completion_at','status'},'completed collection bundle')
            need(bundle['schema']=='neural049_portable_collection_completion_bundle_v1' and _s_equal(bundle['instance'],instance['instance'])
                 and _s_equal(bundle['run'],run_desc) and _s_equal(bundle['authority'],authority_desc)
                 and bundle['status']=='external_original_completion_bound','same completed original collection')
            doc,end=_s_collection(io,instance,run,a,authority_desc,bundle['collection'],bundle['completion'])
            need(bundle['observation']==doc['joined']['observation'] and bundle['nested_caller']==doc['receipts']['CALLER.json'],'actual nested metadata unchanged')
            _s_late_fields(instance,run,a,authority_desc,bundle,payload)
            _s_late_proof(io,instance,run,a,bundle,payload)
            if action=='request-late-grade':
                outputs['request']=_s_put(io,root,'REQUEST.json',{'schema':'neural049_portable_late_grade_request_v1','run':run_desc,
                    'authority':authority_desc,'collection_bundle':bundle_desc,'payload':payload,'payload_pin':pin_bytes(encode(payload)),
                    'status':'external_actual_declaration_required'});status='selected_not_qualified'
            else:
                actual=_s_read(io,params['declaration'],run['roots']['operator'])
                need(_s_equal(actual,payload),'independently issued exact late declaration; no constructor verdict')
                outputs['declaration_bundle']=_s_put(io,root,'DECLARATION_BUNDLE.json',{'schema':'neural049_portable_late_grade_bundle_v1',
                    'request':params['request'],'declaration':params['declaration'],'collection_bundle':bundle_desc,
                    'status':'external_grade_review_request_required','protected_targets_read':False})
        else:raise Refusal('unimplemented stage')
        # No usable final result survives a current-J change during metadata assembly.
        io.read(instance['registry'],expected=instance['registry_state']['current_registry'],cap=131072,readonly=True)
        io.tick()
        result={'schema':'neural049_portable_stage_result_v1','action':action,'status':status,'instance':instance['instance'],
                'registry_state':instance['registry_state_descriptor'],'outputs':outputs,'costs':io.record(),'automatic_retry':False}
        result_desc=_s_put(io,root,'STAGE_RESULT.json',result)
        io.tick();return {'result':result_desc,'action':action,'status':status,'instance':instance['instance'],
                'registry_state':instance['registry_state_descriptor'],'outputs':outputs,'costs_after_result_publication':io.record()}
