"""Selected operator custody. No key, filesystem or provider work at import.

Only admit_operator issues an OperatorContext, after the independently selected
source/deployment, real root MAC and all original gate bodies have been joined.
This is trusted-host custody, not a boundary against arbitrary same-host Python.
BUILD ONLY controls never construct an authentic selection or positive context.
"""
from pathlib import Path
from types import MappingProxyType
import hashlib
import hmac
import json
import os
import re
import stat
import time
import math
import weakref
from contextlib import contextmanager
from . import declaration as d
from .runtime.core.custody import AuthorityVerifier, canonical, digest, CustodyError
from .runtime.runner.authority import RoleIssuer
from .runtime.runner.policy import Policy
from .runtime.core.inference import InferencePolicy


class OperatorError(CustodyError):
    pass


_ACTIONS = frozenset(('run','observe','grade','extract_usage','issue_terminal'))
_ROLES = frozenset(('admission','export','reference_fit','reference_predict',
                    'candidate_author','candidate_query','score','close'))
_BASE_KEYS = ('accepted_parent_closure_digest','code_closure_digest','task_design_digest',
              'deployment_digest','source_freeze_digest','policy_file_digest',
              'invocation_intent_digest','execution_selection_envelope_sha256','runtime_policy_digest')
_ROOT_REQUIRED = frozenset(_BASE_KEYS) - {'execution_selection_envelope_sha256'}
_GATES = ('original_body_source_authority','converter_fidelity','rights_redistribution',
          'cross_person_identity_adjudication','geometry_full_support','native_runtime_and_isolation',
          'privileged_oom_witness','fixed_provider_and_inference','complete_capacity_and_storage',
          'private_output_custody')
_SECTION_FIELDS = {
    'numerical': ('n073_numerical_section_v1', ('contract','native_qualification_digest')),
    'corpus': ('n073_corpus_section_v1', ('inventory_pin','canonical_root','geometry','identity_conflicts','adjudications')),
    'host': ('n073_host_section_v1', ('host_specs_pin','tool_specs_pin')),
    'provider': ('n073_provider_section_v1', ('model_profile_id','inference_policy','common_profile')),
    'capacity': ('n073_capacity_section_v1', ('metadata_limits','canonical_limits','reference_capacity',
                                           'preparation_numeric_limits','storage','whole_wall_seconds')),
    'private_output': ('n073_private_output_section_v3', ('output_parent','store_template','evidence_limits','attempt_limits',
                        'terminal_write_bytes','usage_extraction_limits','usage_extraction_budget')),
}
_PROVIDER_FIELDS = ('model_revision','source_closure_digest','fixed_model_evidence_digest',
    'stateless_evidence_digest','tokenizer_evidence_digest','usage_evidence_digest',
    'environment_evidence_digest','protocol_evidence_digest','capacity_evidence_digest',
    'capacity_basis','max_frame_bytes','max_capture_bytes')
_INTENT_FIELDS = ('schema','invocation_id','selection_id','output_path','policy_pin','runtime_policy_digest',
    'accepted_parent_closure_digest','code_closure_digest','task_design_digest','deployment_digest',
    'source_freeze_digest','other_reserve_bytes')
_TERMINAL_FIELDS = ('schema','root_id','run_id','domain','manifest_pin','identities',
    'artifact_index_digest','journal_events','journal_head','close_receipt_digest','status','attempt_binding')
_SEAL = object()
_OPERATORS = weakref.WeakKeyDictionary()
_TERMINALS = weakref.WeakKeyDictionary()


def _need(value, message):
    if not value:
        raise OperatorError(message)


def _closed(value, names, role):
    _need(type(value) is dict and set(value) == set(names), 'closed ' + role + ' fields')
    return value


def _copy(value):
    return json.loads(canonical(value))


def _text(value, role, maximum=512):
    _need(type(value) is str and bool(value) and '\x00' not in value and
          len(value.encode('utf-8')) <= maximum, 'bounded ' + role)
    return value


def _token(value):
    _need(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', value) is not None,
          'safe explicit invocation/selection token')
    return value


def _positive(value, role):
    _need(type(value) is int and 0 < value <= 2**53-1, 'finite positive ' + role)
    return value


def _metadata_limits(value):
    _closed(value, ('file_bytes','total_bytes'), 'metadata limits')
    for key in value:
        _positive(value[key], key)
    _need(value['file_bytes'] <= 64*1024*1024 and value['file_bytes'] <= value['total_bytes'],
          'source metadata file limit/total relation')
    return value


def _path(root, value):
    if type(value) is str and value.startswith('/'):
        return d._absolute(value)
    return d._absolute(root) / d.relative_path(value)


def _identity_pin(pin, *, maximum=64*1024*1024):
    _closed(pin, ('path','bytes','sha256'), 'explicit metadata descriptor')
    d._pin(pin, max_bytes=maximum)
    _need(pin['bytes'] > 0, 'nonempty selected metadata')
    return pin


