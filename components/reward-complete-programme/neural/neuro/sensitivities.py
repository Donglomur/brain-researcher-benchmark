"""Explicit alternative estimands; unavailable acquisition stays unavailable."""
import copy
from .base import require, finite, digest, observed_window


def endpoint_sensitivity(bank, quantity):
    require(bank['task'] == 'NEURAL-046' and quantity in (
        'mean_difference', 'baseline_span_corrected_auc'), 'endpoint_sensitivity')
    out = copy.deepcopy(bank); retained = []
    for case in out['cases']:
        selected = 'cue' if bank['endpoint'] == 'aversive' else bank['endpoint']
        endpoint = case['secondary'][selected]
        if 'source_windows' not in endpoint:
            out['exclusions'].append({'id': case['id'], 'reason': 'sensitivity_native_windows_unavailable'}); continue
        post, pre = endpoint['source_windows']['post'], endpoint['source_windows']['pre']
        case['target'] = (post['mean'] - pre['mean'] if quantity == 'mean_difference' else
                          post['integral'] - pre['mean'] * post['covered_seconds'])
        case['endpoint'] = bank['endpoint'] + '/' + quantity
        retained.append(case)
    out['cases'] = retained; out['endpoint'] += '/' + quantity
    out['sensitivity'] = {'kind': quantity, 'original_bank_digest': digest(bank),
                          'raw_primary_replaced': False, 'separate_result_required': True}
    return out


def feature_sensitivity(corpus, bank, axis, definition):
    require(digest(corpus) == bank['source_digest'], 'sensitivity_source_binding')
    require((axis == 'N' and definition in ('cue_count', 'all_reward_count', 'verified_consumption_count')) or
            (axis == 'E' and definition in ('chamber_exposure', 'calendar_elapsed')), 'feature_definition')
    out = copy.deepcopy(bank); lookup = {r['id']: r for r in out['cases']}; missing = []
    for animal in corpus['animals']:
        previous_count = 0; chamber_before = 0.; known = True
        origin = animal['sessions'][0].get('start_epoch_seconds')
        for session in animal['sessions']:
            events = session['events']; outcomes = {e['trial_id']: e for e in events if e['kind'] in ('outcome', 'shock_on')}
            if axis == 'N':
                known = known and session['history']['delivered_count_known']
                if definition == 'cue_count': occurrences = [e['time'] for e in events if e['kind'] == 'cue']
                elif definition == 'all_reward_count': occurrences = [e['time'] for e in events if e['kind'] in ('outcome', 'shock_on', 'milk') and e['delivered']]
                else:
                    known = known and session['history']['lick_history_known']
                    occurrences = []
                    for outcome in outcomes.values():
                        if not outcome['delivered']: continue
                        ongoing = False
                        for e in events:
                            if e['time'] > outcome['time']: break
                            if e['kind'] == 'lick_on': ongoing = True
                            elif e['kind'] == 'lick_off': ongoing = False
                        after = next((e['time'] for e in events if e['kind'] == 'lick_on' and
                                      e['trial_id'] == outcome['trial_id'] and e['time'] > outcome['time']), None)
                        if ongoing: occurrences.append(outcome['time'])
                        elif after is None: known = False
                        else: occurrences.append(after)
            for cue in (e for e in events if e['kind'] == 'cue'):
                key = animal['id'] + '/' + session['id'] + '/' + cue['id']
                if key not in lookup: continue
                case = lookup[key]
                anchor = outcomes[cue['trial_id']]['time'] if bank['endpoint'] in ('reward', 'omission', 'delivery') else cue['time']
                value = None
                if axis == 'N' and known: value = previous_count + sum(t < anchor for t in occurrences)
                if axis == 'E' and definition == 'calendar_elapsed' and origin is not None and session.get('start_epoch_seconds') is not None:
                    value = finite(session['start_epoch_seconds']) + anchor - finite(origin)
                if axis == 'E' and definition == 'chamber_exposure' and chamber_before is not None and session.get('recording_chamber_offset_seconds') is not None:
                    value = chamber_before + finite(session['recording_chamber_offset_seconds']) + anchor
                if value is not None: require(finite(value) >= 0, 'negative_sensitivity_clock_or_count')
                else: missing.append({'case': key, 'reason': 'source_history_or_clock_unverified'})
                case['features'][axis] = value
            if axis == 'N': previous_count += len(occurrences)
            if session.get('chamber_duration_seconds') is None: chamber_before = None
            elif chamber_before is not None: chamber_before += finite(session['chamber_duration_seconds'])
    out['sensitivity'] = {'axis': axis, 'definition': definition, 'missing': missing,
                          'original_bank_digest': digest(bank), 'primary_not_replaced': True}
    return out


def delivery_aligned_reward(corpus, bank):
    require(bank['task'] == 'NEURAL-046' and bank['endpoint'] == 'reward' and
            digest(corpus) == bank['source_digest'], 'delivery_sensitivity_source')
    from .prepare import prepare
    # Reconstruct eligibility from the original neutral source, recovering missing-lick trials.
    out = prepare(corpus, 'NEURAL-046', bank['view'], 'delivery')
    out['sensitivity'] = {'original_bank_digest': digest(bank), 'consumption_requirement_replaced': True,
                          'recovered_missing_consumption_cases': len(out['cases']) - len(bank['cases']),
                          'separate_result_required': True}
    return out
