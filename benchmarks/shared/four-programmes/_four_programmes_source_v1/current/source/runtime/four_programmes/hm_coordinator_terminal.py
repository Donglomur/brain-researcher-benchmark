"""Original HM C report/terminal notice; never an H process-closure producer.

Only already-loaded captured HM classes and their actual owned return objects
are consumed. Missing issuer, StageHost or installed qualification is not supplied
by this module. There is no model or scientific computation. Final transport
still uses the original qualified channel and its actual I/O.
"""
from .common import need, closed, pin, encode, parse, bounded_size, failure
from .source_session import SourceSession
from .channel import RootChannel

PROGRAMME = 'PAPER-paper-method-replacement-016'


def _module(session, name):
    module = session.modules.get(name)
    need(module is not None and vars(module).get('__loader__') is session and
         vars(module).get('__name__') == session.prefix + '.' + name,
         'actual already-loaded captured HM module, no new final-stage import')
    return vars(module)


def _owner(coordinator):
    session = getattr(coordinator, 'session', None)
    need(type(session) is SourceSession and session.programme == PROGRAMME and
         not session.closed, 'same live original HM source session')
    cm = _module(session, 'coordinator')
    need(type(coordinator) is cm['Coordinator'], 'actual original HM Coordinator')
    bm = _module(session, 'stage_budget')
    gm = _module(session, 'guard')
    sm = _module(session, 'stage_closure')
    budget = coordinator.budget
    need(type(budget) is bm['ExclusiveBudget'] and budget.owner == 'C' and
         type(coordinator.score_io) is bm['PrepaidScoreIO'] and
         coordinator.score_io.budget is budget,
         'same actual C writer and its existing complete C05 score reservation')
    return session, budget, coordinator.score_io, bm, gm, sm


def _full_scientific_shape(coordinator, session, original_encode):
    """Retain complete already-scored support without recomputing a metric."""
    scope = coordinator.scope
    conditions = _module(session, 'scope')['condition_rows'](scope)
    rois = [roi for group in scope['roi_groups'].values() for roi in group]
    need(len(conditions) == 335 and len({row['id'] for row in conditions}) == 335 and
         len(rois) == len(set(rois)) == 17 and len(scope['subjects']) == 10 and
         len(set(scope['subjects'])) == 10, 'full original335 conditions17 ROIs10 people')
    expected = [(condition['id'], roi) for condition in conditions for roi in rois]
    reference = coordinator.reference
    need(type(reference) is dict and set(coordinator.candidates) == {'A', 'B'} and
         set(coordinator.seals) == {'A', 'B'} and set(coordinator.scores) == {'A', 'B'},
         'complete previously captured/scored original reference and both candidates')
    reference_document = reference['document']
    need(pin(original_encode(reference_document)) ==
         {key: reference['submission'][key] for key in ('bytes', 'sha256')},
         'same actual canonical consume-Publisher reference document after scoring')
    for arm in ('A', 'B'):
        candidate = coordinator.candidates[arm]
        seal = coordinator.seals[arm]
        need(seal['original'] is candidate and type(seal['raw']) is bytes and
             original_encode(candidate['document']) == seal['raw'] and
             pin(seal['raw']) == seal['identity'],
             'same full original candidate after both pre-reference seals')
    documents = [reference_document] + [coordinator.candidates[a]['document'] for a in ('A', 'B')]
    for document in documents:
        need(document['schema'] == 'hundred_models_submission_v2' and
             document['scope'] == coordinator.identities['scope'] and
             document['subjects'] == scope['subjects'] and
             [(row['condition'], row['roi']) for row in document['rsa']] == expected,
             'complete ordered biological support, never candidate-process count as scientific scope')
        need([row['figure'] for row in document['figures']] == list(range(1, 23)) and
             [row['table'] for row in document['tables']] == [1, 2],
             'all original22 figure and two table obligations retained')
        for row, reference_row in zip(document['rsa'], reference_document['rsa']):
            layers = reference_row['layers']
            need(type(layers) is list and len(layers) == len(set(layers)) > 0 and
                 row['layers'] == layers and len(row['values']) == len(layers) and
                 all(type(values) is list and len(values) == 10 for values in row['values']),
                 'every original layer and all ten people, no subset terminal success')


