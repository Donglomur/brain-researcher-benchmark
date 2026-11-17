"""Whole-job H projection and C admission of the actual closed native attempt.

Reference scientific bodies and raw streams stay in H custody. The projection
contains process/budget metadata and a result descriptor; it cannot qualify an
environment or replace the two-candidate seal barrier.
"""
from .common import need, closed, integer, encode, pin, descriptor, bounded_size
from .channel import HostEvent
from .hm_whole_job_profile_v1 import HMWholeJobPlanV1
from .hm_whole_job_controller_v1 import HMWholeControllerCustodyV1
from .hm_whole_worker_contract_v1 import wrapped, validate_stage_chain, process

_TOKEN = object()
FIELDS = ('schema', 'profile', 'sequence', 'stage', 'subject', 'request', 'lease',
          'start', 'scope', 'inputs', 'full_plan', 'submission', 'previous_return',
          'result', 'completed_reference_ids', 'candidate_receipt', 'outer',
          'scientific_budget', 'stage_finished_ns', 'native_closed',
          'whole_qualification', 'reference_body_withheld')


class HMWholeStageAdmissionV1:
    def __init__(self, token, **fields):
        need(token is _TOKEN, 'fixed actual original stage event admission')
        self.__dict__.update(fields)


def publish_original_hm_whole_stage_return_v1(stage, *, previous_return):
    from .hm_whole_job_native_v1 import HMNativeStageAttemptV1
    need(type(stage) is HMNativeStageAttemptV1 and stage.finished and
         stage.closure_complete and stage.eligible and stage.raw_first is None and
         stage.campaign.stages.get(stage.sequence) is stage and
         stage.allocation.native_attempt is stage and stage.allocation.complete,
         'actual original complete native attempt and nonrefundable allocation')
    need(getattr(stage, '_public_return_attempted', False) is False,
         'one H stage return publication attempt, including failures')
    stage._public_return_attempted = True
    try:
        c = stage.campaign; subject = stage.subject['body']; terminal = stage.worker_terminal['body']
        reference = stage.allocation.stage == 'reference'
        original = stage.original_result
        need(original['descriptor'] == terminal['result'] and
             original['root'] == stage.request['body']['output'],
             'actual captured original scientific result, not caller metadata')
        if reference:
            body = original['body']
            closed(body, ('plan', 'completed', 'scientific_qualified', 'budget'))
            need(body['plan'] == subject['full_plan'] and type(body['completed']) is dict and
                 len(body['completed']) == 8223, 'whole original reference completion graph')
            completed = list(body['completed']); candidate = None
        else:
            completed = None
            candidate = {'descriptor': original['descriptor'], 'body': original['body']}
        body = {'schema': 'hm_whole_stage_public_return_v1', 'profile': c.plan.pin,
            'sequence': stage.sequence, 'stage': stage.allocation.stage,
            'subject': stage.subject, 'request': stage.request, 'lease': stage.lease,
            'start': stage.start,
            **{k: subject[k] for k in ('scope', 'inputs', 'full_plan', 'submission')},
            'previous_return': previous_return, 'result': original['descriptor'],
            'completed_reference_ids': completed, 'candidate_receipt': candidate,
            'outer': {'descriptor': stage.observation.receipt,
                      'body': stage.observation.receipt_record,
                      'actual_return': stage.observation.record},
            'scientific_budget': terminal['scientific_budget'],
            'stage_finished_ns': stage.final_clock, 'native_closed': True,
            'whole_qualification': False, 'reference_body_withheld': reference}
        descriptor_out = c.host.outputs.publish('hm_whole_' + str(stage.sequence) + '_PUBLIC_RETURN.json', body)
        stage._public_return = {'descriptor': descriptor_out, 'body': body}
        return stage._public_return
    except BaseException as error:
        stage.retain(error, 'actual_H_public_return');raise stage.raw_first


