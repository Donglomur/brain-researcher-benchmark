"""Complete NEURAL-069 artifact scorer, with no implicit data location or execution.

Operator owns an immutable packet root and independently supplied binding hash.
Candidate files must be sealed before this process starts. This is not a sandbox.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from io_contract import (IOContractError, capture_regular, strict_json, parse_npy,
                         validate_prediction_files, write_json_exclusive)
from numerical_core import (SUBJECTS, ROIS, FAMILIES, _validate_panel,
                            _aggregate, _mean, pearson_columns)

METRIC = "participant_macro_roi_macro_voxel_pearson"
LEGACY_METRIC = "participant_macro_family_macro_voxel_pearson"


class PacketError(ValueError):
    """Operator packet failure; never a candidate zero score."""


def need(ok, message):
    if not ok:
        raise PacketError(message)


def exact_file(root, descriptor, cap):
    need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"},
         "exact operator file descriptor required")
    path = descriptor["path"]
    need(type(path) is str and path not in ("", ".") and not Path(path).is_absolute()
         and "\\" not in path and ".." not in Path(path).parts
         and str(Path(path)) == path, "safe operator-relative path required")
    target = Path(root)
    for part in Path(path).parts:
        target /= part
        need(not target.is_symlink(), "operator symlinks forbidden")
    size = descriptor["bytes"]
    need(type(size) is int and 0 < size <= cap, "bounded operator file required")
    raw, digest = capture_regular(target, size)
    need(len(raw) == size and digest == descriptor["sha256"], "operator file pin mismatch")
    return raw


def read_contract(root, binding_sha256):
    """Authenticate captured metadata only; no target arrays are opened."""
    need(type(binding_sha256) is str and re.fullmatch(r"[a-f0-9]{64}", binding_sha256),
         "external operator binding SHA-256 required")
    root = Path(root)
    need(root.is_dir() and not root.is_symlink() and not (root / "private").is_symlink(),
         "operator-owned ordinary packet root required")
    raw, digest = capture_regular(root / "private/DATA_BINDING.json", 2_000_000)
    need(digest == binding_sha256, "external operator binding pin mismatch")
    binding = strict_json(raw)
    need(type(binding) is dict and binding.get("schema") == "boldmoments-private-binding-v1",
         "prepared operator binding required")
    roster = strict_json(exact_file(root, binding.get("roster"), 2_000_000))
    need(type(roster) is dict and roster.get("schema") == "boldmoments-public-roster-v1"
         and roster.get("subjects") == list(SUBJECTS)
         and roster.get("families") == {k: list(v) for k, v in FAMILIES.items()},
         "fixed complete biological panel required")
    need(roster.get("train_video_ids") == [f"vid{i:04}" for i in range(1, 1001)]
         and roster.get("query_video_ids") == [f"vid{i:04}" for i in range(1001, 1103)],
         "original ordered 1000/102 video split required")
    need(roster.get("training_repeats") == 3 and roster.get("query_repeats") == 10,
         "original three/ten repeat projection required")
    expected = [f"{s}/{r}" for s in SUBJECTS for r in ROIS]
    shapes = {}
    for rows, label in ((roster.get("cases"), "public"), (binding.get("cases"), "operator")):
        need(type(rows) is list and len(rows) == 80 and all(type(c) is dict for c in rows)
             and [c.get("id") for c in rows] == expected,
             "complete ordered 80-case " + label + " panel required")
    for case in roster["cases"]:
        need(f"{case.get('subject')}/{case.get('roi')}" == case["id"], "case identity mismatch")
        voxels, coords = case.get("voxels"), case.get("coordinates")
        need(type(voxels) is int and voxels > 0 and type(coords) is list and len(coords) == voxels,
             "complete coordinate support required")
        need(all(type(row) is list and len(row) == 3
                 and all(type(x) is int and x >= 0 for x in row) for row in coords),
             "native integer coordinate triples required")
        tuples = [tuple(row) for row in coords]
        need(tuples == sorted(set(tuples)), "distinct C-order coordinates required")
        shapes[case["id"]] = (102, voxels)
    return {"root": root, "binding": binding, "binding_sha256": digest,
            "roster_sha256": binding["roster"]["sha256"], "shapes": shapes}


def load_targets(contract):
    truth = {s: {} for s in SUBJECTS}
    for row in contract["binding"]["cases"]:
        shape = contract["shapes"][row["id"]]
        raw = exact_file(contract["root"], row.get("target"), 8 * math.prod(shape) + 16396)
        subject, roi = row["id"].split("/")
        truth[subject][roi] = parse_npy(raw, shape)
    return truth


def raw_mse(truth, prediction):
    """Unnormalized cell error; unrepresentable arithmetic is explicit."""
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        difference = truth - prediction
        squared = difference ** 2
    if not np.isfinite(squared).all():
        return {"status": "undefined", "value": None, "reason": "squared_error_overflow"}
    if np.any((difference != 0) & (squared == 0)):
        return {"status": "undefined", "value": None, "reason": "squared_error_underflow"}
    return {"status": "defined", "value": _mean(squared.ravel())}


def score_arrays(truth, prediction):
    """Strict 10 x 8 x 102 panel. Coordinate identity is the outer loader's job."""
    subjects, videos, yy, panels, _ = _validate_panel(truth, {"prediction": prediction}, None, True)
    people, legacy_people, errors = {}, {}, {}
    for subject in subjects:
        cells = {roi: pearson_columns(yy[subject][roi], panels["prediction"][subject][roi])
                 for roi in ROIS}
        cell_errors = {roi: raw_mse(yy[subject][roi], panels["prediction"][subject][roi])
                       for roi in ROIS}
        families = {family: _aggregate({r: cells[r] for r in rois},
                                      {r: cells[r]["support"]["total_voxels"] for r in rois})
                    for family, rois in FAMILIES.items()}
        people[subject] = {"rois": cells, "primary": _aggregate(cells),
                           "raw_mse_by_roi": cell_errors}
        legacy_people[subject] = _aggregate(families)
        errors[subject] = _aggregate(cell_errors)
    primary = _aggregate({s: people[s]["primary"] for s in subjects})
    return {"metric": METRIC, "primary": primary, "participants": people,
            "raw_mse": {**_aggregate(errors), "units": "squared prepared-response units",
                        "aggregation": "equal voxels per ROI; equal eight ROIs; equal ten participants"},
            "legacy_companion": {"metric": LEGACY_METRIC, **_aggregate(legacy_people),
                                 "participants": legacy_people,
                                 "role": "historical weighting only; not the current primary"},
            "panel": {"participants": len(subjects), "rois_per_participant": 8, "videos": videos},
            "constant_policy": "constant prediction on varying truth is zero; constant truth blocks aggregate",
            "uncertainty": "not estimated; shared video-family identities and resampling protocol remain unresolved"}


