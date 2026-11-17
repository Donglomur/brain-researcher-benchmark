"""Independent RTT forecast arithmetic; functions run only in a qualified worker.

The primary model uses a joint three-dimensional objective. This audit assembles
one channel's matrix at a time and uses independent dot products/reductions.
Only invented fixtures use the fully scalar objective and derivative routine.
No primary model, scoring, or feature-construction function is imported here.
"""
import math


FULL_GRADIENT_LIMIT = 1e-6
LAMBDA_GRID = (0.01, 0.1, 1.0)
COMPARISON_RTOL = 1e-10
SCORE_ATOL = 1e-9
SCORE_RTOL = 1e-12
COUNTER_KEYS = (
    'fit_audits_attempted', 'fit_audits_completed',
    'fit_channels_completed', 'fit_feature_cells_checked',
    'fit_gradient_coordinates_checked', 'fit_target_cells_checked',
    'prediction_audits_attempted', 'prediction_audits_completed',
    'prediction_channels_completed', 'prediction_feature_cells_checked',
    'prediction_rates_checked', 'gain_audits_attempted', 'gain_audits_completed',
    'gain_channels_checked', 'rate_audits_attempted', 'rate_audits_completed',
    'rate_channels_checked', 'score_audits_attempted', 'score_audits_completed',
    'score_cells_checked', 'score_channels_completed',
    'scalar_equations_attempted', 'scalar_equations_completed',
    'scalar_equation_cells_checked', 'scalar_gradient_coordinates_checked',
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _tick(tick):
    if tick is not None:
        tick()


def _counters(counters):
    if counters is None:
        counters = {}
    need(type(counters) is dict, 'Mutable independent audit counters')
    for key in COUNTER_KEYS:
        counters.setdefault(key, 0)
        need(type(counters[key]) is int and counters[key] >= 0,
             'Nonnegative integer audit counter: ' + key)
    return counters


def _finite(value, name):
    need(not isinstance(value, (bool, str, bytes)), 'Numeric scalar ' + name)
    value = float(value)
    need(math.isfinite(value), 'Finite scalar ' + name)
    return value


def _compare(actual, expected, name, score=False, positive_scale=False):
    actual, expected = _finite(actual, name), _finite(expected, 'independent ' + name)
    if positive_scale:
        need(actual > 0.0 and expected > 0.0, 'Positive nonconstant population scale')
        tolerance = COMPARISON_RTOL * abs(expected)
    elif score:
        tolerance = SCORE_ATOL + SCORE_RTOL * max(abs(actual), abs(expected))
    else:
        tolerance = COMPARISON_RTOL * max(1.0, abs(actual), abs(expected))
    difference = abs(actual - expected)
    need(difference <= tolerance, 'Independent agreement: ' + name)
    return difference


def _raw(np, raw):
    need(type(raw) is np.ndarray and raw.dtype == np.dtype('float64') and raw.ndim == 3,
         'Explicit float64 rows-by-channel-by-feature matrix')
    n, channels, width = raw.shape
    need(0 < n <= 25100 and 0 < channels <= 96 and 0 < width <= 20,
         'Bounded complete forecast matrix')
    need(bool(np.isfinite(raw).all()), 'Finite raw transformed-count features')
    return n, channels, width


def _targets(np, y, shape):
    need(type(y) is np.ndarray and y.dtype == np.dtype('int64') and y.shape == shape,
         'Exact int64 target count shape')
    need(bool((y >= 0).all()) and bool((y <= 4294967295).all()),
         'Nonnegative counts inside frozen uint32 source representation')


def _means(np, means, shape):
    need(type(means) is np.ndarray and means.dtype == np.dtype('float64') and means.shape == shape,
         'Exact float64 predicted count-rate shape')
    need(bool(np.isfinite(means).all()) and bool((means > 0.0).all()),
         'Strictly positive finite predicted means without clipping')


def _model(np, model, channels, width):
    alpha = np.asarray(model['alpha'], dtype=np.float64)
    beta = np.asarray(model['beta'], dtype=np.float64)
    mean = np.asarray(model['scaler']['mean'], dtype=np.float64)
    scale = np.asarray(model['scaler']['scale'], dtype=np.float64)
    mask_source = model['scaler']['constant']
    need(len(mask_source) == channels and all(len(row) == width for row in mask_source)
         and all(type(v) is bool for row in mask_source for v in row),
         'Exact boolean constant-column schema')
    constant = np.asarray(mask_source, dtype=np.bool_)
    need(alpha.shape == (channels,) and all(v.shape == (channels, width) for v in (beta, mean, scale, constant)),
         'Full channel and coefficient/scaler schema')
    need(all(bool(np.isfinite(v).all()) for v in (alpha, beta, mean, scale)),
         'Finite committed model and scaler values')
    need(bool((scale[constant] == 1.0).all()) and bool((scale[~constant] > 0.0).all())
         and bool((beta[constant] == 0.0).all()), 'Exact inactive unit divisors and zero coefficients')
    lam = _finite(model['lambda'], 'positive ridge lambda')
    need(lam > 0.0, 'Positive ridge penalty')
    return alpha, beta, mean, scale, constant, lam


def _channel(np, raw, channel, mean, scale, constant):
    # One independent channel matrix; no primary transform or 3D einsum.
    source = raw[:, channel, :]
    transformed = np.zeros(source.shape, dtype=np.float64)
    active = ~constant[channel]
    transformed[:, active] = (source[:, active] - mean[channel, active]) / scale[channel, active]
    need(bool(np.isfinite(transformed).all()), 'Finite independently standardized channel matrix')
    return source, transformed


def audit_fit(raw, y, model, tick=None, counters=None):
    """Audit all fit cells and full per-channel gradients of the summed objective."""
    import numpy as np
    counters = _counters(counters)
    counters['fit_audits_attempted'] += 1
    _tick(tick)
    n, channels, width = _raw(np, raw)
    _targets(np, y, (n, channels))
    for key, expected in (('n_fit', n), ('channels', channels),
                          ('features_per_channel', width),
                          ('parameter_coordinates', channels * (width + 1))):
        need(type(model[key]) is int and model[key] == expected,
             'Exact integral saved fitting metadata: ' + key)
    need(_finite(model['lambda'], 'saved fixed-grid lambda') in LAMBDA_GRID,
         'Saved regularization belongs to the frozen three-point grid')
    alpha, beta, mean, scale, constant, lam = _model(np, model, channels, width)
    channel_objectives, gradients, channel_gradient_max = [], [], []
    mean_difference = scale_difference = 0.0
    for channel in range(channels):
        _tick(tick)
        source = raw[:, channel, :]
        expected_constant = np.equal(source, source[0]).all(axis=0)
        need(bool(np.array_equal(expected_constant, constant[channel])),
             'Exact fitting constants detected before floating reductions')
        expected_mean = np.sum(source, axis=0, dtype=np.float64) / n
        expected_mean[expected_constant] = source[0, expected_constant]
        for j in range(width):
            mean_difference = max(mean_difference,
                _compare(mean[channel, j], expected_mean[j], 'fitting-only feature mean'))
            if expected_constant[j]:
                need(mean[channel, j] == source[0, j], 'Constant feature retains its exact repeated value')
        # RMS is independently reduced around the verified saved mean. This
        # avoids changing the primary floating centering convention by an ulp.
        centered = source - mean[channel]
        independent_scale = np.linalg.norm(centered, axis=0) / math.sqrt(n)
        for j in range(width):
            if not expected_constant[j]:
                scale_difference = max(scale_difference,
                    _compare(scale[channel, j], independent_scale[j], 'fitting population scale', positive_scale=True))
        unused, x = _channel(np, raw, channel, mean, scale, constant)
        eta = np.dot(x, beta[channel]) + alpha[channel]
        with np.errstate(over='raise', invalid='raise', under='ignore'):
            mu = np.exp(eta)
            intercept_rate = float(np.exp(alpha[channel]))
        need(bool(np.isfinite(eta).all()) and bool(np.isfinite(mu).all()) and bool((mu > 0.0).all())
             and math.isfinite(intercept_rate) and intercept_rate > 0.0,
             'Finite positive independently evaluated fit means and baseline intensity')
        target = y[:, channel].astype(np.float64)
        residual = mu - target
        objective = math.fsum((float(np.sum(mu - target * eta, dtype=np.float64)) / n,
                              (0.5 * intercept_rate - 0.5 * float(alpha[channel])) / n,
                              0.5 * lam * float(np.dot(beta[channel], beta[channel]))))
        intercept_gradient = (float(np.sum(residual, dtype=np.float64))
                              + 0.5 * intercept_rate - 0.5) / n
        slopes = np.dot(x.T, residual) / n + lam * beta[channel]
        gradient = [intercept_gradient] + slopes.tolist()
        need(math.isfinite(objective) and all(math.isfinite(v) for v in gradient),
             'Finite full independent per-channel objective and gradient')
        maximum = max(abs(value) for value in gradient)
        channel_objectives.append(objective)
        gradients.append(gradient)
        channel_gradient_max.append(maximum)
        counters['fit_feature_cells_checked'] += n * width
        counters['fit_target_cells_checked'] += n
        counters['fit_gradient_coordinates_checked'] += width + 1
        counters['fit_channels_completed'] += 1
    objective = math.fsum(channel_objectives)
    gradient_max = max(channel_gradient_max)
    objective_difference = _compare(model['objective'], objective, 'SUM of per-channel mean objectives')
    gradient_difference = _compare(model['gradient_max_abs'], gradient_max, 'full unaveraged gradient infinity norm')
    need(gradient_max <= FULL_GRADIENT_LIMIT,
         'Every channel/intercept/slope derivative <=1e-6, without division by96')
    counters['fit_audits_completed'] += 1
    return {'status': 'independent_channel_fit_audit_passed', 'rows': n, 'channels': channels,
            'features_per_channel': width, 'feature_cells_checked': n * channels * width,
            'gradient_coordinates_checked': channels * (width + 1),
            'independent_objective': objective, 'objective_absolute_difference': objective_difference,
            'independent_gradient_max_abs': gradient_max,
            'gradient_max_abs_absolute_difference': gradient_difference,
            'independent_gradient': gradients, 'per_channel_objective': channel_objectives,
            'per_channel_gradient_max_abs': channel_gradient_max,
            'maximum_mean_difference': mean_difference, 'maximum_scale_difference': scale_difference,
            'full_gradient_limit': FULL_GRADIENT_LIMIT, 'objective_gap_certificate': False,
            'joint_objective_reduction': 'sum_of_channel_mean_objectives',
            'comparison_rtol_times_max_one': COMPARISON_RTOL,
            'scale_comparison_has_no_absolute_floor': True}


def audit_predictions(raw, model, means, gain=None, tick=None, counters=None):
    """No response labels: verify complete positive mean arrays before commitment."""
    import numpy as np
    counters = _counters(counters)
    counters['prediction_audits_attempted'] += 1
    _tick(tick)
    n, channels, width = _raw(np, raw)
    _means(np, means, (n, channels))
    alpha, beta, center, scale, constant, unused = _model(np, model, channels, width)
    if gain is None:
        multipliers = np.ones(channels, dtype=np.float64)
    else:
        multipliers = np.asarray(gain, dtype=np.float64)
        need(multipliers.shape == (channels,) and bool(np.isfinite(multipliers).all())
             and bool((multipliers > 0.0).all()), 'Fixed positive calibration gain vector')
    maximum = 0.0
    for channel in range(channels):
        _tick(tick)
        unused, x = _channel(np, raw, channel, center, scale, constant)
        eta = np.dot(x, beta[channel]) + alpha[channel]
        with np.errstate(over='raise', invalid='raise', under='ignore'):
            expected = np.exp(eta) * multipliers[channel]
        need(bool(np.isfinite(expected).all()) and bool((expected > 0.0).all()),
             'Independent query means strictly positive and finite')
        # Vector comparison preserves the prespecified scalar max(1,a,b) rule.
        difference = np.abs(means[:, channel] - expected)
        tolerance = COMPARISON_RTOL * np.maximum(1.0, np.maximum(np.abs(means[:, channel]), np.abs(expected)))
        need(bool((difference <= tolerance).all()), 'Every query mean matches independent causal-view prediction')
        maximum = max(maximum, float(np.max(difference)))
        counters['prediction_feature_cells_checked'] += n * width
        counters['prediction_rates_checked'] += n
        counters['prediction_channels_completed'] += 1
    counters['prediction_audits_completed'] += 1
    return {'status': 'independent_channel_prediction_audit_passed', 'rows': n,
            'channels': channels, 'features_per_channel': width, 'rates_checked': n * channels,
            'maximum_absolute_difference': maximum, 'query_response_values_supplied': 0,
            'fixed_calibration_gain_applied': gain is not None}


def audit_gain(cal_y, frozen_means, gain, tick=None, counters=None):
    import numpy as np
    counters = _counters(counters)
    counters['gain_audits_attempted'] += 1
    need(type(cal_y) is np.ndarray and cal_y.ndim == 2, 'Calibration target matrix')
    n, channels = cal_y.shape
    need(0 < n <= 3000 and 0 < channels <= 96, 'Bounded fixed calibration support')
    _targets(np, cal_y, (n, channels))
    _means(np, frozen_means, (n, channels))
    need(len(gain) == channels, 'Every channel calibration multiplier retained')
    details = []
    for channel in range(channels):
        _tick(tick)
        count = sum(int(v) for v in cal_y[:, channel])
        exposure = math.fsum(float(v) for v in frozen_means[:, channel])
        expected = (count + 0.5) / (exposure + 0.5)
        actual = _finite(gain[channel], 'calibration multiplier')
        need(actual > 0.0 and math.isfinite(expected) and expected > 0.0,
             'Strictly positive finite Gamma-MAP gain without clipping')
        difference = _compare(actual, expected, 'fixed-prefix intercept-only calibration gain')
        details.append({'channel_index': channel, 'calibration_spikes': count,
                        'frozen_expected_count': exposure, 'independent_gain': expected,
                        'absolute_difference': difference})
        counters['gain_channels_checked'] += 1
    counters['gain_audits_completed'] += 1
    return {'status': 'independent_calibration_gain_audit_passed', 'rows': n,
            'channels': channels, 'per_channel': details,
            'formula': '(observed_count+0.5)/(frozen_expected_count+0.5)',
            'prior': 'Gamma(shape=1.5,rate=0.5) density on gain; MAP in gain parameter'}


def audit_rates(y, rates, tick=None, counters=None):
    import numpy as np
    counters = _counters(counters)
    counters['rate_audits_attempted'] += 1
    need(type(y) is np.ndarray and y.ndim == 2, 'Fitting count matrix for rate control')
    n, channels = y.shape
    need(0 < n <= 18700 and 0 < channels <= 96, 'Bounded declared constant-rate support')
    _targets(np, y, (n, channels))
    need(len(rates) == channels, 'Complete constant-rate channel vector')
    details = []
    for channel in range(channels):
        _tick(tick)
        count = sum(int(v) for v in y[:, channel])
        expected = (count + 0.5) / (n + 0.5)
        actual = _finite(rates[channel], 'constant rate')
        need(actual > 0.0, 'Source-silent channels retain positive prior rate')
        difference = _compare(actual, expected, 'Gamma-MAP rate control')
        details.append({'channel_index': channel, 'fitting_spikes': count,
                        'independent_rate': expected, 'absolute_difference': difference})
        counters['rate_channels_checked'] += 1
    counters['rate_audits_completed'] += 1
    return {'status': 'independent_constant_rate_audit_passed', 'rows': n,
            'channels': channels, 'per_channel': details,
            'formula': '(observed_count+0.5)/(rows+0.5)',
            'prior': 'Gamma(shape=1.5,rate=0.5) density on mean count; MAP in intensity parameter'}


def audit_score(y, means, score, tick=None, counters=None):
    """Independent full Poisson log likelihood in bounded scalar chunks.

    No zero-rate rescue, factorial omission, clipping, channel dropping, or
    bits-per-spike denominator substitution occurs here. The worker derives
    contrasts against its common precommitted rate baseline after this audit.
    """
    import numpy as np
    counters = _counters(counters)
    counters['score_audits_attempted'] += 1
    need(type(y) is np.ndarray and y.ndim == 2, 'Scored count matrix')
    n, channels = y.shape
    need(0 < n <= 25100 and 0 < channels <= 96, 'Complete bounded scoring roster')
    _targets(np, y, (n, channels))
    _means(np, means, (n, channels))
    need(score['rows'] == n and score['channels'] == channels and score['cells'] == n * channels,
         'Exact reported scoring support')
    need(len(score['per_channel']) == channels, 'All scored channels retained')
    channel_likelihoods, channel_spikes, details = [], [], []
    maximum_difference = 0.0
    for channel in range(channels):
        count = 0
        partials = []
        for start in range(0, n, 1024):
            _tick(tick)
            terms = []
            for row in range(start, min(start + 1024, n)):
                observed = int(y[row, channel])
                mu = float(means[row, channel])
                term = (observed * math.log(mu) if observed else 0.0) - mu - math.lgamma(observed + 1)
                need(math.isfinite(term), 'Finite full scalar Poisson log probability')
                terms.append(term)
                count += observed
                counters['score_cells_checked'] += 1
            partials.append(math.fsum(terms))
        likelihood = math.fsum(partials)
        saved = score['per_channel'][channel]
        need(saved['channel_index'] == channel and saved['spikes'] == count,
             'Identity-bound per-channel support and observed count')
        ll_difference = _compare(saved['log_likelihood'], likelihood, 'per-channel full Poisson log likelihood', score=True)
        nll_difference = _compare(saved['mean_nll'], -likelihood / n, 'per-channel mean NLL', score=True)
        maximum_difference = max(maximum_difference, ll_difference, nll_difference)
        channel_likelihoods.append(likelihood)
        channel_spikes.append(count)
        details.append({'channel_index': channel, 'spikes': count,
                        'independent_log_likelihood': likelihood,
                        'independent_mean_nll': -likelihood / n,
                        'log_likelihood_absolute_difference': ll_difference})
        counters['score_channels_completed'] += 1
    likelihood = math.fsum(channel_likelihoods)
    spikes = sum(channel_spikes)
    need(score['spikes'] == spikes, 'Exact full observed-count denominator')
    ll_difference = _compare(score['log_likelihood'], likelihood, 'full Poisson log likelihood', score=True)
    nll_difference = _compare(score['mean_nll'], -likelihood / (n * channels), 'all-cell mean NLL', score=True)
    maximum_difference = max(maximum_difference, ll_difference, nll_difference)
    counters['score_audits_completed'] += 1
    return {'status': 'independent_scalar_poisson_score_audit_passed', 'rows': n,
            'channels': channels, 'cells': n * channels, 'spikes': spikes,
            'independent_log_likelihood': likelihood,
            'independent_mean_nll': -likelihood / (n * channels),
            'per_channel': details, 'maximum_absolute_difference': maximum_difference,
            'comparison_atol': SCORE_ATOL, 'comparison_rtol': SCORE_RTOL,
            'zero_spike_BPS_denominator_is_undefined': spikes == 0}


def scalar_objective_gradient(x, y, theta, lam, tick=None, counters=None):
    """Independent small-fixture equations for all coordinates, including priors.

    x[row][channel][feature] is already standardized. This deliberately scalar
    implementation is for invented controls, not repeated empirical fitting.
    """
    counters = _counters(counters)
    counters['scalar_equations_attempted'] += 1
    n = len(x)
    need(n > 0 and len(y) == n, 'Small complete invented equation fixture')
    channels, width = len(x[0]), len(x[0][0])
    need(0 < channels <= 96 and 0 < width <= 20
         and all(len(row) == channels and all(len(v) == width for v in row) for row in x)
         and all(len(row) == channels for row in y), 'Exact scalar equation fixture shape')
    need(len(theta) == channels * (width + 1), 'Flattened channel-major intercept-first parameters')
    lam = _finite(lam, 'scalar ridge lambda')
    need(lam > 0.0, 'Positive scalar equation ridge')
    objectives, gradient = [], []
    for channel in range(channels):
        _tick(tick)
        offset = channel * (width + 1)
        alpha = _finite(theta[offset], 'scalar intercept')
        beta = [_finite(theta[offset + 1 + j], 'scalar slope') for j in range(width)]
        residuals, terms = [], []
        for row in range(n):
            if row % 64 == 0:
                _tick(tick)
            values = [_finite(x[row][channel][j], 'scalar standardized feature') for j in range(width)]
            observed = _finite(y[row][channel], 'scalar count')
            need(observed >= 0.0 and observed.is_integer(), 'Integer scalar fixture count')
            eta = math.fsum((alpha, math.fsum(a * b for a, b in zip(values, beta))))
            mu = math.exp(eta)
            need(math.isfinite(mu) and mu > 0.0, 'Finite positive scalar fixture rate')
            residuals.append(mu - observed)
            terms.append(mu - observed * eta)
            counters['scalar_equation_cells_checked'] += 1
        base = math.exp(alpha)
        objective = math.fsum(terms) / n + (0.5 * base - 0.5 * alpha) / n
        objective += 0.5 * lam * math.fsum(value * value for value in beta)
        need(math.isfinite(objective), 'Finite scalar joint-channel objective')
        objectives.append(objective)
        gradient.append((math.fsum(residuals) + 0.5 * base - 0.5) / n)
        for j in range(width):
            derivative = math.fsum(float(x[row][channel][j]) * residuals[row] for row in range(n)) / n
            gradient.append(derivative + lam * beta[j])
        counters['scalar_gradient_coordinates_checked'] += width + 1
    need(all(math.isfinite(v) for v in gradient), 'Finite scalar full gradient')
    counters['scalar_equations_completed'] += 1
    return math.fsum(objectives), gradient
