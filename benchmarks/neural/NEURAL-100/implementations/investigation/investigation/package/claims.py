"""Typed interpretation of the complete NEURAL-100 investigation.

No file reads, arrays, scientific execution, candidate self-grounding, scalar
reasoning score, or pass threshold. The parent first admits both submissions,
then supplies one actual independently recomputed full core result and its
unchanged report_contract.project projection. Missing retained evidence is
explicitly ungradable; a missing spike is never certified observed silence.
"""
import math
import re


TASK = 'NEURAL-100'
CONTRACT = 'neural100_released_panel_draft_v1'
SCHEMA = 'neural100_investigation_claims_v1'
AREAS = ('A1', 'A2')
LAYERS = ('L4', 'L6')
CONDITIONS = ('primary', 'threshold_2_5', 'threshold_3_5', 'bins_2ms',
              'boundary_erosion_one_depth', 'baseline_pseudo_onset',
              'development_snr_bin_contact_matched', 'first_spike_median_descriptive')
DETECTORS = ('primary', 'threshold_2_5', 'threshold_3_5', 'bins_2ms',
             'boundary_erosion_one_depth', 'development_snr_bin_contact_matched')
DIRECTIONS = ('L6_earlier', 'L6_later', 'equal', 'undefined')
ESTIMATORS = ('population_threshold', 'pre_stimulus_pseudo_onset',
              'conditional_first_population_spike')
INTERPRETATION_FLAGS = (
    'exact_paper_reproduction', 'physical_timing_calibration_established',
    'complete_window_observation_required', 'zero_events_prove_observed_silence',
    'causal_pathway_established', 'manuscript_area_counts_reconciled',
    'pseudo_onset_is_calibrated_permutation_p_value',
    'first_spike_is_chase_young_significance_estimator',
    'intervals_are_simultaneous_significance_declarations',
    'development_matching_establishes_exact_snr_or_biological_matching',
    'boundary_erosion_reconstructs_anatomical_shifts',
)
EVIDENCE_COUNTS = ('test_trials', 'spiking_trials', 'no_spike_trials')
MAX_EXACT_INTEGER = 2 ** 53


class InvalidClaims(ValueError):
    """Malformed candidate claims; no private reference is needed to reject."""


class InvalidReference(ValueError):
    """Unexpected/incomplete core or projection; not a candidate score."""


def _need(condition, message, error=InvalidClaims):
    if not condition:
        raise error(message)


def _keys(value, keys, label, error=InvalidClaims):
    _need(type(value) is dict and set(value) == set(keys), 'Exact ' + label + ' fields', error)


def _integer(value, cap, label, error=InvalidClaims):
    _need(type(value) is int and 0 <= value <= cap, 'Bounded nonboolean ' + label, error)


def _enum(value, values, label, error=InvalidClaims):
    _need(type(value) is str and value in values, 'Typed ' + label, error)


def _number(value, label, nullable=True):
    _need((value is None and nullable) or
          (type(value) in (int, float) and math.isfinite(value) and -50 <= value <= 50),
          'Finite reference latency: ' + label, InvalidReference)


def _roster(roster, error=InvalidClaims):
    _need(type(roster) is list and len(roster) == 47, 'Complete 47-recording roster', error)
    rows = {}
    for row in roster:
        _keys(row, ('recording_id', 'participant_id', 'area'), 'roster', error)
        _need(all(type(row[key]) is str and row[key] for key in ('recording_id', 'participant_id')),
              'Nonempty roster identities', error)
        _enum(row['area'], AREAS, 'source area', error)
        _need(row['recording_id'] not in rows, 'Unique recording identity', error)
        rows[row['recording_id']] = row
    _need(len({row['participant_id'] for row in rows.values()}) == 41,
          'Complete 41-participant roster', error)
    _need({area: sum(row['area'] == area for row in rows.values()) for area in AREAS} ==
          {'A1': 39, 'A2': 8}, 'Released 39/8 source-area support', error)
    return rows


