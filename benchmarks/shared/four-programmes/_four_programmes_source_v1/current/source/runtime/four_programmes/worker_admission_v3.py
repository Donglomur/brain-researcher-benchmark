"""Exact original admission object delivery and once-only worker finish claims."""
from .common import need
from .worker_context_records_v3 import body, equal, pinned, decode
from .worker_channel_v3 import completed_capture, require_capture

def _fetch_admission(context,selection,kind):
    field={'BackendAdmissionAck':'admission','HostInitializationObservation':'host_observation'}[kind]
    descriptor=selection.completed_reply['payload'][field];total=descriptor['bytes']
    need(0<total<=context.logical_limit,'complete original admission object bound')
    parts=[];offset=0;last=None
    while offset<total:
        request=body('AdmissionObjectRequestV1',completed_reply_sequence=selection.sequence,kind=kind,offset=offset)
        pending=context.channel.request('AdmissionObjectRequestV1','admission_object',request,
                                        ('AdmissionObjectChunkV1',),context.deadline('initialization'))
        reply=pending.completed_reply['payload']
        need(reply['completed_reply_sequence']==selection.sequence and reply['kind']==kind and
             equal(reply['capture'],descriptor) and reply['offset']==offset,'same original admission object/offset')
        chunk=bytes.fromhex(reply['raw_hex']);need(0<len(chunk)<=16384 and len(chunk)<=total-offset,
                                               'positive bounded contiguous admission chunk')
        need(reply['final']==(offset+len(chunk)==total),'exact final admission chunk')
        parts.append(chunk);offset+=len(chunk);last=pending;context.channel.acknowledge(pending)
    raw=b''.join(parts);pinned(raw,descriptor);decode(kind,raw,context.logical_limit)
    return completed_capture(context,last,kind,raw,descriptor,'admission_delivery',selection)

def poll_backend_admission(context,initialization,snapshot):
    context.require_active()
    need(context.meter.current_effect is None and context.publisher.pending_publication is None and
         context.admission_captures is None,'same original completed initialization, no replacement admission')
    require_capture(initialization,context,'BackendInitializationObservation')
    require_capture(snapshot,context,'BackendAttempt')
    init=initialization.body;snap=snapshot.body
    need(initialization.origin==snapshot.origin=='publication_ack' and
         equal(init['attempt'],snap['base_attempt']) and snap['snapshot_stage']=='postinitialization' and
         snap['snapshot_ordinal']==1 and snap['state']=='initialized',
         'actual original postinitialization snapshot and stable base')
    try:
        request=body('PollBackendAdmissionV1',initialization=initialization.pin,snapshot=snapshot.pin)
        pending=context.channel.request('PollBackendAdmissionV1','poll_backend_admission',request,
             ('PendingBackendAdmissionV1','CompletedBackendAdmissionV1'),context.deadline('initialization'))
        context.admission_pending=pending;reply=pending.completed_reply['payload']
        need(equal(reply['initialization'],initialization.pin),'same actual original initialization capture')
        if reply['state']=='pending':
            need(reply['observed_ns']<=context.deadline('initialization'),'pending does not extend original J')
            context.channel.acknowledge(pending)
            return None
        context.channel.acknowledge(pending)
        ack=_fetch_admission(context,pending,'BackendAdmissionAck')
        observation=_fetch_admission(context,pending,'HostInitializationObservation')
        a=ack.body;o=observation.body;c=context.context_identity
        need(equal(a['host_observation'],observation.pin) and equal(a['initialization'],initialization.pin) and
             equal(o['initialization'],initialization.pin) and equal(a['backend_attempt'],init['attempt']) and
             equal(o['attempt'],init['attempt']) and equal(a['worker_attempt'],c['original_attempt']) and
             a['condition']==o['condition']==c['condition'] and a['nonce']==o['pair_nonce']==c['launch_nonce'] and
             a['pair_id']==c['pair_id'] and equal(a['source_admission'],c['source_admission']) and
             equal(o['source_admission'],c['source_admission']) and
             equal(a['host_owner_binding'],o['host_owner_binding']) and
             a['generation_deadline_ns']==context.deadline('generation') and
             a['issued_ns']<=context.deadline('generation'),'complete original actual admission/source/clock joins')
        context.admission_captures=(ack,observation)
        return context.admission_captures
    except BaseException as error:
        context.retain(error);context.channel.retain(error,context.channel.pending,uncertain=True);raise

def finish_worker(context,terminal_snapshot,closure,local_failure=None):
    """This only reports the worker claim; it never supplies H outside closure."""
    need(context.finish_pending is None and not context.channel.poisoned and
         context.channel.pending is None,'one original finish, no continuation after lost channel acknowledgement')
    if terminal_snapshot is not None:require_capture(terminal_snapshot,context,'BackendAttempt')
    if closure is not None:require_capture(closure,context,'BackendClosure')
    if local_failure is None:
        need(not context.poisoned and context.local_raw_first is None and
             terminal_snapshot is not None and closure is not None and
             context.meter.current_effect is None and context.publisher.pending_publication is None,
             'complete worker claim needs actual original terminal captures and no unresolved effects')
        disposition='complete'
    else:
        from .worker_context_records_v3 import validate
        validate('WireFailureProjectionV1',local_failure)
        need(context.local_raw_first is not None and local_failure['raw_error_retained_at_producer'],
             'wire projection refers to an actual local original error')
        disposition='unknown' if local_failure['unknown_effect'] else 'failed'
    request=body('FinishWorkerV1',closure=None if closure is None else closure.pin,disposition=disposition,
                 local_failure=local_failure,terminal_snapshot=None if terminal_snapshot is None else terminal_snapshot.pin)
    # Latch a source-owned attempt before any encode/send; even a failure before
    # request() returns must prohibit a second finish attempt.
    context.finish_pending=request
    try:
        pending=context.channel.request('FinishWorkerV1','finish_worker',request,('FinishWorkerAckV1',),
                                        context.deadline('shutdown'))
        context.finish_pending=pending;ack=pending.completed_reply['payload']
        need(ack['request_sequence']==pending.sequence and ack['received_ns']<=context.deadline('shutdown'),
             'same original finish occurrence within worker R')
        context.channel.acknowledge(pending)
        context.activated=False
        return ack
    except BaseException as error:
        context.retain(error);context.channel.retain(error,context.channel.pending,uncertain=True);raise
