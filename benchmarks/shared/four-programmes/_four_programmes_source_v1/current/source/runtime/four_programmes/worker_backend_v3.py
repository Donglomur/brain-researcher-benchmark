"""Concrete V3 preparation and actual granted-effect consumers.

This is not the complete server/HTTP/agent MAIN. It cannot select an absent
per-operation resource recipe, produce native qualification, or create a grant.
"""
from .common import need
from .worker_context_v3 import WorkerContextProxy
from .worker_meter_v3 import WorkerArmMeterProxy,WorkerEffectAttempt
from .worker_publication_v3 import WorkerCanonicalPublisher
from .worker_channel_v3 import require_capture
from .precommit_records import RECORDS,validate_type

_ADMISSION=object()
_KINDS=('WorkerLaunchAck','DevelopmentRequest','InitialStatePreparation',
        'WorkspaceObservation','LocalBackendProfile','LocalArtifactSelection',
        'NativeArtifactRootSelectionV1','NativeArtifactRootBundleV1','NativeContextPolicyV2')

def _metadata_floor(captures):
    # Logical prepayment convention, not a Python allocator/RSS or CPU estimate.
    # Complete immutable captured bytes are accounted, including all root rows.
    extent=sum(len(c.raw) for c in captures)
    return {'work_units':128*extent+8192,'retained_bytes':32*extent+8192}

class WorkerBootstrapAdmissionV3:
    """Finite same-context ownership selection; no native/source requalification."""
    def __init__(self,token,context,captures,roots):
        need(token is _ADMISSION,'fixed V3 preparation factory only')
        self.context=context;self.captures=captures;self.roots=roots
        self.backend=None;self.decoded=None;self.root_rows=None
    @classmethod
    def from_context(cls,context):
        need(type(context)is WorkerContextProxy and context.channel.context is context and
             context.activated and not context.poisoned and context.local_raw_first is None and
             not context.channel.poisoned and context.channel.raw_first is None and context.backend is None and
             type(context.meter)is WorkerArmMeterProxy and context.meter.context is context and
             context.meter.local_raw_first is None and
             type(context.publisher)is WorkerCanonicalPublisher and context.publisher.context is context and
             context.publisher.raw_first is None,
             'actual earlier complete source-owned bootstrap and original proxy pair')
        # Selecting retained objects does not reparse their bodies. All extended
        # validation/decoding below occurs inside an earlier real effect grant.
        captures=tuple(context.bootstrap(k) for k in _KINDS)
        roots=tuple(c for c in context.bootstrap_objects if c.kind=='NativeRootObservationV1')
        need(1<=len(roots)<=5,'full original bounded root roster')
        return cls(_ADMISSION,context,captures,roots)
    def require_original(self):
        b=self.backend;c=self.context
        need(type(b)is WorkerBackendOwnerV3 and c.backend is b and b.admission is self and
             c.meter is b.meter and c.publisher is b.publisher,
             'same registered original V3 preparation owner')
        return self