def _support(value, cap, label):
    _keys(value, ('recorded', 'defined', 'undefined'), label)
    for key in value:
        _integer(value[key], cap, label + '/' + key)
    _need(value['defined'] + value['undefined'] == value['recorded'],
          'Complete partition of ' + label)


def _evidence(value):
    _keys(value, ('status', 'conditional_scope', *EVIDENCE_COUNTS), 'first-spike evidence')
    _enum(value['status'], ('retained', 'ungradable_missing_full_reference_evidence'), 'evidence status')
    _enum(value['conditional_scope'], ('spiking_test_trials_only', 'all_test_trials'), 'first-spike scope')
    if value['status'] == 'retained':
        for key in EVIDENCE_COUNTS:
            _integer(value[key], MAX_EXACT_INTEGER, key)
        _need(value['spiking_trials'] + value['no_spike_trials'] == value['test_trials'],
              'First-spike support partition')
    else:
        _need(all(value[key] is None for key in EVIDENCE_COUNTS),
              'Ungradable support uses null evidence, not invented counts')


def admit(claims, roster):
    """Validate only the public typed contract; incorrect science stays gradeable.

No claim is checked against a candidate numerical report or private reference.
Internal count partitions and full identity coverage are representation rules;
direction, interval, estimator and interpretation assertions may be incorrect.
"""
    expected = _roster(roster)
    _keys(claims, ('schema', 'task_id', 'contract', 'scope', 'interpretation',
                   'recordings', 'conditions'), 'claims')
    _need(claims['schema'] == SCHEMA and claims['task_id'] == TASK and
          claims['contract'] == CONTRACT, 'Exact claims identity')
    _keys(claims['scope'], ('recordings', 'participants', 'source_area_recording_counts'), 'scope')
    _need(type(claims['scope']['recordings']) is int and claims['scope']['recordings'] == 47 and
          type(claims['scope']['participants']) is int and claims['scope']['participants'] == 41,
          'Full investigation scope')
    _keys(claims['scope']['source_area_recording_counts'], AREAS, 'area scope')
    _need(all(type(claims['scope']['source_area_recording_counts'][area]) is int and
              claims['scope']['source_area_recording_counts'][area] == {'A1': 39, 'A2': 8}[area]
              for area in AREAS), 'Source cohort, never manuscript relabeling')
    interpretation = claims['interpretation']
    _keys(interpretation, (*INTERPRETATION_FLAGS, 'aggregation_unit', 'repeated_recordings',
                           'primary_condition'), 'interpretation')
    _need(all(type(interpretation[key]) is bool for key in INTERPRETATION_FLAGS),
          'Typed interpretation assertions')
    _enum(interpretation['aggregation_unit'], ('participant', 'recording', 'unit', 'trial'), 'aggregation unit')
    _enum(interpretation['repeated_recordings'], ('average_within_participant_area',
          'independent_recordings'), 'repeat handling')
    _enum(interpretation['primary_condition'], CONDITIONS, 'prespecified primary identity')
    _need(type(claims['recordings']) is list and len(claims['recordings']) == 47,
          'All recording claims required')
    seen = set()
    for row in claims['recordings']:
        _keys(row, ('recording_id', 'participant_id', 'area', 'conditions', 'first_spike_evidence'),
              'recording claim')
        key = row['recording_id']
        _need(type(key) is str and key in expected and key not in seen, 'Exact recording join')
        seen.add(key)
        _need(all(row[name] == expected[key][name] for name in ('participant_id', 'area')),
              'Exact participant/area join')
        _keys(row['conditions'], CONDITIONS, 'recording conditions')
        for condition in CONDITIONS:
            value = row['conditions'][condition]
            _keys(value, ('direction', 'layer_status'), 'recording interpretation')
            _enum(value['direction'], DIRECTIONS, 'recording direction')
            _keys(value['layer_status'], LAYERS, 'layer dispositions')
            for layer in LAYERS:
                _enum(value['layer_status'][layer], ('defined', 'undefined'), 'layer disposition')
        _keys(row['first_spike_evidence'], LAYERS, 'first-spike layers')
        for layer in LAYERS:
            _evidence(row['first_spike_evidence'][layer])
    _keys(claims['conditions'], CONDITIONS, 'all eight scientific conditions')
    for condition in CONDITIONS:
        value = claims['conditions'][condition]
        _keys(value, ('estimator', 'areas'), 'condition claim')
        _enum(value['estimator'], ESTIMATORS, 'estimator distinction')
        _keys(value['areas'], AREAS, 'both source areas')
        for area in AREAS:
            claim = value['areas'][area]
            _keys(claim, ('full_cohort_direction', 'observed_only_direction', 'observed_only_scope',
                          'participant_support', 'recording_support', 'interval',
                          'direction_relation_to_primary'), 'area claim')
            for key in ('full_cohort_direction', 'observed_only_direction'):
                _enum(claim[key], DIRECTIONS, key)
            _enum(claim['observed_only_scope'], ('full_cohort', 'defined_participants_only',
                  'no_defined_participants'), 'observed-only scope')
            _support(claim['participant_support'], 41, 'participant support')
            _support(claim['recording_support'], 47, 'recording support')
            interval = claim['interval']
            _keys(interval, ('position', 'defined_draws', 'undefined_draws',
                             'complete_unconditional_interval'), 'interval claim')
            _enum(interval['position'], ('strictly_below_zero', 'strictly_above_zero',
                  'contains_zero', 'withheld'), 'interval position')
            for key in ('defined_draws', 'undefined_draws'):
                _integer(interval[key], 1000, key)
            _need(interval['defined_draws'] + interval['undefined_draws'] == 1000,
                  'Complete bootstrap support partition')
            _need(type(interval['complete_unconditional_interval']) is bool, 'Typed interval availability')
            _enum(claim['direction_relation_to_primary'], ('same', 'different', 'unavailable'),
                  'condition-specific primary relation')
    return claims


