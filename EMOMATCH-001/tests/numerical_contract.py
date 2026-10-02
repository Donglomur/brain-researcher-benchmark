"""Prospective EMOMATCH numerical contract, not wired to production grading.

Only explicitly supplied manufactured/canonical arrays are accepted here. There
is no source loader, file I/O, historical bank, oracle import or executable
entrypoint. Grader SVD uses SciPy/gesvd; HRF/drift are shared pinned Nilearn
primitives and linear algebra still shares LAPACK with the planned oracle.
Source authentication, keys and actual numerical gates belong upstream.
"""
from dataclasses import dataclass
from decimal import Decimal
import math
from numbers import Real, Integral
import warnings

import numpy as np
from scipy import linalg, special, stats
from nilearn.glm.first_level.design_matrix import create_cosine_drift
from nilearn.glm.first_level.hemodynamic_models import compute_regressor


EPS = np.finfo(np.float64).eps
CONFOUNDS = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "a_comp_cor_00", "a_comp_cor_01", "a_comp_cor_02", "a_comp_cor_03",
             "a_comp_cor_04", "white_matter", "csf")


@dataclass(frozen=True)
class Tolerance:
    atol: float
    rtol: float


SOURCE_TOL = Tolerance(1e-8, 1e-6)
FIT_TOL = Tolerance(1e-7, 1e-5)
GROUP_TOL = Tolerance(1e-7, 1e-5)
DIAGNOSTIC_TOL = Tolerance(1e-14, 1e-6)
EVENT_TOL = Tolerance(1e-9, 1e-8)
GEOMETRY_TOL = Tolerance(1e-7, 1e-8)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def scalar(value):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not a measurement")
    require(isinstance(value, (Real, Decimal)), "measurement must be numeric, not text")
    number = float(value)
    require(math.isfinite(number), "nonfinite measurement")
    return number


def count(value):
    require(isinstance(value, Integral) and not isinstance(value, (bool, np.bool_)),
            "count must be typed integer")
    require(0 <= value <= 2**63 - 1, "count range")
    return int(value)


def _check_sequence_types(value):
    if isinstance(value, (list, tuple)):
        for child in value:
            _check_sequence_types(child)
    elif isinstance(value, np.ndarray):
        require(value.dtype.kind in "iuf", "array must be real numeric, not Boolean/object")
    else:
        scalar(value)


def array(value, ndim=None):
    """Check Python leaves before coercion can hide mixed Boolean values."""
    _check_sequence_types(value)
    result = np.asarray(value, dtype=np.float64)
    require(ndim is None or result.ndim == ndim, "numeric array dimensions")
    require(np.isfinite(result).all(), "nonfinite numeric array")
    return result


def boolean_mask(value, shape):
    result = np.asarray(value)
    require(result.dtype.kind == "b" and result.shape == shape, "typed Boolean mask shape")
    return result


def finite_result(*values):
    require(all(np.isfinite(value).all() for value in values), "nonfinite arithmetic result")


def normalization(raw):
    """All finite frames, float64 population SD+1e-8; exact constants retained."""
    values = array(raw, 2)
    require(min(values.shape) > 0, "empty normalization input")
    constant = np.all(values == values[0], axis=0)
    center = np.array([values[0, j] if constant[j]
                       else math.fsum(map(float, values[:, j])) / len(values)
                       for j in range(values.shape[1])], dtype=np.float64)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        shifted = values - center
        variance = np.array([math.fsum(float(v) * float(v) for v in shifted[:, j])
                             / len(values) for j in range(values.shape[1])])
        sd = np.sqrt(variance)
        denominator = sd + 1e-8
        normalized = shifted / denominator
    finite_result(center, sd, denominator, normalized)
    return dict(mean=center, sd=sd, denominator=denominator,
                exact_constant=constant, normalized=normalized)


