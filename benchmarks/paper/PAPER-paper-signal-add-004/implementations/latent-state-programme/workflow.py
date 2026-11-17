"""Complete sequential program coordination with externally trusted closures.

The executor is operator infrastructure, never candidate-provided Python. Its
implementation/image/resource enforcement must be independently qualified. No
function here calls a native library, starts an experiment at import, or accepts
a candidate-authored exit/energy receipt as an execution observation.
"""
import math
import json
from core import ROLES, HMM, BRANCHES, CONTROLS, TASK, need, identity, encoded, native_jobs, held_jobs, select_sets
from admission import output_pins


def criterion(job):
    if job['branch'] == 'ctf_static':
        return None
    if job['phase'] == 'native' and job['branch'] == 'ctf_dynemo':
        return 'literal_final_epoch_history_loss'
    return 'historical_model_free_energy_on_training_sequences'


def validate_policy(policy):
    need(set(policy) == {'schema', 'task_id', 'source_freeze', 'images', 'exposure_audits',
                        'limits', 'native_inputs', 'held_preparations', 'programs',
                        'provider_source_pin', 'provider_qualification_pin'},
         'Complete operator policy, not a candidate readiness flag')
    need(policy['schema'] == 'osl_full_program_policy_v1' and policy['task_id'] == TASK,
         'Exact task policy')
    need(set(policy['images']) == set(ROLES) and set(policy['exposure_audits']) == set(ROLES)
         and set(policy['programs']) == set(ROLES), 'Separate A/B/reference images, audits and programs')
    for program in policy['programs'].values():
        need(type(program) is dict and set(program) == {'entrypoint', 'source_sha256', 'selection_producer_source_pin'}
             and type(program['entrypoint']) is list and program['entrypoint']
             and all(type(v) is str and v for v in program['entrypoint'])
             and all(type(program[k]) is str and len(program[k]) == 64
                     for k in ('source_sha256', 'selection_producer_source_pin')),
             'Closed reviewed program and independent selection-producer identities')
    need(set(policy['limits']) == {'phase_wall_s', 'phase_output_bytes', 'phase_read_bytes',
                                  'phase_write_bytes', 'phase_memory_bytes', 'aggregate_wall_s',
                                  'aggregate_read_bytes', 'aggregate_write_bytes'}, 'All future resource bounds')
    need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in policy['limits'].values()),
         'Prospectively specified finite positive bounds; no invented defaults')
    need(set(policy['native_inputs']) == set(BRANCHES),
         'All six native input bindings')
    need(set(policy['held_preparations']) == {f'{b}:{f}' for b in HMM for f in range(5)},
         'All twenty full held-person preparations')


def request(job, policy, clock_binding=None):
    """No private query pool in any candidate training/native-role request."""
    role, branch = job['role'], job['branch']
    if job['phase'] == 'native':
        view = policy['native_inputs'][branch]
    else:
        prepared = policy['held_preparations'][f'{branch}:{job["fold"]}']
        need(set(prepared) == {'representation_id', 'training_controls', 'operator_query_pin',
                              'static_reference_pin'}, 'Complete independent operator preparation')
        view = {'representation_id': prepared['representation_id'],
                'training': prepared['training_controls'][job['control']]}
    return {'schema': 'osl_attempt_request_v1', 'task_id': TASK, 'job': job,
            'source_freeze': policy['source_freeze'], 'image': policy['images'][role],
            'exposure_audit': policy['exposure_audits'][role], 'program': policy['programs'][role],
            'input_view': view, 'limits': policy['limits'], 'fresh_context': job['id'],
            'network': 'disabled', 'query_mount': False if job['phase'] == 'held_hmm' else None,
            'clock': clock_binding}