class WorkerBackendOwnerV3:
    """Registered before the first new effect; owns real partial failures."""
    def __init__(self,admission):
        need(type(admission)is WorkerBootstrapAdmissionV3 and admission.backend is None and
             admission.context.backend is None,'one concrete backend per original context')
        self.admission=admission;self.context=admission.context
        self.meter=self.context.meter;self.publisher=self.context.publisher
        self.base=None;self.base_entered=False;self.base_effect=None;self.base_body=None
        self.state='bootstrap_selected';self.raw_first=None;self.secondaries=[]
        self.io=None;self.artifact_attempts={};self.artifact_captures={}
        self.cleanup_entered=False;self.cleanup_complete=False
        admission.backend=self;self.context.backend=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((site,error))
        self.state='failed';self.context.retain(error)
    def _effect(self,effect,site,prior):
        self.admission.require_original()
        need(self.raw_first is None and not self.context.poisoned and self.context.local_raw_first is None and
             not self.context.channel.poisoned and self.context.channel.raw_first is None and
             self.meter.local_raw_first is None and self.publisher.raw_first is None,
             'no ordinary native consumer after an original local/channel/meter/publication failure')
        need(type(effect)is WorkerEffectAttempt and effect.meter is self.meter and
             self.meter.current_effect is effect and effect.site==site and
             effect.stage=='initialization' and effect.deadline==self.context.deadline('initialization') and
             effect.grant is not None and not effect.entered and not effect.finished and not effect.reported and
             len(effect.prior_captures)==len(prior) and
             all(a is b for a,b in zip(effect.prior_captures,prior)),
             'actual original complete same-context grant and exact ordered prior owners')
        effect.require_current()
        need(effect.maximum['cpu_ns']>0 and effect.maximum['wall_ns']>0 and
             effect.maximum['write_bytes']==0 and effect.maximum['process_starts']==0,
             'existing positive physical reservation, no new process/write opportunity')
        return effect
    def base_effect_operands_v3(self):
        self.admission.require_original()
        return self.admission.captures+self.admission.roots
    def capture_base_v3(self,effect):
        need(not self.base_entered and self.base is None and self.raw_first is None,
             'one actual base capture attempt including failure')
        self.base_entered=True;self.base_effect=effect
        try:
            prior=self.base_effect_operands_v3();self._effect(effect,'local_parse',prior)
            floor=_metadata_floor(prior)
            need(effect.maximum['read_bytes']==0 and all(effect.maximum[k]>=v for k,v in floor.items()),
                 'whole metadata/hash/decode/copy bound before any extended intake')
            effect.enter()
            for c in prior:require_capture(c,self.context)
            decoded={k:c.body for k,c in zip(_KINDS,self.admission.captures)}
            a=decoded['WorkerLaunchAck'];r=decoded['DevelopmentRequest'];p=decoded['InitialStatePreparation']
            w=decoded['WorkspaceObservation'];f=decoded['LocalBackendProfile'];t=decoded['LocalArtifactSelection']
            selection=decoded['NativeArtifactRootSelectionV1'];bundle=decoded['NativeArtifactRootBundleV1']
            c=self.context.context_identity;caps=dict(zip(_KINDS,self.admission.captures))
            need(a['condition']==r['condition']==p['condition']==w['condition']==c['condition'] and
                 a['pair_id']==p['pair_id']==w['pair_id']==c['pair_id'] and a['nonce']==c['launch_nonce'],
                 'same actual original arm/pair/nonce')
            need(a['request']==caps['DevelopmentRequest'].pin and p['workspace']==caps['WorkspaceObservation'].pin and
                 p['backend_profile']==caps['LocalBackendProfile'].pin and
                 p['artifact_selection']==f['artifact_selection']==caps['LocalArtifactSelection'].pin and
                 selection['artifact_selection']==caps['LocalArtifactSelection'].pin and
                 selection['backend_profile']==caps['LocalBackendProfile'].pin and
                 bundle['selection']==caps['NativeArtifactRootSelectionV1'].pin and
                 bundle['roots']==[x.pin for x in self.admission.roots],
                 'actual complete original capture/source/root joins')
            need(decoded['NativeContextPolicyV2']['original_source_admission']==a['source_admission']==c['source_admission'],
                 'same earlier actual source admission')
            J=self.context.deadline('initialization');G=self.context.deadline('generation');R=self.context.deadline('shutdown')
            S=a['original_start_ns'];schedule=r['schedule'];limits=f['limits']
            need(R==S+schedule['duration_ns'] and G==R-limits['shutdown_duration_ns'] and
                 J==min(S+limits['initialization_duration_ns'],G) and
                 schedule['earliest_launch_ns']<=S<=schedule['latest_launch_ns'] and
                 R<=schedule['common_cutoff_ns']<=a['run_deadline_ns'] and
                 limits['initialization_duration_ns']+limits['shutdown_duration_ns']<schedule['duration_ns'],
                 'unchanged original S/J/G/R with full shutdown reservation')
            root_rows=tuple(x.body for x in self.admission.roots)
            need(len({x['root_id'] for x in root_rows})==len(root_rows), 'complete unique original root identities')
            self.admission.decoded=decoded;self.admission.root_rows=root_rows
            effect.finish();self.meter.observe_effect(effect)
            body={'schema':RECORDS['BackendAttemptBase']['schema_literal'],'condition':c['condition'],
                  'pair_id':c['pair_id'],'nonce':c['launch_nonce'],'worker_attempt':a['original_attempt'],
                  'worker_launch_ack':caps['WorkerLaunchAck'].pin,'request':caps['DevelopmentRequest'].pin,
                  'preparation':caps['InitialStatePreparation'].pin,'workspace':caps['WorkspaceObservation'].pin,
                  'profile':caps['LocalBackendProfile'].pin,'initialization_deadline_ns':J,
                  'generation_deadline_ns':G,'shutdown_deadline_ns':R,'spawn_state':'not_attempted',
                  'cost_prefix':self.meter.acknowledged_prefix()}
            self.base_body=body
            self.base=self.publisher.capture_fixed_site('base',body,ordinal=0,stage='initialization')
            self.state='prepared';return self.base
        except BaseException as error:
            if (type(effect)is WorkerEffectAttempt and effect.meter is self.meter and
                    self.meter.current_effect is effect and effect.grant is not None and not effect.reported):
                try:
                    if effect.raw_first is None:effect.fail(error,())
                    self.meter.observe_effect(effect)
                except BaseException as later:
                    if later is not error:self.secondaries.append(('base_effect_observation',later))
            self.retain(error,'capture_base');raise
    def artifact_effect_operands_v3(self,role):
        self.admission.require_original();need(self.base is not None and self.raw_first is None,'actual prepared base')
        d=self.admission.decoded;selection=d['NativeArtifactRootSelectionV1']
        rows=[x for x in selection['roles'] if x['role']==role];need(len(rows)==1,'selected original five-role member')
        roots=[x for x,body in zip(self.admission.roots,self.admission.root_rows) if body['root_id']==rows[0]['root_id']]
        need(len(roots)==1,'one exact original root observation')
        return (self.base,self.admission.captures[_KINDS.index('NativeArtifactRootSelectionV1')],roots[0])
    def observe_artifact_v3(self,role,effect):
        from .worker_native_io_v3 import WorkerNativeIOV3
        need(role not in self.artifact_attempts and self.raw_first is None,'one actual original artifact role attempt')
        self.artifact_attempts[role]=None
        try:
            prior=self.artifact_effect_operands_v3(role);self._effect(effect,'artifact_read',prior)
            if self.io is None:self.io=WorkerNativeIOV3(self)
            attempt=self.io.read_selected_artifact_v3(role,effect,prior)
            self.artifact_attempts[role]=attempt
            need(attempt.complete and attempt.closed and attempt.raw_first is None and effect.reported,
                 'actual complete observed artifact and acknowledged original effect')
            s=attempt.file_stat;identity={'schema':RECORDS['OwnedPathIdentity']['schema_literal'],
                 'device':s.st_dev,'inode':s.st_ino,'kind':'regular_file','mode':s.st_mode,'uid':s.st_uid,
                 'relative_path':'/'.join(attempt.relative_components),
                 'parent_handle_ordinal':attempt.parent_ordinal,'observed_ns':attempt.observed_ns}
            validate_type('OwnedPathIdentity',identity)
            body={'schema':RECORDS['ArtifactObservation']['schema_literal'],'condition':self.context.context_identity['condition'],
                 'attempt':self.base.pin,'role':role,'selected':attempt.selected,'observed_bytes':attempt.count,
                 'observed_sha256':attempt.digest,'filesystem_identity':identity,'readonly':True,
                 'observed_ns':attempt.observed_ns,'cost_prefix':self.meter.acknowledged_prefix()}
            ordinal=('server_executable','model_gguf','template','tokenizer_source','renderer_source').index(role)
            cap=self.publisher.capture_fixed_site('artifact',body,ordinal=ordinal,stage='initialization')
            self.artifact_captures[role]=cap;return cap
        except BaseException as error:self.retain(error,'artifact');raise
    def close_preparation_once_v3(self):
        """Close retained descriptors even after budget/channel failure; not server closure."""
        if self.cleanup_entered:return self.cleanup_complete
        self.cleanup_entered=True
        self.cleanup_complete=True if self.io is None else self.io.close_all_once_v3()
        return self.cleanup_complete