def _actual_outer(value, *, worker, plan, row):
    closed(value, ('descriptor', 'body', 'actual_return'))
    wrapped({'descriptor': value['descriptor'], 'body': value['body']})
    record = value['actual_return']; before = value['body']
    need(type(record) is dict and record['schema'] == 'four_original_process_observation_v1' and
         record['identity'] == worker and record['source'] == worker['source'] and
         record['campaign'] == plan.body['campaign_id'], 'same actual observed W identity')
    need(set(before) == set(record) and
         all(before[k] == record[k] for k in before if k != 'publication_complete') and
         before['publication_complete'] is False and record['publication_complete'] is True,
         'complete original publication prefix and actual returned completion')
    for key in ('spawn_attempted', 'spawn_acknowledged', 'natural_exit', 'group_empty',
                'group_removed', 'physical_final_known', 'publication_complete'):
        need(record[key] is True, 'actual complete original process ' + key)
    for key in ('forced', 'timed_out'):
        need(record[key] is False, 'actual unforced original process ' + key)
    need(type(record['exit_code']) is int and record['exit_code'] == 0 and
         record['streams_eof'] == {'stdout': True, 'stderr': True} and
         record['original_failure'] is None and record['cleanup_errors'] == [] and
         record['unknown_dimensions'] == [], 'actual successful complete original observation')
    for key in ('stdout', 'stderr'):
        descriptor(record[key]); integer(record[key + '_bytes'])
        need(record[key]['bytes'] == record[key + '_bytes'] and
             record[key + '_bytes'] <= row['physical']['stream_bytes'],
             'complete bounded original stream descriptor; body stays in H')
    return record


