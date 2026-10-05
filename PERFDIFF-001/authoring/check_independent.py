"""Check IVIM source/receipts with separate equations and bounded solver diagnostics.

This does not import the oracle. Centered scalar OLS, signal prediction, analytic
derivatives, ROI membership, and validity are implemented separately. An optional
32-voxel dogbox diagnostic shares SciPy and the public objective with the oracle,
but uses another solver. Parameter disagreement is not automatically an error:
biexponential fits can be poorly identified. No biological ground truth is claimed.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.optimize import least_squares


METHODS = ("trr_explicit", "segmented_b200")
MAX_DIAGNOSTIC_VOXELS = 32
X_SCALE = np.array([1.0, 0.1, 0.01, 0.001])
UPPER = np.array([np.inf, 1.0, 1.0, 1.0])
BOUND_NAMES = ("a_lower", "f_lower", "f_upper", "Dstar_lower", "Dstar_upper",
               "D_lower", "D_upper", "Dstar_D_lower")
EXPECTED_FILES = {
    "IVIM.nii.gz": "c360a1eb252815bf6ad5cc1d27ff351bc57aaaea3349853c97a5cb5176cf727d",
    "IVIM.bvals": "0d35b62862dc648dea241290024a3b6aeb2f7b63aaba79ac1a03e9001f8afea1",
    "IVIM.bvecs": "1d3262bf345cab948873c2347a2e05d5117881a6fac2bc14a7949b7fb6c12aa3",
}
# Predeclared before the native oracle run; not widened to fit its results.
TOLERANCES = {
    "prediction": {"atol": 1e-12, "rtol": 1e-10},
    "initialization": {"atol": 1e-10, "rtol": 1e-8},
    "analytic_jacobian": {"atol": 1e-10, "rtol": 1e-10},
}
DOGBOX_SETTINGS = {
    "method": "dogbox", "loss": "linear", "tr_solver": "exact",
    "ftol": 1e-10, "xtol": 1e-10, "gtol": 1e-10, "max_nfev": 2000,
}


def compare(actual, expected, *, atol=0, rtol=0):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape:
        raise ValueError(f"Shape mismatch: {actual.shape} versus {expected.shape}")
    finite = np.isfinite(actual) & np.isfinite(expected)
    same_missing = np.isnan(actual) & np.isnan(expected)
    differences = np.abs(actual[finite].astype(float) - expected[finite].astype(float))
    bad = int(np.sum(~finite & ~same_missing))
    bad += int(np.sum(differences > atol + rtol * np.abs(expected[finite])))
    return {"passed": bad == 0, "n_mismatched_values": bad,
            "n_finite_comparisons": int(finite.sum()),
            "n_matching_nan_values": int(same_missing.sum()),
            "max_abs_difference": float(differences.max(initial=0)), "atol": atol, "rtol": rtol}


def biexponential(q, bvals):
    """q=[S0_fit/S0_observed, f, Dstar, D], signal in observed-b0 units."""
    a, f, fast, slow = q
    return a * (f * np.exp(-bvals * fast) + (1 - f) * np.exp(-bvals * slow))


def analytic_jacobian(q, bvals):
    a, f, fast, slow = q
    ef, es = np.exp(-bvals * fast), np.exp(-bvals * slow)
    return np.column_stack((f * ef + (1 - f) * es,
                            a * (ef - es), -a * f * bvals * ef,
                            -a * (1 - f) * bvals * es))


def complex_step_jacobian(q, bvals):
    result = np.empty((len(bvals), 4))
    for column in range(4):
        perturbed = np.asarray(q, dtype=complex).copy()
        perturbed[column] += 1e-30j
        result[:, column] = np.imag(biexponential(perturbed, bvals)) / 1e-30
    return result


def centered_log_ols(signal, bvals, selection):
    """Closed-form centered regression; no shared lstsq or oracle helper."""
    x = bvals[selection]
    log_y = np.log(signal[selection])
    centered_x = x - np.mean(x)
    slope = np.dot(centered_x, log_y - np.mean(log_y)) / np.dot(centered_x, centered_x)
    intercept = np.mean(log_y) - slope * np.mean(x)
    return float(np.exp(intercept)), float(-slope)


def trr_initializer(normalized_signal, bvals):
    amplitude_high, slow = centered_log_ols(normalized_signal, bvals, bvals >= 400)
    a, fast = centered_log_ols(normalized_signal, bvals, bvals <= 200)
    raw = np.array([a, 1 - amplitude_high / a, fast, slow])
    projected = np.array([max(a, 1e-8), np.clip(raw[1], 1e-6, 1 - 1e-6),
                          np.clip(fast, 1e-8, 1 - 1e-8), np.clip(slow, 1e-8, 1 - 1e-8)])
    return raw, projected


def segmented_initializer(normalized_signal, bvals):
    amplitude_high, slow = centered_log_ols(normalized_signal, bvals, bvals >= 200)
    fraction = 1 - amplitude_high
    if not (0 < fraction < 1 and 0 <= slow < 1):
        return np.array([1.0, fraction, np.nan, slow]), False
    margin = 1e-8 * (1 - slow)
    fast = np.clip(0.01, slow + margin, 1 - margin)
    return np.array([1.0, fraction, fast, slow]), True


def source_data(data_dir):
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    if manifest["source_version"] != "figshare-3395704-v1":
        raise ValueError("Expected the pinned Figshare version 1 IVIM source")
    if len(manifest["files"]) != 3 or {row["path"] for row in manifest["files"]} != set(EXPECTED_FILES):
        raise ValueError("Expected exactly the three source observations, not the supplied fitted map")
    hashes = {}
    for row in manifest["files"]:
        path = data_dir / row["path"]
        if path.stat().st_size != row["size_bytes"]:
            raise ValueError(f"Source size mismatch: {path.name}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != EXPECTED_FILES[path.name] or digest != row["sha256"]:
            raise ValueError(f"Source digest mismatch: {path.name}")
        hashes[path.name] = digest
    image = nib.load(data_dir / "IVIM.nii.gz")
    bvals, bvecs = np.loadtxt(data_dir / "IVIM.bvals"), np.loadtxt(data_dir / "IVIM.bvecs")
    if image.shape != (256, 256, 54, 21) or bvals.shape != (21,) or bvecs.shape != (3, 21):
        raise ValueError("Unexpected image or acquisition dimensions")
    if image.header.get_xyzt_units()[0] != "mm" or np.sum(bvals == 0) != 1:
        raise ValueError("Unexpected header units or actual b0 count")
    # Read the deposited float32 image once; no smoothing, clipping, or resampling.
    native = np.asanyarray(image.dataobj)
    signal = np.asarray(native[90:120, 90:120, 33, :], float).reshape(900, 21)
    del native
    coordinates = np.array([(i, j, 33) for i in range(90, 120) for j in range(90, 120)])
    b0 = signal[:, bvals == 0].mean(axis=1)
    positive_b0 = b0[np.isfinite(b0) & (b0 > 0)]
    if not len(positive_b0):
        raise ValueError("No positive source b0 in the fixed box")
    threshold = 0.5 * float(np.median(positive_b0))
    tissue = np.isfinite(b0) & (b0 > threshold)
    eligible = tissue & np.all(np.isfinite(signal) & (signal > 0), axis=1)
    evidence = {"sha256": hashes, "shape": list(image.shape),
                "header_zooms": [float(v) for v in image.header.get_zooms()],
                "affine": image.affine.tolist(),
                "nifti_spatial_units": image.header.get_xyzt_units()[0],
                "axis_codes": list(nib.aff2axcodes(image.affine)), "bvals": bvals.tolist(),
                "actual_b0_threshold": 0, "tissue_threshold": threshold,
                "n_box_voxels": 900, "n_tissue_eligible": int(tissue.sum()),
                "n_positive_finite_signal_eligible": int(eligible.sum()),
                "processing_boundary": "Source already registered and direction-averaged; not raw directions."}
    return signal, bvals, b0, coordinates, tissue, eligible, evidence


def canonicalize(q):
    result = np.asarray(q, float).copy()
    if result[2] < result[3]:
        result[1] = 1 - result[1]
        result[2], result[3] = result[3], result[2]
    return result


def jacobian_diagnostics(q, bvals, measured):
    jacobian = analytic_jacobian(q, bvals)
    singular = np.linalg.svd(jacobian * X_SCALE[None, :], compute_uv=False)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else None
    gradient = jacobian.T @ (biexponential(q, bvals) - measured)
    return {"scaled_jacobian_singular_values": singular.tolist(),
            "scaled_jacobian_condition": condition,
            "scaled_gradient_infinity_norm": float(np.max(np.abs(gradient * X_SCALE)))}


def dogbox_diagnostic(receipt, signal, bvals, b0, eligible):
    """Different nonlinear solver; diagnostic cost/prediction comparisons, not truth."""
    params = receipt["params_trr_explicit"]
    successful = eligible & (receipt["optimizer_status_trr_explicit"] > 0) & np.all(np.isfinite(params), axis=1)
    candidates = np.flatnonzero(successful)
    if not len(candidates):
        raise ValueError("No converged eligible TRR rows available for a bounded diagnostic")
    rows = candidates[np.unique(np.linspace(0, len(candidates) - 1,
                                           min(MAX_DIAGNOSTIC_VOXELS, len(candidates)), dtype=int))]
    comparisons = []
    for row in rows:
        measured = signal[row] / b0[row]
        _, initial = trr_initializer(measured, bvals)
        fitted = least_squares(lambda q: biexponential(q, bvals) - measured, initial,
                               jac=lambda q: analytic_jacobian(q, bvals),
                               bounds=(np.zeros(4), UPPER), x_scale=X_SCALE, **DOGBOX_SETTINGS)
        independent = canonicalize(fitted.x)
        original = params[row].copy()
        original[0] /= b0[row]
        independent_prediction = biexponential(independent, bvals)
        original_prediction = biexponential(original, bvals)
        independent_cost = float(np.mean((independent_prediction - measured) ** 2))
        original_cost = float(np.mean((original_prediction - measured) ** 2))
        comparisons.append({
            "row": int(row), "ijk": receipt["roi_ijk"][row].tolist(),
            "dogbox_success": bool(fitted.success), "dogbox_status": int(fitted.status),
            "dogbox_message": str(fitted.message), "dogbox_nfev": int(fitted.nfev),
            "dogbox_optimality": float(fitted.optimality),
            "independent_q": independent.tolist(), "oracle_q": original.tolist(),
            "max_abs_parameter_difference": float(np.max(np.abs(independent - original))),
            "max_abs_prediction_difference_over_b0": float(np.max(np.abs(independent_prediction - original_prediction))),
            "dogbox_normalized_mean_squared_error": independent_cost,
            "oracle_normalized_mean_squared_error": original_cost,
            "cost_difference_dogbox_minus_oracle": independent_cost - original_cost,
            "oracle_jacobian": jacobian_diagnostics(original, bvals, measured),
            "dogbox_jacobian": jacobian_diagnostics(independent, bvals, measured),
        })
    return {"role": "diagnostic_only_not_parameter_ground_truth", "n_voxels": len(rows),
            "selection": "At most 32 evenly spaced source-order successful TRR rows; no residual-based selection.",
            "settings": DOGBOX_SETTINGS, "x_scale": X_SCALE.tolist(),
            "n_dogbox_nonconverged": sum(not row["dogbox_success"] for row in comparisons),
            "rows": comparisons,
            "limits": "Both solvers share SciPy, objective, bounds and initialization contract. Dogbox is not recommended for rank-deficient Jacobians; these bounded runs diagnose cost/prediction sensitivity rather than proving parameter identifiability."}


def self_test():
    bvals = np.array([0., 10., 20., 100., 200., 400., 600., 1000.])
    comparisons = []
    for q in (np.array([1., .2, .03, .001]), np.array([.9, .001, .001, .001]),
              np.array([2., 0., 1., 0.]), np.array([1.1, 1., .003, .002])):
        comparisons.append(compare(analytic_jacobian(q, bvals), complex_step_jacobian(q, bvals),
                                   **TOLERANCES["analytic_jacobian"]))
        swapped = np.array([q[0], 1-q[1], q[3], q[2]])
        comparisons.append(compare(biexponential(q, bvals), biexponential(swapped, bvals),
                                   **TOLERANCES["prediction"]))
    pure_decay = 1.3 * np.exp(-bvals * .002)
    amplitude, diffusion = centered_log_ols(pure_decay, bvals, bvals >= 200)
    comparisons.append(compare(np.array([amplitude, diffusion]), np.array([1.3, .002]),
                               **TOLERANCES["initialization"]))
    return {"passed": all(row["passed"] for row in comparisons), "checks": comparisons,
            "scope": "Analytic equations, complex-step derivatives, component symmetry, and exact monoexponential OLS only; no source-data model fitting."}


def receipt_checks(receipt, signal, bvals, b0, coordinates, tissue, eligible):
    checks = {
        "source_coordinates_all_900": compare(receipt["roi_ijk"], coordinates),
        "source_signal": compare(receipt["signal"], signal),
        "source_bvals": compare(receipt["bvals"], bvals),
        "observed_b0_only_actual_b0": compare(receipt["b0_observed"], b0),
        "tissue_eligibility": compare(receipt["tissue_eligible"], tissue),
        "positive_finite_signal_eligibility": compare(receipt["eligible"], eligible),
    }
    methods, valid_by_method = {}, {}
    for method in METHODS:
        params = receipt[f"params_{method}"]
        if params.shape != (900, 4):
            raise ValueError(f"All 900 source rows and four parameters are required for {method}")
        prediction = np.full_like(signal, np.nan)
        nrmse = np.full(900, np.nan)
        costs = np.full(900, np.nan)
        full_costs = np.full(900, np.nan)
        expected_initial = np.full((900, 4), np.nan)
        expected_unprojected = np.full((900, 4), np.nan)
        projected = np.zeros(900, bool)
        analytic_checks = []
        optimizer_status = receipt[f"optimizer_status_{method}"]
        for row in np.flatnonzero(eligible):
            measured = signal[row] / b0[row]
            if method == "trr_explicit":
                raw, initial = trr_initializer(measured, bvals)
                expected_unprojected[row], expected_initial[row] = raw, initial
                projected[row] = bool(np.any(raw != initial))
            else:
                initial, feasible = segmented_initializer(measured, bvals)
                expected_unprojected[row] = initial
                if feasible:
                    expected_initial[row] = initial
                    expected_unprojected[row, 2] = 0.01
                    projected[row] = bool(expected_unprojected[row, 2] != initial[2])
            if np.isfinite(params[row]).all():
                q = params[row].copy()
                q[0] /= b0[row]
                prediction[row] = biexponential(q, bvals)
                nrmse[row] = np.sqrt(np.mean((prediction[row] - measured) ** 2))
                full_costs[row] = 0.5 * np.sum((prediction[row] - measured) ** 2)
                if np.isfinite(optimizer_status[row]):
                    selected = np.ones(len(bvals), bool) if method == "trr_explicit" else bvals < 200
                    costs[row] = 0.5 * np.sum((prediction[row, selected] - measured[selected]) ** 2)
                if len(analytic_checks) < MAX_DIAGNOSTIC_VOXELS:
                    analytic_checks.append(compare(analytic_jacobian(q, bvals),
                                                   complex_step_jacobian(q, bvals),
                                                   **TOLERANCES["analytic_jacobian"]))
        valid = (eligible & (optimizer_status > 0) & np.isfinite(params).all(axis=1)
                 & (params[:, 0] > 0) & (params[:, 1] > 0) & (params[:, 1] < 1)
                 & (params[:, 3] >= 0) & (params[:, 3] < params[:, 2]) & (params[:, 2] <= 1))
        valid_by_method[method] = valid
        method_checks = {
            "predictions_from_source_and_fitted_parameters": compare(
                receipt[f"normalized_predictions_{method}"], prediction, **TOLERANCES["prediction"]),
            "all_bvalue_normalized_rmse": compare(receipt[f"nrmse_{method}"], nrmse,
                                                 **TOLERANCES["prediction"]),
            "optimizer_objective_recomputed": compare(receipt[f"cost_{method}"], costs,
                                                       **TOLERANCES["prediction"]),
            "all_bvalue_signal_cost": compare(receipt[f"full_signal_cost_{method}"], full_costs,
                                               **TOLERANCES["prediction"]),
            "independent_centered_OLS_initialization": compare(receipt[f"params_initial_{method}"],
                                                               expected_initial, **TOLERANCES["initialization"]),
            "independent_raw_initialization": compare(receipt[f"params_initial_unprojected_{method}"],
                                                       expected_unprojected, **TOLERANCES["initialization"]),
            "source_and_parameter_status_eligibility": compare(receipt[f"status_{method}"] == "ok", valid),
            "initializer_projection_only": compare(receipt[f"init_projected_{method}"], projected),
            "no_undisclosed_fallback": compare(receipt[f"fallback_{method}"], np.zeros(900, bool)),
        }
        expected_flags = []
        for row in range(900):
            amplitude, fraction, fast, slow = params[row]
            amplitude = amplitude / b0[row] if np.isfinite(b0[row]) and b0[row] > 0 else np.nan
            distances = [amplitude, fraction, 1-fraction, fast, 1-fast, slow, 1-slow, fast-slow]
            expected_flags.append("|".join(name for name, distance in zip(BOUND_NAMES, distances)
                                           if np.isfinite(distance) and distance <= 1e-8))
        method_checks["boundary_flags_not_exclusion"] = compare(
            np.asarray(receipt[f"bound_flags_{method}"]) == np.asarray(expected_flags), np.ones(900, bool))
        if method == "segmented_b200":
            method_checks["fixed_measured_S0"] = compare(params[eligible, 0], b0[eligible],
                                                        **TOLERANCES["prediction"])
            fitted = eligible & np.isfinite(params).all(axis=1)
            method_checks["segmented_f_and_D_from_high_b_OLS"] = compare(
                params[fitted][:, [1, 3]], expected_initial[fitted][:, [1, 3]],
                **TOLERANCES["initialization"])
        methods[method] = {
            "checks": method_checks, "analytic_vs_complex_step_jacobian_checks": analytic_checks,
            "n_admissible_converged_rows": int(valid.sum()),
            "n_optimizer_not_converged": int(np.sum(eligible & np.isfinite(optimizer_status) & (optimizer_status <= 0))),
            "n_initialization_projected": int(projected.sum()),
            "nrmse_quantiles_0_50_95_100": np.quantile(nrmse[np.isfinite(nrmse)], [0, .5, .95, 1]).tolist()
            if np.isfinite(nrmse).any() else [],
        }
    common = valid_by_method[METHODS[0]] & valid_by_method[METHODS[1]]
    checks["common_support_not_residual_filtered"] = compare(receipt["common_valid"], common)
    if not common.any():
        raise ValueError("No common valid support; no cross-method result can be validated")
    all_checks = list(checks.values())
    for method in methods.values():
        all_checks.extend(method["checks"].values())
        all_checks.extend(method["analytic_vs_complex_step_jacobian_checks"])
    return {"passed": all(row["passed"] for row in all_checks), "source_checks": checks,
            "methods": methods, "n_common_valid": int(common.sum())}


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/ivim"))
    parser.add_argument("--oracle-output", type=Path, default=Path("/oracle"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true", help="Equation fixtures only; no source fits")
    parser.add_argument("--skip-dogbox", action="store_true", help="Explicitly omit the separate nonlinear diagnostic")
    args = parser.parse_args()
    report = {"check": "independent_IVIM_receipt_algebra_and_bounded_solver_diagnostic",
              "versions": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "nibabel")},
              "python": platform.python_version(), "tolerances": TOLERANCES,
              "independent_components": ["Source-byte verification and manual fixed-box extraction",
                                         "Centered scalar OLS rather than oracle least-squares helper",
                                         "Biexponential prediction and analytic derivatives checked by complex step",
                                         "Common support and source-level residual reconstruction",
                                         "Bounded dogbox diagnostic rather than the oracle TRF solver"],
              "shared_components": ["Same pinned input data and publicly specified estimator contract",
                                    "NumPy/SciPy/nibabel numerical and image libraries",
                                    "Same mathematical objective, bounds and initializer contract for the nonlinear diagnostic"],
              "claim_limits": ["Receipt algebra and a second solver do not establish unbiased perfusion parameters.",
                               "Dogbox comparisons are diagnostic; convergence and parameter/prediction/cost gaps require interpretation with Jacobian conditioning.",
                               "This is not a reproduction of the original Le Bihan cohort or evidence of model-agent difficulty."]}
    try:
        if report["versions"]["scipy"] != "1.14.1":
            raise ValueError("This check targets the pinned SciPy 1.14.1 solver contract")
        report["equation_fixtures"] = self_test()
        if args.self_test:
            report["passed"] = report["equation_fixtures"]["passed"]
        else:
            signal, bvals, b0, coordinates, tissue, eligible, source = source_data(args.data_dir)
            report["source"] = source
            with np.load(args.oracle_output / "fit_receipt.npz", allow_pickle=False) as archive:
                receipt = {key: archive[key] for key in archive.files}
            contract = json.loads(str(receipt["metadata_json"]))
            if (contract["b0_threshold"] != 0
                    or contract["source_processing"] != "depositor_registered_and_direction_averaged"
                    or contract["source_sha256"] != source["sha256"]
                    or contract["header_spatial_units"] != source["nifti_spatial_units"]
                    or not np.array_equal(contract["affine"], source["affine"])
                    or not np.array_equal(contract["header_voxel_sizes"], source["header_zooms"][:3])):
                raise ValueError("Receipt source identity, geometry, processing or actual-b0 contract mismatch")
            report["receipt_checks"] = receipt_checks(receipt, signal, bvals, b0, coordinates, tissue, eligible)
            report["dogbox_diagnostic"] = ({"status": "explicitly_skipped"} if args.skip_dogbox else
                                            dogbox_diagnostic(receipt, signal, bvals, b0, eligible))
            report["passed"] = report["equation_fixtures"]["passed"] and report["receipt_checks"]["passed"]
            report["pass_scope"] = "Source, public initialization, predictions, objectives, derivatives and support checks only; nonlinear parameter identifiability is not a pass/fail claim."
    except Exception as error:
        report["passed"] = False
        report["error"] = f"{type(error).__name__}: {error}"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(json_safe(report), indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
