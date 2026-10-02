"""Prospective FCVAR shared computational kernel; no I/O or import-time work.

The oracle and verifier intentionally share this deterministic statistic kernel
so exact inclusive Monte Carlo ranks do not become a hidden BLAS/rounding test.
Source authentication, spatial extraction and evidence assembly remain separate.
This is an explicit float64 Nilearn-inspired cleaning recipe, not unconditional
API equivalence at numerical QR boundaries. No source data are loaded here.
"""
from __future__ import annotations

import math
import re
import numpy as np
from scipy import linalg, signal

WINDOWS = (20, 30, 44)
STEP = 3
N_DRAWS = 50
EPS = np.finfo(np.float64).eps
LOCAL_RELATIVE_TOLERANCE = 1e-6
CONFOUND_COLUMNS = (
    'motion-pitch', 'motion-roll', 'motion-yaw', 'motion-x', 'motion-y',
    'motion-z', 'compcor1', 'compcor2', 'compcor3', 'compcor4', 'compcor5',
    'wm', 'csf',
)


class PreconditionError(ValueError):
    pass


class FidelityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreconditionError(message)


def real_array(value, *, ndim=None):
    def reject_bool(item):
        if isinstance(item, (bool, np.bool_)):
            raise PreconditionError('Boolean is not a scientific number')
        if isinstance(item, (tuple, list)):
            for entry in item:
                reject_bool(entry)
    reject_bool(value)
    a = np.asarray(value)
    require(a.dtype.kind in 'iuf' and np.isfinite(a).all(), 'finite real array required')
    require(ndim is None or a.ndim == ndim, 'array dimensionality')
    return np.array(a, dtype=np.float64, order='C', copy=True)


def integer(value, low, high, name):
    require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)),
            name + ' must be an integer, not Boolean')
    out = int(value)
    require(low <= out <= high, name + ' outside public domain')
    return out


def subject_key(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9]{7}', value) is not None,
            'literal seven-character participant ID required')
    return value


def stable_center(vector):
    """Return scaled centered vector, original scale, and physical centered L2."""
    x = real_array(vector, ndim=1)
    require(len(x) > 0, 'nonempty vector required')
    if np.all(x == x[0]):
        return np.zeros_like(x), 0., 0.
    scale = float(np.max(np.abs(x)))
    c = x / scale
    c -= math.fsum(map(float, c)) / len(c)
    amplitude = float(np.max(np.abs(c)))
    norm_scaled = 0. if amplitude == 0 else amplitude * math.sqrt(
        math.fsum(float(v / amplitude) ** 2 for v in c))
    norm = scale * norm_scaled
    require(math.isfinite(norm), 'centered norm overflow')
    return c, scale, norm


def detrend(values):
    x = real_array(values, ndim=2)
    x -= x.mean(axis=0, dtype=np.float64)
    trend = np.arange(len(x), dtype=np.float64)
    trend -= trend.mean(dtype=np.float64)
    length = np.sqrt(np.sum(trend ** 2, dtype=np.float64))
    if length >= EPS:
        trend /= length
    x -= np.dot(trend, x) * trend[:, None]
    return np.ascontiguousarray(x)


def clean_roi_signals(raw, confounds, tr_sec, geometry_present):
    """Explicit cleaning and canonical whole-run support, retaining all48 IDs."""
    y0, c0 = real_array(raw, ndim=2), real_array(confounds, ndim=2)
    geom = np.asarray(geometry_present)
    require(y0.shape[1] == 48 and c0.shape == (len(y0), 13) and len(y0) > 33,
            'all48 ROIs, exact13 nuisances, matching complete frames>33 required')
    require(geom.shape == (48,) and geom.dtype.kind == 'b', 'Boolean geometry mask required')
    require(np.all(y0[:, ~geom] == 0), 'geometry-empty raw means use explicit zero sentinel')
    tr = real_array([tr_sec])[0]
    require(.1 < tr < 10 and .08 < .5 / tr, 'valid per-person TR and filter Nyquist required')
    y, c = detrend(y0), detrend(c0)
    sos = signal.butter(5, [.009, .08], btype='bandpass', fs=1. / tr, output='sos')
    # Canonical C layout is explicit at each filtered matrix boundary.
    y = np.array(signal.sosfiltfilt(sos, y, axis=0, padtype='odd', padlen=33), order='C')
    c = np.array(signal.sosfiltfilt(sos, c, axis=0, padtype='odd', padlen=33), order='C')
    c -= c.mean(axis=0, dtype=np.float64)
    sd = c.std(axis=0, ddof=0, dtype=np.float64)
    sd[sd < EPS] = 1.
    c /= sd
    q, r, _ = linalg.qr(c, mode='economic', pivoting=True, check_finite=True)
    retained = np.abs(np.diag(r)) > 100 * EPS
    q = np.ascontiguousarray(q[:, retained])
    residual = np.ascontiguousarray(y - (q @ q.T) @ y)
    residual -= residual.mean(axis=0, dtype=np.float64)
    clean = np.zeros_like(y0)
    raw_sd = np.zeros(48)
    norms = np.zeros(48)
    thresholds = np.zeros(48)
    active = np.zeros(48, dtype=bool)
    for roi in range(48):
        _, _, raw_norm = stable_center(y0[:, roi])
        centered, scale, residual_norm = stable_center(residual[:, roi])
        raw_sd[roi] = raw_norm / math.sqrt(len(y0) - 1)
        norms[roi] = residual_norm
        thresholds[roi] = 1e-12 * raw_norm
        active[roi] = bool(geom[roi] and raw_norm > 0 and residual_norm > thresholds[roi])
        if active[roi]:
            # Equivalent to centered residual / positive stable sample SD,
            # without an absolute epsilon floor or underflowing physical divisor.
            clean[:, roi] = centered / (residual_norm / scale) * math.sqrt(len(y0) - 1)
    full_norm = np.array([stable_center(clean[:, j])[2] for j in range(48)])
    require(all(np.isfinite(a).all() for a in (clean, raw_sd, norms, thresholds, full_norm)),
            'nonfinite cleaning output or diagnostic')
    return dict(clean=clean, active=active, raw_sample_sd=raw_sd,
                prestandardization_centered_l2=norms, activity_threshold=thresholds,
                full_clean_centered_l2=full_norm, cleaning_rank=int(retained.sum()))


