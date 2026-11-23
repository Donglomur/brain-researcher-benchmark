"""Complete empirical iSTTC sensitivity production and Figure 7C model inputs.

Authentic source admission and scientific qualification remain external. Import
uses only stdlib; the native backend and Figure 7C arithmetic load dependencies
only when explicitly called. Original source components are verified by bytes.
"""
import argparse
import bisect
import hashlib
from fractions import Fraction
from functools import lru_cache
import json
import math
from pathlib import Path
import random
import sys
import types

METHODS = ('acf_full', 'isttc_full', 'pearsonr_trial_avg', 'sttc_trial_concat')
DURATIONS = (1, 5, 10, 20, 30)
COUNTS = (40, 60, 80, 100)
FS = 30000
SIGNAL_TICKS = 54000000
N_UNITS = 5775
N_MICE = 26
N_COORDINATES = N_UNITS * 18
REFERENCE_POLICIES = ('method_specific_full', 'all_full_isttc')
DRAW_SCOPE = 'prospective_independent_count_draws_matched_between_methods_v1'
BRIDGE_SHA = '63d41e13b7300f6ba1dc845be9c7fb7dba167c4b44c99b2f869930f42522dd40'
PRODUCER_SHA = '23971d6e4f3b437274034d4360fdb09b6c751d5be5cb5f396bdcf5d9a4991d7f'
MODELS_SHA = 'a5ef9412e00a9c488dc170bfcfd502a5280afabfbdf1a492a273287ffc652fe8'
POLICY_SHA = '5dbf111108829d57d76138233fbcf008b798bc7e95fb247b7b26c7c5723421b6'
WINDOW_SEED = 20261117004
BOOTSTRAP_SEED = 20261117005
BOOTSTRAP_REPETITIONS = 1000
METADATA_CAP = 16 * 1024 * 1024
FIT_CAP = 64 * 1024 * 1024
RECORD_CAP = 64 * 1024 * 1024
WINDOW_CAP = 32 * 1024


def digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def strict_json(body):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise ValueError('duplicate JSON key')
            output[key] = value
        return output
    def bad_constant(value):
        raise ValueError('nonfinite JSON literal')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant)


def _module(path, expected=None):
    """Execute captured source bytes, without bytecode-cache selection."""
    path = Path(path)
    with path.open('rb') as stream:
        body = stream.read(METADATA_CAP + 1)
    if len(body) > METADATA_CAP or (expected is not None and hashlib.sha256(body).hexdigest() != expected):
        raise ValueError('source identity differs: ' + str(path))
    result = types.ModuleType('_isttc_' + path.stem)
    result.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


@lru_cache(maxsize=1)
def bridge():
    return _module(Path(__file__).resolve().parent.parent / 'empirical-diagnostics' / 'empirical_bridge.py', BRIDGE_SHA)


@lru_cache(maxsize=1)
def producer():
    return _module(Path(__file__).resolve().parent.parent / 'empirical-estimation' / 'producer.py', PRODUCER_SHA)


def models():
    return _module(Path(__file__).resolve().parent / 'models.py', MODELS_SHA)


def policy():
    path = Path(__file__).resolve().parent / 'POLICY.json'
    with path.open('rb') as stream:
        body = stream.read(METADATA_CAP + 1)
    if len(body) > METADATA_CAP or hashlib.sha256(body).hexdigest() != POLICY_SHA:
        raise ValueError('published scientific policy differs')
    return strict_json(body)


def _cohort(document):
    rows = bridge().cohort(document)
    sessions = {}
    for unit in rows:
        previous = sessions.setdefault(unit['session_id'], unit['mouse_id'])
        if previous != unit['mouse_id']:
            raise ValueError('one biological mouse per session required')
    # The exact identities and QC still require authentic admission. This count
    # cannot establish that an operator supplied the original eight areas.
    if len({row['area'] for row in rows}) != 8:
        raise ValueError('complete declared eight-area cohort required')
    return rows


