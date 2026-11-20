"""Small independent scalar co-bps oracle for generated float64 controls.

This is test code, never a replacement evaluator. Compare it with the exact
retained bits_per_spike/neg_log_likelihood functions on disposable float64
arrays. Canonical NLL mutates zero rates; this scalar oracle never mutates inputs.
No original neural data or candidate implementation is embedded here.
"""
import math

EVALUATOR_SOURCE = {
    'bytes': 18292,
    'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476',
}
ORDERED_GAIN_RATIONALS = (
    (1, 1), (8, 9), (9, 8), (4, 5), (5, 4),
    (2, 3), (3, 2), (1, 2), (2, 1),
)


def _shape(values):
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError('Nonempty nested trial/time/neuron fixture required')
    times = len(values[0])
    neurons = len(values[0][0]) if times else 0
    if not times or not neurons:
        raise ValueError('Nonempty time and neuron dimensions required')
    for trial in values:
        if not isinstance(trial, (tuple, list)) or len(trial) != times:
            raise ValueError('Rectangular time dimension required')
        for row in trial:
            if not isinstance(row, (tuple, list)) or len(row) != neurons:
                raise ValueError('Rectangular neuron dimension required')
    return len(values), times, neurons


def oracle_bits_per_spike(rates, spikes):
    """Scalar Poisson likelihood versus per-neuron observed-target mean.

    Scope: generated rectangular 3-D float64-compatible inputs, nonnegative
    finite observed counts/rates, optional NaN spike targets, positive observed
    spike mass. A target NaN removes that entry before model-rate validation,
    matching the canonical mask. A completely missing neuron contributes no
    likelihood terms. Zero observed rates and zero null means use 1e-9.

    The independent math.fsum/math.lgamma implementation can differ by normal
    floating-point rounding from NumPy/scipy; compare with a declared numerical
    tolerance, never use that tolerance to change the exact gain tie policy.
    """
    shape = _shape(spikes)
    if _shape(rates) != shape:
        raise ValueError('Identical trial/time/neuron shapes required')
    trials, times, neurons = shape
    observed = [[] for _ in range(neurons)]
    observations = []
    for trial in range(trials):
        for time in range(times):
            for neuron in range(neurons):
                count = float(spikes[trial][time][neuron])
                if math.isnan(count):
                    continue
                rate = float(rates[trial][time][neuron])
                if not math.isfinite(count) or count < 0:
                    raise ValueError('Finite nonnegative observed fixture counts required')
                if not math.isfinite(rate) or rate < 0:
                    raise ValueError('Finite nonnegative observed fixture rates required')
                observed[neuron].append(count)
                observations.append((neuron, rate, count))
    mass = math.fsum(count for _, _, count in observations)
    if mass <= 0:
        raise ValueError('Positive observed spike mass required; canonical zero denominator is undefined')
    means = [math.fsum(column) / len(column) if column else math.nan for column in observed]
    model_terms, null_terms = [], []
    for neuron, rate, count in observations:
        model_rate = 1e-9 if rate == 0 else rate
        null_rate = 1e-9 if means[neuron] == 0 else means[neuron]
        factorial = math.lgamma(count + 1.0)
        model_terms.append(model_rate - count * math.log(model_rate) + factorial)
        null_terms.append(null_rate - count * math.log(null_rate) + factorial)
    result = (math.fsum(null_terms) - math.fsum(model_terms)) / mass / math.log(2.0)
    if not math.isfinite(result):
        raise ValueError('Finite fixture co-bps required')
    return result


def fixture_cases():
    """Fresh tiny cases: positive rates, zero rates/null neuron, missing targets."""
    return (
        {
            'name': 'finite_positive',
            'rates': [[[0.25, 0.75], [1.5, 0.3]], [[0.8, 2.5], [2.75, 1.2]]],
            'spikes': [[[0.0, 1.0], [2.0, 0.0]], [[1.0, 3.0], [3.0, 1.0]]],
        },
        {
            'name': 'zero_rates_and_zero_null_neuron',
            'rates': [[[0.0, 0.0], [0.0, 0.2]], [[0.5, 0.0], [0.0, 0.0]]],
            'spikes': [[[0.0, 0.0], [1.0, 0.0]], [[2.0, 0.0], [0.0, 0.0]]],
        },
        {
            'name': 'masked_targets_keep_per_neuron_mean',
            'rates': [[[9.0, 0.25], [1.5, 1.0]], [[0.75, 8.0], [0.2, 1.75]]],
            'spikes': [[[math.nan, 0.0], [2.0, 1.0]], [[1.0, math.nan], [0.0, 2.0]]],
        },
    )


