"""Actual original-H custody of fixed worker publications.

Received worker evidence is never an independent H observation or native
qualification. This view is registered on the original attempt before work.
It is not a worker BackendAttemptHandle transported across exec.
"""
import hashlib
from .common import need, same, DependencyUnavailable
from .backend_capture import CapturedRecord
from .precommit_records import validate_type

_VIEW=object()
_ROLES=('server_executable','model_gguf','template','tokenizer_source','renderer_source')
_SITES={
 'base':('BackendAttemptBase','backend_attempt_base'),
 'snapshot':('BackendAttempt','backend_attempt_snapshot'),
 'artifact':('ArtifactObservation','artifact'),'environment':('EnvironmentObservation','backend_environment'),
 'process':('ProcessObservation','backend_process'),'socket':('SocketObservation','backend_socket'),
 'peer':('PeerCredentialObservation','backend_peer'),'http_request':('BackendHttpRequest','http_request'),
 'http_raw':('RawHttpResponse','http_raw'),'http_health':('ParsedHealth','http_health'),
 'http_slots':('ParsedSlots','http_slots'),'http_completion':('ParsedCompletion','http_completion'),
 'http_rejected':('RejectedResponse','http_rejected'),'source_initialization':('SourceInitializationProof','backend_source_initialization'),
 'initialization':('BackendInitializationObservation','backend_initialization'),
 'exchange':('BackendExchangeObservation','backend_exchange'),'agent_completion':('AgentCompletion','agent_completion'),
 'signal':('SignalObservation','backend_signal'),'exit':('ExitObservation','backend_exit'),
 'streams':('StreamClosureObservation','backend_streams'),'socket_closure':('SocketClosureObservation','backend_socket_closure'),
 'subtree':('SubtreeObservation','backend_subtree'),'closure':('BackendClosure','backend_closure'),
 'rendered_template':('RenderedTemplateObservation','rendered_template'),
 'completion_request':('CompletionRequest','completion_request'),
 'agent_input_product':('AgentInputProductV1','agent_input_product')}

