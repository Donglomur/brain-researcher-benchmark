"""Original two-arm H completion, followed by the existing programme route.

This caller requires the fixed H receiver/view source and its actual independent
native observations. It cannot run from serialized worker handles. The selected
native V3 issuer and producer migration remain separate unactivated dependencies.
"""
from .common import need, same
from .backend_capture import CapturedRecord
from .development_preparation import PreparationHandle
from .development_handles import DevelopmentAttemptHandle, PairCompletionHandle, _PAIR_COMPLETE
from .development_finalization import OriginalOutputFinalization, finalize_original_outputs_v2
from .development_targets import validate_target_values, require_completion_targets
from .development_contract import require_original_schedule
from .precommit_records import CONDITIONS, validate_type


def _original_backend(attempt):
    # Fixed source owner, supplied by the exact separately frozen H component.
    # No duck-typed worker object or caller-created record can take this route.
    from .backend_host_view import HBackendView
    view=attempt.backend
    need(type(view) is HBackendView and view.attempt is attempt,
         'actual same original H backend view')
    # The fixed identity validator returns None. Only the completion validator
    # returns the same owner; do not invent a fluent identity-validation ABI.
    view.require_original()
    need(view.require_completed() is view,
         'actual same registered completed H backend view and independent native observation')
    for kind,actual in (('BackendAttemptBase',view.base),
                       ('BackendInitializationObservation',view.initialization),
                       ('BackendAdmissionAck',view.admission),('BackendClosure',view.closure)):
        need(type(actual) is CapturedRecord and actual.owner is attempt.owner and
             actual.kind==kind and actual._attempt.complete is actual and actual._attempt.raw_first is None,
             'same original H completed publication occurrence')
        validate_type(kind,actual.body)
    base=view.base.body;init=view.initialization.body;ack=view.admission.body;closed=view.closure.body
    a=attempt;arm=a.arm
    need(base['worker_attempt']==a.prefix_capture.pin and base['worker_launch_ack']==a.launch_ack.pin and
         base['request']==arm.request.pin and base['workspace']==arm.workspace_capture.pin and
         base['preparation']==arm.state_capture.pin and base['profile']==a.pair.contract.backend_pin and
         base['pair_id']==a.pair.pair_id and base['condition']==a.condition,
         'actual backend base belongs to this original worker/preparation/profile')
    need(init['attempt']==view.base.pin and init['worker_launch_ack']==a.launch_ack.pin and
         init['worker_identity']==a.launch_ack.body['worker_identity'] and
         init['preparation']==arm.state_capture.pin and init['workspace']==arm.workspace_capture.pin and
         init['profile']==a.pair.contract.backend_pin and init['condition']==a.condition and
         init['generation_requests_before_capture']==0,
         'actual fresh initialization retains its exact original launch and state ancestry')
    need(ack['backend_attempt']==view.base.pin and ack['initialization']==view.initialization.pin and
         ack['host_observation']==view.host_observation.pin and ack['worker_attempt']==a.prefix_capture.pin and
         ack['host_owner_binding']==a.owner.parent.binding_pin and ack['condition']==a.condition and
         ack['pair_id']==a.pair.pair_id and ack['nonce']==base['nonce'] and
         ack['generation_deadline_ns']==base['generation_deadline_ns'],
         'actual H admission is the independent original observer result')
    need(closed['attempt']==view.base.pin and closed['condition']==a.condition and
         closed['initialization']==view.initialization.pin and closed['admission']==view.admission.pin and
         closed['server_identity']==init['server_identity'] and closed['status']=='complete' and
         closed['purpose']=='planned_protocol_shutdown' and closed['pending_requests']==0 and
         closed['first_error'] is None and not closed['forced_group_cleanup'],
         'complete planned original server closure, never forced/failed/unknown success')
    return view


def _pair_opportunity(handle):
    """Verify both original states and schedule before claiming completion."""
    pair=handle.pair
    need(handle.attempted and set(handle.backend_views)==set(CONDITIONS),
         'complete original two-arm H view roster')
    starts=[];servers=[]
    schedule=require_original_schedule(pair.contract,pair.pair_plan.body['schedule'])
    for condition in CONDITIONS:
        attempt=handle.attempts[condition];view=_original_backend(attempt)
        need(handle.backend_views[condition] is view,'same actual H receiver view retained by this producer')
        starts.append(attempt.launch_ack.body['original_start_ns'])
        identity=view.initialization.body['server_identity']
        servers.append(tuple(identity[k] for k in ('boot_id','pid','start_monotonic_ns')))
        need(same(attempt.arm.request.body['schedule'],schedule),
             'same earlier original full schedule, never a per-arm replacement')
    need(servers[0]!=servers[1] and
         handle.backend_views[CONDITIONS[0]].host_admission_owner is not
         handle.backend_views[CONDITIONS[1]].host_admission_owner,
         'two independently owned fresh backend processes, not a reused mutable server')
    skew=max(starts)-min(starts);need(skew<=schedule['maximum_launch_skew_ns'],'actual original bounded launch skew')
    return skew


