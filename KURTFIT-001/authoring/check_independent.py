"""Check a bounded sample of CFIN DKI fits with a separate NumPy WLS solver.

The weighted least-squares solve is independent of DIPY's fitting function.
Source preprocessing, ROI DTI, design matrices, parameter conversion, analytical
MK and signal prediction use the same scientific contract and shared libraries.
This is a numerical implementation check, not independent biological ground truth.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import gaussian_filter

from dipy.core.gradients import gradient_table
from dipy.reconst.dki import dki_prediction, mean_kurtosis, params_to_dki_params
from dipy.reconst.dti import TensorModel
from dipy.reconst.utils import dki_design_matrix
from dipy.segment.mask import median_otsu


CAPS = (1000, 1400, 2000, 2400, 3000)
MAX_VOXELS = 256
FWHM_MM = 1.25
MIN_SIGNAL = 1e-4
# Fixed before running: these allow small floating-point solver differences,
# while remaining far below meaningful changes in DKI tensors/maps or signal.
TOLERANCES = {
    "diffusion_tensor": {"atol": 1e-9, "rtol": 1e-6},
    "eigenvalues": {"atol": 1e-9, "rtol": 1e-6},
    "kurtosis_tensor": {"atol": 1e-5, "rtol": 1e-6},
    "mean_kurtosis": {"atol": 1e-5, "rtol": 1e-6},
    "S0_hat": {"atol": 1e-4, "rtol": 1e-6},
    "normalized_prediction": {"atol": 1e-6, "rtol": 1e-6},
    "nrmse": {"atol": 1e-7, "rtol": 1e-5},
}


def compare(actual, expected, *, atol, rtol):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape:
        raise ValueError(f"Comparison shape mismatch: {actual.shape} versus {expected.shape}")
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("Non-finite values in numerical comparison")
    difference = np.abs(actual - expected)
    mismatch = difference > atol + rtol * np.abs(expected)
    return {"passed": not bool(mismatch.any()), "n_mismatched_values": int(mismatch.sum()),
            "max_abs_difference": float(difference.max(initial=0)), "atol": atol, "rtol": rtol}


def load_sources(data_dir):
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    paths, hashes = {}, {}
    for row in manifest["files"]:
        path = data_dir / row["path"]
        if path.stat().st_size != row["size_bytes"]:
            raise ValueError(f"Source size changed: {path.name}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"Source digest changed: {path.name}")
        paths[row["role"]], hashes[row["path"]] = path, digest
    if set(paths) != {"image", "bval", "bvec"}:
        raise ValueError("Expected image, bval and bvec source roles")
    image = nib.load(paths["image"])
    if image.header.get_xyzt_units()[0] != "mm":
        raise ValueError("Physical smoothing requires NIfTI spatial units in mm")
    bvals = np.loadtxt(paths["bval"])
    bvecs = np.loadtxt(paths["bvec"]).T
    if image.shape[-1] != len(bvals) or bvecs.shape != (len(bvals), 3):
        raise ValueError("Source gradient table does not match image volumes")
    return image, bvals, bvecs, hashes


def solve_two_step_wls(design, signals):
    """OLS-derived signal weights, then weighted log-signal least squares.

