"""APCx exporter-specific, owner-only census arithmetic; no I/O or imports of data.

Every computation is a released-field diagnostic. None supplies a physical
delivery target, missing original chronology, or an all-QC roster certificate.
"""
import bisect
import hashlib
import math
import re
import struct

FIELDS = ('Animal', 'Session', 'Date', 'Trial', 'Total_pulse', 'High_trial',
          'High_choice', 'Correct', 'Trial odor', 'Sniff histogram', 'Breathing',
          'Cell', 'Spike_times', 'Firing_rates')
ANIMALS = ('Tabby', 'Shorthair', 'Bengal')
EDGES = tuple((10 + i) / 20 for i in range(91))
PERMANENT_HOLDS = (
    'EXTERNAL_GOOD_CELLS_BST_ROSTER_AND_ALL_QC_LINEAGE_UNVERIFIED',
    'ORIGINAL_TRIAL_IDS_EXCLUSIONS_AND_CHRONOLOGY_UNAVAILABLE',
    'PHYSICAL_VALVE_DELIVERY_EVENT_LOG_AND_OVERLAP_SEMANTICS_UNAVAILABLE',
    'COMPILER_TO_DEPOSITED_FILE_EXECUTION_LINEAGE_UNPROVEN',
    'SOURCE_ZERO_TICK_VS_PADDING_AND_FIXED_SPIKE_CAP_PROVENANCE',
)


def fingerprint(value, max_elements=250000, max_depth=8):
    """Typed decoded-value digest; no pickle, repr, object coercion or raw hash claim."""
    h = hashlib.sha256(); count = 0; logical = 0
    def visit(x, depth):
        nonlocal count, logical
        count += 1
        if count > max_elements or depth > max_depth:
            raise ValueError('decoded value structural cap')
        if x is None: h.update(b'N'); logical += 1
        elif type(x) is bool: h.update(b'B1' if x else b'B0'); logical += 1
        elif type(x) is int:
            if not -(2**63) <= x < 2**64: raise ValueError('integer outside Arrow64 domain')
            h.update(b'I' + str(x).encode() + b';'); logical += 8
        elif type(x) is float: h.update(b'F' + struct.pack('>d', x)); logical += 8
        elif type(x) is str:
            b = x.encode('utf8'); h.update(b'S' + struct.pack('>Q', len(b)) + b); logical += len(b)
        elif type(x) is bytes:
            h.update(b'Y' + struct.pack('>Q', len(x)) + x); logical += len(x)
        elif type(x) is list:
            h.update(b'L' + struct.pack('>Q', len(x)))
            for item in x: visit(item, depth + 1)
        elif type(x) is dict and all(type(k) is str for k in x):
            h.update(b'D' + struct.pack('>Q', len(x)))
            for key in sorted(x): visit(key, depth + 1); visit(x[key], depth + 1)
        else: raise ValueError('unsupported decoded object type: ' + type(x).__name__)
    visit(value, 0)
    return {'sha256': h.hexdigest(), 'elements': count, 'logical_scalar_bytes': logical}


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def numeric_list(x):
    return type(x) is list and all(number(v) for v in x)


def spike_census(values):
    out = {'status': 'INVALID', 'bins_50ms': None, 'physical_sampling_window': [0.5, 5.0],
           'first_500ms_observed': False, 'unit': 'spike count', 'violations': []}
    if type(values) is not list:
        out['violations'].append('SPIKE_TIMES_NOT_LIST'); return out
    out['source_entries'] = len(values)
    if not numeric_list(values):
        out['violations'].append('SPIKE_TIMES_NONNUMERIC_OR_NONFINITE'); return out
    bins = [0] * 90; early = after = negative = 0
    for t in values:
        if t < 0: negative += 1
        elif t < 0.5: early += 1
        elif t >= 5.0: after += 1
        else: bins[bisect.bisect_right(EDGES, t) - 1] += 1
    if negative: out['violations'].append('NEGATIVE_RELEASED_SPIKE_TIME')
    if after: out['violations'].append('SPIKES_AT_OR_AFTER_DECLARED_FIVE_SECOND_END')
    if early: out['violations'].append('RELEASE_CONTAINS_SPIKES_IN_DECLARED_UNOBSERVED_INTERVAL')
    if any(b < a for a, b in zip(values, values[1:])):
        out['violations'].append('SPIKE_TIMES_NOT_NONDECREASING')
    duplicates = len(values) - len(set(values))
    if duplicates: out['violations'].append('DUPLICATE_SPIKE_TIMES_PRESERVED_NOT_DEDUPLICATED')
    out.update(status='OBSERVED_WINDOW_PROJECTION_ONLY', bins_50ms=bins,
               observed_spikes=sum(bins), early_entries=early,
               at_or_after_five_seconds=after, negative_entries=negative,
               duplicate_time_entries=duplicates,
               explicit_half_open_bin_convention=True)
    return out


