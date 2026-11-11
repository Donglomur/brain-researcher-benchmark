"""Fixed worker bootstrap, source-bound captures and original stage clocks."""
from .common import need
from .worker_context_records_v3 import body, encode, decode, pinned, equal
from .worker_context_schema_v3 import (BOOTSTRAP_ROOT_KIND, BOOTSTRAP_ROOT_MIN,
    BOOTSTRAP_ROOT_MAX, require_bootstrap_roster_v3)
from .worker_channel_v3 import begin_channel, completed_capture

_CONTEXT = object()

class WorkerContextProxy:
    def __init__(self,token,channel):
        need(token is _CONTEXT and channel.context is None,'fixed actual bootstrap source factory')
        self.channel=channel;self.context_identity=None;self.grant_capture=None
        self.bootstrap_objects=[];self.object_table=None;self.captures=[];self.source_policy=None
        self.original_deadlines={};self.meter=None;self.publisher=None
        self.local_raw_first=None;self.ordered_local_secondaries=[];self.poisoned=False;self.activated=False
        self.backend=None;self.admission_pending=None;self.admission_captures=None;self.finish_pending=None
        self.logical_limit=channel.endpoint.maximum_logical_record
        self.maximum_publications=channel.endpoint.maximum_publications
        need(type(self.logical_limit) is int and 0<self.logical_limit<=9007199254740991 and
             type(self.maximum_publications) is int and self.maximum_publications>0,
             'actual earlier admitted complete record/publication bounds')
        channel.context=self

    def retain(self,error):
        if self.local_raw_first is None:self.local_raw_first=error
        elif error is not self.local_raw_first:self.ordered_local_secondaries.append(error)
        self.poisoned=True

    def require_active(self):
        if self.local_raw_first is not None:raise self.local_raw_first
        need(self.activated and not self.poisoned and not self.channel.poisoned and
             self.channel.endpoint.protocol is self.channel and self.channel.context is self,
             'actual activated original worker context without prior failure')
        self.channel.endpoint.require_original()

    def deadline(self,stage):
        need(stage in self.original_deadlines,'fixed original worker stage')
        return self.original_deadlines[stage]

    def bootstrap(self,kind):
        found=[x for x in self.bootstrap_objects if x.kind==kind]
        need(len(found)==1,'one exact fixed bootstrap kind')
        return found[0]

    def _receive_object(self,row):
        need(type(row) is dict and any(x is row for x in self.object_table['rows']),
             'only an actual retained original table row')
        descriptor=row['capture'];total=descriptor['bytes']
        need(0<total<=self.logical_limit,'full selected object fits original logical bound')
        offset=0;parts=[];last=None
        while offset<total:
            request=body('BootstrapObjectRequestV1',table=self.grant_capture.completed_reply['payload']['object_table'],
                         ordinal=row['ordinal'],offset=offset)
            pending=self.channel.request('BootstrapObjectRequestV1','bootstrap_object',request,
                                         ('BootstrapObjectChunkV1',),self.deadline('bootstrap'))
            reply=pending.completed_reply['payload']
            need(equal(reply['table'],request['table']) and equal(reply['capture'],descriptor) and
                 reply['kind']==row['kind'] and reply['ordinal']==row['ordinal'] and reply['offset']==offset,
                 'same exact selected table object and contiguous offset')
            raw=bytes.fromhex(reply['raw_hex']);need(0<len(raw)<=16384 and len(raw)<=total-offset,
                                                  'positive bounded original object chunk')
            need(reply['final']==(offset+len(raw)==total),'exact original final chunk marker')
            parts.append(raw);offset+=len(raw);last=pending
            self.channel.acknowledge(pending)
        raw=b''.join(parts);pinned(raw,descriptor);decode(row['kind'],raw,self.logical_limit)
        result=completed_capture(self,last,row['kind'],raw,descriptor,'bootstrap_delivery',row)
        self.bootstrap_objects.append(result)
        return result

    def _join_bootstrap(self):
        get=lambda kind:self.bootstrap(kind)
        grant=self.grant_capture.completed_reply['payload'];c=self.context_identity
        ack=get('WorkerLaunchAck');request=get('DevelopmentRequest');prep=get('InitialStatePreparation')
        workspace=get('WorkspaceObservation');local=get('LocalBackendProfile');artifacts=get('LocalArtifactSelection')
        policy=get('NativeContextPolicyV2');selection=get('NativeArtifactRootSelectionV1')
        bundle=get('NativeArtifactRootBundleV1');entry=get('BootstrapEntrySelectionV1')
        agent=get('NativeAgentPolicyV4');input_selection=get('AgentInputSelectionV1');profile=get('NativeDevelopmentProfileV3')
        reservation=get('ChannelBudgetReservationV1');opened=get('ChannelOpenObservationV1');peer=get('ChannelPeerObservationV1')
        a=ack.body;r=request.body;p=prep.body;w=workspace.body;l=local.body;t=artifacts.body
        pol=policy.body;sel=selection.body;bu=bundle.body;e=entry.body;ag=agent.body;pr=profile.body
        re=reservation.body;op=opened.body;pe=peer.body
        def same(x,y,label):need(equal(x,y),label)
        same(policy.pin,self.source_policy,'actual delivered policy Pin')
        same(ack.pin,grant['worker_launch_ack'],'original worker launch acknowledgement')
        for key in ('condition','pair_id','source_admission'):
            same(a[key],c[key],'same original context '+key)
        same(a['original_attempt'],c['original_attempt'],'same original worker attempt')
        same(a['nonce'],c['launch_nonce'],'same original launch nonce')
        same(a['worker_identity'],grant['worker'],'actual original worker identity')
        same(a['request'],request.pin,'actual earlier development request')
        need(a['original_start_ns']==grant['original_S_ns'] and a['run_deadline_ns']==grant['R_ns'] and
             a['evidence_deadline_ns']==grant['E_ns'],'original start/run/evidence clocks')
        for obj in (r,p,w,re,op):same(obj['condition'],c['condition'],'same original arm')
        same(p['pair_id'],c['pair_id'],'same preparation pair');same(w['pair_id'],c['pair_id'],'same workspace pair')
        same(p['workspace'],workspace.pin,'actual preparation workspace capture')
        same(r['workspace_identity'],w['filesystem_identity'],'same original workspace identity')
        same(p['backend_profile'],local.pin,'original selected backend profile')
        same(p['artifact_selection'],artifacts.pin,'original selected artifacts')
        same(l['artifact_selection'],artifacts.pin,'same profile artifacts')
        same(p['recipe'],l['initial_state_recipe'],'same initial-state recipe')
        same(r['agent_policy'],agent.pin,'current native agent selection')
        same(r['development_profile'],profile.pin,'current native development selection')
        same(pr['agent_policy'],agent.pin,'profile selects current native agent')
        same(pr['native_context_policy'],policy.pin,'profile same native policy')
        same(ag['native_context_policy'],policy.pin,'agent same native policy')
        same(ag['local_backend'],local.pin,'agent same local backend')
        same(ag['agent_input_selection'],input_selection.pin,'actual complete selected agent input body')
        ai=input_selection.body
        same(ai['template'],t['template_file'],'same selected original template identity')
        same(ai['renderer_source'],t['template_renderer'],'same selected original renderer identity')
        need(all(ai[k]in ag['source_closure']for k in
                 ('input_ABI','producer_source','protocol_source','renderer_source','renderer_bound_source')),
             'complete independently selected input and enforcing source closure')
        same(pr['entry_argv'],ag['entry_argv'],'one exact current source argv')
        same(pr['environment'],ag['environment'],'one exact environment selection')
        same(ag['entry_argv'],[e['interpreter_absolute'],'-I',e['entry_absolute']],'fixed isolated interpreter entry argv')
        same(l['worker_entry_source'],e['entry_script'],'actual current fixed worker entry')
        same(pol['bootstrap_entry'],entry.pin,'earlier selected entry')
        same(pol['artifact_roots'],selection.pin,'earlier selected artifact roots')
        same(pol['original_source_admission'],c['source_admission'],'same original source admission')
        same(pr['source_admission'],c['source_admission'],'same profile source admission')
        same(sel['artifact_selection'],artifacts.pin,'root selection current artifacts')
        same(sel['backend_profile'],local.pin,'root selection current profile')
        same(bu['selection'],selection.pin,'actual root bundle selection')
        same(bu['source_admission'],c['source_admission'],'actual root bundle source')
        same(bu['host'],grant['host'],'same original host root observer')
        expected=[('server_executable',l['server_executable']),('model_gguf',t['model_gguf']),
                  ('template',t['template_file']),('tokenizer_source',t['tokenizer_source']),('renderer_source',t['template_renderer'])]
        need([(x['role'],x['selected']) for x in sel['roles']]==expected,'five exact ordered artifact roles')
        roots=[x for x in self.bootstrap_objects if x.kind==BOOTSTRAP_ROOT_KIND]
        ids=[x.body['root_id'] for x in roots]
        need(ids==sorted(ids) and len(ids)==len(set(ids)) and BOOTSTRAP_ROOT_MIN<=len(ids)<=BOOTSTRAP_ROOT_MAX,'ordered unique actual roots')
        same(bu['roots'],[x.pin for x in roots],'bundle contains exact earlier root captures')
        need({x['root_id'] for x in sel['roles']}<=set(ids),'every artifact uses selected actual root')
        for root in roots:
            value=root.body;same(value['source_admission'],c['source_admission'],'same actual root source')
            same(value['host'],grant['host'],'same actual root host')
            same(value['root_policy'],sel['root_policy'],'same selected root policy')
        same(re['context_policy'],policy.pin,'same earlier channel reservation policy')
        same(re['original_owner_binding'],a['owner_binding'],'same original H reservation owner')
        same(re['schedule'],r['schedule'],'same original matched schedule')
        need(re['original_evidence_deadline_ns']==grant['E_ns'] and
             re['packet_limit']==self.channel.packet_limit and re['maximum_sequences']==self.channel.sequence_limit and
             re['logical_record_limit']==self.logical_limit,'exact earlier reservation limits, no worker replacement')
        same(reservation.pin,grant['channel_reservation'],'actual channel reserve capture')
        same(op['reservation'],reservation.pin,'actual channel open reserve')
        same(op['policy'],policy.pin,'actual channel open policy')
        same(op['host'],grant['host'],'same actual channel host')
        same(peer.pin,grant['channel_peer'],'actual peer capture')
        same(pe['channel_open'],opened.pin,'actual peer channel')
        same(pe['context'],c,'actual peer context');same(pe['worker'],grant['worker'],'actual peer worker')
        same(pe['host'],grant['host'],'actual peer host')
        # This fixed method belongs to the exact native endpoint class. It must
        # check actual namespace/group/clock/source observations, never a hook.
        self.channel.endpoint.verify_bootstrap_objects(self.bootstrap_objects)
        need(self.channel.packet_limit<=min(65536,pr['maximum_request_bytes'],pr['maximum_metadata_bytes']),
             'earlier original reservation fits every selected profile cap; no widening')
        self.maximum_publications=min(self.maximum_publications,pr['maximum_files'])
        need(self.maximum_publications>0,'positive remaining original publication bound')

