"""Paired NEURAL-069 artifact comparison on one complete authenticated panel.

The operator seals both submissions and supplies one immutable packet and its
independently verified binding hash. This does not run or qualify either method.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score


def admit(submission, contract):
    """Capture a complete candidate panel without opening any target arrays."""
    raw, digest = score.capture_regular(submission, 100_000)
    value = score.strict_json(raw)
    if (type(value) is not dict or set(value) != {"task_id", "roster_sha256", "predictions"}
            or value["task_id"] != "NEURAL-069"
            or value["roster_sha256"] != contract["roster_sha256"]):
        raise score.IOContractError("exact task and shared roster identity required")
    captured = score.validate_prediction_files(
        Path(submission).parent, value["predictions"], contract["shapes"],
        max_total_bytes=sum(8 * math.prod(shape) + 16396 for shape in contract["shapes"].values()))
    panel = {subject: {} for subject in score.SUBJECTS}
    for identifier, array in captured["arrays"].items():
        subject, roi = identifier.split("/")
        panel[subject][roi] = array
    return {"submission_sha256": digest, "panel": panel}


def difference(first, second):
    """First minus second; unavailable required support is never omitted."""
    defined = first["status"] == second["status"] == "defined"
    return {"status": "defined" if defined else "undefined",
            "value": first["value"] - second["value"] if defined else None}


def compare(first, second, packet_root, binding_sha256, *, loader=score.load_targets):
    contract = score.read_contract(packet_root, binding_sha256)
    captured, invalid = {}, {}
    # Admit both sides before the single target read, even if one is malformed.
    for side, submission in (("first", first), ("second", second)):
        try:
            captured[side] = admit(submission, contract)
        except (score.IOContractError, OSError) as error:
            invalid[side] = str(error)
    common = {"task_id": "NEURAL-069", "metric": score.METRIC,
              "difference_direction": "first_minus_second",
              "roster_sha256": contract["roster_sha256"],
              "binding_sha256": contract["binding_sha256"]}
    if invalid:
        return {**common, "status": "invalid_submission", "score_difference": None,
                "invalid_submissions": invalid, "targets_loaded": False}
    truth = loader(contract)
    analyses = {side: score.score_arrays(truth, value["panel"])
                for side, value in captured.items()}
    participants = {}
    for subject in score.SUBJECTS:
        left, right = (analyses[side]["participants"][subject] for side in ("first", "second"))
        rois = {roi: difference(left["rois"][roi], right["rois"][roi]) for roi in score.ROIS}
        participants[subject] = {"rois": rois, "primary": score._aggregate(rois)}
    delta = score._aggregate({subject: value["primary"] for subject, value in participants.items()})
    return {**common, "status": "compared" if delta["status"] == "defined"
            else "undefined_required_support", "score_difference": delta["value"],
            "paired_primary": delta, "participants": participants,
            "submissions": {side: {"submission_sha256": captured[side]["submission_sha256"],
                                    "analysis": analyses[side]} for side in ("first", "second")},
            "legacy_companion_difference": {
                "metric": score.LEGACY_METRIC,
                **difference(analyses["first"]["legacy_companion"], analyses["second"]["legacy_companion"]),
                "role": "historical weighting only; not the current paired primary"},
            "panel": {"participants": 10, "rois_per_participant": 8, "videos": 102},
            "targets_loaded": True,
            "uncertainty": "not estimated; shared video-family identities and resampling protocol remain unresolved",
            "claim": "paired public-development prediction artifacts; input entitlement, access mode, execution and scientific qualification not established"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("fresh output required")
    try:
        result = compare(args.first, args.second, args.packet, args.binding_sha256)
    except (score.PacketError, score.IOContractError, OSError, ValueError, KeyError, TypeError) as error:
        result = {"task_id": "NEURAL-069", "status": "operator_error", "score_difference": None,
                  "reason": type(error).__name__ + ": " + str(error)}
    score.write_json_exclusive(args.output, result, max_bytes=2_000_000)
    return 0 if result["status"] == "compared" else 2


if __name__ == "__main__":
    raise SystemExit(main())