def command_census(values, released_total, high_label):
    """Count conventions at source-declared 1 ms/100-unit/50 ms hypotheses.

    Agreement never proves physical pulse delivery. Full-array compiler area,
    exact five-second area, source diff>0, diff==100 and initial-aware command
    runs are separate named diagnostics; none substitutes for the primary.
    """
    out = {'status': 'UNRESOLVED', 'physical_event_count': None,
           'physical_delivery_verified': False, 'violations': [],
           'convention_basis': 'source hypotheses: 1 ms samples; command100; pulse50ms; denominator5000'}
    if type(values) is not list or not numeric_list(values):
        out['violations'].append('COMMAND_NOT_FINITE_NUMERIC_LIST'); return out
    out['source_samples'] = len(values)
    if any(v not in (0, 100) for v in values):
        out['violations'].append('COMMAND_AMPLITUDE_NOT_EXACT_SOURCE_ZERO_OR_100'); return out
    out['compiler_full_array_ceiling'] = math.ceil(math.fsum(values) / 5000)
    out['compiler_label_equal'] = type(released_total) is int and released_total == out['compiler_full_array_ceiling']
    if not out['compiler_label_equal']: out['violations'].append('RELEASED_TOTAL_DIFFERS_FROM_COMPILER_FULL_ARRAY_QUANTITY')
    if len(values) < 5000:
        out['violations'].append('INSUFFICIENT_SAMPLES_FOR_FIVE_SECOND_COMMAND_HYPOTHESIS'); return out
    window = values[:5000]
    positive = [i for i in range(1, 5000) if window[i] > window[i - 1]]
    exact100 = [i for i in range(1, 5000) if window[i] - window[i - 1] == 100]
    starts = ([0] if window[0] == 100 else []) + positive
    runs = []
    for start in starts:
        end = start + 1
        while end < 5000 and window[end] == 100: end += 1
        runs.append(end - start)
    five_quantity = math.ceil(math.fsum(window) / 5000)
    out.update(status='COMMAND_CONVENTIONS_ONLY_NOT_PHYSICAL_TARGET',
               exact_first5000_area_ceiling=five_quantity,
               source_diff_positive_count=len(positive), source_diff_equal100_count=len(exact100),
               initial_aware_command_run_count=len(starts),
               command_high_at_t0=bool(window[0]), command_high_at_last_sample=bool(window[-1]),
               early_command_run_starts=sum(i < 500 for i in starts),
               observed_command_run_starts=sum(i >= 500 for i in starts),
               run_length_samples_histogram={str(k): runs.count(k) for k in sorted(set(runs))},
               extra_after_five_second_nonzero_samples=sum(v != 0 for v in values[5000:]),
               five_second_area_and_initial_aware_run_agree=five_quantity == len(starts),
               source_diff_and_initial_aware_agree=len(positive) == len(starts),
               released_high_equals_quantity_boundary=(type(high_label) is int and high_label in (0, 1)
                                                       and high_label == int(five_quantity >= 9)))
    if five_quantity != out['compiler_full_array_ceiling']:
        out['violations'].append('FULL_ARRAY_QUANTITY_DIFFERS_FROM_FIVE_SECOND_QUANTITY')
    if any(n != 50 for n in runs): out['violations'].append('COMMAND_RUN_NOT_ONE_50_SAMPLE_PULSE')
    if not out['released_high_equals_quantity_boundary']:
        out['violations'].append('RELEASED_CATEGORY_DIFFERS_FROM_FIVE_SECOND_QUANTITY_BOUNDARY')
    return out