def require_original_pair_outputs(handle):
    """Private original-pair inverse after publication, without effect replay."""
    pair=handle.pair;skew=_pair_opportunity(handle)
    for condition in CONDITIONS:
        attempt=handle.attempts[condition];view=handle.backend_views[condition]
        require_completion_targets(attempt,handle.completions[condition])
        body=handle.completions[condition].body
        need(body['backend_initialization']==view.initialization.pin and
             body['backend_admission']==view.admission.pin and body['backend_closure']==view.closure.pin,
             'actual backend captures project into the original Completion')
    need(handle.closure._attempt.complete is handle.closure and handle.closure._attempt.raw_first is None,
         'actual completed pair closure publication occurrence')
    body=handle.closure.body;validate_type('DevelopmentPairClosure',body)
    need(body['actual_start_skew_ns']==skew and
         body['original_cutoff_ns']==pair.owner.parent.original_deadline and
         body['backend_profile']==pair.contract.backend_pin and
         body['backend_closure_by_condition']=={c:handle.backend_views[c].closure.pin for c in CONDITIONS} and
         body['initialization_by_condition']=={c:handle.backend_views[c].initialization.pin for c in CONDITIONS},
         'complete original closure maps, actual skew and unchanged earlier H cutoff')
    return handle


def finish_pair_backend_v1(pair):
    need(type(pair) is PreparationHandle and pair.promotion is pair and
         pair.owner.parent.preparation is pair,'same actual admitted and prepared original pair')
    need(not hasattr(pair,'backend_completion'),'one original pair finish, including failed attempts')
    handle=PairCompletionHandle(_PAIR_COMPLETE,pair);pair.backend_completion=handle
    handle.attempted=True
    # Visit both existing actual attempts. A failure on one side cannot suppress
    # independent once-only terminal custody of the other original worker.
    for condition in CONDITIONS:
        attempt=pair.launches.get(condition)
        try:
            need(type(attempt) is DevelopmentAttemptHandle and attempt.pair is pair and
                 attempt.condition==condition,'actual original attempt roster before terminal effects')
            attempt.require_live_original();handle.attempts[condition]=attempt
        except BaseException as error:
            handle.retain(error,'finish_pair_backend_v1.attempt');continue
        try:handle.backend_views[condition]=_original_backend(attempt)
        except BaseException as error:handle.retain(error,'finish_pair_backend_v1.backend')
        try:
            final=attempt.output_finalization
            if final is None:final=finalize_original_outputs_v2(attempt)
            need(type(final) is OriginalOutputFinalization and final.attempt is attempt and
                 final.require_completed() is final,'actual once-only terminal output caller')
        except BaseException as error:handle.retain(error,'finish_pair_backend_v1.outputs')
    try:
        need(handle.raw_first is None and pair.owner.parent.first_raw is None and
             set(handle.attempts)==set(CONDITIONS) and set(handle.backend_views)==set(CONDITIONS),
             'both complete original arms before any successful pair promotion')
        skew=_pair_opportunity(handle)
        for condition in CONDITIONS:
            attempt=handle.attempts[condition];arm=attempt.arm;view=handle.backend_views[condition]
            body={'schema':'ci_developmentcompletion_v3','condition':condition,
                  'actual_launch':attempt.launch_ack.pin,'actual_original_process':attempt.process_observation.receipt,
                  'backend_admission':view.admission.pin,'backend_closure':view.closure.pin,
                  'backend_initialization':view.initialization.pin,'closed_ns':pair.clock(),
                  'complete_stream_capture':attempt.complete_stream_capture.pin,
                  'cost_observation':attempt.cost_observation.pin,
                  'descendant_and_workspace_closure':attempt.descendant_workspace_closure.pin,
                  'equal_opportunity':True,'exposure':arm.exposure.pin,'launch_request':arm.launch.pin,
                  'original_attempt':attempt.prefix_capture.pin,'pair_plan':pair.pair_plan.pin,
                  'request':arm.request.pin,'started_ns':attempt.launch_ack.body['original_start_ns'],
                  'state_identity':arm.state_capture.pin,'status':'complete','unknown_dimensions':[],
                  'workspace_identity':arm.workspace_capture.pin}
            validate_target_values(completion=body,prefix=attempt.prefix_capture.body,launch=arm.launch.body,
                request=arm.request.body,ack=attempt.launch_ack.body,streams=attempt.complete_stream_capture.body,
                workspace=attempt.descendant_workspace_closure.body,subtree=attempt.whole_arm_capture.body,
                cost=attempt.cost_observation.body,cutoff=pair.owner.parent.original_deadline,
                owner_binding=pair.owner.parent.binding_pin,workspace_observation=arm.workspace_capture.body)
            capture=pair.host_publisher.capture('development_'+condition+'_COMPLETION.json','DevelopmentCompletion',body)
            handle.completions[condition]=capture;pair.owner.parent.known_records.append(capture.pin)
        body={'schema':'ci_developmentpairclosure_v3','actual_start_skew_ns':skew,
              'backend_closure_by_condition':{c:handle.backend_views[c].closure.pin for c in CONDITIONS},
              'backend_profile':pair.contract.backend_pin,'both_fresh_states':True,
              'both_original_descendant_closures':True,
              'completion_by_condition':{c:handle.completions[c].pin for c in CONDITIONS},
              'equal_opportunity':True,
              'initialization_by_condition':{c:handle.backend_views[c].initialization.pin for c in CONDITIONS},
              'original_cutoff_ns':pair.owner.parent.original_deadline,
              'pair_plan':pair.pair_plan.pin,'same_owner_binding':pair.owner.parent.binding_pin}
        handle.closure=pair.host_publisher.capture('development_PAIR_CLOSURE.json','DevelopmentPairClosure',body)
        pair.owner.parent.known_records.append(handle.closure.pin)
        pair.clock();return handle.require_original()
    except BaseException as error:
        handle.retain(error,'finish_pair_backend_v1.completion')
        raise handle.raw_first
