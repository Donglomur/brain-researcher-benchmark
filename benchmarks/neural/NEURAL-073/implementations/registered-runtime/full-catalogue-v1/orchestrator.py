"""One selected full invocation using the unchanged scientific execution graph.

Importing this module does not read an operator key, canonical array or runtime.
The initially shipped deployment refuses before all such operations. Future
execution requires independent source, input, native, provider and capacity
qualification; this source is not evidence that those conditions have passed.
"""
from pathlib import Path
from dataclasses import asdict
import hashlib
import hmac
import os
import re
import stat
import time

from .declaration import (DeclarationError, ReadLedger, read_json_pinned,
                          read_bytes_pinned, canonical_file_bytes)
from .constructors import construct_typed, construct_trusted
from .runtime.core.custody import CustodyError, canonical, digest, require_digest
from .runtime.core.plan import CONDITIONS, PEOPLE


class InvocationError(CustodyError):
    pass


def _need(ok, text):
    if not ok:
        raise InvocationError(text)


def _closed(value, keys, text):
    _need(type(value) is dict and set(value) == set(keys), 'closed ' + text)
    return value


def _positive(value, name):
    _need(type(value) is int and value > 0, 'positive finite ' + name)
    return value


def _pin(raw):
    return {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}


# Constructor names never come from a deployment document. These are the exact
# operative nested fields of fixed internal host/tool construction call sites.
_NESTED = {
    ('MountAPIContract','source_api_closure'):'EvidencePin',
    ('MountAPIContract','native_command_controls'):'EvidencePin',
    ('SealAdmission','namespace_qualification'):'EvidencePin',
    ('SealAdmission','mount_api'):'MountAPIContract',
    ('SealAdmission','limits'):'IOLimits',
    ('InferencePolicy','settings'):'InferenceSettings',
    ('InferencePolicy','schedule'):'RepetitionSchedule',
    ('AdapterAdmission','inference_policy'):'InferencePolicy',
    ('HostPreparation','capsule_limits'):'IOLimits',
    ('HostPreparation','capsule_seal_admission'):'SealAdmission',
    ('HostPreparation','guard_admission'):'GuardAdmission',
    ('HostPreparation','monitor_runtime'):'MonitorRuntime',
    ('HostPreparation','provider_admission'):'AdapterAdmission',
    ('HostPreparation','snapshot_limits'):'IOLimits',
    ('HostPreparation','snapshot_seal_admission'):'SealAdmission',
    ('ToolPreparation','limits'):'IOLimits',
    ('ToolPreparation','seal_admission'):'SealAdmission',
    ('ToolPreparation','model_limits'):'PublicModelLimits',
}
_SEQUENCE = {('InferenceSettings','parameters'):'InferenceParameter',
    ('GuardAdmission','runtime_members'):'MemberPin',
    ('AdapterAdmission','source_closure'):'SourcePin'}


def hydrate_fixed(ident, row):
    """Internal fixed constructor recursion; unknown fields still fail closed."""
    _need(type(row) is dict, 'explicit typed metadata')
    values = dict(row)
    for field in row:
        key = (ident,field)
        if key in _NESTED:
            values[field] = hydrate_fixed(_NESTED[key],row[field])
        elif key in _SEQUENCE:
            _need(type(row[field]) is list and len(row[field]) <= 100000,
                  'bounded exact nested sequence')
            values[field] = tuple(hydrate_fixed(_SEQUENCE[key],x) for x in row[field])
    return construct_typed(ident,values)


def _metadata(operator, pin):
    cap = operator.sections['capacity']['metadata_limits']['file_bytes']
    path=Path(pin['path'])
    if not path.is_absolute():path=operator.package['root']/path
    return read_json_pinned(path,pin,limit=cap,ledger=operator.ledger)[0]


