"""Root-adopted complete CI report contracts and public paired output ABI.

These functions inspect ordinary metadata only. They neither invent scientific
outputs nor qualify a missing original producer. The original numerical and
native bodies are unchanged; candidate is an operation, never a new kind.
"""
from pathlib import Path
from .custody import read_pin,parse,descriptor,need,pin,encode
from .guard import RequiredUnscorable
from .views import validate_pair,materialize
from four_programmes.common import closed,integer,bounded_size,relative,Store,failure,same
from four_programmes.precommit_records import validate_type
from four_programmes.schema import check
from four_programmes.observer import OriginalProcessObservation
from .programme_links_v3 import require_canonical_v3,read_known_v3_links

CONDITIONS=("paper_data","paper_data_author_code")
EXECUTION=("prepare","independent_reference","native_reference","candidate")
ROW=("job_id","operation","kind","report_relative_path","report_cap_bytes","report_role",
     "public_ABI_binding","producer_source","availability","missing_producer","producer_by_condition")
NUMERIC_SOURCE={"path":"authoring/delivery-20261105/common/remaining-builds-wave39/critical-init-complete-design/implementation-v1/successor-v3/critical_init/workflow.py",
                "bytes":10875,"sha256":"9f95ba69439ee5486b3acfdad933d6b86c51f9ca51d86360ba28e2dc39df9ecc"}
NATIVE_SOURCE={"path":"authoring/delivery-20261105/common/remaining-builds-wave39/critical-init-complete-design/implementation-v1/successor-v3/critical_init/native_worker.py",
               "bytes":9673,"sha256":"36e92f71758759ae08b4b3f09288347b7789977d34ac4305da9eff13ef1b4802"}
_COMPILED=object()
_VIEWS=object()

def _json_shape(schema,depth=0):
    """Closed bounded literal public identity grammar, with no refs or callbacks."""
    need(type(schema) is dict and depth<=16,"finite public identity schema")
    kind=schema.get('type')
    if kind=='object':
        closed(schema,('type','properties','required','additionalProperties'))
        need(schema['additionalProperties'] is False and type(schema['properties']) is dict and
             type(schema['required']) is list and len(schema['properties'])<=128 and
             len(set(schema['required']))==len(schema['required']) and
             set(schema['required'])==set(schema['properties']),'closed complete identity fields')
        for key,spec in schema['properties'].items():
            need(type(key) is str and 0<len(key)<=256,'bounded literal identity field')
            _json_shape(spec,depth+1)
    elif kind=='array':
        closed(schema,('type','items','minItems','maxItems'))
        integer(schema['minItems']);integer(schema['maxItems']);need(schema['minItems']<=schema['maxItems']<=8192,'finite identity array')
        _json_shape(schema['items'],depth+1)
    elif kind=='string':
        closed(schema,('type','minLength','maxLength'))
        integer(schema['minLength']);integer(schema['maxLength']);need(schema['minLength']<=schema['maxLength']<=4096,'finite identity string')
    elif kind in ('integer','number'):
        closed(schema,('type','minimum','maximum'))
        # Source-owned schema.check rejects nonfinite values and boolean numbers.
        for value in (schema['minimum'],schema['maximum']):check(value,{'type':'number'})
        need(schema['minimum']<=schema['maximum'],'ordered finite identity bounds')
    else:
        closed(schema,('type',));need(kind in ('boolean','null'),'closed original JSON identity type')

def _bundle_schema(shapes):
    need(type(shapes) is dict and 0<len(shapes)<=8192,'complete finite original array-name schema')
    for name,spec in shapes.items():
        need(type(name) is str and 0<len(name)<=256 and '/' not in name and '\\' not in name and name not in ('.','..'),
             'ordinary original NPZ member name')
        closed(spec,('shape','dtype'))
        need(type(spec['shape']) is list and len(spec['shape'])<=32,'original bounded rank')
        for n in spec['shape']:integer(n)
        need(type(spec['dtype']) is str and 0<len(spec['dtype'])<=64,'literal original dtype')
    # Original read_npz retains authoritative dtype/header/payload checks later.

def validate_public_abi(abi,census,scope_digest,meter):
    meter.charge('work_units',bounded_size(abi))
    validate_type('PublicABI',abi)
    need(abi['scope_digest']==scope_digest,'fixed same full scope public ABI v2')
    jobs=[j for j in census['jobs']if j['operation']=='candidate']
    need([r['job_id']for r in abi['jobs']]==[j['id']for j in jobs],'full original candidate order in public ABI')
    out={}
    for row,job in zip(abi['jobs'],jobs):
        need(same(row['kind'],job['kind'])and same(row['task_expected_outputs'],job['expected_outputs']),
             'exact source-selected output declaration, never inferred from results')
        out[job['id']]=row
    return out

