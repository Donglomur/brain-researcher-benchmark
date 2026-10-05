"""Independent raw-TAC parsing and ODE/matrix-exponential forward checks.

No imports from the oracle or verifier. The alternate dogbox fit shares SciPy's
optimizer library, but uses a separate matrix-exponential predictor and Jacobian.
Parameter disagreement is diagnostic, not a biological-truth failure gate.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
from scipy.optimize import least_squares

SCANS = [(s, e) for s in ("sub-01", "sub-02") for e in ("ses-baseline", "ses-rescan")]
COLUMNS = ["left_putamen", "right_putamen", "left_cerebellum_cortex", "right_cerebellum_cortex"]
LOW = np.array([.01, .0001, -.5])
HIGH = np.array([3., 5., 15.])


def ode_prediction(mid, reference, params):
    r1, k2, bp = params
    theta = k2 / (1+bp)
    times, values = [0.] + list(mid), [0.] + list(reference)
    z, answer = 0., []
    for a, b, ca, cb in zip(times[:-1], times[1:], values[:-1], values[1:]):
        slope = (cb-ca)/(b-a)
        def rhs(t, state):
            return [ca+slope*(t-a)-theta*state[0]]
        sol = solve_ivp(rhs, (a, b), [z], method="DOP853", rtol=1e-11, atol=1e-12,
                        t_eval=[b])
        assert sol.success
        z = sol.y[0, -1]
        answer.append(r1*cb + (k2-r1*theta)*z)
    return np.asarray(answer)


def matrix_prediction(mid, reference, params):
    """Linear augmented-state propagation, independent of the oracle phi functions."""
    r1, k2, bp = params
    theta = k2/(1+bp)
    generator = np.array([[-theta, 1, 0], [0, 0, 1], [0, 0, 0]])
    z = 0.
    result = []
    time0, ref0 = 0., 0.
    for time1, ref1 in zip(mid, reference):
        h = time1-time0
        state = expm(generator*h) @ np.array([z, ref0, (ref1-ref0)/h])
        z = state[0]
        result.append(r1*ref1 + (k2-r1*theta)*z)
        time0, ref0 = time1, ref1
    return np.asarray(result)


def matrix_jacobian(mid, reference, params):
    columns = []
    for k in range(3):
        perturbed = np.asarray(params, dtype=complex).copy()
        perturbed[k] += 1e-20j
        columns.append(matrix_prediction(mid, reference, perturbed).imag / 1e-20)
    return np.column_stack(columns)


def load_source(data_dir):
    root = Path(data_dir)
    manifest = json.loads((root / "source_manifest.json").read_text())
    assert manifest["dataset_id"] == "ds001420" and manifest["snapshot"] == "1.2.0"
    assert manifest["git_tree_sha1"] == "c937d6f6c05c0e7c788190f4962c0393534a7212"
    assert manifest["git_tag_commit_sha1"] == "2b21a6d6e57cf712ec068faf594be4bbf14cdcbe"
    for file in manifest["files"]:
        data = (root / file["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == file["sha256"]
        assert len(data) == file["size_bytes"]
    records = {}
    for key in SCANS:
        entries = [f for f in manifest["files"]
                   if (f.get("subject"), f.get("session")) == key]
        tsv = [f for f in entries if f["role"] == "tac"]
        raw = [f for f in entries if f["role"] == "pet_metadata"]
        assert len(tsv) == len(raw) == 1
        with (root / tsv[0]["path"]).open(newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        sidecar = json.loads((root / raw[0]["path"]).read_text())
        start = np.array([float(r["frame_start"]) for r in rows])
        end = np.array([float(r["frame_end"]) for r in rows])
        assert np.array_equal(start, sidecar["FrameTimesStart"])
        assert np.array_equal(end-start, sidecar["FrameDuration"])
        assert sidecar["ScanStart"] == sidecar["InjectionStart"] == 0
        assert sidecar["ImageDecayCorrected"] and sidecar["ImageDecayCorrectionTime"] == 0
        assert sidecar["Units"] == "Bq/mL"
        raw_tacs = np.array([[float(r[name]) for name in COLUMNS] for r in rows])
        assert np.isfinite(raw_tacs).all() and (raw_tacs >= 0).all()
        target = (raw_tacs[:, 0]+raw_tacs[:, 1])*.5
        reference = (raw_tacs[:, 2]+raw_tacs[:, 3])*.5
        records[key] = {"start": start, "end": end, "mid": (start+end)/120,
                        "raw": raw_tacs, "target": target, "reference": reference,
                        "scale": float(max(reference))}
    return manifest, records


def check(data_dir, output_dir, alternate=True):
    out = Path(output_dir)
    manifest, source = load_source(data_dir)
    with (out / "bp_estimates.csv").open(newline="") as stream:
        parameter_rows = list(csv.DictReader(stream))
    params = {(r["subject"], r["session"]): r for r in parameter_rows}
    assert len(parameter_rows) == len(params) == 4 and set(params) == set(SCANS)
    with (out / "tac_fit.csv").open(newline="") as stream:
        frame_rows = list(csv.DictReader(stream))
    frames = {(r["subject"], r["session"], int(r["frame_index"])): r for r in frame_rows}
    assert len(frames) == len(frame_rows) == sum(len(v["mid"]) for v in source.values())
    with np.load(out / "analysis_arrays.npz", allow_pickle=False) as receipt:
        candidates = json.loads(str(receipt["candidates_json"]))
    report = []
    for i, key in enumerate(SCANS):
        scan, row = source[key], params[key]
        p = np.array([float(row[n]) for n in ("R1", "k2", "BP_ND")])
        assert np.isfinite(p).all() and np.all(p >= LOW) and np.all(p <= HIGH)
        norm_ref, norm_tar = scan["reference"]/scan["scale"], scan["target"]/scan["scale"]
        pred_ode = ode_prediction(scan["mid"], norm_ref, p)
        pred_matrix = matrix_prediction(scan["mid"], norm_ref, p)
        assert np.allclose(pred_ode, pred_matrix, atol=1e-9, rtol=1e-9)
        predicted, residuals = [], []
        for j in range(len(scan["mid"])):
            frame = frames[key + (j,)]
            for field, expected in [("frame_start_s", scan["start"][j]),
                                    ("frame_end_s", scan["end"][j]),
                                    ("mid_time_min", scan["mid"][j]),
                                    ("target", scan["target"][j]),
                                    ("reference", scan["reference"][j])]:
                assert float(frame[field]) == expected, (key, j, field)
            assert np.array_equal([float(frame[n]) for n in COLUMNS], scan["raw"][j])
            predicted.append(float(frame["predicted_target"])/scan["scale"])
            residuals.append(float(frame["residual"])/scan["scale"])
        predicted, residuals = np.asarray(predicted), np.asarray(residuals)
        assert np.allclose(predicted, pred_ode, atol=1e-9, rtol=1e-9)
        assert np.allclose(residuals, predicted-norm_tar, atol=1e-12, rtol=1e-12)
        sse = float(residuals @ residuals)
        assert np.isclose(float(row["sse"])/scan["scale"]**2, sse, atol=1e-12, rtol=1e-12)
        assert np.isclose(float(row["rmse"])/scan["scale"], np.sqrt(sse/len(predicted)), atol=1e-12)
        assert np.isclose(float(row["normalized_rmse"]), np.sqrt(sse/len(predicted)), atol=1e-12)
        assert float(row["reference_scale"]) == scan["scale"]
        assert float(row["k2prime"]) == p[1]/p[0]
        eps = 1e-7*np.maximum(1., HIGH-LOW)
        assert json.loads(row["at_lower_bound"]) == (np.abs(p-LOW) <= eps).tolist()
        assert json.loads(row["at_upper_bound"]) == (np.abs(p-HIGH) <= eps).tolist()
        usable = [v for v in candidates[i] if v["success"]]
        selected = min(usable, key=lambda v: (v["normalized_sse"], v["start_index"]))
        assert int(row["selected_start_index"]) == selected["start_index"]
        assert np.array_equal(p, selected["params"])
        jac = matrix_jacobian(scan["mid"], norm_ref, p)
        sv = np.linalg.svd(jac, compute_uv=False)
        item = {"subject": key[0], "session": key[1], "n_frames": len(predicted),
                "duration_min": float(scan["end"][-1]/60),
                "max_normalized_prediction_error": float(max(abs(predicted-pred_ode))),
                "normalized_sse": sse, "params": p.tolist(),
                "successful_start_parameter_range": np.ptp([v["params"] for v in usable], axis=0).tolist(),
                "normalized_jacobian_singular_values": sv.tolist(),
                "normalized_jacobian_condition": float(sv[0]/sv[-1])}
        if alternate:
            def residual(par):
                return matrix_prediction(scan["mid"], norm_ref, par)-norm_tar
            fit = least_squares(residual, [1., .05, .5],
                                jac=lambda par: matrix_jacobian(scan["mid"], norm_ref, par),
                                bounds=(LOW, HIGH), method="dogbox", x_scale=1.,
                                ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=500)
            item["alternate_dogbox"] = {
                "status": int(fit.status), "nfev": int(fit.nfev),
                "success": bool(fit.success), "params": fit.x.tolist(),
                "parameter_difference": (fit.x-p).tolist(),
                "normalized_sse_difference": float(fit.fun @ fit.fun - sse),
                "max_normalized_prediction_difference": float(max(abs(residual(fit.x)+norm_tar-predicted))),
                "interpretation": "diagnostic_only_not_parameter_truth"}
        report.append(item)
    results = json.loads((out / "pet_results.json").read_text())
    pairs = {v["subject"]: v for v in results["per_subject"]}
    pcts = []
    for subject in ("sub-01", "sub-02"):
        b = float(params[(subject, "ses-baseline")]["BP_ND"])
        r = float(params[(subject, "ses-rescan")]["BP_ND"])
        mean = (b+r)/2
        pct = 100*abs(b-r)/mean if mean > 0 else None
        expected = {"subject": subject, "baseline_BP_ND": b, "rescan_BP_ND": r,
                    "absolute_difference": abs(b-r), "pair_mean": mean,
                    "test_retest_pct": pct,
                    "status": "ok" if pct is not None else "undefined_nonpositive_mean"}
        assert pairs[subject] == expected
        pcts.append(pct)
    headline = sum(pcts)/2 if all(v is not None for v in pcts) else None
    assert results["test_retest_pct"] == headline
    assert np.isclose(results["putamen_BP_ND_mean"],
                      sum(float(params[k]["BP_ND"]) for k in SCANS)/4, atol=1e-12, rtol=1e-12)
    assert results["n_defined_pairs"] == sum(v is not None for v in pcts)
    return {"status": "passed", "scope": "source and numerical computation, not biological truth",
            "source_sha256": {v["path"]: v["sha256"] for v in manifest["files"]},
            "n_frames": len(frames), "scans": report, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="/app/data/petref")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-alternate-fit", action="store_true")
    args = parser.parse_args()
    result = check(args.data_dir, args.output_dir, not args.skip_alternate_fit)
    Path(args.report).write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"], "n_frames": result["n_frames"]}))