def window_rows(cohort, seed):
    units = _cohort(cohort)
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('prospective window seed must be uint64')
    rng = random.Random(seed)
    for unit in units:
        yield {'schema': 'isttc_sensitivity_windows_v1', 'unit_id': unit['unit_id'],
               'seed': seed, 'draw_scope': DRAW_SCOPE, 'fs_hz': FS,
               'signal_ticks': SIGNAL_TICKS,
               'conditions': [{'trial_count': count,
                               'windows_ticks': [[start, start + FS] for start in
                                                 (rng.randrange(SIGNAL_TICKS - FS + 1) for _ in range(count))]}
                              for count in COUNTS]}


class AuthorSensitivityBackend:
    """The unchanged verified author helpers with explicit paper parameters."""
    def __init__(self, checkout):
        self.original = producer().AuthorBackend(checkout)
        self.identity = dict(self.original.identity)
        self.identity['adapter'] = 'isttc_sensitivity_grid_v1'

    def fit(self, axis, level, method, spikes, trials):
        source = self.original
        if type(level) is not int or (axis == 'duration_minutes' and level not in DURATIONS):
            raise producer().BackendProtocolError('condition level differs from frozen source grid')
        if axis == 'duration_minutes':
            length = level * 60 * FS
            if method == 'acf_full':
                binned = source.spikes.bin_spike_train_fixed_len(spikes, 50, FS, length, verbose_=False)
                curve = source.acf(binned, nlags=20)
            elif method == 'isttc_full':
                curve = source.curves.acf_sttc(source.np.asarray(spikes), 20,
                    lag_shift_=1500, sttc_dt_=750, signal_length_=length, verbose_=False)
            else:
                raise producer().BackendProtocolError('duration method')
            if len(curve) != 21:
                raise producer().BackendProtocolError('full-recording curve must have 21 points')
            fit = source.fitter.fit_single_exp(curve, start_idx_=1, exp_fun_=source.fitter.func_single_exp)
            if len(fit) != 7:
                raise producer().BackendProtocolError('source fitter return shape')
            return fit[2], fit[4], fit[6]
        if axis != 'trial_count' or level not in COUNTS or len(trials) != level or method not in METHODS[2:]:
            raise producer().BackendProtocolError('trial condition')
        return source.fit(method, spikes, trials)


def produce(cohort, recordings, windows, backend):
    """Produce all 103,950 coordinates from complete ordered unit streams.

    Every failure retains its unit/method/condition. Missing, extra or reordered
    records and source/interface failures stop the whole call before publication.
    """
    policy()
    units, original, contract = _cohort(cohort), producer(), bridge()
    record_iterator, window_iterator = iter(recordings), iter(windows)
    rows, recording_pins, window_pins = [], [], []
    seed, expected_iterator = None, None
    for unit in units:
        try:
            recording, window = next(record_iterator), next(window_iterator)
        except StopIteration as exc:
            raise ValueError('complete recordings and windows required') from exc
        ticks = original.validate_recording(recording, unit)
        if type(window) is not dict or type(window.get('seed')) is not int:
            raise ValueError('window record seed')
        if expected_iterator is None:
            seed = window['seed']
            if seed != WINDOW_SEED:
                raise ValueError('windows do not use the frozen prospective policy seed')
            expected_iterator = iter(window_rows(cohort, seed))
        if window != next(expected_iterator):
            raise ValueError('windows differ from complete declared prospective draw')
        recording_pins.append({'unit_id': unit['unit_id'], 'sha256': digest(recording)})
        window_pins.append({'unit_id': unit['unit_id'], 'sha256': digest(window)})
        for axis, levels, methods_ in (('duration_minutes', DURATIONS, METHODS[:2]),
                                       ('trial_count', COUNTS, METHODS[2:])):
            for index, level in enumerate(levels):
                if axis == 'duration_minutes':
                    selected = ticks[:bisect.bisect_left(ticks, level * 60 * FS)]
                    trials = None
                else:
                    selected = ticks
                    trials = contract.slice_trials(ticks, window['conditions'][index]['windows_ticks'])
                for method in methods_:
                    class AtCondition:
                        def fit(self, selected_method, selected_ticks, selected_trials):
                            return backend.fit(axis, level, selected_method, selected_ticks, selected_trials)
                    row = original._fit_row(unit['unit_id'], method, AtCondition(), selected, trials)
                    row.update(axis=axis, level=level)
                    rows.append(row)
    for iterator in (record_iterator, window_iterator):
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            raise ValueError('extra input after complete cohort')
    document = {'schema': 'isttc_sensitivity_estimates_v1', 'rows': rows}
    estimate_rows(document, units)
    receipt = {'schema': 'isttc_sensitivity_production_receipt_v1',
               'cohort_sha256': digest(cohort), 'estimates_sha256': digest(document),
               'recording_pins': recording_pins, 'window_pins': window_pins,
               'window_seed': seed, 'window_scope': DRAW_SCOPE,
               'policy_sha256': POLICY_SHA, 'python_version': sys.version,
               'backend': backend.identity, 'unit_count': N_UNITS, 'fit_coordinates': len(rows),
               'native_parity_qualified': False, 'authentic_inputs_qualified': False,
               'scientifically_qualified': False, 'historical_rng_recovered': False}
    return document, receipt