def start_worker_context(endpoint):
    channel=begin_channel(endpoint);context=WorkerContextProxy(_CONTEXT,channel)
    try:
        pending=channel.request('BootstrapHelloV3','fixed_entry',endpoint.hello_body(),('WorkerBootstrapGrantV1',),endpoint.original_bootstrap_deadline)
        reply=pending.completed_reply;grant=reply['payload'];table=grant['object_table_body']
        pinned(encode('BootstrapObjectTableV1',table,context.logical_limit),grant['object_table'])
        need(equal(table['context'],grant['context']) and
             equal(table['source_admission'],grant['context']['source_admission']),'same original table source/context')
        rows=require_bootstrap_roster_v3(table['rows'])
        S=grant['original_S_ns'];J=grant['J_ns'];G=grant['G_ns'];R=grant['R_ns'];E=grant['E_ns']
        need(S<=grant['issued_ns']<=J<=G<R<=E and J<=endpoint.original_bootstrap_deadline,
             'original bounded bootstrap/generation/run/evidence clock order')
        context.context_identity=grant['context'];context.source_policy=reply['source_policy']
        channel.context_identity=context.context_identity;channel.source_policy=context.source_policy
        context.original_deadlines={'bootstrap':J,'initialization':J,'generation':G,'shutdown':R}
        context.object_table=table;context.grant_capture=pending;channel.grant_pending=pending
        channel.acknowledge(pending)
        for row in rows:context._receive_object(row)
        context._join_bootstrap()
        from .worker_meter_v3 import WorkerArmMeterProxy
        from .worker_publication_v3 import WorkerCanonicalPublisher
        context.meter=WorkerArmMeterProxy._from_context(context)
        context.publisher=WorkerCanonicalPublisher._from_context(context)
        context.activated=True
        return context
    except BaseException as error:
        context.retain(error);channel.retain(error,channel.pending)
        raise
