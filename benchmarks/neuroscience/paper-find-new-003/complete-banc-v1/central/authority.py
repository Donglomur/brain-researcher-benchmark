"""Independent configured deployment and exact operation evidence admission.

The registry pins this package's deployment file. It ships unconfigured and
cannot admit any method/key/data/reference body through an execution route.
Keys and real qualification evidence are separately provisioned by the operator.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,hmac,time,os
from banc_runtime.codec import need,parse,encode,pin,descriptor
from .io import metadata,exact_fields,digest,integer,absolute_directory,read_json
from .source import ROOT,PROFILE,STAGES
from .method import validate_method,method_identity

DEPLOYMENT_FIELDS=('schema','status','source_profile','input_root','output_root','keyring','issuers',
 'minimum_other_reserve_bytes','runtime_evidence','sandbox','limits')
LIMIT_FIELDS=('read_bytes','output_bytes','row_count','pair_work','jobs','wall_seconds','cpu_seconds','address_space_bytes','file_bytes')

@dataclass(frozen=True)
class Authorization:
    operation:str
    method_identity:str
    source_identity:str
    deployment_identity:str
    evidence_identity:str
    attempt:str
    condition:str

def verify_envelope(value,keys,issuer,kind):
    exact_fields(value,('payload','signature'),'signed evidence')
    p=value['payload'];exact_fields(p,('schema','issuer','kind','issued_at','expires_at','content'),'evidence payload')
    need(p['schema']=='banc_operator_evidence_v1' and p['issuer']==issuer and p['kind']==kind,'independent evidence issuer/kind')
    need(type(p['issued_at']) is int and type(p['expires_at']) is int and p['issued_at']<=int(time.time())<=p['expires_at'],'current independently selected evidence')
    digest(value['signature'])
    need(hmac.compare_digest(hmac.new(keys[issuer],encode(p),hashlib.sha256).hexdigest(),value['signature']),'evidence signature')
    return p['content']

def admit(source,action,method_path,output,review_path,deployment_path,deployment_sha,other_reserve_bytes,meter,clock):
    need(action in STAGES+('run',),'exact complete stage route')
    need(Path(deployment_path).absolute()==ROOT/'DEPLOYMENT.json','only registry-selected portable deployment path')
    raw=metadata(deployment_path,meter,65536);need(pin(raw)['sha256']==digest(deployment_sha),'exact deployment pin')
    need(source['captured']['DEPLOYMENT.json']==raw and any(row['path']=='DEPLOYMENT.json' and
      {k:row[k] for k in ('bytes','sha256')}==pin(raw) for row in source['manifest']['files']), 'complete actual deployment policy belongs to authenticated full source')
    deployment=parse(raw);exact_fields(deployment,DEPLOYMENT_FIELDS,'deployment')
    need(deployment['schema']=='banc_deployment_v2' and deployment['source_profile']==PROFILE,'complete deployment profile')
    need(deployment['status']=='independently_configured','deployment unconfigured: no method, key, data, model or reference body admitted')
    roots={k:absolute_directory(deployment[k]) for k in ('input_root','output_root')}
    need(roots['input_root'].identity!=roots['output_root'].identity and roots['input_root']!=roots['output_root'] and not roots['input_root'].is_relative_to(roots['output_root']) and not roots['output_root'].is_relative_to(roots['input_root']),'separate trusted input/output roots')
    st=roots['output_root'].stat();need(st.st_uid==os.geteuid() and not st.st_mode&0o077,'owned private output root')
    integer(other_reserve_bytes,'extra reserve');integer(deployment['minimum_other_reserve_bytes'],'deployment reserve')
    need(other_reserve_bytes>=deployment['minimum_other_reserve_bytes'],'explicit extra reserve below deployment policy')
    exact_fields(deployment['limits'],LIMIT_FIELDS,'whole-attempt limits')
    for key,value in deployment['limits'].items():integer(value,key,1)
    clock.bind(deployment['limits']['wall_seconds'])
    from dataclasses import replace
    meter.attempt_clock=clock;meter.limits=replace(meter.limits,deadline_ns=clock.record['deadline_monotonic_ns'])
    exact_fields(deployment['issuers'],('authorization','runtime','reference'),'independent issuer roles')
    issuers=deployment['issuers'];need(len(set(issuers.values()))==3,'authorization/runtime/reference issuers must be distinct')
    keyref=descriptor(deployment['keyring']);need(keyref['bytes']<=65536,'bounded configured operator keyring')
    encoded=read_json(roots['input_root'],keyref,meter,65536)
    need(type(encoded) is dict and set(encoded)==set(issuers.values()),'exact separately provisioned issuer key set')
    keys={}
    for name,value in encoded.items():
        need(type(value) is str and len(value)==64 and all(x in '0123456789abcdef' for x in value),'operator key encoding')
        keys[name]=bytes.fromhex(value)
    need(len(set(keys.values()))==3,'independent issuer keys')
    mraw=metadata(method_path,meter,1048576);method=parse(mraw);program=validate_method(method,source)
    review=verify_envelope(parse(metadata(review_path,meter,65536)),keys,issuers['authorization'],'operation')
    exact_fields(review,('operation','profile','method_sha256','source_sha256','deployment_sha256','attempt','condition','output','other_reserve_bytes','previous_journal_sha256','attempt_directory_identity','runtime_evidence_sha256','previous_terminal_evidence'),'operation review')
    need(review['operation']==action and review['profile']==PROFILE and review['method_sha256']==pin(mraw)['sha256'] and
      review['source_sha256']==source['manifest_identity']['sha256'] and review['deployment_sha256']==deployment_sha and
      review['condition']==method['condition'] and review['other_reserve_bytes']==other_reserve_bytes,'exact independently selected operation/method/source/condition/reserve')
    attempt=review['attempt'];need(type(attempt) is str and 1<=len(attempt)<=100 and all(c.isascii() and (c.isalnum() or c in '._-') for c in attempt),'ordinary fixed attempt name')
    expected=roots['output_root']/attempt
    need(Path(output).absolute()==expected and review['output']==str(expected),'exact selected attempt output')
    from banc_runtime.codec import relative
    # Late authenticated attachment: the source-bound policy selects its path.
    # Complete proof bytes are authenticated by an independent issuer, then
    # retained by content hash. No source/proof hash cycle is constructed.
    runtime_path=relative(deployment['runtime_evidence'])
    runtime_raw=metadata(roots['input_root']/runtime_path,meter,1048576)
    rref={'path':runtime_path,**pin(runtime_raw)}
    need(rref['sha256']==digest(review['runtime_evidence_sha256']),'independently selected exact late runtime proof hash')
    runtime=verify_envelope(parse(runtime_raw),keys,issuers['runtime'],'runtime')
    exact_fields(runtime,('source_sha256','method_sha256','deployment_sha256','sandbox_sha256','complete_input_bindings','qualification_receipts','output_custody'),'runtime evidence')
    need(runtime['source_sha256']==source['manifest_identity']['sha256'] and runtime['method_sha256']==pin(mraw)['sha256'] and runtime['deployment_sha256']==deployment_sha and
      runtime['sandbox_sha256']==pin(encode(deployment['sandbox']))['sha256'] and runtime['complete_input_bindings']==method['data'],'independent exact runtime/input/physical enclosure evidence')
    required={'ordinary_source_closure','native_import_ABI','full_input_view_provenance','source_output_panel_mapping','physical_resource_enclosure','actor_information_boundary','private_reference_mount'}
    need(type(runtime['qualification_receipts']) is dict and set(runtime['qualification_receipts'])==required,'complete independently qualified runtime evidence roles')
    for value in runtime['qualification_receipts'].values():digest(value)
    custody=runtime['output_custody']
    exact_fields(custody,('policy','output_root_identity','parent_identity','exclusive_parent_lifetime_qualified','acquisition_evidence_sha256'),'independent positive custody evidence')
    need(custody['policy']=='banc_directory_capability_exclusive_parent_v2' and custody['output_root_identity']==roots['output_root'].identity and custody['parent_identity']==roots['output_root'].parent.identity and
      custody['exclusive_parent_lifetime_qualified'] is True,'independently qualified positive output acquisition and parent lifetime required')
    digest(custody['acquisition_evidence_sha256'])
    terminal=None
    if action in ('prepare','run'):
        need(review['attempt_directory_identity'] is None and review['previous_terminal_evidence'] is None,'new attempt has no existing output or terminal predecessor')
    else:
        from .custody import acquire
        acquire(expected,review['attempt_directory_identity'])
        terminal_ref=descriptor(review['previous_terminal_evidence'])
        terminal=verify_envelope(read_json(roots['input_root'],terminal_ref,meter,1048576),keys,issuers['runtime'],'terminal_closure')
        exact_fields(terminal,('source_sha256','method_sha256','deployment_sha256','attempt_directory_identity','previous_journal_sha256','attempt_clock',
          'exit_code','directory_and_log_closure_qualified','outer_publication_complete','terminal_monotonic_ns','terminal_wall_ns','observer_evidence_sha256'),'independent outer terminal evidence')
        need(terminal['source_sha256']==source['manifest_identity']['sha256'] and terminal['method_sha256']==pin(mraw)['sha256'] and
          terminal['deployment_sha256']==deployment_sha and terminal['attempt_directory_identity']==review['attempt_directory_identity'] and
          terminal['previous_journal_sha256']==review['previous_journal_sha256'],'exact independently selected terminal predecessor')
        need(type(terminal['exit_code']) is int and terminal['exit_code']==0 and terminal['directory_and_log_closure_qualified'] is True and
          terminal['outer_publication_complete'] is True,'provisional journal requires independently observed complete outer closure')
        digest(terminal['observer_evidence_sha256']);clock.adopt(terminal['attempt_clock'])
        meter.limits=replace(meter.limits,deadline_ns=clock.record['deadline_monotonic_ns'])
        for name,origin_key,deadline_key in (('terminal_monotonic_ns','origin_monotonic_ns','deadline_monotonic_ns'),('terminal_wall_ns','origin_wall_ns','deadline_wall_ns')):
            need(type(terminal[name]) is int and clock.record[origin_key]<=terminal[name]<=clock.record[deadline_key], 'outer terminal completion must be inside the original interval')
    authority=Authorization(action,method_identity(method),source['manifest_identity']['sha256'],deployment_sha,rref['sha256'],attempt,method['condition'])
    return {'source':source,'method':method,'program':program,'deployment':deployment,'roots':roots,'keys':keys,'runtime':runtime,'authority':authority,'output':expected,
      'previous_journal_sha256':review['previous_journal_sha256'],'clock':clock,'attempt_directory_identity':review['attempt_directory_identity'],'previous_terminal_confirmation':terminal}
