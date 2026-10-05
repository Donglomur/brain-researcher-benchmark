"""Source-bound unsmoothed CFIN WLS method control; import performs no I/O.

The three model choices are conditional estimators, not unbiased tissue truth.
Raw linear coefficients and post-eigenvalue-floor summaries remain distinct.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

PIPELINE_ID = "cfin-unsmoothed-wls-md-fa-v2"
CONFIGS = ("dki_all", "dti_lowb", "dti_all")
DIPY_VERSION = "1.12.1"
MIN_SIGNAL, FA_THRESHOLD, B0_THRESHOLD = 1e-4, 0.5, 50
MASK_PARAMETERS = {"vol_idx": [0], "median_radius": 4, "numpass": 2,
                   "autocrop": False, "dilate": 1}
COEFFICIENT_NAMES = ["Dxx", "Dxy", "Dyy", "Dxz", "Dyz", "Dzz"]
KURTOSIS_NAMES = ["Cxxxx", "Cyyyy", "Czzzz", "Cxxxy", "Cxxxz", "Cxyyy", "Cyyyz",
                  "Cxzzz", "Cyzzz", "Cxxyy", "Cxxzz", "Cyyzz", "Cxxyz", "Cxyyz", "Cxyzz"]
VOXEL_FIELDS = ["i", "j", "k", "md", "fa", "S0_hat", "observed_b0", "normalization_scale",
                "nrmse", "log_rmse", "n_signal_floored", "n_eigenvalues_floored"]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def load_inputs(data_dir):
    import nibabel as nib
    from dipy.io.gradients import read_bvals_bvecs
    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    records = manifest["files"]
    if len(records) != 3:
        raise ValueError("require exactly image/bval/bvec sources")
    paths, hashes = {}, {}
    for record in records:
        rel = Path(record["path"]); path = (data_dir / rel).resolve()
        if rel.is_absolute() or not path.is_relative_to(data_dir):
            raise ValueError("source path escapes the data directory")
        role = record["role"]
        if role not in {"image", "bval", "bvec"} or role in paths or record["path"] in hashes:
            raise ValueError("duplicate or unexpected source role")
        if path.stat().st_size != record["size_bytes"]:
            raise ValueError("source size mismatch")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != record["sha256"]:
            raise ValueError("source SHA256 mismatch")
        paths[role], hashes[record["path"]] = path, digest
    image = nib.load(paths["image"])
    bvals, bvecs = read_bvals_bvecs(paths["bval"], paths["bvec"])
    bvals, bvecs = np.asarray(bvals, float), np.asarray(bvecs, float)
    if image.shape != (96, 96, 19, 496) or bvals.shape != (496,) or bvecs.shape != (496, 3):
        raise ValueError("source shape/gradient count mismatch")
    if not np.isfinite(bvals).all() or not np.isfinite(bvecs).all() or np.any(bvals < 0):
        raise ValueError("invalid gradients")
    if image.header.get_xyzt_units()[0] != "mm" or not np.isfinite(image.affine).all():
        raise ValueError("invalid source physical geometry")
    if not np.array_equal(np.flatnonzero(bvals <= B0_THRESHOLD), [0]):
        raise ValueError("this source contract has one b0 at volume zero")
    return image, bvals, bvecs, hashes


def config_design(bvals, bvecs, config):
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import design_matrix as dti_design
    from dipy.reconst.dki import design_matrix as dki_design
    if config not in CONFIGS:
        raise ValueError("unknown public model_config")
    selected = np.flatnonzero(np.round(bvals, -2) <= 1000) if config == "dti_lowb" else np.arange(len(bvals))
    gtab = gradient_table(bvals[selected], bvecs=bvecs[selected],
                          b0_threshold=B0_THRESHOLD, atol=.01)
    design = (dki_design if config == "dki_all" else dti_design)(gtab)
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise ValueError("source model design is rank deficient")
    return selected, np.asarray(design, float)


def metadata_contract(image, bvals, bvecs, hashes, config):
    selected, design = config_design(bvals, bvecs, config)
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": "cfin_multib", "model_config": config,
        "source_sha256": hashes, "shape": list(image.shape), "affine": image.affine.tolist(),
        "voxel_sizes_mm": [float(v) for v in image.header.get_zooms()[:3]], "spatial_units": "mm",
        "preprocessing": {"smoothing": False, "brain_mask": MASK_PARAMETERS,
                          "intensity_rescale": False, "gradient_b0_threshold": B0_THRESHOLD,
                          "gradient_norm_atol": .01},
        "roi": {"model": "DTI-WLS", "shell_rule": "round_b_to_nearest_100_le_1000",
                "fa_strictly_greater_than": FA_THRESHOLD, "finite_fa": True,
                "signal_floor": MIN_SIGNAL, "extra_qc_exclusion": False},
        "fit": {"method": "two_pass_log_signal_WLS", "signal_floor": MIN_SIGNAL,
                "ols": "pinv(A,rcond=1e-15)@log(max(signal,1e-4))",
                "sqrt_weights": "exp(A@beta_OLS)",
                "wls": "pinv(sqrt_weights[:,None]*A,rcond=1e-15)@(sqrt_weights*log_signal)",
                "pinv_rcond": 1e-15, "dipy_baseline_version": DIPY_VERSION,
                "design_column_order": COEFFICIENT_NAMES + (KURTOSIS_NAMES if config == "dki_all" else []) + ["minus_log_S0"],
                "n_coefficients": int(design.shape[1]),
                "eigenvalue_floor": float(1e-6 / (-design.min())),
                "eigenvalue_floor_rule": "elementwise_maximum_each_raw_eigenvalue_with_1e-6_over_minus_design_min",
                "prediction": "exp(A@beta_postfloor); replace_diffusion6_only",
                "quartic_coefficients": "raw_dimensionful_coefficients_unchanged" if config == "dki_all" else "absent"},
        "volume_indices": selected.tolist(), "selected_bvals": bvals[selected].tolist(),
        "n_selected_volumes": len(selected), "md_units": "1e-3 mm^2/s", "fa_units": "dimensionless",
        "residuals": {"log_rmse": "RMSE(log(max(raw_signal,1e-4))-A@beta_raw)",
                      "nrmse": "RMSE(raw_signal-exp(A@beta_postfloor))/normalization_scale",
                      "normalization_scale": "max(mean(raw_b0),1e-4)",
                      "fitted_S0": "exp(-beta_last)", "quality_gate": False},
    }


def prepare_data(image, bvals, bvecs):
    import dipy
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import TensorModel
    from dipy.segment.mask import median_otsu
    if dipy.__version__ != DIPY_VERSION:
        raise ValueError(f"declared baseline uses DIPY {DIPY_VERSION}")
    data = image.get_fdata(dtype=np.float64, caching="unchanged")
    if not np.isfinite(data).all():
        raise ValueError("source contains nonfinite signal")
    masked, brain = median_otsu(data, **MASK_PARAMETERS)
    del masked
    low = np.round(bvals, -2) <= 1000
    gtab = gradient_table(bvals[low], bvecs=bvecs[low], b0_threshold=B0_THRESHOLD, atol=.01)
    fa_brain = TensorModel(gtab, fit_method="WLS", min_signal=MIN_SIGNAL).fit(data[brain][:, low]).fa
    fa = np.zeros(brain.shape)
    fa[brain] = fa_brain
    roi = brain & np.isfinite(fa) & (fa > FA_THRESHOLD)
    if not roi.any():
        raise ValueError("public ROI is empty")
    return data, brain, fa, roi


def fit_raw_wls(design, signal, chunk_size=256):
    """Same two-pass WLS mathematics without allocating dense diagonal weights."""
    design, signal = np.asarray(design, float), np.asarray(signal, float)
    if signal.ndim != 2 or signal.shape[1] != design.shape[0] or not np.isfinite(signal).all():
        raise ValueError("finite voxel-by-measurement signal required")
    inverse = np.linalg.pinv(design, rcond=1e-15)
    coefficients = np.empty((len(signal), design.shape[1]))
    for start in range(0, len(signal), chunk_size):
        y = np.log(np.maximum(signal[start:start+chunk_size], MIN_SIGNAL))
        initial = y @ inverse.T
        weights = np.exp(initial @ design.T)
        if not np.isfinite(weights).all() or np.any(weights <= 0):
            raise ValueError("invalid OLS-predicted WLS weights")
        weighted_design = weights[:, :, None] * design[None, :, :]
        coefficients[start:start+len(y)] = np.einsum(
            "vpg,vg->vp", np.linalg.pinv(weighted_design, rcond=1e-15), weights*y)
    if not np.isfinite(coefficients).all():
        raise ValueError("nonfinite WLS coefficients")
    return coefficients


def tensor_from_coefficients(coefficients):
    raw = np.asarray(coefficients)
    tensor = np.empty(raw.shape[:-1]+(3, 3))
    tensor[..., 0, 0] = raw[..., 0]; tensor[..., 1, 1] = raw[..., 2]; tensor[..., 2, 2] = raw[..., 5]
    tensor[..., 0, 1] = tensor[..., 1, 0] = raw[..., 1]
    tensor[..., 0, 2] = tensor[..., 2, 0] = raw[..., 3]
    tensor[..., 1, 2] = tensor[..., 2, 1] = raw[..., 4]
    return tensor


def derive_fit(design, signal, beta, observed_b0):
    """All published receipts derive from raw coefficients on their exact support."""
    minimum = float(1e-6 / (-design.min()))
    eigenvalues, eigenvectors = np.linalg.eigh(tensor_from_coefficients(beta))
    clipped = np.maximum(eigenvalues, minimum)
    mean = clipped.mean(axis=1)
    fa = np.sqrt(1.5*np.sum((clipped-mean[:, None])**2, axis=1)/np.sum(clipped**2, axis=1))
    post_tensor = np.einsum("vik,vk,vjk->vij", eigenvectors, clipped, eigenvectors)
    post = beta.copy()
    post[:, :6] = post_tensor[:, [0,0,1,0,1,2], [0,1,1,2,2,2]]
    scale = np.maximum(observed_b0, MIN_SIGNAL)
    with np.errstate(over="raise", invalid="raise"):
        predicted = np.exp(post @ design.T)
        s0 = np.exp(-beta[:, -1])
        nrmse = np.sqrt(np.mean((signal-predicted)**2, axis=1))/scale
        log_rmse = np.sqrt(np.mean((np.log(np.maximum(signal, MIN_SIGNAL))-beta @ design.T)**2, axis=1))
    result = {"md": mean*1000, "fa": fa, "S0_hat": s0, "observed_b0": observed_b0,
              "normalization_scale": scale, "nrmse": nrmse, "log_rmse": log_rmse,
              "n_signal_floored": np.sum(signal < MIN_SIGNAL, axis=1),
              "n_eigenvalues_floored": np.sum(eigenvalues < minimum, axis=1)}
    if any(not np.isfinite(values).all() for values in result.values()) or np.any(s0 <= 0):
        raise ValueError("undefined required fit product; no ROI rows may be dropped")
    return result


def summarize(config, values):
    return {"status": "ok", "pipeline_id": PIPELINE_ID, "model_config": config,
            "md_units": "1e-3 mm^2/s", "n_wm_voxels": len(values["md"]),
            **{key+"_mean": float(values[key].mean()) for key in ("md", "fa", "S0_hat", "nrmse", "log_rmse")},
            "n_signal_floored_total": int(values["n_signal_floored"].sum()),
            "n_eigenvalues_floored_total": int(values["n_eigenvalues_floored"].sum()),
            "n_voxels_signal_floored": int(np.count_nonzero(values["n_signal_floored"])),
            "n_voxels_eigenvalues_floored": int(np.count_nonzero(values["n_eigenvalues_floored"]))}


def run(data_dir, output, config):
    image, bvals, bvecs, hashes = load_inputs(data_dir)
    metadata = metadata_contract(image, bvals, bvecs, hashes, config)
    data, brain, fa_low, roi = prepare_data(image, bvals, bvecs)
    coordinates, signal = np.argwhere(roi), data[roi]
    del data
    observed_b0 = signal[:, bvals <= B0_THRESHOLD].mean(axis=1)
    selected, design = config_design(bvals, bvecs, config)
    beta = fit_raw_wls(design, signal[:, selected])
    values = derive_fit(design, signal[:, selected], beta, observed_b0)
    results = summarize(config, values)
    fields = VOXEL_FIELDS + [f"beta_{i}" for i in range(beta.shape[1])]
    with (output / "md_voxelwise.csv").open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(fields)
        for n, coordinate in enumerate(coordinates):
            writer.writerow([*map(int, coordinate),
                             *(int(values[key][n]) if key.startswith("n_") else float(values[key][n]) for key in VOXEL_FIELDS[3:]),
                             *map(float, beta[n])])
    write_json(output / "diffusivity.json", results)
    write_json(output / "run_metadata.json", metadata | {"status": "ok", "n_wm_voxels": len(coordinates),
                                                       "n_brain_voxels": int(brain.sum())})
    np.savez_compressed(output / "analysis_arrays.npz", roi_ijk=coordinates, signal=signal,
                        bvals=bvals, bvecs=bvecs, volume_indices=selected, design=design, beta=beta,
                        roi_fa_low=fa_low[roi], n_brain_voxels=np.array(int(brain.sum())),
                        metadata_json=np.array(json.dumps(metadata, sort_keys=True)), **values)
    (output / "findings.md").write_text(
        "# Conditional white-matter diffusivity estimate\n\n"
        f"Selected {config} on {len(coordinates)} exact unsmoothed low-b-FA-defined ROI voxels. "
        f"Mean MD={results['md_mean']:.8f} (1e-3 mm^2/s), mean FA={results['fa_mean']:.8f}. "
        f"Mean normalized signal RMSE={results['nrmse_mean']:.8g}; "
        f"mean raw-regression log RMSE={results['log_rmse_mean']:.8g}.\n\n"
        f"Signal flooring affected {results['n_voxels_signal_floored']} voxels "
        f"({results['n_signal_floored_total']} samples); eigenvalue flooring affected "
        f"{results['n_voxels_eigenvalues_floored']} voxels "
        f"({results['n_eigenvalues_floored_total']} eigenvalues). All ROI voxels remain. "
        "These are algorithmic diagnostics, not physiological exclusions or proof of fit adequacy. "
        f"Observed b0 is zero in {int(np.count_nonzero(values['observed_b0'] == 0))} ROI voxels; "
        "the declared 1e-4 normalization floor can make their normalized residuals enormous. "
        f"The all-voxel median normalized RMSE is {float(np.median(values['nrmse'])):.8g}; "
        "the mean is not a typical-voxel fit-quality estimate. No such voxels are discarded.\n\n"
        "The ROI is selected by the same low-b DTI FA criterion for all allowed model choices, "
        "which conditions the sample on that estimator. Rotational invariance does not make "
        "MD/FA invariant to model, shell range, noise or preprocessing. WLS uses a log-signal "
        "approximation, not the cited rat study's Rician likelihood. These human CFIN values "
        "are conditional method outputs; no independent Gaussian diffusivity truth is given. "
        "Only the selected configuration is reported here, so no uncomputed cross-model "
        "comparison, unbiasedness, population claim or model difficulty is asserted. "
        "Input acquisition used inversion-recovery CSF suppression. Raw regression residuals "
        "and post-eigenvalue-floor signal residuals refer to distinct, explicitly stated stages.\n")
    print(json.dumps(results), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/app/data/cfin")))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--config", choices=CONFIGS, default="dki_all")
    parser.add_argument("--print-contracts", action="store_true")
    args = parser.parse_args()
    if args.print_contracts:
        image, bvals, bvecs, hashes = load_inputs(args.data)
        print(json.dumps({c: metadata_contract(image, bvals, bvecs, hashes, c) for c in CONFIGS}, indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        run(args.data, args.output, args.config)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        failure = {"status": "failed_precondition", "reason": reason, "pipeline_id": PIPELINE_ID}
        write_json(args.output / "run_metadata.json", failure)
        write_json(args.output / "diffusivity.json", failure)
        (args.output / "md_voxelwise.csv").write_text(",".join(VOXEL_FIELDS)+"\n")
        (args.output / "findings.md").write_text("# Failed precondition\n\n"+reason+"\n")
        raise SystemExit(reason)


if __name__ == "__main__":
    main()
