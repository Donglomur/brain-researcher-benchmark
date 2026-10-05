"""Instrumented, explicitly specified DIPY 1.12.1 tensor fitting recipes.

The free-water initialization and LM recipe adapt dipy.reconst.fwdti.
Copyright (c) 2008-2026, dipy developers. BSD-3-Clause; see
THIRD_PARTY_LICENSES.md. Unlike the convenience fit wrapper, retain the fitted
intercept, optimizer termination, unmodified tensor, and skipped/failed rows.
"""
from __future__ import annotations

import warnings
import numpy as np
from scipy.optimize import leastsq

MODELS = ("fwdti", "dti_b2000", "dti_b1000")
DIS0, MDREG, FW_MIN_SIGNAL, DTI_MIN_SIGNAL = .003, .0027, 1e-6, 1e-4
COEFFICIENT_NAMES = ("Dxx", "Dxy", "Dyy", "Dxz", "Dyz", "Dzz", "neg_log_S0")
LM_SETTINGS = dict(ftol=1.49012e-8, xtol=1.49012e-8, gtol=0., maxfev=1800,
                   epsfcn=None, factor=100., diag=None)
STATUSES = ("ok", "invalid_input", "insufficient_signal", "md_threshold",
            "initialization_failed", "high_initial_fraction", "optimizer_failed",
            "nonfinite_candidate", "decomposition_failed")


def tensor_matrix(coefficients):
    q = np.asarray(coefficients, float)
    result = np.empty(q.shape[:-1] + (3, 3))
    result[..., 0, 0] = q[..., 0]; result[..., 0, 1] = result[..., 1, 0] = q[..., 1]
    result[..., 1, 1] = q[..., 2]; result[..., 0, 2] = result[..., 2, 0] = q[..., 3]
    result[..., 1, 2] = result[..., 2, 1] = q[..., 4]; result[..., 2, 2] = q[..., 5]
    return result


def lower_tensor(tensor):
    matrix = np.asarray(tensor)
    return matrix[..., (0, 0, 1, 0, 1, 2), (0, 1, 1, 2, 2, 2)]


def tensor_metrics(beta, eigen_floor):
    """Reported tensor has explicitly floored eigenvalues; raw beta is unchanged."""
    raw_evals, vectors = np.linalg.eigh(tensor_matrix(beta))
    values = np.maximum(raw_evals, eigen_floor)
    md = np.mean(values, axis=-1)
    denominator = np.sum(values**2, axis=-1)
    numerator = 1.5*np.sum((values-md[..., None])**2, axis=-1)
    fa = np.sqrt(np.divide(numerator, denominator, out=np.zeros_like(denominator),
                           where=denominator > 0))
    reported = (vectors*values[..., None, :]) @ np.swapaxes(vectors, -1, -2)
    return dict(fa=fa, md=md, raw_eigenvalues=raw_evals, reported_tensor=lower_tensor(reported),
                n_eigenvalues_clipped=np.sum(raw_evals < eigen_floor, axis=-1),
                nonzero_tensor=denominator > 0)


def predict(beta, fraction, design):
    """Unfloored raw-candidate prediction, preserving the fitted negative log S0."""
    beta = np.asarray(beta, float)
    isotropic = np.array([DIS0, 0., DIS0, 0., 0., DIS0, beta[6]])
    return (1-fraction)*np.exp(design @ beta) + fraction*np.exp(design @ isotropic)


def residual(q, design, signal):
    fraction = .5*(1+np.sin(q[7]-np.pi/2))
    return signal - predict(q[:7], fraction, design)


def prediction_jacobian(beta, fraction, design):
    """Derivative of raw prediction in physical beta/f coordinates (not periodic ft)."""
    tissue = np.exp(design @ beta)
    iso = np.exp(design @ np.array([DIS0, 0., DIS0, 0., 0., DIS0, beta[6]]))
    derivative = (1-fraction)*tissue[:, None]*design
    derivative[:, 6] -= fraction*iso
    return np.column_stack((derivative, iso-tissue))


def base_record(n_volumes):
    return dict(status="invalid_input", fit_attempted=False, eligible=False,
                beta=np.full(7, np.nan), f=np.nan, S0_hat=np.nan, fa=np.nan, md=np.nan,
                sse=np.nan, nrmse=np.nan, n_eigenvalues_clipped=None,
                optimizer_status=None, nfev=0, init_f=np.nan, init_md=np.nan,
                n_signal_floored=0, observed_b0=np.nan, normalization_scale=np.nan,
                boundary_f_low=False, boundary_f_high=False,
                prediction=np.full(n_volumes, np.nan), residual=np.full(n_volumes, np.nan),
                reported_prediction=np.full(n_volumes, np.nan),
                initial_beta=np.full(7, np.nan), initial_raw_beta=np.full(7, np.nan),
                initial_prediction=np.full(n_volumes, np.nan), initial_ft=np.nan,
                optimizer_q=np.full(8, np.nan), raw_eigenvalues=np.full(3, np.nan),
                reported_tensor=np.full(6, np.nan), scaled_jacobian_singular_values=np.full(8, np.nan),
                jacobian_rank=None, jacobian_condition=np.nan, optimizer_message="",
                warnings=[], eigen_floor=np.nan)