def close(job, req, closure, independently_observed_pin, observed_at):
    """The trusted provider supplies the pin out-of-band from candidate output."""
    need(identity(closure) == independently_observed_pin, 'Trusted external closure, not candidate JSON')
    expected_keys = {'schema', 'request_id', 'job_id', 'natural_exit', 'exit_code', 'reason',
                         'oom', 'deadline_exceeded', 'provider_error', 'outputs',
                         'training_measurement', 'cost', 'timing'}
    need(set(closure) in (expected_keys, expected_keys|{'resource_observation'}), 'Exact complete external disposition')
    need(closure['schema'] == 'osl_attempt_closure_v1' and closure['request_id'] == identity(req)
         and closure['job_id'] == job['id'], 'Actual phase/input/source/image binding')
    need(set(closure['cost']) == {'elapsed_s', 'read_bytes', 'write_bytes', 'peak_memory_bytes'}
         and all(type(closure['cost'][k]) in (int, float) and math.isfinite(closure['cost'][k]) and closure['cost'][k] >= 0
                 for k in ('elapsed_s','read_bytes','write_bytes')), 'Observed scoped costs retained, including failures')
    c, limits = closure['cost'], req['limits']
    resource_observation = closure.get('resource_observation')
    if c['peak_memory_bytes'] is None:
        need(type(resource_observation) is dict and set(resource_observation) ==
             {'scope','producer_read_bytes','producer_write_bytes','exact_peak_memory_bytes',
              'enforced_memory_bytes','enforced_memory_observed','transport_receipt_pin'} and
             resource_observation['scope'] == 'observed_transport_and_staging_only' and
             resource_observation['producer_read_bytes'] is None and resource_observation['producer_write_bytes'] is None and
             resource_observation['exact_peak_memory_bytes'] is None and
             type(resource_observation['enforced_memory_observed']) is bool and
             ((resource_observation['enforced_memory_observed'] and type(resource_observation['enforced_memory_bytes']) is int
               and resource_observation['enforced_memory_bytes'] > 0) or
              (not resource_observation['enforced_memory_observed'] and resource_observation['enforced_memory_bytes'] is None)) and
             type(resource_observation['transport_receipt_pin']) is str and len(resource_observation['transport_receipt_pin']) == 64,
             'Unknown producer measurements remain null; exact observed enforced memory ceiling is separate')
        memory_within = resource_observation['enforced_memory_observed'] and resource_observation['enforced_memory_bytes'] <= limits['phase_memory_bytes']
    else:
        need(resource_observation is None, 'Measured-resource closure has no unsupported alternate observation schema')
        need(type(c['peak_memory_bytes']) in (int,float) and math.isfinite(c['peak_memory_bytes'])
             and c['peak_memory_bytes'] >= 0, 'Measured peak or explicit unmeasured resource envelope')
        memory_within = c['peak_memory_bytes'] <= limits['phase_memory_bytes']
    t = closure['timing']
    need(type(t) is dict and set(t) == {'origin', 'deadline', 'started', 'finished'} and
         all(type(v) in (float, int) and math.isfinite(v) for v in t.values()),
         'Actual external original-clock closure')
    need(req['clock'] is not None and t['origin'] == req['clock']['origin'] and
         t['deadline'] == req['clock']['phase_deadline'] and
         t['origin'] <= t['started'] <= t['finished'], 'Original origin/deadline preserved')
    need(type(observed_at) in (int, float) and math.isfinite(observed_at)
         and t['finished'] <= observed_at and t['started'] >= req['clock'].get('requested_at', t['origin']),
         'Closure times cannot exceed the independent fresh observed clock')
    need(c['elapsed_s'] + 1e-9 >= t['finished']-t['started'], 'Retain full observed execution duration')
    within = (c['elapsed_s'] <= limits['phase_wall_s'] and c['read_bytes'] <= limits['phase_read_bytes']
              and c['write_bytes'] <= limits['phase_write_bytes'] and
              memory_within and t['finished'] <= t['deadline'] and observed_at <= t['deadline'])
    success = (closure['natural_exit'] is True and closure['exit_code'] == 0 and
               closure['oom'] is False and closure['deadline_exceeded'] is False and
               closure['provider_error'] is False and within)
    if not success:
        need(type(closure['reason']) is str and closure['reason'], 'Explicit failed disposition')
    energy = None
    selection_complete = True
    selection_reason = None
    if success and job['branch'] != 'ctf_static':
        measurement = closure['training_measurement']
        if measurement is None:
            selection_complete = False
            selection_reason = 'original_selection_statistic_not_independently_established'
        else:
            need(type(measurement) is dict and set(measurement) ==
                 {'value', 'producer_source_pin', 'input_binding', 'candidate_supplied',
                  'query_used', 'criterion', 'evidence_mode', 'evidence_pin'},
                 'Complete independently observed original selection statistic')
            need(measurement['candidate_supplied'] is False and measurement['query_used'] is False
                 and measurement['input_binding'] == identity(req['input_view'])
                 and measurement['producer_source_pin'] == req['program']['selection_producer_source_pin']
                 and type(measurement['evidence_pin']) is str and len(measurement['evidence_pin']) == 64,
                 'Pinned trusted producer/evidence, no submitted/query statistic')
            need(measurement['criterion'] == criterion(job), 'Literal original selection criterion')
            permitted = {'independent_exact_training_trajectory_replay'}
            if job['role'] != 'A':
                permitted.add('trusted_exact_source_training_observation')
            if criterion(job) != 'literal_final_epoch_history_loss':
                permitted.add('independent_exact_source_parameter_evaluation')
            need(measurement['evidence_mode'] in permitted,
                 'Final DyNeMo weights cannot reconstruct historical evolving epoch loss')
            need(type(measurement['value']) in (int, float) and math.isfinite(measurement['value']),
                 'Finite original selection statistic')
            energy = measurement['value']
    if success:
        need(output_pins(closure['outputs']) <= limits['phase_output_bytes'],
             'Actual captured outputs within allocation')
    return {'job': job, 'status': 'completed' if success and selection_complete else 'failed',
            'training_free_energy': energy, 'capture_pin': independently_observed_pin,
            'selection_criterion': criterion(job), 'selection_complete': success and selection_complete,
            'natural_execution_completed': success,
            'outputs': closure['outputs'], 'reason': selection_reason or closure['reason'],
            'cost': closure['cost'], 'resource_observation': resource_observation,
            'whole_producer_actual_resource_measurement': resource_observation is None}