def validate_trust_anchor(value):
    """Pure shape/permission contract; it opens no key or directory."""
    _closed(value, ('schema','root_id','issuer_id','keys','evidence_root','intent_root','metadata_limits'), 'trust anchor')
    _need(value['schema'] == 'n073_trust_anchor_v1', 'trust anchor schema')
    _text(value['root_id'], 'root ID'); _text(value['issuer_id'], 'issuer ID')
    d._absolute(value['evidence_root']); d._absolute(value['intent_root'])
    _metadata_limits(value['metadata_limits'])
    _closed(value['keys'], ('root','issuer','context','permutation','export'), 'five key references')
    paths = set()
    for name, ref in value['keys'].items():
        _closed(ref, ('path','max_bytes','owner_uid','mode'), 'private key reference')
        path = str(d._absolute(ref['path']))
        _need(path not in paths, 'private key references cannot alias')
        paths.add(path)
        _need(type(ref['owner_uid']) is int and ref['owner_uid'] >= 0 and
              type(ref['mode']) is int and ref['mode'] in (0o400,0o600) and
              type(ref['max_bytes']) is int and 32 <= ref['max_bytes'] <= 4096,
              'explicit private key owner/mode/byte cap')
    return _copy(value)


def _read_secret(ref, ledger):
    """Future selected private read; no content/hash enters its metadata receipt."""
    path = d._absolute(ref['path']); held = []; chain = []; original = None
    row = ledger.reserve('private-key-reference', ref['max_bytes'])
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY); held.append(fd)
        for name in path.parts[1:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            held.append(child); chain.append((fd,name,child,d._stamp(os.fstat(child)))); fd=child
        f = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd); held.append(f)
        before = os.fstat(f)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == ref['owner_uid']
              and stat.S_IMODE(before.st_mode) == ref['mode'] and 32 <= before.st_size <= ref['max_bytes'],
              'private key ownership/mode/extent refused')
        pieces=[];left=before.st_size
        while left:
            raw=os.read(f,left);_need(bool(raw),'short private read')
            pieces.append(raw);left-=len(raw);row['read_bytes']+=len(raw);ledger.actual_bytes+=len(raw)
        _need(d._stamp(before)==d._stamp(os.fstat(f))==d._stamp(os.stat(path.name,dir_fd=fd,follow_symlinks=False)),
              'private key changed during read')
        for parent,name,child,identity in chain:
            _need(d._stamp(os.fstat(child))==identity==d._stamp(os.stat(name,dir_fd=parent,follow_symlinks=False)),
                  'private key ancestor changed')
        row['status']='private_read_stable';return b''.join(pieces)
    except BaseException as error:
        original=error;row['status']='failed';row['error_type']=type(error).__name__;raise
    finally:
        errors=[]
        for f in reversed(held):
            try:os.close(f)
            except OSError as error:errors.append(error)
        if errors:
            raise BaseExceptionGroup('private read/close errors',([original]if original is not None else[])+errors) from None


def _read_section(package, name, ledger, file_limit):
    pin=package['D']['section_manifests'][name]
    _identity_pin(pin,maximum=file_limit)
    value,raw=d.read_json_pinned(_path(package['root'],pin['path']),pin,limit=file_limit,ledger=ledger)
    schema,fields=_SECTION_FIELDS[name]
    _closed(value,('schema',*fields),name+' section')
    _need(value['schema']==schema,'selected '+name+' schema')
    return value,raw


def _validate_sections(sections):
    """Closed metadata shapes; actual native/data consumers retain their gates."""
    from .constructors import construct_typed
    from .evidence import EvidenceLimits
    capacity=sections['capacity'];_metadata_limits(capacity['metadata_limits'])
    _closed(capacity['canonical_limits'],('total_read_bytes','per_file_bytes','cache_bytes',
             'max_array_elements','max_workspace_bytes'),'canonical capacities')
    for key,value in capacity['canonical_limits'].items():
        _need(type(value)is int and value>=0 if key=='cache_bytes' else type(value)is int and value>0,
              'finite canonical capacity')
    construct_typed('ReferenceCapacity',capacity['reference_capacity'])
    construct_typed('NumericLimits',capacity['preparation_numeric_limits'])
    _positive(capacity['whole_wall_seconds'],'whole invocation wall')
    storage=_closed(capacity['storage'],('root','minimum_free_bytes','owned_reservation_bytes',
                      'other_reserve_minimum_bytes'),'storage selection')
    d._absolute(storage['root'])
    for key in ('minimum_free_bytes','owned_reservation_bytes'):_positive(storage[key],key)
    _need(type(storage['other_reserve_minimum_bytes'])is int and storage['other_reserve_minimum_bytes']>=0,
          'explicit other-work reservation')
    corpus=sections['corpus'];_identity_pin(corpus['inventory_pin']);d._absolute(corpus['canonical_root'])
    construct_typed('Geometry',corpus['geometry'])
    for field,ident in (('identity_conflicts','IdentityConflict'),('adjudications','Adjudication')):
        _need(type(corpus[field])is list and len(corpus[field])<=100000,'bounded explicit '+field)
        for row in corpus[field]:construct_typed(ident,row)
    for key in ('host_specs_pin','tool_specs_pin'):_identity_pin(sections['host'][key])
    num=sections['numerical'];d._sha(num['native_qualification_digest'])
    contract=_closed(num['contract'],('schema','package','version','python_major_minor','distribution_root',
                     'source_read_cap','pins'),'native numerical contract')
    _need(contract['schema']=='n073_native_numpy_runtime_v1' and contract['package']=='numpy' and
          contract['version']=='2.4.6' and contract['python_major_minor']==[3,11],'selected native numerical identity')
    d._absolute(contract['distribution_root']);_positive(contract['source_read_cap'],'native source read bound')
    _need(type(contract['pins'])is dict and bool(contract['pins']),'explicit native pins')
    for pin in contract['pins'].values():_identity_pin(pin)
    provider=sections['provider'];_text(provider['model_profile_id'],'model profile')
    InferencePolicy.from_dict(provider['inference_policy'])
    _closed(provider['common_profile'],_PROVIDER_FIELDS,'fixed provider common profile')
    for key,value in provider['common_profile'].items():
        if key.endswith('_digest'):d._sha(value)
        elif key.startswith('max_'):_positive(value,key)
        else:_text(value,key)
    private=sections['private_output'];d._absolute(private['output_parent'])
    from .attempts import AttemptLimits
    _closed(private['attempt_limits'],tuple(AttemptLimits.__dataclass_fields__),'attempt capacities')
    attempt_limits=AttemptLimits(**private['attempt_limits'])
    _need(attempt_limits.wall_seconds>=sections['capacity']['whole_wall_seconds'],
          'attempt custody must cover entire selected invocation wall bound')
    _closed(private['store_template'],('single_artifact_bytes','total_write_bytes','journal_record_bytes',
                    'store_contract_digest'),'private store template')
    d._sha(private['store_template']['store_contract_digest'])
    for key in ('single_artifact_bytes','total_write_bytes','journal_record_bytes'):
        _positive(private['store_template'][key],key)
    _closed(private['evidence_limits'],tuple(EvidenceLimits.__dataclass_fields__),'evidence capacities')
    EvidenceLimits(**private['evidence_limits'])
    _positive(private['terminal_write_bytes'],'terminal metadata write budget')
    _closed(private['usage_extraction_limits'],('max_capture_bytes','max_frame_bytes','max_projection_bytes',
             'max_workspace_bytes','max_frames','wall_seconds'),'usage extraction limits')
    _closed(private['usage_extraction_budget'],('max_total_capture_bytes','max_total_projection_bytes',
             'max_workspace_bytes','wall_seconds','max_contexts'),'whole usage extraction budget')
    for group in ('usage_extraction_limits','usage_extraction_budget'):
        for key,value in private[group].items():_positive(value,key)
    _need(private['usage_extraction_budget']['max_contexts']==234,'all234 usage contexts required')