def validate_policy(policy,policy_pin,abi,abi_pin,paired,census,census_pin,scope_digest,meter,
                    *,execution_binding,public_interface,seals):
    meter.charge('work_units',bounded_size(policy)+bounded_size(paired)+bounded_size(execution_binding)+
                 bounded_size(public_interface)+bounded_size(seals))
    validate_type('PairedPolicy',policy);validate_type('ExecutionBinding',execution_binding)
    validate_type('PublicTaskInterface',public_interface)
    descriptor(policy_pin);descriptor(abi_pin)
    need(pin(encode(policy))=={k:policy_pin[k]for k in ('bytes','sha256')}and
         pin(encode(abi))=={k:abi_pin[k]for k in ('bytes','sha256')},'actual v4 policy and v2 ABI bytes')
    need(policy['census']==census_pin and execution_binding['final_census']==census_pin,
         'same final complete execution census')
    need(pin(encode(execution_binding))=={k:policy['execution_binding'][k]for k in ('bytes','sha256')},
         'actual prior execution binding bytes')
    need(execution_binding['public_ABI']==abi_pin and execution_binding['public_interface']==abi['task_interface'] and
         execution_binding['agent_policy']==policy['same_agent_policy'] and execution_binding['seals']==policy['programme_seals'],
         'exact earlier interface/ABI/agent policy/two-seal ancestry')
    need(pin(encode(public_interface))=={k:abi['task_interface'][k]for k in ('bytes','sha256')}and
         public_interface['scope_digest']==scope_digest,'actual original public interface content')
    need(pin(encode(paired))=={k:policy['paired_view_manifest'][k]for k in ('bytes','sha256')},'actual paired view manifest bytes')
    validate_pair(paired)
    visible=[m for m in paired['common']if m['source']==abi_pin]
    need(len(visible)==1 and visible[0]['role']=='task'and all(m['source']!=abi_pin for m in paired['author_code']),
         'same earlier ABI exactly once in common view before development')
    by_job=validate_public_abi(abi,census,scope_digest,meter)
    candidates=[j for j in census['jobs']if j['operation']=='candidate'];ids=[j['id']for j in candidates]
    need([r['job_id']for r in public_interface['jobs']]==ids and [r['job_id']for r in policy['jobs']]==ids,
         'full original interface/policy/census order')
    for public,job in zip(public_interface['jobs'],candidates):
        need(same(public['kind'],job['kind'])and same(public['task_expected_outputs'],job['expected_outputs']),
             'earlier public scientific question equals final selected job')
    closed(seals,CONDITIONS);producer_maps={key:{}for key in ids};pair_closure=None
    for condition in CONDITIONS:
        seal=seals[condition];validate_type('ProgrammeSeal',seal)
        expected=policy['programme_seals'][condition]
        require_canonical_v3(seal,expected,'ProgrammeSeal')
        need(seal['condition']==condition and seal['agent_policy']==policy['same_agent_policy'],
             'same fixed agent policy and exact original arm')
        need([row['job_id']for row in seal['jobs']]==ids,'every scientific job has its actual per-arm report producer')
        if pair_closure is None:pair_closure=seal['pair_closure']
        else:need(seal['pair_closure']==pair_closure,'both seals derive from the same actual pair closure')
        need(len({encode(row)for row in seal['source_closure']})==len(seal['source_closure']),
             'no duplicate sealed programme source descriptor')
        for row in seal['jobs']:
            need(row['report_producer']in seal['source_closure'],'actual report producer is in this arm sealed programme source')
            producer_maps[row['job_id']][condition]=row['report_producer']
    need(policy['programme_seals'][CONDITIONS[0]]!=policy['programme_seals'][CONDITIONS[1]],
         'two distinct original arm seals')
    policy_jobs={}
    for row,job in zip(policy['jobs'],candidates):
        need(row['command']==job['command']==execution_binding['dispatcher_argv'] and
             row['command_source_pins']==job['command_source_pins']==execution_binding['dispatcher_source'],
             'one common dispatcher; actual scientific producers remain separate per-arm seal sources')
        policy_jobs[job['id']]={**row,'report_producer_by_condition':producer_maps[job['id']]}
    return by_job,policy_jobs

class OutputContract:
    __slots__=('body','pin','policy','policy_pin','abi','abi_pin','abi_jobs','policy_jobs','rows','paired','_token')
    def __init__(self,token,**values):
        need(token is _COMPILED,'actual complete source compiler')
        for k,v in values.items():setattr(self,k,v)
        self._token=token
    def require_executable(self):
        missing=[r for r in self.body['ordered_jobs'] if r['availability']=='required_unscorable']
        if missing:raise RequiredUnscorable('G08','Complete output contract contains missing mandatory original producers',missing)
        return self

