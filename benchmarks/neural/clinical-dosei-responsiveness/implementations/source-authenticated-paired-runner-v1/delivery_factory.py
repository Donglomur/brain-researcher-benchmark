"""Ordered host-only delivery for the unchanged PairController.

No explicit live-adapter or file I/O occurs in this module's import statements
or factory constructor; Python's import machinery may itself load files. A later
__call__ may invoke the supplied admitted projector and Docker backend. The
outer driver MUST authenticate the complete public manifest, private indices,
member receipts, accepted observation rows, source proofs and every injected
module/callback before construction. It must keep those inputs stable while
this factory lives, impose resource/deadline guards and own final close().
A supplied digest string is a required binding, never module authentication.

The projector has the existing host.project_case(index, receipt, **options)
shape. The parent's checked projector additionally joins current output to the
accepted observation row, including array identity, coverage and source rows.
Fresh projection counters/receipt bytes need not equal a historical receipt.

The two public arms receive one identical public packet with independent
PairedCaseDelivery/TraceViewer instances. Private inputs and source evidence
bodies stay host-side; only an evidence binding is returned to PairController.
Python objects are not an isolation boundary. A code_backend_factory that
raises before returning an object owns cleanup of its incomplete construction.
"""
import copy
import hashlib
import json
import math
import re

CASES=7345
RECORDINGS=171
ARMS=('viewer_only','code_enabled')
OWNED_PROCESS_SHA256='afae111f8dec293391bbf077cd0d700e8061328d5541f5d116ade63c1cf7d219'
MAX_PACKET_BYTES=2097152
MAX_EVIDENCE_BYTES=4194304
COMMON_DISCLOSURE="{\"clinical_diagnosis\":false,\"condition\":\"native_marker_relative_30s_v1\",\"cross_case_feedback_or_memory\":false,\"dataset_label_training\":false,\"demonstrations\":[],\"display_connections\":\"drawing_geometry_only_not_inserted_samples\",\"display_policy\":\"dosei_observed_points_gap8_display_v1\",\"documented_nominal_EEG_channel_hz\":125,\"schema\":\"dosei_paired_workflow_disclosure_v1\",\"source_blank_cells\":\"unobserved_common_grid_cells_not_imputed\",\"source_hardware_endpoints\":\"retained_and_flagged_not_removed\",\"table_clock_hz\":250,\"target\":\"source_grouped_MOAAS_responsiveness_1_to_5\",\"task_specific_pretrained_detector\":false,\"time_relation\":\"retrospective_marker_association_not_verified_challenge_onset\"}".encode('ascii')
PUBLIC_FIELDS=frozenset(('schema','condition','case_id','channels','units','interval_ms',
    'relative_time_ms','values_uv','observation_mask','source_endpoint_mask','coverage'))
CODE_REQUIRED=frozenset(('profile_bytes','staging_parent','docker_executable','docker_socket',
    'policy_api','command_api','call_wall_seconds','max_calls'))
CODE_OPTIONAL=frozenset(('command_runner',))


class DeliveryFactoryRefusal(ValueError):
    pass


def require(value,message):
    if not value:raise DeliveryFactoryRefusal(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'exact SHA256 string required')
    return value


def binding(raw):
    require(type(raw) is bytes,'immutable evidence bytes required')
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def artifact(value):
    require(type(value) is dict and set(value)=={'bytes','sha256'} and
        type(value['bytes']) is int and 0<=value['bytes']<=MAX_EVIDENCE_BYTES,'exact bounded evidence binding')
    return {'bytes':value['bytes'],'sha256':digest(value['sha256'])}


def public_binding(value):
    require(type(value) is dict and set(value)=={'case_id','observation_sha256'},'exact public manifest fields')
    return {k:digest(value[k]) for k in ('case_id','observation_sha256')}


def preferred(primary,secondary):
    # An interruption cannot disappear behind an ordinary diagnostic failure.
    if primary is None or isinstance(primary,Exception) and not isinstance(secondary,Exception):return secondary
    return primary


