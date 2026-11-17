"""Fixed H receiver with actual packet/publication/error custody.

The physical channel, original owner, publishers and completed bootstrap must
be actual source objects. The pending V3 root/bootstrap producer is not replaced
by a dictionary. This module is an inactive source construction component.
"""
import hashlib
from .common import need, same, DependencyUnavailable, pin, bounded_size
from .backend_json import parse, canonical
from .backend_capture import CanonicalPublisher, CapturedRecord, CaptureAttempt, _CAPTURE
from .backend_linux_channel import HNativeChannelOwner
from .backend_native_boundary import HWorkerLaunchAdmission
from .backend_native_v3_codec import validate_native_type, packet_decode, packet_encode, payload_name
from .backend_native_v3_records import NATIVE_RECORDS
from .backend_native_reservations import NativeReservationLedger
from .backend_host_view import HBackendView, _VIEW, _SITES

_ACTIVATION=object()

class HReceiverActivation:
    """Private live output of the fixed H bootstrap, never a wire factory.

    Exact V3 issuer/entry/group/start/memfd joins are being separately authored.
    There is deliberately no public supplied-captures activation constructor.
    The token path is only for that forthcoming fixed original producer.
    """
    def __init__(self,token):
        need(token is _ACTIVATION,'fixed H bootstrap issuer only')
        self.channel=None;self.admission=None;self.policy=None;self.reservation=None
        self.table=None;self.objects=();self.grant=None;self.context=None
        self.host_publisher=None;self.arm_publisher=None;self.ledger=None
        self.S=self.J=self.G=self.R=self.E=None;self.packet_limit=None
        self.logical_limit=None;self.maximum_sequences=None;self.maximum_publications=None
        self.complete=False;self.receiver=None;self.bootstrap_owner=None
    def require_original(self):
        need(self.complete and type(self.channel)is HNativeChannelOwner and
             getattr(self.channel,'receiver_activation',None)is self,
             'same completed source-owned original H bootstrap activation')
        a=self.channel.attempt;a.require_live_original()
        need(type(self.admission)is HWorkerLaunchAdmission and a.native_launch_admission is self.admission and
             self.admission.owner is a.owner and self.admission.condition==a.condition and
             self.admission.ack is a.launch_ack,'actual original native worker launch capability')
        need(type(self.ledger)is NativeReservationLedger and self.ledger.channel is self.channel and
             self.channel.reservation_ledger is self.ledger,'same original prior reservation ledger')
        for pub,condition in ((self.host_publisher,None),(self.arm_publisher,a.condition)):
            need(type(pub)is CanonicalPublisher and pub.owner is a.owner and pub.condition==condition,
                 'original fixed same-owner H and arm-paid publishers')
        from .backend_h_bootstrap_v3 import HWorkerBootstrapOwnerV3,HBootstrapObjectV3
        source=self.bootstrap_owner
        need(type(source)is HWorkerBootstrapOwnerV3 and source.attempt is a and
             source.channel is self.channel and self.channel.bootstrap_owner_v3 is source and
             source.activation is self and source.prepared and source.raw_first is None,
             'actual original staged bootstrap owner, no supplied activation')
        for cap in (self.policy,self.reservation):
            need(type(cap)is HBootstrapObjectV3 and cap.owner is source,'original delivery view')
            cap.require_original()
        if source.complete:
            need(self.table is source.table and type(self.table)is CapturedRecord and
                 self.table.owner is a.owner and self.table._attempt.complete is self.table and
                 self.table._attempt.raw_first is None and self.grant is not None,
                 'original complete first-Hello peer/table/grant publication')
            for cap in self.objects:
                need(type(cap)is HBootstrapObjectV3 and cap.owner is source,'same original full delivery roster')
                cap.require_original()
        else:
            need(self.table is None and self.grant is None and not self.objects,
                 'no future peer/table/grant before actual first Hello')
        need(0<self.packet_limit<=65536 and 0<self.maximum_sequences<=4096 and
             0<self.logical_limit<=self.arm_publisher.maximum_bytes and self.maximum_publications>0,
             'complete finite original packet/publication capacities')
        need(self.S==a.started_ns and self.S<self.J<=self.G<self.R==a.run_deadline_ns and self.E==a.evidence_deadline_ns,
             'same earlier actual S/J/G/R/E; no prestart-prefix rewrite')

