"""Authoring-only, source-bound WLS audit; imports no oracle or verifier.

All ROI rows receive independently implemented coefficient/tensor/prediction
checks. A prespecified 256-row subset receives a SciPy GELSD two-pass refit.
ROI selection shares DIPY's median_otsu and low-b TensorModel: this limitation
is explicit, and numerical agreement is not independent diffusivity truth.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import linalg

PIPELINE = "cfin-unsmoothed-wls-md-fa-v2"
CONFIGS = {"dki_all": 22, "dti_lowb": 7, "dti_all": 7}
SIGNAL_FLOOR = 1e-4
COEF_RTOL = 1e-6
REPORTED_ATOL = REPORTED_RTOL = 1e-6
SOURCE_HASHES = {
    "__DTI_AX_ep2d_2_5_iso_33d_20141015095334_4.nii":
        "1081b5b586a5429a6754078653ffe4ab430d348eb712bc7231c8f99919ac3eff",
    "__DTI_AX_ep2d_2_5_iso_33d_20141015095334_4.bval":
        "508d18044a4e220e28bdfcbe192238f0abb20869e36b0e2c2c4ead85fc75e614",
    "__DTI_AX_ep2d_2_5_iso_33d_20141015095334_4.bvec":
        "4774696dfb4b20223fd1bbb5e05b90a2c01a8b2b8e6f13ebc807b152cb8b5fdd",
}
METRIC_COLUMNS = ("md", "fa", "S0_hat", "observed_b0", "normalization_scale",
                  "nrmse", "log_rmse", "n_signal_floored", "n_eigenvalues_floored")


def manual_design(bvals, bvecs, kurtosis=False):
    """Independent expansion in DIPY's published diffusion/quartic order."""
    b = np.asarray(bvals, dtype=float)
    g = np.asarray(bvecs, dtype=float)
    assert b.ndim == 1 and g.shape == (len(b), 3)
    assert np.isfinite(b).all() and np.isfinite(g).all() and np.all(b >= 0)
    x, y, z = g.T
    terms = [x*x, 2*x*y, y*y, 2*x*z, 2*y*z, z*z]
    columns = [-b*term for term in terms]
    if kurtosis:
        powers = ((4, 0, 0), (0, 4, 0), (0, 0, 4), (3, 1, 0),
                  (3, 0, 1), (1, 3, 0), (0, 3, 1), (1, 0, 3),
                  (0, 1, 3), (2, 2, 0), (2, 0, 2), (0, 2, 2),
                  (2, 1, 1), (1, 2, 1), (1, 1, 2))
        factors = (1, 1, 1, 4, 4, 4, 4, 4, 4, 6, 6, 6, 12, 12, 12)
        columns += [b*b*(factor/6)*x**px*y**py*z**pz
                    for (px, py, pz), factor in zip(powers, factors)]
    columns.append(-np.ones_like(b))
    return np.column_stack(columns)


def tensor_from_beta(beta):
    beta = np.asarray(beta, dtype=float)
    assert beta.ndim == 2 and beta.shape[1] in (7, 22)
    tensor = np.empty((len(beta), 3, 3), dtype=float)
    tensor[:, 0, 0], tensor[:, 1, 1], tensor[:, 2, 2] = beta[:, 0], beta[:, 2], beta[:, 5]
    tensor[:, 0, 1] = tensor[:, 1, 0] = beta[:, 1]
    tensor[:, 0, 2] = tensor[:, 2, 0] = beta[:, 3]
    tensor[:, 1, 2] = tensor[:, 2, 1] = beta[:, 4]
    return tensor


