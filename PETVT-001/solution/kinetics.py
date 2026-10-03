"""Prospective PETVT arithmetic only: no files, fetching, side effects or bank.

This is the oracle's implementation. The later private source reconstruction
and fit validator must not import this module. Manufactured tests use analytic
integrals and an independent QR calculation where the design is well resolved.
"""
import math

import numpy as np
from scipy import linalg

ASSUMPTIONS = ('already_image_reference', 'sample_time_reference')
ESTIMATORS = ('logan', 'ma1')
EPS = np.finfo(np.float64).eps


class ContractError(ValueError):
    pass


class Unavailable(ValueError):
    pass


def real_array(value, ndim, name):
    source = np.asarray(value)
    if source.ndim != ndim or source.dtype.kind not in 'iuf' or not np.all(np.isfinite(source)):
        raise ContractError('invalid finite real '+name)
    result = np.array(source, dtype=np.float64, order='C', copy=True)
    if not np.all(np.isfinite(result)):
        raise ContractError('float64 conversion overflow: '+name)
    return result


def scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ContractError('invalid scalar '+name)
    result = float(value)
    if not math.isfinite(result): raise ContractError('nonfinite '+name)
    return result


def l2(value):
    return math.hypot(*map(float, np.ravel(value)))


def cortical_mean(values):
    values = real_array(values, 2, 'cortical values')
    if 0 in values.shape: raise ContractError('empty cortical values')
    means = []
    for row in values:
        scale = float(np.max(np.abs(row)))
        means.append(0.0 if scale == 0 else scale*(math.fsum(float(x/scale) for x in row)/len(row)))
    return np.asarray(means, dtype=np.float64)


def tissue_integral(frame_starts_s, frame_ends_s, tissue, injection_start_s=0.0):
    starts = real_array(frame_starts_s, 1, 'frame starts')
    ends = real_array(frame_ends_s, 1, 'frame ends')
    ct = real_array(tissue, 1, 'tissue')
    origin = scalar(injection_start_s, 'injection origin')
    if not len(starts) or starts.shape != ends.shape or starts.shape != ct.shape:
        raise ContractError('frame shape')
    if abs(starts[0]-origin) > 1e-6 or np.any(ends <= starts) or np.any(np.abs(starts[1:]-ends[:-1]) > 1e-6):
        raise ContractError('noncontiguous frame support')
    duration = (ends-starts)/60.0
    midpoint = ((starts-origin)/60.0+(ends-origin)/60.0)*0.5
    with np.errstate(over='ignore', invalid='ignore'):
        areas = ct*duration
    if not np.all(np.isfinite(areas)) or not np.all(np.isfinite(midpoint)):
        raise Unavailable('numerical_failure')
    try:
        integral = np.asarray([math.fsum(map(float, areas[:i]))+float(areas[i])*0.5 for i in range(len(ct))])
    except OverflowError:
        raise Unavailable('numerical_failure') from None
    if not np.all(np.isfinite(integral)): raise Unavailable('numerical_failure')
    return midpoint, integral


def parent_knots(time_s, plasma, parent_fraction, assumption, *, half_life_s=6586.2,
                 image_reference_s=0.0, injection_start_s=0.0):
    times = real_array(time_s, 1, 'paired time')
    activity = real_array(plasma, 1, 'plasma')
    parent = real_array(parent_fraction, 1, 'parent fraction')
    half_life = scalar(half_life_s, 'half life')
    reference = scalar(image_reference_s, 'image reference')
    origin = scalar(injection_start_s, 'injection origin')
    if assumption not in ASSUMPTIONS or half_life <= 0:
        raise ContractError('assumption/half life')
    if times.shape != activity.shape or times.shape != parent.shape:
        raise ContractError('paired knot shape')
    if len(times) < 2: raise Unavailable('input_time_support_unavailable')
    if times[0] < origin or np.any(np.diff(times) <= 0) or np.any(activity < 0) or np.any(parent < 0) or np.any(parent > 1):
        raise ContractError('paired knot domain/order')
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        values = activity*parent
        if assumption == 'sample_time_reference':
            values = values*np.exp(np.log(2.0)*(times-reference)/half_life)
        minutes = (times-origin)/60.0
    if (not np.all(np.isfinite(values)) or not np.all(np.isfinite(minutes)) or
            np.any((activity > 0) & (parent > 0) & (values == 0))):
        raise Unavailable('numerical_failure')
    anchor = bool(times[0] > origin)
    if anchor:
        minutes = np.concatenate(([0.0], minutes)); values = np.concatenate(([0.0], values))
    return dict(times_min=minutes, values=values, inserted_zero_anchor=anchor)