def impute_confounds(raw_with_placeholders, missing):
    """Missing entries have finite parser placeholders; the mask is authoritative."""
    raw = array(raw_with_placeholders, 2)
    absent = boolean_mask(missing, raw.shape)
    require(raw.shape[0] > 0, "no confound frames")
    effective = raw.copy()
    fill = np.zeros(raw.shape[1], dtype=np.float64)
    for column in range(raw.shape[1]):
        observed = raw[~absent[:, column], column]
        if len(observed):
            fill[column] = math.fsum(map(float, observed)) / len(observed)
        effective[absent[:, column], column] = fill[column]
    finite_result(fill, effective)
    return dict(effective=effective, missing=absent.copy(), fill=fill,
                all_missing=np.all(absent, axis=0))


def duration_models(rt_with_placeholders, missing):
    rt = array(rt_with_placeholders, 1)
    absent = boolean_mask(missing, rt.shape)
    good = rt[~absent]
    require(len(rt) > 0 and len(good) > 0, "no valid pooled target RT")
    require(np.all(good > 0), "nonpositive valid RT")
    ordered = np.sort(good)
    middle = len(ordered) // 2
    median = (float(ordered[middle]) if len(ordered) % 2
              else math.fsum([float(ordered[middle - 1]) / 2, float(ordered[middle]) / 2]))
    require(math.isfinite(median) and median > 0, "invalid pooled RT median")
    a = np.full(rt.shape, median)
    b = np.where(absent, median, rt)
    return dict(median=median, modelA=a, modelB=b, modelB_imputed=absent.copy())


def design(onsets, durations, conditions, n_frames, confounds):
    """Unregularized task+cosine+13 original-scale nuisance+constant design.

    The HRF has min_onset=-24, but whether an original onset is a source
    precondition failure remains a structural-policy decision upstream. This
    function retains any library warning rather than inventing an exclusion.
    """
    n_frames = count(n_frames)
    require(n_frames >= 2, "at least two design frames required")
    onset, duration, nuisance = array(onsets, 1), array(durations, 1), array(confounds, 2)
    condition = np.asarray(conditions)
    require(condition.dtype.kind in "US" and condition.ndim == 1, "condition text axis")
    if condition.dtype.kind == "S":
        condition = np.char.decode(condition, "utf-8")
    require(onset.shape == duration.shape == condition.shape, "event axis mismatch")
    require(set(condition.tolist()) <= {"control", "emotion"}, "unknown included condition")
    require(np.all(duration > 0), "modeled durations must be positive")
    require(nuisance.shape == (n_frames, len(CONFOUNDS)), "nuisance shape")
    times = 2.0 * np.arange(n_frames, dtype=np.float64)
    task = []
    present = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for name in ("control", "emotion"):
            selected = condition == name
            present.append(bool(np.any(selected)))
            if not np.any(selected):
                task.append(np.zeros(n_frames))
            else:
                column, _ = compute_regressor(
                    (onset[selected], duration[selected], np.ones(np.count_nonzero(selected))),
                    "spm", times, con_id=name, oversampling=50, min_onset=-24)
                task.append(column[:, 0])
        drift = create_cosine_drift(.008, times)
    matrix = np.column_stack([*task, drift[:, :-1], nuisance, np.ones(n_frames)])
    names = ["control", "emotion"] + [f"drift_{i+1}" for i in range(drift.shape[1]-1)]
    names += list(CONFOUNDS) + ["constant"]
    contrast = np.zeros(matrix.shape[1]); contrast[0], contrast[1] = -1., 1.
    finite_result(matrix)
    return dict(matrix=matrix, column_keys=names, frame_times=times, contrast=contrast,
                condition_present=np.array(present, dtype=bool),
                warnings=[{"category": type(w.message).__name__, "message": str(w.message)}
                          for w in caught])


