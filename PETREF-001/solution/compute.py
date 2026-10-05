"""Pinned, explicitly approximate midpoint-SRTM method control; no network access."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

PIPELINE = "srtm-pwl-midpoint-v2"
DATASET = "ds001420"
SNAPSHOT = "1.2.0"
TREE = "c937d6f6c05c0e7c788190f4962c0393534a7212"
COMMIT = "2b21a6d6e57cf712ec068faf594be4bbf14cdcbe"
SCANS = [(s, e) for s in ("sub-01", "sub-02")
         for e in ("ses-baseline", "ses-rescan")]
COLUMNS = ["left_putamen", "right_putamen", "left_cerebellum_cortex",
           "right_cerebellum_cortex"]
LOWER = np.array([0.01, 0.0001, -0.5])
UPPER = np.array([3.0, 5.0, 15.0])
STARTS = [[1.0, 0.05, 0.5], [1.0, 0.2, 2.0], [1.0, 0.8, 5.0]]
TARGET = "putamen_equal_hemisphere"
REFERENCE = "cerebellar_cortex_equal_hemisphere"
MODEL = "SRTM-PWL-midpoint"


class FitFailure(RuntimeError):
    def __init__(self, candidates):
        super().__init__("all three prespecified optimization attempts failed")
        self.candidates = candidates


def metadata_contract(manifest):
    """Public recipe only: this function does not read TACs or fit any model."""
    return {
        "pipeline_id": PIPELINE, "dataset_id": DATASET, "snapshot": SNAPSHOT,
        "git_tree_sha1": TREE, "git_tag_commit_sha1": COMMIT,
        "source_sha256": {v["path"]: v["sha256"] for v in manifest["files"]},
        "scans": [{"subject": s, "session": e} for s, e in SCANS],
        "source_columns": COLUMNS, "activity_units": "Bq/mL",
        "target_region": TARGET, "reference_region": REFERENCE,
        "aggregation": "unweighted_arithmetic_mean_of_two_hemisphere_TACs",
        "preprocessing": {
            "pvc": "nopvc", "tac_variant": "desc-mc",
            "time_units": "minutes", "observation": "source_frame_midpoint",
            "initial_zero_frames": "retain", "origin": [0.0, 0.0],
            "reference_reconstruction": "piecewise_linear_origin_and_midpoints",
            "frame_average_forward_model": False,
            "normalization": "divide_both_TACs_by_maximum_reference"},
        "model": {
            "name": MODEL, "parameter_order": ["R1", "k2", "BP_ND"],
            "theta": "k2/(1+BP_ND)", "z_initial": 0.0,
            "z_ode": "dz/dt=C_R-theta*z",
            "prediction": "R1*C_R+(k2-R1*theta)*z",
            "integration": "analytic_piecewise_linear_exponential_convolution",
            "k2_units": "min^-1", "k2prime": "k2/R1"},
        "fit": {
            "objective": "unweighted_sum_squared_normalized_frame_residuals",
            "residual": "prediction_minus_observed",
            "bounds_lower": LOWER.tolist(), "bounds_upper": UPPER.tolist(),
            "bounds_interpretation": "numerical_not_physiological",
            "starts": STARTS, "method": "trf", "jac": "3-point", "x_scale": 1.0,
            "loss": "linear", "ftol": 1e-10, "xtol": 1e-10, "gtol": 1e-10,
            "max_nfev": 5000,
            "selection": "lowest_SSE_successful_finite_in_bounds_candidate_then_start_index",
            "bound_flag_atol": "1e-7*max(1,upper-lower)", "bound_flag_rtol": 0.0},
        "summary": {
            "scan_mean": "equal_weight_all_four_scans",
            "pair_percent": "100*abs(baseline-rescan)/pair_mean",
            "nonpositive_pair_mean": "undefined_nonpositive_mean",
            "headline_percent": "equal_weight_two_pairs_only_if_both_defined",
            "population_reliability_claim": False},
        "tolerances": {
            "source": {"atol": 1e-10, "rtol": 1e-9},
            "parameters": {"R1_atol": 1e-6, "k2_atol": 1e-7,
                           "BP_ND_atol": 1e-6, "rtol": 1e-5},
            "normalized_prediction": {"atol": 1e-7, "rtol": 1e-6},
            "normalized_arithmetic": {"atol": 1e-8, "rtol": 1e-6},
            "summary_atol": 1e-6, "percent_atol": 1e-5},
    }


def read_tac(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        names = reader.fieldnames
        assert names and len(names) == len(set(names)), "duplicate/missing TAC headers"
        rows = list(reader)
    assert rows, "empty TAC"
    assert all(set(r) == set(names) and None not in r.values() for r in rows), "ragged TAC"
    need = ["frame_start", "frame_end"] + COLUMNS
    assert set(need) <= set(names), "missing required TAC columns"
    a = np.array([[float(r[c]) for c in need] for r in rows], dtype=float)
    assert np.isfinite(a).all(), "nonfinite required source field"
    start, end = a[:, 0], a[:, 1]
    assert start[0] == 0 and np.all(end > start), "invalid frame bounds"
    assert np.all(start[1:] >= end[:-1]), "overlapping/nonchronological frames"
    assert np.all(a[:, 2:] >= 0), "negative required regional TAC"
    return start, end, a[:, 2:]


def load_source(data_dir):
    root = Path(data_dir).resolve()
    manifest = json.loads((root / "source_manifest.json").read_text())
    assert manifest["dataset_id"] == DATASET and manifest["snapshot"] == SNAPSHOT
    assert manifest["git_tree_sha1"] == TREE
    assert manifest["git_tag_commit_sha1"] == COMMIT
    paths = [v["path"] for v in manifest["files"]]
    assert len(paths) == len(set(paths)), "duplicate source manifest path"
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        assert path.is_relative_to(root), "unsafe manifest path"
        raw = path.read_bytes()
        assert len(raw) == item["size_bytes"], "source byte count changed"
        assert hashlib.sha256(raw).hexdigest() == item["sha256"], "source SHA256 changed"
    by_role = {}
    for item in manifest["files"]:
        key = (item["role"], item.get("subject"), item.get("session"))
        if item["role"] in ("tac", "pet_metadata"):
            assert key not in by_role, "duplicate source scan role"
            by_role[key] = item
    assert set(by_role) == {(role, s, e) for role in ("tac", "pet_metadata") for s, e in SCANS}
    dataset_meta = [v for v in manifest["files"] if v["role"] == "dataset_metadata"]
    assert len(dataset_meta) == 1
    assert json.loads((root / dataset_meta[0]["path"]).read_text())["License"] == "CC0"
    scans = []
    for s, e in SCANS:
        start, end, tac = read_tac(root / by_role[("tac", s, e)]["path"])
        sidecar = json.loads((root / by_role[("pet_metadata", s, e)]["path"]).read_text())
        assert sidecar["Units"] == "Bq/mL"
        assert sidecar["ScanStart"] == sidecar["InjectionStart"] == 0
        assert sidecar["ImageDecayCorrected"] is True and sidecar["ImageDecayCorrectionTime"] == 0
        assert np.array_equal(start, np.asarray(sidecar["FrameTimesStart"], dtype=float))
        assert np.array_equal(end, start + np.asarray(sidecar["FrameDuration"], dtype=float))
        mid = (start + end) / 120.0
        target = tac[:, :2].mean(axis=1)
        reference = tac[:, 2:].mean(axis=1)
        scale = float(reference.max())
        assert scale > 0, "reference has no positive signal"
        scans.append({"subject": s, "session": e, "start": start, "end": end,
                      "mid": mid, "tacs": tac, "target": target,
                      "reference": reference, "scale": scale})
    return manifest, scans


def linear_segment(z, left, slope, h, theta):
    """Stable exact convolution propagation for C_R(u)=left+slope*u."""
    x = theta * h
    if abs(x) < 1e-3:
        # (1-exp(-x))/x and (x-1+exp(-x))/x**2; analytic limits at zero.
        p1 = 1 + x * (-0.5 + x * (1/6 + x * (-1/24 + x * (1/120 - x/720))))
        p2 = 0.5 + x * (-1/6 + x * (1/24 + x * (-1/120 + x * (1/720 - x/5040))))
    else:
        em1 = np.expm1(-x)
        p1 = -em1 / x
        p2 = (x + em1) / (x*x)
    return np.exp(-x) * z + left * h * p1 + slope * h*h * p2


def srtm_predict(mid, reference, params):
    R1, k2, bp = np.asarray(params, dtype=float)
    theta = k2 / (1 + bp)
    assert theta > 0 and np.isfinite(theta)
    times = np.r_[0.0, mid]
    refs = np.r_[0.0, reference]
    assert np.all(np.diff(times) > 0)
    z = 0.0
    values = []
    for i, h in enumerate(np.diff(times)):
        z = linear_segment(z, refs[i], (refs[i+1] - refs[i]) / h, h, theta)
        values.append(R1 * refs[i+1] + (k2 - R1*theta) * z)
    return np.asarray(values)


def boundary_flags(params):
    atol = 1e-7 * np.maximum(1.0, UPPER - LOWER)
    return np.abs(params - LOWER) <= atol, np.abs(params - UPPER) <= atol


def fit_scan(scan):
    scale = scan["scale"]
    ref, target = scan["reference"] / scale, scan["target"] / scale
    def residual(p):
        return srtm_predict(scan["mid"], ref, p) - target
    candidates = []
    for index, start in enumerate(STARTS):
        try:
            fit = least_squares(residual, start, bounds=(LOWER, UPPER), method="trf",
                                jac="3-point", x_scale=1.0, loss="linear", ftol=1e-10,
                                xtol=1e-10, gtol=1e-10, max_nfev=5000)
            params = fit.x
            usable = bool(fit.success and np.isfinite(params).all()
                          and np.all(params >= LOWER) and np.all(params <= UPPER)
                          and np.isfinite(fit.fun).all())
            item = {"start_index": index, "initial": start, "success": usable,
                    "optimizer_status": int(fit.status), "nfev": int(fit.nfev),
                    "message": str(fit.message), "params": params.tolist(),
                    "normalized_sse": float(np.dot(fit.fun, fit.fun)),
                    "optimality": float(fit.optimality),
                    "jacobian_singular_values": np.linalg.svd(fit.jac, compute_uv=False).tolist(),
                    "jacobian_condition": float(np.linalg.cond(fit.jac))}
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            item = {"start_index": index, "initial": start, "success": False,
                    "optimizer_status": None, "nfev": 0, "message": str(error),
                    "params": None, "normalized_sse": None, "optimality": None,
                    "jacobian_singular_values": None,
                    "jacobian_condition": None}
        candidates.append(item)
    valid = [c for c in candidates if c["success"]]
    if not valid:
        raise FitFailure(candidates)
    chosen = min(valid, key=lambda c: (c["normalized_sse"], c["start_index"]))
    params = np.array(chosen["params"])
    prediction = srtm_predict(scan["mid"], scan["reference"], params)
    error = prediction - scan["target"]
    sse = float(error @ error)
    rmse = float(np.sqrt(sse / len(error)))
    low, high = boundary_flags(params)
    return {"params": params, "prediction": prediction, "residual": error,
            "sse": sse, "rmse": rmse, "normalized_rmse": rmse / scale,
            "selected_start_index": chosen["start_index"],
            "optimizer_status": chosen["optimizer_status"], "nfev": chosen["nfev"],
            "lower_bound": low, "upper_bound": high, "candidates": candidates}


def summarize(params):
    pairs = []
    for n, subject in enumerate(("sub-01", "sub-02")):
        b, r = float(params[2*n, 2]), float(params[2*n+1, 2])
        mean = (b + r) / 2
        pct = 100 * abs(b-r) / mean if mean > 0 else None
        pairs.append({"subject": subject, "baseline_BP_ND": b, "rescan_BP_ND": r,
                      "absolute_difference": abs(b-r), "pair_mean": mean,
                      "test_retest_pct": pct,
                      "status": "ok" if pct is not None else "undefined_nonpositive_mean"})
    defined = sum(p["test_retest_pct"] is not None for p in pairs)
    return {"status": "ok", "pipeline_id": PIPELINE, "n_scans": 4, "n_subjects": 2,
            "putamen_BP_ND_mean": float(params[:, 2].mean()), "per_subject": pairs,
            "n_defined_pairs": defined,
            "test_retest_pct": float(np.mean([p["test_retest_pct"] for p in pairs]))
            if defined == 2 else None}


def observations(scans):
    return [{"subject": s["subject"], "session": s["session"], "n_frames": len(s["mid"]),
             "start_s": float(s["start"][0]), "end_s": float(s["end"][-1]),
             "duration_s": float(s["end"][-1]-s["start"][0])} for s in scans]


def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(json_safe(value), indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    assert rows
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_arrays(scans, fits):
    arrays = {
        "ref_subject": np.array([s for s, _ in SCANS]),
        "ref_session": np.array([e for _, e in SCANS]),
        "ref_params": np.array([f["params"] for f in fits]),
        "ref_frame_scan": np.concatenate([np.full(len(s["mid"]), i) for i, s in enumerate(scans)]),
        "ref_frame_index": np.concatenate([np.arange(len(s["mid"])) for s in scans]),
        "ref_source_tacs": np.concatenate([s["tacs"] for s in scans]),
        "ref_reference_scale": np.array([s["scale"] for s in scans]),
    }
    for key, source in [("frame_start_s", "start"), ("frame_end_s", "end"),
                        ("mid_time_min", "mid"), ("target", "target"), ("reference", "reference")]:
        arrays["ref_" + key] = np.concatenate([s[source] for s in scans])
    for key in ("prediction", "residual"):
        arrays["ref_" + key] = np.concatenate([f[key] for f in fits])
    for key in ("selected_start_index", "optimizer_status", "nfev", "lower_bound", "upper_bound"):
        arrays["ref_" + key] = np.array([f[key] for f in fits])
    return arrays


def write_outputs(out, manifest, scans, fits):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    param_rows, frame_rows = [], []
    for s, f in zip(scans, fits):
        R1, k2, bp = f["params"]
        param_rows.append({
            "subject": s["subject"], "session": s["session"], "target": TARGET,
            "reference_region": REFERENCE, "model": MODEL, "R1": R1, "k2": k2,
            "BP_ND": bp, "k2prime": k2 / R1, "status": "ok",
            "selected_start_index": f["selected_start_index"],
            "optimizer_status": f["optimizer_status"], "nfev": f["nfev"],
            "at_lower_bound": json.dumps(f["lower_bound"].tolist()),
            "at_upper_bound": json.dumps(f["upper_bound"].tolist()),
            "sse": f["sse"], "rmse": f["rmse"], "normalized_rmse": f["normalized_rmse"],
            "reference_scale": s["scale"]})
        for j in range(len(s["mid"])):
            row = {"subject": s["subject"], "session": s["session"], "frame_index": j,
                   "frame_start_s": s["start"][j], "frame_end_s": s["end"][j],
                   "mid_time_min": s["mid"][j]}
            row.update(dict(zip(COLUMNS, s["tacs"][j])))
            row.update(target=s["target"][j], reference=s["reference"][j],
                       predicted_target=f["prediction"][j], residual=f["residual"][j])
            frame_rows.append(row)
    write_csv(out / "bp_estimates.csv", param_rows)
    write_csv(out / "tac_fit.csv", frame_rows)
    arrays = make_arrays(scans, fits)
    result = summarize(arrays["ref_params"])
    metadata = {**metadata_contract(manifest), "status": "ok",
                "per_scan_observations": observations(scans)}
    write_json(out / "pet_results.json", result)
    write_json(out / "run_metadata.json", metadata)
    np.savez_compressed(out / "analysis_arrays.npz", **arrays,
                        candidates_json=json.dumps(json_safe([f["candidates"] for f in fits]),
                                                   allow_nan=False))
    scan_text = "\n".join(
        f"- {s['subject']} {s['session']}: {len(s['mid'])} frames, "
        f"{s['end'][-1]/60:g} min; BP_ND={f['params'][2]:.6f}, "
        f"R1={f['params'][0]:.6f}, k2={f['params'][1]:.6f} min^-1, "
        f"normalized RMSE={f['normalized_rmse']:.6g}; "
        f"boundary flags={int(f['lower_bound'].sum()+f['upper_bound'].sum())}."
        for s, f in zip(scans, fits))
    pair_text = "\n".join(
        f"- {p['subject']}: absolute BP difference={p['absolute_difference']:.6f}; "
        f"repeat difference={p['test_retest_pct']}% ({p['status']})."
        for p in result["per_subject"])
    (out / "findings.md").write_text(
        "# Four-scan midpoint-SRTM method control\n\n" + scan_text + "\n\n" + pair_text +
        f"\n\nMean BP_ND={result['putamen_BP_ND_mean']:.6f}; mean paired repeat "
        f"difference={result['test_retest_pct']}%.\n\n"
        "The fixed model uses equally weighted left/right regional means, not a pooled "
        "voxel-weighted bilateral mask. Its reference input is a piecewise-linear "
        "reconstruction through (0,0) and measured frame midpoints. Predicted values are "
        "compared at midpoints; this is not a frame-average forward model. The 53.6-minute "
        "baseline scan and the three 90-minute scans are not duration matched. "
        "Reference-tissue assumptions, input reconstruction, unweighted fitting and "
        "uncorrected partial volume can affect estimates. Numerical convergence and "
        "agreement with a computational reference do not establish biological truth or "
        "parameter identifiability. These two within-person pairs are descriptive, not "
        "an estimate of population reliability. No whole-cerebellum comparison or "
        "cross-estimator agreement is claimed.\n")
    return arrays, result, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.environ.get("PETREF_DATA", "/app/data/petref"))
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    completed_attempts = []
    try:
        manifest, scans = load_source(args.data_dir)
        fits = []
        for scan in scans:
            try:
                fitted = fit_scan(scan)
            except FitFailure as error:
                completed_attempts.append({"subject": scan["subject"], "session": scan["session"],
                                           "candidates": error.candidates})
                raise
            fits.append(fitted)
            completed_attempts.append({"subject": scan["subject"], "session": scan["session"],
                                       "candidates": fitted["candidates"]})
        _, result, _ = write_outputs(out, manifest, scans, fits)
        print(json.dumps(result, allow_nan=False))
    except Exception as error:
        write_json(out / "optimizer_diagnostics.json", completed_attempts)
        write_json(out / "run_metadata.json", {
            "status": "failed_precondition", "pipeline_id": PIPELINE,
            "dataset_id": DATASET, "reason": str(error)})
        (out / "findings.md").write_text("# Failed precondition\n\n" + str(error) + "\n")
        raise


if __name__ == "__main__":
    main()