class HReceiverPending:
    def __init__(self,receiver):
        self.receiver=receiver;self.sequence=receiver.sequence;self.raw=None;self.packet=None;self.kind=None
        self.reply=None;self.encoded_reply=None;self.sent_count=None;self.complete=False
        self.receive_entered=False;self.send_entered=False;self.raw_first=None;self.secondaries=[]
        self.effect_slot=None;self.capture_attempt=None;self.uncertain=False
        self.input_admitted=False;self.dispatch_entered=False;self.parse_entered=False;self.encode_entered=False
        self.send_origin=None
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)

class HPublicationReceive:
    def __init__(self,receiver,intent):
        self.receiver=receiver;self.intent=dict(intent);self.id=len(receiver.publications)
        self.original_sequence=receiver.sequence;self.slot=None;self.raw_chunks=[];self.received=0
        self.next_index=0;self.chunk_size=None;self.chunk_count=None;self.raw=None;self.parsed=None
        self.capture=None;self.path=None;self.complete=False;self.raw_first=None

class HEffectReceive:
    def __init__(self,receiver,intent):
        self.receiver=receiver;self.intent=intent;self.sequence=receiver.sequence;self.slot=None
        self.grant=None;self.delivery=None;self.observation=None;self.complete=False
        self.intent_pending=receiver.pending;self.observation_pending=None