def fit_svd(design_matrix, response, contrast, *, condition_present=(True, True)):
    x, y, c = array(design_matrix, 2), array(response, 2), array(contrast, 1)
    require(min(x.shape) > 0 and y.shape[0] == len(x) and y.shape[1] > 0, "fit axes")
    require(c.shape == (x.shape[1],) and np.any(c), "nonzero contrast shape")
    present = boolean_mask(condition_present, (2,))
    u, s, vh = linalg.svd(x, full_matrices=False, check_finite=True, lapack_driver="gesvd")
    cutoff = max(x.shape) * EPS * s[0]
    keep = s > cutoff
    vr = vh[keep].T
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        beta = (vr / s[keep]) @ (u[:, keep].T @ y)
        residual = y - x @ beta
        sse = np.array([math.fsum(float(v) * float(v) for v in residual[:, j])
                        for j in range(y.shape[1])])
        error = float(linalg.norm(c - vr @ (vr.T @ c)))
        bound = float(100 * EPS * max(x.shape) * linalg.norm(c))
        estimable = error <= bound
        status = ("missing_condition" if not present.all() else
                  "ok" if estimable else "contrast_nonestimable")
        defined = np.full(y.shape[1], status == "ok", dtype=bool)
        estimate = (np.array([math.fsum(float(w)*float(v) for w, v in zip(c, beta[:, j]))
                              for j in range(y.shape[1])]) if status == "ok"
                    else np.zeros(y.shape[1]))
    finite_result(beta, sse, estimate, s, cutoff, error, bound)
    return dict(beta=beta, contrast_estimate=estimate, contrast_defined=defined,
                contrast_estimable=bool(estimable), status=status,
                design_rank=int(keep.sum()), residual_df=len(x)-int(keep.sum()),
                singular_values=s, rank_cutoff=float(cutoff),
                contrast_rowspace_residual=error, estimability_bound=bound,
                residual_sse=sse)


def complete_summary(values, expected_n=20):
    n = count(expected_n)
    require(isinstance(values, (list, tuple, np.ndarray)) and len(values) == n,
            "complete expected person membership")
    present = [scalar(v) for v in values if v is not None]
    out = dict(n_expected=n, n_defined=len(present), mean=None, sample_sd=None,
               df=None, t=None, p=None, ci95=None)
    if len(present) != n:
        return dict(out, status="incomplete_support")
    if n < 2:
        return dict(out, status="insufficient_n", mean=present[0] if n else None)
    if min(present) == max(present):
        mean = present[0]
        return dict(out, status="zero_variance", mean=mean, sample_sd=0., df=n-1,
                    ci95=[mean, mean])
    mean = math.fsum(present) / n
    deviation = [v - mean for v in present]
    scale = max(map(abs, deviation))
    sd = scale * math.sqrt(math.fsum((d/scale)**2 for d in deviation)/(n-1))
    require(sd > 0, "nonconstant sample SD underflow")
    se = sd / math.sqrt(n)
    t, df = mean / se, n-1
    tail_x = 0. if abs(t) > math.sqrt(np.finfo(float).max-df) else df/(df+t*t)
    p = float(special.betainc(df/2., .5, tail_x))
    half_width = float(stats.t.ppf(.975, df)) * se
    finite_result(mean, sd, t, p, mean-half_width, mean+half_width)
    return dict(out, status="ok", mean=mean, sample_sd=sd, df=df, t=t, p=p,
                ci95=[mean-half_width, mean+half_width])


def paired_summary(model_a, model_b, expected_n=20):
    n = count(expected_n)
    require(len(model_a) == len(model_b) == n, "paired complete membership")
    # Validate BOTH endpoints before null propagation or coercion hides a Boolean.
    a = [None if v is None else scalar(v) for v in model_a]
    b = [None if v is None else scalar(v) for v in model_b]
    delta = [None if x is None or y is None else y-x for x, y in zip(a, b)]
    return complete_summary(delta, n)


def bound(reference, tolerance):
    require(isinstance(tolerance, Tolerance), "explicit tolerance required")
    require(math.isfinite(tolerance.atol) and math.isfinite(tolerance.rtol)
            and tolerance.atol >= 0 and tolerance.rtol >= 0, "invalid tolerance")
    ref = array(reference)
    with np.errstate(over="raise", invalid="raise"):
        result = tolerance.atol + tolerance.rtol * np.abs(ref)
    finite_result(result)
    return result