def grade(submission, packet_root, binding_sha256, *, loader=load_targets):
    contract = read_contract(packet_root, binding_sha256)
    try:
        raw, submission_sha = capture_regular(submission, 100_000)
        value = strict_json(raw)
        if (type(value) is not dict or set(value) != {"task_id", "roster_sha256", "predictions"}
                or value["task_id"] != "NEURAL-069"
                or value["roster_sha256"] != contract["roster_sha256"]):
            raise IOContractError("exact task and roster identity required")
        admitted = validate_prediction_files(
            Path(submission).parent, value["predictions"], contract["shapes"],
            max_total_bytes=sum(8 * math.prod(shape) + 16396 for shape in contract["shapes"].values()))
    except (IOContractError, OSError) as error:
        return {"task_id": "NEURAL-069", "status": "invalid_submission", "score": None,
                "reason": str(error)}
    # Every candidate file is captured/finite before any target callback.
    truth = loader(contract)
    prediction = {s: {} for s in SUBJECTS}
    for identifier, array in admitted["arrays"].items():
        subject, roi = identifier.split("/")
        prediction[subject][roi] = array
    result = score_arrays(truth, prediction)
    return {"task_id": "NEURAL-069", "status": "scored" if result["primary"]["status"] == "defined"
            else "undefined_required_support", "score": result["primary"]["value"],
            "analysis": result, "submission_sha256": submission_sha,
            "roster_sha256": contract["roster_sha256"], "binding_sha256": contract["binding_sha256"],
            "claim": "public-development held-video response prediction; no direct/viewer or causal claim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("fresh output required")
    try:
        result = grade(args.submission, args.packet, args.binding_sha256)
    except (PacketError, IOContractError, OSError, ValueError, KeyError, TypeError) as error:
        result = {"task_id": "NEURAL-069", "status": "operator_error", "score": None,
                  "reason": type(error).__name__ + ": " + str(error)}
    write_json_exclusive(args.output, result, max_bytes=1_000_000)
    return 0 if result["status"] == "scored" else 2


if __name__ == "__main__":
    raise SystemExit(main())