def compile_contract(body,contract_pin,*,census,census_pin,campaign_id,scope_digest,
                     policy,policy_pin,abi,abi_pin,paired,meter,execution_binding,public_interface,seals):
    meter.charge('work_units',bounded_size(body))
    closed(body,('schema','campaign_id','census','scope_digest','participant_policy','ordered_jobs'))
    descriptor(contract_pin)
    need(pin(encode(body))=={k:contract_pin[k]for k in ('bytes','sha256')},'actual full v2 output contract bytes')
    need(body['schema']=='critical_init_complete_job_output_contract_v2'and body['campaign_id']==campaign_id and
         execution_binding['campaign_id']==campaign_id and body['census']==census_pin and
         body['scope_digest']==scope_digest and body['participant_policy']==policy_pin,
         'same exact whole source census/scope/campaign/policy')
    abi_jobs,policy_jobs=validate_policy(policy,policy_pin,abi,abi_pin,paired,census,census_pin,scope_digest,meter,
                                       execution_binding=execution_binding,public_interface=public_interface,seals=seals)
    need(type(body['ordered_jobs'])is list and len(census['jobs'])==len(body['ordered_jobs'])and
         [r['job_id']for r in body['ordered_jobs']]==[j['id']for j in census['jobs']],'every job once in full original order')
    need(len({j['id']for j in census['jobs']})==len(census['jobs']),'no duplicate full census job')
    rows={}
    for row,job in zip(body['ordered_jobs'],census['jobs']):
        closed(row,ROW)
        need(row['operation']==job['operation']and row['kind']==job['kind']and job['kind']in ('numeric','native','artifact'),
             'original operation/kind separation')
        route=None;producers=None
        if job['operation']=='candidate':
            route=('candidate_report.json','candidate_collection_report',None,policy_pin)
            producers=policy_jobs[job['id']]['report_producer_by_condition']
        elif job['operation']in ('prepare','independent_reference')and job['kind']=='numeric':
            route=('result.json','independent_numeric_report',NUMERIC_SOURCE,None)
        elif job['operation']=='native_reference'and job['kind']=='native':
            route=('native_result.json','original_native_report',NATIVE_SOURCE,None)
        if route is None:
            need(row['availability']=='required_unscorable'and type(row['missing_producer'])is str and
                 0<len(row['missing_producer'])<=4096 and all(row[k]is None for k in
                 ('report_relative_path','report_cap_bytes','report_role','public_ABI_binding','producer_source','producer_by_condition')),
                 'mandatory unknown original producer remains required_unscorable')
        else:
            need(row['availability']=='available'and row['missing_producer']is None,'closed available original row')
            integer(row['report_cap_bytes'],1)
            need((row['report_relative_path'],row['report_role'],row['producer_source'],row['public_ABI_binding'])==route and
                 same(row['producer_by_condition'],producers),'fixed operation and actual arm-specific scientific producer')
            relative(row['report_relative_path'])
            if producers is None:validate_type('Pin',row['producer_source'])
            else:
                validate_type('ArmMap',row['producer_by_condition'])
                need(row['report_cap_bytes']==abi_jobs[job['id']]['report_cap_bytes'],'same complete report bound for both arms')
        rows[job['id']]=row
    return OutputContract(_COMPILED,body=body,pin=contract_pin,policy=policy,policy_pin=policy_pin,abi=abi,abi_pin=abi_pin,
                          abi_jobs=abi_jobs,policy_jobs=policy_jobs,rows=rows,paired=paired)

def load_contract(root,selection,census,*,meter):
    b=selection.body;budget=selection.budget;cap=b['evidence_cap_bytes']
    contract_pin=b['job_output_contract'];body=parse(read_pin(root,contract_pin,cap,budget))
    policy_pin=body['participant_policy'];policy=parse(read_pin(root,policy_pin,cap,budget))
    validate_type('PairedPolicy',policy)
    abi_pin=policy['report_ABI'];abi=parse(read_pin(root,abi_pin,cap,budget));validate_type('PublicABI',abi)
    paired=parse(read_pin(root,policy['paired_view_manifest'],cap,budget))
    execution=parse(read_pin(root,policy['execution_binding'],cap,budget));validate_type('ExecutionBinding',execution)
    public_interface=parse(read_pin(root,abi['task_interface'],cap,budget))
    seals={condition:parse(read_pin(root,policy['programme_seals'][condition],cap,budget))for condition in CONDITIONS}
    contract=compile_contract(body,contract_pin,census=census,census_pin=b['census_pin'],campaign_id=b['campaign_id'],
                             scope_digest=b['scope_digest'],policy=policy,policy_pin=policy_pin,abi=abi,abi_pin=abi_pin,
                             paired=paired,meter=meter,execution_binding=execution,public_interface=public_interface,seals=seals)
    # Full V3 child ancestry is required before original producer reads or any
    # executable contract return; parsed complete-looking seals are not enough.
    read_known_v3_links(root,seals,policy_pin=policy['same_agent_policy'],
                        interface=public_interface,cap=cap,budget=budget,meter=meter)
    from .programme_output_v2 import read_output_v2
    read_output_v2(root,seals=seals,policy=policy,execution=execution,census=census,census_pin=b['census_pin'],
                   public_interface=public_interface,cap=cap,budget=budget,meter=meter)
    # Authenticate every actual scientific report producer. The common wrapper
    # is not relabelled as the participant's arm-specific report programme.
    unique={}
    for row in body['ordered_jobs']:
        if row['availability']!='available':continue
        producers=[row['producer_source']]if row['producer_by_condition']is None else list(row['producer_by_condition'].values())
        for producer in producers:unique[encode(producer)]=producer
    for producer in unique.values():read_pin(root,producer,cap,budget)
    return contract.require_executable()

