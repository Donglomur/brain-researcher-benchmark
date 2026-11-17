"""New implementation of the pinned author's delayed-normalization equations.

The source objective is a scalar sum of squared errors passed to least_squares,
which minimizes one half of that scalar squared. This unusual contract is kept.
P (response scaling) and S (stimulus scaling) are distinct recipes. No function
loads data, writes files, changes NumPy global options, or launches a fit on import.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

CATEGORIES = ("BODIES", "BUILDINGS", "FACES", "OBJECTS", "SCENES", "SCRAMBLED")
SOURCE_REVISION = "09cd778fac545d406cba39ba408f0f00fbe39975"
SOURCE_SAMPLE_RATE = 512
SOURCE_MAX_NFEV = 500
SOURCE_OBJECTIVE = "scalar_total_sse_as_one_least_squares_residual"
SOURCE_RUNTIME = {"python": "3.9.7", "numpy": "1.21.3", "scipy": "1.7.1"}
_NAMES = ("shift", "scale", "tau", "n", "sigma", "tau_a")
_INITIAL = (30., 1., .01, 1.5, .15, .07)
_LOWER = (0., .01, .001, .1, 0., .01)
_UPPER = (70., 200., 1., 5., 1., 2.)


class ModelError(ValueError):
    """Invalid inputs or non-finite numerical operation; no silent repair."""


def _mode(scaling):
    if scaling not in ("none", "S", "P"):
        raise ModelError("scaling must be exactly none, S, or P")
    return scaling


def _array(value, dimensions, label):
    try:
        raw = np.asarray(value)
    except (ValueError, TypeError) as exc:
        raise ModelError(label + " must be a rectangular numeric array") from exc
    if raw.dtype.kind not in "fiu" or raw.dtype.kind == "b":
        raise ModelError(label + " must contain real numeric values, not booleans")
    try:
        out = np.asarray(raw, dtype=np.float64)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ModelError(label + " cannot be represented as float64") from exc
    if out.ndim != dimensions or not all(out.shape) or not np.isfinite(out).all():
        raise ModelError(label + " must have finite values and nonempty required dimensions")
    return out


def parameter_spec(scaling="none"):
    """Return fresh names, initialization, lower bounds and upper bounds."""
    _mode(scaling)
    if scaling == "none":
        return _NAMES, np.array(_INITIAL), np.array(_LOWER), np.array(_UPPER)
    names = _NAMES + tuple("sf_" + category.lower() for category in CATEGORIES)
    return names, np.array(_INITIAL + (1.,) * 6), np.array(_LOWER + (.01,) * 6), np.array(_UPPER + (200.,) * 6)


def _parameters(parameters, scaling):
    names, _, lower, upper = parameter_spec(scaling)
    values = _array(parameters, 1, "parameters")
    if values.shape != lower.shape or np.any(values < lower) or np.any(values > upper):
        raise ModelError("parameters must match the named source bounds: " + ",".join(names))
    return values


def _rate(sample_rate):
    if isinstance(sample_rate, (bool, np.bool_)):
        raise ModelError("sample_rate must be a positive finite scalar")
    try:
        value = float(sample_rate)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ModelError("sample_rate must be a positive finite scalar") from exc
    if not math.isfinite(value) or value <= 0:
        raise ModelError("sample_rate must be a positive finite scalar")
    return value


def _windows(pulse_windows, n_samples):
    if pulse_windows is None:
        raise ModelError("S scaling requires explicit source pulse windows")
    try:
        rows = tuple(tuple(row) for row in pulse_windows)
    except TypeError as exc:
        raise ModelError("pulse windows must be one or two onset/offset pairs") from exc
    if len(rows) not in (1, 2):
        raise ModelError("pulse windows must be one or two onset/offset pairs")
    for row in rows:
        if len(row) != 2 or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)) for v in row):
            raise ModelError("pulse-window endpoints must be integer sample indices")
        if not 0 <= row[0] <= row[1] <= n_samples:
            raise ModelError("pulse windows must lie within the complete time course")
    return rows


def stimulus_timecourse(trial, condition, onepulse, twopulse, n_samples=819):
    """Build the original unit-height, half-open pulse stimulus without file I/O.

    Source tables are supplied explicitly. Fractional endpoint inputs are refused
    rather than silently truncated; admitted original tables have integer indices.
    """
    if isinstance(n_samples, bool) or not isinstance(n_samples, (int, np.integer)) or n_samples < 2:
        raise ModelError("at least two time samples are required")
    if not isinstance(trial, str) or isinstance(condition, bool) or not isinstance(condition, (int, np.integer)):
        raise ModelError("trial must be text and condition an integer row index")
    if "onepulse" in trial:
        table, width = _array(onepulse, 2, "onepulse table"), 2
    elif "twopulse" in trial:
        table, width = _array(twopulse, 2, "twopulse table"), 4
    else:
        raise ModelError("unknown source trial type")
    if table.shape[1] != width or not 0 <= condition < len(table):
        raise ModelError("source condition index/table width mismatch")
    endpoints = table[int(condition)]
    if np.any(endpoints != np.floor(endpoints)):
        raise ModelError("source pulse endpoints must be integer sample indices")
    windows = _windows(tuple((int(endpoints[i]), int(endpoints[i + 1])) for i in range(0, width, 2)), n_samples)
    result = np.zeros(n_samples, dtype=np.float64)
    for start, stop in windows:
        result[start:stop] = 1.
    return result


def predict(stimulus, parameters, *, scaling="none", category=None,
            pulse_windows=None, sample_rate=SOURCE_SAMPLE_RATE, components=False):
    """Predict one trace using normalized discrete source kernels.

    Delay is int(shift) samples, despite the old source docstring saying seconds.
    Kernel length equals trace length. Convolutions are causal prefixes of full
    convolution, with no extra dt multiplier. S reconstructs only the declared
    pulse intervals; P multiplies the final response. Returned drive/denominator
    have the author's unscaled-component meaning even in mode P.
    """
    scaling = _mode(scaling)
    stim = _array(stimulus, 1, "stimulus")
    if len(stim) < 2:
        raise ModelError("at least two time samples are required")
    p = _parameters(parameters, scaling)
    rate = _rate(sample_rate)
    factor = 1.
    if scaling != "none":
        if category not in CATEGORIES:
            raise ModelError("category must match an original category name")
        factor = p[6 + CATEGORIES.index(category)]
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise", under="ignore"):
            if scaling == "S":
                intervals = _windows(pulse_windows, len(stim))
                selected = np.zeros(len(stim), dtype=np.float64)
                for start, stop in intervals:
                    selected[start:stop] = factor * stim[start:stop]
                stim = selected
            delay = int(p[0])
            shifted = np.pad(stim, (delay, 0), mode="constant")[:len(stim)]
            time = np.arange(len(stim), dtype=np.float64) / rate
            # Shape-two gamma density; retain the source's arithmetic order.
            kernel = (time / p[2]) ** 1 * np.exp(-time / p[2]) / p[2]
            kernel = kernel / np.sum(kernel)
            memory = np.exp(-time / p[5])
            memory = memory / np.sum(memory)
            linear = np.convolve(shifted, kernel, mode="full")[:len(stim)]
            drive = np.abs(linear) ** p[3]
            pool = np.convolve(linear, memory, mode="full")[:len(stim)]
            denominator = p[4] ** p[3] + np.abs(pool) ** p[3]
            response = p[1] * (drive / denominator)
            if scaling == "P":
                response = factor * response
    except (FloatingPointError, OverflowError) as exc:
        raise ModelError("non-finite source DN operation; no epsilon or parameter repair applied") from exc
    if not all(np.isfinite(v).all() for v in (response, drive, denominator, linear)):
        raise ModelError("non-finite source DN result")
    if components:
        return {"response": response, "drive": drive, "numerator": drive,
                "normalization_pool": pool, "denominator": denominator,
                "linear": linear, "semisaturation": float(p[4] ** p[3]),
                "category_scale": float(factor)}
    return response


def _training(X, y, scaling, categories, pulse_windows):
    stimuli = _array(X, 2, "X")
    responses = _array(y, 2, "y")
    if stimuli.shape != responses.shape or stimuli.shape[1] < 2:
        raise ModelError("X and y must have identical nonempty trace shapes")
    if scaling == "none":
        cats = [None] * len(stimuli)
    else:
        if categories is None or len(categories) != len(stimuli) or any(c not in CATEGORIES for c in categories):
            raise ModelError("one exact category is required per training trace")
        cats = list(categories)
    if scaling == "S":
        if pulse_windows is None or len(pulse_windows) != len(stimuli):
            raise ModelError("one pulse-window sequence is required per training trace")
        windows = [_windows(w, stimuli.shape[1]) for w in pulse_windows]
    else:
        windows = [None] * len(stimuli)
    return stimuli, responses, cats, windows


def objective(parameters, X, y, *, scaling="none", categories=None,
              pulse_windows=None, sample_rate=SOURCE_SAMPLE_RATE):
    """Return scalar total SSE, exactly the quantity passed by the source fitter."""
    scaling = _mode(scaling)
    stimuli, responses, cats, windows = _training(X, y, scaling, categories, pulse_windows)
    total = np.float64(0.)
    try:
        with np.errstate(over="raise", invalid="raise"):
            for stimulus, response, category, intervals in zip(stimuli, responses, cats, windows):
                prediction = predict(stimulus, parameters, scaling=scaling, category=category,
                                     pulse_windows=intervals, sample_rate=sample_rate)
                total = total + np.sum((prediction - response) ** 2)
    except (FloatingPointError, OverflowError) as exc:
        raise ModelError("non-finite scalar SSE") from exc
    if not np.isfinite(total):
        raise ModelError("non-finite scalar SSE")
    return float(total)


@dataclass(frozen=True)
class FitResult:
    parameter_names: tuple[str, ...]
    parameters: np.ndarray
    scaling: str
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    cost: float
    optimality: float
    objective_sse: float
    solver_options: dict[str, Any]
    scipy_version: str

    def as_dict(self):
        return {"parameter_names": list(self.parameter_names), "parameters": self.parameters.tolist(),
                "scaling": self.scaling, "success": self.success, "status": self.status,
                "message": self.message, "nfev": self.nfev, "njev": self.njev,
                "cost": self.cost, "optimality": self.optimality, "objective_sse": self.objective_sse,
                "objective_contract": SOURCE_OBJECTIVE, "solver_options": dict(self.solver_options),
                "runtime_scipy": self.scipy_version, "source_runtime": dict(SOURCE_RUNTIME),
                "source_default_max_nfev_preserved": self.solver_options["max_nfev"] == SOURCE_MAX_NFEV,
                "historical_runtime_parity": False}


def fit(X, y, *, scaling="none", categories=None, pulse_windows=None,
        sample_rate=SOURCE_SAMPLE_RATE, max_nfev=SOURCE_MAX_NFEV):
    """Explicitly run one source-recipe fit; never warm-start from another fold.

    The caller must enforce its own admitted wall/CPU/resource envelope. The
    supplied response columns/exposure are caller-owned and recorded upstream.
    Small max_nfev values are supported for generated controls, and are labeled.
    """
    import scipy
    from scipy.optimize import least_squares

    scaling = _mode(scaling)
    if isinstance(max_nfev, bool) or not isinstance(max_nfev, (int, np.integer)) or not 1 <= max_nfev <= SOURCE_MAX_NFEV:
        raise ModelError("max_nfev must be an integer from 1 through the source limit500")
    _rate(sample_rate)
    stimuli, responses, cats, windows = _training(X, y, scaling, categories, pulse_windows)
    names, initial, lower, upper = parameter_spec(scaling)
    # Explicit SciPy1.7.1 defaults prevent a newer x_scale default changing them.
    options = {"jac": "2-point", "method": "trf", "ftol": 1e-8, "xtol": 1e-8,
               "gtol": 1e-8, "x_scale": 1., "loss": "linear", "f_scale": 1.,
               "diff_step": None, "tr_solver": None, "tr_options": {},
               "jac_sparsity": None, "max_nfev": int(max_nfev), "verbose": 0}

    def scalar_sse(parameters):
        return objective(parameters, stimuli, responses, scaling=scaling, categories=cats,
                         pulse_windows=windows, sample_rate=sample_rate)

    try:
        answer = least_squares(scalar_sse, initial, bounds=(lower, upper), **options)
        values = _parameters(answer.x, scaling).copy()
        sse = scalar_sse(values)
        scalars = (answer.cost, answer.optimality, sse)
        if not all(math.isfinite(float(v)) for v in scalars):
            raise ModelError("non-finite optimizer diagnostic")
    except ModelError:
        raise
    except (ValueError, FloatingPointError, OverflowError) as exc:
        raise ModelError("source least-squares fit failed: " + str(exc)) from exc
    values.setflags(write=False)
    return FitResult(names, values, scaling, bool(answer.success), int(answer.status),
                     str(answer.message), int(answer.nfev), None if answer.njev is None else int(answer.njev),
                     float(answer.cost), float(answer.optimality), sse, options, scipy.__version__)
