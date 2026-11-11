"""Composite effect grants and truthful original worker observation custody.

This is deliberately not EarlyResources/PartitionMeter and has no .charge shim.
Concrete native callers must reserve one complete fixed operation, enter once,
retain actual returns, and report once. No generic callable executor is provided.
"""
from .common import need
from .worker_context_records_v3 import body, encode, equal, validate
from .worker_channel_v3 import completed_capture

_METER=object();_EFFECT=object()
_DIMENSIONS=('read_bytes','write_bytes','work_units','process_starts','cpu_ns','wall_ns','retained_bytes')
_FAILURES={
    'artifact_open':'read_failure','artifact_read':'read_failure','proc_open':'read_failure',
    'proc_read':'read_failure','namespace_read':'read_failure','group_open':'read_failure',
    'group_enumerate':'read_failure','group_read':'read_failure','socket_observe':'observation_failure',
    'server_spawn':'spawn_failure','http_connect':'observation_failure','http_send':'write_failure',
    'http_receive':'read_failure','server_signal':'cleanup_failure','server_wait':'cleanup_failure',
    'stream_read':'read_failure','socket_remove':'cleanup_failure','descriptor_close':'cleanup_failure',
    'local_encode':'encode_failure','local_parse':'decode_failure','render_template':'encode_failure',
}

class WorkerEffectAttempt:
    __slots__=('meter','site','stage','ordinal','maximum','deadline','prior_captures','pending',
               'grant','entered','finished','known_read_bytes','known_write_bytes','known_processes',
               'unknown_dimensions','raw_first','secondaries','observation_pending','reported')
    def __init__(self,token,meter,site,stage,ordinal,maximum,deadline,prior):
        need(token is _EFFECT,'actual source-owned composite effect attempt')
        self.meter=meter;self.site=site;self.stage=stage;self.ordinal=ordinal;self.maximum=dict(maximum)
        self.deadline=deadline;self.prior_captures=prior;self.pending=None;self.grant=None
        self.entered=False;self.finished=False;self.known_read_bytes=0;self.known_write_bytes=0;self.known_processes=[]
        self.unknown_dimensions=[];self.raw_first=None;self.secondaries=[];self.observation_pending=None;self.reported=False
    def require_current(self):
        need(self.meter.current_effect is self and self.grant is not None and not self.reported,
             'same actual outstanding granted effect')
    def enter(self):
        self.require_current();need(not self.entered and self.raw_first is None,'one original effect attempt')
        self.entered=True  # Latch before fallible original time/effect checks.
        try:self.meter.context.channel.endpoint.now(self.deadline)
        except BaseException as error:self.fail(error,());raise
        return self
    def acknowledge_read(self,raw):
        self.require_current();need(self.entered and not self.finished and type(raw) is bytes,'actual returned read bytes')
        self.known_read_bytes+=len(raw)
        need(self.known_read_bytes<=self.maximum['read_bytes'],'actual returned prefix within original read ceiling')
    def acknowledge_write(self,count,requested):
        self.require_current();need(self.entered and not self.finished and type(requested) is bytes and
             type(count) is int and 0<=count<=len(requested),'actual returned bounded write count')
        self.known_write_bytes+=count
        need(self.known_write_bytes<=self.maximum['write_bytes'],'actual written prefix within original write ceiling')
    def acknowledge_process(self,process):
        self.require_current();need(self.entered and not self.finished and process is not None and
             not any(x is process for x in self.known_processes),'actual distinct returned process occurrence')
        self.known_processes.append(process)
        need(len(self.known_processes)<=self.maximum['process_starts'],'actual process prefix within original ceiling')
    def fail(self,error,unknown_dimensions):
        self.require_current()
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        for dimension in unknown_dimensions:
            need(dimension in _DIMENSIONS,'closed unknown dimension')
            if dimension not in self.unknown_dimensions:self.unknown_dimensions.append(dimension)
        # Retain local first without erasing the live grant needed for the one
        # diagnostic observation. It cannot authorize another ordinary effect.
        self.meter.retain(error)
    def finish(self):
        self.require_current();need(self.entered and not self.finished,'one actual original effect completion')
        self.finished=True
        try:self.meter.context.channel.endpoint.now(self.deadline)
        except BaseException as error:self.fail(error,());raise
        return self