class HChannelReceiver:
    def __init__(self,activation):
        need(type(activation)is HReceiverActivation,'fixed earlier H bootstrap object')
        activation.require_original();need(activation.receiver is None,'one original receiver')
        self.activation=activation;self.channel=activation.channel;self.attempt=self.channel.attempt
        self.owner=self.attempt.owner;self.ledger=activation.ledger
        self.host_meter=self.ledger.host_meter();self.arm_meter=self.ledger.arm_meter()
        self.sequence=0;self.previous_ack=None;self.pending=None;self.history=[]
        self.raw_first=None;self.secondaries=[];self.poisoned=False;self.finished=False
        self.publication=None;self.publications=[];self.effect=None;self.effects=[]
        self.capture_attempts=[];self.delivered_objects={};self.bootstrap_offsets={}
        self.admission_offsets={};self.admission_delivered=set()
        self.maximum_generation_requests=self.attempt.pair.contract.backend['limits']['maximum_generation_requests']
        self.backend_view=None;activation.receiver=self;self.channel.protocol=self
        self.backend_view=HBackendView(_VIEW,self)
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.poisoned=True
        if self.pending is not None:self.pending.retain(error)
        self.backend_view.retain(error)
        try:self.channel.retain(error,'receiver_'+site)
        except BaseException as later:self.secondaries.append(later)
    def _now(self,stage):
        deadline={'bootstrap':self.activation.J,'initialization':self.activation.J,
                  'generation':self.activation.G,'shutdown':self.activation.R}[stage]
        return self.channel._now(deadline),deadline
    def _stage(self):
        if self.backend_view.closure is not None:return 'shutdown'
        if self.backend_view.admission is not None:return 'generation'
        return 'bootstrap' if self.sequence==0 else 'initialization'
    def _prefix(self):return self.owner.cost_prefix()
    def _require_worker_stage(self,stage):
        view=self.backend_view
        if stage=='bootstrap':need(view.base is None,'bootstrap cannot reopen after original base')
        elif stage=='initialization':need(view.admission is None and view.closure is None,'initialization cannot reopen after original admission/closure')
        elif stage=='generation':need(view.admission is not None and view.closure is None,'actual H admission before generation')
        else:need(stage=='shutdown' and view.base is not None,'original backend exists before shutdown effects')
        return self._now(stage)
    def _capture_native(self,name,kind,body):
        """Closed host-only EffectGrant producer on the original H Store."""
        need(kind=='EffectGrantV1' and name=='native_context/'+self.attempt.condition+'/effect_grant_'+str(self.sequence)+'.json',
             'one source-fixed grant pathname and exact record type')
        pub=self.activation.host_publisher
        need(pub.raw_first is None and name not in pub.attempts,'one original canonical attempt')
        key=(str(pub.outputs.root),name)
        need(key not in pub.parent.canonical_publications and len(pub.parent.canonical_publications)<pub.maximum_members,
             'same whole-owner publication census including failures')
        attempted=CaptureAttempt(name,kind);pub.attempts[name]=attempted
        pub.parent.canonical_publications[key]=attempted;self.capture_attempts.append(attempted)
        try:
            bound=bounded_size(body);self.host_meter.charge('work_units',bound)
            self.host_meter.charge('retained_bytes',bound);validate_native_type(kind,body)
            raw=canonical(body,pub.maximum_bytes,maximum_depth=pub.maximum_depth);attempted.raw=raw
            attempted.write_entered=True;observed=pub.outputs.write(name,raw);attempted.provisional=observed
            self.host_meter.charge('retained_bytes',len(raw)+1);attempted.readback_entered=True
            reread=pub.outputs.read(observed,pub.maximum_bytes,metadata=True)
            need(reread==raw and pin(reread)==pin(raw),'complete actual original grant readback')
            cap=CapturedRecord(_CAPTURE,raw,observed,self.owner,kind,attempted);attempted.complete=cap
            return cap
        except BaseException as error:
            attempted.retain(error);pub.raw_first=error;raise
    def step_once_v3(self):
        """Return pending on completion, otherwise None; never wait for IO.

        At most one recvmsg and one sendmsg per invocation. A known EAGAIN
        retains the same pending request, bounds and debit. Parsing, dispatch
        and reply encoding are each entered once; an ambiguous reply is never
        replayed. MAIN owns fairness and original physical/stream pumping.
        """
        need(not self.poisoned and not self.finished,'live original receiver')
        pending=self.pending
        if pending is None:
            need(self.sequence<self.activation.maximum_sequences,'finite original failed/completed sequence slots')
            pending=HReceiverPending(self);self.pending=pending;self.history.append(pending)
        need(pending.receiver is self and pending.sequence==self.sequence and not pending.complete,
             'same original outstanding sequence, no caller replacement')
        try:
            self.activation.require_original();cap=self.activation.packet_limit
            if not pending.input_admitted:
                # Mark before charges: partial reservation failure never retries.
                pending.input_admitted=True
                self.host_meter.charge('retained_bytes',32*cap+4096)
                self.host_meter.charge('work_units',32*cap+4096)
            if pending.raw is None:
                pending.receive_entered=True
                raw=self.channel.try_receive_v3(cap,self.activation.R)
                if raw is None:return None
                pending.raw=raw
            if not pending.parse_entered:
                pending.parse_entered=True
                packet=packet_decode(pending.raw,cap);pending.packet=packet
                need(packet['direction']=='worker_to_host' and packet['sequence']==self.sequence and
                     same(packet['previous_ack'],self.previous_ack),'exact original request order/direction')
                kind=payload_name(packet['payload']);pending.kind=kind
                if self.sequence==0:
                    need(kind=='BootstrapHelloV3' and packet['context']is None and packet['source_policy']is None,
                         'only fixed first Hello has no future context/policy')
                else:
                    need(kind!='BootstrapHelloV3' and same(packet['context'],self.activation.context) and
                         same(packet['source_policy'],self.activation.policy.pin),'same original context/source selection')
            if not pending.dispatch_entered:
                pending.dispatch_entered=True
                pending.reply=self._dispatch(pending.kind,pending.packet['payload'])
            if not pending.encode_entered:
                pending.encode_entered=True;payload_name(pending.reply,reply=True)
                envelope={'schema':'four_packet_v1','direction':'host_to_worker','sequence':self.sequence,
                  'previous_ack':self.previous_ack,'context':self.activation.context,
                  'source_policy':self.activation.policy.pin,'payload':pending.reply}
                pending.encoded_reply=packet_encode(envelope,cap)
            pending.send_entered=True
            if pending.send_origin is None:pending.send_origin=self.channel.known_written
            sent=self.channel.try_send_v3(pending.encoded_reply,cap,self.activation.R)
            if sent is None:return None
            pending.sent_count=sent
            need(sent==len(pending.encoded_reply),'whole original response accepted once')
            pending.complete=True;self.previous_ack=self.sequence;self.sequence+=1;self.pending=None
            if pending.kind=='FinishWorkerV1':self.finished=True
            return pending
        except BaseException as error:
            pending.uncertain=(self.channel.unknown_read or self.channel.unknown_write or
                (pending.send_origin is not None and self.channel.known_written>pending.send_origin))
            self.retain(error,'step_once');raise

    def io_interest_v3(self):
        """Fixed readiness facts only; returned endpoint conveys no new owner."""
        need(not self.poisoned and not self.finished,'live original receiver')
        self.activation.require_original();self.channel._nonblocking_ready_owner()
        pending=self.pending
        return (self.channel.host,'write' if pending is not None and pending.encoded_reply is not None else 'read')

    def serve_one(self):
        """Legacy convenience only; never the actual two-arm driver entry."""
        while True:
            _,interest=self.io_interest_v3()
            self.channel._ready(self.activation.R,interest=='write')
            complete=self.step_once_v3()
            if complete is not None:return complete
    def _dispatch(self,kind,b):
        if self.publication is not None:
            need(kind in ('PublicationChunkV1','PublicationCommitV1'),'no interleaving logical publication')
        if self.effect is not None:need(kind=='EffectObservationV1','one unresolved original effect')
        if kind=='BootstrapHelloV3':
            carrier=self.attempt.bootstrap_carrier
            from .backend_bootstrap_carrier_v3 import HBootstrapCarrierOwnerV3
            need(type(carrier)is HBootstrapCarrierOwnerV3 and carrier.attempt is self.attempt and
                 carrier.complete and carrier.raw_first is None and carrier.closed and carrier.close_entered,
                 'actual original completed H carrier and parent-alias closure')
            need(b['carrier_sha256']==hashlib.sha256(carrier.raw).hexdigest() and
                 b['start_observation']==carrier.start.capture.pin and
                 carrier.body['context']==self.activation.context and
                 carrier.body['context_policy']==self.activation.policy.pin,
                 'first Hello inverses actual earlier carrier/start/context; no supplied authority')
            return self.activation.bootstrap_owner.grant_after_original_hello(self.pending)
        need(self.activation.bootstrap_owner.complete,'actual completed original first Hello before later requests')
        if kind=='BootstrapObjectRequestV1':return self._object(b)
        if kind=='CheckRequestV1':
            now,deadline=self._require_worker_stage(b['stage'])
            return {'schema':'four_check_ack_v1','admissible':True,'cost_prefix':self._prefix(),
                    'observed_ns':now,'original_deadline_ns':deadline,'request_sequence':self.sequence,'stage':b['stage']}
        if kind=='EffectIntentV1':return self._reserve_effect(b)
        if kind=='EffectObservationV1':return self._observe_effect(b)
        if kind=='PublicationIntentV1':return self._publication_begin(b)
        if kind=='PublicationChunkV1':return self._publication_chunk(b)
        if kind=='PublicationCommitV1':return self._publication_commit(b)
        if kind=='PollBackendAdmissionV1':return self._poll_admission(b)
        if kind=='AdmissionObjectRequestV1':return self._admission_object(b)
        if kind=='FinishWorkerV1':return self._finish(b)
        need(False,'compiled exhaustive request branch')
    def _chunk_bytes(self):
        payload={'schema':'four_publication_chunk_v1','publication_id':self.activation.maximum_publications,
          'index':self.activation.logical_limit,'offset':self.activation.logical_limit,'raw_hex':''}
        outer={'schema':'four_packet_v1','direction':'worker_to_host','sequence':4095,'previous_ack':4095,
          'context':self.activation.context,'source_policy':self.activation.policy.pin,'payload':payload}
        # Size-only upper-width scalar probes are not records or authority.
        base=canonical(outer,self.activation.packet_limit)
        return min(16384,max(0,(self.activation.packet_limit-len(base))//2))
    def _object(self,b):
        need(same(b['table'],self.activation.table.pin),'exact original object table')
        ordinal=b['ordinal'];need(ordinal<len(self.activation.objects),'closed original bootstrap ordinal')
        cap=self.activation.objects[ordinal];offset=self.bootstrap_offsets.get(ordinal,0)
        need(b['offset']==offset and ordinal not in self.delivered_objects,'contiguous one-time original object delivery')
        prototype={'schema':'four_bootstrap_object_chunk_v1','table':self.activation.table.pin,'ordinal':ordinal,
          'kind':cap.kind,'capture':cap.pin,'offset':offset,'raw_hex':'','final':False}
        outer={'schema':'four_packet_v1','direction':'host_to_worker','sequence':self.sequence,
          'previous_ack':self.previous_ack,'context':self.activation.context,
          'source_policy':self.activation.policy.pin,'payload':prototype}
        count=min(16384,max(0,(self.activation.packet_limit-len(canonical(outer,self.activation.packet_limit)))//2))
        need(count>0,'original packet supports exact framed object chunk')
        raw=cap.raw[offset:offset+count];need(raw,'no repeated EOF object request')
        after=offset+len(raw);self.bootstrap_offsets[ordinal]=after
        if after==len(cap.raw):self.delivered_objects[ordinal]=cap
        return {'schema':'four_bootstrap_object_chunk_v1','table':self.activation.table.pin,'ordinal':ordinal,
                'kind':cap.kind,'capture':cap.pin,'offset':offset,'raw_hex':raw.hex(),'final':after==len(cap.raw)}
    def _reserve_effect(self,b):
        need(self.effect is None and len(self.delivered_objects)==len(self.activation.objects),
             'complete original bootstrap before fixed effects')
        now,deadline=self._require_worker_stage(b['stage']);need(b['deadline_ns']==deadline,'exact original phase cutoff')
        if b['site']=='render_template':
            from .worker_selected_source_v3 import require_host_render_operands_v3
            need(not any(x.intent['site']=='render_template' and x.intent['ordinal']==b['ordinal']
                         for x in self.effects),'no reuse of an original render ordinal, including failure')
            require_host_render_operands_v3(self.backend_view,b)
        else:
            for previous in b['prior_captures']:self.backend_view._prior(previous)
        effect=HEffectReceive(self,b);self.effect=effect;self.effects.append(effect)
        # Before any effect reservation, prove the later full reply fits this
        # actual packet bound. Bound all scalar widths and actual fixed Pin path.
        bound=self.activation.packet_limit
        estimated=bounded_size(b)+bounded_size(self.activation.context)+bounded_size(self._prefix())+8192
        need(estimated<=bound,'full grant/body/Pin/envelope width preadmitted before grant')
        # The ledger binds both actual owners before any fallible debit.
        self.ledger.reserve_worker_effect(effect)
        body={'schema':'four_effect_grant_v1','context':self.activation.context,'cost_prefix':self._prefix(),
              'intent':b,'issued_ns':now,'original_ledger_slot':effect.slot.ordinal,'request_sequence':self.sequence}
        effect.grant=self._capture_native('native_context/'+self.attempt.condition+'/effect_grant_'+str(self.sequence)+'.json',
                                         'EffectGrantV1',body)
        effect.delivery={'schema':'four_effect_grant_delivery_v2','grant':effect.grant.pin,'grant_body':body}
        return effect.delivery
    def _observe_effect(self,b):
        effect=self.effect;need(effect is not None and effect.grant is not None,'actual earlier complete grant')
        need(b['request_sequence']==effect.sequence and same(b['grant'],effect.grant.pin),'exact earlier grant and sequence')
        effect.observation=b;effect.slot.observation=b # Retain even invalid excess before checks.
        if effect.intent['site']=='render_template':
            need(effect.observation_pending is None and type(self.pending)is HReceiverPending and
                 self.pending.receiver is self and self.pending.kind=='EffectObservationV1' and
                 self.pending.packet['payload']is b,'actual original render observation pending')
            effect.observation_pending=self.pending
        for key,dim in (('known_read_bytes','read_bytes'),('known_write_bytes','write_bytes'),('known_returned_processes','process_starts')):
            need(b[key]<=effect.intent['maximum'][dim],'original observed prefix within granted bound')
        need(len(set(b['unknown_dimensions']))==len(b['unknown_dimensions']),'unique unknown resource dimensions')
        permitted=b['state']=='complete' and b['failure']is None and not b['unknown_dimensions']
        if not permitted:
            for dim in b['unknown_dimensions']:self.owner.parent.unknown.add(dim)
        effect.complete=True;self.effect=None
        # A remote failure is a remote observation, never a fabricated H raw exception.
        if not permitted:self.finished=True
        return {'schema':'four_effect_observation_ack_v1','charged_prefix':self._prefix(),
                'continued_effects_allowed':permitted,'grant':effect.grant.pin,'observation_sequence':self.sequence}
    def _publication_begin(self,b):
        need(len(self.delivered_objects)==len(self.activation.objects),'complete bootstrap before worker publications')
        need(b['site']in _SITES and _SITES[b['site']][0]==b['kind'],'fixed source site/kind pair')
        need(len(self.publications)<self.activation.maximum_publications and b['canonical_bytes']<=self.activation.logical_limit,
             'original whole publication/file/logical limits')
        p=HPublicationReceive(self,b);self.publication=p;self.publications.append(p)
        size=b['canonical_bytes'];self.host_meter.charge('retained_bytes',32*size+4096)
        self.host_meter.charge('work_units',32*size+4096)
        p.chunk_size=self._chunk_bytes();need(p.chunk_size>0,'positive chunk under original packet ceiling')
        p.chunk_count=(size+p.chunk_size-1)//p.chunk_size
        need(self.sequence+p.chunk_count+2<=self.activation.maximum_sequences,'complete begin/chunks/commit fit unchanged sequence limit')
        p.slot=self.ledger.control_host
        return {'schema':'four_publication_start_ack_v1','chunk_bytes':p.chunk_size,'chunk_count':p.chunk_count,
                'intent_sequence':self.sequence,'original_ledger_slot':p.slot.ordinal,'publication_id':p.id}
    def _publication_chunk(self,b):
        p=self.publication;need(p is not None and b['publication_id']==p.id and b['index']==p.next_index and
             b['offset']==p.received and p.next_index<p.chunk_count,'exact contiguous original publication chunk')
        raw=bytes.fromhex(b['raw_hex']);p.raw_chunks.append(raw) # Preserve original returned prefix before length check.
        p.received+=len(raw);p.next_index+=1
        required=min(p.chunk_size,p.intent['canonical_bytes']-b['offset'])
        need(len(raw)==required,'exact bounded full chunk including final remainder')
        return {'schema':'four_publication_chunk_ack_v1','acknowledged_bytes':len(raw),'index':b['index'],'publication_id':p.id}
    def _publication_commit(self,b):
        p=self.publication;need(p is not None and b['publication_id']==p.id and p.next_index==p.chunk_count and
             p.received==b['canonical_bytes']==p.intent['canonical_bytes'] and b['canonical_sha256']==p.intent['canonical_sha256'],
             'complete exact original chunk set and declared canonical identity')
        p.raw=b''.join(p.raw_chunks)
        need(hashlib.sha256(p.raw).hexdigest()==b['canonical_sha256'],'actual complete canonical digest')
        p.parsed=parse(p.raw,len(p.raw),maximum_depth=64,maximum_members=len(p.raw),maximum_string_bytes=len(p.raw))
        need(canonical(p.parsed,len(p.raw))==p.raw,'canonical worker publication with no alternate representation')
        p.path=self.backend_view.validate_publication(p.intent['site'],p.intent['ordinal'],p.parsed)
        site=p.intent['site']
        if site in ('signal','exit','streams','socket_closure','subtree','closure') or (
             site=='snapshot' and p.parsed['snapshot_stage']=='terminal'):stage='shutdown'
        elif site in ('rendered_template','completion_request','exchange','agent_completion') or (
             site.startswith('http_') and p.parsed['endpoint']=='completion'):stage='generation'
        else:stage='initialization'
        self._require_worker_stage(stage)
        binding=self.activation.arm_publisher.require_native_source_v3()
        capture_source=binding.source_pin
        need(capture_source==self.activation.policy.body['canonical_publisher_source'],
             'same actual earlier publisher source selected by current native policy')
        p.capture=self.activation.arm_publisher.capture(p.path,p.intent['kind'],p.parsed)
        self.backend_view.accept_completed(p.intent['site'],p.intent['ordinal'],p.capture)
        p.complete=True;self.publication=None
        return {'schema':'four_publication_ack_v1','capture':p.capture.pin,'commit_sequence':self.sequence,
                'context':self.activation.context,'cost_prefix':self._prefix(),'kind':p.capture.kind,
                'original_capture_source':capture_source,'publication_id':p.id}
    def _poll_admission(self,b):
        view=self.backend_view
        need(view.initialization is not None and same(b['initialization'],view.initialization.pin),
             'actual original initialization before H admission poll')
        snapshot=view._prior(b['snapshot'],'BackendAttempt')
        need(snapshot.body['snapshot_stage']=='postinitialization','actual initial ready snapshot')
        now,_=self._now('generation')
        if view.admission is None:
            from .backend_host_native_evidence import HBackendNativeEvidence
            if view.host_admission_owner is None:
                observer=HBackendNativeEvidence(view)
                observer.observe_initialization()
            need(type(view.host_admission_owner)is HBackendNativeEvidence,'fixed actual H native observer')
            if not view.host_admission_owner.initialization_complete:
                return {'schema':'four_pending_backend_admission_v1','initialization':view.initialization.pin,
                        'observed_ns':now,'state':'pending'}
        need(view.host_admission_owner is not None,'wire admission cannot replace actual independent H observer')
        return {'schema':'four_completed_backend_admission_v1','admission':view.admission.pin,
                'host_observation':view.host_observation.pin,'initialization':view.initialization.pin,'state':'admitted'}
    def _admission_object(self,b):
        sequence=b['completed_reply_sequence'];need(sequence<self.sequence and sequence<len(self.history),
             'earlier actual completed admission reply, never own/future sequence')
        prior=self.history[sequence]
        need(prior.complete and prior.kind=='PollBackendAdmissionV1' and
             prior.reply['schema']=='four_completed_backend_admission_v1',
             'actual fully sent admission reply, no pending/failed delivery')
        view=self.backend_view
        cap=view.admission if b['kind']=='BackendAdmissionAck'else view.host_observation
        need(type(cap)is CapturedRecord and view.host_admission_owner is not None,'actual independent H admission object')
        key=(sequence,b['kind']);offset=self.admission_offsets.get(key,0)
        need(key not in self.admission_delivered and b['offset']==offset,'one contiguous original admission delivery')
        proto={'schema':'four_admission_object_chunk_v1','capture':cap.pin,'completed_reply_sequence':sequence,
          'final':False,'kind':cap.kind,'offset':offset,'raw_hex':''}
        outer={'schema':'four_packet_v1','direction':'host_to_worker','sequence':self.sequence,
          'previous_ack':self.previous_ack,'context':self.activation.context,'source_policy':self.activation.policy.pin,'payload':proto}
        count=min(16384,max(0,(self.activation.packet_limit-len(canonical(outer,self.activation.packet_limit)))//2))
        need(count>0,'complete exact framed admission chunk fits original cap')
        raw=cap.raw[offset:offset+count];need(raw,'no repeated or empty admission chunk')
        after=offset+len(raw);self.admission_offsets[key]=after
        if after==len(cap.raw):self.admission_delivered.add(key)
        proto.update(raw_hex=raw.hex(),final=after==len(cap.raw));return proto
    def _finish(self,b):
        view=self.backend_view
        if b['closure']is not None:
            need(view.closure is not None and same(b['closure'],view.closure.pin),'same actually captured backend closure')
        if b['terminal_snapshot']is not None:
            cap=view._prior(b['terminal_snapshot'],'BackendAttempt');need(cap.body['snapshot_stage']=='terminal','actual terminal snapshot')
        if b['disposition']=='complete':
            need(b['local_failure']is None and view.closure is not None and view.closure.body['status']=='complete',
                 'complete worker claim only with complete original closure evidence')
            from .backend_host_native_evidence import HBackendNativeEvidence
            need(type(view.host_admission_owner)is HBackendNativeEvidence,'actual earlier H initialization observation owner')
            view.host_admission_owner.observe_closure()
        now,_=self._now('shutdown')
        return {'schema':'four_finish_worker_ack_v1','outside_host_closure_required':True,
                'received_ns':now,'request_sequence':self.sequence}

    def close_transport_once(self):
        # No later parse, budget or clock gate can prevent independent original
        # endpoint/alias close attempts. This is not server/subtree completion.
        try:return self.channel.close_all()
        except BaseException as error:self.retain(error,'close_transport');return False
