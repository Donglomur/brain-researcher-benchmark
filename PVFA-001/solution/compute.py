"""Source-bound diffusion-defined adjacent-proxy FA comparison; import-safe.

This method control is not an anatomical ventricular ROI or independently
known tissue anisotropy. Source processing and fitting occur only via run().
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import importlib.metadata
import itertools
import json
import os
from pathlib import Path
import time

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter, generate_binary_structure
from dipy.core.gradients import gradient_table
from dipy.reconst.dti import design_matrix
from dipy.segment.mask import median_otsu
from estimators import (MODELS, COEFFICIENT_NAMES, DIS0, MDREG, FW_MIN_SIGNAL,
                        DTI_MIN_SIGNAL, LM_SETTINGS, STATUSES, dti_wls_beta,
                        tensor_metrics, fit_dti, fit_free_water)

PIPELINE_ID = "sherbrooke-proxy-fa-v2"
MANIFEST_SHA256 = "f59a83a45da820308010d02ea93a29291df1bee117a66f399ddc95978c6be2fa"
VERSIONS = {"numpy": "2.1.3", "scipy": "1.14.1", "dipy": "1.12.1", "nibabel": "5.4.2", "h5py": "3.12.1"}
FWHM_VOXELS = .625
SIGMA_VOXELS = FWHM_VOXELS/np.sqrt(8*np.log(2))
PARAM_FIELDS = ("i", "j", "k", "model", "status", "fit_attempted", "eligible", "common_valid",
                *COEFFICIENT_NAMES, "S0_hat", "f", "fa", "md", "sse", "nrmse",
                "n_eigenvalues_clipped", "optimizer_status", "nfev", "init_f", "init_md",
                "n_signal_floored", "observed_b0", "normalization_scale", "boundary_f_low", "boundary_f_high")
SUMMARY_FIELDS = ("fa", "md", "f", "S0_hat", "nrmse")


def check_versions():
    actual = {key: importlib.metadata.version(key) for key in VERSIONS}
    if actual != VERSIONS: raise ValueError(f"Pinned oracle software differs: {actual}")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""): digest.update(block)
    return digest.hexdigest()


def load_inputs(data_dir):
    """Read verified source geometry/gradients, without reading image voxels."""
    data_dir = Path(data_dir); manifest_path = data_dir/"data_manifest.json"
    if file_hash(manifest_path) != MANIFEST_SHA256: raise ValueError("Frozen source manifest SHA256 mismatch")
    manifest = json.loads(manifest_path.read_text())
    if manifest["dataset_id"] != "sherbrooke_3shell" or manifest["source_version"] != "dipy-1.12.1-corrected-bvec":
        raise ValueError("Unexpected source identity")
    files = manifest["files"]
    if len(files) != 3 or {entry["role"] for entry in files} != {"image", "bval", "bvec"}:
        raise ValueError("Expected exactly three source roles")
    paths, hashes = {}, {}
    for entry in files:
        path = data_dir/entry["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size_bytes"] or file_hash(path) != entry["sha256"]:
            raise ValueError(f"Source verification failed: {entry['path']}")
        paths[entry["role"]] = path; hashes[entry["path"]] = entry["sha256"]
    image = nib.load(paths["image"]); bvals = np.loadtxt(paths["bval"]).reshape(-1); bvecs = np.loadtxt(paths["bvec"])
    if image.shape != (128, 128, 60, 193) or bvals.shape != (193,) or bvecs.shape != (193, 3):
        raise ValueError("Unexpected source dimensions")
    if not np.isfinite(bvals).all() or not np.isfinite(bvecs).all() or set(bvals) != {0., 1000., 2000., 3500.}:
        raise ValueError("Unexpected gradients")
    if np.flatnonzero(bvals <= 50).tolist() != [0]: raise ValueError("Expected the first volume to be the sole b0")
    gradient_table(bvals, bvecs=bvecs, b0_threshold=50)
    return dict(image=image, bvals=bvals, bvecs=bvecs, hashes=hashes, manifest=manifest)


def model_indices(bvals, model):
    bvals = np.asarray(bvals)
    select = ((bvals >= -1) & (bvals <= 50)) | (np.abs(bvals-1000) <= 50)
    if model != "dti_b1000": select |= np.abs(bvals-2000) <= 50
    return np.flatnonzero(select)


def metadata_contract(inputs):
    """Public source/recipe template; never fit results or ROI membership."""
    image, bvals, bvecs = inputs["image"], inputs["bvals"], inputs["bvecs"]
    subsets = {}
    for model in MODELS:
        indices = model_indices(bvals, model)
        design = design_matrix(gradient_table(bvals[indices], bvecs=bvecs[indices], b0_threshold=50))
        subsets[model] = dict(volume_indices=indices.tolist(), bvals=bvals[indices].tolist(), bvecs=bvecs[indices].tolist(),
            design_rank=int(np.linalg.matrix_rank(design)), shells=sorted(set(bvals[indices].tolist())),
            eigen_floor=0. if model == "fwdti" else 1e-6/(-float(design.min())))
    return dict(pipeline_id=PIPELINE_ID, dataset_id="sherbrooke_3shell",
        source_version="dipy-1.12.1-corrected-bvec", source_manifest_sha256=MANIFEST_SHA256,
        source_sha256=inputs["hashes"], shape=list(image.shape), affine=image.affine.tolist(),
        header_voxel_sizes=list(map(float, image.header.get_zooms()[:3])), header_spatial_units=image.header.get_xyzt_units()[0],
        gradient_contract=dict(b0_threshold=50, corrected_bvec_already_applied=True,
            coefficient_order=list(COEFFICIENT_NAMES), subsets=subsets),
        preprocessing=dict(brain_mask=dict(source="unsmoothed_first_b0", median_radius=4, numpass=2, dilate=1, autocrop=False),
            smoothing=dict(fwhm_voxels=FWHM_VOXELS, sigma_voxels=float(SIGMA_VOXELS), mode="reflect", truncate=4.,
                spatial_axes_only=True, dtype="float64", physical_mm_claim=False)),
        roi=dict(name="diffusion_defined_high_MD_low_FA_adjacent_proxy", selector="dti_b1000",
            seed=dict(md_above=.002, fa_below=.2), dilation=dict(iterations=2, connectivity=1, structure="3D_six_neighbour", border_value=0),
            remove_seed=True, inside_brain=True, md_strictly_between=[.0008, .0015], fa_above=.25,
            anatomical_segmentation=False, independent_tissue_truth=False, minimum_count=1, coordinate_order="C"),
        models=dict(allowed=list(MODELS), minimum_selected=2,
            dti=dict(estimator="two_pass_WLS", signal_floor=DTI_MIN_SIGNAL, weights="squared_OLS_predicted_signal",
                     pinv_rcond=1e-15, eigen_floor="1e-6/(-design.min())", fitted_intercept_retained=True),
            fwdti=dict(estimator="DIPY_1.12.1_instrumented_WLS_init_NLS", Diso=DIS0, mdreg=MDREG,
                signal_floor=FW_MIN_SIGNAL, wls_weights="observed_signal_squared", pinv_rcond=1e-15,
                piterations=3, grid_sizes=[9, 19, 19], grid_precision=[.1, .01, .001],
                grid_bounds="start0..1_then_previous_f_plus_minus_previous_precision",
                nonpositive_tissue_adjusted_signal_replacement=FW_MIN_SIGNAL,
                initializer_eigen_floor=0., initializer_S0="mean_observed_b0",
                initializer_fraction_transform="asin(2*f_init-1)+pi/2",
                skip_rule="mean_signal<=1e-6_or_b0<=1e-6_or_initial_MD>=.0027_or_initial_f>=.99",
                cholesky=False, f_transform=True, jac=False, weighting=None, sigma=None,
                optimizer="scipy.optimize.leastsq", full_output=True, Dfun=None, col_deriv=False,
                optimizer_settings=LM_SETTINGS, successful_ier=[1, 2, 3, 4], tensor_bounds=None, negative_log_S0_bounds=None,
                fraction="0.5*(1+sin(ft-pi/2))", postfit_eigen_floor=0., decomposition_fallback=False)),
        reporting=dict(statuses=list(STATUSES), residual="unfloored_smoothed_signal_minus_raw_tensor_prediction",
            fitted_S0="exp(-neg_log_S0)", normalization_scale="max(mean_observed_b0,1e-6)",
            init_md="preliminary_observed_signal_squared_WLS_raw_MD_before_fraction_search",
            DTI_fraction="fixed0_not_a_measured_free_water_fraction", DTI_optimizer_status=None, DTI_nfev=0,
            undefined_final_fields="CSV_blank_for_no_candidate", keep_failed_candidates=True,
            eligible="status_ok_finite_candidate_and_prediction_S0_positive_reported_tensor_nonzero_0<=f<1",
            common_valid="intersection_of_eligible_rows_across_selected_models", primary_mean="main_model_own_eligible_rows", empty_mean=None,
            boundary_f_low_max=1e-6, boundary_f_high_min=1-1e-6, clipping_is_diagnostic=True, rank_is_diagnostic=True,
            jacobian=dict(coordinates="raw_D6_negative_log_S0_f_for_FW_D7_for_DTI",
                parameter_scales={model: [.001]*6+([1., 1.] if model == "fwdti" else [1.]) for model in MODELS},
                parameter_counts={model: 8 if model == "fwdti" else 7 for model in MODELS},
                residual_scale="normalization_scale", relative_singular_value_rank_threshold=1e-12),
            paired_difference_keys="lexicographically_later_model_minus_earlier_model"),
        tolerances=dict(raw_D=dict(atol=1e-8, rtol=1e-5), f_FA=dict(atol=1e-5, rtol=1e-5),
            normalized_S0=dict(atol=1e-5, rtol=1e-5), normalized_prediction_atol=1e-5, normalized_prediction_rtol=0., residual_arithmetic_atol=1e-6,
            within_row_algebra_cross_file_and_summary=dict(atol=1e-6, rtol=1e-6),
            md_arithmetic=dict(atol=1e-8, rtol=1e-6), eigenvectors_and_periodic_ft_compared=False, optimizer_history_exact_match=False),
        software=VERSIONS)


def prepare_source(inputs):
    """One original uint16 load, per-volume smoothing, chunked low-b WLS."""
    image, bvals, bvecs = inputs["image"], inputs["bvals"], inputs["bvecs"]
    raw = np.asarray(image.dataobj)
    if not np.isfinite(raw).all() or np.any(raw < 0): raise ValueError("Nonfinite or negative original DWI")
    _, brain = median_otsu(raw[..., 0], median_radius=4, numpass=2, dilate=1, autocrop=False)
    selected = model_indices(bvals, "dti_b2000")
    smoothed = np.empty(image.shape[:3]+(len(selected),), float)
    for out_index, source_index in enumerate(selected):
        smoothed[..., out_index] = gaussian_filter(np.asarray(raw[..., source_index], float),
            sigma=(SIGMA_VOXELS,)*3, mode="reflect", truncate=4.)
    brain_ijk = np.argwhere(brain); low = np.flatnonzero(bvals[selected] <= 1050)
    design = design_matrix(gradient_table(bvals[selected[low]], bvecs=bvecs[selected[low]], b0_threshold=50))
    brain_beta = np.empty((len(brain_ijk), 7)); brain_signal = smoothed[brain][:, low]
    for start in range(0, len(brain_ijk), 256): brain_beta[start:start+256] = dti_wls_beta(brain_signal[start:start+256], design)
    metrics = tensor_metrics(brain_beta, 1e-6/(-float(design.min())))
    fa = np.zeros(brain.shape); md = np.zeros(brain.shape); fa[brain] = metrics["fa"]; md[brain] = metrics["md"]
    seed = brain & (md > .002) & (fa < .2)
    roi = binary_dilation(seed, structure=generate_binary_structure(3, 1), iterations=2, border_value=0)
    roi &= brain & ~seed & (md > .0008) & (md < .0015) & (fa > .25)
    ijk = np.argwhere(roi)
    if not len(ijk): raise ValueError("Diffusion-defined proxy ROI is empty")
    return dict(roi_ijk=ijk, signal=smoothed[roi], raw_signal=np.asarray(raw[roi], float),
        volume_indices=selected, bvals=bvals[selected], bvecs=bvecs[selected], original_bvals=bvals, original_bvecs=bvecs,
        brain_ijk=brain_ijk, brain_low_beta=brain_beta, seed_ijk=np.argwhere(seed), roi_fa_low=fa[roi], roi_md_low=md[roi],
        n_brain_voxels=int(brain.sum()), n_seed_voxels=int(seed.sum()))


def assemble_model(records, indices, design):
    boolean_keys = ("fit_attempted", "eligible", "boundary_f_low", "boundary_f_high")
    integer_keys = ("nfev", "n_signal_floored")
    nullable_int_keys = ("optimizer_status", "n_eigenvalues_clipped", "jacobian_rank")
    float_keys = ("f", "S0_hat", "fa", "md", "sse", "nrmse", "init_f", "init_md", "observed_b0",
                  "normalization_scale", "initial_ft", "eigen_floor", "jacobian_condition")
    array_keys = ("beta", "prediction", "residual", "reported_prediction", "initial_beta", "initial_raw_beta",
                  "initial_prediction", "optimizer_q", "raw_eigenvalues", "reported_tensor", "scaled_jacobian_singular_values")
    result = {key: np.asarray([record[key] for record in records], bool) for key in boolean_keys}
    result.update({key: np.asarray([record[key] for record in records], int) for key in integer_keys})
    result.update({key: np.asarray([np.nan if record[key] is None else record[key] for record in records], float) for key in nullable_int_keys})
    result.update({key: np.asarray([record[key] for record in records], float) for key in float_keys+array_keys})
    result["status"] = np.asarray([record["status"] for record in records], str)
    result["optimizer_message"] = np.asarray([record["optimizer_message"] for record in records], str)
    result["warnings_json"] = np.asarray(json.dumps([record["warnings"] for record in records]))
    result["signal_indices"] = indices; result["design"] = design
    return result


def fit_models(prepared, models, pilot_max_voxels=None):
    full_ijk = prepared["roi_ijk"]; chosen = np.arange(len(full_ijk))
    if pilot_max_voxels is not None:
        if not 1 <= pilot_max_voxels <= 64: raise ValueError("Pilot size must be 1..64 ROI rows")
        chosen = np.unique(np.linspace(0, len(full_ijk)-1, min(pilot_max_voxels, len(full_ijk)), dtype=int))
    arrays = dict(prepared); arrays.update(full_roi_ijk=full_ijk, selected_roi_indices=chosen)
    for key in ("roi_ijk", "signal", "raw_signal", "roi_fa_low", "roi_md_low"): arrays[key] = prepared[key][chosen]
    arrays["models"] = {}
    for model in models:
        indices = model_indices(arrays["bvals"], model); signal = arrays["signal"][:, indices]
        b0_mask = arrays["bvals"][indices] <= 50
        design = design_matrix(gradient_table(arrays["bvals"][indices], bvecs=arrays["bvecs"][indices], b0_threshold=50))
        if np.linalg.matrix_rank(design) != 7: raise ValueError(f"Rank-deficient source design: {model}")
        if model == "fwdti":
            records = []
            for index, row in enumerate(signal):
                records.append(fit_free_water(row, design, b0_mask))
                if (index+1) % 100 == 0: print(f"fwdti {index+1}/{len(signal)} rows", flush=True)
        else: records = fit_dti(signal, design, b0_mask)
        arrays["models"][model] = assemble_model(records, indices, design)
        counts = dict(Counter(record["status"] for record in records)); warning_count = sum(len(record["warnings"]) for record in records)
        print(f"{model}: statuses={counts}; captured_warnings={warning_count}", flush=True)
        for index, record in enumerate(records):
            if record["warnings"]:
                print(f"{model} row{index}: first warning={record['warnings'][0]}", flush=True); break
    return arrays


def means(model, mask):
    return {key+"_mean": float(np.mean(model[key][mask])) if mask.any() else None for key in SUMMARY_FIELDS}


def summarize_results(arrays, main_model, status="ok"):
    models = arrays["models"]; common = np.logical_and.reduce([model["eligible"] for model in models.values()])
    by_model = {}
    for name, model in models.items():
        valid = model["eligible"]; clipped = model["n_eigenvalues_clipped"]
        by_model[name] = dict(means(model, valid), n_valid=int(valid.sum()), status_counts=dict(Counter(model["status"].tolist())),
            n_eigenvalues_clipped_total=int(np.nansum(clipped)), n_voxels_eigenvalues_clipped=int(np.sum(clipped > 0)))
    differences = {}
    for left, right in itertools.combinations(sorted(models), 2):
        differences[f"{right}_minus_{left}"] = float(np.mean(models[right]["fa"][common]-models[left]["fa"][common])) if common.any() else None
    result = dict(status=status, pipeline_id=PIPELINE_ID, main_model=main_model, n_roi_voxels=len(arrays["roi_ijk"]),
        n_common_valid=int(common.sum()), fa_proxy_roi=by_model[main_model]["fa_mean"], by_model=by_model,
        common_valid=dict(n_voxels=int(common.sum()), by_model={name: means(model, common) for name, model in models.items()},
                          paired_fa_differences=differences))
    return result, common


def csv_value(value):
    if value is None: return ""
    if isinstance(value, (bool, np.bool_)): return int(value)
    if isinstance(value, (float, np.floating)) and not np.isfinite(value): return ""
    return value.item() if isinstance(value, np.generic) else value


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow({key: csv_value(row[key]) for key in fields})


def write_json(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def parameter_rows(arrays, common):
    for name, model in arrays["models"].items():
        for index, ijk in enumerate(arrays["roi_ijk"]):
            row = dict(zip(("i", "j", "k"), ijk)); row.update(model=name, common_valid=common[index])
            row.update(zip(COEFFICIENT_NAMES, model["beta"][index]))
            for key in PARAM_FIELDS:
                if key not in row: row[key] = model[key][index]
            yield row


def write_outputs(output, arrays, contract, main_model, status="ok"):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    result, common = summarize_results(arrays, main_model, status)
    metadata = dict(contract, status=status, main_model=main_model, fitted_models=list(arrays["models"]),
        n_roi_voxels=len(arrays["roi_ijk"]), n_brain_voxels=arrays["n_brain_voxels"], n_seed_voxels=arrays["n_seed_voxels"],
        n_common_valid=int(common.sum()), status_counts_by_model={name: row["status_counts"] for name, row in result["by_model"].items()})
    if status == "resource_pilot": metadata.update(n_source_roi_voxels=len(arrays["full_roi_ijk"]), selected_roi_indices=arrays["selected_roi_indices"].tolist())
    write_json(output/"results.json", result); write_json(output/"run_metadata.json", metadata)
    write_csv(output/"fit_parameters.csv", PARAM_FIELDS, parameter_rows(arrays, common))
    write_csv(output/"fa_voxelwise.csv", ("i", "j", "k", "fa"),
              (dict(zip(("i", "j", "k", "fa"), (*ijk, fa))) for ijk, fa in zip(arrays["roi_ijk"], arrays["models"][main_model]["fa"])))
    write_csv(output/"fa_sweep.csv", ("i", "j", "k", "model", "fa"),
              (dict(zip(("i", "j", "k", "model", "fa"), (*ijk, name, fa)))
               for name, model in arrays["models"].items() for ijk, fa in zip(arrays["roi_ijk"], model["fa"])))
    private = {key: value for key, value in arrays.items() if key != "models"}
    for name, model in arrays["models"].items(): private.update({f"{key}_{name}": value for key, value in model.items()})
    private.update(common_valid=common, metadata_json=np.asarray(json.dumps(metadata, allow_nan=False)),
                   results_json=np.asarray(json.dumps(result, allow_nan=False)), pipeline_id=np.asarray(PIPELINE_ID))
    np.savez_compressed(output/"analysis_arrays.npz", **private)
    lines = ["# Diffusion-defined adjacent-proxy model sensitivity",
        f"Source-defined proxy ROI: {len(arrays['full_roi_ijk'])} voxels; evaluated {len(arrays['roi_ijk'])}.",
        f"Main {main_model}: eligible-row mean FA={result['fa_proxy_roi']}; common eligible support={int(common.sum())}."]
    for name, model in arrays["models"].items():
        summary = result["by_model"][name]
        lines.append(f"{name}: eligible={summary['n_valid']}, mean FA={summary['fa_mean']}, normalized RMSE={summary['nrmse_mean']}; statuses={summary['status_counts']}; eigenvalues clipped={summary['n_eigenvalues_clipped_total']}; fraction-boundary rows low/high={int(model['boundary_f_low'].sum())}/{int(model['boundary_f_high'].sum())}.")
    lines += [f"Signed common-support FA differences: {result['common_valid']['paired_fa_differences']}.",
        "The source header does not declare millimeters; smoothing is 0.625 voxel FWHM. The region is a diffusion-defined high-MD/low-FA-adjacent proxy, not independently segmented ventricles or confirmed periventricular white matter. Selection uses low-b tensor FA/MD from the same acquisition.",
        "Free-water-model fractions and eigenvalue-clipped FA are computational estimates, not independently known tissue anisotropy or true CSF volume. Single-tensor f=0 is a model setting, not estimated absence of water. Raw-candidate predictions retain fitted S0; clipping can change predictions. Rank/conditioning and clipping are diagnostics, not additional exclusion criteria.",
        "These single-acquisition calculations adapt a published method; they do not reproduce the original paper cohort, establish an estimator direction, or validate biological identifiability."]
    if status == "resource_pilot": lines.append("This is a bounded resource pilot, not a complete participant output or reference bank.")
    (output/"findings.md").write_text("\n\n".join(lines)+"\n")
    return result, metadata


def run(data, output, models=MODELS, main_model="fwdti", pilot_max_voxels=None):
    models = tuple(models)
    if len(set(models)) != len(models) or not 2 <= len(models) <= 3 or not set(models) <= set(MODELS) or main_model not in models:
        raise ValueError("Choose two or three distinct public models and a selected main model")
    check_versions(); inputs = load_inputs(data); contract = metadata_contract(inputs)
    prepared = prepare_source(inputs); arrays = fit_models(prepared, models, pilot_max_voxels)
    return write_outputs(output, arrays, contract, main_model, "ok" if pilot_max_voxels is None else "resource_pilot")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--models", choices=MODELS, nargs="+", default=list(MODELS))
    parser.add_argument("--main-model", choices=MODELS, default="fwdti")
    parser.add_argument("--pilot-max-voxels", type=int)
    parser.add_argument("--print-contracts", action="store_true")
    args = parser.parse_args()
    if args.print_contracts:
        print(json.dumps(metadata_contract(load_inputs(args.data)), indent=2, allow_nan=False)); return
    started = time.monotonic()
    try: run(args.data, args.output, args.models, args.main_model, args.pilot_max_voxels)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = dict(status="failed_precondition", pipeline_id=PIPELINE_ID, reason=str(exc))
        write_json(args.output/"results.json", failure); write_json(args.output/"run_metadata.json", failure)
        (args.output/"findings.md").write_text("# Failed precondition\n\n"+str(exc)+"\n"); raise
    print(f"Finished in {time.monotonic()-started:.3f} seconds", flush=True)


if __name__ == "__main__": main()
