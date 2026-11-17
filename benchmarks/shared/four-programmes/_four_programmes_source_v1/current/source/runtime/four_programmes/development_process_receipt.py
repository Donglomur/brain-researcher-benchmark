"""Finite nominal PROCESS.json binding; serialized evidence is not authority."""
from .common import need, same, encode, descriptor

FIELDS=frozenset(('argv','campaign','cleanup_errors','closed_ns','costs','exit_code','forced',
    'group_empty','group_removed','identity','mode','natural_exit','original_evidence_deadline_ns',
    'original_failure','original_output_prefixes','original_run_deadline_ns','physical_final',
    'physical_final_known','physical_prefix','publication_complete','schema','source','spawn_acknowledged',
    'spawn_attempted','stderr','stderr_bytes','stdout','stdout_bytes','stream_materialization',
    'streams_eof','timed_out','unknown_dimensions'))

def validate_receipt_values(body,*,launch,ack,streams,completion=None):
    """Exact nominal/value inverse only. This never creates a process handle."""
    from .precommit_records import validate_type
    need(type(body) is dict and set(body)==FIELDS,'all and only original H process receipt fields')
    need(body['schema']=='four_original_process_observation_v1' and body['mode']=='ci_development_v2',
         'fixed original process receipt type and original development mode')
    need(body['publication_complete'] is False,
         'earlier receipt does not claim its own later completed publication')
    need(body['identity']==ack['worker_identity'] and body['argv']==launch['argv'] and
         body['source']==ack['worker_identity']['source'] and
         body['original_run_deadline_ns']==ack['run_deadline_ns']<=launch['run_deadline_ns'] and
         body['original_evidence_deadline_ns']==launch['evidence_deadline_ns'],
         'same original actual worker/source/argv and unchanged clocks')
    need(type(body['closed_ns']) is int and ack['original_start_ns']<=body['closed_ns']<=
         body['original_evidence_deadline_ns'],'original ordered receipt observation')
    need(body['spawn_attempted'] is True and body['spawn_acknowledged'] is True and
         body['natural_exit'] is True and type(body['exit_code']) is int and body['exit_code']==0 and
         body['streams_eof']=={'stdout':True,'stderr':True} and body['group_empty'] is True and
         body['group_removed'] is True and body['forced'] is False and body['timed_out'] is False and
         body['original_failure'] is None and body['cleanup_errors']==[] and body['unknown_dimensions']==[] and
         body['physical_final_known'] is True and body['physical_final'] is not None,
         'complete successful original process prefix, never failed/unknown-to-zero')
    validate_type('CostPrefix',body['costs'])
    need(not body['costs']['unknown_dimensions'] and
         all(value is not None for value in body['costs']['observed'].values()),'known original receipt cost prefix')
    need(body['stream_materialization']=={'stdout':True,'stderr':True} and
         body['original_output_prefixes']==[body['stdout'],body['stderr']],
         'both original raw stream occurrences retained in order')
    for side in ('stdout','stderr'):
        descriptor(body[side])
        need(body[side]==streams[side]['raw_bytes'] and body[side+'_bytes']==streams[side]['bytes'] and
             streams[side]['closed_ns']<=body['closed_ns'],'exact original closed raw stream receipt')
    if completion is not None:
        need(body['closed_ns']<=completion['closed_ns'],'receipt precedes the separate Completion')
    return body

def require_original_process(attempt):
    from .development_handles import DevelopmentAttemptHandle
    from .development_native_observations import DevelopmentNativeObservation
    from .observer import OriginalProcessObservation, RunningProcess
    need(type(attempt) is DevelopmentAttemptHandle,'actual original H attempt')
    attempt.require_live_original();producer=attempt.native_observations;observed=attempt.process_observation
    need(type(producer) is DevelopmentNativeObservation and producer.attempt is attempt and
         producer.kernel is attempt.worker_kernel and producer.kernel.native_observations is producer and
         producer.observation is observed and type(observed) is OriginalProcessObservation and observed.success,
         'same actual later completed source-owned original process observation')
    running=attempt.process
    need(type(running) is RunningProcess and running is producer.kernel.running and running.owner is attempt.host and
         observed.record is running.record and observed.identity is running.identity and
         observed.receipt is producer.receipt and observed.receipt_record is producer.receipt_record and
         producer.raw_first is None and producer.kernel.raw_first is None and running.primary is None,
         'same original kernel/receipt/custody, never an equal-Pin reconstruction')
    pin=observed.receipt;descriptor(pin)
    need(pin['path']==attempt.arm.launch.body['output_prefix']+'_PROCESS.json',
         'original output prefix determines the one concrete process receipt')
    body=observed.receipt_record
    validate_receipt_values(body,launch=attempt.arm.launch.body,ack=attempt.launch_ack.body,
                            streams=attempt.complete_stream_capture.body)
    live=dict(body);live['publication_complete']=True
    need(same(live,observed.record) and producer.last_time is not None and
         body['closed_ns']<=producer.last_time<=attempt.evidence_deadline_ns and
         body['campaign']==running.spec['campaign'] and
         body['original_run_deadline_ns']==running.spec['run_deadline_ns']==attempt.run_deadline_ns and
         attempt.started_ns==attempt.launch_ack.body['original_start_ns'] and
         body['source']==running.spec['source']==attempt.pair.contract.profile['launcher_source'],
         'only actual later readback/final-clock completion changes the chronological flag')
    publisher=producer.publisher
    publisher.meter.charge('retained_bytes',16*pin['bytes']+4096)
    need(publisher.outputs.read(pin,publisher.maximum_bytes,metadata=True)==encode(body),
         'complete same original H receipt readback')
    for side in ('stdout','stderr'):
        capture=attempt.evidence_capture.stream_attempts[side].complete
        need(getattr(observed,side) is capture.raw,'actual original raw stream bytes retained, no substituted payload')
    return observed
