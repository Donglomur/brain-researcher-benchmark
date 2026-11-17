"""Typed source preparation, biological splits and control-specific projections.

The neutral corpus is an operator export, not a claim of an available NWB/raw
adapter. Its external native receipt and all missing-source gates are retained.
"""
import copy
import math
import random
from collections import defaultdict
from .base import require, finite, digest, observed_window, ContractError
from .contracts import assert_numerical, assert_endpoint_applicable, gate_report


def endpoint(signal, start, stop):
    return observed_window(signal['times'], signal['values'], start, stop,
                           signal['max_gap'])


def cue_endpoints(signal, aversive=False):
    post, pre = ((1, 15), (-14, 0)) if aversive else ((0, .5), (-.5, 0))
    a, b = endpoint(signal, *post), endpoint(signal, *pre)
    return {'auc': a['integral'] - b['integral'],
            'mean_difference': a['mean'] - b['mean'],
            'baseline_span_corrected_auc': a['integral'] - b['mean'] * a['covered_seconds'],
            'response_span': a['covered_seconds'], 'baseline_span': b['covered_seconds'],
            'response_samples': len(a['times']), 'baseline_samples': len(b['times']),
            'source_windows': {'post': a, 'pre': b}}


def validate_corpus(corpus):
    require(corpus['schema'] == 'reward_neural_operator_export_v1', 'corpus_schema')
    require(type(corpus['synthetic']) is bool, 'synthetic_flag')
    require(isinstance(corpus['source_receipts'], list) and corpus['source_receipts'],
            'native_export_receipts_required')
    report = gate_report(corpus['support'], corpus['qualification'])
    ids, aliases, session_ids = set(), set(), set()
    for a in corpus['animals']:
        require(a['id'] not in ids and bool(a['aliases']), 'animal_identity')
        ids.add(a['id'])
        require(not (set(a['aliases']) & aliases), 'cross_animal_alias_overlap')
        aliases.update(a['aliases'])
        require(a['condition'] in corpus['support'], 'unknown_condition')
        previous_day = -1
        for s in a['sessions']:
            require(s['id'] not in session_ids, 'duplicate_session')
            session_ids.add(s['id'])
            require(type(s['day']) is int and s['day'] >= previous_day, 'session_order')
            previous_day = s['day']
            require(set(s['history']) == {'duration_known', 'delivered_count_known',
                                         'lick_history_known'} and
                    all(type(x) is bool for x in s['history'].values()), 'history_evidence')
            require(finite(s['duration']) > 0 and finite(s['max_gap']) > 0, 'session_extent')
            t, y = s['times'], s['fluorescence']
            require(len(t) == len(y), 'signal_shape')
            if t:
                require(len(t) >= 2 and t[0] >= 0 and t[-1] <= s['duration'], 'signal_extent')
                require(all(finite(v) == v for v in y), 'signal_finite')
                require(all(finite(b) > finite(a0) for a0, b in zip(t, t[1:])), 'clock_order')
            event_ids = set()
            previous_time = -math.inf
            for e in s['events']:
                require(e['id'] not in event_ids, 'duplicate_event')
                event_ids.add(e['id'])
                require(0 <= finite(e['time']) <= s['duration'] and
                        previous_time <= e['time'], 'event_order')
                previous_time = e['time']
                require(e['kind'] in ('cue', 'outcome', 'lick_on', 'lick_off',
                                      'shock_on', 'shock_off', 'distractor', 'milk'),
                        'event_kind')
                require(e['delivered'] is None or type(e['delivered']) is bool,
                        'delivered_not_boolean')
                if e['kind'] in ('outcome', 'shock_on', 'milk'):
                    require(type(e['delivered']) is bool, 'outcome_flag_required')
    require(bool(ids), 'empty_corpus')
    return report


def normalized_event(code, flag, condition):
    """Explicit appetitive author semantics; unknown event codes are rejected."""
    if code == 15:
        return 'cue', None
    if code == 10:
        require(type(flag) is int and flag in (0, 1), 'omission_flag')
        return 'outcome', flag == 0
    if code in (5, 6):
        return ('lick_on' if code == 5 else 'lick_off'), None
    if code == 7 and condition == '60s-CSminus':
        return 'distractor', None
    if code == 7 and condition == '600s-bgdmilk':
        return 'milk', True
    raise ContractError('unsupported_event_semantics')


