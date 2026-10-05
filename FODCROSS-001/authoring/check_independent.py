"""Check Sherbrooke receipts with separate SH/peak code and a bounded second QP solver.

SciPy harmonics and NumPy graph operations independently implement the legacy
Descoteaux basis and peak extraction. QR plus dual nonnegative least squares
independently solves the MSMT program for 64 evenly spaced voxels plus the
retained OSQP failure sentinel at row 1047 (at most 65). Source data, sphere
meshes, DTI/mask implementations, response estimates and design matrices are
shared; agreement is not anatomical or biological ground truth.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import nnls
from scipy.special import sph_harm


RECIPES = ("msmt", "csd_b1000", "csd_b3500")
MAX_QP_VOXELS = 64
BOX = ((45, 83), (45, 90), (31, 36))
COS_SEPARATION = float(np.cos(np.deg2rad(25.0)))
# Declared before any source-data fit/check, not adjusted to force agreement.
TOLERANCES = {
    "sh_odf": {"atol": 1e-10, "rtol": 1e-10},
    "receipt_residual": {"atol": 1e-12, "rtol": 1e-9},
    "qp_normalized_loss": {"atol": 1e-7, "rtol": 1e-4},
    "qp_signal_over_b0": {"atol": 2e-4, "rtol": 1e-4},
    "qp_odf_over_oracle_peak": {"atol": 5e-4, "rtol": 1e-4},
    "qp_constraint_violation_over_coefficient_scale": 2e-5,
}
DUAL_NNLS_SETTINGS = {"maxiter": 10000}
FAILURE_SENTINEL_ROW = 1047


def compare(actual, expected, *, atol, rtol):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape:
        raise ValueError(f"Comparison shape mismatch: {actual.shape} versus {expected.shape}")
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("Nonfinite numerical comparison")
    differences = np.abs(actual - expected)
    mismatches = differences > atol + rtol * np.abs(expected)
    return {"passed": not bool(mismatches.any()), "n_mismatched_values": int(mismatches.sum()),
            "max_abs_difference": float(differences.max(initial=0)), "atol": atol, "rtol": rtol}


def legacy_descoteaux_basis(vertices):
    """Even l=0..8, m=-l..l; legacy convention uses |m| in complex harmonics."""
    vertices = np.asarray(vertices, float)
    radius = np.linalg.norm(vertices, axis=1)
    if np.any(radius <= 0):
        raise ValueError("Invalid zero sphere vertex")
    polar = np.arccos(np.clip(vertices[:, 2] / radius, -1, 1))
    azimuth = np.arctan2(vertices[:, 1], vertices[:, 0])
    columns = []
    for degree in range(0, 9, 2):
        for order in range(-degree, degree + 1):
            harmonic = sph_harm(abs(order), degree, azimuth, polar)
            real = harmonic.imag if order > 0 else harmonic.real
            columns.append(real * (1 if order == 0 else np.sqrt(2)))
    return np.column_stack(columns)


def local_maxima(odf, edges):
    """>= every neighbor and > at least one; constant functions have no maxima."""
    left, right = edges.T
    smaller, larger = np.zeros(len(odf), bool), np.zeros(len(odf), bool)
    np.logical_or.at(smaller, left, odf[left] < odf[right])
    np.logical_or.at(smaller, right, odf[right] < odf[left])
    np.logical_or.at(larger, left, odf[left] > odf[right])
    np.logical_or.at(larger, right, odf[right] > odf[left])
    indices = np.flatnonzero(larger & ~smaller)
    return indices[np.argsort(-odf[indices], kind="stable")]


def numpy_peaks(odf, vertices, edges):
    """Shifted relative threshold, antipodal 25-degree suppression, and 3-peak cap."""
    if not np.isfinite(odf).all():
        raise ValueError("Nonfinite ODF")
    candidates = local_maxima(odf, edges)
    if len(candidates) > 1:
        baseline = max(0.0, float(odf.min()))
        shifted = odf[candidates] - baseline
        candidates = candidates[shifted >= 0.5 * shifted[0]]
    selected = []
    for candidate in candidates:
        if all(abs(float(vertices[candidate] @ vertices[previous])) <= COS_SEPARATION
               for previous in selected):
            selected.append(int(candidate))
            if len(selected) == 3:
                break
    values, indices = np.zeros(3), np.full(3, -1, dtype=int)
    indices[:len(selected)] = selected
    values[:len(selected)] = odf[selected]
    return values, indices


def peak_boundary_diagnostics(odf, vertices, edges):
    """Expose decision margins without automatically excusing a count mismatch."""
    candidates = local_maxima(odf, edges)
    baseline = max(0.0, float(odf.min()))
    scale = max(float(np.max(np.abs(odf))), np.finfo(float).tiny)
    threshold = baseline + 0.5 * (float(odf[candidates[0]]) - baseline) if len(candidates) else None
    selected_values, selected_indices = numpy_peaks(odf, vertices, edges)
    adjacent_margins = []
    for idx in selected_indices[selected_indices >= 0]:
        adjacent = np.r_[edges[edges[:, 0] == idx, 1], edges[edges[:, 1] == idx, 0]]
        adjacent_margins.append(float(np.min(odf[idx] - odf[adjacent])) / scale)
    return {"local_maximum_indices": candidates.tolist(),
            "local_maximum_values": odf[candidates].tolist(),
            "threshold": threshold,
            "threshold_margins_over_peak": ((odf[candidates] - threshold) / scale).tolist()
            if threshold is not None else [],
            "selected_indices": selected_indices.tolist(), "selected_values": selected_values.tolist(),
            "selected_neighbor_margins_over_peak": adjacent_margins}


def array_digest(array, dtype):
    return hashlib.sha256(np.ascontiguousarray(array, dtype=dtype).tobytes()).hexdigest()


def load_source(data_dir):
    data_dir = data_dir.resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    if manifest["source_version"] != "dipy-1.12.1-corrected-bvec" or len(manifest["files"]) != 3:
        raise ValueError("Expected the corrected pinned three-file Sherbrooke bundle")
    paths, hashes = {}, {}
    for item in manifest["files"]:
        path = (data_dir / item["path"]).resolve()
        if not path.is_relative_to(data_dir) or item["role"] in paths:
            raise ValueError("Invalid source path or duplicate role")
        if path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"Source size mismatch: {path.name}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Source SHA256 mismatch: {path.name}")
        paths[item["role"]], hashes[item["path"]] = path, digest
    if set(paths) != {"image", "bval", "bvec"}:
        raise ValueError("Invalid source roles")
    image = nib.load(paths["image"])
    bvals, bvecs = np.loadtxt(paths["bval"]), np.loadtxt(paths["bvec"])
    if image.shape != (128, 128, 60, 193) or bvals.shape != (193,) or bvecs.shape != (193, 3):
        raise ValueError("Source dimensions or corrected b-vector orientation changed")
    return image, bvals, bvecs, hashes


def shared_roi_check(image, bvals, bvecs, receipt):
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dti import TensorModel
    from dipy.segment.mask import median_otsu

    # Native uint16 reads save memory; mean b0 and fitted matrices are float64.
    data = np.asanyarray(image.dataobj)
    b0 = data[..., bvals <= 50].mean(axis=-1)
    _, brain = median_otsu(b0, median_radius=3, numpass=1, autocrop=False, dilate=None)
    box = np.zeros(brain.shape, bool)
    box[tuple(slice(start, stop) for start, stop in BOX)] = True
    eligible = box & brain
    low_b = bvals <= 1050
    gradients = gradient_table(bvals[low_b], bvecs=bvecs[low_b], b0_threshold=50)
    fa = np.zeros(brain.shape)
    fa[eligible] = TensorModel(gradients, fit_method="WLS", min_signal=1e-4).fit(
        np.asarray(data[eligible][:, low_b], dtype=float)).fa
    roi = eligible & np.isfinite(fa) & (fa > 0.3) & (fa < 0.9)
    coords = np.argwhere(roi)
    if not np.array_equal(coords, receipt["roi_ijk"]):
        raise ValueError("Oracle coordinates differ from the full fixed low-b FA ROI")
    signal = np.asarray(data[roi], dtype=float)
    del data
    mean_b0 = b0[roi]
    if np.any(mean_b0 <= 0):
        raise ValueError("Fixed ROI has nonpositive b0; cannot normalize residuals")
    checks = {"fa": compare(fa[roi], receipt["fa"], atol=1e-10, rtol=1e-9),
              "mean_b0": compare(mean_b0, receipt["mean_b0"], atol=0, rtol=0)}
    return signal, mean_b0, {"n_voxels": len(coords), "exact_coordinate_membership": True,
                           "shared_DTI_and_mask_implementation": True, "comparisons": checks}


def check_all_receipt_maps(receipt, signal, bvals, mean_b0, basis, vertices, edges):
    reports = []
    for name in RECIPES:
        coefficients = receipt[f"coeff_{name}"]
        odf = coefficients[:, 2:] @ basis.T if name == "msmt" else coefficients @ basis.T
        counts, values, indices, mismatch_details = [], [], [], []
        for row, distribution in enumerate(odf):
            pk, ind = numpy_peaks(distribution, vertices, edges)
            count = int(np.sum(pk > 0))
            counts.append(count)
            values.append(pk)
            indices.append(ind)
            if (count != receipt[f"map_{name}"][row]
                    or not np.array_equal(ind, receipt[f"peak_indices_{name}"][row])) and len(mismatch_details) < 20:
                mismatch_details.append({"row": row, "ijk": receipt["roi_ijk"][row].tolist(),
                                         "expected_count": int(receipt[f"map_{name}"][row]),
                                         "independent_count": count,
                                         "expected_indices": receipt[f"peak_indices_{name}"][row].tolist(),
                                         "boundary": peak_boundary_diagnostics(distribution, vertices, edges)})
        counts, values, indices = np.asarray(counts), np.asarray(values), np.asarray(indices)
        design = receipt[f"design_{name}"]
        prediction = coefficients @ design.T
        if name == "msmt":
            measured, prediction = signal[:, bvals > 50], prediction[:, bvals > 50]
        else:
            measured = signal[:, bvals == int(name[5:])]
        if prediction.shape != measured.shape:
            raise ValueError(f"DWI prediction/source dimensions differ for {name}")
        nrmse = np.sqrt(np.mean((prediction - measured) ** 2, axis=1)) / mean_b0
        comparisons = {
            "independent_sh_reconstructed_odf": compare(odf, receipt[f"odf_{name}"], **TOLERANCES["sh_odf"]),
            "independent_peak_counts": compare(counts, receipt[f"map_{name}"], atol=0, rtol=0),
            "independent_peak_values": compare(values, receipt[f"peak_values_{name}"], **TOLERANCES["sh_odf"]),
            "independent_peak_indices": compare(indices, receipt[f"peak_indices_{name}"], atol=0, rtol=0),
            "source_DWI_residual_recomputed": compare(nrmse, receipt[f"nrmse_{name}"], **TOLERANCES["receipt_residual"]),
        }
        reports.append({"recipe": name, "n_tested_voxels": len(signal), "comparisons": comparisons,
                        "first_count_mismatch_diagnostics": mismatch_details,
                        "qc": {"crossing_fraction": float(np.mean(counts >= 2)),
                               "n_zero_peak_voxels": int(np.sum(counts == 0)),
                               "n_capped_three_peak_voxels": int(np.sum(counts == 3)),
                               "negative_odf_sample_fraction": float(np.mean(odf < 0)),
                               "nrmse_quantiles_0_50_95_99_100": np.quantile(nrmse, [0, .5, .95, .99, 1]).tolist(),
                               "nrmse_gt_0_1_count": int(np.sum(nrmse > .1))}})
    return reports


class QRDualNNLS:
    """min .5||Xc-y||² subject Gc>=0, via a distinct dual active-set solve."""

    def __init__(self, design, constraints):
        self.design, self.constraints = np.asarray(design), np.asarray(constraints)
        if np.linalg.matrix_rank(self.design) != self.design.shape[1]:
            raise ValueError("The QR/dual derivation requires a full-column-rank design")
        self.q, self.r = np.linalg.qr(self.design, mode="reduced")
        self.a = solve_triangular(self.r.T, self.constraints.T, lower=True).T

    def solve(self, measured):
        z = self.q.T @ measured
        dual, dual_residual_norm = nnls(self.a.T, -z, **DUAL_NNLS_SETTINGS)
        u = z + self.a.T @ dual
        coefficients = solve_triangular(self.r, u)
        primal = self.constraints @ coefficients
        residual = self.design @ coefficients - measured
        stationarity = self.design.T @ residual - self.constraints.T @ dual
        signal_energy = max(1.0, float(measured @ measured))
        gradient_scale = max(1.0, float(np.max(np.abs(self.design.T @ measured))))
        complementarity = float(np.max(np.abs(dual * primal)))
        return coefficients, {
            "primal_constraint_minimum": float(np.min(primal)),
            "dual_multiplier_minimum": float(np.min(dual)),
            "max_abs_complementarity": complementarity,
            "max_abs_complementarity_over_signal_energy": complementarity / signal_energy,
            "stationarity_infinity_norm": float(np.max(np.abs(stationarity))),
            "stationarity_over_source_gradient_scale": float(np.max(np.abs(stationarity))) / gradient_scale,
            "nnls_residual_norm_equals_norm_u_not_primal_fit_residual": float(dual_residual_norm),
            "independent_primal_fit_residual_norm": float(np.linalg.norm(residual)),
            "nonunique_dual_multipliers_not_compared": True,
        }


def qp_equation_fixtures():
    """Three tiny exact projections validate signs and non-orthogonal constraints."""
    design = np.array([[1., 0.], [0., 2.], [1., 1.]])
    fixtures = [(np.eye(2), np.eye(2), np.array([-2., 3.]), np.array([0., 3.])),
                (design, np.eye(2), design @ np.array([1.2, .8]), np.array([1.2, .8])),
                (np.eye(2), np.array([[1., -1.], [0., 1.]]), np.array([0., 1.]), np.array([.5, .5]))]
    reports = []
    for design, constraints, measured, expected in fixtures:
        actual, kkt = QRDualNNLS(design, constraints).solve(measured)
        agreement = compare(actual, expected, atol=1e-12, rtol=1e-12)
        passed = (agreement["passed"] and kkt["primal_constraint_minimum"] >= -1e-12
                  and kkt["dual_multiplier_minimum"] >= 0 and kkt["max_abs_complementarity"] <= 1e-12
                  and kkt["stationarity_infinity_norm"] <= 1e-12)
        reports.append({"passed": passed, "agreement": agreement, "KKT_diagnostics": kkt})
    return {"passed": all(row["passed"] for row in reports), "fixtures": reports,
            "scope": "Tiny exact constrained least-squares fixtures; not scientific source fits."}


def second_solver_check(receipt, signal, mean_b0, basis, vertices, edges):
    design, reg = receipt["design_msmt"], receipt["reg_msmt"]
    if design.shape != (193, 47) or reg.shape != (len(vertices) + 2, 47):
        raise ValueError("Unexpected shared MSMT design or constraint shape")
    reconstructed_reg = np.zeros_like(reg)
    reconstructed_reg[:2, :2] = np.eye(2)
    reconstructed_reg[2:, 2:] = basis
    reg_check = compare(reconstructed_reg, reg, atol=1e-12, rtol=1e-12)
    solver = QRDualNNLS(design, reg)
    rows = np.unique(np.linspace(0, len(signal) - 1, min(MAX_QP_VOXELS, len(signal)), dtype=int))
    if len(signal) > FAILURE_SENTINEL_ROW:
        rows = np.unique(np.r_[rows, FAILURE_SENTINEL_ROW])
    diagnostics, comparisons = [], []
    for row in rows:
        y, observed_b0 = signal[row], mean_b0[row]
        coeff, kkt = solver.solve(y)
        original = receipt["coeff_msmt"][row]
        predicted, oracle_prediction = design @ coeff, design @ original
        odf, oracle_odf = basis @ coeff[2:], basis @ original[2:]
        # Add back the objective constant and divide by source energy scale to
        # compare stable nonnegative losses rather than large negative offsets.
        loss = 0.5 * np.mean((predicted - y) ** 2) / observed_b0 ** 2
        oracle_loss = 0.5 * np.mean((oracle_prediction - y) ** 2) / observed_b0 ** 2
        scale = max(float(np.max(np.abs(oracle_odf))), np.finfo(float).tiny)
        coeff_scale = max(1.0, float(np.max(np.abs(coeff))), float(np.max(np.abs(original))))
        primal_violation = max(0.0, -float(np.min(reg @ coeff))) / coeff_scale
        oracle_violation = max(0.0, -float(np.min(reg @ original))) / coeff_scale
        independent_peaks, independent_indices = numpy_peaks(odf, vertices, edges)
        oracle_peaks, oracle_indices = numpy_peaks(oracle_odf, vertices, edges)
        count, oracle_count = int(np.sum(independent_peaks > 0)), int(np.sum(oracle_peaks > 0))
        numerical = {
            "normalized_full_signal_loss": compare(loss, oracle_loss, **TOLERANCES["qp_normalized_loss"]),
            "predicted_signal_over_b0": compare(predicted / observed_b0, oracle_prediction / observed_b0,
                                                **TOLERANCES["qp_signal_over_b0"]),
            "odf_over_oracle_peak": compare(odf / scale, oracle_odf / scale,
                                           **TOLERANCES["qp_odf_over_oracle_peak"]),
            "primal_feasibility": {"passed": max(primal_violation, oracle_violation)
                                   <= TOLERANCES["qp_constraint_violation_over_coefficient_scale"],
                                   "independent_violation": primal_violation,
                                   "oracle_violation": oracle_violation,
                                   "tolerance": TOLERANCES["qp_constraint_violation_over_coefficient_scale"]},
        }
        row_report = {"row": int(row), "ijk": receipt["roi_ijk"][row].tolist(),
                      "status": "nnls_returned_without_iteration_failure", "iterations": None,
                      "iteration_count_note": "SciPy nnls does not expose its completed iteration count; maxiter is bounded.",
                      "KKT_diagnostics": kkt,
                      "objective_without_constant": float(0.5 * predicted @ predicted - y @ predicted),
                      "oracle_objective_without_constant": float(0.5 * oracle_prediction @ oracle_prediction - y @ oracle_prediction),
                      "normalized_loss": float(loss), "oracle_normalized_loss": float(oracle_loss),
                      "peak_count": count, "oracle_peak_count": oracle_count,
                      "peak_indices": independent_indices.tolist(), "oracle_peak_indices": oracle_indices.tolist(),
                      "peak_counts_equal": count == oracle_count,
                      "coefficient_max_abs_difference_diagnostic_only": float(np.max(np.abs(coeff - original))),
                      "comparisons": numerical}
        if count != oracle_count or not np.array_equal(independent_indices, oracle_indices):
            row_report["peak_boundary_diagnostics"] = {
                "independent": peak_boundary_diagnostics(odf, vertices, edges),
                "oracle": peak_boundary_diagnostics(oracle_odf, vertices, edges),
                "policy": "Count differences require review even when continuous numerical comparisons pass; boundary proximity never automatically excuses them."}
        diagnostics.append(row_report)
        comparisons.extend(numerical.values())
    return {"solver": "thin_QR_plus_dual_scipy_nnls", "settings": DUAL_NNLS_SETTINGS,
            "n_tested_voxels": len(rows), "row_indices": rows.tolist(),
            "sampling": "64 equally spaced rows of the full lexicographic ROI plus retained OSQP failure row 1047; at most 65 unique rows. The additional sentinel is disclosed, not substituted for a sampled voxel.",
            "mathematics": "X=QR, z=Q.T@y, A=G@R^-1; lambda=nnls(A.T,-z)>=0; u=z+A.T@lambda; c=solve(R,u). Triangular solves avoid an explicit inverse or Gram matrix in the independent solve.",
            "shared_design_rank": int(np.linalg.matrix_rank(design)),
            "shared_design_condition_number": float(np.linalg.cond(design)),
            "independent_constraint_basis_comparison": reg_check,
            "numerical_comparisons_passed": reg_check["passed"] and all(x["passed"] for x in comparisons),
            "all_peak_counts_equal": all(x["peak_counts_equal"] for x in diagnostics),
            "voxel_diagnostics": diagnostics}


def check(data_dir, oracle_output):
    for name, expected in {"dipy": "1.12.1", "scipy": "1.14.1"}.items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f"Independent check requires {name}=={expected}")
    fixtures = qp_equation_fixtures()
    if not fixtures["passed"]:
        raise ValueError("Independent QR/dual-NNLS equation fixtures failed")
    image, bvals, bvecs, hashes = load_source(data_dir)
    with np.load(oracle_output / "fit_receipt.npz", allow_pickle=False) as source:
        receipt = {key: source[key] for key in source.files}
    metadata = json.loads(str(receipt["metadata_json"]))
    if metadata["source_sha256"] != hashes:
        raise ValueError("Oracle receipt does not use the pinned source bytes")
    if metadata["header_spatial_units"] != image.header.get_xyzt_units()[0]:
        raise ValueError("Receipt misstates the source NIfTI spatial units")
    geometry_checks = {"affine": compare(image.affine, metadata["affine"], atol=0, rtol=0),
                       "header_zooms": compare(image.header.get_zooms()[:3], metadata["header_voxel_sizes"], atol=0, rtol=0)}
    vertices, edges = receipt["sphere_vertices"], receipt["sphere_edges"]
    if vertices.shape != (362, 3) or edges.ndim != 2 or edges.shape[1] != 2:
        raise ValueError("Unexpected sphere mesh shape")
    if not np.issubdtype(edges.dtype, np.integer) or edges.min() < 0 or edges.max() >= len(vertices):
        raise ValueError("Invalid sphere edges")
    from dipy.data import default_sphere
    if (not np.array_equal(vertices, default_sphere.vertices)
            or not np.array_equal(edges, default_sphere.edges)):
        raise ValueError("Receipt mesh differs from the shared pinned DIPY default sphere")
    sphere_metadata = metadata["peak_parameters"]["sphere"]
    if (array_digest(vertices, "<f8") != sphere_metadata["vertices_sha256_le_float64"]
            or array_digest(edges, "<i8") != sphere_metadata["edges_sha256_le_int64"]):
        raise ValueError("Sphere receipt hashes differ from the public contract")
    basis = legacy_descoteaux_basis(vertices)
    signal, mean_b0, roi_report = shared_roi_check(image, bvals, bvecs, receipt)
    map_reports = check_all_receipt_maps(receipt, signal, bvals, mean_b0, basis, vertices, edges)
    qp_report = second_solver_check(receipt, signal, mean_b0, basis, vertices, edges)
    passed = all(x["passed"] for x in geometry_checks.values()) and all(
        x["passed"] for x in roi_report["comparisons"].values()) and all(
        x["passed"] for recipe in map_reports for x in recipe["comparisons"].values()) and (
        qp_report["numerical_comparisons_passed"] and qp_report["all_peak_counts_equal"])
    return {"status": "passed" if passed else "failed", "source_sha256": hashes,
            "QP_equation_fixtures": fixtures,
            "source_geometry": {"shape": list(image.shape), "header_spatial_units": image.header.get_xyzt_units()[0],
                                "comparisons": geometry_checks, "physical_mm_operations_performed": False},
            "fixed_roi": roi_report, "all_roi_sh_peak_residual_checks": map_reports,
            "bounded_independent_QP_check": qp_report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "evidence_type": "independent_SH_peak_implementation_and_bounded_second_QP_solver_check",
        "independent_components": ["SciPy legacy Descoteaux basis assembly", "NumPy neighbor maxima and antipodal peak selection",
                                   "Thin QR plus dual SciPy nonnegative least-squares solver, separate from the oracle CLARABEL implementation",
                                   "direct source-signal residual recomputation"],
        "shared_components": ["source bytes", "sphere meshes", "DIPY median_otsu and DTI ROI fitting",
                              "oracle response estimates and signal-design matrices", "SciPy complex harmonics also used internally by DIPY",
                              "NumPy/SciPy numerical libraries"],
        "interpretation_limit": "All-ROI SH, peak and residual reconstruction plus at most 65 independent MSMT solves; no independent CSD fit or response estimation, no anatomical fibre-count truth, and no frontier-agent difficulty evidence.",
        "pinned_sources": ["https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/reconst/shm.py",
                           "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/reconst/dirspeed.pyx",
                           "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/reconst/recspeed.pyx",
                           "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/reconst/mcsd.py",
                           "https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.optimize.nnls.html"],
        "tolerances": TOLERANCES,
        "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ("numpy", "scipy", "nibabel", "dipy", "clarabel")}},
    }
    try:
        report.update(check(args.data_dir, args.oracle_output))
    except Exception as error:
        report.update(status="error", error_type=type(error).__name__, error=str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "error": report.get("error"), "report": str(args.report)}))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
