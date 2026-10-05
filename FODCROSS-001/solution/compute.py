"""Offline Sherbrooke fODF method-sensitivity baseline; imports have no side effects."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

PIPELINE_ID = "sherbrooke-fodf-v2"
DATASET_ID = "sherbrooke_3shell"
RECIPES = ["msmt", "csd_b1000", "csd_b3500"]
VERSIONS = {"dipy": "1.12.1", "clarabel": "0.11.1", "scipy": "1.14.1"}
BOX = [[45, 83], [45, 90], [31, 36]]
B0_THRESHOLD = 50
MIN_SIGNAL = 0.0001
SH_ORDER = 8
MASK_SETTINGS = {"median_radius": 3, "numpass": 1, "autocrop": False, "dilate": None}
RESPONSE_SETTINGS = {"roi_radii": 10, "wm_fa_thr": 0.7, "gm_fa_thr": 0.3,
                     "csf_fa_thr": 0.15, "gm_md_thr": 0.001, "csf_md_thr": 0.0032}
SOLVER_SETTINGS = {"tol_gap_abs": 1e-10, "tol_gap_rel": 1e-10,
                   "tol_feas": 1e-10, "max_iter": 300, "max_threads": 1}


def check_versions():
    import importlib
    for name, expected in VERSIONS.items():
        package = importlib.import_module(name)
        if package.__version__ != expected:
            raise ValueError(f"public baseline requires {name}=={expected}")


def load_inputs(data_dir):
    import nibabel as nib
    from dipy.io.gradients import read_bvals_bvecs

    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    files = manifest["files"]
    if len(files) != 3:
        raise ValueError("require image, bval, and bvec source files")
    paths, hashes = {}, {}
    for item in files:
        relative = Path(item["path"])
        path = (data_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(data_dir):
            raise ValueError("source path escapes the data directory")
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
    bvals, bvecs = read_bvals_bvecs(paths["bval"], paths["bvec"])
    bvals, bvecs = np.asarray(bvals, float), np.asarray(bvecs, float)
    if len(image.shape) != 4 or bvals.shape != (image.shape[-1],) or bvecs.shape != (len(bvals), 3):
        raise ValueError("source image and gradient dimensions disagree")
    if not np.isfinite(bvals).all() or not np.isfinite(bvecs).all() or np.any(bvals < 0):
        raise ValueError("invalid gradients")
    if not np.isfinite(image.affine).all() or any(image.shape[i] < stop for i, (_, stop) in enumerate(BOX)):
        raise ValueError("source geometry does not support the fixed voxel box")
    shells = np.round(bvals, -2).astype(int)
    if set(shells) != {0, 1000, 2000, 3500}:
        raise ValueError("source does not have the declared four shells")
    return image, bvals, bvecs, hashes


def array_digest(array, dtype):
    return hashlib.sha256(np.ascontiguousarray(array, dtype=dtype).tobytes()).hexdigest()


def sphere_contract(sphere, name):
    return {"name": name, "n_vertices": len(sphere.vertices),
            "vertices_sha256_le_float64": array_digest(sphere.vertices, "<f8"),
            "edges_sha256_le_int64": array_digest(sphere.edges, "<i8")}


def metadata_contract(image, bvals, source_sha256):
    from dipy.data import default_sphere, small_sphere
    shells = np.round(bvals, -2).astype(int)
    subsets = {}
    for name in RECIPES:
        selected = np.ones(len(shells), bool) if name == "msmt" else np.isin(shells, [0, int(name[5:])])
        subsets[name] = {"volume_indices": np.flatnonzero(selected).tolist(),
                         "bvals": shells[selected].tolist()}
    small = sphere_contract(small_sphere, "small_sphere:hemisphere(symmetric362)")
    default = sphere_contract(default_sphere, "default_sphere:hemisphere(repulsion724)")
    single_shell = {"model": "ConstrainedSphericalDeconvModel", "sh_order_max": SH_ORDER,
                    "lambda_": 1.0, "tau": 0.1, "convergence": 50, "reg_sphere": small,
                    "response": "response_from_mask_ssst_on_selected_shell_shared_low_b_WM_mask"}
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID, "source_sha256": source_sha256,
        "shape": list(image.shape), "affine": image.affine.tolist(),
        "header_voxel_sizes": [float(x) for x in image.header.get_zooms()[:3]],
        "header_spatial_units": image.header.get_xyzt_units()[0],
        "gradient_contract": {"b0_threshold": B0_THRESHOLD, "rounding": "numpy_round_decimals_minus_2",
                              "original_bvals": bvals.tolist(), "rounded_bvals": shells.tolist(),
                              "subsets": subsets},
        "roi": {"box": BOX, "brain_mask": {"input": "mean_b0", **MASK_SETTINGS},
                "dti_fit_method": "WLS", "dti_shells": [0, 1000], "min_signal": MIN_SIGNAL,
                "fa_lower_exclusive": 0.3, "fa_upper_exclusive": 0.9,
                "finite_fa_required": True, "smoothing": None, "reorientation": None},
        "response_selection": {"low_b_shells": [0, 1000], "center_rule": "floor(shape_xyz/2)",
                               "shared_low_b_WM_mask": True, "masks_are_heuristic": True,
                               **RESPONSE_SETTINGS},
        "estimators": {
            "msmt": {"model": "MultiShellDeconvModel", "sh_order_max": SH_ORDER, "iso": 2,
                     "tol": 20, "response": "response_from_mask_msmt_on_all_shells",
                     "reg_sphere": default,
                     "solver": {"name": "CLARABEL", "interface": "direct_quadratic_program",
                                "warm_start": False, "objective_normalization": "none",
                                **SOLVER_SETTINGS}},
            "csd_b1000": {**single_shell, "shell": 1000},
            "csd_b3500": {**single_shell, "shell": 3500},
        },
        "peak_parameters": {"sphere": default, "sh_basis": "descoteaux07_legacy",
                            "relative_peak_threshold": 0.5, "min_separation_angle": 25,
                            "npeaks": 3, "gfa_thr": 0, "normalize_peaks": False,
                            "is_symmetric": True},
        "software": VERSIONS,
    }


def prepare_data(image, bvals, bvecs):
    """Derive fixed target ROI and response tissue masks from the raw low-b data."""
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import TensorModel
    from dipy.reconst.mcsd import mask_for_response_msmt
    from dipy.segment.mask import median_otsu

    data = image.get_fdata(dtype=np.float64, caching="unchanged")
    if not np.isfinite(data).all():
        raise ValueError("source signal is nonfinite")
    shells = np.round(bvals, -2).astype(int)
    b0 = data[..., shells == 0].mean(axis=-1)
    _, brain = median_otsu(b0, **MASK_SETTINGS)
    box = np.zeros(brain.shape, bool)
    box[tuple(slice(start, stop) for start, stop in BOX)] = True
    eligible = box & brain
    low_b = np.isin(shells, [0, 1000])
    gradients = gradient_table(shells[low_b].astype(float), bvecs=bvecs[low_b], b0_threshold=B0_THRESHOLD)
    fa = np.zeros(brain.shape, float)
    fa[eligible] = TensorModel(gradients, fit_method="WLS", min_signal=MIN_SIGNAL).fit(data[eligible][:, low_b]).fa
    roi = eligible & np.isfinite(fa) & (fa > 0.3) & (fa < 0.9)
    if not roi.any():
        raise ValueError("fixed target ROI is empty")
    masks = mask_for_response_msmt(gradients, data[..., low_b],
                                   roi_center=np.asarray(data.shape[:3]) // 2, **RESPONSE_SETTINGS)
    if any(not np.any(mask) for mask in masks):
        raise ValueError("one or more low-b response tissue masks are empty")
    return data, shells, brain, fa, roi, masks


class ExplicitQPFitter:
    """DIPY's unchanged constrained least-squares objective, explicitly solved."""

    def __init__(self, design, regularization):
        from scipy import sparse
        self.design = np.asarray(design, float)
        self.regularization = np.asarray(regularization, float)
        gram = self.design.T @ self.design
        if not np.isfinite(gram).all() or np.max(np.diag(gram)) <= 0:
            raise ValueError("MSMT quadratic objective has no positive finite scale")
        self.quadratic = sparse.csc_matrix(np.triu(gram))
        # Clarabel uses A*c+s=b, s>=0: A=-reg and b=0 implements reg*c>=0.
        self.constraints = sparse.csc_matrix(-self.regularization)
        self.diagnostics = []

    def __call__(self, signal):
        import clarabel
        settings = clarabel.DefaultSettings()
        settings.verbose = False
        for key, value in SOLVER_SETTINGS.items():
            setattr(settings, key, value)
        result = clarabel.DefaultSolver(self.quadratic, -(self.design.T @ signal),
            self.constraints, np.zeros(len(self.regularization)),
            [clarabel.NonnegativeConeT(len(self.regularization))], settings).solve()
        if str(result.status) != "Solved":
            raise ValueError(f"MSMT solver did not converge: {result.status}; iterations={result.iterations}")
        coefficients = np.asarray(result.x, float)
        if not np.isfinite(coefficients).all():
            raise ValueError("nonfinite MSMT coefficients")
        prediction = self.design @ coefficients
        self.diagnostics.append({"iterations": int(result.iterations),
                                 "objective": float(0.5 * prediction @ prediction - prediction @ signal),
                                 "primal_residual": float(result.r_prim),
                                 "dual_residual": float(result.r_dual),
                                 "dual_objective": float(result.obj_val_dual),
                                 "constraint_minimum": float(np.min(self.regularization @ coefficients))})
        return coefficients