def _gate_bodies(claims, package, trust, ledger, file_limit):
    evidence=claims['evidence'];_need(type(evidence)is list and len(evidence)==len(_GATES),'all ten root-selected gates')
    by_kind={}
    for pin in evidence:
        _closed(pin,('kind','bytes','sha256'),'root evidence pin')
        _need(pin['kind']in _GATES and pin['kind']not in by_kind,'exact unique gate names')
        d._pin({k:pin[k]for k in('bytes','sha256')},path_allowed=False,max_bytes=file_limit)
        _need(pin['bytes']>0,'nonempty gatebody');by_kind[pin['kind']]=pin
    expected={'accepted_parent_closure_digest':package['pins']['A']['sha256'],
              'code_closure_digest':package['pins']['B']['sha256'],'task_design_digest':package['pins']['T']['sha256'],
              'deployment_digest':package['pins']['D']['sha256'],'source_freeze_digest':package['pins']['F']['sha256']}
    result={};root=d._absolute(trust['evidence_root']);seen={p['sha256']for p in evidence}
    for name in _GATES:
        pin=by_kind[name];body,_=d.read_json_pinned(root/(pin['sha256']+'.json'),
            {k:pin[k]for k in('bytes','sha256')},limit=file_limit,ledger=ledger)
        _closed(body,('schema','gate','status',*expected,'control_receipts','claim_scope'),'original gate qualification')
        _need(body['schema']=='n073_gate_qualification_v1' and body['gate']==name and body['status']=='passed',
              'root-selected gate qualification not passed')
        _need(all(body[k]==v for k,v in expected.items()),'gate is for a different source/deployment')
        _text(body['claim_scope'],'gate claim scope',8192)
        controls=body['control_receipts'];_need(type(controls)is list and 1<=len(controls)<=64,'actual bounded control provenance')
        unique=set()
        for control in controls:
            _closed(control,('kind','bytes','sha256'),'original control evidence pin');_text(control['kind'],'control evidence role')
            d._pin({k:control[k]for k in('bytes','sha256')},path_allowed=False,max_bytes=file_limit)
            _need(control['bytes']>0 and control['sha256']not in seen and control['sha256']not in unique,
                  'cyclic/duplicate gate provenance')
            unique.add(control['sha256'])
            original,_=d.read_json_pinned(root/(control['sha256']+'.json'),
                {k:control[k]for k in('bytes','sha256')},limit=file_limit,ledger=ledger)
            _need(type(original)is dict and bool(original),'actual original metadata receipt body required')
        result[name]=body
    return result


