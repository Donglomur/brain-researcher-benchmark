"""Source-bound arithmetic checks and independently implemented fit diagnostics.

Does not import the oracle or verifier. Source reading, median_otsu, Gaussian
filtering, NumPy/SciPy linear algebra and optimizers are shared libraries. The
design, WLS, free-water initialization, analytic Jacobian, tensor summaries and
report calculations are separate implementations. Alternative nonlinear optima
are diagnostics, not a tissue-truth or automatic fixed-recipe equivalence test.
"""
import argparse
import csv
import hashlib
import json
import math
import warnings
from collections import Counter
from itertools import combinations
from pathlib import Path

import nibabel as nib
import numpy as np
import scipy
from scipy import linalg, ndimage, optimize
from dipy.segment.mask import median_otsu

MANIFEST_SHA256 = "f59a83a45da820308010d02ea93a29291df1bee117a66f399ddc95978c6be2fa"
PIPELINE_ID = "sherbrooke-proxy-fa-v2"
MODELS = ("fwdti", "dti_b2000", "dti_b1000")
DIS0 = 0.003
FWHM_VOXELS = 0.625
SIGMA_VOXELS = FWHM_VOXELS / np.sqrt(8 * np.log(2))
PINV_RCOND = 1e-15


def design_matrix(bvals, bvecs):
    """Explicit tensor order: xx, xy, yy, xz, yz, zz, negative-log S0."""
    bvals = np.asarray(bvals, float)
    g = np.asarray(bvecs, float)
    if g.shape != (len(bvals), 3) or not np.isfinite(g).all():
        raise ValueError("Invalid gradient array")
    x, y, z = g.T
    return -np.column_stack((bvals*x*x, 2*bvals*x*y, bvals*y*y,
                             2*bvals*x*z, 2*bvals*y*z, bvals*z*z,
                             np.ones(len(bvals))))


def unpack_tensor(coeff):
    coeff = np.asarray(coeff)
    result = np.empty(coeff.shape[:-1] + (3, 3), dtype=float)
    result[..., 0, 0] = coeff[..., 0]
    result[..., 0, 1] = result[..., 1, 0] = coeff[..., 1]
    result[..., 1, 1] = coeff[..., 2]
    result[..., 0, 2] = result[..., 2, 0] = coeff[..., 3]
    result[..., 1, 2] = result[..., 2, 1] = coeff[..., 4]
    result[..., 2, 2] = coeff[..., 5]
    return result


def pack_tensor(tensor):
    return np.asarray(tensor)[..., (0, 0, 1, 0, 1, 2), (0, 1, 1, 2, 2, 2)]


def tensor_summary(coeff, floor):
    eig, vectors = np.linalg.eigh(unpack_tensor(coeff))
    clipped = np.maximum(eig, floor)
    md = clipped.mean(axis=-1)
    denominator = np.square(clipped).sum(axis=-1)
    numerator = 1.5 * np.square(clipped-md[..., None]).sum(axis=-1)
    fa = np.sqrt(np.divide(numerator, denominator, out=np.zeros_like(md), where=denominator > 0))
    reported = (vectors * clipped[..., None, :]) @ np.swapaxes(vectors, -1, -2)
    return {"raw_eigenvalues": eig[..., ::-1], "eigenvalues": clipped[..., ::-1],
            "fa": fa, "md": md, "clipped": np.any(eig < floor, axis=-1),
            "reported_tensor": reported}


def dti_wls(signal, design, chunk_size=1024):
    """Two-pass OLS-predicted-weight WLS, independent from DIPY's wrapper."""
    signal = np.atleast_2d(np.asarray(signal, float))
    result = np.empty((len(signal), 7), float)
    inverse = np.linalg.pinv(design, rcond=PINV_RCOND)
    for begin in range(0, len(signal), chunk_size):
        logarithm = np.log(np.maximum(signal[begin:begin+chunk_size], 1e-4))
        ols = logarithm @ inverse.T
        weight = np.exp(ols @ design.T)
        weighted_design = design[None, :, :] * weight[..., None]
        result[begin:begin+chunk_size] = np.einsum(
            "nij,nj->ni", np.linalg.pinv(weighted_design, rcond=PINV_RCOND), weight*logarithm)
    return result


def dti_lstsq(signal, design):
    """Separate SciPy least-squares solve for a small deterministic sample."""
    logarithm = np.log(np.maximum(np.asarray(signal), 1e-4))
    ols = linalg.lstsq(design, logarithm, cond=PINV_RCOND, lapack_driver="gelsd")[0]
    weight = np.exp(design @ ols)
    return linalg.lstsq(design*weight[:, None], logarithm*weight,
                        cond=PINV_RCOND, lapack_driver="gelsd")[0]


def fw_prediction(parameters, design):
    parameters = np.asarray(parameters, float)
    fraction = 0.5 * (1 - np.cos(parameters[7]))
    tissue = np.exp(design @ parameters[:7])
    isotropic_parameters = np.array([DIS0, 0, DIS0, 0, 0, DIS0, parameters[6]])
    water = np.exp(design @ isotropic_parameters)
    return (1-fraction)*tissue + fraction*water


