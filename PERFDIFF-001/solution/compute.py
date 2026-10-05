"""Offline, explicit IVIM fitting recipes with retained per-voxel numerical QC."""
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares

PIPELINE_ID = "ivim-explicit-qc-v2"
DATASET_ID = "ivim-figshare-3395704-v1"
METHODS = ["trr_explicit", "segmented_b200"]
VERSIONS = {"numpy": "2.2.6", "scipy": "1.14.1", "nibabel": "5.3.2",
            "dipy": "1.12.1", "h5py": "3.16.0"}
BVALS = [0, 10, 20, 30, 40, 60, 80, 100, 120, 140, 160, 180, 200,
         300, 400, 500, 600, 700, 800, 900, 1000]
BOX = {"x": [90, 120], "y": [90, 120], "z": 33}
SOLVER = {"method": "trf", "jacobian": "analytic", "loss": "linear",
          "tr_solver": "exact", "ftol": 1e-10, "xtol": 1e-10, "gtol": 1e-10,
          "max_nfev": 1000}
PARAMETER_ORDER = ["S0", "f", "Dstar", "D"]
STAT_KEYS = ["S0_mean", "f_mean", "Dstar_mean", "D_mean", "nrmse_mean"]
BOUND_NAMES = ["a_lower", "f_lower", "f_upper", "Dstar_lower", "Dstar_upper",
               "D_lower", "D_upper", "Dstar_D_lower"]
FLAG_EPS = 1e-8
STATUSES = ["not_tissue", "invalid_signal", "initialization_invalid",
            "segmented_out_of_bounds", "optimizer_failed", "invalid_parameters",
            "degenerate_or_unordered", "ok"]


def check_versions():
    for name, expected in VERSIONS.items():
        actual = importlib.import_module(name).__version__
        if actual != expected:
            raise ValueError(f"declared baseline requires {name}=={expected}, found {actual}")


