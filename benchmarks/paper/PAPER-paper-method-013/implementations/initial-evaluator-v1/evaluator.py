"""Post-assembly evaluator for the ten-recording DeepCaImX task.

This module performs no acquisition, model execution, reference construction or
scientific admission. See the paired documentation for the prospective conflict
resolution and aggregation policies.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "PAPER-paper-method-013"
RECORDINGS = {
    "501271265": 175, "501704220": 175, "524691284": 275,
    "531006860": 275, "603516552": 550, "604145810": 550,
    "607040613": 375, "669233895": 625, "671162628": 625,
    "679353932": 375,
}
FRAME_LABELS = [18501, 23500]
N_FRAMES = 5000
IMAGE_SHAPE = (488, 488)
POLICY_ID = "deepcaimx-assembled-prospective-v1"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_array(value: Any, name: str, ndim: int) -> np.ndarray:
    a = np.asarray(value)
    _require(a.ndim == ndim and a.dtype.kind in "biuf", f"{name}: numeric {ndim}D array required")
    _require(bool(np.isfinite(a).all()), f"{name}: nonfinite values")
    return a


def validate_masks(value: Any, name: str) -> np.ndarray:
    a = _finite_array(value, name, 3)
    _require(a.shape[1] > 0 and a.shape[2] > 0, f"{name}: empty image")
    _require(bool(((a == 0) | (a == 1)).all()), f"{name}: masks must be binary; threshold upstream")
    a = a.astype(bool, copy=False)
    _require(bool(a.any(axis=(1, 2)).all()), f"{name}: empty ROI")
    return a


def pairwise_iou(reference: Any, predicted: Any) -> np.ndarray:
    """Intersection over union on binary full-field footprints, including overlap."""
    r, p = validate_masks(reference, "reference masks"), validate_masks(predicted, "predicted masks")
    _require(r.shape[1:] == p.shape[1:], "reference and prediction image shapes differ")
    # Row-wise intersection avoids an N_reference x N_prediction x H x W tensor.
    areas_r = r.sum(axis=(1, 2), dtype=np.int64)
    areas_p = p.sum(axis=(1, 2), dtype=np.int64)
    result = np.zeros((len(r), len(p)), dtype=float)
    for i, mask in enumerate(r):
        intersection = np.count_nonzero(p & mask, axis=(1, 2))
        result[i] = intersection / (areas_r[i] + areas_p - intersection)
    return result


def match_iou(iou: Any) -> list[tuple[int, int, float]]:
    """Paper rule: each reference selects its highest IoU strictly above 0.5.

    A shared selected prediction has no resolved historical assignment in the
    inspected source and fails closed. Equal-IoU ties use the first declared
    prediction row as an explicit prospective rule, without inspecting traces.
    """
    a = _finite_array(iou, "IoU", 2).astype(float)
    _require(bool(((a >= 0) & (a <= 1)).all()), "IoU outside [0,1]")
    if not a.size:
        return []
    matches = []
    used = set()
    for i, row in enumerate(a):
        maximum = float(row.max())
        if maximum <= 0.5:
            continue
        choices = np.flatnonzero(row == maximum)
        j = int(choices[0])
        _require(j not in used, "ambiguous prediction selected by multiple reference ROIs: historical matching hold")
        used.add(j)
        matches.append((i, j, maximum))
    return matches


def _counts(tp: int, n_reference: int, n_predicted: int) -> dict[str, Any]:
    return {
        "true_positive": tp, "false_positive": n_predicted - tp,
        "false_negative": n_reference - tp,
        "reference_roi_count": n_reference, "predicted_roi_count": n_predicted,
        "precision": tp / n_predicted if n_predicted else 0.0,
        "recall": tp / n_reference if n_reference else None,
        "f1": 2 * tp / (n_reference + n_predicted) if n_reference + n_predicted else None,
    }


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    # Scaling first avoids overflow and preserves Pearson under positive scaling.
    sx, sy = float(np.max(np.abs(x))), float(np.max(np.abs(y)))
    if sx == 0 or sy == 0:
        return None
    x, y = x / sx, y / sy
    x, y = x - x.mean(), y - y.mean()
    dx, dy = float(np.linalg.norm(x)), float(np.linalg.norm(y))
    if dx == 0 or dy == 0:
        return None
    return float(np.clip(np.dot(x / dx, y / dy), -1, 1))


def score_recording(reference_masks: Any, predicted_masks: Any,
                    reference_traces: Any, predicted_traces: Any) -> dict[str, Any]:
    """Score final assembled masks and ROI-ordered unaltered fluorescence traces."""
    r = validate_masks(reference_masks, "reference masks")
    p = validate_masks(predicted_masks, "predicted masks")
    rt = _finite_array(reference_traces, "reference traces", 2).astype(float)
    pt = _finite_array(predicted_traces, "predicted traces", 2).astype(float)
    _require(len(r) > 0, "reference must contain at least one ROI")
    _require(rt.shape[0] == len(r) and pt.shape[0] == len(p), "ROI/trace row counts differ")
    _require(rt.shape[1] == pt.shape[1] and rt.shape[1] >= 2, "trace frame counts differ or are too short")
    matches = match_iou(pairwise_iou(r, p))
    pairs = []
    for i, j, overlap in matches:
        corr = _pearson(rt[i], pt[j])
        pairs.append({"reference_index": i, "prediction_index": j,
                      "iou": overlap, "pearson_r": corr,
                      "undefined_reason": "constant_trace" if corr is None else None})
    values = [v["pearson_r"] for v in pairs if v["pearson_r"] is not None]
    result = _counts(len(matches), len(r), len(p))
    result.update({"matches": pairs, "trace_defined_count": len(values),
                   "trace_undefined_count": len(matches) - len(values),
                   "trace_unmatched_reference_count": len(r) - len(matches),
                   "trace_mean_pearson_r": float(np.mean(values)) if values else None,
                   "trace_median_pearson_r": float(np.median(values)) if values else None,
                   "trace_evaluable_reference_fraction": len(values) / len(r)})
    return result


def tile_layout() -> list[dict[str, Any]]:
    """Paper geometry only: 9 x 9 x 13 padded 64 x 64 x 400 tiles.

    Rows advance first, as in the pinned MATLAB tailor. Valid ranges explicitly
    distinguish padding from the 488 x 488 x 5000 annotated field. This does not
    assert that generic tailor defaults reproduce the paper assembly pipeline.
    """
    tiles = []
    for t in range(13):
        for col in range(9):
            for row in range(9):
                starts = [row * 53, col * 53, t * 400]
                stops = [starts[0] + 64, starts[1] + 64, starts[2] + 400]
                tiles.append({"tile_index": len(tiles), "start_zero_based": starts,
                              "stop_exclusive": stops,
                              "valid_stop_exclusive": [min(stops[0], 488), min(stops[1], 488), min(stops[2], 5000)]})
    return tiles


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    """Parse and identify one captured manifest, without reopening its path."""
    def reject_constant(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out = {}
        for key, value in pairs:
            _require(key not in out, f"duplicate JSON key: {key}")
            out[key] = value
        return out
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant, object_pairs_hook=unique_keys)
    _require(isinstance(value, dict), "manifest must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    """Retain the existing parser interface for callers needing no digest."""
    return _json_snapshot(path)[0]


def _validate_common(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    _require(manifest.get("schema_version") == 1, "schema_version must be 1")
    _require(manifest.get("task_id") == TASK_ID, "wrong task_id")
    _require(manifest.get("frame_labels_inclusive") == FRAME_LABELS, "wrong annotated frame window")
    _require(manifest.get("frame_count") == N_FRAMES, "all 5000 frames are required")
    _require(manifest.get("image_shape") == list(IMAGE_SHAPE), "full 488x488 field required")
    _require(manifest.get("coordinate_system") == "zero_based_row_column", "coordinate system mismatch")
    rows = manifest.get("recordings")
    _require(isinstance(rows, list), "recordings must be a list")
    result = {}
    for row in rows:
        _require(isinstance(row, dict), "recording must be an object")
        rid = row.get("recording_id")
        _require(isinstance(rid, str) and rid in RECORDINGS, "unknown recording")
        _require(rid not in result, "duplicate recording")
        _require(row.get("depth_um") == RECORDINGS[rid], "depth mismatch")
        result[rid] = row
    _require(set(result) == set(RECORDINGS), "the exact ten-recording cohort is required")
    return result


def _load_arrays(row: dict[str, Any], manifest_path: Path) -> tuple[np.ndarray, np.ndarray]:
    _require(isinstance(row.get("array_file"), str), "array_file missing")
    path = (manifest_path.parent / row["array_file"]).resolve()
    _require(path.is_file(), "array_file does not exist")
    # Authenticate and decode the same snapshot. A pathname replacement after
    # capture cannot change the scored masks or traces. This binds content; it
    # does not establish filesystem/process isolation or authentic provenance.
    raw = path.read_bytes()
    _require(row.get("array_sha256") == hashlib.sha256(raw).hexdigest(), "array SHA256 mismatch")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        _require(set(archive.files) == {"masks", "traces"} and len(archive.files) == 2,
                 "NPZ must contain only masks and traces, without duplicate members")
        masks, traces = archive["masks"], archive["traces"]
    _require(masks.ndim == 3 and masks.shape[1:] == IMAGE_SHAPE, "wrong full-field mask shape")
    _require(traces.ndim == 2 and traces.shape[1] == N_FRAMES, "wrong full-window trace shape")
    return masks, traces


def _runtime_seconds(value: Any) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), "positive finite wall_seconds required")
    try:
        seconds = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("positive finite wall_seconds required") from exc
    _require(bool(np.isfinite(seconds)) and seconds > 0, "positive finite wall_seconds required")
    return seconds


def _runtime_ratio(numerator: float, denominator: float) -> float:
    ratio = numerator / denominator
    _require(bool(np.isfinite(ratio)) and ratio > 0, "runtime ratio outside positive finite numeric range")
    return ratio


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = _counts(sum(r["true_positive"] for r in rows),
                  sum(r["reference_roi_count"] for r in rows),
                  sum(r["predicted_roi_count"] for r in rows))
    out["recording_count"] = len(rows)
    out["macro_recording_f1"] = float(np.mean([r["f1"] for r in rows]))
    out["macro_recording_trace_mean_pearson_r"] = (
        float(np.mean([r["trace_mean_pearson_r"] for r in rows]))
        if all(r["trace_mean_pearson_r"] is not None for r in rows) else None)
    out["trace_defined_count"] = sum(r["trace_defined_count"] for r in rows)
    out["trace_undefined_count"] = sum(r["trace_undefined_count"] for r in rows)
    out["trace_unmatched_reference_count"] = sum(r["trace_unmatched_reference_count"] for r in rows)
    out["trace_evaluable_reference_fraction"] = out["trace_defined_count"] / out["reference_roi_count"]
    return out


def evaluate(reference_path: str | Path, submission_path: str | Path) -> dict[str, Any]:
    """Evaluate every declared method on the same separately supplied reference."""
    ref_path, sub_path = Path(reference_path), Path(submission_path)
    reference, reference_sha256 = _json_snapshot(ref_path)
    submission, submission_sha256 = _json_snapshot(sub_path)
    refs = _validate_common(reference)
    _require(reference.get("reference_kind") == "author_constructed_fluorescence", "only imaging-derived author reference is supported")
    _require(isinstance(reference.get("source_transformation_receipt"), str) and bool(reference["source_transformation_receipt"].strip()), "reference transformation receipt required")
    _require(submission.get("policy_id") == POLICY_ID, "prospective policy must be acknowledged")
    _require(submission.get("reference_manifest_sha256") == reference_sha256, "submission targets a different reference manifest")
    methods = submission.get("methods")
    _require(isinstance(methods, list) and len(methods) >= 2, "candidate and at least one baseline required")
    _require(all(isinstance(m, dict) for m in methods), "each method must be an object")
    _require(sum(m.get("role") == "candidate" for m in methods) == 1, "exactly one candidate required")
    names = set()
    results = []
    runtime_contract = None
    for method in methods:
        name = method.get("method_id")
        _require(isinstance(name, str) and bool(name.strip()) and name not in names, "method IDs must be nonempty and unique")
        names.add(name)
        _require(method.get("role") in {"candidate", "baseline"}, "method role invalid")
        _require(isinstance(method.get("implementation_identity"), str) and bool(method["implementation_identity"].strip()), "implementation/checkpoint identity required")
        rows = _validate_common(method)
        reports = []
        total_runtime = 0.0
        for rid in RECORDINGS:
            reference_arrays = _load_arrays(refs[rid], ref_path)
            prediction_arrays = _load_arrays(rows[rid], sub_path)
            report = score_recording(reference_arrays[0], prediction_arrays[0], reference_arrays[1], prediction_arrays[1])
            report.update({"recording_id": rid, "depth_um": RECORDINGS[rid]})
            runtime = rows[rid].get("runtime")
            _require(isinstance(runtime, dict), "runtime receipt required")
            seconds = _runtime_seconds(runtime.get("wall_seconds"))
            fields = [runtime.get(k) for k in ("hardware_id", "scope", "environment_id")]
            _require(all(isinstance(v, str) and v.strip() for v in fields), "runtime hardware, scope and environment required")
            if runtime_contract is None:
                runtime_contract = fields
            _require(runtime.get("scope") == "processing_excluding_data_loading_and_writing", "runtime scope must exclude loading and writing")
            _require(fields == runtime_contract, "runtime receipts must use identical hardware, timing scope and environment")
            report["runtime_wall_seconds"] = float(seconds)
            total_runtime += seconds
            _require(bool(np.isfinite(total_runtime)), "total runtime outside finite numeric range")
            reports.append(report)
        results.append({"method_id": name, "role": method["role"],
                        "implementation_identity": method["implementation_identity"],
                        "recordings": reports, "pooled_roi_counts": _aggregate(reports),
                        "by_depth_um": {str(depth): _aggregate([r for r in reports if r["depth_um"] == depth]) for depth in sorted(set(RECORDINGS.values()))},
                        "total_runtime_wall_seconds": total_runtime})
    # The paper compares traces only for reference ROIs detected by every method.
    # Per-method matched-set summaries above are diagnostic, never this endpoint.
    common_trace = []
    for index, rid in enumerate(RECORDINGS):
        maps = {r["method_id"]: {p["reference_index"]: p["pearson_r"] for p in r["recordings"][index]["matches"]} for r in results}
        common = sorted(set.intersection(*(set(m) for m in maps.values())))
        common_trace.append({"recording_id": rid, "depth_um": RECORDINGS[rid],
            "common_detected_reference_indices": common,
            "common_detected_reference_count": len(common),
            "reference_roi_count": results[0]["recordings"][index]["reference_roi_count"],
            "methods": {name: {"pearson_by_reference": {str(i): values[i] for i in common},
                "defined_count": sum(values[i] is not None for i in common),
                "mean_pearson_r": float(np.mean([values[i] for i in common])) if common and all(values[i] is not None for i in common) else None}
                for name, values in maps.items()}})
    candidate = next(r for r in results if r["role"] == "candidate")
    comparisons = []
    for baseline in (r for r in results if r["role"] == "baseline"):
        paired = []
        for c, b, common in zip(candidate["recordings"], baseline["recordings"], common_trace):
            cv = common["methods"][candidate["method_id"]]["mean_pearson_r"]
            bv = common["methods"][baseline["method_id"]]["mean_pearson_r"]
            paired.append({"recording_id": c["recording_id"], "f1_delta": c["f1"] - b["f1"],
                           "common_detected_reference_count": common["common_detected_reference_count"],
                           "common_reference_mean_pearson_r_delta": cv - bv if cv is not None and bv is not None else None,
                           "baseline_over_candidate_runtime": _runtime_ratio(b["runtime_wall_seconds"], c["runtime_wall_seconds"])})
        comparisons.append({"baseline_id": baseline["method_id"], "paired_recordings": paired,
                            "baseline_over_candidate_total_runtime": _runtime_ratio(baseline["total_runtime_wall_seconds"], candidate["total_runtime_wall_seconds"])})
    return {"task_id": TASK_ID, "policy_id": POLICY_ID, "scientific_qualification": "unknown",
            "scope": "post_assembly_offline_metrics", "reference_kind": reference["reference_kind"],
            "reference_manifest_sha256": reference_sha256, "submission_manifest_sha256": submission_sha256,
            "runtime_contract": dict(zip(("hardware_id", "scope", "environment_id"), runtime_contract)),
            "methods": results, "all_method_common_reference_trace_endpoint": common_trace, "paired_comparisons": comparisons,
            "holds": ["authentic_reference_and_native_execution_unverified", "source_frame_index_mapping_and_patch_merge_unverified", "donor_identity_and_tuning_exposure_unverified", "rights_and_equal_resource_admission_unverified", "prospective_aggregation_not_historical_reproduction"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    score = commands.add_parser("score")
    score.add_argument("--reference", required=True)
    score.add_argument("--submission", required=True)
    score.add_argument("--output", required=True)
    layout = commands.add_parser("tile-layout")
    layout.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = evaluate(args.reference, args.submission) if args.command == "score" else {"geometry_only": True, "tiles": tile_layout()}
        output = Path(args.output)
        if args.command == "score":
            _require(output.resolve() not in {Path(args.reference).resolve(), Path(args.submission).resolve()}, "output would overwrite a manifest")
        with output.open("x") as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"evaluation failed: {exc}\n")


if __name__ == "__main__":
    main()