def hydrate_hosts(operator, plan):
    """All 234 private contexts and 39 full tool sets; no sparse/default hosts."""
    section = operator.sections['host']
    _closed(section,('schema','host_specs_pin','tool_specs_pin'),'host section')
    _need(section['schema']=='n073_host_section_v1','host schema')
    hosts = _metadata(operator,section['host_specs_pin'])
    tools = _metadata(operator,section['tool_specs_pin'])
    _closed(hosts,('schema','hosts'),'expanded hosts')
    _closed(tools,('schema','tools'),'expanded tools')
    _need(hosts['schema']=='n073_expanded_host_specs_v1' and
          tools['schema']=='n073_expanded_tool_specs_v1','expanded metadata schema')
    expected = {c.context_id:c for c in plan.contexts()}
    _need(type(hosts['hosts']) is dict and set(hosts['hosts'])==set(expected) and
          len(expected)==234,'complete 234 hosts')
    host_specs = {cid:hydrate_fixed('HostPreparation',row)
                  for cid,row in hosts['hosts'].items()}
    profile = operator.sections['provider']['common_profile']
    for cid,host in host_specs.items():
        _need(host.context_id==cid,'host context identity')
        operator.policy.require_adapter(host.provider_admission,expected[cid])
        _need({k:getattr(host.provider_admission,k) for k in profile}==profile,
              'one declared fixed provider across all contexts')
    source_specs = (
        ('reference_cli.py','runtime/runner/reference_cli.py',0o555),
        ('public_transform.py','runtime/runner/public_transform.py',0o444),
        ('public_model.py','runtime/public_models/model.py',0o444))
    sources=[]
    for name,path,mode in source_specs:
        pin=operator.package['B']['files'][path]
        raw=read_bytes_pinned(operator.package['root']/path,
            {'bytes':pin['bytes'],'sha256':pin['sha256']},
            limit=pin['bytes'],ledger=operator.ledger)
        sources.append(construct_typed('PublicSource',{
            'name':name,'body':raw,'sha256':pin['sha256'],'mode':mode}))
    _need(type(tools['tools']) is list and len(tools['tools'])==39,'all 39 tool specifications')
    tool_specs={}
    for row in tools['tools']:
        _closed(row,('person','condition','preparation'),'tool row')
        key=(row['person'],row['condition'])
        _need(key not in tool_specs,'duplicate tool row')
        preparation=dict(row['preparation'])
        _need(preparation.get('public_sources')==[x[0] for x in source_specs],
              'fixed ordered public source identifiers only')
        preparation['public_sources']=tuple(sources)
        tool_specs[key]=hydrate_fixed('ToolPreparation',preparation)
    _need(set(tool_specs)=={(p,c) for p in plan.people for c in CONDITIONS},'complete tool graph')
    return host_specs,tool_specs


def public_roots(hosts,tools):
    """Complete explicit public/candidate roots for the private-store boundary."""
    roots=set()
    for host in hosts.values():
        roots.update((host.capsule_parent,host.snapshot_parent,
                      host.guard_admission.scratch_mount,host.guard_admission.runtime_root))
        # Every declared mount source, including runtime source trees, is checked
        # by its own admission. These declared parents cover future exports.
    roots.update(t.parent for t in tools.values())
    return tuple(sorted(roots))



def assert_private_sources_isolated(operator, roots):
    """No selected private source namespace may become a public native mount."""
    anchor=operator.sections['trust_anchor']
    private=[str(operator.package['root']), operator.sections['corpus']['canonical_root'],
        operator.sections['private_output']['output_parent'],
        anchor['evidence_root'],anchor['intent_root'],operator.intent['output_path'],
        derive_run_root(operator.intent,operator.sections['private_output'])]
    private.extend(row['path'] for row in anchor['keys'].values())
    host=operator.sections['host']
    selected_pins=[*operator.package['D']['section_manifests'].values(),
        operator.sections['corpus']['inventory_pin'],host['host_specs_pin'],
        host['tool_specs_pin'],operator.intent['policy_pin']]
    for pin in selected_pins:
        path=Path(pin['path'])
        private.append(str(path if path.is_absolute() else operator.package['root']/path))
    for secret in private:
        _need(type(secret) is str and secret.startswith('/') and
              os.path.normpath(secret)==secret,'canonical selected private namespace')
        for public in roots:
            _need(type(public) is str and public.startswith('/') and
                  os.path.normpath(public)==public,'canonical selected public namespace')
            _need(not (secret==public or secret.startswith(public.rstrip('/')+'/') or
                       public.startswith(secret.rstrip('/')+'/')),
                  'private source/key/output namespace overlaps a candidate public root')
    return {'private_paths_checked':len(private),'public_roots_checked':len(roots),
            'check':'declared canonical namespace separation; actual native mounts remain independently gated'}

def derive_run_root(intent, private_output):
    output=Path(intent['output_path']); parent=Path(private_output['output_parent'])
    _need(output.is_absolute() and output.parent==parent and output.name not in ('','.', '..'),
          'signed submission must be an immediate child of selected private parent')
    invocation=intent['invocation_id']
    _need(type(invocation) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',invocation),
          'bounded invocation identity')
    root=parent/('run-'+invocation)
    _need(root!=output,'submission and private run root differ')
    return str(root)