def load_inputs(data_dir):
    import nibabel as nib
    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    if manifest.get("source_version") != "figshare-3395704-v1":
        raise ValueError("unexpected IVIM source version")
    files = manifest["files"]
    if len(files) != 3:
        raise ValueError("require the original image, bval and bvec files only")
    paths, hashes = {}, {}
    for item in files:
        relative = Path(item["path"])
        path = (data_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(data_dir):
            raise ValueError("source path escapes data directory")
        role = item["role"]
        if role not in {"image", "bval", "bvec"} or role in paths or item["path"] in hashes:
            raise ValueError("duplicate or unknown source role")
        if path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"source size mismatch: {relative}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"source SHA256 mismatch: {relative}")
        paths[role], hashes[item["path"]] = path, digest
    image = nib.load(paths["image"])
    bvals = np.loadtxt(paths["bval"], dtype=float)
    bvecs = np.loadtxt(paths["bvec"], dtype=float)
    if image.shape != (256, 256, 54, 21) or not np.array_equal(bvals, BVALS):
        raise ValueError("source image or b-values differ from the pinned acquisition")
    if bvecs.shape != (3, 21) or not np.array_equal(bvecs, np.tile([[0], [0], [1]], (1, 21))):
        raise ValueError("unexpected direction-averaged b-vector metadata")
    if not np.isfinite(image.affine).all() or image.header.get_xyzt_units()[0] != "mm":
        raise ValueError("unexpected source geometry")
    return image, bvals, bvecs, hashes


def metadata_contract(image, bvals, source_sha256):
    """Configuration and source identity only; no data fits or derived ROI answers."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID,
        "source_sha256": source_sha256, "shape": list(image.shape),
        "affine": image.affine.tolist(),
        "header_voxel_sizes": [float(x) for x in image.header.get_zooms()[:3]],
        "header_spatial_units": image.header.get_xyzt_units()[0],
        "source_processing": "depositor_registered_and_direction_averaged",
        "bvals": np.asarray(bvals, float).tolist(), "b0_threshold": 0,
        "parameter_order": PARAMETER_ORDER, "diffusivity_units": "mm^2/s",
        "roi": {**BOX, "output_unit": "all_900_fixed_box_voxels",
                "b0_observed": "mean_of_measured_b_equals_zero",
                "tissue_rule": "b0_observed > 0.5 * median(finite_positive_box_b0_observed)",
                "input_eligible": "tissue_and_all_21_signals_finite_and_strictly_positive",
                "reorientation": None, "smoothing": None, "resampling": None},
        "model": "S0 * (f * exp(-b * Dstar) + (1-f) * exp(-b * D))",
        "normalization": "observed_signal / observed_mean_b0",
        "methods": {
            "trr_explicit": {
                "solver": SOLVER, "x_scale": [1.0, 0.1, 0.01, 0.001],
                "fit_parameter_order": ["a", "f", "Dstar", "D"],
                "bounds_lower": [0.0, 0.0, 0.0, 0.0],
                "bounds_upper": [None, 1.0, 1.0, 1.0],
                "null_upper_bound_means": "unbounded",
                "initialization": {
                    "regression": "OLS log(normalized_signal) = intercept - b * slope",
                    "D_b_min_inclusive": 400, "a_Dstar_b_max_inclusive": 200,
                    "f": "1 - exp(high_b_intercept) / exp(low_b_intercept)",
                    "a_lower": 1e-8, "f_clip": [1e-6, 1.0 - 1e-6],
                    "diffusivity_clip": [1e-8, 1.0 - 1e-8]},
                "component_canonicalization": "if_converged_Dstar_less_than_D_swap_and_f_equals_1_minus_f",
                "fallback": False},
            "segmented_b200": {
                "S0": "observed_mean_b0",
                "high_b": "b >= 200",
                "high_b_regression": "OLS log(normalized_signal) = intercept - b * D",
                "f": "1 - exp(intercept)",
                "initial_admissibility": "0 < f < 1 and 0 <= D < 1",
                "low_b": "b < 200",
                "fit": "Dstar_only_original_normalized_signal_residual_with_S0_D_f_fixed",
                "Dstar_bounds": ["D", 1.0],
                "Dstar_initial": "clip(0.01, D+1e-8*(1-D), 1-1e-8*(1-D))",
                "solver": SOLVER, "x_scale": [0.01], "fallback": False}},
        "qc": {
            "fit_statuses": STATUSES,
            "status_definitions": {
                "not_tissue": "source_b0_tissue_threshold_not_met_no_solver",
                "invalid_signal": "tissue_but_any_source_measurement_nonfinite_or_nonpositive_no_solver",
                "initialization_invalid": "log_linear_initialization_not_finite_or_failed_no_solver",
                "segmented_out_of_bounds": "segmented_initial_f_not_strictly_0_to_1_or_D_not_0_inclusive_to_1_exclusive_no_solver",
                "optimizer_failed": "optimizer_exception_or_unsuccessful_termination_candidate_not_admitted",
                "invalid_parameters": "optimizer_success_but_nonfinite_or_out_of_computational_bounds",
                "degenerate_or_unordered": "optimizer_success_but_f_not_strictly_0_to_1_or_Dstar_not_greater_than_D",
                "ok": "optimizer_success_and_numerically_admissible"},
            "optimizer_status": "SciPy_OptimizeResult_status_integer_minus_1_to_4_or_empty_if_no_result_success_requires_positive",
            "nfev": "SciPy_reported_function_evaluations_1_to_1000_or_0_if_no_OptimizeResult",
            "failed_candidates": "retain_defined_initial_or_last_iterate_parameters_as_diagnostics_never_as_valid_fallback_fits",
            "numerical_validity": "eligible_and_solver_success_and_finite_S0>0_and_0<f<1_and_0<=D<Dstar<=1",
            "common_valid": "intersection_of_both_methods_numerical_validity",
            "boundary_exclusion": False, "residual_exclusion": False,
            "bound_flag_epsilon": FLAG_EPS, "bound_flag_order": BOUND_NAMES,
            "bound_flag_delimiter": "|",
            "bound_flag_distances": ["S0/S0obs", "f", "1-f", "Dstar", "1-Dstar", "D", "1-D", "Dstar-D"],
            "bound_flag_rule": "emit_name_if_corresponding_distance_is_finite_and_less_than_or_equal_to_epsilon",
            "undefined_csv": "empty", "undefined_json": None,
            "nrmse": "sqrt(mean((prediction-observed_signal)**2)) / observed_mean_b0",
            "parameter_bounds_are": "computational_guards_not_physiological_reference_ranges"},
        "verification": {
            "parameter_atol": {"S0_over_b0": 1e-6, "f": 1e-6, "Dstar": 1e-8, "D": 1e-8},
            "parameter_rtol": 1e-6, "normalized_prediction_atol": 1e-5, "nrmse_atol": 1e-6,
            "summary_atol": {"S0_mean_over_mask_mean_observed_b0": 1e-6, "f_mean": 1e-6,
                             "Dstar_mean": 1e-8, "D_mean": 1e-8, "nrmse_mean": 1e-6},
            "geometry_atol": 1e-6, "undefined_pattern": "must_match_the_declared_source_bound_recipe",
            "optimizer_history": "status_and_nfev_checked_semantically_not_exact_iteration_history",
            "bound_flags": "recomputed_from_submitted_parameters_not_a_separate_exclusion_gate"},
        "software": VERSIONS,
    }


def extract_source_roi(image, bvals):
    signal = np.asarray(image.dataobj[90:120, 90:120, 33, :], dtype=np.float64).reshape(900, 21)
    offsets = np.indices((30, 30)).reshape(2, -1).T
    coordinates = np.column_stack((offsets + 90, np.full(900, 33))).astype(int)
    b0 = signal[:, np.asarray(bvals) == 0].mean(axis=1)
    positive = b0[np.isfinite(b0) & (b0 > 0)]
    if not len(positive):
        raise ValueError("fixed box has no finite positive b0 observations")
    tissue = np.isfinite(b0) & (b0 > 0.5 * np.median(positive))
    eligible = tissue & np.isfinite(signal).all(axis=1) & (signal > 0).all(axis=1)
    return coordinates, signal, b0, tissue, eligible


def normalized_prediction(q, bvals):
    a, fraction, fast, slow = np.asarray(q, float)
    bvals = np.asarray(bvals, float)
    return a * (fraction * np.exp(-bvals * fast) + (1.0 - fraction) * np.exp(-bvals * slow))


def normalized_jacobian(q, bvals):
    a, fraction, fast, slow = np.asarray(q, float)
    bvals = np.asarray(bvals, float)
    ef, ed = np.exp(-bvals * fast), np.exp(-bvals * slow)
    return np.column_stack((fraction * ef + (1.0 - fraction) * ed,
                            a * (ef - ed), -a * fraction * bvals * ef,
                            -a * (1.0 - fraction) * bvals * ed))


def log_linear(y, bvals, mask):
    design = np.column_stack((np.ones(np.count_nonzero(mask)), -np.asarray(bvals)[mask]))
    intercept, diffusivity = np.linalg.lstsq(design, np.log(np.asarray(y)[mask]), rcond=None)[0]
    return float(np.exp(intercept)), float(diffusivity)


def trr_initialization(y, bvals):
    high_a, slow = log_linear(y, bvals, np.asarray(bvals) >= 400)
    a, fast = log_linear(y, bvals, np.asarray(bvals) <= 200)
    raw = np.asarray([a, 1.0 - high_a / a, fast, slow])
    if not np.isfinite(raw).all():
        raise ValueError("nonfinite log-linear initialization")
    projected = raw.copy()
    projected[0] = max(projected[0], 1e-8)
    projected[1] = np.clip(projected[1], 1e-6, 1.0 - 1e-6)
    projected[2:] = np.clip(projected[2:], 1e-8, 1.0 - 1e-8)
    return raw, projected


def bound_flags(params, b0):
    s0, fraction, fast, slow = np.asarray(params, float)
    a = s0 / b0 if np.isfinite(b0) and b0 > 0 else np.nan
    distances = [a, fraction, 1-fraction, fast, 1-fast, slow, 1-slow, fast-slow]
    return "|".join(name for name, value in zip(BOUND_NAMES, distances)
                    if np.isfinite(value) and value <= FLAG_EPS)


def empty_fit(status):
    return {"params": np.full(4, np.nan), "params_initial": np.full(4, np.nan),
            "params_initial_unprojected": np.full(4, np.nan), "status": status,
            "optimizer_status": np.nan, "nfev": 0, "init_projected": False,
            "component_swap": False, "bound_flags": "", "fallback": False,
            "normalized_predictions": np.full(21, np.nan), "nrmse": np.nan, "cost": np.nan,
            "full_signal_cost": np.nan}


def finalize_fit(record, signal, b0, bvals):
    params = record["params"]
    if np.isfinite(params).all() and b0 > 0:
        q = params / np.asarray([b0, 1, 1, 1])
        prediction = normalized_prediction(q, bvals)
        if np.isfinite(prediction).all():
            record["normalized_predictions"] = prediction
            residual = prediction - np.asarray(signal) / b0
            record["nrmse"] = float(np.sqrt(np.mean(residual**2)))
            record["full_signal_cost"] = float(0.5 * np.sum(residual**2))
    record["bound_flags"] = bound_flags(params, b0)
    if record["status"] == "ok":
        s0, fraction, fast, slow = params
        if not np.isfinite(params).all() or not (s0 > 0 and 0 <= fraction <= 1 and 0 <= slow <= 1 and 0 <= fast <= 1):
            record["status"] = "invalid_parameters"
        elif not (0 < fraction < 1 and slow < fast):
            record["status"] = "degenerate_or_unordered"
    return record


def fit_voxel(signal, bvals, b0, tissue, eligible, method):
    if method not in METHODS:
        raise ValueError("unknown fitting method")
    if not tissue:
        return empty_fit("not_tissue")
    if not eligible:
        return empty_fit("invalid_signal")
    record = empty_fit("initialization_invalid")
    y, bvals = np.asarray(signal, float) / b0, np.asarray(bvals, float)
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            if method == "trr_explicit":
                raw, initial = trr_initialization(y, bvals)
            else:
                amplitude, slow = log_linear(y, bvals, bvals >= 200)
                fraction = 1.0 - amplitude
                raw = np.asarray([1.0, fraction, np.nan, slow])
                record["params"] = raw * np.asarray([b0, 1, 1, 1])
                record["params_initial_unprojected"] = raw.copy()
                if not np.isfinite([fraction, slow]).all():
                    return finalize_fit(record, signal, b0, bvals)
                if not (0 < fraction < 1 and 0 <= slow < 1):
                    record["status"] = "segmented_out_of_bounds"
                    return finalize_fit(record, signal, b0, bvals)
                raw[2] = 0.01
                initial = raw.copy()
                initial[2] = np.clip(0.01, slow + 1e-8*(1-slow), 1-1e-8*(1-slow))
    except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
        return record
    record["params_initial_unprojected"] = raw
    record["params_initial"] = initial
    record["init_projected"] = not np.array_equal(raw, initial)
    record["params"] = initial * np.asarray([b0, 1, 1, 1])
    record["status"] = "optimizer_failed"
    options = {key: value for key, value in SOLVER.items() if key != "jacobian"}
    try:
        if method == "trr_explicit":
            fit = least_squares(lambda q: normalized_prediction(q, bvals) - y, initial,
                                jac=lambda q: normalized_jacobian(q, bvals),
                                bounds=([0, 0, 0, 0], [np.inf, 1, 1, 1]),
                                x_scale=[1.0, 0.1, 0.01, 0.001], **options)
            candidate = np.asarray(fit.x, float).copy()
        else:
            low = bvals < 200
            fraction, slow = initial[1], initial[3]
            def residual(fast):
                q = [1.0, fraction, float(fast[0]), slow]
                return normalized_prediction(q, bvals[low]) - y[low]
            def jacobian(fast):
                return (-fraction * bvals[low] * np.exp(-bvals[low] * fast[0]))[:, None]
            fit = least_squares(residual, [initial[2]], jac=jacobian,
                                bounds=([slow], [1.0]), x_scale=[0.01], **options)
            candidate = np.asarray([1.0, fraction, float(fit.x[0]), slow])
        record["optimizer_status"] = int(fit.status)
        record["nfev"] = int(fit.nfev)
        record["cost"] = float(fit.cost)
        if bool(fit.success) and fit.status > 0:
            record["status"] = "ok"
            if method == "trr_explicit" and candidate[2] < candidate[3]:
                candidate[2], candidate[3] = candidate[3], candidate[2]
                candidate[1] = 1.0 - candidate[1]
                record["component_swap"] = True
        record["params"] = candidate * np.asarray([b0, 1, 1, 1])
    except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
        pass
    return finalize_fit(record, signal, b0, bvals)


def summarize(params, nrmse, mask):
    count = int(np.count_nonzero(mask))
    values = np.column_stack((params, nrmse))
    return {"n_voxels": count, **{
        name: float(values[mask, index].mean()) if count else None
        for index, name in enumerate(STAT_KEYS)}}


def summarize_results(arrays, common_valid, primary="trr_explicit"):
    fits = []
    common = {}
    for method in METHODS:
        params, residual = arrays[f"params_{method}"], arrays[f"nrmse_{method}"]
        own_valid = arrays[f"status_{method}"] == "ok"
        fits.append({"method": method, **summarize(params, residual, own_valid)})
        common[method] = summarize(params, residual, common_valid)
    delta = np.column_stack((arrays["params_segmented_b200"] - arrays["params_trr_explicit"],
                             arrays["nrmse_segmented_b200"] - arrays["nrmse_trr_explicit"]))
    count = int(np.count_nonzero(common_valid))
    differences = {name: float(delta[common_valid, index].mean()) if count else None
                   for index, name in enumerate(STAT_KEYS)}
    return {
        "status": "ok" if count else "failed_precondition",
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID, "primary_method": primary,
        "diffusivity_units": "mm^2/s", "n_box_voxels": 900,
        "n_tissue_voxels": int(np.count_nonzero(arrays["tissue_eligible"])),
        "n_eligible_voxels": int(np.count_nonzero(arrays["eligible"])), "fits": fits,
        "common_valid": {"n_voxels": count, "by_method": common,
                         "paired_differences": {"segmented_minus_trr": differences}},
        **({"reason": "no common numerically valid voxels"} if not count else {}),
    }


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def csv_value(value):
    if isinstance(value, (bool, np.bool_)):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return ""
    return value


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows([csv_value(value) for value in row] for row in rows)


def render_findings(arrays, result):
    """Describe measured fits and diagnostics without changing inclusion rules."""
    def fmt(value, signed=False):
        if value is None:
            return "undefined"
        return format(value, "+.9g" if signed else ".9g")

    common = arrays["common_valid"]
    n_common = int(np.count_nonzero(common))
    fits = {fit["method"]: fit for fit in result["fits"]}
    shared = result["common_valid"]["by_method"]
    lines = [
        "# IVIM numerical recipe comparison", "",
        f"All {result['n_box_voxels']} fixed-box coordinates are retained per recipe: "
        f"{result['n_tissue_voxels']} meet the source-tissue rule, "
        f"{result['n_eligible_voxels']} are input-eligible, and {n_common} belong to "
        f"the common numerically admissible set. Primary recipe: {result['primary_method']}.", "",
        "| Recipe | Own-valid n | Own-valid mean f | Common mean f | Common mean D (mm²/s) | Common mean Dstar (mm²/s) | Common mean NRMSE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in METHODS:
        own, paired = fits[method], shared[method]
        lines.append(f"| {method} | {own['n_voxels']} | {fmt(own['f_mean'])} | "
                     f"{fmt(paired['f_mean'])} | {fmt(paired['D_mean'])} | "
                     f"{fmt(paired['Dstar_mean'])} | {fmt(paired['nrmse_mean'])} |")
    differences = result["common_valid"]["paired_differences"]["segmented_minus_trr"]
    lines += ["", f"On the same {n_common} coordinates, the signed segmented-minus-TRR "
              f"mean differences are f={fmt(differences['f_mean'], True)}, "
              f"D={fmt(differences['D_mean'], True)} mm²/s, "
              f"Dstar={fmt(differences['Dstar_mean'], True)} mm²/s, "
              f"S0={fmt(differences['S0_mean'], True)} in source signal units, and "
              f"NRMSE={fmt(differences['nrmse_mean'], True)}. The own-valid means "
              "use different selected sets and are not substituted for this paired comparison.", "",
              "## Numerical QC", ""]
    for method in METHODS:
        statuses = arrays[f"status_{method}"]
        valid = statuses == "ok"
        flags = arrays[f"bound_flags_{method}"]
        flagged = flags != ""
        status_counts = ", ".join(f"{status}={int(np.sum(statuses == status))}"
                                  for status in STATUSES if np.any(statuses == status))
        def flag_counts(mask):
            counts = {name: sum(name in str(value).split("|") for value in flags[mask])
                      for name in BOUND_NAMES}
            return ", ".join(f"{name}={count}" for name, count in counts.items() if count) or "none"
        lines += [
            f"- {method}: status counts {status_counts}. Projected initializers="
            f"{int(np.sum(arrays[f'init_projected_{method}']))}; canonical component swaps="
            f"{int(np.sum(arrays[f'component_swap_{method}']))}; fallback fits="
            f"{int(np.sum(arrays[f'fallback_{method}']))}.",
            f"  Bound-flagged candidate rows: all={int(flagged.sum())}/{len(flags)}, "
            f"own-valid={int(np.sum(flagged & valid))}/{int(valid.sum())}, "
            f"common-valid={int(np.sum(flagged & common))}/{n_common}. "
            f"All-row flag counts: {flag_counts(np.ones(len(flags), dtype=bool))}. "
            f"Common-set flag counts: {flag_counts(common)}.", "",
        ]
    lines += [
        "Flag-type counts can overlap and include known parameter components from rejected "
        "rows; they are diagnostics, not additional exclusions. In particular, D_lower "
        "flags a slow coefficient at or near its numerical lower bound, and Dstar_D_lower "
        "flags nearly equal component diffusivities. Near-zero fractions and nearly "
        "coincident diffusivities can leave components weakly separated even when the "
        "strict numerical ordering test passes. No rows were removed using a post-hoc "
        "residual or boundary threshold.", "",
        "## Interpretation limits", "",
        "These are outputs of two declared numerical recipes on one registered, "
        "direction-averaged public acquisition, not the original Le Bihan sample, "
        "independent physiological perfusion truth, or evidence that these fitted "
        "parameters are identifiable. Recipes differ in S0 estimation, b-value subsets "
        "and optimization constraints; the measured gap is not attributable solely "
        "to the optimizer. Convergence, low signal residuals and repeatability do not "
        "establish unique parameter recovery or a biological perfusion mechanism. "
        "The common-set comparison is conditional on both recipes' numerical "
        "admissibility and is not a population estimate.", "",
    ]
    return "\n".join(lines)


def write_outputs(output, arrays, contract, primary="trr_explicit"):
    coordinates = arrays["roi_ijk"]
    common = arrays["common_valid"]
    diagnostic = ["status", "optimizer_status", "nfev", "init_projected", "component_swap",
                  "bound_flags", "fallback"]
    rows = []
    for method in METHODS:
        for index, coordinate in enumerate(coordinates):
            rows.append([*coordinate, method, *arrays[f"params_{method}"][index],
                         *[arrays[f"{key}_{method}"][index] for key in diagnostic],
                         arrays["eligible"][index], common[index], arrays[f"nrmse_{method}"][index]])
    write_csv(output / "parameters_voxelwise.csv",
              ["i", "j", "k", "method", *PARAMETER_ORDER, *diagnostic, "eligible", "common_valid", "nrmse"], rows)
    write_csv(output / "f_voxelwise.csv", ["i", "j", "k", "f"],
              ([*coordinate, fraction] for coordinate, fraction in zip(coordinates, arrays[f"params_{primary}"][:, 1])))
    write_csv(output / "f_sweep.csv", ["i", "j", "k", "method", "f"],
              ([*coordinate, method, fraction] for method in METHODS
               for coordinate, fraction in zip(coordinates, arrays[f"params_{method}"][:, 1])))
    result = summarize_results(arrays, common, primary)
    write_json(output / "ivim_results.json", result)
    write_json(output / "run_metadata.json", {
        **contract, "status": result["status"], "primary_method": primary, "fitted_methods": METHODS,
        "n_box_voxels": result["n_box_voxels"], "n_tissue_voxels": result["n_tissue_voxels"],
        "n_eligible_voxels": result["n_eligible_voxels"],
        "n_common_valid_voxels": result["common_valid"]["n_voxels"],
        "status_counts": {method: {status: int(np.sum(arrays[f"status_{method}"] == status))
                                  for status in STATUSES} for method in METHODS},
        **({"reason": result["reason"]} if "reason" in result else {}),
    })
    (output / "findings.md").write_text(render_findings(arrays, result))
    return result


def run(output_dir, data_dir):
    check_versions()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    image, bvals, _, hashes = load_inputs(data_dir)
    contract = metadata_contract(image, bvals, hashes)
    coordinates, signal, b0, tissue, eligible = extract_source_roi(image, bvals)
    arrays = {"roi_ijk": coordinates, "signal": signal, "bvals": bvals, "b0_observed": b0,
              "tissue_eligible": tissue, "eligible": eligible,
              "metadata_json": np.asarray(json.dumps(contract, sort_keys=True, allow_nan=False))}
    for method in METHODS:
        records = []
        for index in range(900):
            records.append(fit_voxel(signal[index], bvals, b0[index], tissue[index], eligible[index], method))
            if (index + 1) % 150 == 0:
                print(f"{method}: processed {index + 1}/900 fixed-box voxels", flush=True)
        for field in records[0]:
            arrays[f"{field}_{method}"] = np.asarray([record[field] for record in records])
    arrays["common_valid"] = eligible & (arrays["status_trr_explicit"] == "ok") & (arrays["status_segmented_b200"] == "ok")
    result = write_outputs(output, arrays, contract)
    np.savez_compressed(output / "fit_receipt.npz", **arrays)
    print(json.dumps(result, allow_nan=False))
    return result


def main():
    output = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
    data_dir = Path(os.environ.get("IVIM_DATA_DIR", "/app/data/ivim"))
    try:
        result = run(output, data_dir)
        return 0 if result["status"] == "ok" else 1
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "reason": str(error),
                   "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID}
        write_json(output / "run_metadata.json", failure)
        write_json(output / "ivim_results.json", failure)
        (output / "findings.md").write_text(f"# Failed precondition\n\n{error}\n")
        print(f"failed_precondition: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