def estimate_rows(document, units):
    if (type(document) is not dict or set(document) != {'schema', 'rows'} or
            document['schema'] != 'isttc_sensitivity_estimates_v1' or
            type(document['rows']) is not list or len(document['rows']) != len(units) * 18):
        raise ValueError('all eighteen sensitivity coordinates per original unit required')
    contract, identities, indexed = bridge(), {u['unit_id'] for u in units}, {}
    keys = {'unit_id', 'axis', 'level', 'method', 'tau_bins', 'r_squared', 'failure_reason'}
    for row in document['rows']:
        if type(row) is not dict or set(row) != keys:
            raise ValueError('exact sensitivity estimate fields required')
        axis, level, method = row['axis'], row['level'], row['method']
        if type(level) is not int or not ((axis == 'duration_minutes' and level in DURATIONS and method in METHODS[:2]) or
                                        (axis == 'trial_count' and level in COUNTS and method in METHODS[2:])):
            raise ValueError('unknown sensitivity condition')
        key = (row['unit_id'], axis, level, method)
        if row['unit_id'] not in identities or key in indexed:
            raise ValueError('unknown or duplicate sensitivity unit coordinate')
        tau, r2 = contract.finite(row['tau_bins'], True), contract.finite(row['r_squared'], True)
        if tau is not None:
            contract.finite(tau * 50)
        reason = row['failure_reason']
        if reason is not None and (type(reason) is not str or not reason or len(reason) > 1024):
            raise ValueError('fit failure reason')
        if ((tau is None or r2 is None) != (reason is not None)):
            raise ValueError('failure reason must identify exactly the missing fit fields')
        indexed[key] = row
    return indexed


def _error(tau, reference):
    if reference <= 0:
        return None
    # Exact rational subtraction/division prevents representable finite errors
    # from being lost to intermediate overflow, underflow or cancellation.
    try:
        value = float(abs(Fraction(tau) - Fraction(reference)) / Fraction(reference) * 100)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return float((Fraction(ordered[middle - 1]) + Fraction(ordered[middle])) / 2)


def _summary(values, denominator):
    complete = len(values) == denominator
    return {'complete_case_denominator': denominator, 'defined_count': len(values),
            'support_complete': complete,
            'median_pseudo_ree_percent': _median(values) if values and complete else None,
            'within_percent': {str(t): 100 * sum(value <= t for value in values) / denominator
                               if values and complete else None for t in (100, 75, 50, 25)}}


