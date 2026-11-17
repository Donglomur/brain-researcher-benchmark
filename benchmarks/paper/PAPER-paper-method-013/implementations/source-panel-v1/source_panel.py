"""Convert the author's manual ROIs and score the complete segmentation panel.

This operator-side utility authenticates the manual masks, not the source movies,
model checkpoint or historical assembly. It reuses the retained evaluator's IoU
and matching kernels. No trace target or invented runtime is needed to measure
the segmentation endpoint alone.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "deepcaimx_retained_evaluator", HERE.parent / "initial-evaluator-v1/evaluator.py")
assert _SPEC is not None and _SPEC.loader is not None
LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LEGACY)

TASK_ID = LEGACY.TASK_ID
RECORDINGS = LEGACY.RECORDINGS
IMAGE_SHAPE = LEGACY.IMAGE_SHAPE
FRAME_LABELS = LEGACY.FRAME_LABELS
AUTHOR_REVISION = "305a4827929b2c6e82e44c5c69b2ea9d410e20a4"
REFERENCE_SCHEMA = "deepcaimx-roi-reference/v1"
PREDICTION_SCHEMA = "deepcaimx-segmentation-predictions/v1"
POLICY_ID = LEGACY.POLICY_ID
CONVERSION = "MATLAB_seg_row_column_roi_to_numpy_roi_row_column_without_spatial_transform"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return LEGACY._sha256(path)


def git_blob_sha1(body: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return LEGACY._read_json(path)


def source_pins() -> dict[str, dict[str, Any]]:
    pins = read_json(HERE / "roi_sources.json")
    _require(pins["author_revision"] == AUTHOR_REVISION, "wrong author source revision")
    rows = pins["recordings"]
    _require(set(rows) == set(RECORDINGS), "source pins require all ten original recordings")
    return rows


def authenticated_source(source_root: Path, rid: str,
                         pins: dict[str, dict[str, Any]]) -> tuple[bytes, dict[str, Any]]:
    """Capture and authenticate bytes before MAT parsing; filenames are not proof."""
    pin = pins[rid]
    path = source_root / pin["path"]
    _require(path.is_file(), f"{rid}: source MAT missing")
    _require(path.stat().st_size == pin["bytes"], f"{rid}: source MAT size mismatch")
    body = path.read_bytes()
    _require(len(body) == pin["bytes"], f"{rid}: source MAT changed while reading")
    _require(git_blob_sha1(body) == pin["git_blob_sha1"], f"{rid}: source Git blob mismatch")
    digest = hashlib.sha256(body).hexdigest()
    _require(digest == pin["sha256"], f"{rid}: source SHA256 mismatch")
    return body, {"source_path": pin["path"], "source_bytes": len(body),
                  "source_git_blob_sha1": pin["git_blob_sha1"],
                  "source_sha256": digest}


def manual_seg_to_masks(seg: Any) -> np.ndarray:
    """Preserve row/column orientation and every author ROI; do not resize/crop."""
    array = np.asarray(seg)
    _require(array.ndim == 3, "MAT seg must have row, column, ROI axes")
    _require(array.shape[2] > 0, "MAT seg must contain at least one reference ROI")
    return LEGACY.validate_masks(np.moveaxis(array, 2, 0), "author seg")


def decode_mat(body: bytes) -> np.ndarray:
    from scipy.io import loadmat

    # The pinned author files are ordinary MATLAB v5 MAT files, not MATLAB v7.3
    # HDF files; scipy preserves axis order rather than inferring a transpose.
    values = loadmat(io.BytesIO(body), variable_names=["seg"])
    _require("seg" in values, "MAT seg variable missing")
    masks = manual_seg_to_masks(values["seg"])
    _require(masks.shape[1:] == IMAGE_SHAPE, "author seg must cover the 488x488 field")
    return masks


def _common(schema: str) -> dict[str, Any]:
    return {"schema": schema, "task_id": TASK_ID,
            "frame_labels_inclusive": FRAME_LABELS, "image_shape": list(IMAGE_SHAPE),
            "coordinate_system": "zero_based_row_column"}


def convert_panel(source_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Create a complete reference cache; input/output targets stay operator-owned.

    ``source_root`` is an external checkout/extraction root containing the pinned
    ``Manually Labelled ROIs/ABO`` paths. All ten source identities are checked
    before creating an output directory. ``reference.json`` is written last.
    """
    source_root, output_dir = Path(source_root), Path(output_dir)
    pins = source_pins()
    captured = {rid: authenticated_source(source_root, rid, pins) for rid in RECORDINGS}
    _require(not output_dir.exists(), "output directory already exists")
    output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for rid, depth in RECORDINGS.items():
        body, identity = captured[rid]
        masks = decode_mat(body)
        name = f"{rid}.masks.npy"
        with (output_dir / name).open("xb") as stream:
            np.save(stream, masks, allow_pickle=False)
        rows.append({"recording_id": rid, "depth_um": depth, "mask_file": name,
                     "mask_sha256": sha256(output_dir / name), "roi_count": len(masks),
                     **identity})
    manifest = {**_common(REFERENCE_SCHEMA), "author_revision": AUTHOR_REVISION,
                "conversion": CONVERSION,
                "frame_index_semantics": "author_filename_labels_not_verified_movie_indices",
                "movie_identity_verified": False, "recordings": rows}
    with (output_dir / "reference.json").open("x") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return manifest


def _roster(manifest: dict[str, Any], schema: str) -> dict[str, dict[str, Any]]:
    for key, expected in _common(schema).items():
        _require(manifest.get(key) == expected, f"{key} mismatch")
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
    _require(set(result) == set(RECORDINGS), "exact ten-video original panel required")
    return result