def prepare(corpus, task, view='retrospective', endpoint_name='cue'):
    report = validate_corpus(corpus)
    require(task in ('NEURAL-045', 'NEURAL-046'), 'task')
    require(view in ('retrospective', 'cue_time'), 'view')
    require(endpoint_name in ('cue', 'reward', 'omission', 'aversive', 'delivery'), 'endpoint_name')
    require(task == 'NEURAL-046' or endpoint_name == 'cue', 'trajectory_endpoint')
    cases, exclusions, eligibility = [], [], []

    def window(session, cue_time, start, stop):
        # Admission is for this required scientific window, never optional context.
        require(session['times'][0] <= cue_time + start and
                session['times'][-1] >= cue_time + stop, 'endpoint_recording_extent')
        return observed_window([x - cue_time for x in session['times']],
                               session['fluorescence'], start, stop, session['max_gap'])

    def extracted(session, cue_time, post, pre):
        a, b = window(session, cue_time, *post), window(session, cue_time, *pre)
        return {'auc': a['integral'] - b['integral'],
                'mean_difference': a['mean'] - b['mean'],
                'baseline_span_corrected_auc': a['integral'] - b['mean'] * a['covered_seconds'],
                'response_span': a['covered_seconds'], 'baseline_span': b['covered_seconds'],
                'response_samples': len(a['times']), 'baseline_samples': len(b['times']),
                'source_windows': {'post': a, 'pre': b},
                'required_windows': {'post': list(post), 'pre': list(pre)}}

    def response(session, cue, outcome, aversive, name):
        t = cue['time']
        if name == 'cue':
            return extracted(session, t, (1, 15), (-14, 0)) if aversive else extracted(session, t, (0, .5), (-.5, 0))
        require(not aversive, 'endpoint_population_inapplicable')
        require(outcome is not None, 'missing_scheduled_outcome')
        if name == 'omission':
            require(outcome['delivered'] is False, 'endpoint_outcome_type_inapplicable')
            return extracted(session, t, (outcome['time'] - t, outcome['time'] - t + 2), (-2, 0))
        require(outcome['delivered'] is True, 'endpoint_outcome_type_inapplicable')
        anchor = outcome['time']
        if name == 'reward':
            require(session['history']['lick_history_known'], 'consumption_history_unverified')
            ongoing = False
            for event in session['events']:
                if event['time'] > outcome['time']: break
                if event['kind'] == 'lick_on': ongoing = True
                elif event['kind'] == 'lick_off': ongoing = False
            if not ongoing:
                anchor = next((e['time'] for e in session['events'] if e['kind'] == 'lick_on' and
                               e['trial_id'] == outcome['trial_id'] and e['time'] > outcome['time']), None)
            require(anchor is not None, 'missing_consumption_anchor')
        value = extracted(session, t, (anchor - t, anchor - t + .5), (-.5, 0))
        value['response_anchor_relative_to_cue'] = anchor - t
        return value

    for a in corpus['animals']:
        elapsed, prior_rewards, prior_cues = 0., 0, 0
        time_known = count_known = True
        aversive = a['condition'].startswith('FC-')
        for s in a['sessions']:
            time_known = time_known and s['history']['duration_known']
            count_known = count_known and s['history']['delivered_count_known']
            outcome_events = [e for e in s['events'] if e['kind'] == ('shock_on' if aversive else 'outcome')]
            outcomes = {e['trial_id']: e for e in outcome_events}
            require(len(outcomes) == len(outcome_events), 'duplicate_trial_outcome')
            cues = [e for e in s['events'] if e['kind'] == 'cue']
            delivered = [e for e in outcome_events if e['delivered']]
            licks = [e['time'] for e in s['events'] if e['kind'] == 'lick_on']
            for index, cue in enumerate(cues):
                key = a['id'] + '/' + s['id'] + '/' + cue['id']
                support = {'id': key, 'animal': a['id'], 'session': s['id'], 'condition': a['condition'],
                           'endpoint': endpoint_name, 'eligible': False, 'status': 'pending'}
                eligibility.append(support)
                out = outcomes.get(cue['trial_id']); t = cue['time']
                secondary = {}; required_windows = {}
                try:
                    require(bool(s['times']), 'no_neural_acquisition')
                    if task == 'NEURAL-046':
                        require(not (endpoint_name == 'cue' and aversive), 'separate_required_aversive_endpoint')
                        require(endpoint_name != 'aversive' or aversive, 'endpoint_population_inapplicable')
                        chosen = 'cue' if endpoint_name == 'aversive' else endpoint_name
                        # Only this endpoint can determine primary case admission.
                        selected = response(s, cue, out, aversive, chosen)
                        secondary[chosen] = selected
                        required_windows = selected['required_windows']
                        lo = min(v[0] for v in required_windows.values())
                        hi = max(v[1] for v in required_windows.values())
                        anchor = t
                        native = observed_window(s['times'], s['fluorescence'], t + lo, t + hi, s['max_gap'])
                        signal = {'times': [x - t for x in native['times']], 'values': native['values'], 'max_gap': s['max_gap']}
                        target = selected['auc']
                        # Wider context and other responses are optional, never admission gates.
                        for other in ('cue', 'reward', 'omission', 'delivery'):
                            if other in secondary: continue
                            try: secondary[other] = response(s, cue, out, aversive, other)
                            except ContractError as error: secondary[other] = {'status': 'source_unscorable', 'reason': str(error)}
                    else:
                        require(aversive or view == 'cue_time' or out is not None, 'missing_scheduled_outcome')
                        anchor = t if aversive or view == 'cue_time' else out['time']
                        lo, hi = ((-15, 25) if aversive else (0, 4.25) if view == 'cue_time' else (-7, 30))
                        native = window(s, anchor, lo, hi)
                        signal = {'times': native['times'], 'values': native['values'], 'max_gap': s['max_gap']}
                        target = list(signal['values']); required_windows = {'trajectory': [lo, hi]}
                except ContractError as error:
                    reason = str(error)
                    inapplicable = reason in ('endpoint_population_inapplicable', 'endpoint_outcome_type_inapplicable',
                                               'separate_required_aversive_endpoint')
                    support.update(status='inapplicable_endpoint_population' if inapplicable else 'source_unscorable', reason=reason)
                    exclusions.append(dict(support))
                    continue
                state_time = out['time'] if endpoint_name in ('reward', 'omission', 'delivery') else t
                f = {'E': elapsed + state_time if time_known else None,
                     'N': prior_rewards + sum(e['time'] < state_time for e in delivered) if count_known else None,
                     'day': s['day'], 'condition': a['condition'], 'sex': a['sex'], 'hardware': a['hardware'],
                     'preceding_interval': t - (cues[index - 1]['time'] if index else 0),
                     'baseline_lick_rate': sum(t - 1.25 <= x < t for x in licks) / 1.25 if s['history']['lick_history_known'] else None,
                     'concurrent_lick_rate': sum(t <= x < t + 1.25 for x in licks) / 1.25 if s['history']['lick_history_known'] else None}
                for name, value in a.get('protocol', {}).items():
                    require(name in ('mean_iri_seconds', 'reward_probability', 'cue_seconds', 'trace_seconds', 'scheduled_trials_per_day'), 'protocol_descriptor')
                    f['protocol_' + name] = finite(value, name)
                cases.append({'id': key, 'animal': a['id'], 'aliases': list(a['aliases']),
                              'session': s['id'], 'condition': a['condition'], 'trial_ordinal': prior_cues + index + 1,
                              'domain': 'aversive' if aversive else 'appetitive',
                              'outcome_stratum': ('unknown_current_outcome' if out is None else
                                                   'delivered' if out['delivered'] else 'omission'),
                              'retrospective_events': [dict(e, time=e['time'] - anchor) for e in s['events']
                                                       if anchor + lo <= e['time'] < anchor + hi],
                              'features': f, 'signal': signal, 'target': target,
                              'secondary': secondary, 'view': view, 'endpoint': endpoint_name,
                              'required_windows': required_windows, 'native_source_indices': native['indices']})
                support.update(eligible=True, status='eligible', required_windows=required_windows)
            elapsed += s['duration']; prior_rewards += len(delivered); prior_cues += len(cues)
    return {'schema': 'prepared_neural_bank_v1', 'task': task, 'view': view, 'endpoint': endpoint_name,
            'synthetic': corpus['synthetic'], 'source_digest': digest(corpus), 'cases': cases,
            'exclusions': exclusions, 'eligibility': eligibility,
            'denominators': {'expected_cue_records': len(eligibility), 'eligible_endpoint_records': len(cases),
                             'source_unscorable_records': sum(r['status'] == 'source_unscorable' for r in eligibility),
                             'endpoint_population_inapplicable_records': sum(r['status'] == 'inapplicable_endpoint_population' for r in eligibility)},
            'support': report,
            'continuous_training_source': [
                {'animal': a['id'], 'session': s['id'], 'times': list(s['times']), 'values': list(s['fluorescence']),
                 'events': copy.deepcopy(s['events']), 'max_gap': s['max_gap']}
                for a in corpus['animals'] for s in a['sessions']],
            'scientific_qualification': False}