def capacity_preflight(operator):
    """Read-only future-host storage check; never deletes or silently downscopes."""
    c=operator.sections['capacity']
    _closed(c,('schema','metadata_limits','canonical_limits','reference_capacity',
               'preparation_numeric_limits','storage','whole_wall_seconds'),'capacity section')
    _need(c['schema']=='n073_capacity_section_v1','capacity schema')
    storage=_closed(c['storage'],('root','minimum_free_bytes','owned_reservation_bytes',
                                  'other_reserve_minimum_bytes'),'storage')
    root=Path(storage['root'])
    _need(root.is_absolute() and str(root)==storage['root'] and '..' not in root.parts,
          'explicit canonical storage root')
    # Hold and verify the selected root without following any component symlink.
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in root.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        st=os.fstatvfs(fd)
        available=st.f_bavail*st.f_frsize
    finally:os.close(fd)
    for key in ('minimum_free_bytes','owned_reservation_bytes'):
        _positive(storage[key],key)
    _need(type(storage['other_reserve_minimum_bytes']) is int and storage['other_reserve_minimum_bytes']>=0,
          'nonnegative explicit other-work reserve minimum')
    reserve=operator.intent['other_reserve_bytes']
    _need(type(reserve) is int and reserve>=storage['other_reserve_minimum_bytes'],
          'other-project storage reservation')
    needed=storage['minimum_free_bytes']+storage['owned_reservation_bytes']+reserve
    _need(available>=needed,'complete selected storage does not fit; no partial scope')
    return {'available_bytes':available,'required_bytes':needed,
            'reservation_is_physical_allocation':False,'source_root':str(root)}


def _deadline(deadline):
    _need(time.monotonic()<=deadline,'whole invocation wall allowance exceeded')


def preserve_score_capability(study, final):
    """Reproduce the exact last stateless signature; never issue a new score run.

    FullStudy.evaluate is the last original capability caller. Do this immediately
    after its inherited execute returns, before any extraction close capability.
    """
    from .runtime import scoring
    records=study.data.score_records(tuple(r.case_id for r in study.plan.records))
    constructions={r.case_id:r.construction for r in study.plan.records}
    bindings={**study.issuer.global_bindings,
        'records_digest':scoring.records_digest(records),
        'closure_digest':final['closure_digest'],
        'construction_digest':digest(constructions)}
    _need(study.issuer.ordinal>0,'actual final score issuance required')
    envelope=study.issuer.verifier.issue(role='score',domain='authentic',
        context_id='full_locked_scoring',nonce=f'{study.issuer.ordinal:016x}',bindings=bindings)
    authority=study.issuer.verifier.verify(envelope,role='score',domain='authentic',bindings=bindings)
    panels=list(final['candidate_panels'].values())+list(final['reference_panels'].values())
    _need(len(panels)==66 and all(p['authority_digest']==authority.authority_digest for p in panels),
          'stored original score capability must match all original panels')
    return study.store.put_utf8('full_score_capability',envelope.decode('utf-8'))


def journal_pins(store):
    """Original writer receipts, not newly guessed files or directory discovery."""
    by_name={}
    for row in store.partial_operations:
        name=row['target']
        if re.fullmatch(r'j[0-9]{8}\.json',name):
            _need(name not in by_name and row.get('published') is True and row.get('durable') is True
                  and row['written_bytes']==row['intended_bytes'],'journal original publication incomplete')
            by_name[name]={'file':name,'bytes':row['intended_bytes'],'sha256':row['intended_sha256']}
    names=[f'j{i:08d}.json' for i in range(store.journal_index)]
    _need(set(by_name)==set(names),'original complete journal filenames')
    return [by_name[name] for name in names]