def evaluate_coefficients(beta, design, signal, observed_b0):
    """Report raw-regression and post-eigenfloor quantities separately."""
    beta = np.asarray(beta, dtype=float)
    design = np.asarray(design, dtype=float)
    signal = np.asarray(signal, dtype=float)
    observed_b0 = np.asarray(observed_b0, dtype=float)
    assert signal.shape == (len(beta), len(design))
    assert beta.shape[1] == design.shape[1] and observed_b0.shape == (len(beta),)
    assert all(np.isfinite(a).all() for a in (beta, design, signal, observed_b0))
    floor = 1e-6 / (-float(design.min()))
    assert np.isfinite(floor) and floor > 0
    raw_evals, vectors = np.linalg.eigh(tensor_from_beta(beta))
    evals = np.maximum(raw_evals, floor)
    post_tensor = (vectors*evals[:, None, :]) @ np.swapaxes(vectors, 1, 2)
    post_beta = beta.copy()
    for index, (i, j) in enumerate(((0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2))):
        post_beta[:, index] = post_tensor[:, i, j]
    average = evals.mean(axis=1)
    fa = np.sqrt(1.5*np.sum((evals-average[:, None])**2, axis=1)/np.sum(evals**2, axis=1))
    with np.errstate(over="raise", invalid="raise"):
        predicted = np.exp(post_beta @ design.T)
        s0 = np.exp(-beta[:, -1])
    assert np.isfinite(predicted).all() and np.isfinite(s0).all() and np.all(s0 > 0)
    scale = np.maximum(observed_b0, SIGNAL_FLOOR)
    log_residual = np.log(np.maximum(signal, SIGNAL_FLOOR)) - beta @ design.T
    return {
        "md": average*1000, "fa": fa, "S0_hat": s0,
        "observed_b0": observed_b0, "normalization_scale": scale,
        "nrmse": np.sqrt(np.mean(((signal-predicted)/scale[:, None])**2, axis=1)),
        "log_rmse": np.sqrt(np.mean(log_residual**2, axis=1)),
        "n_signal_floored": np.sum(signal < SIGNAL_FLOOR, axis=1),
        "n_eigenvalues_floored": np.sum(raw_evals < floor, axis=1),
        "raw_eigenvalues": raw_evals, "floored_eigenvalues": evals,
        "predicted": predicted, "post_beta": post_beta, "eigenvalue_floor": floor,
    }


def gelsd_wls(design, signal):
    """Alternative solver; same declared two-pass objective, no oracle imports."""
    design = np.asarray(design, dtype=float)
    signal = np.asarray(signal, dtype=float)
    assert signal.ndim == 2 and signal.shape[1] == len(design)
    result = np.empty((len(signal), design.shape[1]))
    ranks = []
    for i, row in enumerate(signal):
        y = np.log(np.maximum(row, SIGNAL_FLOOR))
        initial, _, ols_rank, _ = linalg.lstsq(design, y, cond=1e-15, lapack_driver="gelsd")
        with np.errstate(over="raise", invalid="raise"):
            weights = np.exp(design @ initial)
        assert np.isfinite(weights).all() and np.all(weights > 0)
        fitted, _, weighted_rank, _ = linalg.lstsq(
            design*weights[:, None], y*weights, cond=1e-15, lapack_driver="gelsd")
        result[i] = fitted
        ranks.append((int(ols_rank), int(weighted_rank)))
    assert np.isfinite(result).all()
    return result, np.asarray(ranks, dtype=int)


def coefficient_atol(n_coefficients):
    assert n_coefficients in (7, 22)
    return np.array([1e-10]*6 + ([1e-12]*15 if n_coefficients == 22 else []) + [1e-7])


def check_coefficients(actual, expected):
    atol = coefficient_atol(expected.shape[1])
    assert actual.shape == expected.shape and np.isfinite(actual).all()
    assert np.all(np.abs(actual-expected) <= atol[None, :]+COEF_RTOL*np.abs(expected)), \
        "independent raw WLS coefficient mismatch"
    return {
        "max_absolute_diffusion_coefficient_error": float(np.max(np.abs(actual[:, :6]-expected[:, :6]))),
        "max_absolute_quartic_coefficient_error": (float(np.max(np.abs(actual[:, 6:21]-expected[:, 6:21])))
                                                     if expected.shape[1] == 22 else None),
        "max_absolute_intercept_error": float(np.max(np.abs(actual[:, -1]-expected[:, -1]))),
    }


