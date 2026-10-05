"""Offline fixed-window simplified-reference Logan descriptors, not kinetic truth.

All estimator choices and missing-value rules are in the frozen public contract.
Importing this module reads no source, fits nothing and writes nothing.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np

TASK_ID = "PETDVR-001"
PIPELINE_ID = "petdvr-fixed-window-reference-logan-v2"
METHOD_SHA256 = "f82719c34120a87a0a2143294a45e1f9db115a7f83afe40d0168e13e4dab3d69"
SOURCE_SHA256 = "9ca371309a1a5b5e8ebbc80b5c40d1b766bff666774b9f243f6cc27ca1def6a6"
SCANS = [(s, e) for s in ("sub-01", "sub-02") for e in ("ses-baseline", "ses-rescan")]
TARGETS = ["highbinding", "left_thalamus", "right_thalamus", "left_caudate",
           "right_caudate", "left_putamen", "right_putamen"]
STARTS = [0, 10, 20, 30, 40]
ENDS = ["native", "common50"]


def finite(value, name):
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"Nonfinite {name}")
    return array


def scalar(value, name="arithmetic result"):
    return float(finite(value, name))


def parse_tsv(content):
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    columns = reader.fieldnames
    required = ["frame_start", "frame_end", "reference", *TARGETS]
    if not columns or len(columns) != len(set(columns)) or not set(required) <= set(columns):
        raise ValueError("Missing or duplicate original TAC columns")
    rows = list(reader)
    if not rows or any(None in row or any(row[k] is None for k in columns) for row in rows):
        raise ValueError("Empty or malformed original TAC rows")
    data = {name: finite([float(row[name]) for row in rows], name) for name in required}
    return columns, data


def validate_timing(data, sidecar):
    start, end = data["frame_start"], data["frame_end"]
    duration = finite(sidecar["FrameDuration"], "FrameDuration")
    official_start = finite(sidecar["FrameTimesStart"], "FrameTimesStart")
    if (start.ndim != 1 or not len(start) or start.shape != end.shape
            or duration.shape != start.shape or official_start.shape != start.shape):
        raise ValueError("Source frame dimensions disagree")
    if (np.any(duration <= 0) or np.any(end <= start) or start[0] != 0
            or not np.allclose(start, official_start, atol=1e-9, rtol=0)
            or not np.allclose(end, official_start+duration, atol=1e-9, rtol=0)
            or not np.allclose(start[1:], end[:-1], atol=1e-9, rtol=0)):
        raise ValueError("Source timing must be origin-zero, positive and contiguous")
    if (sidecar.get("ScanStart") != 0 or sidecar.get("InjectionStart") != 0
            or sidecar.get("ImageDecayCorrected") is not True
            or sidecar.get("ImageDecayCorrectionTime") != 0 or sidecar.get("Units") != "Bq/mL"):
        raise ValueError("Unexpected acquisition/injection/decay/unit metadata")
    return (start+end)/2


def resolve_stager_path(module_path=None, build_path=Path("/opt/source/stage_data.py")):
    """The native task mount and Harbor solution copy have different layouts."""
    module_path = Path(__file__ if module_path is None else module_path)
    local = module_path.resolve().parents[1]/"environment"/"stage_data.py"
    for candidate in (local, Path(build_path)):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise ValueError("Offline source-verification helper is missing")


def load_inputs(source_dir, method_contract_path, pilot=False):
    """Verify all original files before reading any required concentration values."""
    method_path = Path(method_contract_path)
    if method_path.is_symlink() or not method_path.is_file():
        raise ValueError("Method contract must be a regular file")
    method_bytes = method_path.read_bytes()
    if hashlib.sha256(method_bytes).hexdigest() != METHOD_SHA256:
        raise ValueError("Frozen public method checksum mismatch")
    method = json.loads(method_bytes)
    stager_path = resolve_stager_path()
    spec = importlib.util.spec_from_file_location("petdvr_source_stager", stager_path)
    stager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stager)
    manifest = stager.verify_staged(source_dir)
    root = Path(source_dir)
    if hashlib.sha256((root/"source_manifest.json").read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source manifest identity mismatch")
    by_role = {(r.get("subject"), r.get("session"), r["role"]): r for r in manifest["files"]}
    scans, observed = [], []
    for subject, session in (SCANS[:1] if pilot else SCANS):
        tac = by_role[subject, session, "tac"]
        pet = by_role[subject, session, "pet_metadata"]
        columns, data = parse_tsv((root/tac["path"]).read_text())
        sidecar = json.loads((root/pet["path"]).read_text())
        midpoint = validate_timing(data, sidecar)
        expected_n = 32 if (subject, session) == SCANS[0] else 36
        if len(midpoint) != expected_n:
            raise ValueError("Frozen scan frame count changed")
        common = data["frame_end"] <= 3000
        scans.append(dict(subject=subject, session=session, data=data, midpoint=midpoint))
        observed.append(dict(subject=subject, session=session, tac_path=tac["path"],
            pet_metadata_path=pet["path"], n_frames=len(midpoint), tac_columns=columns,
            source_time_unit="s", analysis_time_unit="min", activity_unit="Bq/mL",
            activity_unit_evidence="raw_pet_sidecar_and_derivative_lineage_not_TAC_specific_sidecar",
            scan_start_s=sidecar["ScanStart"], injection_start_s=sidecar["InjectionStart"],
            image_decay_corrected=sidecar["ImageDecayCorrected"],
            image_decay_correction_time_s=sidecar["ImageDecayCorrectionTime"],
            native_end_s=float(data["frame_end"][-1]),
            common50_actual_end_s=float(data["frame_end"][common][-1]),
            first_frame_start_s=float(data["frame_start"][0]), frames_contiguous=True))
    return dict(method=method, manifest=manifest, scans=scans,
                observed=observed, targets=TARGETS[:1] if pilot else TARGETS,
                status="resource_pilot" if pilot else "ok")


def midpoint_integral(values, start_s, end_s):
    values = finite(values, "concentrations")
    duration_min = (finite(end_s, "end")-finite(start_s, "start"))/60
    if values.shape != duration_min.shape or values.ndim != 1 or np.any(duration_min <= 0):
        raise ValueError("Invalid integral input shape or duration")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        area = values*duration_min
        previous = np.concatenate(([0.0], np.cumsum(area[:-1], dtype=np.float64)))
        return finite(previous+0.5*area, "midpoint integral")


def make_graph(data, target):
    ct, cr = data[target], data["reference"]
    it = midpoint_integral(ct, data["frame_start"], data["frame_end"])
    ir = midpoint_integral(cr, data["frame_start"], data["frame_end"])
    valid, ratio_valid = ct != 0, cr != 0
    x, y, tr, rt = [np.full(len(ct), np.nan) for _ in range(4)]
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        x[valid], y[valid] = ir[valid]/ct[valid], it[valid]/ct[valid]
        rt[valid], tr[ratio_valid] = cr[valid]/ct[valid], ct[ratio_valid]/cr[ratio_valid]
    for name, values, mask in (("x", x, valid), ("y", y, valid),
                                ("reference/target", rt, valid), ("target/reference", tr, ratio_valid)):
        finite(values[mask], name)
    return dict(it=it, ir=ir, x=x, y=y, tr=tr, rt=rt, valid=valid, ratio_valid=ratio_valid)


def centered_ols(x, y):
    x, y = finite(x, "OLS x"), finite(y, "OLS y")
    if x.ndim != 1 or y.shape != x.shape:
        raise ValueError("OLS vector shape mismatch")
    result = dict(fit_status="insufficient_frames", Sxx_min2=None, Sxy_min2=None,
        Syy_min2=None, rank_threshold_min2=None, logan_slope=None, intercept_min=None,
        sse_min2=None, rmse_min=None, r_squared=None, r_squared_status="fit_unavailable")
    prediction = None
    if len(x) == 0:
        return result, prediction
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        # Preserve the exact constant-vector case despite mean-rounding artifacts.
        xbar = x[0] if np.all(x == x[0]) else np.mean(x)
        ybar = y[0] if np.all(y == y[0]) else np.mean(y)
        dx, dy = x-xbar, y-ybar
        xx, xy, yy = np.sum(dx*dx), np.sum(dx*dy), np.sum(dy*dy)
        threshold = 1e-24*max(1.0, scalar(np.sum(x*x)))
        result.update(Sxx_min2=scalar(xx), Sxy_min2=scalar(xy),
                      Syy_min2=scalar(yy), rank_threshold_min2=scalar(threshold))
        if len(x) < 3:
            return result, prediction
        if xx <= threshold:
            result["fit_status"] = "rank_deficient_under_public_rule"
            return result, prediction
        slope = xy/xx
        intercept = ybar-slope*xbar
        prediction = finite(slope*x+intercept, "OLS prediction")
        residual = prediction-y
        sse = np.sum(residual*residual)
        result.update(fit_status="ok", logan_slope=scalar(slope), intercept_min=scalar(intercept),
            sse_min2=scalar(sse), rmse_min=scalar(np.sqrt(sse/len(x))),
            r_squared=None if yy == 0 else scalar(1-sse/yy),
            r_squared_status="constant_y" if yy == 0 else "ok")
    return result, prediction


def ratio_diagnostics(ratio, midpoint_min):
    ratio, times = finite(ratio, "ratios"), finite(midpoint_min, "ratio times")
    if ratio.ndim != 1 or ratio.shape != times.shape:
        raise ValueError("Ratio/time shape mismatch")
    result = dict(ratio_mean=None, ratio_min=None, ratio_max=None, ratio_population_sd=None,
        ratio_cv=None, ratio_cv_status="no_valid_ratio", ratio_time_slope_per_min=None,
        ratio_trend_status="no_valid_ratio")
    if not len(ratio):
        return result
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        mean = np.mean(ratio)
        sd = np.sqrt(np.mean((ratio-mean)**2))
        result.update(ratio_mean=scalar(mean), ratio_min=scalar(np.min(ratio)),
            ratio_max=scalar(np.max(ratio)), ratio_population_sd=scalar(sd),
            ratio_cv=None if mean == 0 else scalar(sd/abs(mean)),
            ratio_cv_status="zero_mean" if mean == 0 else "ok",
            ratio_trend_status="insufficient_distinct_times")
        if len(ratio) >= 2:
            dt = times-np.mean(times)
            xx = scalar(np.sum(dt*dt))
            if xx > 0:
                result.update(ratio_time_slope_per_min=scalar(np.sum(dt*(ratio-mean))/xx),
                              ratio_trend_status="ok")
    return result


def analyze_scan(scan, targets):
    subject, session, data = scan["subject"], scan["session"], scan["data"]
    midpoint = scan["midpoint"]
    frames, graphs, fits, points = [], [], [], []
    for i in range(len(midpoint)):
        row = dict(subject=subject, session=session, frame_index=i,
            frame_start_s=float(data["frame_start"][i]), frame_end_s=float(data["frame_end"][i]),
            frame_duration_s=float(data["frame_end"][i]-data["frame_start"][i]), frame_mid_s=float(midpoint[i]))
        row.update({name: float(data[name][i]) for name in ["reference", *TARGETS]})
        frames.append(row)
    for target in targets:
        g = make_graph(data, target)
        identity = dict(subject=subject, session=session, target=target)
        for i in range(len(midpoint)):
            graphs.append(dict(**identity, frame_index=i,
                integral_target_bq_min_per_ml=float(g["it"][i]), integral_reference_bq_min_per_ml=float(g["ir"][i]),
                x_min=float(g["x"][i]) if g["valid"][i] else None,
                y_min=float(g["y"][i]) if g["valid"][i] else None,
                graph_status="ok" if g["valid"][i] else "zero_target",
                target_over_reference=float(g["tr"][i]) if g["ratio_valid"][i] else None,
                ratio_status="ok" if g["ratio_valid"][i] else "zero_reference",
                reference_over_target=float(g["rt"][i]) if g["valid"][i] else None))
        for end_policy in ENDS:
            end = float(data["frame_end"][-1]) if end_policy == "native" else 3000.0
            for start in STARTS:
                window = (midpoint >= 60*start) & (data["frame_end"] <= end)
                eligible = window & g["valid"]
                ratio_mask = window & g["ratio_valid"]
                idx, fidx = np.flatnonzero(window), np.flatnonzero(eligible)
                numeric, pred = centered_ols(g["x"][eligible], g["y"][eligible])
                key = dict(**identity, end_policy=end_policy, start_min=start)
                row = dict(**key, requested_end_s=end, n_window=len(idx), n_fit=len(fidx), n_ratio=int(ratio_mask.sum()),
                    first_window_frame=int(idx[0]) if len(idx) else None,
                    last_window_frame=int(idx[-1]) if len(idx) else None,
                    first_fit_frame=int(fidx[0]) if len(fidx) else None,
                    last_fit_frame=int(fidx[-1]) if len(fidx) else None,
                    actual_window_start_s=float(data["frame_start"][idx[0]]) if len(idx) else None,
                    actual_window_end_s=float(data["frame_end"][idx[-1]]) if len(idx) else None,
                    actual_fit_first_mid_s=float(midpoint[fidx[0]]) if len(fidx) else None,
                    actual_fit_last_mid_s=float(midpoint[fidx[-1]]) if len(fidx) else None, **numeric)
                row.update(ratio_diagnostics(g["tr"][ratio_mask], midpoint[ratio_mask]/60))
                fits.append(row)
                predictions = {} if pred is None else dict(zip(fidx, pred))
                for i in idx:
                    used = i in predictions
                    points.append(dict(**key, frame_index=int(i), graph_valid=bool(g["valid"][i]), in_fit=used,
                        point_status="zero_target" if not g["valid"][i] else "used" if used else "fit_unavailable",
                        predicted_y_min=float(predictions[i]) if used else None,
                        residual_y_min=float(predictions[i]-g["y"][i]) if used else None))
    return frames, graphs, fits, points


def make_summary(fits, targets, scans, status="ok"):
    lookup = {(r["subject"], r["session"], r["target"], r["end_policy"], r["start_min"]): r for r in fits}
    subjects = sorted({s for s, _ in scans})
    pairs, groups = [], []
    for target in targets:
        for end in ENDS:
            for start in STARTS:
                cell_pairs = []
                for subject in subjects:
                    rows = [lookup.get((subject, session, target, end, start)) for session in ("ses-baseline", "ses-rescan")]
                    statuses = [r["fit_status"] if r else "not_in_pilot" for r in rows]
                    slopes = [r["logan_slope"] if r else None for r in rows]
                    valid = all(s == "ok" for s in statuses)
                    pair = dict(subject=subject, target=target, end_policy=end, start_min=start,
                        baseline_fit_status=statuses[0], rescan_fit_status=statuses[1],
                        baseline_slope=slopes[0], rescan_slope=slopes[1],
                        rescan_minus_baseline=scalar(slopes[1]-slopes[0]) if valid else None,
                        pair_status="ok" if valid else "incomplete_pair")
                    pairs.append(pair)
                    cell_pairs.append(pair)
                valid_rows = [lookup[s, e, target, end, start] for s, e in scans
                              if lookup[s, e, target, end, start]["fit_status"] == "ok"]
                valid_pairs = [r for r in cell_pairs if r["pair_status"] == "ok"]
                represented = sorted({r["subject"] for r in valid_rows})
                groups.append(dict(target=target, end_policy=end, start_min=start,
                    n_expected_scans=4, n_expected_subjects=2, n_defined_scans=len(valid_rows),
                    defined_scans=[[r["subject"], r["session"]] for r in valid_rows],
                    n_represented_subjects=len(represented), represented_subjects=represented,
                    mean_logan_slope=scalar(np.mean([r["logan_slope"] for r in valid_rows])) if valid_rows else None,
                    n_defined_pairs=len(valid_pairs), defined_pair_subjects=[r["subject"] for r in valid_pairs],
                    mean_rescan_minus_baseline=scalar(np.mean([r["rescan_minus_baseline"] for r in valid_pairs])) if valid_pairs else None))
    return dict(status=status, task_id=TASK_ID, pipeline_id=PIPELINE_ID, n_scans=len(scans),
                n_subjects=len(subjects), targets=targets, start_min=STARTS, end_policies=ENDS,
                paired_changes=pairs, group_windows=groups)


def make_metadata(inputs):
    return dict(status=inputs["status"], task_id=TASK_ID, pipeline_id=PIPELINE_ID,
        source_manifest_sha256=SOURCE_SHA256, method_contract_sha256=METHOD_SHA256,
        source_sha256={r["path"]: r["sha256"] for r in inputs["manifest"]["files"]},
        method_contract=inputs["method"], source_observed={"scans": inputs["observed"]},
        software_versions={"python": platform.python_version(), "numpy": np.__version__})


def prepare_destinations(output_dir, private_dir):
    paths = [Path(output_dir).absolute(), Path(private_dir).absolute()]
    if paths[0] == paths[1] or paths[0] in paths[1].parents or paths[1] in paths[0].parents:
        raise ValueError("Public and private directories must be separate")
    for path in paths:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("Symlink output directory")
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise FileExistsError(f"Refusing existing evidence: {path}")
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run(inputs, output_dir, private_dir):
    tables = [[], [], [], []]
    for scan in inputs["scans"]:
        for table, new in zip(tables, analyze_scan(scan, inputs["targets"])):
            table.extend(new)
    if inputs["status"] == "ok" and [len(t) for t in tables] != [140, 980, 280, 3584]:
        raise ValueError("Full source/grid coverage differs from frozen timing contract")
    scan_keys = [(s["subject"], s["session"]) for s in inputs["scans"]]
    summary = make_summary(tables[2], inputs["targets"], scan_keys, inputs["status"])
    metadata = make_metadata(inputs)
    out, private = Path(output_dir), Path(private_dir)
    names = ["source_frames.csv", "graph_points.csv", "window_fits.csv", "fit_points.csv"]
    for name, rows in zip(names, tables):
        with (out/name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=inputs["method"]["outputs"][name])
            writer.writeheader()
            writer.writerows(rows)
    write_json(out/"summary.json", summary)
    write_json(out/"run_metadata.json", metadata)
    statuses = {s: sum(r["fit_status"] == s for r in tables[2]) for s in inputs["method"]["fit_statuses"]}
    with (out/"findings.md").open("x") as stream:
        stream.write("# Fixed-window reference-Logan sensitivity\n\n"
            f"Status: {inputs['status']}. {len(scan_keys)} scans from {summary['n_subjects']} participants; "
            f"{len(tables[2])} predeclared window/target fits: {statuses}.\n\n"
            "The complete fixed grid, signed baseline/rescan differences and available-scan descriptive means are in the tables and summary. "
            "Undefined windows are retained, including the two-frame common50/start40 windows; no fallback or favorable window was selected.\n\n"
            "These are simplified-reference Logan slopes on supplied PETPrep derivatives, not validated DASB DVR or kinetic truth. "
            "Both concentration-ratio diagnostics and linearity are descriptive; neither establishes omitted-efflux assumptions or reference-region validity. "
            "Native scan durations differ, and common50 is a complete-frame upper limit with unequal effective final support. "
            "The full four scans are repeated observations of two participants, not four independent subjects. "
            "Source extraction, corrections and the highbinding composite are inherited, not rerun or biologically validated.\n")
        stream.write("\nHighbinding fixed-grid descriptive means (all declared windows, no preferred window):\n\n"
                     "| End policy | Start (min) | Defined scans | Mean Logan slope |\n"
                     "| --- | ---: | ---: | ---: |\n")
        for row in summary["group_windows"]:
            if row["target"] == "highbinding":
                value = "undefined" if row["mean_logan_slope"] is None else format(row["mean_logan_slope"], ".9g")
                stream.write(f"| {row['end_policy']} | {row['start_min']} | {row['n_defined_scans']} | {value} |\n")
        stream.write("\nActual acquisition / last complete common50 frame ends (minutes):\n\n")
        for observed in inputs["observed"]:
            stream.write(f"- {observed['subject']} {observed['session']}: native "
                         f"{observed['native_end_s']/60:g}; common50 "
                         f"{observed['common50_actual_end_s']/60:g}.\n")
    arrays = {name.replace(".csv", "_json"): np.array(json.dumps(rows, allow_nan=False)) for name, rows in zip(names, tables)}
    arrays.update(metadata_json=np.array(json.dumps(metadata, allow_nan=False)),
                  summary_json=np.array(json.dumps(summary, allow_nan=False)))
    for scan in inputs["scans"]:
        prefix = scan["subject"]+"_"+scan["session"]
        arrays[prefix+"_source_columns"] = np.array(list(scan["data"]))
        arrays[prefix+"_source_values"] = np.column_stack(list(scan["data"].values()))
    with (private/"analysis_arrays.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return summary, statuses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=os.environ.get("SOURCE_DIR", "/app/data/petdvr"))
    parser.add_argument("--method-contract", default=os.environ.get("METHOD_CONTRACT", "/app/method_contract.json"))
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    parser.add_argument("--private-dir", default=os.environ.get("PRIVATE_DIR", "/app/oracle_private"))
    parser.add_argument("--pilot", action="store_true", help="Only first scan/highbinding; never a complete valid submission")
    args = parser.parse_args(argv)
    try:
        out, private = prepare_destinations(args.output_dir, args.private_dir)
    except (ValueError, OSError) as exc:
        print(f"Refusing output: {exc}", file=sys.stderr)
        return 1
    try:
        inputs = load_inputs(args.source_dir, args.method_contract, args.pilot)
        _, statuses = run(inputs, out, private)
    except Exception as exc:
        failure = dict(status="failed_precondition", task_id=TASK_ID, pipeline_id=PIPELINE_ID,
                       reason=f"{type(exc).__name__}: {exc}")
        for name in ("summary.json", "run_metadata.json"):
            if not (out/name).exists():
                write_json(out/name, failure)
        if not (out/"findings.md").exists():
            with (out/"findings.md").open("x") as stream:
                stream.write("# Failed precondition\n\n"+failure["reason"]+"\n")
        print(failure["reason"], file=sys.stderr)
        return 1
    print(json.dumps(dict(status=inputs["status"], fit_status_counts=statuses), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