def audit_row(row, max_elements=250000):
    if type(row) is not dict or not all(type(k) is str for k in row):
        raise ValueError('ordinary row mapping required')
    findings = []; hashes = {}; logical = 0
    for key, value in row.items():
        item = fingerprint(value, max_elements=max_elements)
        hashes[key] = item; logical += item['logical_scalar_bytes']
    missing = sorted(set(FIELDS) - set(row)); extra = sorted(set(row) - set(FIELDS))
    if missing: findings.append('MISSING_EXACT_EXPORT_FIELDS')
    if extra: findings.append('UNEXPECTED_EXPORT_FIELDS_NO_ALIAS_MAPPING')
    identity = {k: row.get(k) for k in ('Animal', 'Session', 'Date', 'Trial', 'Cell')}
    valid_identity = all(type(identity[k]) is str and len(identity[k].encode()) <= 256
                         for k in ('Animal', 'Session', 'Date'))
    valid_identity = valid_identity and all(type(identity[k]) is int and 0 <= identity[k] < 2**31
                                            for k in ('Trial', 'Cell'))
    if not valid_identity: findings.append('INVALID_RELEASE_IDENTITY')
    elif (identity['Animal'] not in ANIMALS or
          not re.fullmatch(re.escape(identity['Animal']) + r'_[0-9]{8}_0', identity['Session']) or
          identity['Date'] != identity['Session'][-10:-2]):
        findings.append('IDENTITY_NOT_COMPATIBLE_WITH_PINNED_EXPORTER')
    labels = {k: row.get(k) for k in ('Total_pulse', 'High_trial', 'High_choice', 'Correct')}
    if type(labels['Total_pulse']) is not int or labels['Total_pulse'] < 0:
        findings.append('INVALID_RELEASED_TOTAL_QUANTITY_LABEL')
    for key in ('High_trial', 'High_choice', 'Correct'):
        if type(labels[key]) is not int or labels[key] not in (0, 1): findings.append('INVALID_BINARY_' + key)
    if all(type(labels[k]) is int and labels[k] in (0, 1) for k in ('High_trial', 'High_choice', 'Correct')):
        if labels['High_choice'] != int(labels['Correct'] == labels['High_trial']):
            findings.append('HIGH_CHOICE_DIFFERS_FROM_EXPORTER_CORRECT_EQUALS_HIGH_TRIAL')
    spikes = spike_census(row.get('Spike_times'))
    commands = command_census(row.get('Trial odor'), labels['Total_pulse'], labels['High_trial'])
    findings.extend(spikes['violations']); findings.extend(commands['violations'])
    for key in ('Firing_rates', 'Breathing', 'Sniff histogram'):
        if not numeric_list(row.get(key)): findings.append('INVALID_NUMERIC_LIST_' + key)
    if type(row.get('Firing_rates')) is list and len(row['Firing_rates']) != 450:
        findings.append('FIRING_RATE_NOT_450_SOURCE_SLOTS')
    if type(row.get('Breathing')) is list and len(row['Breathing']) != 9000:
        findings.append('BREATHING_NOT_2500_PRE_PLUS_6500_TRIAL_SOURCE_SAMPLES')
    if type(row.get('Sniff histogram')) is list and len(row['Sniff histogram']) != 15:
        findings.append('SNIFF_HISTOGRAM_NOT_15_SOURCE_BINS')
    common = {k: hashes[k]['sha256'] for k in sorted(hashes)
              if k not in ('Cell', 'Spike_times', 'Firing_rates')}
    return {'identity': identity, 'identity_valid_for_released_grouping': valid_identity,
            'labels_owner_only': labels, 'field_fingerprints': hashes,
            'field_shapes': {k: len(v) if type(v) is list else None for k, v in row.items()},
            'logical_scalar_bytes': logical, 'spikes': spikes, 'commands_owner_only': commands,
            'trial_shared_fields_sha256': fingerprint(common)['sha256'],
            'missing_fields': missing, 'extra_fields': extra,
            'violations': sorted(set(findings)), 'scientific_primary_admitted': False,
            'fixed_source_holds': list(PERMANENT_HOLDS)}


def session_conclusion(animal, session, trials, released_units, duplicate_rows):
    """All RELEASED support only. Never certify external all-QC membership."""
    ids = sorted(trials); n = len(ids); cal = (3 * n) // 5; dev = n // 5; test = n - cal - dev
    missing = {str(t): sorted(set(released_units) - set(trials[t]['units'])) for t in ids
               if set(trials[t]['units']) != set(released_units)}
    return {'animal': animal, 'session': session, 'released_trials': n,
            'released_units': sorted(released_units), 'released_trial_ids': ids,
            'trial_ids_contiguous_postfilter_enumeration': ids == list(range(n)),
            'rows_with_duplicate_trial_unit_identity': duplicate_rows,
            'trial_missing_released_unit_support': missing,
            'conditional_60_20_remainder_sizes': [cal, dev, test],
            'conditional_16_8_10_support_gate': cal >= 16 and dev >= 8 and test >= 10,
            'original_chronology_authenticated': False, 'all_original_qc_units_authenticated': False,
            'protected_partitions_constructed': False, 'scientific_primary_admitted': False}
