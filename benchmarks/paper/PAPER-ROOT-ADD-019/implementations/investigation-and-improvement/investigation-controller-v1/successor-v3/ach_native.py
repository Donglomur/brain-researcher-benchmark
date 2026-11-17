"""Reuse actual nativeV3 collection and decode its admitted captured quantities."""
import math
import struct
from ach_util import need,integer,require_pin,pin_bytes,decode,exact_fields,pin,finish_owned

FORMATS={'double':'d','single':'f','int8':'b','uint8':'B','int16':'h','uint16':'H',
         'int32':'i','uint32':'I','int64':'q','uint64':'Q','logical':'B','char':'H'}

def read_closed(provider,context,descriptor,ledger,cap):
    require_pin({k:descriptor[k] for k in ('bytes','sha256')});need(descriptor['bytes']<=cap,'complete declared captured extent')
    ledger.reserve({'read_bytes':descriptor['bytes']+1},'native/project/read')
    ledger.tick();raw=provider.read_closed_output(context,descriptor['path'],0,descriptor['bytes']);ledger.tick()
    need(pin_bytes(raw)=={k:descriptor[k] for k in ('bytes','sha256')},'same immutable captured body')
    need(provider.read_closed_output(context,descriptor['path'],descriptor['bytes'],1)==b'','no capture growth')
    return raw

def leaf_values(leaf,raw,limits,ledger):
    need(leaf['class'] in FORMATS and leaf['byte_order']=='little' and leaf['layout']=='MATLAB_column_major',
         'literal admitted MATLAB leaf encoding')
    shape=leaf['shape'];need(type(shape) is list and 2<=len(shape)<=32,'original full MATLAB dimensions')
    for n in shape:integer(n)
    count=math.prod(shape);need(count<=limits['max_scalars'],'complete scalar extent before decode')
    containers=sum(math.prod(shape[:i]) for i in range(len(shape)))
    need(containers<=limits['max_containers'],'complete container extent including zero-sized axes')
    fmt='<'+FORMATS[leaf['class']];width=struct.calcsize(fmt)
    need(count*width==len(raw)==leaf['bytes'],'exact source class/shape extent')
    ledger.reserve({'native_projection_scalars':count,'native_projection_containers':containers},'native/project/scalars')
    values=[x[0] for x in struct.iter_unpack(fmt,raw)]
    if leaf['class']=='logical':need(all(x in (0,1) for x in values),'literal logical values');values=[bool(x) for x in values]
    strides=[];stride=1
    for n in shape:strides.append(stride);stride*=n
    def build(axis,offset):
        if axis==len(shape):return values[offset]
        return [build(axis+1,offset+i*strides[axis]) for i in range(shape[axis])]
    return build(0,0)

def native_source_identities(libraries,bundle):
    """Prospective non-circular role/root identities from actual source inputs.

    These are metadata identities of executable source, not quantity rules or
    numeric outcomes. NativeV3 separately authenticates the same source bodies
    and all four actual programme bytes before execution.
    """
    contract=libraries.native_contract()
    runtime={name:pin_bytes(body) for name,body in libraries.source_bodies.items() if name.startswith('captured-native/')}
    root_identity={'schema':'ach_native_source_closure_v1','contract_pin':pin(contract),'capture_runtime_pin':pin(runtime)}
    root_pin=pin(root_identity);producer={}
    need(set(bundle['programs'])==set(bundle['authoring_contexts'])==set(contract['candidate_program_keys']),
         'same original four committed programmes and authoring contexts')
    for root in contract['roots']:
        original={k:root['source'][k] for k in ('path','bytes','sha256')}
        for role in contract['roles']:
            programme_key={'A_clarified':'A/native','B_author_code':'B/native','operator_reference':None}[role]
            identity={'schema':'ach_native_role_root_source_v1','role':role,'root_id':root['id'],
                'root_source_pin':root_pin,'original_root_source':original,'capture_mode':root['default_mode'],
                'programme_descriptor':None if programme_key is None else bundle['programs'][programme_key],
                'independent_authoring_context':None if programme_key is None else bundle['authoring_contexts'][programme_key]}
            producer[role+'/'+root['id']]=pin(identity)
    return {'root_source_pin':root_pin,'producer_source_pins':producer,'root_identity':root_identity}

def bind_native_policy_sources(libraries,bundle,quantity_policy):
    identities=native_source_identities(libraries,bundle)
    libraries.get('core','native_compare').validate_policy(quantity_policy,[r['id'] for r in libraries.native_contract()['roots']])
    need(quantity_policy['root_source_pin']==identities['root_source_pin'] and
         quantity_policy['producer_source_pins']==identities['producer_source_pins'],
         'native quantity policy binds actual programme/root/capture source identity before execution')
    return identities