def fw_initialization(design, signal, b0):
    """DIPY's observed-signal-squared WLS and 9/19/19 fraction grid, instrumented.

    This is not the OLS-predicted weighting used by the DTI control recipes.
    The >= mdreg boundary is explicitly classified rather than fitting DIPY's
    exactly-equal-to-mdreg zero sentinel as a tissue initialization.
    """
    weighted = design.T @ np.diag(signal**2)
    solver = np.linalg.pinv(weighted @ design, rcond=1e-15) @ weighted
    preliminary = solver @ np.log(np.maximum(signal, FW_MIN_SIGNAL))
    md = float(np.mean(preliminary[[0, 2, 5]]))
    initial = dict(status="ok", md=md, fraction=np.nan, beta=np.full(7, np.nan),
                   raw_beta=np.full(7, np.nan), preliminary_beta=preliminary)
    if np.mean(signal) <= FW_MIN_SIGNAL or b0 <= FW_MIN_SIGNAL:
        initial.update(status="insufficient_signal", fraction=1. if md > MDREG else 0.)
        return initial
    if not np.isfinite(preliminary).all():
        initial["status"] = "initialization_failed"; return initial
    if md >= MDREG:
        initial.update(status="md_threshold", fraction=1. if md > MDREG else 0.)
        return initial
    isotropic = np.exp(design @ np.array([DIS0, 0., DIS0, 0., 0., DIS0, 0.]))
    precision, lower, upper, number = 1., 0., 1., 9
    for _ in range(3):
        precision *= .1
        fractions = np.linspace(lower+precision, upper-precision, num=number)
        observed = np.tile(signal[:, None], (1, number))
        fs = np.tile(fractions, (len(signal), 1))
        water = np.tile(isotropic[:, None], (1, number))
        adjusted = observed-fs*b0*water
        adjusted[adjusted <= 0] = FW_MIN_SIGNAL
        candidates = solver @ np.log(adjusted/(1-fs))
        predicted = (1-fs)*np.exp(design @ candidates)+fs*b0*water
        errors = np.sum((observed-predicted)**2, axis=0)
        if not np.isfinite(errors).all():
            initial["status"] = "initialization_failed"; return initial
        best = int(np.argmin(errors)); raw_beta = candidates[:, best]; fraction = fractions[best]
        lower, upper, number = fraction-precision, fraction+precision, 19
    metrics = tensor_metrics(raw_beta, 0.)
    # The NLS start deliberately uses observed b0, as in DIPY, not WLS intercept.
    beta = np.r_[metrics["reported_tensor"], -np.log(b0)]
    initial.update(beta=beta, raw_beta=raw_beta, fraction=float(fraction))
    if fraction >= .99: initial["status"] = "high_initial_fraction"
    return initial


def finalize(record, signal, design, eigen_floor, is_free_water=True):
    record["eigen_floor"] = float(eigen_floor)
    beta, fraction = record["beta"], record["f"]
    if not np.isfinite(beta).all() or not np.isfinite(fraction):
        if record["fit_attempted"]: record["status"] = "nonfinite_candidate"
        return record
    try:
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            prediction = predict(beta, fraction, design)
            fitted_b0 = float(np.exp(-beta[6]))
        record["S0_hat"] = fitted_b0
        record["prediction"] = prediction
        record["residual"] = signal-prediction
        metrics = tensor_metrics(beta, eigen_floor)
        for key in ("fa", "md", "raw_eigenvalues", "reported_tensor", "n_eigenvalues_clipped"):
            record[key] = metrics[key]
        report_beta = np.r_[metrics["reported_tensor"], beta[6]]
        record["reported_prediction"] = predict(report_beta, fraction, design)
        record["boundary_f_low"] = bool(fraction <= 1e-6)
        record["boundary_f_high"] = bool(fraction >= 1-1e-6)
        if not np.isfinite(prediction).all() or not np.isfinite(fitted_b0) or fitted_b0 <= 0:
            record["status"] = "nonfinite_candidate"; return record
        record["sse"] = float(np.sum(record["residual"]**2))
        record["nrmse"] = float(np.sqrt(record["sse"]/len(signal))/record["normalization_scale"])
        if not np.isfinite(record["sse"]):
            record["status"] = "nonfinite_candidate"; return record
        record["eligible"] = bool(record["status"] == "ok" and 0 <= fraction < 1
                                   and metrics["nonzero_tensor"] and np.isfinite(record["sse"]))
        # Dimensionless coordinate scaling is declared and diagnostic, never an exclusion.
        jac = prediction_jacobian(beta, fraction, design)/record["normalization_scale"]
        jac *= np.array([.001]*6+[1., 1.])[None, :]
        if not is_free_water:
            jac = jac[:, :7]
        singular = np.linalg.svd(jac, compute_uv=False)
        record["scaled_jacobian_singular_values"][:len(singular)] = singular
        record["jacobian_rank"] = int(np.count_nonzero(singular > singular[0]*1e-12)) if singular[0] else 0
        record["jacobian_condition"] = float(singular[0]/singular[-1]) if singular[-1] > 0 else np.inf
    except np.linalg.LinAlgError as exc:
        record["status"] = "decomposition_failed"; record["eligible"] = False
        record["optimizer_message"] += "; "+str(exc)
    return record