def fw_jacobian(parameters, design):
    """Derivative of prediction, not residual data-minus-prediction."""
    fraction = 0.5 * (1 - np.cos(parameters[7]))
    tissue = np.exp(design @ parameters[:7])
    water = np.exp(design @ np.array([DIS0, 0, DIS0, 0, 0, DIS0, parameters[6]]))
    result = np.empty((len(design), 8))
    result[:, :6] = ((1-fraction)*tissue)[:, None]*design[:, :6]
    result[:, 6] = -((1-fraction)*tissue + fraction*water)
    result[:, 7] = 0.5*np.sin(parameters[7])*(water-tissue)
    return result


def physical_jacobian(beta, fraction, design):
    """Prediction Jacobian in tensor/intercept/f coordinates for reported QC."""
    tissue = np.exp(design @ beta)
    water = np.exp(design @ np.array([DIS0, 0, DIS0, 0, 0, DIS0, beta[6]]))
    jacobian = np.empty((len(design), 8))
    jacobian[:, :6] = ((1-fraction)*tissue)[:, None]*design[:, :6]
    jacobian[:, 6] = -((1-fraction)*tissue+fraction*water)
    jacobian[:, 7] = water-tissue
    return jacobian


def physical_prediction(beta, fraction, design):
    return ((1-fraction)*np.exp(design @ beta)
            + fraction*np.exp(design @ np.array([DIS0, 0, DIS0, 0, 0, DIS0, beta[6]])))


def fw_initializer(signal, design, b0):
    """Observed-signal-squared WLS and 9/19/19 fraction grids, explicitly coded."""
    signal = np.asarray(signal, float)
    result = {"status": "nonfinite_signal", "parameters": None, "fraction": None, "md": None}
    if not np.isfinite(signal).all() or not np.isfinite(b0):
        return result
    weighted_transpose = design.T * np.square(signal)[None, :]
    projector = np.linalg.pinv(weighted_transpose @ design, rcond=PINV_RCOND) @ weighted_transpose
    initial_dti = projector @ np.log(np.maximum(signal, 1e-6))
    md = float(initial_dti[[0, 2, 5]].mean())
    result.update(md=md, preliminary_beta=initial_dti)
    if signal.mean() <= 1e-6 or b0 <= 1e-6:
        result["status"] = "low_signal"
        return result
    if not md < 0.0027:
        result["status"] = "wls_sentinel"
        result["fraction"] = 1.0 if md > 0.0027 else 0.0
        return result
    isotropic = np.exp(design @ np.array([DIS0, 0, DIS0, 0, 0, DIS0, 0]))
    low, high, step = 0.0, 1.0, 1.0
    for samples in (9, 19, 19):
        step *= 0.1
        fractions = np.linspace(low+step, high-step, samples)
        signal_minus_water = signal[:, None] - b0*isotropic[:, None]*fractions[None, :]
        signal_minus_water[signal_minus_water <= 0] = 1e-6
        logs = np.log(signal_minus_water/(1-fractions)[None, :])
        parameters = projector @ logs
        predictions = ((1-fractions)[None, :]*np.exp(design @ parameters)
                       + b0*isotropic[:, None]*fractions[None, :])
        best = np.argmin(np.square(predictions-signal[:, None]).sum(axis=0))
        coefficients = parameters[:, best]
        fraction = float(fractions[best])
        low, high = fraction-step, fraction+step
    summary = tensor_summary(coefficients, 0)
    start = np.r_[pack_tensor(summary["reported_tensor"]), -np.log(b0),
                  np.arcsin(2*fraction-1)+np.pi/2]
    result.update(status="initial_fraction_skip" if fraction >= 0.99 else "ready",
                  parameters=start, fraction=fraction,
                  raw_beta=coefficients, eigen_clipped=bool(summary["clipped"]))
    return result


def fit_alternatives(signal, design, b0):
    """Different numerical methods; differences remain visible, not filtered out."""
    initial = fw_initializer(signal, design, b0)
    result = {"initializer": initial, "lm": None, "trf": None}
    if initial["status"] != "ready":
        return result
    residual = lambda p: (fw_prediction(p, design)-signal)/b0
    jacobian = lambda p: fw_jacobian(p, design)/b0
    for method in ("lm", "trf"):
        diagnostic = {"method": method, "converged": False}
        caught = []
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                if method == "lm":
                    parameters, _, info, message, status = optimize.leastsq(
                        residual, initial["parameters"], Dfun=jacobian, full_output=True,
                        ftol=1.49012e-8, xtol=1.49012e-8, gtol=0, maxfev=1800,
                        epsfcn=None, factor=100, diag=None)
                    converged, nfev = status in (1, 2, 3, 4), int(info["nfev"])
                else:
                    fit = optimize.least_squares(
                        residual, initial["parameters"], jac=jacobian, method="trf",
                        x_scale=np.r_[np.full(6, 0.001), 1.0, 1.0],
                        ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=1800,
                        loss="linear", tr_solver="exact")
                    parameters, message, status = fit.x, fit.message, int(fit.status)
                    converged, nfev = bool(fit.success), int(fit.nfev)
            prediction = fw_prediction(parameters, design)
            diagnostic.update(parameters=parameters, prediction=prediction, status=int(status),
                              message=str(message), converged=converged, nfev=nfev,
                              warnings=[str(item.message) for item in caught],
                              normalized_sse=float(np.sum(((prediction-signal)/b0)**2)),
                              fraction=float(0.5*(1-np.cos(parameters[7]))),
                              fitted_s0=float(np.exp(-parameters[6])))
            if np.isfinite(parameters).all():
                summary = tensor_summary(parameters[:6], 0)
                singular = np.linalg.svd(jacobian(parameters)*np.r_[np.full(6, .001), 1., 1.], compute_uv=False)
                diagnostic.update(fa=float(summary["fa"]), eigen_clipped=bool(summary["clipped"]),
                                  jacobian_singular_values=singular,
                                  jacobian_rank=int(np.sum(singular > singular[0]*max(design.shape[0], 8)*np.finfo(float).eps)),
                                  jacobian_condition=float(singular[0]/singular[-1]) if singular[-1] > 0 else None)
        except Exception as exc:
            diagnostic["error"] = f"{type(exc).__name__}: {exc}"
            diagnostic["warnings"] = [str(item.message) for item in caught]
        result[method] = diagnostic
    return result