def make_models(data, shells, bvecs, response_masks):
    """Build all public response/design recipes, without fitting target voxels."""
    from dipy.core.gradients import gradient_table
    from dipy.data import default_sphere, small_sphere
    from dipy.reconst.csdeconv import ConstrainedSphericalDeconvModel, response_from_mask_ssst
    from dipy.reconst.mcsd import MultiShellDeconvModel, multi_shell_fiber_response, response_from_mask_msmt

    gradients = gradient_table(shells.astype(float), bvecs=bvecs, b0_threshold=B0_THRESHOLD)
    wm, gm, csf = response_from_mask_msmt(gradients, data, *response_masks, tol=20)
    for response in (wm, gm, csf):
        if not np.isfinite(response).all():
            raise ValueError("nonfinite source-derived response")
    response = multi_shell_fiber_response(SH_ORDER, np.asarray([0., 1000., 2000., 3500.]),
                                          wm, gm, csf, sphere=default_sphere, tol=20)
    msmt = MultiShellDeconvModel(gradients, response, reg_sphere=default_sphere,
                               sh_order_max=SH_ORDER, iso=2, tol=20)
    msmt_reg = msmt.fitter._reg.copy()
    msmt.fitter = ExplicitQPFitter(msmt._X, msmt_reg)
    models = {"msmt": (msmt, np.arange(len(shells)), msmt_reg)}
    responses = {"response_wm": wm, "response_gm": gm, "response_csf": csf,
                 "response_msmt": response.response, "response_msmt_s0": np.asarray(response.S0)}
    for cap in (1000, 3500):
        name = f"csd_b{cap}"
        indices = np.flatnonzero(np.isin(shells, [0, cap]))
        subset = gradient_table(shells[indices].astype(float), bvecs=bvecs[indices], b0_threshold=B0_THRESHOLD)
        response_ss, ratio = response_from_mask_ssst(subset, data[..., indices], response_masks[0])
        if not np.isfinite(response_ss[0]).all() or not np.isfinite(response_ss[1]) or response_ss[1] <= 0:
            raise ValueError(f"invalid single-shell response: {name}")
        model = ConstrainedSphericalDeconvModel(subset, response_ss, reg_sphere=small_sphere,
                                                sh_order_max=SH_ORDER, lambda_=1.0, tau=0.1, convergence=50)
        models[name] = (model, indices, model.B_reg.copy())
        responses.update({f"response_{name}_evals": np.asarray(response_ss[0]),
                          f"response_{name}_s0": np.asarray(response_ss[1]),
                          f"response_{name}_ratio": np.asarray(ratio)})
    return models, responses


