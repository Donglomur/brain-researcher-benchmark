"""N059 full-roster structured preparation; no acquisition or qualification.

See preparation-evidence/SCHEMA_V1.md for the frozen operand/limit contract.
Adapted source semantics, not pilot-specific shapes or authentic operands.
"""
import bisect
import copy
import hashlib
import json
import math
import re

REVISION = '6fbd666fe8170a2165f5198c1f490911424a654d'
PIPELINE_SHA256 = '931002bcf87e2ff88a8eb2e270d963b2479971a0a7dabc3659c5098a2bec0c29'
PROFILE = 'reviewed_6fbd_structured_v1'
S_NAMES = ('S:-1', 'S:-0.25', 'S:-0.125', 'S:-0.0625', 'S:0',
           'S:0.0625', 'S:0.125', 'S:0.25', 'S:1')
H_NAMES = ('H:unavailable', 'H:right:0', 'H:right:1', 'H:left:0',
           'H:left:1', 'H:no_response:0', 'H:no_response:1')
B_NAMES = ('B:0.2', 'B:0.5', 'B:0.8')
SIGNED = (-1., -.25, -.125, -.0625, 0., .0625, .125, .25, 1.)
MAGNITUDES = (0., .0625, .125, .25, 1.)
PROBABILITIES = (.2, .5, .8)
BLOCK_CODES = (0, -1, 1)
CONDITIONS = ('SH', 'SHN', 'SBH', 'SBHN')
SPLITS = ('train', 'val', 'test')
ROSTER_DESCRIPTOR_KEYS = ('bytes', 'eid', 'etag', 'inherited_sha256', 'key', 'lab', 'subject')
ROSTER_DESCRIPTOR_SHA256 = '1ca385428a08c993dc68ba21992601f70b4fad7917bcbbc74533b710536b4ffc'
TASKS = ('stimulus_side', 'stimulus_contrast', 'choice',
         'movement_window', 'licking_window', 'reward', 'block_prior')
LIMIT_KEYS = {'max_input_bytes', 'max_output_bytes', 'max_trials',
              'max_units', 'max_spikes', 'max_work'}
RAW_KEYS = {'session_id', 'source_identity', 'source_profile', 'unit_ids',
            'original_trials', 'spike_times', 'spike_units', 'spike_domain',
            'task_intervals', 'stored_splits'}
TRIAL_KEYS = {'raw_index', 'stored_ordinal', 'intervals_0', 'intervals_1',
              'stimOn_times', 'firstMovement_times', 'feedback_times',
              'choice', 'feedbackType', 'probabilityLeft',
              'contrastLeft', 'contrastRight'}
REQUIRED = ('stimOn_times', 'choice', 'feedback_times', 'probabilityLeft',
            'firstMovement_times', 'feedbackType')