def _same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(_same(a[key], b[key]) for key in a)
    if type(a) is list:
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _direction(value):
    _number(value, 'direction operand')
    return 'undefined' if value is None else 'L6_earlier' if value < 0 else 'L6_later' if value > 0 else 'equal'


def _projection(full):
    """Exact field mapping of unchanged report_contract.project, no analysis."""
    rows = []
    for row in full['per_recording']:
        conditions = {}
        for condition in CONDITIONS:
            value = row['conditions'][condition]
            conditions[condition] = {
                layer: {key: value['layers'][layer][key] for key in ('status', 'latency_ms')}
                for layer in LAYERS}
            conditions[condition]['delta_ms'] = value['delta_l6_minus_l4_ms']
        rows.append({key: row[key] for key in ('recording_id', 'participant_id', 'area')} |
                    {'conditions': conditions})
    areas = {}
    for condition in CONDITIONS:
        areas[condition] = {}
        for area in AREAS:
            value = full['conditions'][condition][area]
            areas[condition][area] = {
                'full_mean_ms': value['full_area_mean_ms'],
                'observed_only_mean_ms': value['observed_only_mean_ms'],
                'participants': value['recorded_participants'],
                'defined_participants': value['defined_participants'],
                'defined_draws': value['bootstrap']['defined_draws'],
                'ci95_ms': value['bootstrap']['percentile_95_interval_ms']}
    return {'task_id': TASK, 'contract': CONTRACT, 'recordings': rows, 'areas': areas}


def _retained_evidence(layer):
    result = {'status': 'ungradable_missing_full_reference_evidence',
              'conditional_scope': 'spiking_test_trials_only',
              **{key: None for key in EVIDENCE_COUNTS}}
    if not all(key in layer for key in EVIDENCE_COUNTS):
        return result
    for key in EVIDENCE_COUNTS:
        _integer(layer[key], MAX_EXACT_INTEGER, 'reference ' + key, InvalidReference)
    _need(layer['spiking_trials'] + layer['no_spike_trials'] == layer['test_trials'],
          'Retained first-spike support partition', InvalidReference)
    _need((layer['status'] == 'defined') == (layer['spiking_trials'] > 0),
          'Retained first-spike disposition', InvalidReference)
    return {'status': 'retained', 'conditional_scope': 'spiking_test_trials_only',
            **{key: layer[key] for key in EVIDENCE_COUNTS}}