class OperatorContext:
    __slots__=('_package','_sections','_keys','_intent','_identities','_policy','_policy_document',
               '_verifier','_issuer','_ledger','_claims','_gates','_run_root','__weakref__')
    def __init__(self, *, seal=None, **values):
        _need(seal is _SEAL,'OperatorContext is issued only after independent authentication')
        for key,value in values.items():object.__setattr__(self,'_'+key,value)
        _OPERATORS[self]=(hashlib.sha256(self._claims).hexdigest(),canonical(self._identities))
    def __setattr__(self,*_):raise OperatorError('immutable operator custody')
    def require(self, *, action):
        _need(type(self)is OperatorContext and self in _OPERATORS and action in _ACTIONS,'issued operator/fixed action required')
        selection,identities=_OPERATORS[self]
        _need(type(self._verifier)is AuthorityVerifier and type(self._issuer)is RoleIssuer and
              self._issuer.verifier is self._verifier and self._issuer.domain=='authentic' and
              self._verifier._selection==self._claims and hashlib.sha256(self._claims).hexdigest()==selection and
              canonical(self._identities)==identities,'operator custody or root selection changed')
        constraints=json.loads(self._claims)['binding_constraints']
        _need(self._issuer.global_bindings==constraints,'operator issuer constraints changed')
        _need(set(json.loads(self._claims)['roles'])==_ROLES,'complete selected roles required')
        return _copy(self._identities)
    @property
    def package(self):return {**self._package,**{k:_copy(self._package[k])for k in('A','B','T','D','F','pins')}}
    @property
    def sections(self):return json.loads(self._sections)
    @property
    def keys(self):self.require(action='observe');return MappingProxyType(dict(self._keys))
    @property
    def intent(self):return json.loads(self._intent)
    @property
    def identities(self):return self.require(action='observe')
    @property
    def selection_constraints(self):self.require(action='observe');return _copy(json.loads(self._claims)['binding_constraints'])
    @property
    def policy(self):return self._policy
    @property
    def policy_document(self):return json.loads(self._policy_document)
    @property
    def verifier(self):return self._verifier
    @property
    def issuer(self):return self._issuer
    @property
    def ledger(self):return self._ledger
    @property
    def run_root(self):return self._run_root


def admit_operator(task_root, deployment_path, expected_deployment_sha256, review_path, policy_path,
                   *, other_reserve_bytes, output_path=None):
    package=d.load_package(task_root,read_cap=68*1024*1024)
    return _admit_package(package,deployment_path,expected_deployment_sha256,review_path,policy_path,
                          other_reserve_bytes=other_reserve_bytes,output_path=output_path)