def input_integral(knot_times_min, knot_values, target_times_min):
    times = real_array(knot_times_min, 1, 'integration knots')
    values = real_array(knot_values, 1, 'input values')
    targets = real_array(target_times_min, 1, 'target times')
    if len(times) < 2 or times.shape != values.shape or times[0] != 0 or np.any(np.diff(times) <= 0) or np.any(values < 0):
        raise ContractError('integration knot support')
    if np.any(targets < times[0]) or np.any(targets > times[-1]):
        raise Unavailable('input_time_support_unavailable')
    widths = np.diff(times)
    with np.errstate(over='ignore', invalid='ignore'):
        areas = (values[:-1]*0.5+values[1:]*0.5)*widths
    if not np.all(np.isfinite(areas)): raise Unavailable('numerical_failure')
    result = []
    try:
        for target in targets:
            if target == times[-1]:
                result.append(math.fsum(map(float, areas))); continue
            j = int(np.searchsorted(times, target, side='right')-1)
            dt = float(target-times[j]); fraction = dt/float(widths[j])
            height = (1-fraction)*float(values[j])+fraction*float(values[j+1])
            partial = (float(values[j])*0.5+height*0.5)*dt
            result.append(math.fsum(map(float, areas[:j]))+partial)
    except OverflowError:
        raise Unavailable('numerical_failure') from None
    result = np.asarray(result, dtype=np.float64)
    if not np.all(np.isfinite(result)): raise Unavailable('numerical_failure')
    return result


def empty_fit(status, n_fit_rows, **extra):
    return dict(status=status, n_fit_rows=n_fit_rows, rank=None, coefficients=None,
                column_scales=None, singular_values=None, residual_rss=None,
                rss_status='unavailable', vt=None, nonpositive_vt=None, **extra)


def solve_ols(design, response):
    x = real_array(design, 2, 'design'); y = real_array(response, 1, 'response')
    if x.shape != (len(y), 2): raise ContractError('two-column model shape')
    if len(y) < 3: return empty_fit('insufficient_fit_rows', len(y))
    scales = np.asarray([l2(x[:, j]) for j in range(2)])
    if not np.all(np.isfinite(scales)): return empty_fit('numerical_failure', len(y))
    if np.any(scales == 0): return empty_fit('zero_design_column', len(y), design=x)
    normalized = np.ascontiguousarray(x/scales)
    try:
        scaled, _, rank, singular = linalg.lstsq(normalized, y, cond=max(x.shape)*EPS,
                                               lapack_driver='gelsd', check_finite=True)
    except (ValueError, linalg.LinAlgError):
        return empty_fit('numerical_failure', len(y))
    if rank < 2:
        result = empty_fit('rank_deficient', len(y)); result.update(rank=int(rank),
                      column_scales=scales, singular_values=singular)
        return result
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        coefficients = scaled/scales
        residual = y-x@coefficients
    if not np.all(np.isfinite(coefficients)):
        return empty_fit('numerical_failure', len(y))
    if not np.all(np.isfinite(residual)):
        rss, rss_status = None, 'numerical_overflow'
    else:
        residual_norm = l2(residual); rss = residual_norm*residual_norm
        rss_status = 'ok'
        if not math.isfinite(rss): rss, rss_status = None, 'numerical_overflow'
        elif residual_norm != 0 and rss == 0: rss, rss_status = None, 'numerical_underflow'
    return dict(status='ok', n_fit_rows=len(y), rank=2, coefficients=coefficients,
                column_scales=scales, singular_values=singular, residual_rss=rss,
                rss_status=rss_status, vt=None, nonpositive_vt=None)


def ma1_supported(coefficients):
    values = real_array(coefficients, 1, 'MA1 coefficients')
    if values.shape != (2,): raise ContractError('coefficient shape')
    scale = float(np.max(np.abs(values)))
    return bool(scale > 0 and abs(float(values[1]))/scale > 64*EPS)


def derive_vt(estimator, coefficients, *, source_supported=True):
    values = real_array(coefficients, 1, 'coefficients')
    if values.shape != (2,) or estimator not in ESTIMATORS or type(source_supported) is not bool:
        raise ContractError('model identity/support')
    if estimator == 'logan' and not source_supported:
        raise ContractError('MA1 denominator flag is not a Logan flag')
    if not source_supported: return dict(status='ma1_denominator_unresolved', vt=None, nonpositive_vt=None)
    if estimator == 'logan': value = float(values[0])
    else:
        if values[1] == 0: return dict(status='numerical_failure', vt=None, nonpositive_vt=None)
        value = -float(values[0])/float(values[1])
        if not math.isfinite(value) or (values[0] != 0 and value == 0):
            return dict(status='numerical_failure', vt=None, nonpositive_vt=None)
    return dict(status='ok', vt=value, nonpositive_vt=bool(value <= 0))