def _area(full, records, condition, area):
    value = full['conditions'][condition][area]
    selected = [row for row in records if row['area'] == area]
    grouped = {}
    defined_recordings = 0
    for row in selected:
        delta = row['conditions'][condition]['delta_l6_minus_l4_ms']
        grouped.setdefault(row['participant_id'], []).append(delta)
        defined_recordings += delta is not None
    participant_rows = []
    for participant in sorted(grouped):
        deltas = grouped[participant]
        missing = sum(delta is None for delta in deltas)
        participant_rows.append({'participant_id': participant, 'recordings': len(deltas),
            'status': 'undefined' if missing else 'defined',
            'delta_l6_minus_l4_ms': None if missing else math.fsum(deltas) / len(deltas),
            'undefined_recordings': missing})
    _need(_same(value['participant_effects'], participant_rows),
          'Full reference preserves repeat/participant hierarchy', InvalidReference)
    observed = [row['delta_l6_minus_l4_ms'] for row in participant_rows if row['status'] == 'defined']
    complete = len(observed) == len(participant_rows) and bool(participant_rows)
    observed_mean = math.fsum(observed) / len(observed) if observed else None
    wanted = {'recorded_participants': len(participant_rows), 'recordings': len(selected),
              'defined_participants': len(observed), 'undefined_participants': len(participant_rows) - len(observed),
              'full_area_mean_ms': observed_mean if complete else None,
              'full_area_status': 'defined' if complete else 'undefined_incomplete_participant_effects',
              'observed_only_mean_ms': observed_mean, 'observed_only_is_full_cohort': complete}
    _need(all(_same(value[key], target) for key, target in wanted.items()),
          'Full reference aggregate/support consistency', InvalidReference)
    bootstrap = value['bootstrap']
    for key in ('draws', 'defined_draws', 'undefined_draws', 'no_area_participant_draws',
                'undefined_participant_selected_draws'):
        _integer(bootstrap[key], 1000, 'reference bootstrap ' + key, InvalidReference)
    _need(bootstrap['draws'] == 1000 and bootstrap['defined_draws'] + bootstrap['undefined_draws'] == 1000 and
          bootstrap['no_area_participant_draws'] + bootstrap['undefined_participant_selected_draws'] ==
          bootstrap['undefined_draws'] and bootstrap['redrawn_or_conditioned_on_defined_draws'] is False,
          'Complete unconditional bootstrap support', InvalidReference)
    _need(not complete or bootstrap['undefined_participant_selected_draws'] == 0,
          'A complete participant effect cannot select an undefined participant', InvalidReference)
    ci = bootstrap['percentile_95_interval_ms']
    _need((ci is not None) == (complete and bootstrap['defined_draws'] == 1000),
          'Full reference unconditional interval disposition', InvalidReference)
    if ci is None:
        position = 'withheld'
    else:
        _need(type(ci) is list and len(ci) == 2, 'Reference interval shape', InvalidReference)
        for endpoint in ci:
            _number(endpoint, 'interval endpoint', nullable=False)
        _need(ci[0] <= ci[1], 'Ordered reference interval', InvalidReference)
        position = 'strictly_below_zero' if ci[1] < 0 else 'strictly_above_zero' if ci[0] > 0 else 'contains_zero'
    _need(bootstrap['interval_status'] == ('defined' if ci is not None else
          'withheld_no_complete_unconditional_interval'), 'Reference interval label', InvalidReference)
    direction = _direction(value['full_area_mean_ms'])
    primary = _direction(full['conditions']['primary'][area]['full_area_mean_ms'])
    relation = 'unavailable' if 'undefined' in (direction, primary) else 'same' if direction == primary else 'different'
    return {'full_cohort_direction': direction, 'observed_only_direction': _direction(observed_mean),
            'observed_only_scope': 'full_cohort' if complete else 'defined_participants_only' if observed else
                                   'no_defined_participants',
            'participant_support': {'recorded': len(participant_rows), 'defined': len(observed),
                                    'undefined': len(participant_rows) - len(observed)},
            'recording_support': {'recorded': len(selected), 'defined': defined_recordings,
                                  'undefined': len(selected) - defined_recordings},
            'interval': {'position': position, 'defined_draws': bootstrap['defined_draws'],
                         'undefined_draws': bootstrap['undefined_draws'],
                         'complete_unconditional_interval': ci is not None},
            'direction_relation_to_primary': relation}