class PublicViews:
    __slots__=('contract','materialization','_token')
    def __init__(self,token,contract,materialization):
        need(token is _VIEWS,'actual pre-commit public ABI materialization')
        self.contract=contract;self.materialization=materialization;self._token=token

def materialize_candidate_views(root,contract,parent,*,nonce,budget):
    need(type(contract) is OutputContract,'actual entire compiled contract');contract.require_executable()
    result=materialize(root,contract.paired,parent,nonce=nonce,budget=budget)
    return PublicViews(_VIEWS,contract,result)

def verify_visible_abi(root,contract,selected_views,job_ids,budget):
    """The actual selected read-only input view must contain the earlier ABI."""
    need(type(contract) is OutputContract and set(selected_views)==set(job_ids),
         'same whole selected candidate view domain')
    member=next(m for m in contract.paired['common'] if m['source']==contract.abi_pin)
    for job_id in job_ids:
        path=Path(selected_views[job_id])/member['destination']
        body=read_pin(root,{**contract.abi_pin,'path':str(path)},contract.abi_pin['bytes'],budget)
        need(body==encode(contract.abi),'exact public ABI in actual source-selected input view')
    return True

def validate_candidate_report(payload,contract,job_id,condition,*,meter):
    need(type(contract) is OutputContract and condition in CONDITIONS,'same original report contract and arm')
    meter.charge('work_units',bounded_size(payload))
    closed(payload,('job_id','condition','scope_digest','bundles','identities'))
    need(payload['job_id']==job_id and payload['condition']==condition and
         payload['scope_digest']==contract.body['scope_digest'],'original report identity')
    abi=contract.abi_jobs[job_id]
    need(type(payload['bundles']) is list and len(payload['bundles'])==len(abi['bundles']),'complete ordered public bundle ABI')
    for b,expected in zip(payload['bundles'],abi['bundles']):
        closed(b,('pin','schema','cap_bytes'));descriptor(b['pin'],expected['cap_bytes'])
        need(b['schema']==expected['schema'] and b['cap_bytes']==expected['cap_bytes'],'original public bundle schema/cap')
    check(payload['identities'],abi['identity_schema'])
    return payload

def capture_job_report(observation,contract,job,*,run_root,store,process_cap,condition):
    """Actual H return -> fixed job-root ordinary report; failed rows stay null.

    The caller retains full outcomes including unattempted jobs. This function
    is only the completed-job branch, never a reason to create missing files.
    """
    need(type(observation) is OriginalProcessObservation and observation.success,'actual original whole W closure')
    need(type(contract) is OutputContract and type(store) is Store,'fixed source contract and earlier H terminal Store')
    contract.require_executable();row=contract.rows[job['id']]
    relative(job['id']);need(len(Path(job['id']).parts)==1,'literal original job directory')
    relative(run_root);job_root=run_root+'/'+job['id']
    prefix={'job_id':job['id'],'original_process_record':None,'candidate_report':None}
    try:
        raw,process=store.capture_created(job_root+'/PROCESS.json',process_cap,metadata=True)
        prefix['original_process_record']={**process,'path':str(store.root/process['path'])}
        raw,report=store.capture_created(job_root+'/'+row['report_relative_path'],row['report_cap_bytes'],metadata=True)
        prefix['candidate_report']={**report,'path':str(store.root/report['path'])}
        if job['operation']=='candidate':validate_candidate_report(parse(raw),contract,job['id'],condition,meter=store.meter)
        return {k:prefix[k] for k in ('original_process_record','candidate_report')}
    except BaseException as error:
        # Preserve the actual first captured file when a later capture/parse
        # fails. This is failure evidence, never original_process_closed.
        store.meter.own_error(error,'original_job_report_capture')
        try:BaseException.__setattr__(error,'four_job_capture_prefix',prefix)
        except BaseException as secondary:store.meter.cleanup_errors.append(failure(secondary))
        raise