def split(bank, held, kind='animal'):
    require(kind in ('animal', 'condition'), 'split_kind')
    train = [copy.deepcopy(x) for x in bank['cases'] if x[kind] != held]
    query = [copy.deepcopy(x) for x in bank['cases'] if x[kind] == held]
    require(train and query, 'unsupported_fold')
    if bank['task'] == 'NEURAL-046' and kind == 'animal':
        require({r['condition'] for r in query} <= {r['condition'] for r in train},
                'within_condition_animal_replication_required')
    require(not ({a for x in train for a in x['aliases']} &
                 {a for x in query for a in x['aliases']}), 'split_alias_leak')
    return train, query


def destroy_session_timing(corpus, training_animals, seed=0):
    """Circular index shift within each contiguous, uniform native session segment.

    Nonuniform segments are deliberately unsupported, rather than resampled.
    Only explicitly named training animals can change; query records stay exact.
    """
    transformed = copy.deepcopy(corpus)
    rng = random.Random(seed)
    records = []
    for animal in transformed['animals']:
        if animal['id'] not in training_animals:
            continue
        for session in animal['sessions']:
            times = session['times']
            boundaries = [0] + [i + 1 for i, (a, b) in enumerate(zip(times, times[1:]))
                                  if b - a > session['max_gap']] + [len(times)]
            for left, right in zip(boundaries, boundaries[1:]):
                require(right - left >= 3, 'timing_control_insufficient_contiguous_support')
                dt = times[left + 1] - times[left]
                require(all(abs((times[i + 1] - times[i]) - dt) <=
                            64 * math.ulp(max(abs(times[i + 1]), 1.0))
                            for i in range(left, right - 1)),
                        'nonuniform_timing_control_requires_registered_physical_shift')
                offset = rng.randrange(1, right - left)
                old = session['fluorescence'][left:right]
                session['fluorescence'][left:right] = old[offset:] + old[:offset]
                records.append({'animal': animal['id'], 'session': session['id'],
                                'left': left, 'right': right, 'offset_samples': offset,
                                'offset_seconds': offset * dt})
    return transformed, {'kind': 'training_contiguous_session_timing_destruction',
                         'original_digest': digest(corpus), 'transformed_digest': digest(transformed),
                         'training_animals': sorted(training_animals), 'segments': records,
                         'seed': seed, 'exchangeability_claim': False}