def read_close_originals(store, limits, *, ledger):
    """Read owned original journal bytes once, with bounded complete chain replay."""
    from .evidence import EvidenceMeter,_read,parse_json
    from .runtime.private_store.store import verify_journal_frames
    from .runtime.private_store import PrivateRunStore
    _need(type(store) is PrivateRunStore and store.started and not store.failed and not store.closed,
          'actual still-open original private writer required')
    store._check_root()
    meter=EvidenceMeter(limits);pins=journal_pins(store)
    _need(type(ledger) is ReadLedger,'whole invocation metadata ledger required')
    attempt=ledger.reserve('original_private_journal_before_usage_extraction',sum(x['bytes'] for x in pins))
    _need(len(pins)<=limits.max_journal_events,'journal operation count cap')
    originals={};model_index=[];tool_keys=set()
    class Frames:
        def __len__(self):return len(pins)
        def __iter__(self):
            for pin in pins:
                with meter.workspace(64*pin['bytes']+4096):
                    raw=_read(store.rootfd,pin,meter)
                    event=parse_json(raw,limits=limits,newline=True)
                    if event['kind']=='guard_original_close':
                        payload=event['payload'];r=payload.get('original_receipt',{})
                        cid=r.get('context_id')
                        _need(type(cid) is str and cid not in originals,'one original guard close per context')
                        meter.retain(64*pin['bytes']+4096)
                        originals[cid]=r
                    elif event['kind']=='public_tools_prepared':
                        # Complete tool model identity remains a commitment of the
                        # actual trusted original writer, not a model-body reread.
                        payload=event['payload'];key=(payload.get('outer_person'),payload.get('condition'))
                        _need(key[0] in PEOPLE and key[1] in CONDITIONS and key not in tool_keys,
                              'exact unique full-study public tool identity')
                        require_digest(payload['tool_files_digest']);tool_keys.add(key)
                        meter.retain(64*pin['bytes']+4096)
                        model_index.append({'outer_person':key[0],'condition':key[1],
                            'event_digest':event['event_digest'],'tool_files_digest':payload['tool_files_digest']})
                    yield raw
    try:
        verify_journal_frames(Frames(),run_id=store.a.run_id,domain=store.domain,
                              expected_head=store.head,expected_events=store.journal_index)
        attempt['status']='verified_original_journal'
        return originals,model_index,meter.receipt()
    except BaseException as exc:
        attempt['status']='failed';attempt['error_type']=type(exc).__name__;raise
    finally:
        attempt['read_bytes']=meter.read_bytes
        ledger.actual_bytes+=meter.read_bytes
        attempt['counter_semantics']='conservative logical read debits; may precharge a failed read'


def make_run_contract(operator,study,attempt_binding):
    from .runtime.admission.export import ContextSpec
    contexts={}
    for context in study.contexts:
        spec=ContextSpec(context.outer_person,context.arm,context.condition,
                         context.repetition,context.context_id)
        mapping={hmac.new(operator.keys['export'],canonical(['n073-opaque-v1','case',spec.fingerprint,rid]),
                          hashlib.sha256).hexdigest():rid for rid in study.plan.fold(context.outer_person).query_ids}
        actual=study.results[context.context_id]['submission']['private_mapping_digest']
        _need(digest(mapping)==actual,'independently derived exact private query identity')
        adapter=study.host_specs[context.context_id].provider_admission
        contexts[context.context_id]={'provider_admission_digest':adapter.binding_digest,
            'usage_evidence_digest':adapter.usage_evidence_digest,'private_mapping_digest':actual}
    return {'schema':'n073_run_contract_v2','domain':'authentic','attempt_binding':attempt_binding,
        'identities':{**operator.identities,'plan_digest':study.plan.binding_digest,
                      'assessment_digest':study.data.assessment.fingerprint},
        'reference_source_digest':operator.package['pins']['B']['sha256'],
        'usage_extraction_source_digest':operator.package['B']['files']['transport_evidence.py']['sha256'],
        'context_contracts':contexts,'rawledger_event_replay_available':False}


def _roles(store,study,usage_keys):
    candidates={c.context_id:'candidate_'+c.context_id for c in study.contexts}
    outer={'|'.join(k):'outer_'+digest(list(k)) for k in study.reference.results}
    oof=sorted(k for k in store.artifacts if k.startswith('oof_'))
    _need(len(candidates)==234 and len(outer)==455 and len(oof)==55068 and
          set(usage_keys)==set(candidates),'full output role cardinality')
    out={'run_contract':'run_contract','full_locked_closure':'full_locked_closure',
         'full_study_results':'full_study_results','full_score_capability':'full_score_capability',
         'candidate_contexts':candidates,'outer_references':outer,'reference_oof':oof,
         'provider_usage':dict(usage_keys)}
    keys=[out[k] for k in ('run_contract','full_locked_closure','full_study_results','full_score_capability')]
    keys+=list(candidates.values())+list(outer.values())+oof+list(usage_keys.values())
    _need(len(keys)==len(set(keys)) and set(keys)<=set(store.artifacts),'distinct committed original role bodies')
    return out