Uses lstsq twice rather than DIPY's pinv-based ls_fit_dki. rcond=1e-15
matches the rank cutoff of the pinned implementation's default NumPy pinv.
S0 is the fitted intercept exp(-coefficient[-1]), not the observed b0 signal.
"""
    coefficients, params, fitted_s0 = [], [], []
    minimum_eigenvalue = 1e-6 / -float(design.min())
    for signal in signals:
        log_signal = np.log(np.maximum(signal, MIN_SIGNAL))
        initial = np.linalg.lstsq(design, log_signal, rcond=1e-15)[0]
        residual_weights = np.exp(design @ initial)
        weighted_design = design * residual_weights[:, None]
        weighted_response = log_signal * residual_weights
        result = np.linalg.lstsq(weighted_design, weighted_response, rcond=1e-15)[0]
        converted = params_to_dki_params(result, min_diffusivity=minimum_eigenvalue)
        if converted.shape != (28,):
            raise ValueError("Pinned DIPY parameter conversion must return 27 parameters plus fitted S0")
        coefficients.append(result)
        params.append(converted[:27])
        fitted_s0.append(converted[27])
    return np.asarray(coefficients), np.asarray(params), np.asarray(fitted_s0)


def diffusion_tensors(params):
    vectors = params[:, 3:12].reshape(-1, 3, 3)
    return (vectors * params[:, None, :3]) @ vectors.transpose(0, 2, 1)


def check(data_dir, oracle_output):
    if importlib.metadata.version("dipy") != "1.12.1":
        raise ValueError("This implementation check is pinned to DIPY 1.12.1")
    image, bvals, bvecs, hashes = load_sources(data_dir)
    with np.load(oracle_output / "fit_receipt.npz", allow_pickle=False) as source:
        receipt = {name: source[name] for name in source.files}
    oracle_metadata = json.loads(str(receipt["metadata_json"]))
    coords = np.asarray(receipt["roi_ijk"])
    if coords.ndim != 2 or coords.shape[1] != 3 or not np.issubdtype(coords.dtype, np.integer):
        raise ValueError("Receipt ROI coordinates must be an integer N by 3 array")
    if len(coords) == 0 or len(np.unique(coords, axis=0)) != len(coords):
        raise ValueError("Receipt ROI coordinates must be nonempty and unique")
    if oracle_metadata["source_sha256"] != hashes:
        raise ValueError("Oracle receipt source digests do not match staged inputs")
    if oracle_metadata["available_caps"] != list(CAPS) or oracle_metadata["primary_cap"] != 2000:
        raise ValueError("Oracle receipt does not declare the public shell caps")
    data = image.get_fdata(dtype=np.float64, caching="unchanged")
    zooms = np.asarray(image.header.get_zooms()[:3], dtype=float)
    sigma = FWHM_MM / (np.sqrt(8 * np.log(2)) * zooms)
    if not np.allclose(sigma * zooms * np.sqrt(8 * np.log(2)), FWHM_MM, atol=1e-12):
        raise ValueError("Physical smoothing conversion failed")
    preprocessing = oracle_metadata["preprocessing"]
    if (oracle_metadata["spatial_units"] != "mm" or preprocessing["fwhm_mm"] != FWHM_MM
            or preprocessing["mode"] != "reflect" or preprocessing["truncate"] != 4):
        raise ValueError("Oracle receipt declares a different physical smoothing contract")
    physical_checks = {
        "voxel_sizes_mm": compare(zooms, oracle_metadata["voxel_sizes_mm"], atol=1e-12, rtol=0),
        "sigma_vox": compare(np.r_[sigma, 0.0], preprocessing["sigma_vox"], atol=1e-12, rtol=0),
    }
    # The temporal/gradient dimension has zero sigma: no inter-volume smoothing.
    smoothed = gaussian_filter(data, sigma=tuple(sigma) + (0.0,), mode="reflect", truncate=4.0)
    _, brain = median_otsu(data[..., 0], median_radius=4, numpass=2, autocrop=False, dilate=1)
    del data
    moderate = bvals <= 2050
    moderate_gtab = gradient_table(bvals[moderate], bvecs=bvecs[moderate])
    fa = TensorModel(moderate_gtab, fit_method="WLS", min_signal=MIN_SIGNAL).fit(
        smoothed[..., moderate], mask=brain).fa
    roi = brain & np.isfinite(fa) & (fa > 0.4)
    expected_coords = np.argwhere(roi)
    if not np.array_equal(coords, expected_coords):
        raise ValueError(f"Receipt ROI differs from shared DTI reconstruction: {len(coords)} versus {len(expected_coords)} voxels")
    roi_fa = fa[roi]
    source_b0 = smoothed[..., bvals <= 50].mean(axis=-1)[roi]
    roi_checks = {
        "fa": compare(roi_fa, receipt["fa"], atol=1e-10, rtol=1e-8),
        "S0_b0": compare(source_b0, receipt["S0_b0"], atol=1e-10, rtol=1e-8),
    }
    rows = np.unique(np.linspace(0, len(coords) - 1, min(MAX_VOXELS, len(coords)), dtype=int))
    sampled_coords = coords[rows]
    signals = smoothed[tuple(sampled_coords.T)]
    del smoothed
    sampled_b0 = source_b0[rows]
    if not np.all(sampled_b0 > 0):
        raise ValueError("NRMSE normalization requires positive observed b0 signal")
    cap_reports = []
    for cap in CAPS:
        selected = bvals <= cap + 50
        declared = oracle_metadata["shell_subsets"][str(cap)]
        if (not np.array_equal(np.flatnonzero(selected), declared["volume_indices"])
                or not np.array_equal(bvals[selected], declared["bvals"])
                or declared["max_b"] != cap):
            raise ValueError(f"Oracle source-volume membership differs for cap {cap}")
        gtab = gradient_table(bvals[selected], bvecs=bvecs[selected])
        design = dki_design_matrix(gtab)
        y = signals[:, selected]
        coefficients, params, s0_hat = solve_two_step_wls(design, y)
        oracle_params = receipt[f"params_cap_{cap}"][rows]
        oracle_s0 = receipt[f"S0_hat_cap_{cap}"][rows]
        mk = mean_kurtosis(params, min_kurtosis=0, max_kurtosis=3, analytical=True, fast=True)
        predicted = dki_prediction(params, gtab, S0=s0_hat)
        oracle_predicted = dki_prediction(oracle_params, gtab, S0=oracle_s0)
        nrmse = np.sqrt(np.mean((predicted - y) ** 2, axis=-1)) / sampled_b0
        oracle_residual = np.sqrt(np.mean((oracle_predicted - y) ** 2, axis=-1)) / sampled_b0
        comparisons = {
            "diffusion_tensor": compare(diffusion_tensors(params), diffusion_tensors(oracle_params), **TOLERANCES["diffusion_tensor"]),
            "eigenvalues": compare(params[:, :3], oracle_params[:, :3], **TOLERANCES["eigenvalues"]),
            "kurtosis_tensor": compare(params[:, 12:27], oracle_params[:, 12:27], **TOLERANCES["kurtosis_tensor"]),
            "mean_kurtosis": compare(mk, receipt[f"map_cap_{cap}"][rows], **TOLERANCES["mean_kurtosis"]),
            "S0_hat": compare(s0_hat, oracle_s0, **TOLERANCES["S0_hat"]),
            "normalized_prediction": compare(predicted / sampled_b0[:, None], oracle_predicted / sampled_b0[:, None], **TOLERANCES["normalized_prediction"]),
            "nrmse": compare(nrmse, receipt[f"nrmse_cap_{cap}"][rows], **TOLERANCES["nrmse"]),
            "oracle_receipt_nrmse_recomputed": compare(oracle_residual, receipt[f"nrmse_cap_{cap}"][rows], atol=1e-10, rtol=1e-8),
        }
        # Eigenvector signs are arbitrary; compare reconstructed diffusion tensors
        # and kurtosis components rather than rejecting equivalent sign choices.
        cap_reports.append({"cap": cap, "actual_max_b": float(bvals[selected].max()),
                            "selected_volume_count": int(selected.sum()), "n_tested_voxels": len(rows),
                            "design_rank": int(np.linalg.matrix_rank(design)),
                            "design_condition_number": float(np.linalg.cond(design)),
                            "comparisons": comparisons,
                            "independent_sample_mean_mk": float(np.mean(mk)),
                            "independent_sample_nrmse_range": [float(nrmse.min()), float(nrmse.max())]})
    passed = all(item["passed"] for item in [*physical_checks.values(), *roi_checks.values()]) and all(
        item["passed"] for cap in cap_reports for item in cap["comparisons"].values())
    return {
        "status": "passed" if passed else "failed", "source_sha256": hashes,
        "physical_smoothing": {"fwhm_mm": FWHM_MM, "nifti_spatial_unit": "mm", "voxel_sizes_mm": zooms.tolist(),
                               "sigma_vox": sigma.tolist(), "gradient_axis_sigma": 0.0, "mode": "reflect", "truncate": 4.0,
                               "oracle_metadata_comparisons": physical_checks},
        "roi_validation": {"method": "shared DIPY median_otsu and moderate-b DTI WLS implementation",
                           "n_voxels": len(coords), "exact_coordinate_membership": True, "comparisons": roi_checks},
        "sampling": {"max_voxels_per_cap": MAX_VOXELS, "method": "equally spaced indices in full lexicographic ROI order",
                     "row_indices": rows.tolist(), "tested_coords": sampled_coords.tolist()},
        "caps": cap_reports, "oracle_metadata": oracle_metadata,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/cfin"))
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "evidence_type": "independent_weighted_least_squares_numerical_check",
        "independent_components": ["OLS and weighted log-signal solves using NumPy lstsq", "physical FWHM-to-voxel sigma formula"],
        "shared_components": ["source data", "SciPy Gaussian filtering", "DIPY brain mask and DTI ROI fitting",
                              "DIPY gradient/design matrix", "DIPY parameter conversion and eigenvalue floor",
                              "DIPY analytical MK", "DIPY signal prediction", "NumPy/LAPACK numerical libraries"],
        "interpretation_limit": "Samples at most 256 ROI voxels per cap and independently checks the WLS implementation only; shared components are not independent validation, and no biological truth is established.",
        "pinned_algorithm_source": "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/reconst/dki.py",
        "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ["numpy", "scipy", "nibabel", "dipy"]}},
        "tolerances": TOLERANCES,
    }
    try:
        report.update(check(args.data_dir, args.oracle_output))
    except Exception as exc:
        report.update(status="error", error_type=type(exc).__name__, error=str(exc))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "error": report.get("error"), "report": str(args.report)}))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