def sampled_indices(n, count=256):
    assert n > 0 and count > 0
    return np.unique(np.linspace(0, n-1, min(n, count), dtype=int))


def select_public_contract(document, config):
    """Accept a template collection or the already-selected public template."""
    collection = document.get("configs", document)
    contract = collection.get(config, collection)
    assert isinstance(contract, dict) and contract["pipeline_id"] == PIPELINE
    assert contract["model_config"] == config
    return contract


def distribution(values):
    """Unfiltered descriptive diagnostics, never a quality or exclusion gate."""
    values = np.asarray(values, dtype=float).reshape(-1)
    assert np.isfinite(values).all()
    if not len(values):
        return {"n": 0, "mean": None, "quantiles": None,
                "n_zero": 0, "n_negative": 0}
    probabilities = (0., .01, .05, .25, .5, .75, .95, .99, 1.)
    names = ("min", "p01", "p05", "p25", "median", "p75", "p95", "p99", "max")
    return {"n": len(values), "mean": float(values.mean()),
            "quantiles": dict(zip(names, map(float, np.quantile(values, probabilities)))),
            "n_zero": int(np.count_nonzero(values == 0)),
            "n_negative": int(np.count_nonzero(values < 0))}


def diagnostics(evaluated):
    floored_scale = evaluated["observed_b0"] < SIGNAL_FLOOR
    counts = {}
    for key in ("n_signal_floored", "n_eigenvalues_floored"):
        values, frequencies = np.unique(evaluated[key], return_counts=True)
        counts[key] = [{"count_per_voxel": int(value), "n_voxels": int(frequency)}
                       for value, frequency in zip(values, frequencies)]
    return {
        "scope": "all ROI voxels retained; descriptive diagnostics only, no quality threshold",
        "distributions": {key: distribution(evaluated[key]) for key in
                          ("observed_b0", "normalization_scale", "nrmse", "log_rmse",
                           "n_signal_floored", "n_eigenvalues_floored")},
        "floor_count_histograms": counts,
        "n_normalization_scales_floored": int(floored_scale.sum()),
        "nrmse_by_normalization_floor": {"floored": distribution(evaluated["nrmse"][floored_scale]),
                                         "not_floored": distribution(evaluated["nrmse"][~floored_scale])},
        "interpretation": "Normalized RMSE divides by max(observed b0,1e-4), not fitted S0; "
                          "small observed b0 or unstable predictions can dominate its mean. "
                          "Algebraic and solver agreement do not establish physiological fit adequacy.",
    }


def save_independent_coefficients(directory, config, ijk, indices, beta, source_hashes):
    """Retain an already-computed partial refit; performs no additional fitting."""
    assert config in CONFIGS and beta.shape == (len(indices), CONFIGS[config])
    path = Path(directory)/f"independent_coefficients_{config}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, pipeline_id=np.array(PIPELINE), model_config=np.array(config),
                        n_roi_voxels=np.array(len(ijk), dtype=np.int64),
                        source_sha256_json=np.array(json.dumps(source_hashes, sort_keys=True)),
                        roi_row_indices=np.asarray(indices, dtype=np.int64),
                        roi_ijk=np.asarray(ijk[indices], dtype=np.int64),
                        beta=np.asarray(beta, dtype=np.float64))
    return path