class WorkerArmMeterProxy:
    __slots__=('context','same_channel','last_acknowledged_cost_prefix','current_effect',
               'local_raw_first','ordered_secondaries','attempts','effect_ordinals')
    def __init__(self,token,context):
        need(token is _METER,'fixed actual context arm proxy')
        self.context=context;self.same_channel=context.channel
        self.last_acknowledged_cost_prefix=context.grant_capture.completed_reply['payload']['cost_prefix']
        self.current_effect=None;self.local_raw_first=None;self.ordered_secondaries=[];self.attempts=[];self.effect_ordinals={}
    @classmethod
    def _from_context(cls,context):
        from .worker_context_v3 import WorkerContextProxy
        need(type(context) is WorkerContextProxy and context.channel.context is context and context.meter is None,
             'same exact complete bootstrap context')
        return cls(_METER,context)
    def retain(self,error):
        if self.local_raw_first is None:self.local_raw_first=error
        elif error is not self.local_raw_first:self.ordered_secondaries.append(error)
        self.context.retain(error)
    def acknowledged_prefix(self):
        # Return a parsed copy of only the earlier acknowledged original H
        # observation; future control/cleanup costs are not invented here.
        from .backend_json import canonical,parse
        raw=canonical(self.last_acknowledged_cost_prefix,self.context.logical_limit)
        return parse(raw,len(raw),maximum_depth=64,maximum_members=len(raw),maximum_string_bytes=len(raw))
    def check_stage(self,stage):
        context=self.context;context.require_active()
        need(self.current_effect is None,'no unrelated request while an original effect remains unresolved')
        try:
            pending=self.same_channel.request('CheckRequestV1','check_stage',body('CheckRequestV1',stage=stage),
                                             ('CheckAckV1',),context.deadline(stage))
            ack=pending.completed_reply['payload']
            need(ack['request_sequence']==pending.sequence and ack['stage']==stage and
                 ack['original_deadline_ns']==context.deadline(stage) and ack['observed_ns']<=context.deadline(stage),
                 'same original stage and unchanged deadline')
            self.same_channel.acknowledge(pending);self.last_acknowledged_cost_prefix=ack['cost_prefix']
            need(ack['admissible'],'actual original residual admissibility refused')
            return ack['observed_ns']
        except BaseException as error:
            self.retain(error);self.same_channel.retain(error,self.same_channel.pending);raise
    def reserve_effect(self,site,stage,maximum,prior=()):
        context=self.context;context.require_active()
        need(self.current_effect is None and self.local_raw_first is None and
             context.publisher.pending_publication is None,'one composite original effect, not dimension shims')
        validate('EffectSite',site);validate('ResourceVector',maximum)
        from .worker_channel_v3 import require_capture
        need(type(prior) is tuple and len(prior)<=64,'finite exact earlier capture tuple')
        ordinal=self.effect_ordinals.get(site,0)
        if site=='render_template':
            from .worker_selected_source_v3 import require_worker_render_operands_v3
            require_worker_render_operands_v3(context,stage,ordinal,prior)
        else:
            # Unrelated effects keep exact capture-only semantics. A selected
            # artifact descriptor is not a canonical capture or native result.
            for capture in prior:require_capture(capture,context)
        self.effect_ordinals[site]=ordinal+1
        deadline=context.deadline(stage)
        attempt=WorkerEffectAttempt(_EFFECT,self,site,stage,ordinal,maximum,deadline,prior)
        self.current_effect=attempt;self.attempts.append(attempt) # Before packet/clock/encoding.
        try:
            intent=body('EffectIntentV1',deadline_ns=deadline,maximum=maximum,ordinal=ordinal,
                        prior_captures=[x.pin for x in prior],site=site,stage=stage)
            pending=self.same_channel.request('EffectIntentV1',site,intent,('EffectGrantDeliveryV2',),deadline)
            attempt.pending=pending;delivery=pending.completed_reply['payload'];grant=delivery['grant_body']
            need(equal(grant['context'],context.context_identity) and equal(grant['intent'],intent) and
                 grant['request_sequence']==pending.sequence and grant['issued_ns']<=deadline,
                 'same complete original intent/context/sequence/deadline grant')
            need(grant['issued_ns']>=context.grant_capture.completed_reply['payload']['original_S_ns'],
                 'grant in original worker clock interval')
            need(all(old is attempt or old.grant is None or
                     old.grant.body['original_ledger_slot']!=grant['original_ledger_slot'] for old in self.attempts),
                 'distinct original H ledger occurrence; no reused grant slot')
            raw=encode('EffectGrantV1',grant,context.logical_limit)
            from .worker_context_records_v3 import pinned
            pinned(raw,delivery['grant'])
            self.same_channel.acknowledge(pending)
            attempt.grant=completed_capture(context,pending,'EffectGrantV1',raw,delivery['grant'],
                                            'effect_grant_delivery',pending)
            self.last_acknowledged_cost_prefix=grant['cost_prefix']
            return attempt
        except BaseException as error:
            if attempt.raw_first is None:attempt.raw_first=error
            elif error is not attempt.raw_first:attempt.secondaries.append(error)
            self.retain(error);self.same_channel.retain(error,self.same_channel.pending,uncertain=True);raise
    def observe_effect(self,attempt):
        need(type(attempt) is WorkerEffectAttempt and attempt.meter is self and self.current_effect is attempt and
             attempt.grant is not None and not attempt.reported and attempt.observation_pending is None,
             'one exact original outstanding effect observation')
        need(attempt.finished or attempt.raw_first is not None,'no invented success before actual caller completion')
        state='complete';failure=None
        if attempt.raw_first is not None:
            state='unknown' if attempt.unknown_dimensions else ('partial' if
                  attempt.known_read_bytes or attempt.known_write_bytes or attempt.known_processes else 'failed')
            # FailureCode comes from the unchanged closed original enum; never
            # inspect/format a user exception to derive a message or class name.
            failure=body('WireFailureProjectionV1',first_code=_FAILURES[attempt.site],
                known_prefix_bytes=attempt.known_read_bytes+attempt.known_write_bytes,producer='worker_backend',
                raw_error_retained_at_producer=True,secondary_codes=['unknown_failure']*len(attempt.secondaries),
                source_site=attempt.site,unknown_effect=bool(attempt.unknown_dimensions))
        observation=body('EffectObservationV1',failure=failure,grant=attempt.grant.pin,
            known_read_bytes=attempt.known_read_bytes,known_returned_processes=len(attempt.known_processes),
            known_write_bytes=attempt.known_write_bytes,request_sequence=attempt.pending.sequence,
            state=state,unknown_dimensions=list(attempt.unknown_dimensions))
        try:
            pending=self.same_channel.request('EffectObservationV1',attempt.site,observation,
                                             ('EffectObservationAckV1',),attempt.deadline)
            attempt.observation_pending=pending;ack=pending.completed_reply['payload']
            need(equal(ack['grant'],attempt.grant.pin) and ack['observation_sequence']==pending.sequence,
                 'same original grant and exact observation occurrence')
            self.same_channel.acknowledge(pending);attempt.reported=True
            self.last_acknowledged_cost_prefix=ack['charged_prefix'];self.current_effect=None
            need(ack['continued_effects_allowed'] and attempt.raw_first is None,
                 'failed effect or refused continued use cannot become a successful new effect')
            return attempt
        except BaseException as error:
            if attempt.raw_first is not None and error is not attempt.raw_first:attempt.secondaries.append(error)
            elif attempt.raw_first is None:attempt.raw_first=error
            self.retain(error);self.same_channel.retain(error,self.same_channel.pending,uncertain=not attempt.reported)
            if attempt.raw_first is not error:raise attempt.raw_first
            raise