def nonidentity_grid_case():
    """The unique positive gain optimum is 2; the fixed grid includes it last.

    Four unit rates and total observed spike count8 yield derivative 8/g - 4
    and negative second derivative -8/g**2. Thus gain2 is the unique maximum.
    At gain2 all model rates equal the per-neuron null mean, so co-bps is0.
    The future campaign must still compute all nine actual canonical scores.
    """
    return {
        'name': 'unit_rates_need_gain_two',
        'rates': [[[1.0], [1.0]], [[1.0], [1.0]]],
        'spikes': [[[1.0], [3.0]], [[2.0], [2.0]]],
        'expected_winner_index': 8,
        'expected_gain_rational': (2, 1),
        'expected_winner_cobps': 0.0,
    }


def positive_gain_delta_oracle(rates, spikes, executed_gain):
    """Independent positive-rate co-bps change: [Y log(g)-(g-1)R]/[Y log2].

    Use the actual executed gain converted to Python float, not an ideal rational.
    This formula applies only to positive finite observed rates/count-domain
    inputs without missing targets, clipping, underflow, or extra product
    rounding. The binary-power fixture below avoids additional float32 product
    rounding for the finite normal gains in the declared grid.
    """
    shape = _shape(rates)
    if _shape(spikes) != shape:
        raise ValueError('Identical gain-delta fixture shapes required')
    gain = float(executed_gain)
    if not math.isfinite(gain) or gain <= 0:
        raise ValueError('Executed gain must be finite and positive')
    predicted, observed = [], []
    for trial in range(shape[0]):
        for time in range(shape[1]):
            for neuron in range(shape[2]):
                rate = float(rates[trial][time][neuron])
                count = float(spikes[trial][time][neuron])
                if not math.isfinite(rate) or rate <= 0:
                    raise ValueError('Delta identity requires strictly positive finite rates')
                if not math.isfinite(count) or count < 0:
                    raise ValueError('Delta identity requires finite nonnegative counts')
                predicted.append(rate)
                observed.append(count)
    total_rate, total_spikes = math.fsum(predicted), math.fsum(observed)
    if total_spikes <= 0:
        raise ValueError('Positive observed spike mass required')
    return (total_spikes * math.log(gain) - (gain - 1.0) * total_rate) / total_spikes / math.log(2.0)


def binary_power_grid_case():
    """Normal binary powers make scalar multiplication exact beyond gain rounding.

    Rates sum to7.5 and spike counts to15, so the unique positive global gain
    optimum is2. Supply each actually executed float32/float64 gain to the delta
    oracle. The future campaign, not this source helper, computes the scores.
    """
    return {
        'name': 'binary_power_rates_need_gain_two',
        'rates': [[[0.5], [1.0]], [[2.0], [4.0]]],
        'spikes': [[[1.0], [2.0]], [[4.0], [8.0]]],
        'expected_winner_index': 8,
        'expected_gain_rational': (2, 1),
    }


def zero_rate_identity_tie_case():
    """Canonical metric tie only; candidate zero-rate admission is a separate guard.

    Every finite positive grid gain leaves the all-zero model rates unchanged.
    Original NLL then replaces the same zeros with1e-9, so all canonical scores
    are exactly equal for fresh same-dtype inputs. Earliest fixed-grid index0 is
    identity. Never reuse the canonical metric's mutated zero-rate input array.
    """
    return {
        'name': 'canonical_all_zero_rates_exact_tie',
        'rates': [[[0.0], [0.0]], [[0.0], [0.0]]],
        'spikes': [[[1.0], [2.0]], [[3.0], [4.0]]],
        'expected_winner_index': 0,
        'expected_gain_rational': (1, 1),
        'candidate_zero_rate_admission_assumed': False,
    }