def accepted_coefficients(estimator, submitted, canonical, *, source_supported=True):
    """Public numerical binding; downstream replay uses the returned own values.

    Canonical support cannot be activated by serialization. No canonical VT is
    compared. MA1 relative checks use a common scale, never epsilon floors.
    """
    actual = real_array(submitted, 1, 'submitted coefficients')
    source = real_array(canonical, 1, 'source coefficients')
    if actual.shape != (2,) or source.shape != (2,) or estimator not in ESTIMATORS or type(source_supported) is not bool:
        raise ContractError('coefficient identity/support')
    for observed, expected in zip(actual, source):
        if abs(float(observed)-float(expected)) > 1e-8+1e-6*abs(float(expected)):
            raise ContractError('coefficient source fidelity')
    if estimator == 'ma1' and source_supported:
        if not ma1_supported(source): raise ContractError('inconsistent canonical MA1 support')
        scale = float(np.max(np.abs(source)))
        with np.errstate(over='ignore', invalid='ignore'):
            source_scaled = source/scale
            actual_scaled = actual/scale
        if not np.all(np.isfinite(actual_scaled)) or l2(actual_scaled-source_scaled)/l2(source_scaled) > 1e-6:
            raise ContractError('MA1 coefficient-vector relative fidelity')
        if abs((float(actual[1])-float(source[1]))/float(source[1])) > 1e-6:
            raise ContractError('MA1 denominator relative fidelity')
    return actual


def fit_model(midpoint_min, tissue, tissue_area, plasma_area, estimator):
    times = real_array(midpoint_min, 1, 'midpoints')
    ct = real_array(tissue, 1, 'tissue'); it = real_array(tissue_area, 1, 'tissue integral')
    if estimator not in ESTIMATORS or times.shape != ct.shape or times.shape != it.shape:
        raise ContractError('model/frame shape')
    mask = times >= 30.0; n = int(np.count_nonzero(mask))
    if plasma_area is None: return empty_fit('input_time_support_unavailable', n)
    ip = real_array(plasma_area, 1, 'plasma integral')
    if ip.shape != times.shape: raise ContractError('input integral shape')
    if n < 3: return empty_fit('insufficient_fit_rows', n)
    if estimator == 'logan' and np.any(ct[mask] <= 0):
        return empty_fit('nonpositive_tissue_for_logan', n)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        if estimator == 'logan':
            design = np.column_stack((ip[mask]/ct[mask], np.ones(n))); response = it[mask]/ct[mask]
        else:
            design = np.column_stack((ip[mask], it[mask])); response = ct[mask]
    if not np.all(np.isfinite(design)) or not np.all(np.isfinite(response)):
        return empty_fit('numerical_failure', n)
    result = solve_ols(design, response)
    if result['status'] == 'ok':
        support = estimator != 'ma1' or ma1_supported(result['coefficients'])
        result.update(derive_vt(estimator, result['coefficients'], source_supported=support))
    return result


def complete_summary(values, n_expected=7):
    if type(n_expected) is not int or n_expected < 2 or len(values) != n_expected:
        raise ContractError('complete family membership')
    finite = [scalar(x, 'group value') for x in values if x is not None]
    result = dict(n_expected=n_expected, n_defined=len(finite), status='incomplete',
                  mean=None, sample_sd=None, minimum=None, maximum=None)
    if len(finite) != n_expected: return result
    # Power-of-two scaling avoids ratio-rounding away nearby represented
    # values; first-value-anchored centering preserves small nonzero spread.
    scale = max(map(abs, finite)); exponent = math.frexp(scale)[1] if scale else 0
    scaled = [math.ldexp(v, -exponent) for v in finite]
    differences = [v-scaled[0] for v in scaled]
    mean_difference = math.fsum(differences)/n_expected
    centered = [v-mean_difference for v in differences]
    try:
        mean = math.ldexp(scaled[0]+mean_difference, exponent)
        sd = 0.0 if min(finite) == max(finite) else math.ldexp(l2(centered)/math.sqrt(n_expected-1), exponent)
    except OverflowError:
        result['status'] = 'numerical_failure'; return result
    if (not math.isfinite(mean) or not math.isfinite(sd) or
            (min(finite) != max(finite) and sd == 0)):
        result['status'] = 'numerical_failure'; return result
    result.update(status='ok', mean=mean, sample_sd=sd, minimum=min(finite), maximum=max(finite))
    return result
