"""Private NEURAL-024 scoring using the two already-qualified reference functions.

The controller supplies only the 22,090 scored rows after validating the full
causal transcript. A batch array is not evidence of causal candidate access.
Malformed references/support raise ValueError as INTERNAL trusted-input contract
failures, never as a conclusion that a candidate submitted invalid predictions.
Arithmetic overflow/nonfinite aggregates instead return numerical_failure, with
no clipped or partial score. Deadline exceptions propagate to the controller.
"""
import math


ARMS = ('source_rate', 'calibration_rate', 'self_history_frozen',
        'self_history_adapted', 'self_population_history_frozen',
        'self_population_history_adapted')
SHAPE = (22090, 96)
ATOL = 1e-9
RTOL = 1e-12
PARITY_AGGREGATE_FIELDS = ('rows', 'channels', 'cells', 'spikes', 'log_likelihood', 'mean_nll')
PARITY_CHANNEL_FIELDS = ('channel_index', 'spikes', 'log_likelihood', 'mean_nll')
PARITY_CANDIDATE_CHANNEL_ENRICHMENT = ('log_likelihood_gain_vs_calibration_rate',
                                     'bits_per_spike_vs_calibration_rate',
                                     'bits_per_spike_undefined_reason')
PARITY_REFERENCE_AGGREGATE_ENRICHMENT = ('prediction_sha256_float64_C',
                                       'log_likelihood_gain_vs_calibration_rate',
                                       'bits_per_spike_vs_calibration_rate',
                                       'bits_per_spike_undefined_reason')


def _need(condition, message):
    if not condition:
        raise ValueError('Internal scoring contract: ' + message)


def _finite(value, name):
    _need(type(value) in (int, float) and math.isfinite(value), 'finite ' + name)
    return float(value)


def _close(actual, expected, name):
    actual = _finite(actual, name)
    _need(math.isfinite(expected), 'finite independently reconciled ' + name)
    _need(abs(actual - expected) <= ATOL + RTOL * max(abs(actual), abs(expected)), name + ' reconciles')


def _validate_record(record, shape, observed_by_channel, name):
    rows, channels = shape
    _need(type(record) is dict, name + ' is a score record')
    for key, expected in (('rows', rows), ('channels', channels), ('cells', rows * channels),
                          ('spikes', sum(observed_by_channel))):
        _need(type(record[key]) is int and record[key] == expected, name + ': exact ' + key)
    _need(type(record['per_channel']) is list and len(record['per_channel']) == channels,
          name + ': complete channel roster')
    channel_ll = []
    for index, item in enumerate(record['per_channel']):
        _need(type(item) is dict and type(item['channel_index']) is int and item['channel_index'] == index,
              name + ': fixed channel identity/order')
        _need(type(item['spikes']) is int and item['spikes'] == observed_by_channel[index],
              name + ': exact observed count on every channel')
        ll = _finite(item['log_likelihood'], name + ' per-channel log likelihood')
        _need(ll <= 0.0, name + ': nonpositive full Poisson log likelihood')
        _close(item['mean_nll'], -ll / rows, name + ' per-channel mean NLL')
        channel_ll.append(ll)
    total = math.fsum(channel_ll)
    _close(record['log_likelihood'], total, name + ' summed full log likelihood')
    _close(record['mean_nll'], -total / (rows * channels), name + ' all-cell mean NLL')


def _references(references, shape, observed_by_channel):
    _need(type(references) is dict and references.get('status') == 'complete_fixed_development_panel',
          'completed sealed reference panel')
    arms = references.get('arms')
    _need(type(arms) is dict and set(arms) == set(ARMS), 'all six exact reference arm identities')
    for name in ARMS:
        _validate_record(arms[name], shape, observed_by_channel, 'reference ' + name)
    return arms


def _numeric_finite(value, message):
    if not math.isfinite(value):
        raise ArithmeticError(message)
    return value


def _difference(candidate, reference, observed):
    gain = _numeric_finite(candidate['log_likelihood'] - reference['log_likelihood'],
                           'Nonfinite signed likelihood contrast')
    nll_reduction = _numeric_finite(reference['mean_nll'] - candidate['mean_nll'],
                                    'Nonfinite signed mean NLL contrast')
    bps = None if observed == 0 else _numeric_finite(gain / (observed * math.log(2.)),
                                                    'Nonfinite bits-per-spike contrast')
    return {'log_likelihood_gain': gain, 'mean_nll_reduction': nll_reduction,
            'bits_per_spike_gain': bps,
            'bits_per_spike_undefined_reason': 'zero_observed_query_spikes' if observed == 0 else None}