class _ArmBackend:
    """Only these methods belong at the participant-interface boundary."""
    def __init__(self,owner,public,arm,delivery,code,source_ref):
        self._owner=owner;self._public=dict(public);self._arm=arm
        self._delivery=delivery;self._code=code;self._source_ref=dict(source_ref)
        self._closed=False;self._close_ref=None

    def _usable(self):
        require(not self._closed and not self._owner._closed and not self._owner._poisoned,
            'delivery capability is closed or poisoned')

    def viewer_action(self,command):
        self._usable()
        try:
            raw=self._delivery.viewer_action(command)
            require(type(raw) is bytes and 0<len(raw)<=MAX_PACKET_BYTES,'bounded complete viewer bytes')
            return raw
        except BaseException:
            self._owner._poisoned=True
            raise

    def code_observation(self):
        self._usable();require(self._arm=='code_enabled','viewer-only capability has no numerical observation')
        try:
            raw=self._code.code_observation()
            require(type(raw) is bytes and raw==self._delivery.code_observation(),'code observation changed')
            return raw
        except BaseException:
            self._owner._poisoned=True
            raise

    def run_tool(self,name,program):
        self._usable();require(self._arm=='code_enabled','viewer-only capability has no code execution')
        # The unchanged backend distinguishes participant errors and host faults.
        # A backend error is left available to controller attribution, then close.
        try:return self._code.run_tool(name,program)
        except BaseException:
            self._owner._poisoned=True
            raise

    def close(self):
        if self._closed:
            require(self._close_ref is not None,'prior delivery closure was incomplete')
            return dict(self._close_ref)
        # Terminal before any external callback, including failed custody.
        self._closed=True
        code=self._code;self._code=None;self._delivery=None
        problem=None;code_ref=None
        if code is not None:
            try:code_ref=artifact(code.close())
            except BaseException as error:problem=error
        value={'schema':'dosei_ordered_delivery_arm_close_v1','binding':self._public,
            'arm':self._arm,'source_projection':self._source_ref,'code_close':code_ref,
            'complete':problem is None,'failure_type':None if problem is None else type(problem).__name__,
            'capabilities_closed':True,'isolation_proven_by_this_object':False}
        try:retained=self._owner._store('paired_delivery_close',canonical(value))
        except BaseException as error:problem=preferred(problem,error)
        if problem is not None:
            self._owner._poisoned=True;self._owner._cache=None
            raise problem
        self._close_ref=dict(retained)
        try:self._owner._closed_arm(self)
        except BaseException:
            self._owner._poisoned=True;self._owner._cache=None;self._close_ref=None
            raise
        return dict(self._close_ref)