def derive(full_core_result, numeric_projection, roster):
    """Derive expected claims from the independently computed full result only."""
    expected = _roster(roster, InvalidReference)
    full = full_core_result
    try:
        _need(type(full) is dict and full['policy'] == CONTRACT and
              type(full['recordings']) is int and full['recordings'] == 47 and
              type(full['participants']) is int and full['participants'] == 41,
              'Complete current full core result', InvalidReference)
        _need(_same(full['source_area_recording_counts'], {'A1': 39, 'A2': 8}),
              'Full source area support', InvalidReference)
        for key in ('exact_paper_reproduction', 'timing_alignment_established_by_core',
                    'paper_area_counts_used_to_select_or_relabel', 'anatomical_shift_reconstruction',
                    'causal_pathway_claim'):
            _need(full[key] is False, 'Fixed core limitation: ' + key, InvalidReference)
        _need(full['scientific_success_threshold'] is None and
              full['boundary_control'] == 'one_depth_exclusion_without_relabeling',
              'Fixed scientific scope', InvalidReference)
        schedule = full['bootstrap_schedule']
        _need(schedule['generator'] == 'PCG64' and type(schedule['seed']) is int and schedule['seed'] == 100043 and
              type(schedule['draws']) is int and schedule['draws'] == 1000 and
              type(schedule['draw_size']) is int and schedule['draw_size'] == 41 and
              schedule['participant_order'] == sorted({row['participant_id'] for row in roster}) and
              schedule['shared_across_areas_and_conditions'] is True and
              type(schedule['multiplicity_sha256']) is str and
              re.fullmatch('[0-9a-f]{64}', schedule['multiplicity_sha256']),
              'Retained shared participant bootstrap identity', InvalidReference)
        records = full['per_recording']
        _need(type(records) is list and len(records) == 47, 'Complete full recording results', InvalidReference)
        seen = set()
        for row in records:
            key = row['recording_id']
            _need(type(key) is str and key in expected and key not in seen and
                  all(row[name] == expected[key][name] for name in ('participant_id', 'area')),
                  'Full reference roster join', InvalidReference)
            seen.add(key)
            _keys(row['conditions'], CONDITIONS, 'full recording conditions', InvalidReference)
            for condition in CONDITIONS:
                value = row['conditions'][condition]
                _keys(value['layers'], LAYERS, 'full layer result', InvalidReference)
                for layer in LAYERS:
                    _enum(value['layers'][layer]['status'], ('defined', 'undefined'), 'reference status', InvalidReference)
                    latency = value['layers'][layer]['latency_ms']
                    _number(latency, 'layer latency')
                    _need((latency is not None) == (value['layers'][layer]['status'] == 'defined'),
                          'Reference latency disposition', InvalidReference)
                delta = value['delta_l6_minus_l4_ms']
                _number(delta, 'recording contrast')
                defined = all(value['layers'][layer]['status'] == 'defined' for layer in LAYERS)
                _need(value['status'] == ('defined' if defined else 'undefined') and
                      (delta is not None) == defined and (not defined or
                      delta == value['layers']['L6']['latency_ms'] - value['layers']['L4']['latency_ms']),
                      'Full reference contrast consistency', InvalidReference)
        _keys(full['conditions'], CONDITIONS, 'full area conditions', InvalidReference)
        for condition in CONDITIONS:
            _keys(full['conditions'][condition], AREAS, 'full area results', InvalidReference)
        for area in AREAS:
            _need(all(_same(full['conditions'][condition][area]['bootstrap']['no_area_participant_draws'],
                            full['conditions']['primary'][area]['bootstrap']['no_area_participant_draws'])
                      for condition in CONDITIONS),
                  'Shared participant draws preserve no-area support across all conditions', InvalidReference)
        _need(_same(_projection(full), numeric_projection),
              'Supplied projection must be the unchanged projection of this full core result', InvalidReference)
        records = sorted(records, key=lambda row: row['recording_id'])
        result = {'schema': SCHEMA, 'task_id': TASK, 'contract': CONTRACT,
                  'scope': {'recordings': 47, 'participants': 41,
                            'source_area_recording_counts': {'A1': 39, 'A2': 8}},
                  'interpretation': {**{key: False for key in INTERPRETATION_FLAGS},
                    'complete_window_observation_required': True, 'aggregation_unit': 'participant',
                    'repeated_recordings': 'average_within_participant_area', 'primary_condition': 'primary'},
                  'recordings': [], 'conditions': {}}
        for row in records:
            result['recordings'].append({**{key: row[key] for key in ('recording_id', 'participant_id', 'area')},
                'conditions': {condition: {
                    'direction': _direction(row['conditions'][condition]['delta_l6_minus_l4_ms']),
                    'layer_status': {layer: row['conditions'][condition]['layers'][layer]['status'] for layer in LAYERS}}
                    for condition in CONDITIONS},
                'first_spike_evidence': {layer: _retained_evidence(
                    row['conditions']['first_spike_median_descriptive']['layers'][layer]) for layer in LAYERS}})
        for condition in CONDITIONS:
            estimator = ('population_threshold' if condition in DETECTORS else
                         'pre_stimulus_pseudo_onset' if condition == 'baseline_pseudo_onset' else
                         'conditional_first_population_spike')
            result['conditions'][condition] = {'estimator': estimator,
                'areas': {area: _area(full, records, condition, area) for area in AREAS}}
        return admit(result, roster)
    except InvalidReference:
        raise
    except (KeyError, TypeError, AttributeError, OverflowError, InvalidClaims) as exc:
        raise InvalidReference('Incomplete or invalid full reference: ' + str(exc)) from exc


