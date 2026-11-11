"""Actual bounded lifecycle/capture callers; native leaves explicitly unavailable.

The three snapshots are evidence of this live handle, never authority to recreate
it. No participant dict or callback substitutes for H/native ownership. Costs
stay with the original EarlyResources arm; cleanup never creates a new share.
"""
from .common import need, same, pin
from .backend_json import parse
from .backend_capture import CapturedRecord, CanonicalPublisher
from .early_resources import EarlyResources
from .precommit_records import validate_type, RECORDS
from .backend_protocol import request_wire, parse_response
from .backend_native_boundary import (HWorkerLaunchAdmission, HBackendAdmission,
    BackendNativeOwner, InitializationEvidence, CompletionEvidence)


def _body(kind, **fields):
    return {'schema': RECORDS[kind]['schema_literal'], **fields}


class BackendAttemptHandle:
    """Registered before the first clock/cost/capture effect; never reconstructed."""
    def __init__(self, admission, publisher):
        need(type(admission) is HWorkerLaunchAdmission, 'actual H worker capability')
        need(type(publisher) is CanonicalPublisher and type(admission.owner) is EarlyResources,
             'closed original owner/publication types')
        need(publisher.owner is admission.owner and publisher.condition == admission.condition and
             publisher.meter is admission.owner.arms[admission.condition], 'same original arm')
        need(not admission.consumed and admission.backend_handle is None, 'one backend per original H launch')
        need(type(admission.native) is BackendNativeOwner, 'fixed native boundary, no callback/provider')
        need(admission.native.admission is admission, 'same live original native owner, never another arm handle')
        self.admission=admission; self.publisher=publisher; self.owner=admission.owner
        self.condition=admission.condition; self.meter=publisher.meter; self.native=admission.native
        self.raw_first=None; self.raw_secondaries=[]; self.first_error_capture=None
        self.base=None; self.base_body=None; self.snapshots=[]; self.snapshot_attempts=[]
        self.snapshot_poisoned=False; self.spawn_state='not_attempted'; self.state='not_prepared'
        self.identity=None; self.identity_capture=None; self.group_capture=None
        self.initialization=None; self.source_proof=None; self.host_admission=None; self.artifact_selection=None
        self.pending=None; self.requests=[]; self.exchanges=[]; self.agent_done=False
        self.close_attempted=False; self.purpose=None; self.cleanup_entered=[]; self.cleanup={}
        self.closure=None; self.closure_qualified=False; self.initialization_entered=False; self.host_admission_entered=False
        self.ack_body=None; self.profile_body=None; self.J=None; self.G=None; self.R=None
        # No clock, charge, decode or native operation occurred above.
        admission.backend_handle=self; admission.consumed=True

    def retain(self, error, site):
        if self.raw_first is None: self.raw_first=error
        elif error is not self.raw_first: self.raw_secondaries.append(error)
        self.state='failed'
        try: self.owner.parent.retain(error, 'development_observe', 'observation_failure', site)
        except BaseException as secondary:
            if secondary is not self.raw_first: self.raw_secondaries.append(secondary)

    def read_capture(self, capture, kind):
        need(type(capture) is CapturedRecord and capture.owner is self.owner and
             capture.kind == kind and capture._attempt.complete is capture,
             'actual completed same-owner typed capture')
        raw=capture.raw
        need(type(raw) is bytes and len(raw)<=self.publisher.maximum_bytes,
             'selected original complete capture extent')
        # Decode/copy work and retained allocation are admitted before parsing.
        self.meter.charge('work_units',len(raw)*64+4096)
        self.meter.charge('retained_bytes',len(raw))
        need(pin(raw)=={k:capture.pin[k] for k in ('bytes','sha256')}, 'exact original capture bytes')
        body=parse(raw,len(raw),maximum_depth=self.publisher.maximum_depth,
                   maximum_members=len(raw),maximum_string_bytes=len(raw))
        validate_type(kind,body)
        return body

    def _live(self, deadline):
        need(self.raw_first is None and not self.close_attempted,'no failed/closed continuation')
        self.meter.check()
        now=self.native.now_ns(self)
        need(type(now) is int and self.ack_body['original_start_ns']<=now<deadline,
             'same original clock and unrenewed stage cutoff')
        return now

    def unknown_native(self):
        # Failed effects are not measured zero; keep the original reservation.
        for dimension in ('read_bytes','write_bytes','work_units','process_starts','cpu_ns','wall_ns','retained_bytes'):
            try:self.owner.parent.unknown.add(dimension)
            except BaseException as error:self.retain(error,'unknown_native_projection')

    def _reserve_record(self):
        # Conservative reservation for a new finite wire projection before its
        # construction. Publisher additionally charges encoding/write/readback.
        # These are original-arm debits, not added capacity or measured usage.
        self.meter.charge('retained_bytes',self.publisher.maximum_bytes)
        self.meter.charge('work_units',self.publisher.maximum_bytes)

    def capture_base_v1(self):
        try:
            need(self.base is None and self.state=='not_prepared', 'one original base attempt')
            self.native.assert_worker_admission(self.admission)
            a=self.read_capture(self.admission.ack,'WorkerLaunchAck')
            q=self.read_capture(self.admission.request,'DevelopmentRequest')
            p=self.read_capture(self.admission.preparation,'InitialStatePreparation')
            w=self.read_capture(self.admission.workspace,'WorkspaceObservation')
            f=self.read_capture(self.admission.profile,'LocalBackendProfile')
            need(a['condition']==q['condition']==p['condition']==w['condition']==self.condition,
                 'all original arm identities agree')
            need(a['pair_id']==p['pair_id']==w['pair_id'] and
                 same(a['request'],self.admission.request.pin) and
                 same(p['workspace'],self.admission.workspace.pin) and
                 same(p['backend_profile'],self.admission.profile.pin), 'actual prior preparation/request joins')
            s=a['original_start_ns']; schedule=q['schedule']; limits=f['limits']
            self.R=s+schedule['duration_ns']; self.G=self.R-limits['shutdown_duration_ns']
            self.J=min(s+limits['initialization_duration_ns'],self.G)
            need(schedule['earliest_launch_ns']<=s<=schedule['latest_launch_ns'] and
                 limits['initialization_duration_ns']+limits['shutdown_duration_ns']<schedule['duration_ns'] and
                 self.R<=schedule['latest_launch_ns']+schedule['duration_ns']<=schedule['common_cutoff_ns']<=
                 a['run_deadline_ns']<=a['evidence_deadline_ns']<=self.owner.parent.share.deadline_ns,
                 'unchanged matched original S/J/G/R/E within owner')
            self.ack_body=a; self.profile_body=f; self._live(self.J)
            self._reserve_record()
            body=_body('BackendAttemptBase',condition=self.condition,pair_id=a['pair_id'],nonce=a['nonce'],
                worker_attempt=a['original_attempt'],worker_launch_ack=self.admission.ack.pin,
                request=self.admission.request.pin,preparation=self.admission.preparation.pin,
                workspace=self.admission.workspace.pin,profile=self.admission.profile.pin,
                initialization_deadline_ns=self.J,generation_deadline_ns=self.G,shutdown_deadline_ns=self.R,
                spawn_state='not_attempted',cost_prefix=self.meter.record())
            self.base=self.publisher.capture('worker/backend_attempt_base.json','BackendAttemptBase',body)
            self.base_body=body; self.state='prepared'; return self.base
        except BaseException as error: self.retain(error,'capture_base_v1'); raise

    def _child(self, capture, kind):
        body=self.read_capture(capture,kind)
        need(self.base is not None and same(body['attempt'],self.base.pin) and
             body.get('condition',self.condition)==self.condition, 'child points to actual earlier stable base')
        return body

    def capture_snapshot_v2(self, stage):
        try:
            need(self.base is not None and not self.snapshot_poisoned and stage not in self.snapshot_attempts and
                 len(self.snapshots)<3, 'finite once-only snapshot slots, no retry after uncertain capture')
            if stage=='postspawn': need(self.state=='spawned' and not self.snapshots,'postspawn first')
            elif stage=='postinitialization':
                need(self.state=='initialized' and len(self.snapshots)==1 and self.initialization is not None,
                     'postinitialization after actual child captures')
            else: need(stage=='terminal' and self.close_attempted,'terminal only after original close attempt')
            self.snapshot_attempts.append(stage) # Before cost/encode/publication.
            self._reserve_record()
            ordinal=len(self.snapshots); body=dict(self.base_body)
            body.update(schema=RECORDS['BackendAttempt']['schema_literal'],base_attempt=self.base.pin,
                previous_snapshot=None if not self.snapshots else self.snapshots[-1].pin,
                snapshot_ordinal=ordinal,snapshot_stage=stage,spawn_state=self.spawn_state,state=self.state,
                identity=self.identity,identity_observation=None if self.identity_capture is None else self.identity_capture.pin,
                group_observation=None if self.group_capture is None else self.group_capture.pin,
                first_error=None if self.first_error_capture is None else self.first_error_capture.pin,
                cost_prefix=self.meter.record())
            result=self.publisher.capture('worker/backend_attempt_snapshot_'+str(ordinal)+'.json','BackendAttempt',body)
            self.snapshots.append(result); return result
        except BaseException as error:
            self.snapshot_poisoned=True; self.retain(error,'capture_snapshot_v2'); raise

    def spawn_v1(self):
        try:
            need(self.base is not None and self.spawn_state=='not_attempted','base capture precedes sole spawn')
            self._live(self.J); self.meter.spawn_attempt()
            self.spawn_state='attempted_unacknowledged'; self.state='attempted_unacknowledged'
            self.native.spawn(self) # Native owner must retain all returned handles before fallible work.
            self.spawn_state='acknowledged'
            identity,group=self.native.process_observations(self)
            a=self._child(identity,'ProcessObservation'); g=self._child(group,'ProcessObservation')
            need(a['subject']==g['subject']=='server' and a['producer']==g['producer']=='worker' and
                 same(a['identity'],g['identity']) and same(a['group_identity'],g['group_identity']) and
                 same(a['parent_identity'],self.ack_body['worker_identity']) and
                 same(g['parent_identity'],self.ack_body['worker_identity']), 'same actual original server/group/worker')
            self.identity=a['identity']; self.identity_capture=identity; self.group_capture=group
            self._live(self.J); self.state='spawned'; return self.capture_snapshot_v2('postspawn')
        except BaseException as error:
            self.retain(error,'spawn_v1')
            if self.spawn_state!='not_attempted':self.unknown_native()
            raise

    def initialize_v1(self):
        try:
            need(self.state=='spawned' and len(self.snapshots)==1 and not self.initialization_entered,
                 'one initialization after actual postspawn')
            self.initialization_entered=True; self._live(self.J); self.state='initializing'
            e=self.native.initialization_evidence(self)
            need(type(e) is InitializationEvidence and type(e.artifacts) is tuple and 1<=len(e.artifacts)<=16,
                 'fixed live initialization product')
            selection=self.read_capture(e.selection,'LocalArtifactSelection')
            need(same(e.selection.pin,self.profile_body['artifact_selection']), 'same selected artifact family')
            self.artifact_selection=selection
            roles={}
            for cap in e.artifacts:
                a=self._child(cap,'ArtifactObservation'); need(a['role'] not in roles,'unique artifact role')
                need(a['observed_bytes']==a['selected']['bytes'] and a['observed_sha256']==a['selected']['sha256'],
                     'actual observed whole artifact equals selected identity')
                roles[a['role']]=a
            expected={'model_gguf':selection['model_gguf'],'template':selection['template_file'],
                      'tokenizer_source':selection['tokenizer_source'],'renderer_source':selection['template_renderer']}
            need(set(expected)<=set(roles) and all(same(roles[k]['selected'],v) for k,v in expected.items()),
                 'all required exact selected artifact observations')
            executable=self._child(e.executable,'ArtifactObservation')
            environment=self._child(e.environment,'EnvironmentObservation')
            self._child(e.socket,'SocketObservation'); peer=self._child(e.peer,'PeerCredentialObservation')
            need(executable['role']=='server_executable' and same(executable['selected'],self.profile_body['server_executable']) and
                 executable['observed_bytes']==executable['selected']['bytes'] and
                 executable['observed_sha256']==executable['selected']['sha256'] and
                 same(environment['selected_environment'],self.profile_body['environment_values']) and
                 same(peer['server'],self.identity) and same(peer['socket_observation'],e.socket.pin) and peer['producer']=='worker',
                 'same executable/environment/socket peer under original server')
            health=self._child(e.health,'ParsedHealth'); slots=self._child(e.slots,'ParsedSlots')
            need(health['endpoint']=='health' and slots['endpoint']=='slots' and
                 health['pair_nonce']==slots['pair_nonce']==self.ack_body['nonce'] and
                 health['observed_ns']<=slots['observed_ns']<=self.J and
                 health['ordinal']<slots['ordinal']<self.profile_body['limits']['maximum_initialization_probes'] and
                 slots['slots'][0]['n_ctx']==self.profile_body['limits']['context_tokens'], 'actual bounded health/slots only')
            now=self._live(self.J)
            self._reserve_record()
            proof=_body('SourceInitializationProof',condition=self.condition,attempt=self.base.pin,
                source_admission=self.ack_body['source_admission'],worker_launch_ack=self.admission.ack.pin,
                spawn_observation=self.identity_capture.pin,process_observation=self.group_capture.pin,
                executable_observation=e.executable.pin,artifact_observations=[x.pin for x in e.artifacts],
                environment_observation=e.environment.pin,socket_observation=e.socket.pin,peer_observation=e.peer.pin,
                health=e.health.pin,slots=e.slots.pin,original_S_ns=self.ack_body['original_start_ns'],
                initialization_J_ns=self.J,generation_G_ns=self.G,shutdown_R_ns=self.R,
                last_probe_ordinal=slots['ordinal'],generation_request_count=0,
                source_stage='fresh_slot_task_completed_before_first_generation',cost_prefix=self.meter.record())
            self.source_proof=self.publisher.capture('worker/backend_source_initialization.json','SourceInitializationProof',proof)
            self._reserve_record()
            body=_body('BackendInitializationObservation',condition=self.condition,attempt=self.base.pin,
                preparation=self.admission.preparation.pin,workspace=self.admission.workspace.pin,
                profile=self.admission.profile.pin,worker_launch_ack=self.admission.ack.pin,
                worker_identity=self.ack_body['worker_identity'],server_identity=self.identity,
                spawn_observation=self.identity_capture.pin,same_group_observation=self.group_capture.pin,
                socket_observation=e.socket.pin,peer_credential_observation=e.peer.pin,
                executable_observation=e.executable.pin,artifact_observations=[x.pin for x in e.artifacts],
                environment_observation=e.environment.pin,health_response=e.health.pin,initial_slots_response=e.slots.pin,
                source_initialization_proof=self.source_proof.pin,generation_requests_before_capture=0,
                observed_ready_ns=now,cost_prefix=self.meter.record())
            self.initialization=self.publisher.capture('worker/backend_initialization.json','BackendInitializationObservation',body)
            self.state='initialized'; return self.capture_snapshot_v2('postinitialization')
        except BaseException as error:
            self.retain(error,'initialize_v1'); self.unknown_native(); raise

    def consume_admission_v1(self):
        try:
            need(self.state=='initialized' and len(self.snapshots)==2 and not self.host_admission_entered,
                 'one H admission after completed initialization snapshot')
            self.host_admission_entered=True; self._live(self.G)
            admission=self.native.consume_host_admission(self)
            need(type(admission) is HBackendAdmission and admission.worker_admission is self.admission and
                 admission.backend_handle is self,'actual independent H capability for this live handle')
            a=self.read_capture(admission.ack,'BackendAdmissionAck')
            h=self._child(admission.host_observation,'HostInitializationObservation')
            need(same(a['backend_attempt'],self.base.pin) and same(a['worker_attempt'],self.ack_body['original_attempt']) and
                 same(a['initialization'],self.initialization.pin) and same(h['initialization'],self.initialization.pin) and
                 same(a['host_observation'],admission.host_observation.pin) and
                 same(a['source_admission'],self.ack_body['source_admission']) and
                 same(a['host_owner_binding'],self.ack_body['owner_binding']) and
                 same(h['host_owner_binding'],a['host_owner_binding']) and same(h['source_admission'],a['source_admission']) and
                 a['condition']==self.condition and a['pair_id']==self.ack_body['pair_id'] and
                 a['nonce']==h['pair_nonce']==self.ack_body['nonce'] and a['generation_deadline_ns']==self.G and
                 self.ack_body['original_start_ns']<=h['observed_ns']<=a['issued_ns']<self.G,
                 'actual H ack/base/worker/source/nonce/original deadline joins')
            self._live(self.G); self.host_admission=admission; self.state='admitted'; return admission.ack
        except BaseException as error: self.retain(error,'consume_admission_v1'); raise

    def complete_v1(self, semantic_request):
        try:
            need(self.state in ('admitted','serving') and self.host_admission is not None and
                 self.pending is None and not self.agent_done, 'one in-flight request after actual H admission')
            self._live(self.G); q=self.read_capture(semantic_request,'CompletionRequest')
            ordinal=len(self.requests)
            need(ordinal<self.profile_body['limits']['maximum_generation_requests'] and
                 q['request_ordinal']==ordinal and same(q['backend_admission'],self.host_admission.ack.pin) and
                 same(q['sampling'],self.profile_body['sampling']), 'exact sequential immutable request')
            self.pending=semantic_request; self.requests.append(semantic_request); started=self._live(self.G)
            e=self.native.completion_evidence(self,semantic_request)
            need(type(e) is CompletionEvidence, 'fixed original exchange product')
            w=self._child(e.wire_request,'BackendHttpRequest'); raw=self._child(e.raw_response,'RawHttpResponse')
            p=self._child(e.parsed_response,'ParsedCompletion')
            need(w['endpoint']==raw['endpoint']==p['endpoint']=='completion' and
                 w['ordinal']==raw['ordinal']==p['ordinal']==ordinal and
                 w['pair_nonce']==raw['pair_nonce']==p['pair_nonce']==self.ack_body['nonce'] and
                 same(w['completion_request'],semantic_request.pin) and
                 same(raw['request'],e.wire_request.pin) and same(p['request'],semantic_request.pin) and
                 same(p['raw'],e.raw_response.pin) and raw['state']=='complete' and raw['first_error'] is None and
                 not raw['secondary_errors'] and not raw['unknown_physical_read'] and
                 started<=raw['finished_ns']<=self.G and p['received_ns']==raw['finished_ns'],
                 'complete actual raw/parsed response for pending request')
            bound=8*(self.profile_body['limits']['maximum_request_bytes']+
                     self.profile_body['limits']['maximum_response_bytes']+
                     self.profile_body['limits']['maximum_header_bytes'])
            self.meter.charge('retained_bytes',bound);self.meter.charge('work_units',64*bound)
            expected_wire,body_bytes=request_wire('completion',self.profile_body,q)
            need(w['wire_hex']==expected_wire.hex() and w['wire_bytes']==len(expected_wire) and
                 w['body_bytes']==body_bytes and w['method']=='POST' and w['path']=='/completion',
                 'exact source-generated original completion wire')
            parsed_kind,parsed_body=parse_response(raw,w,self.profile_body,self.artifact_selection,
                semantic_request=q,generation_deadline=self.G)
            need(parsed_kind=='completion' and same(parsed_body,p['body']), 'actual raw parser result equals capture')
            b=p['body']; need(b['index']==b['id_slot']==0 and b['stop'] and not b['truncated'] and
                b['stop_type'] in ('eos','word','limit') and (b['stop_type']!='limit' or b['content']!='') and
                b['generation_settings/n_predict']==q['maximum_generated_tokens'], 'complete selected response semantics')
            limit=self.profile_body['limits']['context_tokens']+q['maximum_generated_tokens']
            need(all(b[k]<=limit for k in ('tokens_cached','tokens_evaluated','tokens_predicted')),
                 'bounded actual counters without clamping')
            self._live(self.G)
            self._reserve_record()
            exchange=self.publisher.capture('worker/backend_exchange_'+str(ordinal)+'.json','BackendExchangeObservation',
                _body('BackendExchangeObservation',attempt=self.base.pin,ordinal=ordinal,
                admission=self.host_admission.ack.pin,request=semantic_request.pin,response=e.parsed_response.pin,
                status='complete',started_ns=started,finished_ns=raw['finished_ns'],request_complete='known_closed',
                response_complete='known_closed',first_error=None,cost_prefix=self.meter.record()))
            self.exchanges.append(exchange)
            self._reserve_record()
            result=self.publisher.capture('worker/backend_completion_'+str(ordinal)+'.json','AgentCompletion',
                _body('AgentCompletion',attempt=self.base.pin,condition=self.condition,ordinal=ordinal,
                parsed_response=e.parsed_response.pin,exchange=exchange.pin,text=b['content'],
                tokens_predicted=b['tokens_predicted'],tokens_evaluated=b['tokens_evaluated'],tokens_cached=b['tokens_cached'],
                generation_stop=b['stop_type'],token_limited=b['stop_type']=='limit'))
            self.pending=None; self.state='serving'; return result
        except BaseException as error:
            self.retain(error,'complete_v1')
            if self.pending is not None:self.unknown_native()
            raise

    def mark_agent_done_v1(self):
        try:
            self._live(self.G); need(self.pending is None and self.host_admission is not None,'completed agent requests')
            self.agent_done=True
        except BaseException as error: self.retain(error,'mark_agent_done_v1'); raise

    def _cleanup_one(self, name, kind):
        try:
            self.cleanup_entered.append(name) # Before native call, even if it raises after an effect.
            self._close_clock()
            if name=='signal': capture=self.native.signal(self,self.purpose)
            elif name=='wait': capture=self.native.wait(self)
            elif name=='streams': capture=self.native.streams(self)
            elif name=='socket': capture=self.native.socket_closure(self)
            else: capture=self.native.subtree(self)
            self.cleanup[name]=(capture,self._child(capture,kind))
        except BaseException as error:
            self.retain(error,'close_'+name); self.unknown_native()

    def _close_clock(self):
        self.meter.check()
        now=self.native.now_ns(self)
        need(type(now) is int and self.ack_body['original_start_ns']<=now<=self.R,
             'original worker shutdown/publication cutoff, not later H evidence time')
        return now

    def _successful_close(self):
        if self.raw_first is not None or self.purpose!='planned_protocol_shutdown' or len(self.cleanup)!=5:return False
        s=self.cleanup['signal'][1]; e=self.cleanup['wait'][1]; t=self.cleanup['streams'][1]
        u=self.cleanup['socket'][1]; g=self.cleanup['subtree'][1]
        return (s['purpose']==self.purpose and s['state']=='complete' and s['first_error'] is None and
            s['attempt_ordinal']==0 and s['sent_ns'] is not None and s['sent_ns']<self.R and
            same(s['server'],self.identity) and same(e['server'],self.identity) and
            e['state']=='reaped' and type(e['exit_code']) is int and e['exit_code']==0 and e['first_error'] is None and
            e['wait_started_ns'] is not None and e['wait_started_ns']<=e['wait_finished_ns']<=self.R and
            t['first_error'] is None and [x['name'] for x in t['sides']]==['stdout','stderr'] and
            all(x['state']=='known_closed' and x['eof_observed'] and x['pending_bytes']==0 and
                not x['unknown_physical_read'] and x['closed_ns'] is not None and x['closed_ns']<=self.R for x in t['sides']) and
            u['first_error'] is None and u['state']=='known_closed' and u['observed_absent'] and
            u['observed_ns'] is not None and u['observed_ns']<=self.R and
            g['scope']=='server_subtree' and g['producer']=='worker' and same(g['root'],self.identity) and
            same(g['excluded_live_worker'],self.ack_body['worker_identity']) and g['enumeration_complete'] and
            g['unresolved_count']==0 and not g['members'] and g['observed_ns']<=self.R)

    def close_v1(self):
        if self.close_attempted:return self.closure if self.closure_qualified else None
        self.close_attempted=True
        self.purpose=('planned_protocol_shutdown' if self.raw_first is None and self.agent_done and
                      self.pending is None and self.host_admission is not None else 'failure_cleanup')
        if self.base is None:return None
        if self.spawn_state!='not_attempted':
            for name,kind in (('signal','SignalObservation'),('wait','ExitObservation'),
                ('streams','StreamClosureObservation'),('socket','SocketClosureObservation'),('subtree','SubtreeObservation')):
                try:self._cleanup_one(name,kind)
                except BaseException as error:self.retain(error,'cleanup_owner_'+name)
        try:
            success=self._successful_close()
            if not success and self.raw_first is None: raise RuntimeError('original closure evidence incomplete')
            self.state='closed' if success else 'failed'
        except BaseException as error: self.retain(error,'close_validation'); success=False
        try:
            self._close_clock()
            if not self.snapshot_poisoned:self.capture_snapshot_v2('terminal')
        except BaseException as error:self.retain(error,'terminal_snapshot_or_clock')
        success=success and self.raw_first is None and not self.snapshot_poisoned and self.snapshot_attempts[-1]=='terminal'
        def child(name): return None if name not in self.cleanup else self.cleanup[name][0].pin
        try:
            self._close_clock()
            self._reserve_record()
            body=_body('BackendClosure',attempt=self.base.pin,condition=self.condition,
                initialization=None if self.initialization is None else self.initialization.pin,
                admission=None if self.host_admission is None else self.host_admission.ack.pin,
                requests=[x.pin for x in self.requests],server_identity=self.identity,purpose=self.purpose,
                signal_observation=child('signal'),exit_observation=child('wait'),stream_closure=child('streams'),
                socket_closure=child('socket'),group_observation=child('subtree'),
                exit_code=None if 'wait' not in self.cleanup else self.cleanup['wait'][1]['exit_code'],
                pending_requests=int(self.pending is not None),forced_group_cleanup=False,
                status='complete' if success else 'unknown',first_error=None if self.first_error_capture is None else self.first_error_capture.pin,
                cost_prefix=self.meter.record())
            self.closure=self.publisher.capture('worker/backend_closure.json','BackendClosure',body)
            # This original observation is outside the already immutable raw
            # record. Failure retains that capture but never returns success.
            self._close_clock(); self.closure_qualified=success and self.raw_first is None
        except BaseException as error:self.retain(error,'close_publication')
        return self.closure if self.closure_qualified else None


def open_initialize_backend_v1(admission,publisher):
    """Fixed worker caller. Failure always attempts original cleanup, no retry."""
    handle=BackendAttemptHandle(admission,publisher)
    try:
        handle.capture_base_v1(); handle.spawn_v1(); handle.initialize_v1(); handle.consume_admission_v1()
        return handle
    except BaseException:
        try:handle.close_v1()
        except BaseException as secondary:handle.retain(secondary,'worker_outer_cleanup')
        raise handle.raw_first
