"""Original H attempt failure, including an unacknowledged original spawn.

This is the failure branch of the adopted StageAttemptFailure schema, never a
StageCompletion or a budget return. It preserves the entire outstanding lease.
"""
from four_programmes.common import need,closed,encode,pin,failure
from four_programmes.observer import RunningProcess,OriginalProcessObservation
from four_programmes.channel import HostEvent,TerminalEvidence

_FAILED=object()

class FailedStage:
    __slots__=('record','descriptor','result','primary','observation','_token')
    def __init__(self,token,record,descriptor,result,primary,observation):
        need(token is _FAILED,'actual original failure producer/consumer')
        self.record=record;self.descriptor=descriptor;self.result=result
        self.primary=primary;self.observation=observation;self._token=token

def publish_failure(owner,running,*,lease,lease_pin,primary,observation,prefix):
    """Called by the actual StageHost error owner after its one finish attempt.

All writes use the same earlier H evidence store. Publication failure propagates
to that owner, which retains the original exception; it grants no extra share.
"""
    need(type(running) is RunningProcess and running.owner is owner.host,
         'actual original owned attempted worker')
    owner.schemas.validate('ci','Lease',lease,owner.store.meter)
    need(lease['campaign_id']==owner.profile['campaign_id'] and
         lease['profile']==owner.profile_pin and lease['controller']==owner.controller.identity and
         lease['observer_source']==owner.source and lease['worker_nonce']==running.spec['nonce'] and
         lease['original_evidence_deadline_ns']==owner.clock['evidence_deadline_ns'],
         'exact earlier lease/host/controller/clock before failure publication')
    need(pin(encode(lease))=={k:lease_pin[k] for k in ('bytes','sha256')},'actual immutable lease bytes')
    need(isinstance(primary,BaseException),'retained raw original H failure')
    need(observation is None or type(observation) is OriginalProcessObservation,
         'actual one-time original observation or explicitly unknown')
    original=running.record
    if observation is not None:
        need(observation.identity==running.identity,'same actual original failed handle')
        original=observation.record
    attempted=original['spawn_attempted'];acknowledged=original['spawn_acknowledged']
    need(type(attempted) is bool and type(acknowledged) is bool and
         (not acknowledged or attempted),'original spawn flags, never inferred PID success')
    if running.identity is not None:
        need(acknowledged and running.identity['launch_nonce']==lease['worker_nonce'],
             'known worker only after actual acknowledgement')
    unknown=list(original.get('unknown_dimensions',[]))
    for dimension in ('no_eligible_stage_completion','terminal_budget_state'):
        if dimension not in unknown:unknown.append(dimension)
    if observation is None and 'original_process_closure' not in unknown:unknown.append('original_process_closure')
    evidence=[]
    diagnostic={'schema':'critical_init_original_attempt_diagnostic_v3',
                'original_H_failure':failure(primary),'original_process':original,
                'retained_handle_still_open':owner.host.active.get(running.spec['nonce']) is running,
                'original_finish_attempted':running.spec['nonce'] in owner.finish_started,
                'secondary_H_failures':[failure(e) for e in owner.errors[running.spec['nonce']]['secondary']]}
    d=owner._publish(prefix+'_DIAGNOSTIC.json',diagnostic,kind='original_outcome',evidence=evidence)
    body={'schema':'critical_init_stage_attempt_failure_v3','campaign_id':lease['campaign_id'],
          'lease':lease_pin,'spawn_attempted':attempted,'spawn_acknowledged':acknowledged,
          'known_worker':running.identity,'original_failure':d,'known_stage_completion':None,
          'known_budget_state':lease['base_state'],'known_prefixes':list(owner.prefixes),
          'unknown_dimensions':unknown,'full_outstanding_delegation_retained':True,
          'dependent_science_allowed':False,'original_evidence_deadline_ns':lease['original_evidence_deadline_ns']}
    owner.schemas.validate('ci','StageAttemptFailure',body,owner.store.meter)
    descriptor=owner._publish(prefix+'_ATTEMPT_FAILURE.json',body,kind='original_outcome',evidence=evidence)
    owner.store.meter.check()
    result={'attempt_failure':descriptor,'evidence':evidence}
    return FailedStage(_FAILED,body,descriptor,result,primary,observation)

def consume_failure(event,*,lease,lease_pin,controller,profile,profile_pin,schemas,bridge_meter):
    """Actual C branch: retain failure without any programme Budget access."""
    need(type(event) is HostEvent and event.body['status'] in ('failed','unknown'),
         'actual failed original H event')
    result=event.body['result'];closed(result,('attempt_failure','evidence'))
    store=TerminalEvidence(event,bridge_meter)
    body=store.document(result['attempt_failure'],4194304)
    schemas.validate('ci','StageAttemptFailure',body,bridge_meter)
    schemas.validate('ci','Lease',lease,bridge_meter)
    need(pin(encode(lease))=={k:lease_pin[k] for k in ('bytes','sha256')} and
         body['lease']==lease_pin and body['campaign_id']==lease['campaign_id']==event.campaign==profile['campaign_id'] and
         lease['controller']==controller and lease['profile']==profile_pin and
         lease['observer_source']==event.source==profile['observer_source'],
         'same complete original lease and independent source, not report-supplied approval')
    need(body['original_evidence_deadline_ns']==lease['original_evidence_deadline_ns'] and
         body['known_budget_state']==lease['base_state'] and body['known_stage_completion'] is None,
         'exact known earlier prefix; no invented returned budget or completion')
    need(not body['spawn_acknowledged'] or body['spawn_attempted'],'original acknowledgement implies attempted spawn')
    worker=body['known_worker']
    need(worker is None or (body['spawn_acknowledged'] and worker['launch_nonce']==lease['worker_nonce'] and worker!=controller),
         'nullable original worker identity, never synthetic after missing acknowledgement')
    diagnostic=store.document(body['original_failure'],4194304)
    closed(diagnostic,('schema','original_H_failure','original_process','retained_handle_still_open',
                       'original_finish_attempted','secondary_H_failures'))
    need(diagnostic['schema']=='critical_init_original_attempt_diagnostic_v3' and
         diagnostic['original_process']['spawn_attempted']==body['spawn_attempted'] and
         diagnostic['original_process']['spawn_acknowledged']==body['spawn_acknowledged'],
         'original raw observation joins exact failed attempt flags')
    need('no_eligible_stage_completion' in body['unknown_dimensions'] and
         'terminal_budget_state' in body['unknown_dimensions'],'unknown cannot become a new zero prefix')
    return FailedStage(_FAILED,body,result['attempt_failure'],result,None,None)