def _admit_package(package,deployment_path,expected_deployment_sha256,review_path,policy_path,
                   *,other_reserve_bytes,output_path=None):
    D=d.validate_deployment(package['D'],configured_required=True) #before any external/key read
    d._sha(expected_deployment_sha256)
    _need(expected_deployment_sha256==package['pins']['D']['sha256'],'selected deployment differs from final source freeze')
    source_ledger=package['ledger']
    selected,rawD=d.read_json_pinned(d._absolute(deployment_path),
        {k:package['pins']['D'][k]for k in('bytes','sha256')},limit=2*1024*1024,ledger=source_ledger)
    _need(selected==D,'literal deployment body mismatch')
    trust_pin=D['section_manifests']['trust_anchor'];_identity_pin(trust_pin)
    bootstrap=d.ReadLedger(max(1,trust_pin['bytes']))
    trust,rawtrust=d.read_json_pinned(_path(package['root'],trust_pin['path']),trust_pin,
                                    limit=64*1024*1024,ledger=bootstrap)
    trust=validate_trust_anchor(trust)
    ledger=d.ReadLedger(trust['metadata_limits']['total_bytes'])
    ledger.reserve('source-bootstrap',source_ledger.reserved_bytes+bootstrap.reserved_bytes)
    ledger.actual_bytes=source_ledger.actual_bytes+bootstrap.actual_bytes
    #Explicit selected private files only. No key hash/body is recorded.
    keys={name:_read_secret(ref,ledger)for name,ref in trust['keys'].items()}
    review=d._safe_read(d._absolute(review_path),None,limit=min(32768,trust['metadata_limits']['file_bytes']),ledger=ledger)
    verifier=AuthorityVerifier(issuer_id=trust['issuer_id'],issuer_key=keys['issuer'],root_id=trust['root_id'],
        root_key=keys['root'],expected_design=package['pins']['T']['sha256'],root_selection=review)
    claims=json.loads(verifier._selection)
    _token(claims['selection_id']);_need(set(claims['roles'])==_ROLES and len(claims['roles'])==len(_ROLES),'all unique full-program roles')
    constraints=claims['binding_constraints'];_need(_ROOT_REQUIRED<=set(constraints),'missing required source/policy/intent constraints')
    capacity,_=_read_section(package,'capacity',ledger,trust['metadata_limits']['file_bytes'])
    _metadata_limits(capacity['metadata_limits'])
    ledger.cap=min(ledger.cap,capacity['metadata_limits']['total_bytes'])
    _need(ledger.reserved_bytes<=ledger.cap,'bootstrap already exceeds selected total metadata capacity')
    file_limit=min(trust['metadata_limits']['file_bytes'],capacity['metadata_limits']['file_bytes'])
    gates=_gate_bodies(claims,package,trust,ledger,file_limit)
    sections={'trust_anchor':trust,'capacity':capacity}
    for name in('numerical','corpus','host','provider','private_output'):
        sections[name],_=_read_section(package,name,ledger,file_limit)
    _validate_sections(sections)
    _need(D['allowed_policy_profile_digest']==D['section_manifests']['provider']['sha256'],
          'fixed provider profile must be exact raw provider L manifest identity')
    intent_path=d._absolute(trust['intent_root'])/(claims['selection_id']+'.json')
    rawI=d._safe_read(intent_path,None,limit=file_limit,ledger=ledger)
    _need(hashlib.sha256(rawI).hexdigest()==constraints['invocation_intent_digest'],'selected original invocation intent hash')
    intent=d._parse(rawI);_closed(intent,_INTENT_FIELDS,'signed invocation intent')
    _need(intent['schema']=='n073_invocation_intent_v1' and intent['selection_id']==claims['selection_id'],'intent selection identity')
    _token(intent['invocation_id'])
    output=d._absolute(intent['output_path']);parent=d._absolute(sections['private_output']['output_parent'])
    _need(output.parent==parent and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,255}',output.name) is not None
          and output.suffix=='.json','signed output must be a direct private submission JSON child')
    run_root=parent/('run-'+intent['invocation_id']);_need(output!=run_root,'submission/store root overlap')
    if output_path is not None:_need(d._absolute(output_path)==output,'caller output differs from signed intent')
    _need(type(other_reserve_bytes)is int and other_reserve_bytes>=0 and
          type(intent['other_reserve_bytes'])is int and intent['other_reserve_bytes']==other_reserve_bytes and
          other_reserve_bytes>=capacity['storage']['other_reserve_minimum_bytes'],'other-work reservation differs from original selection')
    policy_pin=_identity_pin(intent['policy_pin'],maximum=file_limit)
    expected_policy_path=_path(package['root'],policy_pin['path'])
    _need(d._absolute(policy_path)==expected_policy_path,'policy path differs from signed original intent')
    policy_doc,rawP=d.read_json_pinned(expected_policy_path,policy_pin,limit=file_limit,ledger=ledger)
    policy_doc=d.validate_policy(policy_doc)
    provider=sections['provider']
    _need(policy_doc['model_profile_id']==provider['model_profile_id'] and
          canonical(policy_doc['inference_policy'])==canonical(provider['inference_policy']),
          'candidate policy differs from independently fixed model/inference profile')
    policy=Policy(policy_doc['policy_id'],policy_doc['max_response_tokens'],
                  package['B']['files']['runtime/runner/policy.py']['sha256'],
                  InferencePolicy.from_dict(policy_doc['inference_policy']))
    identities={'accepted_parent_closure_digest':package['pins']['A']['sha256'],
                'code_closure_digest':package['pins']['B']['sha256'],'task_design_digest':package['pins']['T']['sha256'],
                'deployment_digest':package['pins']['D']['sha256'],'source_freeze_digest':package['pins']['F']['sha256'],
                'policy_file_digest':hashlib.sha256(rawP).hexdigest(),'invocation_intent_digest':hashlib.sha256(rawI).hexdigest(),
                'execution_selection_envelope_sha256':hashlib.sha256(review).hexdigest(),'runtime_policy_digest':policy.binding_digest}
    for name in _ROOT_REQUIRED:_need(constraints.get(name)==identities[name],'root selected binding mismatch: '+name)
    for name in('accepted_parent_closure_digest','code_closure_digest','task_design_digest','deployment_digest',
                'source_freeze_digest','runtime_policy_digest'):_need(intent[name]==identities[name],'intent upstream binding mismatch: '+name)
    issuer=RoleIssuer(verifier,global_bindings=constraints,domain='authentic')
    return OperatorContext(seal=_SEAL,package=package,sections=canonical(sections),keys=dict(keys),
        intent=canonical(intent),identities=identities,policy=policy,policy_document=canonical(policy_doc),
        verifier=verifier,issuer=issuer,ledger=ledger,claims=verifier._selection,gates=canonical(gates),run_root=str(run_root))


def _require_operator(operator, action):
    _need(type(operator)is OperatorContext,'actual independently issued OperatorContext required')
    return operator.require(action=action)


def claim_invocation(operator):
    """Only a real selected operator may create production attempt custody."""
    _require_operator(operator,'run')
    from .attempts import AttemptClaim,AttemptLimits
    private=operator.sections['private_output']
    return AttemptClaim.create(parent=private['output_parent'],
        invocation_id=operator.intent['invocation_id'],identities=operator.identities,
        limits=AttemptLimits(**private['attempt_limits']))


def _terminal_shape(claims, operator, manifest_pin):
    from .evidence import IDENTITY_KEYS, FINAL_STATUSES, validate_pin
    _closed(claims,_TERMINAL_FIELDS,'terminal custody claims')
    validate_pin(manifest_pin);_need(manifest_pin['file']=='run-manifest.json','fixed terminal manifest filename')
    _need(claims['schema']=='n073_terminal_custody_v2' and claims['domain']=='authentic' and
          claims['root_id']==operator.sections['trust_anchor']['root_id'] and
          claims['run_id']==operator.intent['invocation_id'] and claims['manifest_pin']==manifest_pin and
          claims['status']in FINAL_STATUSES,'terminal original invocation/manifest/status identity')
    _closed(claims['identities'],IDENTITY_KEYS,'complete terminal identities')
    for value in claims['identities'].values():d._sha(value)
    for name,value in operator.identities.items():
        _need(claims['identities'][name]==value,'terminal source/deployment/policy/intent binding differs')
    for name in('assessment_digest','plan_digest'):
        selected=operator.selection_constraints.get(name)
        _need(selected is None or selected==claims['identities'][name],'optional preselected '+name+' differs')
    for key in('artifact_index_digest','journal_head','close_receipt_digest'):d._sha(claims[key])
    _positive(claims['journal_events'],'actual closed journal events')
    from .attempts import AttemptLimits,verify_attempt_binding
    private=operator.sections['private_output']
    verify_attempt_binding(claims['attempt_binding'],parent=private['output_parent'],
        invocation_id=operator.intent['invocation_id'],identities=operator.identities,
        limits=AttemptLimits(**private['attempt_limits']),ledger=operator.ledger)
    return _copy(claims)