def check_close(actual, reference, tolerance=FIT_TOL, label="numeric receipt"):
    actual, reference = array(actual), array(reference)
    require(actual.shape == reference.shape, f"{label}: shape mismatch")
    with np.errstate(over="raise", invalid="raise"):
        difference = np.abs(actual-reference)
    require(np.all(difference <= bound(reference, tolerance)), f"{label}: outside public tolerance")


def weighted_sum(values, weights):
    x, w = array(values, 1), array(weights, 1)
    require(x.shape == w.shape and len(x) > 0, "linear receipt axes")
    result = math.fsum(float(a)*float(b) for a, b in zip(x, w))
    finite_result(result)
    return result


def linear_coherence_bound(reference_components, weights, reference_result, submitted_components,
                           component_tol=FIT_TOL, result_tol=FIT_TOL):
    """Propagate declared per-field budgets; never use an observed mismatch.

    For z=w'b, independently serialized b and z can differ by
    e_z + sum(abs(w_j)*e_bj) + 8*eps64*P*sum(abs(w_j*b_sub_j)).
    P is the complete public fit-column count, or R the number of aggregate
    terms; callers supply that complete, unpadded term vector including zeros.
    This is serialization accounting, not independent proof of the source fit.
    """
    b, w, submitted = (array(reference_components, 1), array(weights, 1),
                       array(submitted_components, 1))
    require(b.shape == w.shape == submitted.shape and len(b) > 0, "linear receipt axes")
    eps_b = bound(b, component_tol)
    eps_z = float(bound(reference_result, result_tol))
    budget = eps_z + math.fsum(float(abs(weight)*error) for weight, error in zip(w, eps_b))
    magnitude = math.fsum(abs(float(weight)*float(value)) for weight, value in zip(w, submitted))
    rounding = 8 * EPS * len(b) * magnitude
    finite_result(budget, rounding)
    return budget + rounding


def validate_linear_receipt(actual_components, reference_components, weights, actual_result,
                            component_tol=FIT_TOL, result_tol=FIT_TOL):
    reference_result = weighted_sum(reference_components, weights)
    check_close(actual_components, reference_components, component_tol, "linear components")
    check_close(actual_result, reference_result, result_tol, "linear result")
    reproduced = weighted_sum(actual_components, weights)
    allowance = linear_coherence_bound(reference_components, weights, reference_result, actual_components,
                                       component_tol, result_tol)
    require(abs(scalar(actual_result)-reproduced) <= allowance, "linear serialization incoherence")
    return dict(recomputed=reproduced, allowed_difference=allowance)


def validate_summary(actual, reference, tolerance=GROUP_TOL):
    require(isinstance(actual, dict) and isinstance(reference, dict), "summary object")
    require(set(reference) <= set(actual), "missing summary fields")
    for key in ("status", "n_expected", "n_defined", "df"):
        expected = reference[key]
        if expected is None:
            require(actual[key] is None, f"summary {key}: null required")
        elif isinstance(expected, int):
            require(count(actual[key]) == expected, f"summary {key}: exact count")
        else:
            require(type(actual[key]) is str and actual[key] == expected, "summary status")
    for key in ("mean", "sample_sd", "t", "p", "ci95"):
        if reference[key] is None:
            require(actual[key] is None, f"summary {key}: null required")
        else:
            check_close(actual[key], reference[key], tolerance, f"summary {key}")
    if actual["sample_sd"] is not None:
        require(scalar(actual["sample_sd"]) >= 0, "negative sample SD")
    if actual["p"] is not None:
        require(0 <= scalar(actual["p"]) <= 1, "p outside [0,1]")
    if actual["ci95"] is not None:
        require(actual["ci95"][0] <= actual["ci95"][1], "CI order")