def _comparable(claims):
    return {**{key: value for key, value in claims.items() if key != 'recordings'},
            'recordings': {row['recording_id']: {key: value for key, value in row.items()
                          if key != 'recording_id'} for row in claims['recordings']}}


def compare(claims, expected):
    """Exact typed-field discrepancies, with unsupported evidence kept separate."""
    roster = [{key: row[key] for key in ('recording_id', 'participant_id', 'area')}
              for row in expected['recordings']]
    admit(expected, roster)
    admit(claims, roster)
    left, right = _comparable(claims), _comparable(expected)
    matches, mismatches, ungradable = [], [], []
    def walk(a, b, path):
        if type(b) is dict:
            missing_evidence = b.get('status') == 'ungradable_missing_full_reference_evidence'
            for key in sorted(b):
                child = path + '/' + key
                if missing_evidence and key in EVIDENCE_COUNTS:
                    ungradable.append({'path': child, 'reason': 'Exact full reference lacks retained first-spike support'})
                else:
                    walk(a[key], b[key], child)
        elif _same(a, b):
            matches.append(path)
        else:
            mismatches.append({'path': path, 'kind': 'typed_claim_mismatch'})
    walk(left, right, '')
    return {'schema': 'neural100_typed_claim_comparison_v1', 'status': 'compared',
            'matching_field_paths': matches, 'mismatches': mismatches,
            'ungradable_evidence': ungradable, 'scientific_reasoning_scalar': None,
            'pass_threshold': None, 'scientific_success_or_SOTA_claim': False,
            'empirical_input_use_established': False,
            'note': 'Typed interpretation agreement is separate from unchanged numerical errors; unsupported evidence is not invented truth.'}