class VerifiedTerminal:
    __slots__=('_claims','_operator_digest','__weakref__')
    def __init__(self,claims=None,operator=None,seal=None):
        _need(seal is _SEAL,'VerifiedTerminal requires actual authenticated operator custody')
        object.__setattr__(self,'_claims',canonical(claims))
        object.__setattr__(self,'_operator_digest',digest(operator.identities))
        _TERMINALS[self]=(self._claims,self._operator_digest)
    def __setattr__(self,*_):raise OperatorError('immutable terminal custody')
    @property
    def claims(self):
        _need(type(self)is VerifiedTerminal and self in _TERMINALS and
              _TERMINALS[self]==(self._claims,self._operator_digest),'unissued/altered terminal custody')
        return json.loads(self._claims)
    def require(self, *, manifest_pin, run_id, identities):
        claims=self.claims
        _need(claims['manifest_pin']==manifest_pin and claims['run_id']==run_id and
              canonical(claims['identities'])==canonical(identities),'terminal consumer identity mismatch')
        return claims


def verify_terminal(envelope_bytes, *, operator, expected_manifest_pin):
    _require_operator(operator,'observe')
    _need(type(envelope_bytes)is bytes and 0<len(envelope_bytes)<=32768,'bounded exact terminal envelope')
    outer=d._parse(envelope_bytes);_closed(outer,('claims','mac'),'terminal envelope');d._sha(outer['mac'])
    expected=hmac.new(operator.keys['root'],canonical(outer['claims']),hashlib.sha256).hexdigest()
    _need(hmac.compare_digest(expected,outer['mac']),'terminal root MAC mismatch')
    claims=_terminal_shape(outer['claims'],operator,expected_manifest_pin)
    return VerifiedTerminal(claims,operator,_SEAL)


@contextmanager
def _reserved_evidence_replay(ledger, pins, limits):
    """Join original replay reservations to the whole invocation metadata cap.

    EvidenceMeter charges declared extents before opens, including failures.
    These are conservative logical charges, never measurements of physical I/O.
    A failed attempt preserves the full reservation and its original exception.
    """
    from .evidence import EvidenceMeter, EvidenceLimits, validate_pin
    _need(type(ledger) is d.ReadLedger and type(limits) is EvidenceLimits,
          'concrete source ledger and exact selected evidence limits required')
    _need(type(pins) is tuple and len(pins) > 0, 'explicit finite replay pin sequence')
    total = 0
    for pin in pins:
        validate_pin(pin)
        _need(pin['bytes'] <= limits.max_file_bytes, 'original replay single body cap')
        total += pin['bytes']
        _need(total <= limits.max_total_read_bytes, 'original replay exceeds evidence total cap')
    row = ledger.reserve('original-terminal-evidence-replay', total)
    row['accounting'] = 'conservative logical extents; not physical I/O'
    meter = EvidenceMeter(limits)
    try:
        yield meter
        _need(meter.read_bytes == total, 'original terminal replay did not consume complete planned extents')
        row['status'] = 'complete'
    except BaseException as error:
        row['status'] = 'failed'
        row['error_type'] = type(error).__name__
        raise
    finally:
        row['conservative_attempted_bytes'] = meter.read_bytes
        row['conservative_peak_workspace_bytes'] = meter.peak
        row['physical_read_bytes_measured'] = False