def _sensitivity_policy_report(cohort, estimates, reference_policy):
    """Caption-based paired support with an explicit conflicting-source policy.

    The primary complete-case mask uses finite tau estimates, including both
    30-minute reference fits. R-squared and covariates never choose this mask.
    An invalid reference keeps the denominator and suppresses affected summaries.
    """
    if reference_policy not in REFERENCE_POLICIES:
        raise ValueError('an explicit named reference policy is required')
    units = _cohort(cohort)
    indexed = estimate_rows(estimates, units)
    panels = {}
    for axis, levels, methods_ in (('duration_minutes', DURATIONS[:-1], METHODS[:2]),
                                   ('trial_count', COUNTS, METHODS[2:])):
        coordinates = [(level, method) for level in levels for method in methods_]
        records, values = [], {(level, method): [] for level, method in coordinates}
        by_mouse = {mouse: {(level, method): [] for level, method in coordinates}
                    for mouse in dict.fromkeys(u['mouse_id'] for u in units)}
        mouse_denominator = dict.fromkeys(by_mouse, 0)
        complete_count = 0
        for unit in units:
            uid = unit['unit_id']
            fits = {(level, method): indexed[(uid, axis, level, method)] for level, method in coordinates}
            references = {method: indexed[(uid, 'duration_minutes', 30, method)] for method in METHODS[:2]}
            missing = [{'level': level, 'method': method} for (level, method), fit in fits.items() if fit['tau_bins'] is None]
            missing_refs = [method for method, fit in references.items() if fit['tau_bins'] is None]
            row = {'unit_id': uid, 'mouse_id': unit['mouse_id'], 'session_id': unit['session_id'], 'area': unit['area'],
                   'status': 'missing_tau' if missing or missing_refs else 'complete_case',
                   'missing_estimates': missing, 'missing_references': missing_refs,
                   'negative_r2': [{'level': level, 'method': method} for (level, method), fit in fits.items()
                                   if fit['r_squared'] is not None and fit['r_squared'] < 0],
                   'missing_r2': [{'level': level, 'method': method} for (level, method), fit in fits.items()
                                  if fit['r_squared'] is None],
                   'errors': []}
            if not missing and not missing_refs:
                complete_count += 1
                mouse_denominator[unit['mouse_id']] += 1
                for level, method in coordinates:
                    full_method = 'isttc_full' if reference_policy == 'all_full_isttc' else (
                        'acf_full' if method in ('acf_full', 'pearsonr_trial_avg') else 'isttc_full')
                    value = _error(fits[(level, method)]['tau_bins'], references[full_method]['tau_bins'])
                    row['errors'].append({'level': level, 'method': method, 'reference_method': full_method,
                                          'pseudo_ree_percent': value,
                                          'log10_pseudo_ree_percent': math.log10(value) if value is not None and value > 0 else None})
                    if value is None:
                        row['status'] = 'undefined_reference_or_arithmetic'
                    else:
                        values[(level, method)].append(value)
                        by_mouse[unit['mouse_id']][(level, method)].append(value)
            records.append(row)
        def retention(field):
            output = []
            for value in dict.fromkeys(u[field] for u in units):
                selected_rows = [row for row in records if row[field] == value]
                output.append({field: value, 'original_units': len(selected_rows),
                               'tau_complete_case_units': sum(row['status'] != 'missing_tau' for row in selected_rows),
                               'undefined_reference_or_arithmetic_units': sum(row['status'] == 'undefined_reference_or_arithmetic'
                                                                              for row in selected_rows)})
            return output
        panels[axis] = {'original_units': len(units), 'complete_case_units': complete_count,
                        'missing_tau_units': len(units) - complete_count, 'records': records,
                        'retention_by_mouse': retention('mouse_id'), 'retention_by_area': retention('area'),
                        'unit_weighted_descriptive': [{'level': level, 'method': method,
                                                      **_summary(values[(level, method)], complete_count)}
                                                     for level, method in coordinates],
                        'mouse_stratified_descriptive': [
                            {'mouse_id': mouse, 'complete_case_units': mouse_denominator[mouse],
                             'conditions': [{'level': level, 'method': method,
                                             **_summary(by_mouse[mouse][(level, method)], mouse_denominator[mouse])}
                                            for level, method in coordinates]} for mouse in by_mouse],
                        'negative_r2_exclusion_applied': False,
                        'animal_level_inferential_test': None}
    return {'schema': 'isttc_sensitivity_diagnostics_v1', 'reference_policy': reference_policy,
            'cohort_sha256': digest(cohort), 'estimates_sha256': digest(estimates), 'panels': panels,
            'mask_policy': 'caption_common_all_levels_both_methods_both_references_tau_available_v1',
            'reported_source_counts_are_not_targets': {'duration': 5674, 'trial_count': 4588},
            'historical_source_conflict_resolved': False, 'native_parity_qualified': False,
            'scientifically_qualified': False, 'scientific_pass': None,
            'interpretation': 'Selected full-recording fits are pseudo references, not biological truth.'}