class OrderedDeliveryFactory:
    """Full-population admission is supplied; this object enforces delivery order.

    evidence_sink(kind, raw_bytes) must durably retain exact original bytes and
    return {bytes, sha256}. context_ids is one preselected unique code context ID
    per public case, in public-manifest order. code_options has the fixed Docker
    options declared by CODE_REQUIRED, optionally command_runner. The factory
    supplies every case, viewer, recorder, context and process API argument.
    """
    def __init__(self,public_manifest,private_indices,member_receipts,*,project_case,
                 projection_options,delivery_module,viewer_module,code_backend_factory,
                 code_options,context_ids,owned_process_v2,owned_process_sha256,evidence_sink):
        require(type(public_manifest) is list and len(public_manifest)==CASES,'complete 7345-case manifest')
        manifest=[public_binding(v) for v in public_manifest]
        ids=[v['case_id'] for v in manifest]
        require(ids==sorted(ids) and len(set(ids))==CASES,'strict fixed public case order')
        require(type(private_indices) is dict and set(private_indices)==set(ids),'complete private case mapping')
        require(type(member_receipts) is dict and len(member_receipts)==RECORDINGS,'complete 171-record mapping')
        records=set();joins=set();indices={}
        for case_id in ids:
            index=private_indices[case_id]
            require(type(index) is dict and index.get('schema')=='dosei_private_window_index_v1' and
                index.get('visibility')=='evaluator_private' and index.get('case_id')==case_id and
                type(index.get('evaluator')) is dict,'private index identity')
            require(all(type(index.get(k)) is str for k in ('schema','visibility','case_id')),
                'exact private index identity strings')
            e=index['evaluator'];rid=e.get('recording_id');row=e.get('source_row')
            require(type(rid) is str and re.fullmatch('[1-9][0-9]{0,8}',rid) and type(row) is int and 0<=row<4000000 and
                e.get('case_id')==case_id and e.get('source_event_id')==f'recording:{rid}/row:{row}',
                'private source join')
            require(type(e.get('case_id')) is str and type(e.get('source_event_id')) is str,
                'exact private source identity strings')
            require((rid,row) not in joins,'duplicate private source join')
            joins.add((rid,row));records.add(rid);indices[case_id]=index
        require(records==set(member_receipts) and len(records)==RECORDINGS,'recording population differs')
        for rid,receipt in member_receipts.items():
            require(type(receipt) is dict and receipt.get('schema')=='dosei_full_eeg_member_success_v1' and
                receipt.get('recording_id')==rid and receipt.get('status')=='succeeded' and
                receipt.get('complete_source_EOF_CRC_SHA') is True and
                receipt.get('all_three_streams_closed_and_size_stat_checked') is True,'complete member receipt scope')
            require(all(type(receipt.get(k)) is str for k in ('schema','recording_id','status')),
                'exact member receipt identity strings')
        require(type(context_ids) in (list,tuple) and len(context_ids)==CASES,'one code context per case')
        contexts=tuple(digest(x) for x in context_ids)
        require(len(set(contexts))==CASES,'fresh unique code context identifiers')
        require(callable(project_case) and type(projection_options) is dict and
            not {'index','receipt'}&set(projection_options),'explicit projection API')
        require(callable(getattr(delivery_module,'PairedCaseDelivery',None)) and
            canonical(delivery_module.DISCLOSURE)==COMMON_DISCLOSURE and
            callable(getattr(viewer_module,'TraceViewer',None)) and
            callable(getattr(viewer_module,'validate_packet',None)),'fixed common delivery definition')
        require(callable(code_backend_factory) and type(code_options) is dict and
            CODE_REQUIRED<=set(code_options)<=CODE_REQUIRED|CODE_OPTIONAL,'exact fixed code options')
        require(type(code_options['profile_bytes']) is bytes and 0<len(code_options['profile_bytes'])<=65536,
            'bounded authenticated runtime profile bytes')
        for key in ('staging_parent','docker_executable','docker_socket'):
            require(type(code_options[key]) is str and code_options[key].startswith('/') and
                '\x00' not in code_options[key],'explicit host paths')
        wall=code_options['call_wall_seconds']
        require(type(wall) in (int,float) and math.isfinite(wall) and 0<wall<=60 and
            type(code_options['max_calls']) is int and 1<=code_options['max_calls']<=128,'frozen code budget')
        require(digest(owned_process_sha256)==OWNED_PROCESS_SHA256 and
            callable(getattr(owned_process_v2,'OwnedProcess',None)),'explicit authenticated owned_process_v2 binding')
        require(callable(evidence_sink),'trusted evidence custody required')
        self._manifest=manifest;self._indices=indices;self._receipts=dict(member_receipts)
        self._project=project_case;self._projection_options=dict(projection_options)
        self._delivery_module=delivery_module;self._viewer_module=viewer_module
        self._code_factory=code_backend_factory;self._code_options=dict(code_options)
        self._contexts=contexts;self._owned=owned_process_v2;self._sink=evidence_sink
        self._position=0;self._arm=0;self._active=None;self._cache=None
        self._projected=0;self._completed_arms=0;self._viewer_instances=0
        self._poisoned=False;self._closed=False;self._close_ref=None;self._setup_cleanup_unknown=False

    def _store(self,kind,raw):
        require(type(kind) is str and re.fullmatch('[a-z][a-z0-9_]{0,47}',kind) and
            type(raw) is bytes and len(raw)<=MAX_EVIDENCE_BYTES,'bounded original custody request')
        retained=artifact(self._sink(kind,raw))
        require(retained==binding(raw),'custody returned different original')
        return retained

    def _closed_arm(self,backend):
        require(self._active is backend,'closure owner differs')
        self._active=None;self._completed_arms+=1
        if self._arm==0:self._arm=1
        else:self._arm=0;self._position+=1;self._cache=None

    def __call__(self,public,arm):
        code=None;delivery=None;code_attempted=False
        try:
            require(not self._closed and not self._poisoned and self._active is None and self._position<CASES,
                'factory closed, poisoned, active or exhausted')
            expected=self._manifest[self._position]
            require(public_binding(public)==expected and type(arm) is str and arm==ARMS[self._arm],
                'fixed viewer/closed/code/closed population order')
            if self._arm==0:
                index=self._indices[expected['case_id']];rid=index['evaluator']['recording_id']
                result=self._project(index,self._receipts[rid],**self._projection_options)
                require(type(result) is tuple and len(result)==2,'projector returns packet and private receipt')
                packet,evidence=result
                require(type(packet) is dict and set(packet)==PUBLIC_FIELDS,'public packet allowlist')
                self._viewer_module.validate_packet(packet)
                raw=canonical(packet)
                require(0<len(raw)<=MAX_PACKET_BYTES and packet['case_id']==expected['case_id'] and
                    binding(raw)['sha256']==expected['observation_sha256'],'projected public observation differs')
                require(type(evidence) is dict and evidence.get('schema')=='dosei_host_slice_projection_receipt_v1' and
                    evidence.get('visibility')=='evaluator_private' and evidence.get('case_id')==expected['case_id'] and
                    evidence.get('observation_sha256')==expected['observation_sha256'] and
                    type(evidence.get('observation_bytes')) is int and evidence['observation_bytes']==len(raw) and
                    type(evidence.get('source_rows_read')) is int and
                    evidence['source_rows_read']==packet['coverage']['row_count'],'fresh projection receipt join')
                digest(evidence.get('array_identity_binding_sha256'))
                eraw=canonical(evidence);require(len(eraw)<=65536,'bounded private projection receipt')
                source_ref=self._store('paired_projection',eraw)
                # Detach all per-case public/render inputs from caller aliases.
                self._cache=(raw,json.loads(eraw),source_ref);self._projected+=1
            require(self._cache is not None,'one matched projection per case')
            raw,evidence,source_ref=self._cache
            delivery=self._delivery_module.PairedCaseDelivery(json.loads(raw),copy.deepcopy(evidence),viewer=self._viewer_module)
            self._viewer_instances+=1
            require(delivery.public_binding()==expected and delivery.code_observation()==raw and
                canonical(delivery.disclosure())==COMMON_DISCLOSURE,'matched arm delivery/disclosure')
            if arm=='code_enabled':
                options=dict(self._code_options)
                options.update(public_binding=dict(expected),observation_bytes=raw,viewer=delivery.viewer_action,
                    context_id=self._contexts[self._position],recorder=self._store,process_api=self._owned)
                code_attempted=True
                code=self._code_factory(**options)
                require(all(callable(getattr(code,name,None)) for name in ('code_observation','viewer_action','run_tool','close')),
                    'owned code backend capability contract')
                observed=code.code_observation()
                require(type(observed) is bytes and observed==raw,'code backend observation differs')
            self._store('paired_delivery_setup',canonical({'schema':'dosei_ordered_delivery_setup_v1',
                'binding':expected,'arm':arm,'source_projection':source_ref,
                'disclosure':binding(COMMON_DISCLOSURE),
                'code_context_id':self._contexts[self._position] if arm=='code_enabled' else None,
                'participant_isolation_proven':False}))
            backend=_ArmBackend(self,expected,arm,delivery,code,source_ref)
            self._active=backend
            return {'backend':backend,'common_disclosure':COMMON_DISCLOSURE,'source_evidence':dict(source_ref)}
        except BaseException as original:
            self._poisoned=True;self._cache=None
            problem=original;cleanup_complete=not code_attempted
            if code is not None:
                try:artifact(code.close());cleanup_complete=True
                except BaseException as error:problem=preferred(problem,error)
            if not cleanup_complete:self._setup_cleanup_unknown=True
            try:self._store('paired_delivery_setup_failure',canonical({'schema':'dosei_ordered_delivery_setup_failure_v1',
                'failure_type':type(original).__name__,'cleanup_complete':cleanup_complete,
                'code_factory_owns_unreturned_constructor_cleanup':True}))
            except BaseException as error:problem=preferred(problem,error)
            raise problem

    def summary(self):
        """Detached host counters; never source joins, labels or mutable inputs."""
        return {'completed_cases':self._position,'completed_arms':self._completed_arms,
            'facade_closures':self._completed_arms,'projected_cases':self._projected,
            'viewer_instances':self._viewer_instances,'cache_empty':self._cache is None,
            'active_backend':self._active is not None,'closed':self._closed,'poisoned':self._poisoned,
            'setup_cleanup_unconfirmed':self._setup_cleanup_unknown,
            'all_cases_completed':self._position==CASES and self._arm==0 and not self._poisoned}

    def close(self):
        if self._closed:
            require(self._close_ref is not None,'factory closure previously incomplete')
            return dict(self._close_ref)
        problem=None
        try:
            if self._active is not None:self._active.close()
        except BaseException as error:problem=error
        if problem is None and self._setup_cleanup_unknown:
            problem=DeliveryFactoryRefusal('earlier setup cleanup remains unconfirmed')
        self._closed=True;self._cache=None
        value={'schema':'dosei_ordered_delivery_factory_close_v1','complete_cleanup':problem is None,
            **self.summary(),'failure_type':None if problem is None else type(problem).__name__}
        try:retained=self._store('paired_factory_close',canonical(value))
        except BaseException as error:problem=preferred(problem,error)
        if problem is not None:self._poisoned=True;raise problem
        self._close_ref=dict(retained);return dict(retained)
