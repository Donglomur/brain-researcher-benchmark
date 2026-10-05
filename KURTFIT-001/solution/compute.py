"""Offline CFIN physical-mm WLS diffusion-kurtosis sensitivity baseline.

Every shell-cap fit uses a single ROI selected by the public DTI recipe. Importing
this module does not load source data, fit models, or write outputs.
"""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np

PIPELINE_ID = "cfin-physical-wls-v2"
DATASET_ID = "cfin-multib"
DIPY_VERSION = "1.12.1"
CAPS = [1000, 1400, 2000, 2400, 3000]
PRIMARY_CAP = 2000
SHELL_TOLERANCE = 50
B0_THRESHOLD = 50
FA_THRESHOLD = 0.4
MIN_SIGNAL = 0.0001
FWHM_MM = 1.25
MASK_PARAMETERS = {"vol_idx": [0], "median_radius": 4, "numpass": 2,
                   "autocrop": False, "dilate": 1}
DKI_PARAMETERS = {"fit_method": "WLS", "min_signal": MIN_SIGNAL,
                  "return_S0_hat": True, "mk_clip": [0, 3],
                  "analytical": True, "fast": True, "dipy_version": DIPY_VERSION}


def gaussian_sigma(fwhm_mm, voxel_sizes_mm):
    """Use the task's tested physical-width conversion without import side effects."""
    spec = importlib.util.spec_from_file_location("cfin_physical", Path(__file__).with_name("physical.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.gaussian_sigma(fwhm_mm, voxel_sizes_mm)


def load_inputs(data_dir):
    """Verify the staged source bytes and acquire gradients without network access."""
    import nibabel as nib
    from dipy.io.gradients import read_bvals_bvecs

    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    files = manifest["files"]
    if len(files) != 3:
        raise ValueError("require the image, b-values, and b-vectors")
    paths, hashes = {}, {}
    for item in files:
        relative = Path(item["path"])
        path = (data_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(data_dir):
            raise ValueError("source manifest path escapes the data directory")
        role = item["role"]
        if role not in {"image", "bval", "bvec"} or role in paths or item["path"] in hashes:
            raise ValueError("duplicate or unknown source role")
        if path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"source size mismatch: {relative}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"source SHA256 mismatch: {relative}")
        paths[role] = path
        hashes[item["path"]] = digest
    image = nib.load(paths["image"])
    bvals, bvecs = read_bvals_bvecs(paths["bval"], paths["bvec"])
    bvals, bvecs = np.asarray(bvals, float), np.asarray(bvecs, float)
    if len(image.shape) != 4 or bvals.shape != (image.shape[-1],) or bvecs.shape != (len(bvals), 3):
        raise ValueError("source image volume count and gradient dimensions disagree")
    if not np.isfinite(bvals).all() or not np.isfinite(bvecs).all() or np.any(bvals < 0):
        raise ValueError("invalid source gradient table")
    if image.header.get_xyzt_units()[0] != "mm" or not np.isfinite(image.affine).all():
        raise ValueError("source spatial geometry must have finite affine and millimeter units")
    if bvals[0] > B0_THRESHOLD:
        raise ValueError("source volume zero must be a b0 for the declared mask")
    return image, bvals, bvecs, hashes


def subset_contract(bvals):
    subsets = {}
    for cap in CAPS:
        indices = np.flatnonzero(bvals <= cap + SHELL_TOLERANCE)
        selected = bvals[indices]
        if not len(indices) or float(selected.max()) != cap or len(np.unique(selected)) < 3:
            raise ValueError(f"source gradients do not support the declared cap {cap}")
        subsets[str(cap)] = {"volume_indices": indices.tolist(), "bvals": selected.tolist(),
                             "shells": np.unique(selected).tolist(), "max_b": int(cap)}
    return subsets


def metadata_contract(image, bvals, source_sha256):
    zooms = [float(x) for x in image.header.get_zooms()[:3]]
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID,
        "source_sha256": source_sha256, "shape": list(image.shape),
        "affine": image.affine.tolist(), "voxel_sizes_mm": zooms, "spatial_units": "mm",
        "preprocessing": {"brain_mask": MASK_PARAMETERS, "fwhm_mm": FWHM_MM,
                          "sigma_vox": list(gaussian_sigma(FWHM_MM, zooms)),
                          "mode": "reflect", "truncate": 4},
        "roi": {"method": "DTI-WLS", "max_b": PRIMARY_CAP,
                "selection_tolerance": SHELL_TOLERANCE, "fa_threshold": FA_THRESHOLD,
                "min_signal": MIN_SIGNAL, "finite_fa_required": True},
        "dki": DKI_PARAMETERS, "gradient_b0_threshold": B0_THRESHOLD,
        "primary_cap": PRIMARY_CAP, "available_caps": CAPS,
        "shell_subsets": subset_contract(bvals),
    }


def prepare_data(image, bvals, bvecs):
    """Create the original-b0 mask, smoothed source and MK-independent fixed ROI."""
    import dipy
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import TensorModel
    from dipy.segment.mask import median_otsu
    from scipy.ndimage import gaussian_filter

    if dipy.__version__ != DIPY_VERSION:
        raise ValueError(f"this declared baseline requires DIPY {DIPY_VERSION}")
    data = image.get_fdata(dtype=np.float64, caching="unchanged")
    if not np.isfinite(data).all():
        raise ValueError("source contains nonfinite diffusion signal")
    masked, brain_mask = median_otsu(data, **MASK_PARAMETERS)
    del masked
    sigma = gaussian_sigma(FWHM_MM, image.header.get_zooms()[:3])
    smoothed = gaussian_filter(data, sigma=sigma, mode="reflect", truncate=4.0)
    del data
    selected = bvals <= PRIMARY_CAP + SHELL_TOLERANCE
    gradients = gradient_table(bvals[selected], bvecs=bvecs[selected], b0_threshold=B0_THRESHOLD)
    # Fit only brain voxels; fitting a matrix gives the same per-voxel WLS model.
    brain_signal = smoothed[brain_mask][:, selected]
    brain_fa = TensorModel(gradients, fit_method="WLS", min_signal=MIN_SIGNAL).fit(brain_signal).fa
    fa = np.zeros(brain_mask.shape, dtype=np.float64)
    fa[brain_mask] = brain_fa
    roi = brain_mask & np.isfinite(fa) & (fa > FA_THRESHOLD)
    if not roi.any():
        raise ValueError("the declared DTI white-matter ROI is empty")
    return smoothed, brain_mask, fa, roi


def predict_and_residual(parameters, fitted_s0, gradients, signal, observed_s0):
    """Normalize fitted-signal RMSE by the observed mean b0, not by fitted S0."""
    from dipy.reconst.dki import dki_prediction

    prediction = dki_prediction(parameters, gradients, S0=fitted_s0)
    residual = np.sqrt(np.mean(np.square(prediction - signal), axis=-1)) / observed_s0
    if not np.isfinite(prediction).all() or not np.isfinite(residual).all():
        raise ValueError("nonfinite DKI prediction or normalized residual")
    return residual


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def run(output_dir, data_dir):
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dki import DiffusionKurtosisModel

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image, bvals, bvecs, hashes = load_inputs(data_dir)
    contract = metadata_contract(image, bvals, hashes)
    smoothed, brain_mask, fa, roi = prepare_data(image, bvals, bvecs)
    coordinates = np.argwhere(roi)
    signal = smoothed[roi]
    observed_s0 = signal[:, bvals <= B0_THRESHOLD].mean(axis=1)
    if not np.isfinite(observed_s0).all() or np.any(observed_s0 <= 0):
        raise ValueError("the fixed ROI contains invalid mean-b0 signal")
    del smoothed
    maps, residual_summaries, fit_qc = {}, {}, {}
    receipt = {"roi_ijk": coordinates, "fa": fa[roi], "S0_b0": observed_s0,
               "metadata_json": np.asarray(json.dumps(contract, sort_keys=True, allow_nan=False))}
    for cap in CAPS:
        selected = np.asarray(contract["shell_subsets"][str(cap)]["volume_indices"], dtype=int)
        gradients = gradient_table(bvals[selected], bvecs=bvecs[selected], b0_threshold=B0_THRESHOLD)
        cap_signal = signal[:, selected]
        model = DiffusionKurtosisModel(gradients, fit_method="WLS", min_signal=MIN_SIGNAL,
                                      return_S0_hat=True)
        fit = model.fit(cap_signal)
        mk = np.asarray(fit.mk(min_kurtosis=0, max_kurtosis=3, analytical=True, fast=True), float)
        parameters = np.asarray(fit.model_params, dtype=np.float64)
        fitted_s0 = np.asarray(fit.model_S0, dtype=np.float64).reshape(-1)
        if mk.shape != (len(coordinates),) or parameters.shape != (len(coordinates), 27):
            raise ValueError(f"unexpected DKI result shape for cap {cap}")
        if (not np.isfinite(mk).all() or np.any(mk < 0) or np.any(mk > 3)
                or not np.isfinite(parameters).all() or not np.isfinite(fitted_s0).all()
                or np.any(fitted_s0 <= 0)):
            raise ValueError(f"invalid DKI result in the fixed ROI for cap {cap}")
        normalized_rmse = predict_and_residual(parameters, fitted_s0, gradients, cap_signal, observed_s0)
        maps[str(cap)] = mk
        receipt.update({f"map_cap_{cap}": mk, f"params_cap_{cap}": parameters,
                        f"S0_hat_cap_{cap}": fitted_s0, f"nrmse_cap_{cap}": normalized_rmse})
        residual_summaries[str(cap)] = {"mean": float(normalized_rmse.mean()),
                                        "median": float(np.median(normalized_rmse)),
                                        "maximum": float(normalized_rmse.max())}
        indicators = {"mk_eq_0": mk == 0, "mk_eq_3": mk == 3,
                      "nrmse_gt_0_1": normalized_rmse > 0.1,
                      "nrmse_gt_1": normalized_rmse > 1.0}
        fit_qc[str(cap)] = {"n_voxels": len(mk)}
        for name, indicator in indicators.items():
            fit_qc[str(cap)][f"{name}_count"] = int(indicator.sum())
            fit_qc[str(cap)][f"{name}_fraction"] = float(indicator.mean())
        print(f"fit cap={cap} n_voxels={len(mk)} mean_MK={mk.mean():.9f}", flush=True)
    means = {cap: float(values.mean()) for cap, values in maps.items()}
    primary = maps[str(PRIMARY_CAP)]
    write_csv(output_dir / "mk_voxelwise.csv", ["i", "j", "k", "mk"],
              ([*map(int, coordinate), float(value)] for coordinate, value in zip(coordinates, primary)))
    write_csv(output_dir / "mk_sweep.csv", ["i", "j", "k", "max_b", "mk"],
              ([*map(int, coordinate), cap, float(value)]
               for cap in CAPS for coordinate, value in zip(coordinates, maps[str(cap)])))
    result = {
        "status": "ok", "pipeline_id": PIPELINE_ID, "mean_kurtosis_wm": means[str(PRIMARY_CAP)],
        "n_wm_voxels": len(coordinates), "b_max_used": PRIMARY_CAP,
        "shells_used": contract["shell_subsets"][str(PRIMARY_CAP)]["shells"],
        "mean_kurtosis_wm_allshell": means["3000"], "mean_kurtosis_wm_by_bcap": means,
        "mk_shell_cap_spread": max(means.values()) - min(means.values()),
    }
    write_json(output_dir / "dki_results.json", result)
    write_json(output_dir / "run_metadata.json", {
        "status": "ok", **contract, "n_wm_voxels": len(coordinates),
        "n_brain_voxels": int(brain_mask.sum()),
        "residual_definition": "RMSE(fitted_DKI_signal-smoothed_source_signal)/mean_smoothed_b0",
        "normalized_signal_residuals": residual_summaries,
        "fit_qc": fit_qc,
    })
    np.savez_compressed(output_dir / "fit_receipt.npz", **receipt)
    sweep_text = "; ".join(f"b <= {cap}: {means[str(cap)]:.6f}" for cap in CAPS)
    primary_qc = fit_qc[str(PRIMARY_CAP)]
    primary_residual = residual_summaries[str(PRIMARY_CAP)]
    (output_dir / "findings.md").write_text(
        "# CFIN white-matter mean-kurtosis sensitivity baseline\n\n"
        f"The declared b <= {PRIMARY_CAP} WLS fit yielded mean MK "
        f"{means[str(PRIMARY_CAP)]:.6f} over {len(coordinates)} fixed-ROI voxels. "
        f"On this identical ROI the shell-cap sweep was {sweep_text}.\n\n"
        f"For the primary cap {PRIMARY_CAP}, "
        f"{primary_qc['mk_eq_0_count']}/{len(coordinates)} voxels "
        f"({primary_qc['mk_eq_0_fraction']:.2%}) had clipped-output MK=0, and "
        f"{primary_qc['mk_eq_3_count']}/{len(coordinates)} "
        f"({primary_qc['mk_eq_3_fraction']:.2%}) had clipped-output MK=3. "
        f"Signal-normalized residual RMSE exceeded 0.1 in "
        f"{primary_qc['nrmse_gt_0_1_count']}/{len(coordinates)} voxels "
        f"({primary_qc['nrmse_gt_0_1_fraction']:.2%}) and exceeded 1 in "
        f"{primary_qc['nrmse_gt_1_count']}/{len(coordinates)} "
        f"({primary_qc['nrmse_gt_1_fraction']:.2%}); "
        f"median={primary_residual['median']:.6g}, "
        f"maximum={primary_residual['maximum']:.6g}. "
        "These are disclosure diagnostics, not exclusions: every fixed-ROI voxel "
        "remains in every map and aggregate. The FA-selected ROI and clipped MK "
        "do not guarantee stable or biologically interpretable fits. Low or zero "
        "source signal and noise can produce unstable fits and large relative "
        "residuals; clipped finite MK is not a sufficient quality check.\n\n"
        "This is a model-sensitivity analysis of one public CFIN acquisition. "
        "Differences describe dependence on the fitted b-range and this estimator; "
        "they do not identify an independently known unbiased MK or a mandatory "
        "direction of bias. The FA-based ROI is an operational white-matter proxy, "
        "and clipping MK to [0, 3] does not establish biophysical validity. The case "
        "does not reproduce Jensen's original cohort finding.\n")
    print(json.dumps(result, allow_nan=False))
    return result


def main():
    output_dir = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
    data_dir = Path(os.environ.get("CFIN_DATA_DIR", "/app/data/cfin"))
    try:
        run(output_dir, data_dir)
    except Exception as error:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "reason": str(error),
                   "dataset_id": DATASET_ID, "pipeline_id": PIPELINE_ID}
        write_json(output_dir / "run_metadata.json", failure)
        write_json(output_dir / "dki_results.json", failure)
        (output_dir / "findings.md").write_text(f"# Failed precondition\n\n{error}\n")
        print(f"failed_precondition: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