def _fit_support(units, indexed):
    original = {u['unit_id']: u for u in units}
    counts = {}
    failures = []
    for (uid, axis, level, method), row in indexed.items():
        key = (axis, level, method)
        item = counts.setdefault(key, {'axis': axis, 'level': level, 'method': method,
                                      'original_units': 0, 'tau_available_units': 0,
                                      'complete_fit_units': 0, 'missing_r2_units': 0,
                                      'negative_r2_units': 0})
        item['original_units'] += 1
        item['tau_available_units'] += row['tau_bins'] is not None
        item['complete_fit_units'] += row['tau_bins'] is not None and row['r_squared'] is not None
        item['missing_r2_units'] += row['r_squared'] is None
        item['negative_r2_units'] += row['r_squared'] is not None and row['r_squared'] < 0
        if row['failure_reason'] is not None:
            failures.append({'unit_id': uid, 'mouse_id': original[uid]['mouse_id'], 'area': original[uid]['area'],
                             'axis': axis, 'level': level, 'method': method, 'tau_bins': row['tau_bins'],
                             'r_squared': row['r_squared'], 'failure_reason': row['failure_reason']})
    return {'original_units': len(units), 'required_coordinates': len(units) * 18,
            'observed_coordinates': len(indexed), 'condition_counts': list(counts.values()),
            'failed_coordinates': failures,
            'success_is_not_source_authenticity_or_reference_competence': True}


def sensitivity_report(cohort, estimates):
    """Always report both frozen policies with inseparable support diagnostics."""
    selected_policy = policy()
    units = _cohort(cohort)
    indexed = estimate_rows(estimates, units)
    reports = {name: _sensitivity_policy_report(cohort, estimates, name) for name in REFERENCE_POLICIES}
    for axis in ('duration_minutes', 'trial_count'):
        supports = [[r['unit_id'] for r in reports[name]['panels'][axis]['records'] if r['status'] != 'missing_tau']
                    for name in REFERENCE_POLICIES]
        if supports[0] != supports[1]:
            raise ValueError('reference policies must share identical paired unit support')
    return {'schema': 'isttc_dual_policy_sensitivity_v1', 'policy_sha256': POLICY_SHA,
            'policy': selected_policy['sensitivity'],
            'primary_reference_policy': REFERENCE_POLICIES[0],
            'mandatory_diagnostic_reference_policy': REFERENCE_POLICIES[1],
            'cohort_sha256': digest(cohort), 'estimates_sha256': digest(estimates),
            'original_population_fit_support': _fit_support(units, indexed),
            'reference_policy_reports': reports,
            'stability_is_conditional_on_common_fit_success_and_realized_windows': True,
            'window_resampling_uncertainty_estimated': False,
            'historical_source_conflict_resolved': False, 'scientifically_qualified': False,
            'scientific_pass': None}


def figure7c_estimates(cohort, sensitivity_estimates):
    """Select exactly the two 30-minute and two 40-trial coordinates per unit.

    All eighteen original coordinates are validated before this selection. This
    structural projection does not authenticate the estimates or their windows.
    """
    units = _cohort(cohort)
    indexed = estimate_rows(sensitivity_estimates, units)
    rows = []
    for unit in units:
        for method in METHODS:
            axis, level = ('duration_minutes', 30) if method in METHODS[:2] else ('trial_count', 40)
            row = indexed[(unit['unit_id'], axis, level, method)]
            rows.append({key: row[key] for key in ('unit_id', 'method', 'tau_bins', 'r_squared', 'failure_reason')})
    return {'schema': 'isttc_empirical_estimates_v1', 'rows': rows}