# Frozen eid/subject/lab tuples from ROSTER.json; ordinary metadata only.
ROSTER = (('0802ced5-33a3-405e-8336-b65ebc5cb07c', 'ZFM-02373', 'mainenlab'), ('09394481-8dd2-4d5c-9327-f2753ede92d7', 'ibl_witten_26', 'wittenlab'), ('0cbeae00-e229-4b7d-bdcc-1b0569d7e0c3', 'CSHL055', 'churchlandlab'), ('12dc8b34-b18e-4cdd-90a9-da134a9be79c', 'CSHL053', 'churchlandlab'), ('16693458-0801-4d35-a3f1-9115c7e5acfd', 'KS014', 'cortexlab'), ('19e66dc9-bf9f-430b-9d6a-acfa85de6fb7', 'UCLA006', 'churchlandlab_ucla'), ('28338153-4113-485b-835b-91cb96d984f2', 'NR_0028', 'steinmetzlab'), ('29a6def1-fc5c-4eea-ac48-47e9b053dcb5', 'NR_0028', 'steinmetzlab'), ('2d9bfc10-59fb-424a-b699-7c42f86c7871', 'NR_0024', 'steinmetzlab'), ('3bcb81b4-d9ca-4fc9-a1cd-353a966239ca', 'NR_0024', 'steinmetzlab'), ('5569f363-0934-464e-9a5b-77c8e67791a1', 'NYU-30', 'angelakilab'), ('56956777-dca5-468c-87cb-78150432cc57', 'NYU-11', 'angelakilab'), ('5c0c560e-9e1f-45e9-b66e-e4ee7855be84', 'NR_0028', 'steinmetzlab'), ('5ec72172-3901-4771-8777-6e9490ca51fc', 'NYU-30', 'angelakilab'), ('6713a4a7-faed-4df2-acab-ee4e63326f8d', 'NYU-11', 'angelakilab'), ('6f6d2c8e-28be-49f4-ae4d-06be2d3148c1', 'ZFM-02370', 'mainenlab'), ('77e6dc6a-66ed-433c-b1a2-778c914f523c', 'NYU-30', 'angelakilab'), ('7cc74598-9c1b-436b-84fa-0bf89f31adf6', 'NR_0024', 'steinmetzlab'), ('810b1e07-009e-4ebe-930a-915e4cd8ece4', 'CSHL053', 'churchlandlab'), ('8c025071-c4f3-426c-9aed-f149e8f75b7b', 'NYU-65', 'angelakilab'), ('934dd7a4-fbdc-459c-8830-04fe9033bc28', 'ZM_3003', 'mainenlab'), ('b9c205c3-feac-485b-a89d-afc96d9cb280', 'KS014', 'cortexlab'), ('c958919c-2e75-435d-845d-5b62190b520e', 'NR_0028', 'steinmetzlab'), ('d0c91c3c-8cbb-4929-8657-31f18bffc294', 'ZFM-02370', 'mainenlab'), ('dc21e80d-97d7-44ca-a729-a8e3f9b14305', 'ibl_witten_26', 'wittenlab'), ('e1931de1-cf7b-49af-af33-2ade15e8abe7', 'KS014', 'cortexlab'), ('f4eb56a4-8bf8-4bbc-a8f3-6e6535134bad', 'NR_0024', 'steinmetzlab'), ('f56194bc-8215-4ae8-bc6a-89781ad8e050', 'NR_0028', 'steinmetzlab'), ('fe1fd79f-b051-411f-a0a9-2530a02cc78d', 'ZM_3003', 'mainenlab'))


class PreparationRefusal(ValueError):
    """Malformed operands/resource ceiling; never a scientific qualification."""
    def __init__(self, code, details=None):
        self.code = code
        self.details = details
        super().__init__(code)


def _need(condition, code, details=None):
    if not condition:
        raise PreparationRefusal(code, details)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _string(value):
    return type(value) is str and bool(value)


def _keys(value, keys, code):
    _need(type(value) is dict and set(value) == set(keys), code)


def _json_bytes(value, maximum, code):
    """Measure bounded canonical wire bytes without a whole serialized copy."""
    total = 0
    try:
        encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False)
        for chunk in encoder.iterencode(value):
            total += len(chunk.encode('utf-8'))
            _need(total <= maximum, code, {'observed_at_least': total, 'limit': maximum})
    except (TypeError, OverflowError, RecursionError, ValueError) as error:
        if isinstance(error, PreparationRefusal):
            raise
        raise PreparationRefusal('non_json_or_nonfinite_operand') from error
    return total


def _limits(limits):
    _keys(limits, LIMIT_KEYS, 'limits_schema')
    _need(all(type(v) is int and v > 0 for v in limits.values()), 'limits_positive_exact_int')


def _member(member):
    _need(type(member) is dict and all(_string(member.get(k)) for k in ('eid', 'subject', 'lab')),
          'member_identity')
    return member['eid'], member['subject'], member['lab']