def validate_final_coordinator_state_v1(coordinator):
    """Validate the real report return and final C prefix, before freezing it.

    Validation consumes the same prepaid C05 credit. It neither runs the scorer
    again nor creates qualification, an H observation, or a later allowance.
    """
    session, budget, io, bm, gm, sm = _owner(coordinator)
    need(coordinator.primary is None and not coordinator.failures and
         coordinator.phase == 'reported_provisional' and budget.active and
         not budget.failed and budget.primary is None and budget.owner == 'C' and
         budget.row == 'C05' and type(budget.generation) is int and budget.generation == 3 and
         budget.pending is None and budget.guard is None and budget.score_reserved and
         coordinator.final_terminal_raw is None and coordinator.final_notice_attempted is False and
         coordinator.final_notice_pin is None,
         'one successful original C05 report before first final notice')
    budget.require_operation('report')
    # Charge complete existing objects before serializing or traversing them.
    objects = [coordinator.scope, coordinator.inputs, coordinator.plan,
               coordinator.reference['document'], coordinator.scores, coordinator.paired]
    objects.extend(coordinator.candidates[a]['document'] for a in ('A', 'B'))
    io.charge('work', sum(bounded_size(value) for value in objects) * 64 + 4096)
    original_encode = gm['encoded']
    need(coordinator.identities == {
        'scope': pin(original_encode(coordinator.scope)),
        'inputs': pin(original_encode(coordinator.inputs)),
        'plan': pin(original_encode(coordinator.plan))}, 'unchanged complete original scientific inputs and plan')
    jobs = coordinator.plan['jobs']
    ids = [job['id'] for job in jobs]
    need(len(ids) == len(set(ids)) == 8223 and ids[8221:] == ['consume', 'report'] and
         set(coordinator.reference['original_jobs']) == set(ids),
         'all8223 actual original reference jobs including consume and report')
    stages = coordinator.stages
    need(type(stages) is list and len(stages) == 3 and len(budget.consumed) == 3,
         'exactly the three actual restored original stages')
    previous = None
    controller = None
    for sequence, stage in enumerate(stages, 1):
        need(type(stage) is sm['StageAdmission'] and stage.plan is budget.plan and
             stage.complete is True and stage.eligible is True and
             budget.consumed.get(encode(stage.return_pin)) is stage,
             'same actual source-owned H admission already restored into this C')
        lease = stage.lease
        need(type(lease['sequence']) is int and lease['sequence'] == sequence and
             lease['stage'] == ('reference' if sequence == 1 else 'candidate:' + ('A' if sequence == 2 else 'B')) and
             lease['previous_return'] == previous and
             all(lease[key] == value for key, value in coordinator.identities.items()),
             'complete actual reference/A/B lease chain and unchanged scientific scope')
        domain = ids if sequence == 1 else [lease['submission']]
        need(stage.completion['ordered_domain'] == domain,
             'full reference graph; distinct singleton own-run candidate process domains')
        if sequence > 1:
            arm = 'A' if sequence == 2 else 'B'
            need(lease['submission'] == pin(original_encode(coordinator.submissions[arm])) and
                 stage.candidate_receipt_pin == coordinator.candidates[arm]['receipt'],
                 'same actual original selected candidate return')
        else:
            need(stage.completion['result'] == coordinator.reference['complete'],
                 'same original full reference completion return')
        if controller is None:
            controller = lease['controller']
        need(lease['controller'] == controller and stage.start['controller'] == controller and
             stage.completion['controller'] == controller, 'one unchanged original C process identity')
        previous = stage.return_pin
    need(budget.previous_return == previous, 'final C prefix extends the actual third return')
    _full_scientific_shape(coordinator, session, original_encode)
    publication = coordinator.report_publication
    descriptor = coordinator.report_descriptor
    raw = coordinator.report_raw
    need(type(publication) is gm['Publisher'] and publication.budget is io and publication.created is True and
         type(raw) is bytes and type(descriptor) is dict,
         'actual original completed report Publisher and its actual write return')
    gm['descriptor'](descriptor)
    need(descriptor['path'] == 'REPORT.json' and pin(raw) ==
         {key: descriptor[key] for key in ('bytes', 'sha256')} and
         publication.outputs == [{**descriptor, 'complete': True}],
         'exact sole completed report write, never a later supplied descriptor')
    io.charge('work', len(raw) * 64 + 4096)
    report = gm['strict'](raw)
    need(original_encode(report) == raw and
         report['schema'] == 'four_hundred_models_complete_original_comparison_v1' and
         report['pair_id'] == coordinator.pair_id and report['full_original_jobs'] == 8223 and
         report['plan'] == coordinator.identities['plan'] and
         report['original_scores'] == coordinator.scores and
         report['original_paired_comparison'] == coordinator.paired and
         report['candidate_seals'] == {a: coordinator.seals[a]['identity'] for a in ('A', 'B')} and
         report['original_stage_receipts'] == [stage.record_pin for stage in stages] and
         report['original_failures'] == coordinator.failures and
         report['original_budget'] == budget.snapshot() and
         report['improvement'] == {'status': 'required_unscorable', 'reason': 'independent private-panel producer not selected'} and
         report['original_C_exit_still_required'] is True and report['scientific_qualification'] is False and
         report['SOTA_claim'] is False,
         'actual unchanged full original report, without exit/qualification/frontier promotion')
    terminal = budget.state()
    previous_terminal = stages[-1].terminal
    bm['state_valid'](previous_terminal, budget.plan)
    for key in ('campaign_id', 'original_clock_binding', 'deadline_ns', 'limits', 'reservation_plan'):
        need(terminal[key] == previous_terminal[key], 'one original final programme opportunity')
    need(terminal['mode'] == 'active_C' and terminal['failed'] is False and terminal['generation'] == 3 and
         terminal['previous_return'] == stages[-1].return_pin,
         'exact successful generation3 C prefix after final restored W')
    for before, after in zip(previous_terminal['row_usage'], terminal['row_usage']):
        need(before['id'] == after['id'], 'all eighteen unchanged ordered original budget rows')
        for key, used in before['logical'].items():
            need(after['logical'][key] >= used and
                 (before['id'] in ('C03', 'C04', 'C05') or after['logical'][key] == used),
                 'only actual final C rows extend last original W terminal')
    need(budget.rows['C05'] == budget.plan.rows['C05']['logical'],
         'whole original C05 reservation retained, no apparent refund after scoring')
    terminal_raw = encode(terminal)
    io.check()
    return terminal_raw