def issue_terminal(*, operator, manifest, manifest_pin, store, reference_engine, attempt):
    """Sign actual closed original state; never accept a caller close-success flag.

    No files are written here. The trusted owner durably writes the original
    manifest first and then writes these exact envelope bytes, preserving partial
    failures within its independently selected terminal_write_bytes budget.
    """
    _require_operator(operator,'issue_terminal')
    from .runtime.private_store.store import PrivateRunStore,verify_journal_frames
    from .runtime.runner.reference import ReferenceEngine
    from .runtime.core.plan import StudyPlan
    from .evidence import EvidenceLimits,EvidenceMeter,validate_manifest_shape,validate_pin,_open_root,_read,parse_json
    _need(type(store)is PrivateRunStore and type(reference_engine)is ReferenceEngine and
          reference_engine.store is store,'actual same reference engine/private store required')
    from .attempts import AttemptClaim
    _need(type(attempt) is AttemptClaim and attempt.invocation_id==operator.intent['invocation_id']
          and attempt.identities==operator.identities,'actual same consumed original invocation required')
    attempt_binding=attempt.binding()
    data=reference_engine.data;plan=data.plan
    _need(type(plan)is StudyPlan and data.domain=='authentic' and store.domain=='authentic',
          'actual authentic issued data/plan/store required')
    data.assessment.require_issued();data.catalogue.require_valid()
    _need(data.assessment.numeric_checks_passed and not data.assessment.issues and
          plan.assessment_digest==data.assessment.fingerprint and
          plan.source_contract_digest==operator.package['pins']['T']['sha256'],
          'actual admission and source-plan joins required')
    completion=reference_engine.assert_complete()
    _need(store.closed is True and store.failed is False and store.rootfd is None and store.started is True and
          not store.incidents and store.a.root==operator.run_root and store.a.run_id==operator.intent['invocation_id'],
          'genuine successful original private-store close required')
    close=store.status();close['receipt_digest']=digest(close)
    private=operator.sections['private_output'];limits=EvidenceLimits(**private['evidence_limits'])
    validate_pin(manifest_pin);validate_manifest_shape(manifest,limits)
    _need(manifest_pin['bytes']<=limits.max_manifest_bytes,'terminal manifest exceeds exact selected capacity')
    _need(canonical(manifest['store_close'])==canonical(close) and canonical(manifest['artifacts'])==canonical(store.artifacts)
          and manifest['run_id']==store.a.run_id and len(manifest['journal'])==store.journal_index,
          'manifest differs from actual closed writer state')
    expected_identities={**operator.identities,'plan_digest':plan.binding_digest,'assessment_digest':data.assessment.fingerprint}
    _need(manifest['identities']==expected_identities,'terminal actual source/admission/plan identities')
    for key in('plan_digest','assessment_digest'):
        bound=operator.selection_constraints.get(key)
        _need(bound is None or bound==expected_identities[key],'optional independently selected admission identity')
    _need(not manifest['diagnostics']['incidents'] and
          canonical(manifest['diagnostics']['partial_operations'])==canonical(store.partial_operations),
          'original failure/publication state must be retained')
    _need(manifest_pin['file']=='run-manifest.json','fixed original manifest file')
    locked_pin=manifest['artifacts'][manifest['roles']['full_locked_closure']]
    contract_pin=manifest['artifacts'][manifest['roles']['run_contract']]
    replay_pins=(manifest_pin,*manifest['journal'],{k:locked_pin[k]for k in('file','bytes','sha256')},
                 {k:contract_pin[k]for k in('file','bytes','sha256')})
    with _reserved_evidence_replay(operator.ledger,replay_pins,limits) as meter:
        fd,identity=_open_root(operator.run_root)
        try:
            _need(tuple(identity)==tuple(store.identity),'original closed root was replaced')
            with meter.workspace(128*manifest_pin['bytes']+8192):
                raw=_read(fd,manifest_pin,meter);read_manifest=parse_json(raw,limits=limits,newline=True)
                _need(canonical(read_manifest)==canonical(manifest),'written manifest differs from original writer value')
            class OriginalFrames:
                def __len__(self):return len(manifest['journal'])
                def __iter__(self):
                    for pin in manifest['journal']:
                        with meter.workspace(64*pin['bytes']+4096):yield _read(fd,pin,meter)
            verify_journal_frames(OriginalFrames(),run_id=store.a.run_id,domain='authentic',
                                  expected_head=store.head,expected_events=store.journal_index)
            key=manifest['roles']['full_locked_closure'];pin=manifest['artifacts'][key]
            with meter.workspace(64*pin['bytes']+4096):
                raw=_read(fd,{k:pin[k]for k in('file','bytes','sha256')},meter)
                locked=parse_json(raw,limits=limits,newline=False)
                _closed(locked,('plan_digest','closure_digest','reference_receipt','contexts'),'actual locked closure')
                _need(locked['plan_digest']==plan.binding_digest and
                      locked['closure_digest']==plan.assert_complete_closure(locked['contexts']) and
                      canonical(locked['reference_receipt'])==canonical(completion),'actual complete234/reference closure')
            with meter.workspace(64*contract_pin['bytes']+4096):
                raw=_read(fd,{k:contract_pin[k]for k in('file','bytes','sha256')},meter)
                contract=parse_json(raw,limits=limits,newline=False)
                _need(contract['schema']=='n073_run_contract_v2' and
                      contract['attempt_binding']==attempt_binding and
                      contract['reference_source_digest']==operator.package['pins']['B']['sha256'],
                      'original run contract must bind consumed attempt and complete B source')
            rootnow=os.fstat(fd);_need((rootnow.st_dev,rootnow.st_ino)==tuple(store.identity),'terminal root changed')
        finally:os.close(fd)
    claims={'schema':'n073_terminal_custody_v2','root_id':operator.sections['trust_anchor']['root_id'],
            'run_id':store.a.run_id,'domain':'authentic','manifest_pin':dict(manifest_pin),'identities':expected_identities,
            'artifact_index_digest':digest(manifest['artifacts']),'journal_events':store.journal_index,
            'journal_head':store.head,'close_receipt_digest':close['receipt_digest'],'status':manifest['status'],
            'attempt_binding':attempt_binding}
    _terminal_shape(claims,operator,manifest_pin)
    envelope=d.canonical_file_bytes({'claims':claims,'mac':hmac.new(operator.keys['root'],canonical(claims),hashlib.sha256).hexdigest()})
    _need(len(envelope)<=32768 and manifest_pin['bytes']+len(envelope)<=private['terminal_write_bytes'],
          'terminal envelope/manifest exceeds selected original write capacity')
    #Verify the exact produced envelope using the same independent-root consumer.
    verify_terminal(envelope,operator=operator,expected_manifest_pin=manifest_pin)
    return envelope


