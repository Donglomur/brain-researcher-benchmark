"""Output V2 exact completion targets and their original private inverses."""
from .common import need
from .backend_capture import CapturedRecord
from .precommit_records import validate_type


def validate_target_values(*, completion, prefix, launch, request, ack, streams, workspace, subtree, cost, cutoff,
                           owner_binding, workspace_observation):
    """Closed serialized checks only; a successful return is never a capability."""
    for kind,value in (('DevelopmentCompletion',completion),('DevelopmentAttempt',prefix),
                       ('DevelopmentLaunchRequest',launch),('DevelopmentRequest',request),('WorkerLaunchAck',ack),
                       ('HStreamCaptureV1',streams),('DevelopmentWorkspaceClosure',workspace),
                       ('SubtreeObservation',subtree),('CostPrefix',cost),
                       ('WorkspaceObservation',workspace_observation)):
        validate_type(kind,value)
    condition=completion['condition']
    need(all(v['condition']==condition for v in (prefix,launch,request,ack,streams,workspace,subtree,workspace_observation)),
         'same actual original condition across every completion target')
    need(prefix['evidence_deadline_ns']==launch['evidence_deadline_ns']==ack['evidence_deadline_ns']==cutoff and
         completion['started_ns']==ack['original_start_ns'] and
         prefix['run_deadline_ns']==launch['run_deadline_ns']<=cutoff and
         completion['started_ns']<=completion['closed_ns']<=cutoff,
         'same earlier E; original worker deadlines are not extended')
    schedule=request['schedule'];start=ack['original_start_ns']
    need(schedule['earliest_launch_ns']<=start<=schedule['latest_launch_ns'] and
         ack['run_deadline_ns']==start+schedule['duration_ns']<=
         schedule['latest_launch_ns']+schedule['duration_ns']<=
         schedule['common_cutoff_ns']==launch['run_deadline_ns'],
         'actual R is original S plus duration, separately bounded by the earlier launch cutoff')
    need(request['pair_plan']==launch['pair_plan'] and request['workspace_identity']==launch['workspace_identity'],
         'same earlier request schedule and original launch context')
    need(prefix['owner_binding']==launch['owner_binding']==ack['owner_binding']==
         streams['owner_binding']==workspace['owner_binding']==owner_binding,
         'same original owner throughout all target records')
    need(streams['original_attempt']==workspace['original_attempt']==subtree['attempt']==
         ack['original_attempt']==completion['original_attempt'], 'same original attempt ancestry')
    need(ack['launch_request']==completion['launch_request'] and
         prefix['launch_request']==completion['launch_request'] and
         completion['workspace_identity']==workspace['workspace'] and
         launch['workspace_identity']==workspace['workspace'] and
         ack['request']==completion['request']==launch['request'],
         'exact original launch/request/workspace inputs')
    need(workspace_observation['pair_id']==ack['pair_id'] and
         launch['pair_plan']==completion['pair_plan'],
         'original exact pair identities cannot be interchanged across arms')
    need(subtree['producer']=='host' and subtree['scope']=='whole_arm' and
         subtree['root']==ack['worker_identity'] and subtree['enumeration_complete'] and
         subtree['unresolved_count']==0 and subtree['excluded_live_worker'] is None and
         all(row['state']=='exited_reaped' for row in subtree['members']),
         'full original whole-arm final enumeration, never the server subset')
    need(subtree['observed_ns']<=workspace['observed_ns']<=completion['closed_ns'] and
         streams['observed_ns']<=completion['closed_ns'],
         'all original target observations precede Completion')
    need(not cost['unknown_dimensions'] and all(v is not None for v in cost['observed'].values()),
         'known same-owner aggregate prefix; no unknown-to-zero conversion')