def figure7c(cohort, estimates, *, bootstrap_seed, bootstrap_repetitions):
    """Complete-source Figure 7C fixed effects plus prospective mouse intervals."""
    if type(bootstrap_seed) is not int or not 0 <= bootstrap_seed < 2**64:
        raise ValueError('bootstrap seed must be uint64')
    if type(bootstrap_repetitions) is not int or not 2 <= bootstrap_repetitions <= 10000:
        raise ValueError('bootstrap repetitions must be an integer from 2 through 10000')
    if bootstrap_seed != BOOTSTRAP_SEED or bootstrap_repetitions != BOOTSTRAP_REPETITIONS:
        raise ValueError('Figure 7C wrapper requires the frozen prospective bootstrap policy')
    selected_policy = policy()
    supplied_estimates_sha = digest(estimates)
    input_schema = estimates.get('schema') if type(estimates) is dict else None
    if input_schema == 'isttc_sensitivity_estimates_v1':
        estimates = figure7c_estimates(cohort, estimates)
    units, contract = _cohort(cohort), bridge()
    indexed = contract.estimate_rows(estimates, units)
    reduction = contract.reduce_rows(units, indexed)
    admitted = [u for u, row in zip(units, reduction['records'])
                if row['status'] in ('complete_case', 'undefined_reference')]
    results = {}
    arithmetic = models()
    for panel, methods_ in (('log10_tau_ms', METHODS), ('log10_pseudo_ree_percent', METHODS[2:])):
        responses, invalid = [], []
        for unit in admitted:
            uid = unit['unit_id']
            current = []
            for method in methods_:
                tau = indexed[(uid, method)]['tau_bins']
                if panel == 'log10_tau_ms':
                    value = tau * 50
                else:
                    reference = indexed[(uid, 'acf_full' if method == METHODS[2] else 'isttc_full')]['tau_bins']
                    value = _error(tau, reference)
                if value is None or value <= 0 or not math.isfinite(value):
                    invalid.append({'unit_id': uid, 'method': method, 'reason': 'undefined_or_nonpositive_log_argument'})
                    current.append(None)
                else:
                    current.append(math.log10(value))
            responses.append(current)
        if invalid:
            results[panel] = {'status': 'unavailable', 'reason': 'source_log_domain_unresolved',
                              'invalid_coordinates': invalid, 'unit_count': len(admitted),
                              'fixed_effects': None, 'mouse_bootstrap': None}
            continue
        covariates = [[u['fr_hz'], u['lv']] for u in admitted]
        mice = [u['mouse_id'] for u in admitted]
        try:
            fitted = arithmetic.balanced_reml(responses, covariates, mice, methods_)
            uncertainty = arithmetic.mouse_bootstrap(responses, covariates, mice, methods_,
                                                     seed=bootstrap_seed, repetitions=bootstrap_repetitions)
        except ValueError as exc:
            results[panel] = {'status': 'unavailable', 'reason': 'model_design_or_arithmetic: ' + str(exc),
                              'unit_count': len(admitted), 'fixed_effects': None, 'mouse_bootstrap': None}
        else:
            results[panel] = {'status': 'available' if fitted['finite_nonsingular_gaussian_fit'] else 'point_estimates_only',
                              'unit_count': len(admitted),
                              'fixed_effects': fitted, 'mouse_bootstrap': uncertainty}
    return {'schema': 'isttc_fig7c_models_v1', 'cohort_sha256': digest(cohort),
            'estimates_sha256': digest(estimates), 'source_reduction': reduction,
            'supplied_estimates_sha256': supplied_estimates_sha, 'supplied_estimates_schema': input_schema,
            'model_unit_ids': [u['unit_id'] for u in admitted], 'models': results,
            'policy_sha256': POLICY_SHA,
            'prospective_animal_uncertainty_policy': selected_policy['prospective_animal_uncertainty'],
            'retention_by_mouse': [{'mouse_id': mouse,
                                    'original_units': sum(u['mouse_id'] == mouse for u in units),
                                    'retained_model_units': sum(u['mouse_id'] == mouse for u in admitted)}
                                   for mouse in dict.fromkeys(u['mouse_id'] for u in units)],
            'retention_by_area': [{'area': area,
                                   'original_units': sum(u['area'] == area for u in units),
                                   'retained_model_units': sum(u['area'] == area for u in admitted)}
                                  for area in dict.fromkeys(u['area'] for u in units)],
            'scientifically_qualified': False, 'historical_lmerTest_p_values_reproduced': False,
            'native_lme4_parity_qualified': False, 'scientific_pass': None}