def admit_original_hm_whole_stage_v1(event, *, custody, budget, full_plan,
                                    expected_subject, expected_request, selected_submission=None):
    from .hm_whole_job_controller_budget_v1 import HMWholeControllerBudgetV1
    need(type(custody) is HMWholeControllerCustodyV1 and not custody.is_endpoint and
         type(budget) is HMWholeControllerBudgetV1 and type(event) is HostEvent and
         custody.plan is budget.plan and type(budget.plan) is HMWholeJobPlanV1,
         'actual original C owners and same compiled whole-job profile')
    try:
        custody.require_original()
        need(custody.channel.owns_completed_event(event) and event.body['status'] == 'observed' and
             event.source == budget.plan.body['observer_source'] and
             event.campaign == budget.plan.body['campaign_id'],
             'actual nonreplayable response from the original qualified H channel')
        result = event.body['result']; closed(result, ('schema', 'return'))
        need(result['schema'] == 'hm_whole_stage_dispatch_response_v1', 'distinct full-stage response')
        record = wrapped(result['return']);closed(record, FIELDS)
        sequence = integer(record['sequence'], 1);row = budget.plan.stage(sequence)
        need(not budget.active and budget.pending_sequence == sequence and
             record['schema'] == 'hm_whole_stage_public_return_v1' and
             record['profile'] == budget.plan.pin and record['stage'] == row['stage'] and
             record['previous_return'] == budget.previous_return and
             record['subject'] == expected_subject and record['request'] == expected_request,
             'same suspended original request, sequence, subject and predecessor')
        validate_stage_chain(budget.plan,
            resource_plan={'descriptor': budget.plan.resource_plan_pin, 'body': budget.plan.resource_plan},
            lease=record['lease'], subject=record['subject'], request=record['request'])
        start = wrapped(record['start']); lease = record['lease']['body']; subject = record['subject']['body']
        need(start['schema'] == 'hm_whole_stage_start_v1' and start['profile'] == budget.plan.pin and
             start['lease'] == record['lease']['descriptor'] and
             start['subject'] == record['subject']['descriptor'] and
             start['controller'] == custody.controller_identity and start['host'] == lease['host'],
             'original actual H start and C process binding')
        for key in ('stage', 'sequence', 'stage_started_ns', 'deadline_ns', 'evidence_deadline_ns'):
            need(start[key] == lease[key], 'same exact original start ' + key)
        worker = process(start['worker'])
        need(worker['source'] == budget.plan.body['worker_source'] and
             worker['launch_nonce'] == row['worker_nonce'] and
             worker['parent_launch'] == record['lease']['descriptor'] and
             worker not in (lease['host'], lease['controller']), 'distinct exact original W source/launch')
        need(type(full_plan) is dict and len(full_plan.get('jobs', [])) == 8223 and
             len({j['id'] for j in full_plan['jobs']}) == 8223 and
             pin(encode(full_plan)) == record['full_plan'], 'entire exact original 8223-job scientific plan')
        custody.meter.charge('work_units', bounded_size(full_plan))
        for key in ('scope', 'inputs', 'full_plan', 'submission'):
            need(record[key] == subject[key], 'same complete scientific identity ' + key)
        descriptor(record['result']);integer(record['stage_finished_ns'], 1)
        need(record['native_closed'] is True and record['whole_qualification'] is False and
             lease['stage_started_ns'] <= start['observed_ns'] <= record['stage_finished_ns'] <=
             lease['evidence_deadline_ns'], 'actual stage lifecycle within original full hold; no science claim')
        outer = _actual_outer(record['outer'], worker=worker, plan=budget.plan, row=row)
        scientific = record['scientific_budget']
        closed(scientific, ('limits', 'reserved', 'deadline_ns', 'terminal_failed', 'physical_IO_RSS_metered'))
        need(scientific['terminal_failed'] is False and
             scientific['limits'] == row['logical'] and scientific['deadline_ns'] == lease['deadline_ns'],
             'unchanged original scientific Budget and deadline')
        for key in row['logical']:
            integer(scientific['reserved'][key]);need(scientific['reserved'][key] <= row['logical'][key],
                                                 'original scientific logical allowance')
        reference = row['stage'] == 'reference';child = streams = candidate_raw = None
        if reference:
            ids = record['completed_reference_ids']
            need(type(ids) is list and len(ids) == 8223 and set(ids) == {j['id'] for j in full_plan['jobs']} and
                 selected_submission is None and record['candidate_receipt'] is None and
                 record['reference_body_withheld'] is True, 'full reference graph with protected bodies withheld')
        else:
            need(record['completed_reference_ids'] is None and record['reference_body_withheld'] is False and
                 type(selected_submission) is dict and pin(encode(selected_submission)) == record['submission'],
                 'same original own-run candidate and no reference body')
            candidate = wrapped(record['candidate_receipt']);candidate_raw = encode(candidate)
            need(record['candidate_receipt']['descriptor'] == record['result'], 'exact actual candidate result')
            closed(candidate, ('submission', 'result', 'completion', 'stdout_hex', 'stderr_hex', 'scientific_qualification'))
            need(candidate['submission'] == record['submission'], 'original candidate invocation identity')
            child = candidate['completion'];closed(child, ('returncode', 'natural_completion', 'pid', 'forced'))
            need(type(child['returncode']) is int and child['returncode'] == 0 and
                 child['natural_completion'] is True and child['forced'] is False,
                 'actual candidate scientific child completion')
            integer(child['pid'], 1);streams = {}
            for name in ('stdout', 'stderr'):
                value = candidate[name + '_hex']
                need(type(value) is str and len(value) % 2 == 0 and
                     len(value) <= 2 * selected_submission['stream_limit_bytes'] and
                     all(c in '0123456789abcdef' for c in value), 'whole original bounded child stream')
                custody.meter.charge('work_units', len(value) + 4096)
                custody.meter.charge('retained_bytes', len(value) // 2)
                streams[name] = pin(bytes.fromhex(value))
        d = result['return']['descriptor']
        return HMWholeStageAdmissionV1(_TOKEN, plan=budget.plan, sequence=sequence,
            complete=True, eligible=True, record=record, record_pin=d, return_key=encode(d),
            previous_return=record['previous_return'], subject='reference' if reference else 'candidate',
            completion={'result': record['result'], 'ordered_domain':
                        [j['id'] for j in full_plan['jobs']] if reference else [record['submission']]},
            original_child_completion=child, original_child_streams=streams,
            candidate_receipt_pin=None if reference else record['result'], candidate_receipt_raw=candidate_raw,
            outer=outer, event=event)
    except BaseException as error:
        budget._own(error);raise