def _commitments(operator,corpus,model_index,usage_projection_index,native_receipt):
    objects={'source':{'source_freeze':operator.identities['source_freeze_digest']},
             'native':native_receipt,'model':model_index,
             'capture':usage_projection_index,'input':corpus.receipt()}
    return [{'kind':kind,'identity':digest(value),'descriptor_digest':digest(value),
             'body_read_by_observer':False} for kind,value in objects.items()]


class TerminalWriter:
    """Exclusive post-store-close metadata, counted separately from store writes."""
    def __init__(self,store,*,max_bytes,max_file_bytes):
        from .runtime.private_store import PrivateRunStore
        _need(type(store) is PrivateRunStore and store.closed and store.identity is not None,
              'actual closed writer required')
        self.store=store;self.limit=_positive(max_bytes,'terminal writer bytes')
        self.file_limit=_positive(max_file_bytes,'terminal single file');self.written=0;self.operations=[]
    def write(self,path,value):
        from .runtime.private_store.store import bounded_json
        raw=bounded_json(value,self.file_limit-1)+b'\n'
        return self.write_encoded(path,raw)
    def write_encoded(self,path,raw):
        _need(type(raw) is bytes and 0<len(raw)<=self.file_limit,
              'exact bounded terminal encoding required')
        path=Path(path)
        _need(path.is_absolute() and os.path.normpath(str(path))==str(path),
              'canonical absolute terminal path')
        _need(self.written+len(raw)<=self.limit,'terminal cumulative write cap')
        # Charge before opening, including partial/failed originals.
        self.written+=len(raw)
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);body_fd=None
        op={'path':str(path),'bytes':len(raw),'written_bytes':0,'durable':False}
        self.operations.append(op)
        try:
            for part in path.parts[1:-1]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                os.close(fd);fd=child
            st=os.fstat(fd)
            if str(path.parent)==self.store.a.root:
                _need((st.st_dev,st.st_ino)==self.store.identity and stat.S_IMODE(st.st_mode)==0o700
                      and st.st_uid==os.getuid(),'closed private root identity')
            else:
                _need(path.parent==Path(self.store.a.root).parent,'selected sibling submission only')
            body_fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
            bs=os.fstat(body_fd)
            _need(stat.S_ISREG(bs.st_mode) and bs.st_nlink==1 and bs.st_uid==os.getuid() and
                  stat.S_IMODE(bs.st_mode)==0o600,'owned exclusive terminal file')
            view=memoryview(raw)
            while op['written_bytes']<len(raw):
                n=os.write(body_fd,view[op['written_bytes']:op['written_bytes']+65536])
                _need(n>0,'terminal write made no progress');op['written_bytes']+=n
            os.fsync(body_fd);after=os.fstat(body_fd)
            _need(after.st_size==len(raw) and after.st_nlink==1 and
                  (after.st_dev,after.st_ino)==(bs.st_dev,bs.st_ino),'terminal extent identity')
            os.close(body_fd);body_fd=None;os.fsync(fd);op['durable']=True
            return {'path':str(path),**_pin(raw)}
        except BaseException as exc:
            op['error_type']=type(exc).__name__;op['error']=str(exc);raise
        finally:
            if body_fd is not None:os.close(body_fd)
            os.close(fd)


def _attempt_snapshot(operator, *, storage=None,native=None,bundle=None,store=None,writer=None):
    """Original metadata counters only; preserve failed snapshot fields explicitly."""
    result={'metadata_reads':{'reserved_bytes':operator.ledger.reserved_bytes,
        'actual_bytes':operator.ledger.actual_bytes,'capacity':operator.ledger.cap,
        'attempts':operator.ledger.attempts},'storage':storage,'native_runtime':native,
        'snapshot_capture_errors':[]}
    for key,value,method in (('corpus',bundle,'receipt'),('store',store,'status')):
        if value is not None:
            try:result[key]=getattr(value,method)()
            except BaseException as exc:
                result['snapshot_capture_errors'].append({'field':key,'exception_type':type(exc).__name__})
    if store is not None:
        result['store_partial_operations']=store.partial_operations
        result['store_incidents']=store.incidents
    if writer is not None:
        result['terminal_writes']={'reserved_bytes':writer.written,'operations':writer.operations}
    return result