def _calibration_parity(candidate, reference, comparison):
    """Report exact control parity without imposing an ordinary accuracy floor."""
    aggregate_keys = set(PARITY_AGGREGATE_FIELDS) | {'per_channel'}
    schema_matches = (set(candidate) == aggregate_keys
        and set(reference) - set(PARITY_REFERENCE_AGGREGATE_ENRICHMENT) == aggregate_keys)
    pairs = [(candidate[key], reference[key]) for key in PARITY_AGGREGATE_FIELDS]
    for actual, expected in zip(candidate['per_channel'], reference['per_channel']):
        schema_matches = (schema_matches
            and set(actual) - set(PARITY_CANDIDATE_CHANNEL_ENRICHMENT) == set(PARITY_CHANNEL_FIELDS)
            and set(expected) == set(PARITY_CHANNEL_FIELDS))
        pairs.extend((actual[key], expected[key]) for key in PARITY_CHANNEL_FIELDS)
    maximum = max(abs(float(actual) - float(expected)) for actual, expected in pairs)
    _numeric_finite(maximum, 'Nonfinite calibration-control parity difference')
    return {'exact_parity': schema_matches and all(actual == expected for actual, expected in pairs),
            'zero_primary_gain': comparison['log_likelihood_gain'] == 0.0
                                 and comparison['bits_per_spike_gain'] == 0.0,
            'base_field_schema_matches': schema_matches,
            'fields_compared': {'aggregate': list(PARITY_AGGREGATE_FIELDS),
                                'every_channel': list(PARITY_CHANNEL_FIELDS)},
            'channels_compared': len(candidate['per_channel']), 'scalar_fields_compared': len(pairs),
            'maximum_absolute_scalar_difference': maximum,
            'excluded_candidate_channel_enrichment': list(PARITY_CANDIDATE_CHANNEL_ENRICHMENT),
            'excluded_reference_aggregate_enrichment': list(PARITY_REFERENCE_AGGREGATE_ENRICHMENT),
            'required_for_ordinary_candidate_scoring': False}


def _score(y, means, references, expected_shape, tick=None):
    """Private small-shape seam is for future invented qualification controls."""
    import numpy as np
    import reference_model_core
    import reference_audit

    if tick is not None:
        tick()
    _need(type(expected_shape) is tuple and len(expected_shape) == 2
          and all(type(v) is int and v > 0 for v in expected_shape), 'explicit scoring dimensions')
    _need(type(y) is np.ndarray and y.dtype == np.dtype('int64') and y.shape == expected_shape,
          'complete int64 scored targets')
    _need(bool((y >= 0).all()) and bool((y <= 4294967295).all()), 'native nonnegative uint32-range counts')
    _need(type(means) is np.ndarray and means.dtype == np.dtype('float64') and means.shape == expected_shape
          and bool(np.isfinite(means).all()) and bool((means > 0.).all()),
          'complete strictly positive finite float64 committed means')
    # The source representation bounds keep these integral totals far below
    # int64 overflow. No fixed observed count is hardcoded into this scorer.
    observed_by_channel = [int(v) for v in np.sum(y, axis=0, dtype=np.int64)]
    observed = sum(observed_by_channel)
    arms = _references(references, expected_shape, observed_by_channel)
    counters = {}
    phase = 'qualified_primary_poisson_score'
    try:
        if tick is not None:
            tick()
        with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
            candidate = reference_model_core.score(y, means)
        for value in [candidate['log_likelihood'], candidate['mean_nll']] + [
                item[key] for item in candidate['per_channel'] for key in ('log_likelihood', 'mean_nll')]:
            _numeric_finite(float(value), 'Nonfinite primary score aggregate')
        _validate_record(candidate, expected_shape, observed_by_channel, 'candidate numerical result')
        phase = 'qualified_independent_scalar_audit'
        checked = reference_audit.audit_score(y, means, candidate, tick=tick, counters=counters)
        phase = 'all_six_fixed_reference_contrasts'
        comparisons = {name: _difference(candidate, arms[name], observed) for name in ARMS}
        # Retain zero-count channels and their signed likelihood contribution;
        # their per-channel BPS denominator is undefined, never silently omitted.
        candidate = dict(candidate)
        candidate['per_channel'] = [dict(item) for item in candidate['per_channel']]
        for index, item in enumerate(candidate['per_channel']):
            if tick is not None:
                tick()
            primary = _difference(item, arms['calibration_rate']['per_channel'][index], item['spikes'])
            item.update(log_likelihood_gain_vs_calibration_rate=primary['log_likelihood_gain'],
                        bits_per_spike_vs_calibration_rate=primary['bits_per_spike_gain'],
                        bits_per_spike_undefined_reason=primary['bits_per_spike_undefined_reason'])
        compact_audit = {key: checked[key] for key in (
            'status', 'rows', 'channels', 'cells', 'spikes', 'independent_log_likelihood',
            'independent_mean_nll', 'maximum_absolute_difference', 'comparison_atol', 'comparison_rtol')}
        compact_audit['counters'] = counters
        control = _calibration_parity(candidate, arms['calibration_rate'], comparisons['calibration_rate'])
        return {'status': 'candidate_poisson_score_completed', 'candidate_score': candidate,
                'independent_audit': compact_audit, 'comparisons': comparisons,
                'calibration_rate_control': control,
                'primary_reference': 'calibration_rate',
                'bits_per_spike_vs_calibration_rate': comparisons['calibration_rate']['bits_per_spike_gain'],
                'bits_per_spike_undefined_reason': comparisons['calibration_rate']['bits_per_spike_undefined_reason'],
                'support': {'rows': expected_shape[0], 'channels': expected_shape[1],
                            'cells': y.size, 'observed_spikes': observed, 'reference_arms_verified': len(ARMS)},
                'causal_qualification_inferred_from_batch_arrays': False,
                'new_model_fits': 0}
    except (ArithmeticError, FloatingPointError, OverflowError) as exc:
        return {'status': 'numerical_failure', 'phase': phase,
                'error_type': type(exc).__name__, 'error': str(exc)[:1000],
                'candidate_score': None, 'comparisons': None,
                'independent_audit_counters': counters, 'score_clipped_or_floored': False,
                'causal_qualification_inferred_from_batch_arrays': False, 'new_model_fits': 0}


def score(y_int64, means_float64, references, tick=None):
    return _score(y_int64, means_float64, references, SHAPE, tick=tick)