def _retain_failure(coordinator, error):
    # Transport failure after the immutable terminal snapshot cannot rewrite its
    # source budget prefix. It remains a separately retained final-notice failure.
    if coordinator.budget.active:
        coordinator._own(error, 'HM_original_final_notice')
    else:
        if coordinator.primary is None:
            coordinator.primary = error
        coordinator.phase = 'final_notice_failed'
        coordinator.failures.append({'operation': 'HM_original_final_notice',
            'original_failure': failure(error), 'same_original_primary': error is coordinator.primary,
            'terminal_prefix': pin(coordinator.final_terminal_raw), 'original_budget_frozen': True})


def _original_channel_events(coordinator, channel, io):
    previous_sequence = 0
    for stage in coordinator.stages:
        event = stage.event
        need(channel.owns_completed_event(event), 'same actual retained source-owned channel event')
        io.charge('work', bounded_size(event.body) * 64 + 4096)
        need(pin(encode(event.body)) == event.raw_pin and
             type(event.sequence) is int and type(event.body['sequence']) is int and
             previous_sequence < event.sequence == event.body['sequence'] <= channel.sequence and
             event.source == event.body['source'] == channel.binding['source'] and
             event.campaign == event.body['campaign'] == channel.binding['campaign'] and
             event.body['status'] == 'observed',
             'unchanged original canonical stage response and ordered actual channel sequence')
        result = event.body['result']
        need(result['schema'] == 'hundred_models_original_stage_response_v2' and
             result['lease'] == stage.lease_pin and result['start'] == stage.start_pin and
             result['completion'] == stage.completion_pin and result['budget_return'] == stage.return_pin and
             result['receipt_admission'] == stage.record_pin and
             result['candidate_receipt'] == stage.candidate_receipt_pin,
             'actual same event result consumed into each original StageAdmission')
        previous_sequence = event.sequence


def send_original_hm_final_notice_v1(*, coordinator, channel):
    """Freeze C exactly once, notify original H and close without awaiting a reply."""
    session, budget, io, bm, gm, sm = _owner(coordinator)
    # No retry effects or revalidation after an earlier actual terminal failure.
    if coordinator.primary is not None:
        raise coordinator.primary
    need(coordinator.final_notice_attempted is False, 'one original final notice attempt, never replay')
    primary = None
    owned_channel = None
    try:
        need(type(channel) is RootChannel and
             channel.binding['campaign'] == budget.plan.body['campaign_id'] and
             channel.binding['source'] == budget.plan.body['observer_source'],
             'same original qualified C/H source and campaign')
        need(len(coordinator.stages) == 3 and
             all(channel.owns_completed_event(stage.event) for stage in coordinator.stages),
             'all three actual restored events belong to this original channel')
        # Cleanup custody follows actual event ownership, never just a matching
        # type or descriptor. Health and terminal success are later conditions.
        owned_channel = channel
        need(not channel.closed and not channel.failed and channel.outstanding is None,
             'original owned channel healthy with no outstanding operation')
        _original_channel_events(coordinator, channel, io)
        terminal_raw = validate_final_coordinator_state_v1(coordinator)
        body = {'schema': 'four_original_coordinator_final_notice_v1', 'programme': PROGRAMME,
                'campaign': budget.plan.body['campaign_id'],
                'report': {**coordinator.report_descriptor,
                           'path': str(coordinator.report_publication.root / coordinator.report_descriptor['path'])},
                'report_kind': 'normal_path_provisional', 'original_C_exit_observed': False,
                'terminal_budget_state': parse(terminal_raw, len(terminal_raw)),
                'last_stage_return': coordinator.stages[-1].return_pin}
        # All report/validation work is finished. Only the earlier separate
        # channel transport owner may perform effects after this point.
        io.check()
        coordinator.final_terminal_raw = terminal_raw
        coordinator.final_notice_attempted = True
        budget.active = False
        coordinator.phase = 'final_notice_pending'
        coordinator.final_notice_pin = channel.send('final_report', body)
        need(coordinator.final_notice_pin is channel.outstanding,
             'actual original channel send return retained, no manufactured acknowledgement')
        coordinator.phase = 'final_notice_sent'
    except BaseException as error:
        primary = error
        _retain_failure(coordinator, error)
    finally:
        if owned_channel is not None:
            try:
                owned_channel.close()
            except BaseException as error:
                if primary is None:
                    primary = error
                _retain_failure(coordinator, error)
    if primary is not None:
        raise primary
    return coordinator.final_notice_pin