def read_voxels(path, expected_ijk, n_coefficients):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        assert len(fields) == len(set(fields)), "duplicate CSV headers"
        required = ("i", "j", "k") + METRIC_COLUMNS + tuple(f"beta_{i}" for i in range(n_coefficients))
        assert set(required) <= set(fields), "missing required numerical columns"
        rows = list(reader)
    assert len(rows) == len(expected_ijk), "incomplete or padded ROI"
    coordinates = np.array([[float(row[key]) for key in ("i", "j", "k")] for row in rows])
    assert np.isfinite(coordinates).all() and np.equal(coordinates, np.floor(coordinates)).all()
    assert np.all(coordinates >= 0), "negative coordinate"
    coordinates = coordinates.astype(np.int64)
    assert len(np.unique(coordinates, axis=0)) == len(coordinates), "duplicate coordinate"
    order = np.lexsort((coordinates[:, 2], coordinates[:, 1], coordinates[:, 0]))
    assert np.array_equal(coordinates[order], expected_ijk), "source ROI key mismatch"
    values = {key: np.array([float(rows[i][key]) for i in order]) for key in required[3:]}
    assert all(np.isfinite(value).all() for value in values.values())
    for key in ("n_signal_floored", "n_eigenvalues_floored"):
        assert np.all(values[key] >= 0) and np.equal(values[key], np.floor(values[key])).all()
    beta = np.column_stack([values[f"beta_{i}"] for i in range(n_coefficients)])
    return values, beta


def load_source(data):
    root = Path(data).resolve()
    manifest = json.loads((root / "data_manifest.json").read_text())
    entries = manifest["files"]
    assert len(entries) == 3 and {entry["role"] for entry in entries} == {"image", "bval", "bvec"}
    assert {entry["path"] for entry in entries} == set(SOURCE_HASHES)
    paths, hashes = {}, {}
    for entry in entries:
        path = (root / entry["path"]).resolve()
        assert path.is_relative_to(root) and path.stat().st_size == entry["size_bytes"]
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert digest == entry["sha256"] == SOURCE_HASHES[entry["path"]]
        paths[entry["role"]] = path
        hashes[entry["path"]] = digest
    image = nib.load(paths["image"])
    assert image.shape == (96, 96, 19, 496) and image.header.get_xyzt_units()[0] == "mm"
    bvals = np.loadtxt(paths["bval"]).reshape(-1)
    bvecs = np.loadtxt(paths["bvec"])
    if bvecs.shape == (3, len(bvals)):
        bvecs = bvecs.T
    assert bvals.shape == (496,) and bvecs.shape == (496, 3)
    assert np.array_equal(np.unique(bvals), np.arange(0, 3001, 200))
    low = np.round(bvals, -2) <= 1000
    assert int(low.sum()) == 166 and np.array_equal(low, bvals <= 1000)
    assert np.count_nonzero(bvals <= 50) == 1
    assert np.allclose(np.linalg.norm(bvecs[bvals > 50], axis=1), 1, atol=1e-5, rtol=0)
    raw = np.asarray(image.dataobj)
    assert np.isfinite(raw).all()
    return raw, bvals, bvecs, hashes, {
        "shape": list(image.shape), "affine": image.affine.tolist(),
        "voxel_sizes_mm": list(map(float, image.header.get_zooms()[:3])),
        "source_sha256": hashes,
    }


def shared_library_roi(raw, bvals, bvecs):
    """Regenerate selection from source, explicitly not an independent mask method."""
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import TensorModel
    from dipy.segment.mask import median_otsu
    _, brain = median_otsu(np.asarray(raw[..., 0], dtype=float), median_radius=4,
                          numpass=2, autocrop=False, dilate=1, finalize_mask=False)
    low = np.round(bvals, -2) <= 1000
    gtab = gradient_table(bvals[low], bvecs=bvecs[low], b0_threshold=50)
    fit = TensorModel(gtab, fit_method="WLS", min_signal=SIGNAL_FLOOR).fit(
        np.asarray(raw[brain][:, low], dtype=float))
    low_fa = np.asarray(fit.fa, dtype=float)
    roi = np.zeros(brain.shape, dtype=bool)
    valid = np.isfinite(low_fa) & (low_fa > .5)
    roi[brain] = valid
    assert roi.any(), "empty source-derived ROI"
    return np.argwhere(roi), int(brain.sum()), low_fa[valid], int(np.count_nonzero(~np.isfinite(low_fa)))