def extract_peaks(odf, sphere):
    """Exactly the non-normalized/gfa-threshold-zero peak step used by DIPY."""
    from dipy.reconst.dirspeed import peak_directions
    if not np.isfinite(odf).all():
        raise ValueError("nonfinite fitted fODF")
    _, values, indices = peak_directions(np.ascontiguousarray(odf, dtype=float), sphere,
                                         relative_peak_threshold=0.5, min_separation_angle=25,
                                         is_symmetric=True)
    peak_values, peak_indices = np.zeros(3, float), np.full(3, -1, dtype=int)
    n = min(3, len(values))
    peak_values[:n], peak_indices[:n] = values[:n], indices[:n]
    return peak_values, peak_indices


def normalized_residual(name, model, coefficients, selected_signal, mean_b0):
    # The fit consumes raw signal. Its design directly predicts those raw DWI
    # measurements; applying model.predict's default S0=1 would rescale them.
    predicted = coefficients @ model._X.T
    measured = selected_signal if name == "msmt" else selected_signal[:, ~model.gtab.b0s_mask]
    if name == "msmt":
        predicted, measured = predicted[:, ~model.gtab.b0s_mask], measured[:, ~model.gtab.b0s_mask]
    residual = np.sqrt(np.mean(np.square(predicted - measured), axis=1)) / mean_b0
    if not np.isfinite(residual).all():
        raise ValueError(f"nonfinite source-signal residual: {name}")
    return residual


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def run(output_dir, data_dir):
    check_versions()
    from dipy.data import default_sphere, small_sphere

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image, bvals, bvecs, hashes = load_inputs(data_dir)
    contract = metadata_contract(image, bvals, hashes)
    data, shells, brain, fa, roi, masks = prepare_data(image, bvals, bvecs)
    coordinates = np.argwhere(roi)
    signal = data[roi]
    mean_b0 = signal[:, shells == 0].mean(axis=1)
    if not np.isfinite(mean_b0).all() or np.any(mean_b0 <= 0):
        raise ValueError("fixed ROI contains nonpositive mean-b0 signal")
    models, responses = make_models(data, shells, bvecs, masks)
    del data
    receipt = {"roi_ijk": coordinates, "fa": fa[roi], "mean_b0": mean_b0,
               "sphere_vertices": default_sphere.vertices, "sphere_edges": default_sphere.edges,
               "small_sphere_vertices": small_sphere.vertices, "small_sphere_edges": small_sphere.edges,
               "metadata_json": np.asarray(json.dumps(contract, sort_keys=True, allow_nan=False)),
               **responses}
    for tissue, mask in zip(("wm", "gm", "csf"), masks):
        receipt[f"response_mask_{tissue}_ijk"] = np.argwhere(mask)
    maps, fractions, qc = {}, {}, {}
    for name in RECIPES:
        model, indices, regularization = models[name]
        selected_signal = signal[:, indices]
        coefficients, odfs, peak_values, peak_indices = [], [], [], []
        for position, voxel_signal in enumerate(selected_signal):
            try:
                fit = model.fit(voxel_signal)
            except Exception as error:
                raise ValueError(f"{name}, ROI row {position}, voxel {coordinates[position].tolist()}: "
                                 f"{error}") from error
            coeff = np.asarray(fit.all_shm_coeff if name == "msmt" else fit.shm_coeff, float)
            odf = np.asarray(fit.odf(default_sphere), float)
            if not np.isfinite(coeff).all():
                raise ValueError(f"nonfinite fitted coefficients: {name}, voxel {position}")
            values, locations = extract_peaks(odf, default_sphere)
            coefficients.append(coeff)
            odfs.append(odf)
            peak_values.append(values)
            peak_indices.append(locations)
            if (position + 1) % 500 == 0:
                print(f"{name}: fitted {position + 1}/{len(coordinates)} voxels", flush=True)
        coefficients, odfs = np.asarray(coefficients), np.asarray(odfs)
        peak_values, peak_indices = np.asarray(peak_values), np.asarray(peak_indices)
        counts = (peak_values > 0).sum(axis=1)
        residual = normalized_residual(name, model, coefficients, selected_signal, mean_b0)
        maps[name], fractions[name] = counts, float(np.mean(counts >= 2))
        receipt.update({f"coeff_{name}": coefficients, f"odf_{name}": odfs,
                        f"peak_values_{name}": peak_values, f"peak_indices_{name}": peak_indices,
                        f"map_{name}": counts, f"nrmse_{name}": residual,
                        f"design_{name}": model._X, f"reg_{name}": regularization})
        qc[name] = {"n_zero_peak_voxels": int(np.sum(counts == 0)),
                    "n_capped_three_peak_voxels": int(np.sum(counts == 3)),
                    "negative_odf_sample_fraction": float(np.mean(odfs < 0)),
                    "dwi_normalized_rmse_median": float(np.median(residual)),
                    "dwi_normalized_rmse_maximum": float(np.max(residual)),
                    "dwi_normalized_rmse_gt_0_1_count": int(np.sum(residual > 0.1))}
        if name == "msmt":
            for field in ("iterations", "objective", "constraint_minimum",
                          "primal_residual", "dual_residual", "dual_objective"):
                receipt[f"solver_{field}_msmt"] = np.asarray([row[field] for row in model.fitter.diagnostics])
            qc[name]["solver_status"] = "all_optimal"
            qc[name]["solver_iterations_maximum"] = int(receipt["solver_iterations_msmt"].max())
            qc[name]["constraint_minimum"] = float(receipt["solver_constraint_minimum_msmt"].min())
            qc[name]["solver_primal_residual_maximum"] = float(receipt["solver_primal_residual_msmt"].max())
            qc[name]["solver_dual_residual_maximum"] = float(receipt["solver_dual_residual_msmt"].max())
        print(f"{name}: crossing_fraction={fractions[name]:.9f}", flush=True)
    primary = "msmt"
    write_csv(output_dir / "peaks_voxelwise.csv", ["i", "j", "k", "n_peaks"],
              ([*map(int, coordinate), int(count)] for coordinate, count in zip(coordinates, maps[primary])))
    write_csv(output_dir / "peaks_sweep.csv", ["i", "j", "k", "estimator", "n_peaks"],
              ([*map(int, coordinate), name, int(count)] for name in RECIPES
               for coordinate, count in zip(coordinates, maps[name])))
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "primary_estimator": primary,
              "crossing_fraction": fractions[primary], "n_roi_voxels": len(coordinates),
              "n_crossing_voxels": int(np.sum(maps[primary] >= 2)),
              "mean_peaks_per_voxel": float(np.mean(maps[primary])),
              "crossing_fraction_by_estimator": fractions}
    write_json(output_dir / "crossing.json", result)
    write_json(output_dir / "run_metadata.json", {
        "status": "ok", **contract, "primary_estimator": primary, "fitted_estimators": RECIPES,
        "n_roi_voxels": len(coordinates), "n_brain_voxels": int(np.sum(brain)),
        "response_tissue_voxel_counts": {t: int(np.count_nonzero(m)) for t, m in zip(("wm", "gm", "csf"), masks)},
        "response_arrays": {key: value.tolist() for key, value in responses.items()},
        "residual_definition": "RMSE(predicted-observed_DWI_on_recipe_shells)/observed_mean_b0",
        "fit_qc": qc,
    })
    np.savez_compressed(output_dir / "fit_receipt.npz", **receipt)
    measured = "; ".join(f"{name}: {fractions[name]:.6f}" for name in RECIPES)
    qc_summary = "\n".join(
        f"- {name}: median DWI RMSE/b0={qc[name]['dwi_normalized_rmse_median']:.6f}; "
        f"{qc[name]['dwi_normalized_rmse_gt_0_1_count']}/{len(coordinates)} voxels exceed 0.1; "
        f"negative fODF sample fraction={qc[name]['negative_odf_sample_fraction']:.6f}."
        for name in RECIPES)
    (output_dir / "findings.md").write_text(
        "# Sherbrooke crossing-fraction method sensitivity\n\n"
        f"The same {len(coordinates)} operational FA-selected slab voxels yielded "
        f"crossing fractions {measured}. The primary estimator is {primary}.\n\n"
        "These are estimator- and acquisition-shell-dependent measurements from one "
        "public subject, not a reproduction of the original paper's cohort prevalence. "
        "The comparison varies shell information and tissue model; it does not isolate "
        "a causal mechanism or establish which fraction is biologically correct. "
        "The FA ROI and possibly overlapping response-selection masks are heuristics, "
        "not anatomical tissue ground truth. Finite fits, solver convergence, and fODF "
        "peaks do not establish true fibre counts; inspect the retained residual and "
        "fit-QC diagnostics. No voxel was excluded based on its fODF or peak count.\n\n"
        "## Measured numerical QC\n\n" + qc_summary + "\n\n"
        "The 0.1 residual level is a disclosed diagnostic, not a validated quality "
        "cutoff or an exclusion rule. Negative sample counts include small numerical "
        "negatives and do not measure biological error. Single-shell CSD uses soft "
        "regularization; its sampled fODF need not be nonnegative everywhere. "
        f"MSMT maximum iterations={qc['msmt']['solver_iterations_maximum']}; "
        f"minimum constraint value={qc['msmt']['constraint_minimum']:.6g}. "
        "Even optimal status permits finite solver-tolerance residuals.\n")
    print(json.dumps(result, allow_nan=False))
    return result


def main():
    output = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
    data_dir = Path(os.environ.get("SHERBROOKE_DATA_DIR", "/app/data/sherbrooke"))
    try:
        run(output, data_dir)
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "reason": str(error),
                   "dataset_id": DATASET_ID, "pipeline_id": PIPELINE_ID}
        write_json(output / "run_metadata.json", failure)
        write_json(output / "crossing.json", failure)
        (output / "findings.md").write_text(f"# Failed precondition\n\n{error}\n")
        print(f"failed_precondition: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