def generate_phases(n_frames, subject_id, window_tr, seed=0):
    n = integer(n_frames, 2, 1000000, 'n_frames')
    sid = subject_key(subject_id)
    w = integer(window_tr, 1, 1000000, 'window_tr')
    require(w in WINDOWS, 'one of the three public windows required')
    base = integer(seed, 0, 2 ** 32 - 1, 'seed')
    rng = np.random.Generator(np.random.PCG64(base + int(sid) + w))
    phases = rng.uniform(0., 2 * np.pi, size=(N_DRAWS, n // 2 + 1))
    phases[:, 0] = 0.
    if n % 2 == 0:
        phases[:, -1] = 0.
    return np.ascontiguousarray(phases)


def phase_surrogate(clean, phase):
    y, p = real_array(clean, ndim=2), real_array(phase, ndim=1)
    require(len(y) >= 2 and p.shape == (len(y) // 2 + 1,), 'full-record phase shape')
    require(p[0] == 0 and (len(y) % 2 or p[-1] == 0), 'fixed DC/even Nyquist')
    require(np.all((p >= 0) & (p < 2 * np.pi)), 'canonical phase angle domain')
    if y.shape[1] == 0:
        return y.copy()
    out = np.fft.irfft(np.fft.rfft(y, axis=0) * np.exp(1j * p)[:, None], n=len(y), axis=0)
    require(np.isfinite(out).all(), 'nonfinite FFT result')
    return np.ascontiguousarray(out)


def _window_vectors(series, window):
    """C-contiguous [start, original-frame, ROI] scale-first centering."""
    starts = np.arange(0, max(0, len(series) - window + 1), STEP, dtype=np.int64)
    if not len(starts):
        shape = (0, window, series.shape[1])
        return np.empty(shape), np.empty((0, series.shape[1])), np.empty((0, series.shape[1]))
    a = np.ascontiguousarray(np.lib.stride_tricks.sliding_window_view(
        series, window, axis=0)[starts].transpose(0, 2, 1))
    scale = np.max(np.abs(a), axis=1)
    c = a / np.where(scale > 0, scale, 1.)[:, None, :]
    c -= np.mean(c, axis=1, keepdims=True, dtype=np.float64)
    constant = np.all(a == a[:, :1, :], axis=1)
    c = np.where(constant[:, None, :], 0., c)
    amplitude = np.max(np.abs(c), axis=1)
    z = c / np.where(amplitude > 0, amplitude, 1.)[:, None, :]
    norm_scaled = amplitude * np.sqrt(np.sum(z * z, axis=1, dtype=np.float64))
    return np.ascontiguousarray(c), scale, norm_scaled


def _local_fidelity(accepted, reference, valid):
    c, scale, _ = accepted
    ref, ref_scale, ref_norm = reference
    # Normalize both centered vectors in the reference window's original scale.
    ratio = np.divide(scale, ref_scale, out=np.zeros_like(scale), where=ref_scale > 0)
    diff = c * ratio[:, None, :] - ref
    amplitude = np.max(np.abs(diff), axis=1)
    z = diff / np.where(amplitude > 0, amplitude, 1.)[:, None, :]
    error = amplitude * np.sqrt(np.sum(z * z, axis=1, dtype=np.float64))
    relative = np.divide(error, ref_norm, out=np.zeros_like(error), where=ref_norm > 0)
    if not np.isfinite(relative[valid]).all() or np.any(relative[valid] > LOCAL_RELATIVE_TOLERANCE):
        raise FidelityError('canonical-active local centered-relative fidelity')


def validate_series(clean, reference_clean, global_active):
    y, ref = real_array(clean, ndim=2), real_array(reference_clean, ndim=2)
    active = np.asarray(global_active)
    require(y.shape == ref.shape and y.shape[1] == 48 and len(y) >= 2, 'full48 aligned series')
    require(active.shape == (48,) and active.dtype.kind == 'b', 'canonical Boolean activity')
    require(np.all(ref[:, ~active] == 0), 'canonical inactive cleaned columns use zero sentinel')
    # Accepted inactive entries are checked only by the public pointwise bound
    # in the evidence validator; their tolerated jitter is never an input below.
    for j in np.flatnonzero(active):
        c, scale, _ = stable_center(y[:, j])
        r, reference_scale, reference_norm = stable_center(ref[:, j])
        require(reference_norm > 0, 'canonical active whole-run signals must be nonconstant')
        difference = c * (scale / reference_scale) - r
        amplitude = float(np.max(np.abs(difference)))
        error = 0. if amplitude == 0 else amplitude * math.sqrt(
            math.fsum(float(v / amplitude) ** 2 for v in difference))
        relative = error / (reference_norm / reference_scale)
        if not math.isfinite(relative) or relative > LOCAL_RELATIVE_TOLERANCE:
            raise FidelityError('canonical-active global centered-relative fidelity')
    return y, ref, active


def window_statistic(clean, reference_clean, original_full_norm, window_tr):
    """Return one scalar slot, checking all canonical-active local vectors."""
    y, reference = real_array(clean, ndim=2), real_array(reference_clean, ndim=2)
    w = integer(window_tr, 1, 1000000, 'window_tr')
    norm = real_array(original_full_norm, ndim=1)
    require(w in WINDOWS and y.shape == reference.shape and norm.shape == (y.shape[1],),
            'matching full-signal and norm axes')
    n_windows = len(range(0, max(0, len(y) - w + 1), STEP))
    if y.shape[1] < 2:
        return {'status': 'insufficient_rois', 'mean_edge_sd': None}
    if n_windows < 2:
        return {'status': 'insufficient_windows', 'mean_edge_sd': None}
    require(np.all(norm > 0), 'retained canonical whole-run norm must be positive')
    canonical = _window_vectors(reference, w)
    accepted = _window_vectors(y, w)
    local_norm = canonical[1] * canonical[2]
    threshold = 1e-12 * math.sqrt(w / len(y)) * norm[None, :]
    valid = local_norm > threshold
    _local_fidelity(accepted, canonical, valid)
    if not np.all(valid):
        return {'status': 'undefined_window_correlation', 'mean_edge_sd': None}
    c, _, n = accepted
    require(np.all(n > 0), 'accepted active vectors must have nonzero norm')
    unit = np.ascontiguousarray(c / n[:, None, :])
    correlations = np.matmul(unit.transpose(0, 2, 1), unit)
    require(np.isfinite(correlations).all(), 'finite window correlations')
    require(np.max(np.abs(correlations)) <= 1 + 1e-12, 'Pearson roundoff domain')
    upper = np.triu_indices(y.shape[1], 1)
    z = np.ascontiguousarray(np.arctanh(np.clip(correlations[:, upper[0], upper[1]], -.999, .999)))
    centered = z - np.mean(z, axis=0, dtype=np.float64)
    edge_sd = np.sqrt(np.sum(centered * centered, axis=0, dtype=np.float64) / (n_windows - 1))
    edge_sd[np.all(z == z[:1], axis=0)] = 0.
    value = float(np.mean(edge_sd, dtype=np.float64))
    require(math.isfinite(value) and value >= 0, 'finite nonnegative variability')
    return {'status': 'ok', 'mean_edge_sd': value}


def summarize_slots(observed, null_slots):
    require(len(null_slots) == N_DRAWS, 'exactly50 null slots')
    observed_value = observed['mean_edge_sd']
    null_values = [row['mean_edge_sd'] for row in null_slots]
    count_defined = sum(value is not None for value in null_values)
    null_mean = math.fsum(null_values) / N_DRAWS if count_defined == N_DRAWS else None
    complete = observed_value is not None and null_mean is not None
    ratio_status = 'incomplete_support'
    ratio = None
    if complete:
        ratio_status = 'zero_null_mean' if null_mean == 0 else 'ok'
        if null_mean > 0:
            ratio = observed_value / null_mean
            require(math.isfinite(ratio), 'finite ratio required')
    comparisons = [None if observed_value is None or value is None else bool(value >= observed_value)
                   for value in null_values]
    exceeds = sum(comparisons) if complete else None
    numerator = 1 + exceeds if complete else None
    return dict(observed_status=observed['status'], mean_edge_sd=observed_value,
        n_null_expected=N_DRAWS, n_null_defined=count_defined,
        null_mean_status='ok' if null_mean is not None else 'incomplete_null_support',
        mean_edge_sd_null=null_mean, ratio_status=ratio_status,
        observed_over_null_ratio=ratio, inference_status='ok' if complete else 'incomplete_support',
        n_exceedances=exceeds, p_numerator=numerator, p_denominator=N_DRAWS + 1,
        p_value=numerator / (N_DRAWS + 1) if complete else None,
        significant=20 * numerator < N_DRAWS + 1 if complete else None), comparisons


def analyze_subject(clean, reference_clean, global_active, subject_id, seed=0):
    """Single accepted-signal replay; canonical geometry/support, no hidden p gate."""
    y, ref, active = validate_series(clean, reference_clean, global_active)
    sid = subject_key(subject_id)
    base = integer(seed, 0, 2 ** 32 - 1, 'seed')
    y, ref = np.ascontiguousarray(y[:, active]), np.ascontiguousarray(ref[:, active])
    norms = np.array([stable_center(ref[:, j])[2] for j in range(ref.shape[1])])
    require(np.all(norms > 0), 'canonical active whole-run signals must be nonconstant')
    rows, draws, phases = [], [], {}
    n_rois = int(active.sum())
    for w in WINDOWS:
        phases[w] = generate_phases(len(y), sid, w, base)
        observed = window_statistic(y, ref, norms, w)
        null = []
        for phase in phases[w]:
            surrogate = phase_surrogate(y, phase)
            canonical_surrogate = phase_surrogate(ref, phase)
            null.append(window_statistic(surrogate, canonical_surrogate, norms, w))
        summary, comparisons = summarize_slots(observed, null)
        rows.append(dict(subject=sid, window_tr=w,
            n_windows=len(range(0, max(0, len(y) - w + 1), STEP)), n_rois=n_rois,
            n_edges=n_rois * (n_rois - 1) // 2, **summary))
        draws.extend(dict(subject=sid, window_tr=w, surrogate_id=b,
                          exceeds_observed=comparisons[b], **slot) for b, slot in enumerate(null))
    return dict(subject=sid, seed=base, n_timepoints=len(y), n_global_active_rois=n_rois,
                n_edges=n_rois * (n_rois - 1) // 2, windows=rows, surrogates=draws, phases=phases)


def summarize_subjects(subject_results, participant_ids):
    ids = list(participant_ids)
    require(len(ids) > 0 and len(set(ids)) == len(ids), 'unique expected participant IDs')
    for sid in ids:
        subject_key(sid)
    results = list(subject_results)
    require(len(results) == len(ids) and {r['subject'] for r in results} == set(ids),
            'complete exact subject-result membership')
    by_id = {r['subject']: r for r in results}
    seeds = {integer(r['seed'], 0, 2 ** 32 - 1, 'seed') for r in results}
    require(len(seeds) == 1, 'one global base seed')
    for result in results:
        require(len(result['windows']) == 3 and {r['window_tr'] for r in result['windows']} == set(WINDOWS),
                'complete three-window results')
    def metric(values, median=False):
        available = [float(v) for v in values if v is not None]
        require(all(math.isfinite(v) for v in available), 'finite group inputs')
        complete = len(available) == len(ids)
        value = None
        if complete:
            if median:
                values_sorted = sorted(available)
                middle = len(values_sorted) // 2
                value = values_sorted[middle] if len(values_sorted) % 2 else math.fsum(values_sorted[middle-1:middle+1]) / 2
            else:
                value = math.fsum(available) / len(ids)
        return dict(n_expected=len(ids), n_defined=len(available), status='ok' if complete else 'incomplete_support', value=value)
    windows = []
    for w in WINDOWS:
        records = [next(row for row in by_id[sid]['windows'] if row['window_tr'] == w) for sid in ids]
        windows.append(dict(window_tr=w,
            mean_observed_edge_sd=metric([r['mean_edge_sd'] for r in records]),
            mean_null_edge_sd=metric([r['mean_edge_sd_null'] for r in records]),
            mean_subject_observed_over_null_ratio=metric([r['observed_over_null_ratio'] for r in records]),
            median_subject_p=metric([r['p_value'] for r in records], median=True),
            fraction_subjects_significant=metric([r['significant'] for r in records])))
    return dict(schema_version='fcvar-results-v3', status='complete', n_subjects=len(ids),
                window_lengths_tr=list(WINDOWS), primary_window_tr=30, step_tr=STEP,
                n_surrogates=N_DRAWS, seed=next(iter(seeds)), windows=windows)
