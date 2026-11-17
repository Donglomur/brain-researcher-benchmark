"""Build a root-reviewable source-only registration from real A/B/T/D/F/S.

No shared file is modified. This module is a B/F source member; the registration
R it returns is a later artifact, never a dependency of F, D, S or the runtime.
All history values are metadata only: no historical result/source path is opened.
"""
from copy import deepcopy
import hashlib
from pathlib import Path,PurePosixPath
import re

from .declaration import (DeclarationError,canonical_file_bytes,load_package,
                          read_json_pinned,read_bytes_pinned,ReadLedger,validate_deployment)


class RegistrationError(ValueError): pass


TASK_ID='NEURAL-073'
TASK_DIRECTORY='benchmarks/neuroscience/neural-073'
RUNTIME_TARGET=TASK_DIRECTORY+'/manifest.json'
CANONICAL_TARGET='benchmarks/manifests/neural/NEURAL-073.json'
README_TARGET=TASK_DIRECTORY+'/README.md'
PROFILE='full_declared_catalogue_v1'
# Selected exact metadata preimages; these constants authorize no shared write.
LEGACY_WORK={'bytes':18176,'sha256':'7dd4373aec6aa0cd55fa5e60b20d9bed35c8bbb24f8b69f89b627c485d5cb071'}
LEGACY_HEAD={'bytes':15919,'sha256':'839fefe968578c8980ab93646dd2b394db7347bd734815c332c9bcbfbc26f457'}
CANONICAL_PREIMAGE={'bytes':11755,'sha256':'194e910a9c12dcfaf1eff314796f40dfb71253c904a6f131c9f4b7a3ae450893'}
README_PREIMAGE={'bytes':1772,'sha256':'35b7dd333a997ec85196792049ab3e2e667e28e0d34696eb3571f25a2e7f35d8'}
SOURCE_READ_CAP=2*64*2**20+8*2**20
REGISTRATION_LIMIT=131072
PREFERENCE_LIMIT=262144
S_FIELDS={'schema','task_id','package_prefix','source_freeze','deployment','wrapper',
          'code_closure','parent_closure','task','status','files'}
FULL_SCOPE={'records':9532,'people':13,'protocols':25,'cells':300,'contexts':234,
    'conditions':['original','spatial_scrambled','C_only'],'arms':['F','I'],'repetitions':[0,1,2],
    'same_existing_ID':True,'new_dataset':False,'source_profile':'declared_catalogue_labels',
    'native_provider_qualification':False,'scientific_qualification':False}


def _relative(value):
    if (not isinstance(value,str) or not value or '\\' in value or '\x00' in value
        or value.startswith('/') or str(PurePosixPath(value))!=value
        or any(p in ('','.','..') for p in value.split('/'))):
        raise RegistrationError('canonical relative source path required')
    return value


def _prefix(value):
    value=_relative(value)
    if not value.startswith(TASK_DIRECTORY+'/'):raise RegistrationError('wrapper must remain inside the registered task directory')
    return value