def group_selection(dispositions, phase, role):
    jobs = native_jobs(role) if phase == 'native' else held_jobs(role)
    need(len(dispositions) == len(jobs) and [x['job'] for x in dispositions] == jobs,
         'Every scheduled attempt, in frozen order')
    groups, static = {}, []
    for r in dispositions:
        j = r['job']
        if j['branch'] == 'ctf_static':
            static.append(r)
            continue
        key = (j['branch'],) if phase == 'native' else (j['branch'], j['fold'], j['control'])
        groups.setdefault(key, []).append({'fit_set': j['fit_set'], 'attempt': j['attempt'],
            'status': r['status'], 'training_free_energy': r['training_free_energy'],
            'capture_pin': r['capture_pin']})
    selected = {':'.join(map(str, key)): select_sets(rows) for key, rows in groups.items()}
    return {'phase': phase, 'role': role, 'groups': selected, 'static': static,
            'complete': all(x['complete'] for x in selected.values()) and
                        all(x['status'] == 'completed' for x in static)}


def execute(policy, expected_policy_id, executor, observer, journal, clock, original_clock=None):
    """Future execution through an explicitly supplied trusted operator backend.

    `executor` enforces reviewed image/mount/resource isolation and supplies
    actual natural-exit observations. `observer` independently obtains the
    expected closure pin; neither may be supplied by the candidate. Injected
    mocks are engineering controls only, never real execution attestations.
    """
    def snapshot(value):
        return json.loads(encoded(value))
    # Canonical private copies sever mutable aliases across every callback.
    policy = snapshot(policy)
    need(identity(policy) == expected_policy_id, 'Externally selected exact operator policy')
    validate_policy(policy)
    last_observed = None
    def observe_clock():
        nonlocal last_observed
        now = clock()
        need(type(now) in (int, float) and math.isfinite(now)
             and (last_observed is None or now >= last_observed), 'Finite monotonic independent clock')
        last_observed = now
        return now
    now = observe_clock()
    if original_clock is None:
        origin, deadline = now, now + policy['limits']['aggregate_wall_s']
    else:
        need(set(original_clock) == {'origin', 'deadline'} and
             all(type(x) in (int, float) and math.isfinite(x) for x in original_clock.values()) and
             original_clock['origin'] <= now <= original_clock['deadline'] and
             original_clock['deadline']-original_clock['origin'] <= policy['limits']['aggregate_wall_s'],
             'Inherited whole-program origin/deadline, never a fresh extension')
        origin, deadline = original_clock['origin'], original_clock['deadline']
    need(math.isfinite(deadline), 'Representable original aggregate deadline')
    def emit(event):
        journal(snapshot(event))
    def within_aggregate(cost):
        now = observe_clock()
        okay = (now <= deadline and cost['read_bytes'] <= policy['limits']['aggregate_read_bytes']
                and cost['write_bytes'] <= policy['limits']['aggregate_write_bytes'])
        if not okay:
            emit({'event': 'aggregate_closure_failed', 'actual_observed': now,
                  'origin': origin, 'deadline': deadline, 'cost': cost, 'complete': False})
            raise ValueError('Actual aggregate closure exceeded original allocation')
        return now
    emit({'event': 'program_start', 'policy_id': expected_policy_id,
          'origin': origin, 'deadline': deadline})
    total = {'elapsed_s': 0., 'read_bytes': 0, 'write_bytes': 0}
    within_aggregate(total)
    results = []
    for phase, factory in (('native', native_jobs), ('held_hmm', held_jobs)):
        for role in ROLES:
            dispositions = []
            for job in factory(role):
                limits = policy['limits']
                if not (within_aggregate(total) + limits['phase_wall_s'] <= deadline
                        and total['read_bytes'] + limits['phase_read_bytes'] <= limits['aggregate_read_bytes']
                        and total['write_bytes'] + limits['phase_write_bytes'] <= limits['aggregate_write_bytes']):
                    emit({'event': 'allocation_stop_before_dispatch', 'next_job': job,
                             'cost': total.copy(), 'origin': origin, 'deadline': deadline,
                             'completion': False})
                    raise ValueError('Insufficient prospective remaining allocation')
                now = observe_clock()
                req = request(job, policy, {'origin': origin, 'program_deadline': deadline,
                                           'requested_at': now,
                                           'phase_deadline': min(deadline, now+limits['phase_wall_s'])})
                req = snapshot(req)
                request_id = identity(req)
                emit({'event': 'attempt_start', 'request_id': request_id, 'job': job,
                         'origin': origin, 'deadline': req['clock']['phase_deadline']})
                if within_aggregate(total) >= req['clock']['phase_deadline']:
                    emit({'event': 'phase_deadline_before_dispatch', 'job': job,
                          'request_id': request_id, 'original_phase_deadline': req['clock']['phase_deadline'],
                          'complete': False, 'executor_called': False})
                    raise TimeoutError('Original phase window consumed before dispatch')
                returned = None
                closure = None
                evidence_encoding_error = None
                try:
                    returned = executor(snapshot(req))
                    try:
                        closure = snapshot(returned)
                    except (TypeError, ValueError, RecursionError) as error:
                        evidence_encoding_error = type(error).__name__
                        raise ValueError('External closure is not primitive canonical metadata') from error
                    observe_clock()
                    closure_pin = observer(job['id'], request_id)
                    observed = observe_clock()
                    result = close(snapshot(job), req, closure, closure_pin, observed)
                except Exception as error:
                    emit({'event': 'unadmitted_external_attempt', 'job': job,
                             'error_type': type(error).__name__, 'origin': origin, 'deadline': deadline,
                             'prior_cost': total.copy(), 'completion': False,
                             'returned_closure': closure,
                             'returned_closure_identity': None if closure is None else identity(closure),
                             'returned_evidence_encoding_error': evidence_encoding_error,
                             'returned_object_type': None if returned is None else type(returned).__name__,
                             'unadmitted_cost_and_outputs_retained_in_closure': closure is not None,
                             'unknown_unadmitted_cost_is_not_zero': True,
                             'actual_last_observed_clock': last_observed})
                    raise
                emit({'event': 'attempt_disposition', **result})
                dispositions.append(snapshot(result))
                for key in total:
                    total[key] += result['cost'][key]
                within_aggregate(total)
            results.append({'dispositions': dispositions,
                            'selection': group_selection(dispositions, phase, role)})
    finished = within_aggregate(total)
    answer = {'task_id': TASK, 'policy_id': expected_policy_id, 'phases': results,
            'cost': total, 'complete': all(x['selection']['complete'] for x in results),
            'origin': origin, 'deadline': deadline, 'actual_observed_wall_s': finished-origin,
            'scientific_qualification': False, 'historical_seed_parity': False,
            'cost_scope': 'attempt_dispatch_and_closure_subtotal_only',
            'whole_study_resource_closure': False}
    emit({'event': 'program_return', 'complete': answer['complete'], 'cost': total.copy(),
          'origin': origin, 'deadline': deadline, 'actual_finished': finished})
    # Includes the last observer/journal. No final-callback overrun may return a
    # successful completion, even if every process itself exited in time.
    answer['actual_observed_wall_s'] = within_aggregate(total)-origin
    return answer