def require_targets(attempt):
    from .development_handles import DevelopmentAttemptHandle
    from .development_evidence import DevelopmentEvidenceCapture, CapturedStreamBytes
    need(type(attempt) is DevelopmentAttemptHandle,'actual original development attempt')
    attempt.require_live_original()
    evidence=attempt.evidence_capture
    need(type(evidence) is DevelopmentEvidenceCapture and evidence.attempt is attempt and
         evidence.raw_first is None and attempt.raw_first is None,
         'same original fixed H evidence owner without retained failure')
    expected=(('HStreamCaptureV1',attempt.complete_stream_capture,evidence.stream_manifest),
              ('DevelopmentWorkspaceClosure',attempt.descendant_workspace_closure,evidence.workspace_capture),
              ('CostPrefix',attempt.cost_observation,evidence.completion_cost))
    for kind,capture,original in expected:
        need(type(capture) is CapturedRecord and capture is original and capture.owner is attempt.owner and
             capture.kind==kind,'exact source-owned target capture, not an equal Pin or body')
        evidence.publisher.meter.charge('retained_bytes',16*len(capture.raw)+4096)
        raw=evidence.publisher.outputs.read(capture.pin,evidence.publisher.maximum_bytes,metadata=True)
        need(raw==capture.raw,'exact complete same-owner target readback')
        validate_type(kind,capture.body)
    streams=attempt.complete_stream_capture.body
    for name in ('stdout','stderr'):
        original=evidence.stream_attempts[name].complete
        need(type(original) is CapturedStreamBytes and original.evidence is evidence and
             original.source_streams is attempt.streams and original.side==name and
             streams[name]['raw_bytes']==original.pin and
             streams[name]['bytes']==attempt.streams.counts[name] and
             streams[name]['closed_ns']==attempt.streams.closed_ns[name],
             'typed side points to its actual original captured stream occurrence')
    workspace=attempt.descendant_workspace_closure.body
    need(evidence.workspace_source is attempt.arm.workspace and
         evidence.whole_arm_source is attempt.whole_arm_capture and
         workspace['subtree']==attempt.whole_arm_capture.pin and
         workspace['retained_workspace_identity']==evidence.workspace_identity and
         workspace['workspace']==attempt.arm.workspace_capture.pin,
         'retained original path/whole-arm/capture identities remain joined')
    from .programme_workspace import retained_workspace_identity
    now=retained_workspace_identity(attempt)
    for key in ('parent_handle_ordinal','relative_path','device','inode','kind','mode','uid'):
        need(now[key]==evidence.workspace_identity[key],'same retained original read anchor through consumers')
    cutoff=attempt.owner.parent.original_deadline
    need(attempt.evidence_deadline_ns==attempt.arm.launch.body['evidence_deadline_ns']==
         attempt.prefix_capture.body['evidence_deadline_ns']==attempt.launch_ack.body['evidence_deadline_ns']==cutoff,
         'original H E exists before preparation and every actual launch')
    cost=attempt.cost_observation.body
    need(not cost['unknown_dimensions'] and all(v is not None for v in cost['observed'].values()),
         'actual complete aggregate cost occurrence remains known')
    return evidence


def require_completion_targets(attempt, completion):
    """Join a completed record to its actual finalizer, not equal wire Pins.

    The finalizer already performed the full original Store readbacks. This
    private occurrence check does not repeat those reads or any terminal effect;
    serialized downstream consumers retain their separate readback obligations.
    Backend admission/closure is additionally checked by the pair producer.
    """
    from .development_handles import DevelopmentAttemptHandle
    from .development_finalization import OriginalOutputFinalization
    from .development_process_receipt import validate_receipt_values
    need(type(attempt) is DevelopmentAttemptHandle and type(completion) is CapturedRecord and
         completion.owner is attempt.owner and completion.kind=='DevelopmentCompletion' and
         completion._attempt.complete is completion and completion._attempt.raw_first is None,
         'actual original completed capture and its original publication occurrence')
    finalization=attempt.output_finalization
    need(type(finalization) is OriginalOutputFinalization and finalization.attempt is attempt and
         finalization.require_completed() is finalization,
         'same source-owned finalization before completion publication')
    body=completion.body;arm=attempt.arm
    actual={'actual_launch':attempt.launch_ack.pin,
            'actual_original_process':attempt.process_observation.receipt,
            'complete_stream_capture':attempt.complete_stream_capture.pin,
            'cost_observation':attempt.cost_observation.pin,
            'descendant_and_workspace_closure':attempt.descendant_workspace_closure.pin,
            'original_attempt':attempt.prefix_capture.pin,'launch_request':arm.launch.pin,
            'request':arm.request.pin,'exposure':arm.exposure.pin,
            'state_identity':arm.state_capture.pin,'workspace_identity':arm.workspace_capture.pin,
            'pair_plan':attempt.pair.pair_plan.pin}
    need(all(body[k]==v for k,v in actual.items()),
         'all completion target Pins are exact projections of the original actual objects')
    validate_target_values(completion=body,prefix=attempt.prefix_capture.body,launch=arm.launch.body,request=arm.request.body,
        ack=attempt.launch_ack.body,streams=attempt.complete_stream_capture.body,
        workspace=attempt.descendant_workspace_closure.body,subtree=attempt.whole_arm_capture.body,
        cost=attempt.cost_observation.body,cutoff=attempt.owner.parent.original_deadline,
        owner_binding=attempt.owner.parent.binding_pin,workspace_observation=arm.workspace_capture.body)
    receipt=attempt.process_observation.receipt_record
    validate_receipt_values(receipt,launch=arm.launch.body,ack=attempt.launch_ack.body,
                            streams=attempt.complete_stream_capture.body,completion=body)
    need(all(attempt.cost_observation.body['charged'][dimension]>=value
             for dimension,value in receipt['costs']['charged'].items()),
         'later actual aggregate prefix retains every original process receipt cost')
    return finalization