def _load_masks(row: dict[str, Any], manifest_path: Path) -> np.ndarray:
    filename = row.get("mask_file")
    _require(isinstance(filename, str) and bool(filename), "mask_file missing")
    path = manifest_path.parent / filename
    _require(path.is_file(), "mask_file missing")
    _require(sha256(path) == row.get("mask_sha256"), "mask SHA256 mismatch")
    masks = np.load(path, mmap_mode="r", allow_pickle=False)
    _require(isinstance(masks, np.ndarray), "masks must be a standalone NPY array")
    _require(masks.ndim == 3 and masks.shape[1:] == IMAGE_SHAPE,
             "masks must use ROI,row,column axes and the 488x488 field")
    return LEGACY.validate_masks(masks, "masks")


def score_masks(reference: Any, predicted: Any) -> dict[str, Any]:
    """Retained strict-IoU matching and counts; no trace-derived matching."""
    reference = LEGACY.validate_masks(reference, "reference")
    predicted = LEGACY.validate_masks(predicted, "predicted")
    _require(len(reference) > 0, "reference cannot be empty")
    matches = LEGACY.match_iou(LEGACY.pairwise_iou(reference, predicted))
    return LEGACY._counts(len(matches), len(reference), len(predicted))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _require(len(rows) > 1, "at least two videos required for sample SD")
    result = {"video_count": len(rows)}
    for metric in ("precision", "recall", "f1"):
        values = [row[metric] for row in rows]
        result[metric] = {"macro_video_mean": float(np.mean(values)),
                          "population_sd_ddof0": float(np.std(values, ddof=0)),
                          "sample_sd_ddof1": float(np.std(values, ddof=1))}
    result["published_sd_convention"] = "unresolved; both conventions reported"
    result["pooled_roi_counts_diagnostic"] = LEGACY._counts(
        sum(row["true_positive"] for row in rows),
        sum(row["reference_roi_count"] for row in rows),
        sum(row["predicted_roi_count"] for row in rows))
    return result


def score_panel(reference_path: str | Path, prediction_path: str | Path,
                source_root: str | Path) -> dict[str, Any]:
    """Score one complete method against reauthenticated manual source masks.

    Re-converting original MAT bytes verifies that a self-declared hash in a
    cache manifest cannot substitute different target masks. This is a metric
    calculation, not authentication of the movie, predictions or full model.
    """
    reference_path, prediction_path = Path(reference_path), Path(prediction_path)
    reference, prediction = read_json(reference_path), read_json(prediction_path)
    refs = _roster(reference, REFERENCE_SCHEMA)
    preds = _roster(prediction, PREDICTION_SCHEMA)
    _require(reference.get("author_revision") == AUTHOR_REVISION, "wrong author revision")
    _require(reference.get("conversion") == CONVERSION, "wrong manual ROI conversion")
    _require(prediction.get("policy_id") == POLICY_ID, "matching policy acknowledgement required")
    _require(prediction.get("reference_manifest_sha256") == sha256(reference_path),
             "prediction targets another reference manifest")
    for key in ("method_id", "implementation_identity"):
        _require(isinstance(prediction.get(key), str) and bool(prediction[key].strip()),
                 f"{key} required")
    pins = source_pins()
    rows = []
    for rid, depth in RECORDINGS.items():
        body, identity = authenticated_source(Path(source_root), rid, pins)
        for key, value in identity.items():
            _require(refs[rid].get(key) == value, f"{rid}: reference source identity mismatch")
        reference_masks = decode_mat(body)
        cached_masks = _load_masks(refs[rid], reference_path)
        _require(np.array_equal(reference_masks, cached_masks), f"{rid}: converted masks differ from source")
        _require(refs[rid].get("roi_count") == len(reference_masks), "reference ROI count mismatch")
        del cached_masks
        predicted_masks = _load_masks(preds[rid], prediction_path)
        rows.append({"recording_id": rid, "depth_um": depth,
                     **score_masks(reference_masks, predicted_masks)})
    return {"schema": "deepcaimx-segmentation-score/v1", "task_id": TASK_ID,
            "method_id": prediction["method_id"],
            "implementation_identity": prediction["implementation_identity"],
            "matching_policy": POLICY_ID, "recordings": rows, "summary": summarize(rows),
            "reference_manifest_sha256": sha256(reference_path),
            "prediction_manifest_sha256": sha256(prediction_path),
            "scope": "complete_original_manual_ROI_segmentation_panel_only",
            "published_f1": {"mean": 0.847, "sd": 0.037, "video_count": 10},
            "qualification": "metric_calculation_only",
            "remaining_limits": ["physical_movie_and_frame_mapping_not_authenticated_by_this_scorer",
                                 "full_model_and_native_assembly_not_authenticated_by_this_scorer",
                                 "trace_and_runtime_endpoints_not_scored",
                                 "historical_matching_ambiguities_remain_fail_closed",
                                 "no_scientific_improvement_decision_or_protected_execution"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert-rois")
    convert.add_argument("--source-root", required=True)
    convert.add_argument("--output-dir", required=True)
    score = commands.add_parser("score-segmentation")
    score.add_argument("--source-root", required=True)
    score.add_argument("--reference", required=True)
    score.add_argument("--prediction", required=True)
    score.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "convert-rois":
            convert_panel(args.source_root, args.output_dir)
        else:
            # Check before reading targets or performing expensive comparison.
            _require(not Path(args.output).exists(), "output already exists")
            result = score_panel(args.reference, args.prediction, args.source_root)
            with Path(args.output).open("x") as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write("\n")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