def read_document(path, cap):
    with Path(path).open('rb') as stream:
        body = stream.read(cap + 1)
    if len(body) > cap:
        raise ValueError('input exceeds declared logical byte cap')
    return strict_json(body)


def json_lines(path, cap):
    with Path(path).open('rb') as stream:
        while True:
            line = stream.readline(cap + 1)
            if not line:
                return
            if len(line) > cap:
                raise ValueError('JSONL record exceeds declared logical byte cap')
            yield strict_json(line)


def write_document(path, document, cap=FIT_CAP):
    body = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'
    if len(body) > cap:
        raise ValueError('output exceeds declared logical byte cap')
    with Path(path).open('xb') as output:
        output.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('windows', 'produce', 'sensitivity', 'figure7c'))
    parser.add_argument('--cohort', required=True)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--recordings-jsonl')
    parser.add_argument('--windows-jsonl')
    parser.add_argument('--author-checkout')
    parser.add_argument('--estimates')
    parser.add_argument('--bootstrap-repetitions', type=int)
    parser.add_argument('--output-directory', required=True)
    args = parser.parse_args()
    policy()
    directory = Path(args.output_directory)
    if directory.exists() or directory.is_symlink():
        raise ValueError('output directory must be absent')
    cohort = read_document(args.cohort, METADATA_CAP)
    _cohort(cohort)
    if args.operation == 'windows':
        selected_seed = WINDOW_SEED if args.seed is None else args.seed
        if selected_seed != WINDOW_SEED:
            raise ValueError('windows command requires the frozen prospective policy seed')
        iterator = iter(window_rows(cohort, selected_seed))
        first = next(iterator)  # Validate seed before creating output.
        directory.mkdir()
        output_digest, written, count = hashlib.sha256(), 0, 0
        with (directory / 'windows.jsonl').open('xb') as stream:
            for row in (first,):
                body = json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                stream.write(body); output_digest.update(body); written += len(body); count += 1
            for row in iterator:
                body = json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                if written + len(body) > FIT_CAP:
                    raise ValueError('window output cap exceeded')
                stream.write(body); output_digest.update(body); written += len(body); count += 1
        write_document(directory / 'receipt.json', {'schema': 'isttc_sensitivity_window_receipt_v1',
                       'cohort_sha256': digest(cohort), 'seed': selected_seed, 'unit_count': count,
                       'sha256': output_digest.hexdigest(), 'bytes': written, 'scope': DRAW_SCOPE,
                       'policy_sha256': POLICY_SHA, 'python_version': sys.version,
                       'historical_rng_recovered': False, 'scientifically_qualified': False})
    elif args.operation == 'produce':
        if not all((args.recordings_jsonl, args.windows_jsonl, args.author_checkout)):
            raise ValueError('recordings, windows and exact author checkout required')
        result, receipt = produce(cohort, json_lines(args.recordings_jsonl, RECORD_CAP),
                                  json_lines(args.windows_jsonl, WINDOW_CAP), AuthorSensitivityBackend(args.author_checkout))
        directory.mkdir()
        write_document(directory / 'estimates.json', result)
        write_document(directory / 'receipt.json', receipt)
    else:
        if args.estimates is None:
            raise ValueError('--estimates required')
        estimates = read_document(args.estimates, FIT_CAP)
        if args.operation == 'sensitivity':
            result = sensitivity_report(cohort, estimates)
        else:
            result = figure7c(cohort, estimates,
                              bootstrap_seed=BOOTSTRAP_SEED if args.seed is None else args.seed,
                              bootstrap_repetitions=BOOTSTRAP_REPETITIONS if args.bootstrap_repetitions is None
                              else args.bootstrap_repetitions)
        directory.mkdir()
        write_document(directory / 'report.json', result)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TypeError, OverflowError, RecursionError, OSError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