def project_collection(libraries,bundle,collection,provider,projection,quantity_policy,ledger,limits):
    """All111 exact captured outputs, with independently frozen selectors/rules.

    Selection and units/support/tolerances are admitted before native execution;
    no rule is fitted to candidate output. No scientific-result callback exists.
    """
    identities=bind_native_policy_sources(libraries,bundle,quantity_policy)
    expected_sources={k:{field:d[field] for field in ('bytes','sha256')} for k,d in bundle['programs'].items()}
    need(collection['commitment']['captured_sources']==expected_sources,
         'actual native collection captured the same four committed source bodies')
    contract=libraries.native_contract();jobs=libraries.get('native','dispatch').plans(contract)
    need(collection['schema']=='ach_all37_native_collection_v1' and
         collection['status']=='complete_collection_provisional' and
         [r['job_id'] for r in collection['records']]==[j['id'] for j in jobs], 'actual full nativeV3 return path')
    exact_fields(projection,('schema','quantity_policy_pin','roots','selection_evidence_pin'),'independent native quantity projection')
    need(projection['schema']=='ach_native_quantity_projection_v1' and projection['quantity_policy_pin']==pin(quantity_policy),
         'same independently frozen quantity rules')
    require_pin(projection['selection_evidence_pin']);roots=[r['id'] for r in contract['roots']]
    need(set(projection['roots'])==set(roots),'all original37 projection schemas')
    libraries.get('core','native_compare').validate_policy(quantity_policy,roots)
    scalars=sum(math.prod(rule['shape']) for quantities in quantity_policy['roots'].values() for rule in quantities.values())*3
    containers=sum(sum(math.prod(rule['shape'][:i]) for i in range(len(rule['shape'])))
        for quantities in quantity_policy['roots'].values() for rule in quantities.values())*3
    need(limits['full_panel_live_bytes']>=64*(scalars+containers),
         'declared full retained panel ceiling covers all scalar/container logical slots')
    panel_live=ledger.acquire_live(limits['full_panel_live_bytes'],'native/project/all111-retained-panel')
    try:
        panels={}
        for ordinal,(job,record) in enumerate(zip(jobs,collection['records'])):
            root=job['root']['id'];context=f'ach-{ordinal:03d}-{root}'
            admitted={d['path']:d for d in record['output']['files']}
            index_descriptor=record['output']['index'];index=decode(read_closed(provider,context,index_descriptor,ledger,
                limits['max_metadata_bytes']),limits['max_metadata_bytes'])
            snapshots=[]
            for d in index['snapshots']:
                need(admitted.get(d['path'])==d,'same independently admitted snapshot')
                snapshots.append(decode(read_closed(provider,context,d,ledger,limits['max_metadata_bytes']),limits['max_metadata_bytes']))
            tree={'snapshots':snapshots};quantities={}
            need(set(projection['roots'][root])==set(quantity_policy['roots'][root]),'every original selected quantity')
            for name,selector in projection['roots'][root].items():
                exact_fields(selector,('path','representation'),'literal independently selected capture path')
                need(type(selector['path']) is list and len(selector['path'])<=64,'bounded literal selector depth')
                value=tree
                for step in selector['path']:
                    need(type(step) in (int,str),'literal capture path component');value=value[step]
                rule=quantity_policy['roots'][root][name]
                if selector['representation']=='raw_leaf':
                    leaf=value['leaf'] if type(value) is dict and value.get('storage')=='little_endian_column_major' else value
                    d={k:leaf[k] for k in ('path','bytes','sha256')}
                    need(admitted.get(d['path'])==d and leaf['shape']==rule['shape'],'full admitted original leaf and quantity axes')
                    # Reserve declared full decoding working memory before material
                    # allocation; physical RSS remains an independent qualification.
                    live=ledger.acquire_live(limits['projection_working_bytes'],'native/project/full-leaf')
                    primary=None
                    try:values=leaf_values(leaf,read_closed(provider,context,d,ledger,limits['max_leaf_bytes']),limits,ledger)
                    except BaseException as error:primary=error;raise
                    finally:finish_owned([('native leaf reservation release',lambda:ledger.release_live(live))],primary)
                elif selector['representation']=='exact_metadata':
                    need(rule['kind']=='exact','metadata quantity requires literal exact comparison')
                    values=value
                else:need(False,'no inferred complex/aggregate quantity conversion')
                quantities[name]={'units':rule['units'],'support_pin':rule['support_pin'],'values':values,'status':'complete'}
            key=job['id']
            panels[key]={'source_pin':identities['producer_source_pins'][key],'quantities':quantities}
        need(set(panels)=={j['id'] for j in jobs},'complete all111 native quantity panel')
        return {'panels':panels,'comparison':libraries.get('core','native_compare').compare(quantity_policy,roots,panels),
                'projection_pin':pin(projection),'retained_live_token':panel_live,
                'actual_native_environment_qualification_is_external':True}
    except BaseException as error:
        finish_owned([('failed full native panel reservation release',lambda:ledger.release_live(panel_live))],error)
        raise

def run_native(libraries,qualification,bundle,admission,source_store,provider,observer,authority,profile,ledger):
    """Actual captured V3 dispatcher, with source-owned bounded operand methods.

    `authority` is the concrete independently authenticated deployment object;
    providers/observers implement transport/observation, never scientific values.
    """
    ledger.tick()
    result=libraries.get('native','dispatch').run(libraries.native_contract(),qualification,
        lambda:bundle,lambda:admission,source_store.read_original,lambda p,s:provider,lambda p,s:observer,
        authority.verify_native,profile,origin_ns=ledger.origin,clock=ledger.clock)
    ledger.tick()
    return result