def project(bank, train, query, cell_id, seed=0, timing_training=None, timing_receipt=None,
            timing_continuous=None, source_prior=None):
    c = assert_numerical(cell_id, bank['task'])
    assert_endpoint_applicable(cell_id, bank['task'], bank['endpoint'])
    require('eligibility' in bank and 'denominators' in bank, 'endpoint_eligibility_ledger_required')
    rights = c['input_control_contract']
    require(len({r['domain'] for r in train + query}) == 1, 'raw_units_domain_pooling_forbidden')
    condition_transfer = not ({r['condition'] for r in train} & {r['condition'] for r in query})
    if bank['task'] == 'NEURAL-046' and condition_transfer:
        require(all(any(k.startswith('protocol_') for k in r['features']) for r in train + query),
                'condition_transfer_requires_verified_physical_descriptors')
    rng = random.Random(seed)
    train = copy.deepcopy(train)
    state = rights['training_neural_state']
    if state == 'pairing_destroyed':
        groups = defaultdict(list)
        for row in train:
            groups[(row['animal'], row['session'], digest(row['signal']['times']))].append(row)
        for group in groups.values():
            require(len(group) >= 2, 'pairing_control_insufficient_matched_trials')
            values = [(r['signal']['values'], r['target'], r['secondary']) for r in group]
            offset = rng.randrange(1, len(values))
            values = values[offset:] + values[:offset]
            for row, (value, target, secondary) in zip(group, values):
                row['signal']['values'], row['target'], row['secondary'] = value, target, secondary
                if bank['task'] == 'NEURAL-046':
                    chosen = 'cue' if bank.get('endpoint', 'cue') == 'aversive' else bank.get('endpoint', 'cue')
                    windows = secondary[chosen]['source_windows']
                    # Recompute from donor native samples; do not reuse the recipient scalar.
                    post, pre = [observed_window(windows[k]['times'], windows[k]['values'],
                        windows[k]['times'][0], math.nextafter(windows[k]['times'][-1], math.inf),
                        row['signal']['max_gap']) for k in ('post', 'pre')]
                    row['target'] = post['integral'] - pre['integral']
    elif state == 'timing_destroyed':
        require(timing_training is not None and timing_receipt is not None,
                'continuous_session_destruction_receipt_required')
        require(timing_receipt['original_digest'] == bank['source_digest'], 'timing_original')
        require({r['id'] for r in timing_training} == {r['id'] for r in train}, 'timing_case_join')
        require(set(timing_receipt['training_animals']) == {r['animal'] for r in train},
                'timing_held_animal_leak')
        train = copy.deepcopy(timing_training)
    continuous = []
    if state in ('original', 'timing_destroyed') and rights['elapsed_conditioning_E_authorized'] and rights['delivered_reward_N_authorized']:
        source = bank['continuous_training_source']
        if state == 'timing_destroyed':
            require(timing_continuous is not None, 'transformed_continuous_training_required')
            source = timing_continuous
        animals = {r['animal'] for r in train}
        continuous = [copy.deepcopy(s) for s in source if s['animal'] in animals]
        require({s['animal'] for s in continuous} == animals, 'continuous_training_coverage')
        if rights['nuisance_Z'] == 'behavior_removed':
            for session in continuous:
                session['events'] = [e for e in session['events'] if e['kind'] not in ('lick_on', 'lick_off')]
    if c['control'] == 'source_prior':
        require(source_prior is not None and source_prior['schema'] == 'reviewed_source_prior_v1' and
                source_prior['contains_protected_target_information'] is False and
                bool(source_prior['review_receipt']), 'reviewed_source_prior_required')
    else:
        require(source_prior is None, 'source_prior_in_wrong_control')
    aliases = {a: 'animal_%04d' % i for i, a in enumerate(sorted({r['animal'] for r in train + query}))}
    opaque_cases = {r['id']: 'case_%06d' % i for i, r in enumerate(train + query)}
    opaque_sessions = {v: 'session_%04d' % i for i, v in enumerate(sorted({r['session'] for r in train + query}))}

    def public(row, training):
        f = dict(row['features'])
        if bank['task'] == 'NEURAL-046' and condition_transfer:
            f.pop('condition', None)
        if not rights['elapsed_conditioning_E_authorized']: f.pop('E', None)
        if not rights['delivered_reward_N_authorized']: f.pop('N', None)
        if rights['nuisance_Z'] != 'past_plus_concurrent' or bank['view'] == 'cue_time':
            f.pop('concurrent_lick_rate', None)
        if rights['nuisance_Z'] in ('behavior_removed', 'metadata_only'):
            f.pop('baseline_lick_rate', None)
        if rights['nuisance_Z'] == 'metadata_only':
            f.pop('preceding_interval', None)
        ident = aliases[row['animal']] if c['control'] == 'opaque_ID' else row['animal']
        result = {'id': opaque_cases[row['id']] if c['control'] == 'opaque_ID' else row['id'],
                  'animal': ident, 'condition': row['condition'],
                  'session': opaque_sessions[row['session']] if c['control'] == 'opaque_ID' else row['session'],
                  'features': f, 'times': row['signal']['times']}
        if bank['task'] == 'NEURAL-045' and bank['view'] == 'retrospective' and rights['elapsed_conditioning_E_authorized'] and rights['delivered_reward_N_authorized']:
            result['retrospective_events'] = [
                {k: v for k, v in e.items() if k not in ('id', 'trial_id')}
                for e in row['retrospective_events'] if
                e['kind'] not in ('lick_on', 'lick_off') or rights['nuisance_Z'] == 'past_plus_concurrent']
        if training and state != 'none':
            result['signal'] = row['signal']
            result['target'] = row['target']
        return result

    if c['control'] == 'opaque_ID':
        for i, session in enumerate(continuous):
            session['animal'] = aliases[session['animal']]
            session['session'] = opaque_sessions[session['session']]
            trials = {v: 'trial_%06d' % j for j, v in enumerate(dict.fromkeys(e['trial_id'] for e in session['events']))}
            for j, event in enumerate(session['events']):
                event['id'] = 'event_%06d' % j
                event['trial_id'] = trials[event['trial_id']]
    by_condition = {condition: {'expected': 0, 'eligible': 0, 'source_unscorable': 0,
                               'endpoint_population_inapplicable': 0, 'reasons': {}}
                    for condition in bank['support']['conditions']}
    for record in bank['eligibility']:
        counts = by_condition[record['condition']]; counts['expected'] += 1
        if record['eligible']: counts['eligible'] += 1
        elif record['status'] == 'source_unscorable': counts['source_unscorable'] += 1
        else: counts['endpoint_population_inapplicable'] += 1
        if 'reason' in record:
            counts['reasons'][record['reason']] = counts['reasons'].get(record['reason'], 0) + 1
    endpoint_support = {'schema': 'endpoint_eligibility_summary_v1', 'endpoint': bank['endpoint'],
        'source_eligibility_digest': digest(bank['eligibility']), 'denominators': dict(bank['denominators']),
        'conditions': by_condition, 'query_eligible_cases': len(query), 'training_eligible_cases': len(train),
        'qualification': 'eligibility_metadata_only_not_scientific_qualification'}
    return {'schema': 'control_projected_inputs_v1', 'task': bank['task'], 'cell_id': cell_id,
            'synthetic': bank['synthetic'], 'view': bank['view'],
            'endpoint': bank.get('endpoint', 'cue'),
            'source_digest': bank['source_digest'], 'rights_digest': digest(rights),
            'endpoint_support': endpoint_support,
            'split_estimand': 'condition_transfer' if condition_transfer else 'within_condition_animal',
            'knowledge_access': 'fixed_source_prior_packet_only' if c['control'] == 'source_prior'
                                else 'common_task_specification_only',
            'training': [public(x, True) for x in train],
            'query': [public(x, False) for x in query],
            'continuous_training': continuous, 'source_prior': source_prior,
            'continuous_projection': 'permitted_full_training_sessions' if continuous else
                                     'controlled_native_windows_only_or_no_neural_training',
            'forecast_interface': 'offline_recording_support_conditioned_array'
                                  if bank['view'] == 'cue_time' else 'retrospective',
            'projection_limits': ['relative native times retained; schedule/row-count proxies disclosed',
                                  'actual native adapter and causal signal pipeline remain unqualified']}