class HBackendView:
    def __init__(self,token,receiver):
        need(token is _VIEW,'fixed original H receiver view constructor')
        self.receiver=receiver;self.attempt=receiver.attempt;self.owner=self.attempt.owner
        need(self.attempt.backend is None,'one original H backend view')
        self.base=None;self.initialization=None;self.admission=None;self.host_observation=None;self.closure=None
        self.host_admission_owner=None;self.host_closure_owner=None
        self.raw_first=None;self.secondaries=[];self.captures={};self.snapshots=[]
        self.semantic_requests=[];self.exchanges=[];self.agent_completions=[]
        self.selected_artifact_sources_v3={}
        self.attempt.backend=self
    def require_original(self):
        from .backend_host_receiver import HChannelReceiver
        need(type(self.receiver)is HChannelReceiver and self.receiver.backend_view is self and
             self.receiver.attempt is self.attempt and self.attempt.backend is self,
             'same registered source-owned H view and original receiver')
        self.attempt.require_live_original()
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
    def _prior(self,pin,kind=None):
        for cap in self.captures.values():
            if same(cap.pin,pin):
                need(kind is None or cap.kind==kind,'exact earlier publication type')
                return cap
        for cap in self.receiver.activation.objects:
            if same(cap.pin,pin):
                need(kind is None or cap.kind==kind,'exact earlier bootstrap capture type')
                return cap
        if self.admission is not None and same(self.admission.pin,pin):return self.admission
        need(False,'actual earlier same-context capture, never a future/foreign Pin')
    def publication_path(self,site,ordinal,body):
        need(site in _SITES and type(ordinal)is int and ordinal>=0,'fixed source publication selector')
        if site=='artifact':
            need(ordinal<len(_ROLES) and body['role']==_ROLES[ordinal],'fixed five-role artifact order')
            return 'worker/artifact_'+_ROLES[ordinal]+'.json'
        if site.startswith('http_'):
            endpoint=body['endpoint'];need(endpoint in ('health','slots','completion'),'closed HTTP endpoint')
            need(body['ordinal']==ordinal,'actual endpoint ordinal')
            if site in ('http_health','http_slots','http_completion'):
                need(endpoint==site[5:],'selected parser endpoint')
                suffix='parsed'
            else:suffix={'http_request':'request','http_raw':'raw','http_rejected':'rejected'}[site]
            return 'worker/http_'+endpoint+'_'+str(ordinal)+'_'+suffix+'.json'
        if site in ('snapshot','process','exchange','agent_completion','rendered_template','completion_request','agent_input_product'):
            limit=3 if site=='snapshot' else 2 if site=='process' else self.receiver.maximum_generation_requests
            need(ordinal<limit,'original finite source slot')
            return 'worker/'+_SITES[site][1]+'_'+str(ordinal)+'.json'
        need(ordinal==0,'singleton publication has one original ordinal')
        return 'worker/'+_SITES[site][1]+'.json'
    def validate_publication(self,site,ordinal,body):
        self.require_original();need(self.raw_first is None,'no view continuation after first error')
        kind=_SITES[site][0]
        if site=='agent_input_product':
            from .backend_native_v3_codec import validate_native_type
            validate_native_type(kind,body)
            # The schema/site is selected, but the actual independent full
            # public-exposure and transcript occurrence producer is absent.
            raise DependencyUnavailable('agent_input_product_v1_original_producer')
        validate_type(kind,body)
        a=self.attempt;c=a.pair.contract;act=self.receiver.activation
        if 'condition'in body:need(body['condition']==a.condition,'same actual original arm')
        if site=='base':
            need(self.base is None,'one original backend base')
            expected={'worker_attempt':a.prefix_capture.pin,'worker_launch_ack':a.launch_ack.pin,
              'request':a.arm.request.pin,'preparation':a.arm.state_capture.pin,
              'workspace':a.arm.workspace_capture.pin,'profile':c.backend_pin,
              'pair_id':act.context['pair_id'],'nonce':act.context['launch_nonce'],
              'initialization_deadline_ns':act.J,'generation_deadline_ns':act.G,'shutdown_deadline_ns':act.R}
            for key,value in expected.items():need(same(body[key],value),'exact original backend base identity/deadline')
        else:
            need(self.base is not None,'earlier captured base before dependent publication')
            if 'attempt'in body:need(same(body['attempt'],self.base.pin),'same earlier BackendAttemptBase')
        if site=='snapshot':
            need(ordinal==len(self.snapshots) and body['snapshot_ordinal']==ordinal,'three ordered actual snapshots')
            need(same(body['base_attempt'],self.base.pin),'same base snapshot ancestry')
            need(same(body['previous_snapshot'],None if not self.snapshots else self.snapshots[-1].pin),'earlier snapshot only')
            for key in ('worker_attempt','worker_launch_ack','request','preparation','workspace','profile','pair_id','nonce',
                        'initialization_deadline_ns','generation_deadline_ns','shutdown_deadline_ns'):
                need(same(body[key],self.base.body[key]),'snapshot preserves full original base')
            for key in ('identity_observation','group_observation'):
                if body[key]is not None:self._prior(body[key])
        elif site=='process':
            need(body['subject']=='server' and body['producer']=='worker','worker-reported actual server observation')
            need(same(body['group_identity'],a.process.identity),'group owner is original worker identity, not inode/pgrp')
        elif site=='subtree':
            need(body['scope']=='server_subtree' and body['producer']=='worker','worker server subtree only, not H whole arm')
        elif site=='artifact':
            need(body['observed_bytes']==body['selected']['bytes'] and body['observed_sha256']==body['selected']['sha256'],
                 'complete selected artifact evidence extent/digest; qualification still independent')
        elif site=='rendered_template':
            need(self.admission is not None and ordinal==len(self.semantic_requests),'admitted fresh semantic generation')
            from .worker_selected_source_v3 import require_completed_render_ack_v3
            effect=require_completed_render_ack_v3(self,ordinal)
            expected=[self.base.pin,body['input_capture'],body['selected_input_ABI'],
                      body['selected_template'],body['selected_renderer'],self.admission.pin]
            need(effect.intent['stage']=='generation' and effect.intent['deadline_ns']==act.G and
                 same(effect.intent['prior_captures'],expected),
                 'same six source-typed operands and original acknowledged render occurrence')
            need(body['ordinal']==ordinal and effect.grant.body['issued_ns']<=body['observed_ns']<=act.G,
                 'actual render follows its original grant within unchanged generation cutoff')
            need(body['prompt_utf8_bytes']==len(body['prompt'].encode('utf8')) and
                 body['prompt_sha256']==hashlib.sha256(body['prompt'].encode('utf8')).hexdigest(),'exact source-return prompt bytes')
        elif site=='completion_request':
            need(self.admission is not None and ordinal==len(self.semantic_requests) and body['request_ordinal']==ordinal,
                 'one new semantic request after original H admission')
            rendered=self._prior(body['rendered_template_observation'],'RenderedTemplateObservation').body
            need(rendered['ordinal']==ordinal and body['prompt']==rendered['prompt'] and
                 same(body['sampling'],c.backend['sampling']) and same(body['backend_admission'],self.admission.pin),
                 'same original renderer, fixed immutable sampler and original admission')
        elif site=='http_request':
            if body['endpoint']=='completion':
                need(ordinal<len(self.semantic_requests) and same(body['completion_request'],self.semantic_requests[ordinal].pin),
                     'exact earlier fresh semantic request')
            else:need(body['completion_request']is None,'no semantic request for initialization probes')
        elif site=='http_raw':self._prior(body['request'],'BackendHttpRequest')
        elif site=='http_completion':
            need(ordinal<len(self.semantic_requests) and same(body['request'],self.semantic_requests[ordinal].pin),
                 'ParsedCompletion names semantic request, never wire request')
            self._prior(body['raw'],'RawHttpResponse')
        elif site in ('http_health','http_slots'):self._prior(body['raw'],'RawHttpResponse')
        elif site=='initialization':
            need(self.initialization is None and not self.semantic_requests and body['observed_ready_ns']<=act.J,
                 'one initial observation before generation and original J')
            for key,typ in (('health_response','ParsedHealth'),('initial_slots_response','ParsedSlots'),
                            ('source_initialization_proof','SourceInitializationProof'),('spawn_observation','ProcessObservation'),
                            ('same_group_observation','SubtreeObservation'),('socket_observation','SocketObservation'),
                            ('peer_credential_observation','PeerCredentialObservation'),('environment_observation','EnvironmentObservation'),
                            ('executable_observation','ArtifactObservation')):self._prior(body[key],typ)
            for pin in body['artifact_observations']:self._prior(pin,'ArtifactObservation')
            need(same(body['worker_identity'],a.process.identity),'same actual original worker')
        elif site=='exchange':
            need(ordinal==len(self.exchanges) and ordinal<len(self.semantic_requests),'original ordered exchange')
            need(same(body['request'],self.semantic_requests[ordinal].pin),'same semantic exchange request')
            if body['response']is not None:self._prior(body['response'],'ParsedCompletion')
        elif site=='agent_completion':
            need(ordinal==len(self.agent_completions) and ordinal<len(self.exchanges),'actual completed exchange prefix')
            need(same(body['exchange'],self.exchanges[ordinal].pin),'same earlier exchange')
            self._prior(body['parsed_response'],'ParsedCompletion')
        elif site=='closure':
            need(self.closure is None,'one actual server closure publication')
            need(body['requests']==[x.pin for x in self.semantic_requests],'all original semantic requests including failures')
            if body['status']=='complete':
                need(self.admission is not None and same(body['admission'],self.admission.pin) and
                     self.initialization is not None and same(body['initialization'],self.initialization.pin),
                     'complete claim joins actual H admission and original initialization')
                for key,typ in (('exit_observation','ExitObservation'),('signal_observation','SignalObservation'),
                                ('group_observation','SubtreeObservation'),('socket_closure','SocketClosureObservation'),
                                ('stream_closure','StreamClosureObservation')):self._prior(body[key],typ)
        return self.publication_path(site,ordinal,body)
    def accept_completed(self,site,ordinal,capture):
        need(type(capture)is CapturedRecord and capture.owner is self.owner and capture.kind==_SITES[site][0],
             'actual original H publisher return, never worker Pin alone')
        path=self.validate_publication(site,ordinal,capture.body)
        need(path not in self.captures,'no duplicate actual source publication slot')
        self.captures[path]=capture
        if site=='base':self.base=capture
        elif site=='initialization':self.initialization=capture
        elif site=='closure':self.closure=capture
        elif site=='snapshot':self.snapshots.append(capture)
        elif site=='completion_request':self.semantic_requests.append(capture)
        elif site=='exchange':self.exchanges.append(capture)
        elif site=='agent_completion':self.agent_completions.append(capture)
    def require_completed(self):
        self.require_original();r=self.receiver
        need(self.raw_first is None and r.raw_first is None and not r.poisoned and r.pending is None and
             r.publication is None and r.effect is None and r.finished,'original complete receiver with no unresolved operation')
        need(all(type(c)is CapturedRecord and c.owner is self.owner for c in
                 (self.base,self.initialization,self.admission,self.host_observation,self.closure)),
             'all actual same-owner backend evidence and original H admission')
        from .backend_host_native_evidence import HBackendNativeEvidence
        need(type(self.host_admission_owner)is HBackendNativeEvidence and
             self.host_closure_owner is self.host_admission_owner and self.host_admission_owner.view is self,
             'actual source-owned independent H native observation owner, never wire proof')
        self.host_admission_owner.require_completed()
        need(self.owner.parent.first_raw is None and not self.owner.parent.unknown,
             'no whole success while original raw errors or aggregate unknowns remain')
        return self