def run_instance(task_root, deployment_path, expected_deployment_sha256, program_path,
                 output_path, review_path, *, other_reserve_bytes):
    """Execute once only after independently authenticating the concrete instance.

    This is a future operational entry point. BUILD ONLY authoring and engineering
    controls never invoke the configured branch or create an authentic selection.
    """
    from .authority import admit_operator,issue_terminal,claim_invocation
    from .attempts import InvocationFailed
    operator=admit_operator(task_root,deployment_path,expected_deployment_sha256,
        review_path,program_path,other_reserve_bytes=other_reserve_bytes,output_path=output_path)
    operator.require(action='run')
    attempt=claim_invocation(operator)  # Atomic durable claim BEFORE every preparation effect.
    store=None;bundle=None;engine=None;study=None;final=None;original=None;original_exc=None
    cleanup=[];closed=None;native_receipt=None;writer=None;terminal_written=False
    storage=None;evidence_limits=None;root=None;output=operator.sections['private_output']
    try:
        attempt.begin('capacity_preflight',_attempt_snapshot(operator))
        _need(str(output_path)==operator.intent['output_path'],'exact selected output path')
        root=derive_run_root(operator.intent,output)
        capacity=operator.sections['capacity']
        deadline=time.monotonic()+_positive(capacity['whole_wall_seconds'],'whole wall seconds')
        from .corpus import load_catalogue,load_corpus,generate_reference_data
        from .runtime.runner import runtime_api
        from .evidence import EvidenceLimits
        from .transport_evidence import (ExtractionLimits,StudyExtractionLimits,UsageExtractionBudget,
                                         extract_transport_usage)
        evidence_limits=EvidenceLimits(**output['evidence_limits'])
        storage=capacity_preflight(operator)
        attempt.begin('catalogue_metadata',_attempt_snapshot(operator,storage=storage))
        catalogue=load_catalogue(operator.package['root'],operator.package,ledger=operator.ledger)
        attempt.begin('native_activation',_attempt_snapshot(operator,storage=storage))
        numerical=operator.sections['numerical']
        _closed(numerical,('schema','contract','native_qualification_digest'),'numerical section')
        _need(numerical['schema']=='n073_numerical_section_v1','numerical schema')
        nb={'numerical_runtime_contract_digest':digest(numerical['contract']),
            'native_qualification_digest':numerical['native_qualification_digest'],
            'numerical_consumer_sources_digest':digest(runtime_api._CONSUMERS)}
        native_receipt=runtime_api.activate(numerical['contract'],
            authority=operator.issuer.capability('admission','native_numerical_runtime',nb),
            native_qualification_digest=numerical['native_qualification_digest'])
        _deadline(deadline)
        attempt.begin('canonical_corpus',_attempt_snapshot(operator,storage=storage,native=native_receipt))
        bundle=load_corpus(operator.package['root'],operator.package,
            operator.sections['corpus'],capacity,catalogue=catalogue,
            ledger=operator.ledger,operator=operator,deadline=deadline)
        numeric_limits=construct_typed('NumericLimits',capacity['preparation_numeric_limits'])
        attempt.begin('reference_data_preparation',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle))
        data=generate_reference_data(bundle,context_key=operator.keys['context'],
            permutation_key=operator.keys['permutation'],source_contract_digest=operator.identities['task_design_digest'],
            numeric_limits=numeric_limits)
        for name,actual in (('assessment_digest',data.assessment.fingerprint),
                            ('plan_digest',data.plan.binding_digest)):
            wanted=operator.selection_constraints.get(name)
            _need(wanted is None or wanted==actual,'optional selected actual '+name)
        _deadline(deadline)
        attempt.begin('host_preparation',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle))
        hosts,tools=hydrate_hosts(operator,data.plan)
        mount_roots=public_roots(hosts,tools)
        private_boundary=assert_private_sources_isolated(operator,mount_roots)
        attempt_binding=attempt.preparation_complete(_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle))
        attempt.begin('private_store_create',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle))
        template=_closed(output['store_template'],('single_artifact_bytes','total_write_bytes',
            'journal_record_bytes','store_contract_digest'),'store template')
        store_admission=construct_typed('StoreAdmission',{
            **template,'root':root,'run_id':operator.intent['invocation_id'],
            'public_mount_roots':mount_roots})
        sa=operator.issuer.capability('reference_fit','private_original_store',{
            'run_digest':digest(store_admission.run_id),
            'private_store_admission_digest':store_admission.binding_digest,
            'private_store_contract_digest':store_admission.store_contract_digest})
        store=construct_trusted('PrivateRunStore',{
            'admission':store_admission,'authority':sa,'role':'reference_fit','domain':'authentic'})
        store.create()
        store.append_event('integration_preparation_original',{
            'attempt_binding':attempt_binding,'storage':storage,'native_runtime':native_receipt,'private_boundary':private_boundary,
            'corpus':bundle.receipt(),'metadata_reads':operator.ledger.actual_bytes,
            'clock_semantics':'monotonic whole-bound checkpoints plus original per-component enforcement'})
        attempt.begin('reference_engine_construction',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle,store=store))
        reference_capacity=construct_typed('ReferenceCapacity',capacity['reference_capacity'])
        reference_source=operator.package['pins']['B']['sha256']
        transform_source=operator.package['B']['files']['runtime/transforms/numeric.py']['sha256']
        rb={'plan_digest':data.plan.binding_digest,'assessment_digest':data.assessment.fingerprint,
            'reference_capacity_digest':reference_capacity.binding_digest,'source_digest':reference_source,
            'transform_source_digest':transform_source,'numerical_contract_digest':native_receipt['contract_digest']}
        engine=construct_trusted('ReferenceEngine',{'data':data,'capacity':reference_capacity,
            'authority':operator.issuer.capability('reference_fit','full_reference_graph',rb),
            'source_digest':reference_source,'transform_source_digest':transform_source,
            'numerical_contract_digest':native_receipt['contract_digest'],'store':store})
        study=construct_trusted('IntegratedFullStudy',{'reference_engine':engine,
            'issuer':operator.issuer,'policy':operator.policy,'host_specs':hosts,
            'tool_specs':tools,'export_key':operator.keys['export']})
        _deadline(deadline)
        attempt.begin('full_study_execute',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle,store=store))
        final=study.execute()  # Exactly one inherited production execution call.
        preserve_score_capability(study,final)  # Before another role nonce.
        _deadline(deadline)
        attempt.begin('original_evidence_extraction',_attempt_snapshot(operator,storage=storage,native=native_receipt,bundle=bundle,store=store))
        originals,model_index,journal_read_receipt=read_close_originals(store,evidence_limits,ledger=operator.ledger)
        _need(set(originals)==set(study.results),'all 234 original aggregate close receipts')
        _need({(x['outer_person'],x['condition']) for x in model_index}==
              {(p,c) for p in study.plan.people for c in CONDITIONS} and len(model_index)==39,
              'all 39 original public tool preparations retained')
        limits=ExtractionLimits(**output['usage_extraction_limits'])
        usage_budget=UsageExtractionBudget(StudyExtractionLimits(**output['usage_extraction_budget']),
                                            set(study.results))
        extraction_source=operator.package['B']['files']['transport_evidence.py']['sha256']
        usage_keys={};usage_projection_index=[]
        operator.require(action='extract_usage')
        for context in study.contexts:
            _deadline(deadline)
            cid=context.context_id;aggregate=originals[cid]
            broker=aggregate['broker_closure']
            records=study.results[cid]['generation_inference_records']
            adapter=hosts[cid].provider_admission
            transport=broker['transport_receipt']
            bindings={'provider_admission_digest':adapter.binding_digest,
                'context_digest':digest(cid),'transport_receipt_digest':transport['receipt_digest'],
                'generation_records_digest':digest(records),'extraction_source_digest':extraction_source}
            projection=extract_transport_usage(admission=adapter,broker_closure=broker,
                aggregate_receipt=aggregate,generation_records=records,limits=limits,
                study_budget=usage_budget,extraction_source_digest=extraction_source,
                writer_authority=operator.issuer.capability('close',cid,bindings))
            key='usage_'+cid;store.put_json(key,projection);usage_keys[cid]=key
            usage_projection_index.append({'context_id':cid,'projection_digest':projection['projection_digest'],
                                            'source_capture_pins':projection['source_capture_pins']})
        usage_receipt=usage_budget.require_complete(set(study.results))
        store.put_json('run_contract',make_run_contract(operator,study,attempt_binding))
        roles=_roles(store,study,usage_keys)
        commitments=_commitments(operator,bundle,model_index,usage_projection_index,native_receipt)
        cleanup_result=bundle.close();bundle=None
        cleanup.append({'operation':'canonical_cache_release','status':'complete','original':cleanup_result})
        store.append_event('integration_full_originals_closed',{
            'usage_extraction':usage_receipt,'journal_original_reads':journal_read_receipt,
            'rawledger_event_replay_available':False,'qualified_by_this_writer':False})
        _deadline(deadline)
        closed=store.close()
        _need(closed['closed'] is True and closed['failed'] is False and not store.incidents,
              'actual private store closed without incident')
        identities={**operator.identities,'plan_digest':data.plan.binding_digest,
                    'assessment_digest':data.assessment.fingerprint}
        status=('complete_with_candidate_failures' if any(
            x['candidate_failure'] is not None or any(v is None for v in x['submission']['probabilities'].values())
            for x in study.results.values()) else 'complete')
        manifest={'schema':'n073_private_run_manifest_v2','domain':'authentic',
            'run_id':store.a.run_id,'status':status,'identities':identities,
            'store_close':closed,'artifacts':dict(store.artifacts),'journal':journal_pins(store),
            'roles':roles,'opaque_commitments':commitments,
            'diagnostics':{'incidents':list(store.incidents),
                'partial_operations':list(store.partial_operations),'cleanup_outcomes':cleanup}}
        attempt.begin('terminal_publication',_attempt_snapshot(operator,storage=storage,native=native_receipt,store=store))
        writer=TerminalWriter(store,max_bytes=output['terminal_write_bytes'],
                              max_file_bytes=evidence_limits.max_file_bytes)
        mp=writer.write(Path(root)/'run-manifest.json',manifest)
        manifest_pin={'file':'run-manifest.json','bytes':mp['bytes'],'sha256':mp['sha256']}
        terminal=issue_terminal(operator=operator,manifest=manifest,manifest_pin=manifest_pin,
                                store=store,reference_engine=engine,attempt=attempt)
        _deadline(deadline)
        tp=writer.write_encoded(Path(root)/'terminal-custody.json',terminal)
        terminal_written=True
        submission={'schema':'n073_grade_submission_v1','run_root':root,
            'manifest_pin':manifest_pin,'terminal_pin':tp,'policy_pin':operator.intent['policy_pin']}
        sp=writer.write(output_path,submission)
        return {'schema':'n073_run_return_v1','status':status,'submission':sp,
                'scientifically_graded':False,'rawledger_event_replay_available':False,
                'terminal_write_bytes':writer.written,'attempt_binding':attempt_binding}
    except BaseException as exc:
        original_exc=exc
        original={'type':type(exc).__name__,'message':str(exc),
                  'qualified':False,'attempt_root':attempt.root,
                  'original_invocation_retained':'claim durable; failure detail capture pending'}
        if store is not None and store.started and not store.closed:
            try:store.append_event('integration_original_failure',original)
            except BaseException as capture:
                cleanup.append({'operation':'failure_journal','status':'failed',
                    'original':{'type':type(capture).__name__,'message':str(capture)}})
    finally:
        if bundle is not None:
            try:
                result=bundle.close()
                cleanup.append({'operation':'canonical_cache_release','status':'complete','original':result})
            except BaseException as exc:
                cleanup.append({'operation':'canonical_cache_release','status':'failed',
                    'original':{'type':type(exc).__name__,'message':str(exc)}})
        if store is not None and store.started and not store.closed:
            try:closed=store.close()
            except BaseException as exc:
                cleanup.append({'operation':'store_close','status':'failed',
                    'original':{'type':type(exc).__name__,'message':str(exc)}})
        if original is not None and store is not None and store.closed:
            # Diagnostic only, never a final terminal/score substitute. If this
            # write itself fails its original exception is added, not retried.
            try:
                if writer is None:
                    writer=TerminalWriter(store,max_bytes=output['terminal_write_bytes'],
                                          max_file_bytes=evidence_limits.max_file_bytes)
                writer.write(Path(root)/'integration-failure.json',{
                    'schema':'n073_failed_invocation_v1','original':original,
                    'store_close':closed,'incidents':list(store.incidents),
                    'partial_operations':list(store.partial_operations),'cleanup_outcomes':cleanup,
                    'terminal_custody_written':terminal_written,'scientific_qualification':False})
            except BaseException as capture:
                original['failure_capture_error']={'type':type(capture).__name__,'message':str(capture)}

        if original_exc is not None:
            report=attempt.fail(original_exc,snapshot=_attempt_snapshot(operator,storage=storage,
                native=native_receipt,bundle=bundle,store=store,writer=writer),cleanup=cleanup)
            try:attempt.close()
            except BaseException as close_error:
                report['failure_capture_errors'].append({'operation':'attempt_descriptor_close',
                    'exception_type':type(close_error).__name__})
                report['failure_details_durable']=False
            raise InvocationFailed(report) from original_exc
        try:attempt.close()
        except BaseException as close_error:
            report=attempt.fail(close_error,snapshot=_attempt_snapshot(operator,storage=storage,
                native=native_receipt,store=store,writer=writer),cleanup=cleanup)
            raise InvocationFailed(report) from close_error