def fit_free_water(signal, design, b0_mask):
    signal = np.asarray(signal, float); record = base_record(len(signal))
    if signal.ndim != 1 or not np.isfinite(signal).all() or np.any(signal < 0): return record
    b0 = float(np.mean(signal[b0_mask]))
    record.update(observed_b0=b0, normalization_scale=max(b0, FW_MIN_SIGNAL),
                  n_signal_floored=int(np.count_nonzero(signal < FW_MIN_SIGNAL)))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            initial = fw_initialization(design, signal, b0)
            record.update(init_f=initial["fraction"], init_md=initial["md"],
                          initial_beta=initial["beta"], initial_raw_beta=initial["raw_beta"],
                          status=initial["status"])
            if np.isfinite(initial["beta"]).all():
                record["initial_prediction"] = predict(initial["beta"], initial["fraction"], design)
            if initial["status"] == "ok":
                initial_ft = float(np.arcsin(2*initial["fraction"]-1)+np.pi/2)
                record["initial_ft"] = initial_ft
                record["fit_attempted"] = True
                q, _, information, message, ier = leastsq(
                    residual, np.r_[initial["beta"], initial_ft], args=(design, signal),
                    Dfun=None, full_output=True, col_deriv=False, **LM_SETTINGS)
                record.update(beta=q[:7], f=float(.5*(1+np.sin(q[7]-np.pi/2))), optimizer_q=q,
                              optimizer_status=int(ier), nfev=int(information["nfev"]),
                              optimizer_message=str(message), status="ok" if ier in (1, 2, 3, 4) else "optimizer_failed")
                finalize(record, signal, design, 0.)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            record["status"] = "optimizer_failed" if record["fit_attempted"] else "initialization_failed"
            record["optimizer_message"] = str(exc)
        record["warnings"] = [{"category": w.category.__name__, "message": str(w.message)} for w in caught]
    return record


def dti_wls_beta(signals, design):
    """DIPY's two-pass WLS; retain raw coefficients before eigenvalue flooring."""
    signal = np.maximum(np.asarray(signals, float), DTI_MIN_SIGNAL)
    logs = np.log(signal)
    first = logs @ np.linalg.pinv(design, rcond=1e-15).T
    weights = np.exp(first @ design.T)
    weighted_design = design[None, :, :]*weights[:, :, None]
    return np.einsum("nij,nj->ni", np.linalg.pinv(weighted_design, rcond=1e-15), weights*logs)


def fit_dti(signals, design, b0_mask, chunk_size=256):
    signals = np.asarray(signals, float)
    records = []
    eigen_floor = 1e-6/(-float(design.min()))
    for start in range(0, len(signals), chunk_size):
        selected = signals[start:start+chunk_size]
        valid = np.isfinite(selected).all(axis=1) & (selected >= 0).all(axis=1)
        beta = np.full((len(selected), 7), np.nan)
        beta[valid] = dti_wls_beta(selected[valid], design)
        for signal, candidate, input_ok in zip(selected, beta, valid):
            record = base_record(len(signal))
            if input_ok:
                b0 = float(np.mean(signal[b0_mask]))
                record.update(status="ok", fit_attempted=True, beta=candidate, f=0.,
                              observed_b0=b0, normalization_scale=max(b0, FW_MIN_SIGNAL),
                              n_signal_floored=int(np.count_nonzero(signal < DTI_MIN_SIGNAL)))
                finalize(record, signal, design, eigen_floor, is_free_water=False)
            records.append(record)
    return records