def _roster_members(members):
    """Bind the full immutable asset/version metadata, not only its ID census."""
    _need(type(members) is list and tuple(_member(m) for m in members) == ROSTER,
          'exact_full_roster_required')
    _need(all(set(ROSTER_DESCRIPTOR_KEYS) <= set(m) for m in members),
          'full_roster_asset_descriptor_required')
    projected = [{key: member[key] for key in ROSTER_DESCRIPTOR_KEYS} for member in members]
    encoded = json.dumps(projected, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    _need(hashlib.sha256(encoded).hexdigest() == ROSTER_DESCRIPTOR_SHA256,
          'full_roster_asset_descriptor_mismatch')


def _pairs(value, code, *, nonempty=True):
    _need(type(value) is list and (value or not nonempty), code)
    previous_end = None
    for pair in value:
        _need(type(pair) is list and len(pair) == 2 and all(_finite(v) for v in pair)
              and pair[0] < pair[1], code)
        _need(previous_end is None or pair[0] >= previous_end, code + '_overlap_or_order')
        previous_end = pair[1]


def _one(index, length):
    return [1. if j == index else 0. for j in range(length)]


def _hold(holds, code, **details):
    # Internal callers supply fixed codes and at most two scalar detail fields.
    # Canonical bounded keys deduplicate without scanning accumulated evidence.
    row = {'code': code, **details}
    key = tuple(sorted(row.items()))
    holds.setdefault(key, row)


def _shape(raw, member, limits):
    _keys(raw, RAW_KEYS, 'raw_schema')
    _need(raw['session_id'] == _member(member)[0], 'session_identity')
    _need(_string(raw['source_profile']), 'source_profile_type')
    _keys(raw['source_identity'], {'repository', 'revision', 'pipeline_sha256', 'source_sha256'},
          'source_identity_schema')
    _need(all(_string(raw['source_identity'][k]) for k in ('repository', 'revision', 'pipeline_sha256')),
          'source_identity_type')
    source_sha = raw['source_identity']['source_sha256']
    _need(source_sha is None or (type(source_sha) is str and
          re.fullmatch('[0-9a-f]{64}', source_sha) is not None), 'source_binding_pin')
    expected_sha = member.get('inherited_sha256')
    _need(expected_sha is None or (type(expected_sha) is str and
          re.fullmatch('[0-9a-f]{64}', expected_sha) is not None), 'member_binding_pin')
    trials, units, times, labels = (raw[k] for k in
                                   ('original_trials', 'unit_ids', 'spike_times', 'spike_units'))
    _need(type(trials) is list and 0 < len(trials) <= limits['max_trials'], 'trial_shape')
    _need(type(units) is list and 0 < len(units) <= limits['max_units']
          and all(_string(u) for u in units) and len(set(units)) == len(units), 'unit_shape')
    _need(type(times) is list and type(labels) is list and len(times) == len(labels)
          and len(times) <= limits['max_spikes'], 'spike_shape')
    _pairs(raw['spike_domain'], 'spike_domain')
    u_set = set(units)
    _need(all(_finite(t) for t in times) and all(a <= b for a, b in zip(times, times[1:])),
          'spike_time_order')
    _need(all(type(u) is str and u in u_set for u in labels), 'spike_unit_identity')
    _keys(raw['task_intervals'], set(TASKS) | {'envelope'}, 'task_schema')
    for name, rows in raw['task_intervals'].items():
        _need(type(rows) is list and len(rows) <= len(trials), 'task_shape', name)
        for row in rows:
            _keys(row, {'trial_index', 'start', 'end'} | (set() if name == 'envelope' else {'value'}),
                  'task_row_schema')
            _need(type(row['trial_index']) is int and 0 <= row['trial_index'] < len(trials)
                  and _finite(row['start']) and _finite(row['end']) and row['start'] < row['end'],
                  'task_row_values')
            if name != 'envelope':
                _need(row['value'] is None if name in ('movement_window', 'licking_window')
                      else type(row['value']) is int, 'task_discrete_type')
    _keys(raw['stored_splits'], SPLITS, 'stored_split_schema')
    for split in SPLITS:
        _pairs(raw['stored_splits'][split], 'stored_' + split)
        _need(len(raw['stored_splits'][split]) == 1, 'reviewed_source_single_split_interval')
    t, p, u, d = len(trials), len(times), len(units), len(raw['spike_domain'])
    work = 100*t + 10*p + 4*t*u + 4*t*d + 8*t*t.bit_length() + 4*p*d
    _need(work <= limits['max_work'], 'work_limit', {'required': work, 'limit': limits['max_work']})
    return work


def _normalized_trials(raw_trials, holds):
    rows = []
    for row in raw_trials:
        _keys(row, TRIAL_KEYS, 'trial_row_schema')
        _need(type(row['raw_index']) is int, 'raw_index_type')
        _need(row['stored_ordinal'] is None or type(row['stored_ordinal']) is int,
              'stored_ordinal_type')
        _need(_finite(row['intervals_0']) and _finite(row['intervals_1'])
              and row['intervals_0'] < row['intervals_1'], 'original_interval')
        for key in TRIAL_KEYS - {'raw_index', 'stored_ordinal', 'intervals_0', 'intervals_1'}:
            _need(row[key] is None or _finite(row[key]), 'raw_trial_scalar', key)
        for key in ('choice', 'feedbackType'):
            _need(row[key] is None or type(row[key]) is int, 'raw_behavior_integer', key)
        rows.append(copy.deepcopy(row))
    t = len(rows)
    _need(sorted(r['raw_index'] for r in rows) == list(range(t)), 'raw_index_bijection')
    witness = [r['stored_ordinal'] for r in rows]
    _need(all(v is None for v in witness) or
          (all(type(v) is int for v in witness) and sorted(witness) == list(range(t))),
          'stored_ordinal_bijection')
    if all(v is None for v in witness):
        if len({r['intervals_0'] for r in rows}) != t:
            _hold(holds, 'G02_sort_tie_without_authenticated_ordinal')
        rows.sort(key=lambda r: r['intervals_0'])
    else:
        rows.sort(key=lambda r: r['stored_ordinal'])
        if any(a['intervals_0'] > b['intervals_0'] for a, b in zip(rows, rows[1:])):
            _hold(holds, 'G02_stored_ordinal_not_source_start_order')
    for i, (a, b) in enumerate(zip(rows, rows[1:])):
        if a['intervals_1'] > b['intervals_0']:
            _hold(holds, 'G02_G04_original_intervals_overlap', left=i, right=i+1)
    normalized = []
    for i, row in enumerate(rows):
        reasons = ['missing_' + k for k in REQUIRED if row[k] is None]
        stim, m, feedback = (row[k] for k in ('stimOn_times', 'firstMovement_times', 'feedback_times'))
        if stim is not None and m is not None:
            if m-stim < 0.: reasons.append('reaction_time_below_zero')
            if m-stim > 10.: reasons.append('reaction_time_above_ten')
        if row['choice'] == 0: reasons.append('raw_no_response')
        choice = {-1: 0, 1: 1, 0: 2}.get(row['choice'])
        reward = {-1: 0, 1: 1}.get(row['feedbackType'])
        if row['choice'] is not None and choice is None:
            _hold(holds, 'G02_unknown_choice_encoding', ordinal=i)
        if row['feedbackType'] is not None and reward is None:
            _hold(holds, 'G02_unknown_feedback_encoding', ordinal=i)
        left, right = row['contrastLeft'], row['contrastRight']
        side, mag, s_index = None, None, None
        if (left is None) == (right is None):
            _hold(holds, 'G02_ambiguous_stimulus_side', ordinal=i)
        else:
            side = 0 if left is None else 1
            presented = right if left is None else left
            if presented not in MAGNITUDES:
                _hold(holds, 'G02_unsupported_contrast', ordinal=i)
            else:
                mag = MAGNITUDES.index(presented)
                signed = 0. if presented == 0. else presented if side == 1 else -presented
                s_index = SIGNED.index(signed)
        probability = row['probabilityLeft']
        b_index = PROBABILITIES.index(probability) if probability in PROBABILITIES else None
        if probability is not None and b_index is None:
            _hold(holds, 'G02_unknown_probability_left', ordinal=i)
        if reward is None or side is None or int(choice != 2 and choice == side) != reward:
            _hold(holds, 'G02_choice_stimulus_reward_conflict', ordinal=i)
        normalized.append({'ordinal': i, 'raw_index': row['raw_index'],
            'source_valid': not reasons, 'source_invalid_reasons': reasons,
            'raw': row, 'choice': choice, 'reward': reward,
            'stimulus_side': side, 'stimulus_contrast': mag,
            'S_index': s_index, 'B_index': b_index,
            'block_prior': BLOCK_CODES[b_index] if b_index is not None else None,
            'stim_on_time': stim, 'movement_onset_time': m, 'feedback_time': feedback})
    return normalized


def _derive_tasks(rows, holds):
    tasks = {name: [] for name in TASKS}
    tasks['envelope'] = []
    for row in rows:
        if not row['source_valid']:
            continue
        i, s, m, f = (row[k] for k in ('ordinal', 'stim_on_time', 'movement_onset_time', 'feedback_time'))
        if any(row[k] is None for k in ('choice', 'reward', 'stimulus_side', 'stimulus_contrast', 'block_prior')):
            _hold(holds, 'G02_unmapped_source_valid_task', ordinal=i)
            continue
        values = {'stimulus_side': (s-.9, s+.1, row['stimulus_side']),
                  'stimulus_contrast': (s-.9, s+.1, row['stimulus_contrast']),
                  'choice': (m-1., m, row['choice']),
                  'movement_window': (m, m+1., None),
                  'licking_window': (f, f+1., None),
                  'reward': (f, f+1., row['reward'])}
        if row['block_prior'] != -1:
            values['block_prior'] = (s-1., s, row['block_prior'])
        for name, (a, b, value) in values.items():
            tasks[name].append({'trial_index': i, 'start': a, 'end': b, 'value': value})
        tasks['envelope'].append({'trial_index': i,
            'start': min(v[0] for v in values.values()), 'end': max(v[1] for v in values.values())})
    for name in ('envelope', 'choice'):
        for a, b in zip(tasks[name], tasks[name][1:]):
            if a['end'] > b['start']:
                _hold(holds, 'G02_G04_' + name + '_overlap', left=a['trial_index'], right=b['trial_index'])
    return tasks


def _derive_splits(envelope, domain, holds):
    intersected = [[max(row['start'], a), min(row['end'], b)]
                   for row in envelope for a, b in domain
                   if max(row['start'], a) < min(row['end'], b)]
    if not intersected:
        _hold(holds, 'G04_empty_task_spike_intersection')
        return None, None
    # Match the reviewed source's float64 sum/cumsum reduction, not a Python
    # summation approximation. This is arithmetic only, never model fitting.
    try:
        import numpy as np
    except ImportError as error:
        raise PreparationRefusal('numpy_source_reduction_unavailable') from error
    lengths = np.asarray([b-a for a, b in intersected], dtype=np.float64)
    total = float(np.sum(lengths))
    cumulative = np.cumsum(lengths).tolist()
    reduction_profile = {'library': 'numpy', 'observed_version': str(np.__version__),
                         'dtype': 'float64', 'sum': 'numpy.sum', 'cumulative': 'numpy.cumsum',
                         'package_authenticated': False, 'authentic_source_parity': False}
    if not math.isfinite(total) or total <= 0 or not all(math.isfinite(x) for x in cumulative):
        _hold(holds, 'G04_nonfinite_cumulative_task_duration')
        return None, reduction_profile
    def cut(offset):
        index = min(bisect.bisect_left(cumulative, offset), len(cumulative)-1)
        previous = cumulative[index-1] if index else 0.
        return intersected[index][0 if offset-previous <= cumulative[index]-offset else 1]
    def gap(boundary):
        end = boundary + 20.
        for a, b in intersected:
            if a < end < b:
                return b
        return end + 1e-12
    train_end = cut(total * .4)
    val_end = cut(total * (.4 + .2))
    result = {'train': [[domain[0][0], train_end]],
              'val': [[gap(train_end), val_end]],
              'test': [[gap(val_end), domain[-1][1]]]}
    for name in SPLITS:
        a, b = result[name][0]
        if not _finite(a) or not _finite(b) or a >= b:
            _hold(holds, 'G04_empty_or_nonfinite_derived_split', split=name)
    if result['train'][0][1] > result['val'][0][0] or result['val'][0][1] > result['test'][0][0]:
        _hold(holds, 'G04_derived_split_overlap')
    return result, reduction_profile


def _history(rows, index):
    if index == 0:
        return _one(0, 7), False, 'no_preceding_original_trial'
    previous, current = rows[index-1], rows[index]
    available = (_finite(previous['feedback_time']) and _finite(current['movement_onset_time'])
        and previous['feedback_time'] < current['movement_onset_time']
        and type(previous['choice']) is int and previous['choice'] in (0, 1, 2)
        and type(previous['reward']) is int and previous['reward'] in (0, 1))
    index_h = 1 + 2*previous['choice'] + previous['reward'] if available else 0
    return _one(index_h, 7), available, ('feedback_strictly_before_cutoff' if available
                                      else 'prior_feedback_or_behavior_unavailable')


def prepare_session(raw, member, *, limits):
    """Derive private original-slot census and all four matched information views."""
    _limits(limits)
    _json_bytes({'raw': raw, 'member': member}, limits['max_input_bytes'], 'input_byte_limit')
    work = _shape(raw, member, limits)
    holds = {}
    identity = raw['source_identity']
    if member.get('inherited_sha256') is not None and identity['source_sha256'] != member['inherited_sha256']:
        _hold(holds, 'G02_member_source_sha_mismatch')
    if (raw['source_profile'] != PROFILE or identity['repository'] != 'brainbench-org/ibl-bwb'
        or identity['revision'] != REVISION or identity['pipeline_sha256'] != PIPELINE_SHA256):
        _hold(holds, 'G02_source_profile_or_generation_mismatch')
    rows = _normalized_trials(raw['original_trials'], holds)
    tasks = _derive_tasks(rows, holds)
    for name in (*TASKS, 'envelope'):
        if tasks[name] != raw['task_intervals'][name]:
            _hold(holds, 'G02_source_task_join_mismatch', task=name)
    # Geometry/source adjudication precedes reductions or counting.
    splits, reduction_profile = (_derive_splits(tasks['envelope'], raw['spike_domain'], holds)
                                 if not holds else (None, None))
    if splits is not None and splits != raw['stored_splits']:
        _hold(holds, 'G02_G04_stored_split_recipe_mismatch')
    if any(not any(a <= t <= b for a, b in raw['spike_domain']) for t in raw['spike_times']):
        _hold(holds, 'G04_spike_outside_declared_domain')
    unit_ids = list(raw['unit_ids'])
    slots, cases = [], []
    counts = {'original_trials': len(rows), 'source_valid_trials': sum(r['source_valid'] for r in rows),
              'eligible_by_split': dict.fromkeys(SPLITS, 0), 'excluded_by_reason': {},
              'unit_count': len(unit_ids), 'spikes': len(raw['spike_times']), 'matrix': [], 'case_ids': []}
    for row in rows:
        i, m = row['ordinal'], row['movement_onset_time']
        valid = row['source_valid']
        slot = {'ordinal': i, 'raw_index': row['raw_index'], 'source_valid': valid,
                'source_invalid_reasons': list(row['source_invalid_reasons']),
                'normalized': copy.deepcopy(row), 'case_id': None, 'split': None,
                'prior_ordinal': i-1 if i else None,
                'choice': {'start': m-1., 'end': m, 'label': row['choice']} if valid else None,
                'disposition': 'source_invalid', 'reasons': list(row['source_invalid_reasons'])}
        if valid:
            reasons = []
            if holds:
                reasons = ['session_structural_hold']
            else:
                a, b = m-1., m
                if not row['stim_on_time'] < m:
                    reasons.append('stimulus_not_strictly_before_cutoff')
                matches = [s for s in SPLITS if any(x <= a and b <= y for x, y in splits[s])]
                if len(matches) != 1:
                    reasons.append('choice_outside_complete_split' if not matches else 'choice_ambiguous_split')
                if not any(x <= a and b <= y for x, y in raw['spike_domain']):
                    reasons.append('choice_outside_complete_spike_domain')
                if not reasons:
                    token = json.dumps([raw['session_id'], identity, i], sort_keys=True, separators=(',', ':'))
                    case_id = 'case_' + hashlib.sha256(token.encode()).hexdigest()
                    h, available, reason = _history(rows, i)
                    cases.append({'case_id': case_id, 'ordinal': i, 'split': matches[0],
                        'S': _one(row['S_index'], 9), 'B': _one(row['B_index'], 3), 'H': h,
                        'N': [], 'y': row['choice'], 'window_start': a, 'window_end': b,
                        'prior_case_id': None, 'history_available': available, 'history_reason': reason,
                        'unit_ids': list(unit_ids), 'count_row': []})
                    slot.update(case_id=case_id, split=matches[0], disposition='eligible')
                else:
                    slot['disposition'] = 'held' if holds else 'excluded_choice'
            slot['reasons'] = reasons
            if holds: slot['disposition'] = 'held'
        for reason in slot['reasons']:
            counts['excluded_by_reason'][reason] = counts['excluded_by_reason'].get(reason, 0) + 1
        slots.append(slot)
    ranks = [SPLITS.index(c['split']) for c in cases]
    if ranks != sorted(ranks):
        _hold(holds, 'G04_selected_split_original_chronology')
        for slot in slots:
            if slot['disposition'] == 'eligible':
                slot.update(disposition='held', reasons=['session_structural_hold'], case_id=None, split=None)
                counts['excluded_by_reason']['session_structural_hold'] = counts['excluded_by_reason'].get('session_structural_hold', 0) + 1
        cases = []
    # Full-unit half-open counting. Left/left endpoint rule adapted from count_core.
    index_by_unit = {u: i for i, u in enumerate(unit_ids)}
    by_ordinal = {case['ordinal']: case for case in cases}
    for case in cases:
        histogram = [0] * len(unit_ids)
        lo = bisect.bisect_left(raw['spike_times'], case['window_start'])
        hi = bisect.bisect_left(raw['spike_times'], case['window_end'])
        for j in range(lo, hi):
            histogram[index_by_unit[raw['spike_units'][j]]] += 1
        case['count_row'] = histogram
        case['N'] = [math.log1p(v) for v in histogram]
        previous = by_ordinal.get(case['ordinal']-1)
        case['prior_case_id'] = previous['case_id'] if previous and case['history_available'] else None
        counts['matrix'].append(list(histogram))
        counts['case_ids'].append(case['case_id'])
        counts['eligible_by_split'][case['split']] += 1
    inverse = [None] * len(rows)
    for row in rows:
        inverse[row['raw_index']] = row['ordinal']
    result = {'session_id': member['eid'], 'subject_id': member['subject'], 'lab': member['lab'],
        'source_identity': copy.deepcopy(identity), 'source_profile': raw['source_profile'],
        'unit_ids': unit_ids, 'slots': slots, 'cases': cases, 'counts': counts,
        'status': 'source_only_unqualified', 'gates': [{'gate': f'G{i:02d}', 'status': 'unpassed'} for i in range(1, 25)],
        'structural_holds': list(holds.values()), 'raw_to_sorted': inverse,
        'sorted_to_raw': [r['raw_index'] for r in rows], 'derived_splits': splits,
        'task_envelope': tasks['envelope'], 'work_units': work}
    result['reduction_profile'] = reduction_profile
    result['source_asset_binding'] = {
        'expected_inherited_sha256': member.get('inherited_sha256'),
        'declared_source_sha256': identity['source_sha256'],
        'member_descriptor': {key: copy.deepcopy(member[key]) for key in ROSTER_DESCRIPTOR_KEYS}
                             if set(ROSTER_DESCRIPTOR_KEYS) <= set(member) else None,
        'authentic_bytes_authenticated': False,
        'unknown_source_sha256': identity['source_sha256'] is None}
    _json_bytes(result, limits['max_output_bytes'], 'output_byte_limit')
    return result


def prepare_all(raw_by_eid, roster_members, *, limits):
    """Require the complete frozen ordered29/13/7 roster, never a pilot subset."""
    _limits(limits)
    _json_bytes({'raw_by_eid': raw_by_eid, 'roster_members': roster_members},
                limits['max_input_bytes'], 'input_byte_limit')
    _roster_members(roster_members)
    _need(len(ROSTER) == 29 and len({s for _, s, _ in ROSTER}) == 13
          and len({lab for _, _, lab in ROSTER}) == 7, 'frozen_roster_integrity')
    _need(type(raw_by_eid) is dict and set(raw_by_eid) == {e for e, _, _ in ROSTER}, 'full_session_set')
    work = sum(_shape(raw_by_eid[m['eid']], m, limits) for m in roster_members)
    _need(work <= limits['max_work'], 'aggregate_work_limit', {'required': work, 'limit': limits['max_work']})
    result = [prepare_session(raw_by_eid[m['eid']], m, limits=limits) for m in roster_members]
    _json_bytes(result, limits['max_output_bytes'], 'output_byte_limit')
    return result


def _indicator(value, length, code):
    _need(type(value) is list and len(value) == length
          and all(type(x) in (int, float) and x in (0., 1.) for x in value)
          and sum(value) == 1., code)


def project_case(case, condition, *, include_label=False):
    """Exact actor schema; context projection never inspects neural fields."""
    _need(type(case) is dict and _string(case.get('case_id')), 'case_identity')
    _need(type(condition) is str and condition in CONDITIONS, 'information_condition')
    _need(type(include_label) is bool, 'include_label_exact_bool')
    _indicator(case.get('S'), 9, 'stimulus_indicator')
    _indicator(case.get('H'), 7, 'history_indicator')
    names, values = list(S_NAMES + H_NAMES), list(case['S']) + list(case['H'])
    if condition in ('SBH', 'SBHN'):
        _indicator(case.get('B'), 3, 'block_indicator')
        names += list(B_NAMES)
        values += list(case['B'])
    if condition in ('SHN', 'SBHN'):
        units, neural = case.get('unit_ids'), case.get('N')
        _need(type(units) is list and units and all(_string(u) for u in units)
              and len(set(units)) == len(units), 'neural_unit_axis')
        _need(type(neural) is list and len(neural) == len(units)
              and all(_finite(x) and x >= 0 for x in neural), 'neural_log_counts')
        names += ['N:' + unit for unit in units]
        values += list(neural)
    result = {'case_id': case['case_id'], 'condition': condition, 'feature_names': names, 'features': values}
    if include_label:
        _need(type(case.get('y')) is int and case['y'] in (0, 1), 'binary_label')
        result['y'] = case['y']
    return result