def _pin(value):
    if not isinstance(value,dict) or set(value) not in ({'bytes','sha256'},{'path','bytes','sha256'}):
        raise RegistrationError('closed exact source pin required')
    if type(value['bytes']) is not int or value['bytes']<0 or not isinstance(value['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['sha256']):
        raise RegistrationError('real nonnegative extent and lowercase SHA256 required')
    if 'path' in value:_relative(value['path'])
    return {'bytes':value['bytes'],'sha256':value['sha256']}


def _actual_pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _descriptor(path,pin):return {'path':_relative(path),**_pin(pin)}


def _no_design_slots(value):
    if isinstance(value,str) and ('DERIVE_' in value or value in ('DERIVE','TODO','TBD')):
        raise RegistrationError('design slot is not an artifact identity')
    if isinstance(value,dict):
        for key,item in value.items():_no_design_slots(key);_no_design_slots(item)
    elif isinstance(value,(list,tuple)):
        for item in value:_no_design_slots(item)


def _selected_legacy(document,pin):
    if _pin(pin)!=LEGACY_WORK:raise RegistrationError('legacy preimage differs from the exact selected captured work body')
    if not isinstance(document,dict) or any(document.get(k)!=v for k,v in
        {'schema_version':1,'id':TASK_ID,'track':'neural','title':'Cognitive task identification from fMRI maps'}.items()):
        raise RegistrationError('legacy task identity differs')
    required={'program_execution','admission','verification','scope','status'}
    if not required.issubset(document):raise RegistrationError('complete captured legacy metadata required')
    return {'active_route':False,'scope':document['scope'],'source_status_at_capture':document['status'],
        'captured_work_metadata_pin':deepcopy(LEGACY_WORK),'captured_head_metadata_pin':deepcopy(LEGACY_HEAD),
        'program_execution':deepcopy(document['program_execution']),'admission':deepcopy(document['admission']),
        'top_level_verification':deepcopy(document['verification']),'qualification_reverified_by_this_build':False,
        'historical_metadata_is_runtime_dependency':False}


def _validate_preferred_source(source,package,prefix):
    """Join S's real inventory to F; central campaign reads files, not wrapper."""
    if not isinstance(source,dict) or set(source)!=S_FIELDS:raise RegistrationError('closed preferred source proposal schema required')
    if (source['schema']!='n073_preferred_source_proposal_v1' or source['task_id']!=TASK_ID
        or source['package_prefix']!=prefix or source['status']!='source_only_unqualified'):
        raise RegistrationError('preferred source identity/status differs')
    pins=package['pins'];frozen=package['F']['files']
    expected={}
    for full,row in frozen.items():
        if not full.startswith(prefix+'/'):raise RegistrationError('freeze member outside exact selected prefix')
        local=_relative(full[len(prefix)+1:])
        if local in ('SOURCE_FREEZE.json','SOURCE_PROPOSAL.json'):raise RegistrationError('F cannot contain itself or S')
        expected[local]=_pin(row)
    expected['SOURCE_FREEZE.json']=_pin(pins['F'])
    if len(expected)>512 or not isinstance(source['files'],dict) or source['files']!=dict(sorted(expected.items())):
        raise RegistrationError('preferred inventory must be exact F members plus F, within central512-member bound')
    joins={'source_freeze':('SOURCE_FREEZE.json',pins['F']),'deployment':('DEPLOYMENT.json',pins['D']),
        'code_closure':('CODE_CLOSURE.json',pins['B']),'parent_closure':('PARENT_CLOSURE.json',pins['A']),
        'task':('TASK.json',pins['T']),'wrapper':('run.py',expected.get('run.py'))}
    for field,(local,pin) in joins.items():
        if pin is None or source[field]!=_descriptor(prefix+'/'+local,pin):
            raise RegistrationError('preferred source graph join differs: '+field)
    _no_design_slots(source)
    return expected


def _replacement(path,document,preimage,*,limit):
    raw=canonical_file_bytes(document)
    if len(raw)>limit:raise RegistrationError('proposed artifact exceeds its concrete central bound')
    return {'path':path,'preimage':deepcopy(preimage),'replacement_pin':_actual_pin(raw),
            'encoding':'canonical_utf8_json_plus_one_LF','document':document}


def build_registration(package_root,*,package_prefix,legacy_snapshot_path,legacy_snapshot_pin,preferred_source_proposal_pin):
    """Read actual closed sources, then return R. No F/S placeholders or writes.

    Future root installation must compare the then-current target to preimage
    exactly and reauthenticate every body. Returning this proposal grants neither
    installation authority nor native/data/provider/scientific qualification.
    """
    prefix=_prefix(package_prefix)
    legacy_pin=_pin(legacy_snapshot_pin)
    if legacy_pin!=LEGACY_WORK:raise RegistrationError('unselected legacy snapshot pin')
    preferred_pin=_pin(preferred_source_proposal_pin)
    if preferred_source_proposal_pin.get('path',prefix+'/SOURCE_PROPOSAL.json')!=prefix+'/SOURCE_PROPOSAL.json':
        raise RegistrationError('preferred source must be the exact interface direct child')
    if not 0<preferred_pin['bytes']<=PREFERENCE_LIMIT:raise RegistrationError('bounded preferred source descriptor required')
    package=load_package(package_root,read_cap=SOURCE_READ_CAP)
    if package['package_prefix']!=prefix:raise RegistrationError('registered prefix differs from authenticated F mapping')
    deployment=validate_deployment(package['D'],configured_required=False)
    if deployment.get('status')!='unconfigured' or deployment.get('execution_enabled') is not False:
        raise RegistrationError('this source-only renderer requires the real unconfigured deployment')
    root=package['root'];ledger=package['ledger']
    source,source_raw=read_json_pinned(root/'SOURCE_PROPOSAL.json',preferred_pin,limit=PREFERENCE_LIMIT,ledger=ledger)
    expected=_validate_preferred_source(source,package,prefix)
    for name in ('run.py','grade.py','registration.py','static/TASK.md','static/OPERATOR.md','static/legacy_registry.json'):
        if name not in expected:raise RegistrationError('required operative/static source absent from F: '+name)
    if expected['static/legacy_registry.json']!=LEGACY_WORK:raise RegistrationError('portable legacy metadata must preserve exact captured work body')
    legacy,legacy_raw=read_json_pinned(legacy_snapshot_path,legacy_pin,limit=REGISTRATION_LIMIT,ledger=ledger)
    history=_selected_legacy(legacy,legacy_pin)
    source_binding={'path':prefix,'source':_descriptor(prefix+'/SOURCE_PROPOSAL.json',preferred_pin)}
    dep_sha=package['pins']['D']['sha256']
    programme={'status':'source_only_unqualified','profile':PROFILE,
        'entrypoint':{'argv':['{python}',prefix+'/run.py','run','--deployment',prefix+'/DEPLOYMENT.json',
            '--deployment-sha256',dep_sha,'--program','{program}','--output','{output}',
            '--review','{review}','--other-reserve-bytes','{other_reserve_bytes}'],
            'sha256':expected['run.py']['sha256'],'working_directory':'.',
            'required_operator_arguments':['review','other_reserve_bytes'],
            'program_operand_semantics':'closed fixed-policy declaration; never trusted host code'},
        'instructions_path':prefix+'/static/TASK.md','operator_instructions_path':prefix+'/static/OPERATOR.md',
        'preferred_source_interface':source_binding,'source_freeze':_descriptor(prefix+'/SOURCE_FREEZE.json',package['pins']['F']),
        'scope':deepcopy(FULL_SCOPE),'source_history_is_runtime_dependency':False,
        'grading':{'primary':'equal_record_mean_within_person_protocol_then_equal_available_protocols_within_person_then_equal13people_accuracy',
            'secondary':'Brier_with_same_weights_and_invalid_row_penalty2','all18candidate_panels':True,
            'all48reference_panels':True,'all6repetition_summaries':True,'all91comparisons':True,
            'no_single_best_arm_repetition_family_selection':True},
        'runtime':{'execution_enabled':False,'deployment_status':'unconfigured','candidate_caps':deepcopy(package['T']['candidate_caps']),
            'reference_data_host_storage_capacity':'Explicit separately qualified complete deployment; no legacy resource reuse'},
        'verification':{'status':'not_run','reason':'New full interface requires fresh independently qualified evidence; legacy controls do not transfer.'}}
    doc={k:deepcopy(legacy[k]) for k in ('id','schema_version','track','title')}
    doc.update(status='full_program_source_only_unqualified',scope='Complete captured NeuroVault6618 declared-label recovery:9532records/13people/25protocols/300available cells; full234-context F/I/control/repetition programme.',
        admission={'runnable':False,'research_qualified':False,'submission_ready':False,'full_candidate_contract_complete':False,
            'source_implementation_complete':False,'source_closure_complete':True,
            'reason':'Exact source closure is not independent source acceptance or data/native/provider/scientific qualification.'},
        verification={'status':'not_run','profile':PROFILE,'legacy_receipts_carried_as_new_qualification':False},
        program_execution=programme,program_conditions={PROFILE:'default'},historical_profiles={'legacy_ibc312_v1':history},
        entrypoints={'score':{'argv':['{python}',prefix+'/grade.py','--submission','{submission}','--output','{output}',
            '--deployment',prefix+'/DEPLOYMENT.json','--deployment-sha256',dep_sha,'--review','{review}',
            '--other-reserve-bytes','{other_reserve_bytes}'],'sha256':expected['grade.py']['sha256'],
            'working_directory':'.','submission_semantics':'sealed-run descriptor and externally authenticated terminal custody, never a scalar/prediction surrogate'}})
    _no_design_slots(doc)
    replacement=_replacement(RUNTIME_TARGET,doc,LEGACY_WORK,limit=REGISTRATION_LIMIT)
    return {'schema':'n073_registration_proposal_v1','task_id':TASK_ID,'source_only':True,'installation_selected':False,
        'package_prefix':prefix,'replacement':replacement,'preferred_source_interface':source_binding,
        'validated_sources':{**{key:_descriptor(prefix+'/'+row['path'],row) for key,row in package['pins'].items()},
            'S':_descriptor(prefix+'/SOURCE_PROPOSAL.json',preferred_pin)},
        'read_bytes':package['read_bytes']+len(source_raw)+len(legacy_raw),
        'root_installation':'Compare exact then-current preimage, preserve unrelated state, reauthenticate all pins and separately select installation.',
        'scientific_or_execution_admission':False}


def _require_registration(proposal):
    if (not isinstance(proposal,dict) or proposal.get('schema')!='n073_registration_proposal_v1'
        or proposal.get('task_id')!=TASK_ID or proposal.get('installation_selected') is not False
        or proposal.get('scientific_or_execution_admission') is not False):
        raise RegistrationError('source-only uninstalled registration proposal required')
    prefix=_prefix(proposal.get('package_prefix'))
    replacement=proposal.get('replacement',{})
    if replacement.get('path')!=RUNTIME_TARGET or replacement.get('preimage')!=LEGACY_WORK:
        raise RegistrationError('registration compare-and-swap target/preimage mismatch')
    doc=replacement.get('document')
    if not isinstance(doc,dict) or _actual_pin(canonical_file_bytes(doc))!=_pin(replacement.get('replacement_pin')):
        raise RegistrationError('registration proposed body changed')
    if (doc.get('id')!=TASK_ID or doc.get('verification',{}).get('status')!='not_run'
        or doc.get('program_execution',{}).get('verification',{}).get('status')!='not_run'
        or doc.get('program_conditions')!={PROFILE:'default'}):
        raise RegistrationError('only the unqualified complete default and named alias may be staged')
    if any(doc.get('admission',{}).get(k) is not False for k in ('runnable','research_qualified','submission_ready')):
        raise RegistrationError('source metadata cannot promote admission')
    _no_design_slots(proposal)
    return prefix


def build_metadata_staging(registration,*,canonical_snapshot_path,canonical_snapshot_pin,readme_snapshot_path,readme_snapshot_pin):
    """Optional exact-preimage canonical-spec/README proposals, with no writes.

    Historical source questions and citations stay explicitly inactive. The root
    must separately select every installation and compare all original bytes.
    """
    prefix=_require_registration(registration)
    if _pin(canonical_snapshot_pin)!=CANONICAL_PREIMAGE or _pin(readme_snapshot_pin)!=README_PREIMAGE:
        raise RegistrationError('optional metadata preimages differ from the selected captured bodies')
    ledger=ReadLedger(2*REGISTRATION_LIMIT)
    old,old_raw=read_json_pinned(canonical_snapshot_path,CANONICAL_PREIMAGE,limit=REGISTRATION_LIMIT,ledger=ledger)
    readme_raw=read_bytes_pinned(readme_snapshot_path,README_PREIMAGE,limit=REGISTRATION_LIMIT,ledger=ledger)
    if (old.get('id')!=TASK_ID or old.get('schema_version')!=1 or old.get('status')!='specification_only'
        or old.get('admission',{}).get('runnable') is not False or old.get('admission',{}).get('research_qualified') is not False):
        raise RegistrationError('canonical specification cannot claim runtime completion')
    new=deepcopy(old)
    new['historical_profiles']={'original_provenance_spec_v1':{'active_profile':False,
        'captured_preimage':deepcopy(CANONICAL_PREIMAGE),'document':deepcopy(old),
        'stronger_original_provenance_gates_fulfilled':False}}
    question='Can one fixed general model/tool policy recover the captured catalogue25 declared protocol labels across all13 held people under full-support F/I and acquisition/scramble controls?'
    overlay={'scientific_question':question,'scope':deepcopy(FULL_SCOPE),
        'primary_metric':'equal records within person/protocol, equal available protocols within person, then equal13people; same Brier weights',
        'inputs':'Exact captured NeuroVault6618 aggregate snapshot; original/canonical body identity, rights, geometry and complete adjudication remain required.',
        'conditions':'One complete programme; conditions and aliases do not add task IDs.',
        'readiness':'source_only_unqualified; unconfigured; no authentic run or external benchmark admission',
        'source_freeze':registration['validated_sources']['F'],
        'source_preference':registration['preferred_source_interface'],
        'stronger_original_producer_lineage_qualified':False}
    new.update(active_profile=PROFILE,scientific_question=question,profile_overlays={PROFILE:overlay})
    new['primary_outputs']=['All18candidate/48reference panels,6repetition summaries and91 prespecified comparisons for the complete9532-record declared-label programme; private rows remain protected.']
    new['case_definition']='All9532 captured catalogue records across13 people/25 declared protocol labels/300 available person-protocol cells; no record or disputed identity removed.'
    new['source_identity']={**deepcopy(old['source_identity']),
        'active_instance_qualification':'Historical source grouping retained; active instance is the exact captured6618 declared-label snapshot, not a claim that raw releases or original producer lineage are homogeneous.'}
    new['input_assets']={'routes':['https://neurovault.org/collections/6618/'],
        'source_metadata':'Exact captured catalogue source in the full package; metadata availability does not prove map content or rights.',
        'exact_asset_records':[],'missing_or_unverified':['Original/canonical map identities and decoding fidelity','Complete source/identity adjudication and cross-person duplicate screen','Rights, common geometry and native/provider/runtime qualification'],
        'historical_input_records':'Retained verbatim in inactive original_provenance_spec_v1.'}
    new['allowed_inputs']={'proposed_scope':'Matched full training/query batches and admitted tools under fixed F/I policy; private targets and source-identity lookup are excluded, while permitted cardinality/grouping and nuisance C remain.',
        'schema_verified':False,'source_only_contract':prefix+'/static/TASK.md'}
    new['split']={'policy':'All13 whole-person outer folds, training-only inner selection/calibration; AP/PA/FFX and all declared variants retained.',
        'data_scope':'public_development_only','manifest_status':'requires_authenticated_full_corpus_and_plan',
        'uncertainty':'Person-level inference across13 people; maps/repetitions do not add independent people.'}
    new['reference']={'source':'Independent complete353-configuration/35-block reference graph fixed by full task source',
        'reference_executed_for_this_contract':False,'legacy_author_code_or_results_reused_as_execution':False}
    new['controls']=['Matched original/spatial_scrambled/C_only complete conditions','N,C,NC competent references and full held-person folds','Fixed F/I inference and three repetitions; source/cardinality/acquisition confounds reported']
    new['access_conditions']={'agent_modes':['F','I'],'full_scope_required':True,'fixed_model_policy_and_inference':True,
        'F':'Model-assisted authoring before actual process/snapshot freeze; no query-time model call.',
        'I':'Same model/tools/full query batch with allowed query-time investigation; no evaluator feedback.'}
    new['evaluation']={'observable_endpoints':{'definition':overlay['primary_metric'],'scoring_status':'source_only_unqualified'},
        'comparability':'Same existing task; aliases and reused sources add no benchmarks.',
        'unresolved_grading':['Independent runtime/data/provider/whole-study/custody qualification'],
        'executor_ref':prefix+'/run.py','scorer_ref':prefix+'/grade.py'}
    new['resources']={'class':'explicit_full_deployment_required','basis':'Candidate ceilings are48hours/16cores/64GiB/512GiB each, not measured needs; separate complete reference/data/storage/observer/grader capacity must be qualified.'}
    new['holds']=[{'id':'full_scope_admission','requirement':'Complete original/canonical corpus identity, rights, geometry, conversion fidelity, duplicate/identity adjudication and all9532 records.'},
        {'id':'native_provider','requirement':'Actual Linux namespace/cgroup/OOM witness, payload eligibility, fixed provider and accounting qualification.'},
        {'id':'whole_study','requirement':'Complete13fold/234context programme, references, original durable closure and protected replay before scientific admission.'},
        {'id':'stronger_provenance','requirement':'Historical original producer/FFX lineage remains a separate unfulfilled profile; declared labels do not resolve it.'}]
    new['next_implementation_action']=['Review complete source and separately qualify a full configured deployment; do not reuse legacy passing receipts.']
    new['admission']={'runnable':False,'research_qualified':False,'submission_ready':False,
        'reason':'Specification and source registration do not admit an authentic benchmark run.'}
    new['provenance']={**deepcopy(old['provenance']),'full_profile_source_freeze':registration['validated_sources']['F'],
        'prior_specification_preimage':deepcopy(CANONICAL_PREIMAGE),'scientific_execution':False}
    spec=_replacement(CANONICAL_TARGET,new,CANONICAL_PREIMAGE,limit=REGISTRATION_LIMIT)
    deployment_sha=registration['validated_sources']['D']['sha256']
    local_prefix=prefix[len(TASK_DIRECTORY)+1:]
    text=('# Full declared-catalogue programme (NEURAL-073)\n\n'
        'The default and `full_declared_catalogue_v1` alias describe one complete programme:9,532 records,13 people,25 declared labels and234 matched F/I/control/repetition contexts. Source is unconfigured and unqualified; central run and score gates remain `not_run`. No scientific result or additional benchmark is claimed.\n\n'
        'Metadata-only inspection, after this exact source package is installed:\n\n'
        '```sh\npython3 '+prefix+'/run.py inspect --deployment '+prefix+'/DEPLOYMENT.json --deployment-sha256 '+deployment_sha+'\n```\n\n'
        'See [task instructions]('+local_prefix+'/static/TASK.md) and [operator requirements]('+local_prefix+'/static/OPERATOR.md). A full configured deployment needs separate data/rights/geometry/identity, numerical, native OOM-witness/provider, storage and complete-study qualification. The original producer-lineage profile remains unfulfilled.\n\n'
        '## Inactive legacy source record\n\nThe exact preceding README follows as historical context; its seven-protocol route and past qualifications are inactive and do not qualify the full programme. No active legacy alias is registered.\n\n'+readme_raw.decode('utf-8'))
    raw=text.encode('utf-8')
    if len(raw)>REGISTRATION_LIMIT:raise RegistrationError('README staging exceeds finite metadata bound')
    readme={'path':README_TARGET,'preimage':deepcopy(README_PREIMAGE),'replacement_pin':_actual_pin(raw),
            'encoding':'utf8','text':text}
    return {'schema':'n073_optional_metadata_staging_v1','task_id':TASK_ID,'installation_selected':False,
        'replacements':[spec,readme],'read_bytes':len(old_raw)+len(readme_raw),
        'root_must_compare_each_then_current_preimage':True,'scientific_or_execution_admission':False}