def _remaining_evidence_limits(original, consumed, started):
    from .evidence import EvidenceLimits
    from dataclasses import asdict
    values=asdict(original)
    values['max_total_read_bytes']-=consumed
    values['wall_seconds']=math.floor(original.wall_seconds-(time.monotonic()-started))
    _need(values['max_total_read_bytes']>0 and values['wall_seconds']>0,
          'original whole grading read/wall capacity exhausted')
    return EvidenceLimits(**values)


def load_grade_context(task_root, deployment_path, expected_deployment_sha256, review_path, submission_path,
                       *, other_reserve_bytes):
    """Authenticate original custody and score capability without neural arrays.

    A preliminary actual observation precedes score-envelope admission. Its read
    and elapsed-time costs reduce the residual limits passed to final grading;
    no count/time reset or caller-supplied score is accepted.
    """
    started=time.monotonic()
    package=d.load_package(task_root,read_cap=68*1024*1024)
    d.validate_deployment(package['D'],configured_required=True) #before submitted refs/keys
    initial=d.ReadLedger(32768)
    raw=d._safe_read(d._absolute(submission_path),None,limit=32768,ledger=initial)
    submission=d._parse(raw)
    _closed(submission,('schema','run_root','manifest_pin','terminal_pin','policy_pin'),'grading submission references')
    _need(submission['schema']=='n073_grade_submission_v1','grading submission schema')
    _identity_pin(submission['terminal_pin'],maximum=32768);_identity_pin(submission['policy_pin'])
    policy_path=_path(package['root'],submission['policy_pin']['path'])
    operator=_admit_package(package,deployment_path,expected_deployment_sha256,review_path,policy_path,
                            other_reserve_bytes=other_reserve_bytes,output_path=submission_path)
    operator.require(action='grade')
    _need(submission['run_root']==operator.run_root and
          submission['policy_pin']==operator.intent['policy_pin'],'submission original root/policy differs')
    expected_terminal=Path(operator.run_root)/'terminal-custody.json'
    _need(_path(package['root'],submission['terminal_pin']['path'])==expected_terminal,'fixed terminal custody filename')
    rawterminal=d.read_bytes_pinned(expected_terminal,submission['terminal_pin'],limit=32768,ledger=operator.ledger)
    terminal=verify_terminal(rawterminal,operator=operator,expected_manifest_pin=submission['manifest_pin'])
    from .corpus import load_catalogue,build_study_plan
    catalogue=load_catalogue(package['root'],package,ledger=operator.ledger)
    identities=terminal.claims['identities']
    plan=build_study_plan(catalogue,assessment_digest=identities['assessment_digest'],
                         source_contract_digest=package['pins']['T']['sha256'],context_key=operator.keys['context'])
    _need(plan.binding_digest==identities['plan_digest'],'reconstructed actual original plan differs')
    from .evidence import EvidenceLimits,load_evidence
    from .observe import observe_instance
    from .runtime import scoring
    original_limits=EvidenceLimits(**operator.sections['private_output']['evidence_limits'])
    consumed=operator.ledger.reserved_bytes+initial.reserved_bytes
    limits=_remaining_evidence_limits(original_limits,consumed,started)
    observation=observe_instance(run_root=operator.run_root,manifest_pin=submission['manifest_pin'],terminal=terminal,
                                 trusted_plan=plan,catalogue=catalogue,policy=operator.policy,limits=limits)
    consumed+=observation['read_receipt']['source_body_read_bytes']
    limits=_remaining_evidence_limits(original_limits,consumed,started)
    records=tuple(scoring.Record(r.case_id,r.person,r.label)for r in plan.records)
    constructions={r.case_id:r.construction for r in plan.records}
    with load_evidence(operator.run_root,submission['manifest_pin'],terminal=terminal,limits=limits) as bundle:
        m=bundle.manifest
        with bundle.artifact(m['roles']['run_contract']) as contract:
            _need(contract['identities']==identities and
                  contract['reference_source_digest']==package['pins']['B']['sha256'] and
                  contract['attempt_binding']==terminal.claims['attempt_binding'] and
                  contract['usage_extraction_source_digest']==package['B']['files']['transport_evidence.py']['sha256'],
                  'original independent reference/extractor source bindings differ')
        with bundle.artifact(m['roles']['full_locked_closure']) as locked:
            closure=plan.assert_complete_closure(locked['contexts'])
            _need(locked['plan_digest']==plan.binding_digest and locked['closure_digest']==closure,'original locked closure mismatch')
            bindings={'records_digest':scoring.records_digest(records),'closure_digest':closure,'construction_digest':digest(constructions)}
        with bundle.artifact(m['roles']['full_score_capability'],text=True) as envelope:
            score_authority=operator.verifier.verify(envelope,role='score',domain='authentic',bindings=bindings)
            original_claims=d._parse(envelope)['claims']
            _need(original_claims['context_id']=='full_locked_scoring' and
                  re.fullmatch('[0-9a-f]{16}',original_claims['nonce']) is not None and int(original_claims['nonce'],16)>0,
                  'stored score capability is not the actual full-scoring ordinal/context')
        consumed+=bundle.meter.read_bytes
    limits=_remaining_evidence_limits(original_limits,consumed,started)
    return {'operator':operator,'terminal':terminal,'run_root':operator.run_root,'manifest_pin':dict(submission['manifest_pin']),
            'trusted_plan':plan,'catalogue':catalogue,'policy':operator.policy,'score_authority':score_authority,
            'limits':limits,'observation':observation}