def dipy_helper_sanity(design, signal, beta, kurtosis):
    """Small shared-library check; explicitly separate from the GELSD calculation."""
    selected = sampled_indices(len(signal), 16)
    measured = np.maximum(signal[selected], SIGNAL_FLOOR)
    if kurtosis:
        from dipy.reconst.dki import ls_fit_dki
        inverse = np.linalg.pinv(design, rcond=1e-15)
        fitted = np.array([ls_fit_dki(design, row, inverse, weights=True,
                                     return_lower_triangular=True)[0] for row in measured])
    else:
        from dipy.reconst.dti import wls_fit_tensor
        fitted = wls_fit_tensor(design, measured, return_lower_triangular=True)[0]
    comparison = check_coefficients(beta[selected], fitted)
    return {"n_rows": len(selected), "roi_row_indices": selected.tolist(), **comparison,
            "scope": "shared DIPY formula sanity check, not independent estimation"}


def check(data, output, coefficient_directory=None):
    raw, bvals, bvecs, hashes, source = load_source(data)
    out = Path(output)
    result = json.loads((out / "diffusivity.json").read_text())
    metadata = json.loads((out / "run_metadata.json").read_text())
    config = result["model_config"]
    assert config in CONFIGS and result["status"] == metadata["status"] == "ok"
    assert result["pipeline_id"] == metadata["pipeline_id"] == PIPELINE
    assert metadata["model_config"] == config and metadata["source_sha256"] == hashes
    assert result["md_units"] == "1e-3 mm^2/s"
    ijk, n_brain, roi_fa_low, n_nonfinite_selection_fa = shared_library_roi(raw, bvals, bvecs)
    signal_all = np.asarray(raw[tuple(ijk.T)], dtype=float)
    del raw
    selected = np.round(bvals, -2) <= 1000 if config == "dti_lowb" else np.ones(len(bvals), dtype=bool)
    signal = signal_all[:, selected]
    observed = signal_all[:, bvals <= 50].mean(axis=1)
    design = manual_design(bvals[selected], bvecs[selected], kurtosis=config == "dki_all")
    values, beta = read_voxels(out / "md_voxelwise.csv", ijk, CONFIGS[config])
    evaluated = evaluate_coefficients(beta, design, signal, observed)
    errors = {}
    for key in METRIC_COLUMNS:
        actual, expected = values[key], evaluated[key]
        if key.startswith("n_"):
            assert np.array_equal(actual, expected), key + " mismatch"
        elif key == "S0_hat":
            assert np.allclose(actual/evaluated["normalization_scale"], expected/evaluated["normalization_scale"],
                               atol=1e-6, rtol=1e-6), "fitted S0 mismatch"
        elif key in ("observed_b0", "normalization_scale"):
            assert np.allclose(actual, expected, atol=1e-10, rtol=1e-10), key + " source mismatch"
        else:
            assert np.allclose(actual, expected, atol=REPORTED_ATOL, rtol=REPORTED_RTOL), key + " mismatch"
        errors[key] = float(np.max(np.abs(actual-expected)))
    assert result["n_wm_voxels"] == metadata["n_wm_voxels"] == len(ijk)
    assert metadata["n_brain_voxels"] == n_brain
    for key in ("md", "fa", "nrmse", "log_rmse", "S0_hat"):
        scale = float(np.mean(evaluated["normalization_scale"])) if key == "S0_hat" else 1.
        assert np.isclose(result[key+"_mean"]/scale, np.mean(evaluated[key])/scale, atol=1e-6, rtol=1e-6)
    for plural in ("signal", "eigenvalues"):
        counts = evaluated[f"n_{plural}_floored"]
        assert result[f"n_{plural}_floored_total"] == int(counts.sum())
        assert result[f"n_voxels_{plural}_floored"] == int(np.count_nonzero(counts))
    contract_path = Path("/app/method_contract.json")
    if not contract_path.exists():
        contract_path = Path(__file__).resolve().parents[1]/"environment/method_contract.json"
    contract = select_public_contract(json.loads(contract_path.read_text()), config)
    for key, value in contract.items():
        assert metadata[key] == value, "public metadata contract mismatch: " + key
    with np.load(out / "analysis_arrays.npz", allow_pickle=False) as receipt:
        exact = {"roi_ijk": ijk, "signal": signal_all, "bvals": bvals,
                 "bvecs": bvecs, "volume_indices": np.flatnonzero(selected),
                 "beta": beta, "n_brain_voxels": np.asarray(n_brain)}
        for key, expected in exact.items():
            assert np.array_equal(receipt[key], expected), "private source receipt mismatch: " + key
        assert np.allclose(receipt["design"], design, atol=1e-8, rtol=1e-14)
        assert np.allclose(receipt["roi_fa_low"], roi_fa_low, atol=1e-12, rtol=1e-12)
        for key in METRIC_COLUMNS:
            assert np.allclose(receipt[key], values[key], atol=1e-12, rtol=1e-12)
        assert json.loads(str(receipt["metadata_json"].item())) == contract
    subset = sampled_indices(len(ijk), 256)
    fitted, ranks = gelsd_wls(design, signal[subset])
    independent_metrics = evaluate_coefficients(fitted, design, signal[subset], observed[subset])
    comparison = check_coefficients(beta[subset], fitted)
    independent_errors = {}
    for key in ("md", "fa", "nrmse", "log_rmse"):
        assert np.allclose(evaluated[key][subset], independent_metrics[key], atol=1e-6, rtol=1e-6)
        independent_errors[key] = float(np.max(np.abs(evaluated[key][subset]-independent_metrics[key])))
    actual_prediction = evaluated["predicted"][subset]/evaluated["normalization_scale"][subset, None]
    independent_prediction = independent_metrics["predicted"]/independent_metrics["normalization_scale"][:, None]
    assert np.allclose(actual_prediction, independent_prediction, atol=1e-5, rtol=1e-6)
    helper = dipy_helper_sanity(design, signal, beta, config == "dki_all")
    coefficient_path = (save_independent_coefficients(coefficient_directory, config, ijk,
                                                     subset, fitted, hashes)
                        if coefficient_directory is not None else None)
    return {
        "status": "passed", "pipeline_id": PIPELINE, "model_config": config,
        "scope": "computational recipe consistency; no independent physiological diffusivity truth",
        "source": source, "n_brain_voxels": n_brain, "n_wm_voxels": len(ijk),
        "n_nonfinite_roi_selection_fa": n_nonfinite_selection_fa,
        "roi_selection_independence_limit": "source regenerated with shared DIPY median_otsu and TensorModel",
        "full_roi_algebra_max_abs_errors": errors,
        "independent_refit": {
            "solver": "SciPy GELSD cond=1e-15 with independent design expansion and two-pass weights",
            "scope": "256 evenly spaced C-order ROI rows, not a complete independent refit",
            "n_rows": len(subset), "roi_row_indices": subset.tolist(),
            "coefficients_artifact": coefficient_path.name if coefficient_path is not None else None,
            "roi_ijk": ijk[subset].tolist(), "rank_pairs": np.unique(ranks, axis=0).tolist(),
            **comparison, "max_absolute_metric_errors": independent_errors,
            "max_normalized_prediction_error": float(np.max(np.abs(actual_prediction-independent_prediction))),
        },
        "dipy_raw_helper_sanity": helper,
        "fit_diagnostics": diagnostics(evaluated),
        "observed_summary": {"md_mean": float(evaluated["md"].mean()),
                             "fa_mean": float(evaluated["fa"].mean()),
                             "n_voxels_with_signal_floor": int(np.count_nonzero(evaluated["n_signal_floored"])),
                             "n_voxels_with_eigenvalue_floor": int(np.count_nonzero(evaluated["n_eigenvalues_floored"]))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/app/data/cfin")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = check(args.data, args.output, coefficient_directory=path.parent)
    path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": report["status"], "model_config": report["model_config"],
                      "n_wm_voxels": report["n_wm_voxels"],
                      "independent_rows": report["independent_refit"]["n_rows"]}))