def json_safe(value):
    """Keep undefined diagnostics visible as null, never write nonstandard NaN."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


class Checks:
    def __init__(self):
        self.items = []
        self.issues = []

    def require(self, name, condition, detail=None):
        item = {"name": name, "passed": bool(condition)}
        if detail is not None:
            item["detail"] = json_safe(detail)
        self.items.append(item)
        if not condition:
            self.issues.append(name)
        return bool(condition)

    def close(self, name, actual, expected, atol=1e-10, rtol=1e-9):
        actual, expected = np.asarray(actual), np.asarray(expected)
        if actual.shape != expected.shape:
            return self.require(name, False, {"actual_shape": actual.shape, "expected_shape": expected.shape})
        close = np.isclose(actual, expected, atol=atol, rtol=rtol, equal_nan=True)
        finite = np.isfinite(actual) & np.isfinite(expected)
        detail = {"atol": atol, "rtol": rtol, "elements": actual.size,
                  "disagreements": int(np.count_nonzero(~close)),
                  "max_abs_difference": float(np.max(np.abs(actual[finite].astype(float)-expected[finite].astype(float)))) if finite.any() else None}
        return self.require(name, close.all(), detail)


def reconstruct_fitted_fields(beta, fraction, signal, design, model):
    """Pure source/parameter arithmetic, including finite failed candidates."""
    if model not in MODELS:
        raise ValueError("Unknown model")
    beta, signal = np.asarray(beta, float), np.asarray(signal, float)
    if beta.shape != (7,) or not np.isfinite(beta).all() or not np.isfinite(fraction):
        return None
    scale = max(float(signal[np.all(design[:, :6] == 0, axis=1)].mean()), 1e-6)
    floor = 0.0 if model == "fwdti" else 1e-6/(-design.min())
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        prediction = physical_prediction(beta, fraction, design)
        s0 = float(np.exp(-beta[6]))
    if not np.isfinite(prediction).all() or not np.isfinite(s0) or s0 <= 0:
        return {"candidate_finite": False, "prediction": prediction, "S0_hat": s0}
    summary = tensor_summary(beta[:6], floor)
    residual = signal-prediction
    sse = float(np.sum(residual**2))
    reported_beta = np.r_[pack_tensor(summary["reported_tensor"]), beta[6]]
    jacobian = physical_jacobian(beta, fraction, design)/scale
    if model != "fwdti":
        jacobian = jacobian[:, :7]
    jacobian = jacobian*np.r_[np.full(6, .001), np.ones(jacobian.shape[1]-6)][None, :]
    singular = np.linalg.svd(jacobian, compute_uv=False)
    return {"candidate_finite": True, "prediction": prediction, "S0_hat": s0,
            "residual": residual, "sse": sse, "nrmse": np.sqrt(sse/len(signal))/scale,
            "normalization_scale": scale, "fa": float(summary["fa"]), "md": float(summary["md"]),
            "raw_eigenvalues": summary["raw_eigenvalues"][::-1],
            "reported_tensor": pack_tensor(summary["reported_tensor"]),
            "n_eigenvalues_clipped": int(np.count_nonzero(summary["raw_eigenvalues"] < floor)),
            "reported_prediction": physical_prediction(reported_beta, fraction, design),
            "nonzero_tensor": bool(np.square(summary["eigenvalues"]).sum() > 0),
            "boundary_f_low": fraction <= 1e-6, "boundary_f_high": fraction >= 1-1e-6,
            "scaled_jacobian_singular_values": singular, "jacobian_parameter_count": len(singular),
            "jacobian_rank": int(np.count_nonzero(singular > singular[0]*1e-12)) if singular[0] else 0,
            "jacobian_condition": float(singular[0]/singular[-1]) if singular[-1] > 0 else np.inf}


def compute_summaries(records_by_model, main_model):
    """Source-validated record summaries, retaining all model-specific failures."""
    models = sorted(records_by_model)
    count = len(records_by_model[models[0]])
    valid = {model: np.array([row["eligible"] for row in records_by_model[model]], bool) for model in models}
    if any(len(mask) != count for mask in valid.values()):
        raise ValueError("Models do not cover the same ROI")
    common = np.logical_and.reduce(list(valid.values()))
    fields = ("fa", "md", "f", "S0_hat", "nrmse")

    def mean(values):
        return math.fsum(map(float, values))/len(values) if len(values) else None

    def means(model, mask):
        return {key+"_mean": mean([row[key] for row, keep in zip(records_by_model[model], mask) if keep]) for key in fields}

    by_model, paired = {}, {}
    for model in models:
        rows = records_by_model[model]
        counts = [row.get("n_eigenvalues_clipped") for row in rows]
        finite_counts = [float(value) for value in counts if value is not None and np.isfinite(value)]
        by_model[model] = dict(n_valid=int(valid[model].sum()), **means(model, valid[model]),
                               status_counts=dict(sorted(Counter(row["status"] for row in rows).items())),
                               n_eigenvalues_clipped_total=int(sum(finite_counts)),
                               n_voxels_eigenvalues_clipped=sum(value > 0 for value in finite_counts))
    for left, right in combinations(models, 2):
        paired[right+"_minus_"+left] = mean([right_row["fa"]-left_row["fa"] for left_row, right_row, keep
                                            in zip(records_by_model[left], records_by_model[right], common) if keep])
    return {"status": "ok", "pipeline_id": PIPELINE_ID, "main_model": main_model,
            "n_roi_voxels": count, "n_common_valid": int(common.sum()),
            "fa_proxy_roi": by_model[main_model]["fa_mean"], "by_model": by_model,
            "common_valid": {"n_voxels": int(common.sum()),
                             "by_model": {model: means(model, common) for model in models},
                             "paired_fa_differences": paired}}, common


def check_summary(actual, expected, checks, prefix="results"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            checks.require(prefix, False, "Expected object")
            return
        if prefix.endswith("status_counts"):
            checks.require(prefix, {key: value for key, value in actual.items() if value != 0} == expected)
            return
        if prefix.endswith("by_model") or prefix.endswith("paired_fa_differences"):
            checks.require(prefix+".keys", set(actual) == set(expected))
        for key, value in expected.items():
            if key not in actual:
                checks.require(prefix+"."+key, False, "Missing key")
            else:
                check_summary(actual[key], value, checks, prefix+"."+key)
    elif expected is None or isinstance(expected, (str, bool, int)):
        checks.require(prefix, type(actual) is type(expected) and actual == expected)
    else:
        checks.close(prefix, actual, expected, atol=1e-6, rtol=1e-6)


def read_csv_rows(path, key_fields):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Invalid CSV header: {path.name}")
        rows = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row: {path.name}")
            key = []
            for field in key_fields:
                if field in ("i", "j", "k"):
                    value = float(row[field])
                    if not np.isfinite(value) or not value.is_integer():
                        raise ValueError("Coordinates must be exact integers")
                    key.append(int(value))
                else:
                    key.append(row[field])
            key = tuple(key)
            if key in rows:
                raise ValueError(f"Duplicate CSV identity: {path.name}")
            rows[key] = row
    return rows


def csv_number(value):
    if not value.strip():
        return np.nan
    result = float(value)
    if not np.isfinite(result):
        raise ValueError("Nonfinite CSV literal; use an empty field for undefined values")
    return result


def csv_boolean(value):
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    raise ValueError("Invalid CSV boolean")


def validate_public(output_dir, records, ijk, metadata, checks):
    main = metadata["main_model"]
    expected, common = compute_summaries(records, main)
    expected["status"] = metadata["status"]
    check_summary(json.loads((output_dir/"results.json").read_text()), expected, checks)
    models = sorted(records)
    coordinates = [tuple(map(int, row)) for row in ijk]
    parameter_rows = read_csv_rows(output_dir/"fit_parameters.csv", ("model", "i", "j", "k"))
    sweep_rows = read_csv_rows(output_dir/"fa_sweep.csv", ("model", "i", "j", "k"))
    main_rows = read_csv_rows(output_dir/"fa_voxelwise.csv", ("i", "j", "k"))
    full_keys = {(model, *coord) for model in models for coord in coordinates}
    identities_ok = checks.require("fit_parameters.identities", set(parameter_rows) == full_keys)
    identities_ok &= checks.require("fa_sweep.identities", set(sweep_rows) == full_keys)
    identities_ok &= checks.require("main_fa.identities", set(main_rows) == set(coordinates))
    if not identities_ok:
        return expected
    checks.close("main_fa.values", [csv_number(main_rows[coord]["fa"]) for coord in coordinates],
                 [row["fa"] for row in records[main]], atol=1e-7, rtol=1e-7)
    scalar_fields = ("S0_hat", "f", "fa", "md", "sse", "nrmse", "n_eigenvalues_clipped",
                     "optimizer_status", "nfev", "init_f", "init_md", "n_signal_floored",
                     "observed_b0", "normalization_scale")
    beta_fields = ("Dxx", "Dxy", "Dyy", "Dxz", "Dyz", "Dzz", "neg_log_S0")
    for model in models:
        rows = [parameter_rows[(model, *coord)] for coord in coordinates]
        checks.require(model+".csv_status", [row["status"] for row in rows] == [row["status"] for row in records[model]])
        checks.close(model+".csv_beta", [[csv_number(row[field]) for field in beta_fields] for row in rows],
                     [row["beta"] for row in records[model]], atol=1e-10, rtol=1e-7)
        for field in scalar_fields:
            wanted = [np.nan if row[field] is None else row[field] for row in records[model]]
            checks.close(model+".csv_"+field, [csv_number(row[field]) for row in rows], wanted, atol=1e-7, rtol=1e-7)
        for field in ("fit_attempted", "eligible", "boundary_f_low", "boundary_f_high"):
            checks.require(model+".csv_"+field, [csv_boolean(row[field]) for row in rows] == [row[field] for row in records[model]])
        checks.require(model+".csv_common", [csv_boolean(row["common_valid"]) for row in rows] == list(common))
        checks.close(model+".sweep_fa", [csv_number(sweep_rows[(model, *coord)]["fa"]) for coord in coordinates],
                     [row["fa"] for row in records[model]], atol=1e-7, rtol=1e-7)
    for field in ("n_roi_voxels", "n_common_valid"):
        checks.require("metadata."+field, metadata[field] == expected[field])
    checks.require("findings_nonempty", bool((output_dir/"findings.md").read_text().strip()))
    return expected


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reconstruct_source(data_dir):
    """Recompute masks/ROI without importing any task implementation."""
    manifest_path = data_dir/"data_manifest.json"
    if hash_file(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch")
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["files"]) != 3:
        raise ValueError("Expected exactly three input files")
    paths, hashes = {}, {}
    for record in manifest["files"]:
        path = data_dir/record["path"]
        if path.is_symlink() or path.stat().st_size != record["size_bytes"] or hash_file(path) != record["sha256"]:
            raise ValueError(f"Source identity mismatch: {record['path']}")
        paths[record["role"]], hashes[record["path"]] = path, record["sha256"]
    image = nib.load(paths["image"])
    bvals, bvecs = np.loadtxt(paths["bval"]), np.loadtxt(paths["bvec"])
    if image.shape != (128, 128, 60, 193) or bvecs.shape != (193, 3):
        raise ValueError("Unexpected source shape")
    raw = np.asarray(image.dataobj)
    _, brain = median_otsu(raw[..., 0], median_radius=4, numpass=2, dilate=1, autocrop=False)
    data = raw.astype(np.float64)
    selected = bvals <= 2050
    for volume in np.flatnonzero(selected):
        data[..., volume] = ndimage.gaussian_filter(data[..., volume], SIGMA_VOXELS,
                                                   mode="reflect", truncate=4)
    low = bvals <= 1050
    low_design = design_matrix(bvals[low], bvecs[low])
    brain_coefficients = dti_wls(data[brain][:, low], low_design)
    low_summary = tensor_summary(brain_coefficients, 1e-6/(-low_design.min()))
    fa, md = np.zeros(brain.shape), np.zeros(brain.shape)
    fa[brain], md[brain] = low_summary["fa"], low_summary["md"]
    seed = brain & (md > 0.002) & (fa < 0.2)
    dilation = ndimage.binary_dilation(seed, structure=ndimage.generate_binary_structure(3, 1), iterations=2)
    roi = dilation & brain & ~seed & (md > 0.0008) & (md < 0.0015) & (fa > 0.25)
    ijk = np.argwhere(roi)
    if not len(ijk):
        raise ValueError("Empty source-derived proxy ROI")
    signal = data[roi][:, selected]
    del data
    return {"roi_ijk": ijk, "brain_mask": brain, "seed_mask": seed, "roi_mask": roi,
            "signal": signal, "bvals": bvals[selected], "bvecs": bvecs[selected],
            "raw_signal": raw[roi].astype(float), "volume_indices": np.flatnonzero(selected),
            "original_bvals": bvals, "original_bvecs": bvecs,
            "brain_ijk": np.argwhere(brain), "low_b_coefficients": brain_coefficients,
            "low_b_fa": fa[roi], "low_b_md": md[roi], "source_sha256": hashes,
            "affine": image.affine, "spatial_units": image.header.get_xyzt_units()[0]}


def records_from_arrays(arrays, model):
    count = len(arrays["roi_ijk"])
    suffix = "_"+model
    fields = {key[:-len(suffix)]: arrays[key] for key in arrays if key.endswith(suffix)
              and key[:-len(suffix)] not in ("warnings_json", "signal_indices", "design")}
    if any(len(value) != count for value in fields.values()):
        raise ValueError("Per-model private array length mismatch")
    return [{key: value[index].item() if np.ndim(value[index]) == 0 else value[index].copy()
             for key, value in fields.items()} for index in range(count)]


def validate_model_arithmetic(source, arrays, model, records, checks):
    selected = arrays["selected_roi_indices"]
    indices = np.flatnonzero(source["bvals"] <= (1050 if model == "dti_b1000" else 2050))
    signal = source["signal"][selected][:, indices]
    design = design_matrix(source["bvals"][indices], source["bvecs"][indices])
    checks.require(model+".signal_indices", np.array_equal(arrays["signal_indices_"+model], indices))
    checks.close(model+".design", arrays["design_"+model], design, atol=1e-12, rtol=1e-12)
    fields = ("S0_hat", "fa", "md", "sse", "nrmse", "n_eigenvalues_clipped", "raw_eigenvalues",
              "reported_tensor", "boundary_f_low", "boundary_f_high", "jacobian_rank", "jacobian_condition")
    computed = {key: [] for key in fields}
    expected_predictions, expected_residuals, reported_predictions, singulars = [], [], [], []
    expected_eligibility, updated, invalid_rows = [], [], []
    observed = signal[:, source["bvals"][indices] <= 50].mean(axis=1)
    scales = np.maximum(observed, 1e-6)
    checks.close(model+".observed_b0", [row["observed_b0"] for row in records], observed, atol=1e-10, rtol=1e-10)
    checks.close(model+".normalization_scale", [row["normalization_scale"] for row in records], scales, atol=1e-10, rtol=1e-10)
    checks.close(model+".signal_floor_count", [row["n_signal_floored"] for row in records],
                 np.count_nonzero(signal < (1e-6 if model == "fwdti" else 1e-4), axis=1), atol=0, rtol=0)
    allowed_statuses = {"ok", "invalid_input", "insufficient_signal", "md_threshold", "initialization_failed",
                        "high_initial_fraction", "optimizer_failed", "nonfinite_candidate", "decomposition_failed"}
    checks.require(model+".known_statuses", all(row["status"] in allowed_statuses for row in records))
    if model != "fwdti":
        checks.close(model+".fixed_fraction", [row["f"] for row in records], np.zeros(len(records)), atol=0, rtol=0)
        checks.require(model+".no_nonlinear_optimizer", all(np.isnan(row["optimizer_status"]) and row["nfev"] == 0 for row in records))
    else:
        q = np.asarray([row["optimizer_q"] for row in records])
        checks.close(model+".raw_optimizer_beta", q[:, :7], [row["beta"] for row in records], atol=0, rtol=0)
        checks.close(model+".fraction_transform", 0.5*(1-np.cos(q[:, 7])), [row["f"] for row in records], atol=1e-15, rtol=1e-14)
    convergence_consistent = True
    no_fake_unattempted = True
    for index, (row, y) in enumerate(zip(records, signal)):
        try:
            arithmetic = reconstruct_fitted_fields(row["beta"], row["f"], y, design, model)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            checks.require(model+f".arithmetic_row_{index}", False, f"{type(exc).__name__}: {exc}")
            arithmetic = None
        finite = arithmetic is not None and arithmetic["candidate_finite"]
        eligible = finite and row["status"] == "ok" and arithmetic["nonzero_tensor"] and 0 <= row["f"] < 1
        if model == "fwdti" and row["status"] == "ok":
            convergence_consistent &= row["fit_attempted"] and row["optimizer_status"] in (1, 2, 3, 4)
        if not row["fit_attempted"]:
            no_fake_unattempted &= arithmetic is None and not np.isfinite(row["f"])
        expected_eligibility.append(bool(eligible))
        copy = dict(row)
        copy["eligible"] = bool(eligible)
        if finite:
            for key in fields:
                computed[key].append(arithmetic[key])
                copy[key] = arithmetic[key]
            expected_predictions.append(arithmetic["prediction"])
            expected_residuals.append(arithmetic["residual"])
            reported_predictions.append(arithmetic["reported_prediction"])
            singulars.append(np.pad(arithmetic["scaled_jacobian_singular_values"],
                                   (0, 8-arithmetic["jacobian_parameter_count"]), constant_values=np.nan))
        else:
            for key in fields:
                value = row[key]
                # No candidate metrics may be invented from an initializer.
                desired = False if key.startswith("boundary_") else np.full(np.shape(value), np.nan)
                computed[key].append(desired)
                copy[key] = desired.item() if np.ndim(desired) == 0 and hasattr(desired, "item") else desired
            expected_predictions.append(np.full(len(y), np.nan) if arithmetic is None else arithmetic["prediction"])
            expected_residuals.append(np.full(len(y), np.nan) if arithmetic is None else y-arithmetic["prediction"])
            reported_predictions.append(np.full(len(y), np.nan))
            singulars.append(np.full(8, np.nan))
        if not eligible:
            invalid_rows.append({"row": index, "ijk": arrays["roi_ijk"][index], "status": row["status"],
                                 "fit_attempted": row["fit_attempted"], "optimizer_status": row["optimizer_status"],
                                 "beta": row["beta"], "f": row["f"], "finite_candidate": finite})
        updated.append(copy)
    checks.require(model+".success_requires_convergence", convergence_consistent)
    checks.require(model+".unattempted_final_parameters_undefined", no_fake_unattempted)
    checks.require(model+".eligible", np.array_equal([row["eligible"] for row in records], expected_eligibility))
    for key in fields:
        checks.close(model+"."+key, [row[key] for row in records], computed[key], atol=1e-8, rtol=1e-8)
    for key, expected in (("prediction", expected_predictions), ("residual", expected_residuals),
                          ("reported_prediction", reported_predictions)):
        checks.close(model+"."+key+"_normalized", np.asarray([row[key] for row in records])/scales[:, None],
                     np.asarray(expected)/scales[:, None], atol=1e-10, rtol=1e-9)
    checks.close(model+".jacobian_singular_values", [row["scaled_jacobian_singular_values"] for row in records],
                 singulars, atol=1e-9, rtol=1e-8)
    return updated, {"n_rows": len(records), "n_eligible": sum(expected_eligibility),
                     "status_counts": dict(Counter(row["status"] for row in records)),
                     "ineligible_rows": invalid_rows}


def sampled_alternatives(source, arrays, records, checks):
    positions = np.unique(np.linspace(0, len(arrays["roi_ijk"])-1, min(64, len(arrays["roi_ijk"])), dtype=int))
    diagnostics = []
    artifacts = {"roi_indices": arrays["selected_roi_indices"][positions], "roi_ijk": arrays["roi_ijk"][positions],
                 "source_manifest_sha256": np.asarray(MANIFEST_SHA256),
                 "source_sha256_json": np.asarray(json.dumps(source["source_sha256"], sort_keys=True)),
                 "pipeline_id": np.asarray(PIPELINE_ID)}
    high_design = design_matrix(source["bvals"], source["bvecs"])
    for model in ("dti_b1000", "dti_b2000"):
        if model not in records:
            continue
        columns = np.flatnonzero(source["bvals"] <= (1050 if model == "dti_b1000" else 2050))
        design = design_matrix(source["bvals"][columns], source["bvecs"][columns])
        coefficients = np.asarray([dti_lstsq(source["signal"][arrays["selected_roi_indices"][row], columns], design) for row in positions])
        reference = np.asarray([records[model][row]["beta"] for row in positions])
        checks.close(model+".scipy_lstsq_tensor", coefficients[:, :6], reference[:, :6], atol=1e-8, rtol=1e-5)
        checks.close(model+".scipy_lstsq_intercept", coefficients[:, 6], reference[:, 6], atol=1e-7, rtol=1e-7)
        artifacts["beta_"+model] = coefficients
    if "fwdti" not in records:
        return diagnostics, artifacts
    alternate_parameters = {method: [] for method in ("lm", "trf")}
    alternate_predictions = {method: [] for method in ("lm", "trf")}
    alternate_status = {method: [] for method in ("lm", "trf")}
    for position in positions:
        original_index = arrays["selected_roi_indices"][position]
        signal = source["signal"][original_index]
        b0 = float(signal[source["bvals"] <= 50].mean())
        oracle = records["fwdti"][position]
        alternatives = fit_alternatives(signal, high_design, b0)
        initial = alternatives["initializer"]
        label = f"fwdti.sample_{int(original_index)}"
        checks.close(label+".init_md", oracle["init_md"], np.nan if initial["md"] is None else initial["md"], atol=1e-9, rtol=1e-7)
        if initial["parameters"] is not None:
            checks.close(label+".initial_beta", oracle["initial_beta"], initial["parameters"][:7], atol=1e-8, rtol=1e-7)
            checks.close(label+".initial_fraction", oracle["init_f"], initial["fraction"], atol=1e-12, rtol=0)
            checks.close(label+".initial_raw_beta", oracle["initial_raw_beta"], initial["raw_beta"], atol=1e-8, rtol=1e-7)
        diagnostic = {"roi_index": int(original_index), "ijk": arrays["roi_ijk"][position],
                      "oracle_status": oracle["status"], "oracle_fraction": oracle["f"], "oracle_fa": oracle["fa"],
                      "oracle_normalized_sse": oracle["sse"]/max(b0, 1e-6)**2, "alternatives": alternatives}
        for method in ("lm", "trf"):
            result = alternatives[method]
            parameters = np.full(8, np.nan) if result is None else result.get("parameters", np.full(8, np.nan))
            prediction = np.full(len(signal), np.nan) if result is None else result.get("prediction", np.full(len(signal), np.nan))
            alternate_parameters[method].append(parameters)
            alternate_predictions[method].append(prediction)
            alternate_status[method].append("skipped" if result is None else str(result.get("status", "error")))
            if result is not None and "normalized_sse" in result:
                result["minus_oracle_normalized_sse"] = result["normalized_sse"]-diagnostic["oracle_normalized_sse"]
                result["max_abs_prediction_difference_over_b0"] = float(np.max(abs(prediction-oracle["prediction"]))/max(b0, 1e-6))
                if "fa" in result:
                    result["fa_difference"] = result["fa"]-oracle["fa"]
                    result["fraction_difference"] = result["fraction"]-oracle["f"]
                result["numerically_equivalent_fixed_recipe_candidate"] = bool(
                    result["converged"] and np.allclose(parameters[:6], oracle["beta"][:6], atol=1e-8, rtol=1e-5)
                    and np.isclose(result["fraction"], oracle["f"], atol=1e-5, rtol=1e-5)
                    and np.isclose(result["fitted_s0"]/max(b0, 1e-6), oracle["S0_hat"]/max(b0, 1e-6), atol=1e-5, rtol=1e-5)
                    and np.max(abs(prediction-oracle["prediction"]))/max(b0, 1e-6) <= 1e-5)
        diagnostics.append(diagnostic)
    for method in ("lm", "trf"):
        artifacts[method+"_parameters"] = np.asarray(alternate_parameters[method])
        artifacts[method+"_predictions"] = np.asarray(alternate_predictions[method])
        artifacts[method+"_status"] = np.asarray(alternate_status[method])
    return diagnostics, artifacts


def run_check(data_dir, oracle_output, pilot=False):
    checks = Checks()
    with np.load(oracle_output/"analysis_arrays.npz", allow_pickle=False) as receipt:
        arrays = {key: receipt[key] for key in receipt.files}
    metadata = json.loads((oracle_output/"run_metadata.json").read_text())
    checks.require("private_pipeline_id", str(arrays["pipeline_id"]) == PIPELINE_ID)
    checks.require("metadata_pipeline_id", metadata["pipeline_id"] == PIPELINE_ID)
    checks.require("private_metadata_identity", json.loads(str(arrays["metadata_json"])) == metadata)
    checks.require("private_results_identity", json.loads(str(arrays["results_json"])) == json.loads((oracle_output/"results.json").read_text()))
    models = metadata["fitted_models"]
    if len(set(models)) != len(models) or not 2 <= len(models) <= 3 or not set(models) <= set(MODELS):
        raise ValueError("Invalid selected models")
    if pilot and (metadata["status"] != "resource_pilot" or not 1 <= len(arrays["roi_ijk"]) <= 64):
        raise ValueError("Pilot check accepts only a marked <=64-row resource pilot")
    if not pilot and metadata["status"] != "ok":
        raise ValueError("Full check requires a complete non-pilot oracle output")
    source = reconstruct_source(data_dir)
    checks.require("source_hash_identity", metadata["source_sha256"] == source["source_sha256"])
    checks.require("source_manifest_identity", metadata["source_manifest_sha256"] == MANIFEST_SHA256)
    checks.require("source_spatial_units", metadata["header_spatial_units"] == source["spatial_units"] == "unknown")
    checks.close("source_affine", metadata["affine"], source["affine"], atol=0, rtol=0)
    smoothing = metadata["preprocessing"]["smoothing"]
    checks.require("public_smoothing_contract", smoothing == {
        "fwhm_voxels": FWHM_VOXELS, "sigma_voxels": float(SIGMA_VOXELS), "mode": "reflect",
        "truncate": 4., "spatial_axes_only": True, "dtype": "float64", "physical_mm_claim": False})
    checks.require("full_source_roi", np.array_equal(arrays["full_roi_ijk"], source["roi_ijk"]))
    desired_indices = (np.unique(np.linspace(0, len(source["roi_ijk"])-1, len(arrays["roi_ijk"]), dtype=int))
                       if pilot else np.arange(len(source["roi_ijk"])))
    if not checks.require("selected_roi_indices", np.array_equal(arrays["selected_roi_indices"], desired_indices)):
        raise ValueError("Invalid source selection; cannot align rows safely")
    selected = arrays["selected_roi_indices"]
    checks.require("evaluated_roi_identity", np.array_equal(arrays["roi_ijk"], source["roi_ijk"][selected]))
    checks.require("brain_identity", np.array_equal(arrays["brain_ijk"], source["brain_ijk"]))
    checks.require("seed_identity", np.array_equal(arrays["seed_ijk"], np.argwhere(source["seed_mask"])))
    checks.close("brain_low_beta", arrays["brain_low_beta"], source["low_b_coefficients"], atol=1e-10, rtol=1e-8)
    for key in ("signal", "raw_signal"):
        checks.close("source_"+key, arrays[key], source[key][selected], atol=1e-10, rtol=1e-12)
    for key in ("volume_indices", "bvals", "bvecs", "original_bvals", "original_bvecs"):
        checks.require("source_"+key, np.array_equal(arrays[key], source[key]))
    checks.close("roi_low_fa", arrays["roi_fa_low"], source["low_b_fa"][selected], atol=1e-10, rtol=1e-9)
    checks.close("roi_low_md", arrays["roi_md_low"], source["low_b_md"][selected], atol=1e-12, rtol=1e-9)
    checks.require("brain_count", metadata["n_brain_voxels"] == len(source["brain_ijk"]))
    checks.require("seed_count", metadata["n_seed_voxels"] == int(source["seed_mask"].sum()))
    records, qc = {}, {}
    original_records = {model: records_from_arrays(arrays, model) for model in models}
    for model in models:
        records[model], qc[model] = validate_model_arithmetic(source, arrays, model, original_records[model], checks)
    summaries = validate_public(oracle_output, records, arrays["roi_ijk"], metadata, checks)
    _, common = compute_summaries(records, metadata["main_model"])
    checks.require("private_common_valid", np.array_equal(arrays["common_valid"], common))
    alternatives, artifacts = sampled_alternatives(source, arrays, original_records, checks)
    report = {"status": "passed" if not checks.issues else "failed", "issues": checks.issues,
              "mode": "resource_pilot" if pilot else "complete_source_check", "pipeline_id": PIPELINE_ID,
              "source_manifest_sha256": MANIFEST_SHA256, "source_sha256": source["source_sha256"],
              "source_roi_count": len(source["roi_ijk"]), "evaluated_roi_count": len(arrays["roi_ijk"]),
              "checks": checks.items, "model_qc": qc, "recomputed_results": summaries,
              "alternative_fit_diagnostics": alternatives,
              "numerical_limits": "Alternative LM/TRF fraction/FA/parameter differences are retained as identifiability diagnostics, not scientific failure or automatic fixed-recipe acceptance. The checker tests no independent tissue truth.",
              "independent_components": ["explicit design expansion", "two-pass NumPy WLS and separate SciPy least-squares solves",
                                         "ROI mask algebra", "free-water observed-weight initializer and analytic Jacobian",
                                         "tensor eigensystem/FA and raw versus floored predictions", "all-row residual/support/summary arithmetic"],
              "shared_components": ["same original acquisition and frozen method contract", "nibabel reader", "DIPY median_otsu",
                                    "SciPy Gaussian filter and morphology", "NumPy/SciPy linear algebra", "SciPy LM and TRF optimizers"],
              "software": {"numpy": np.__version__, "scipy": scipy.__version__, "nibabel": nib.__version__}}
    return report, artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="Allow only a marked resource pilot with at most 64 fitted rows")
    args = parser.parse_args()
    alternate_path = args.report.with_name(args.report.stem+".alternate_fits.npz")
    if args.report.exists() or alternate_path.exists():
        raise FileExistsError("Preserve existing independent evidence; choose fresh output paths")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        report, artifacts = run_check(args.data_dir, args.oracle_output, args.pilot)
        np.savez_compressed(alternate_path, **artifacts)
        report["alternate_fit_artifact"] = {"path": str(alternate_path), "sha256": hash_file(alternate_path)}
    except Exception as exc:
        report = {"status": "failed", "issues": [f"{type(exc).__name__}: {exc}"],
                  "scope": "Checker execution failed; no claim of numerical/scientific agreement"}
    with args.report.open("x") as stream:
        json.dump(json_safe(report), stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "issues": report["issues"], "report": str(args.report)}))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
