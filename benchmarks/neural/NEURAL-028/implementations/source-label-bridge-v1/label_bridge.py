"""Strict source-label projection for NEURAL-028; never loads NPY or neural arrays.

This is construction code for an operator-provided JSON projection. It is not
an authenticated source extractor, a participant observation packet, or a scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK_ID = "NEURAL-028"
SOURCE_REVISION = "ba64ac697f5d9914926baac79399e80707a5f3a6"
INPUT_SCHEMA = "neural028-source-label-input/v1"
OUTPUT_SCHEMA = "neural028-source-label-projection/v1"
TOP_FIELDS = {"schema", "task_id", "source_revision", "source_asset_sha256",
              "session_id", "trial_index_base", "neural_frame_count", "behavior"}
BEHAVIOR_FIELDS = {"UniqWalls", "stim_id", "WallName", "ft_WallID", "ft_trInd", "ntrials"}


class LabelError(ValueError):
    """The projection cannot preserve the frozen task's label and support contract."""


def require(condition, message):
    if not condition:
        raise LabelError(message)


def _fields(value, expected, label):
    require(type(value) is dict and set(value) == expected,
            f"{label}: exact fields required")


def _wall(value):
    # JSON projection must preserve identity; do not stringify distinct wall IDs.
    require((type(value) is str and bool(value)) or type(value) is int,
            "wall identity must be a nonempty string or integer (not bool)")
    return type(value).__name__, value


def _integer(value, label):
    # Source frame indices may be integral floating values. NaN/outside-behavior
    # indices are not a license to remove observations from the complete packet.
    require(type(value) in (int, float), f"{label}: integer-valued number required")
    if type(value) is float:
        require(math.isfinite(value) and value.is_integer(),
                f"{label}: finite integer-valued number required")
    return int(value)


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise LabelError("projection must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def project_labels(source):
    """Translate author wall identities to category IDs without selecting frames.

    The caller must separately authenticate the native extraction, source hash,
    animal/session mapping and index-base declaration. This function verifies
    their syntax and internal consistency only; it never infers an index base.
    """
    _fields(source, TOP_FIELDS, "source")
    require(source["schema"] == INPUT_SCHEMA and source["task_id"] == TASK_ID,
            "wrong input schema or task")
    require(source["source_revision"] == SOURCE_REVISION, "source revision mismatch")
    require(_sha(source["source_asset_sha256"]), "source asset SHA256 required")
    require(type(source["session_id"]) is str and bool(source["session_id"].strip()),
            "session_id required")
    base = source["trial_index_base"]
    require(type(base) is int and base in (0, 1), "explicit trial_index_base 0 or 1 required")
    nframes = source["neural_frame_count"]
    require(type(nframes) is int and nframes > 0, "positive integer neural_frame_count required")
    behavior = source["behavior"]
    _fields(behavior, BEHAVIOR_FIELDS, "behavior")
    ntrials = behavior["ntrials"]
    require(type(ntrials) is int and ntrials > 0, "positive integer ntrials required")
    for key in BEHAVIOR_FIELDS - {"ntrials"}:
        require(type(behavior[key]) is list, f"{key}: JSON list required")
    walls, categories = behavior["UniqWalls"], behavior["stim_id"]
    require(len(walls) == len(categories) and bool(walls), "wall/category mapping length mismatch")
    lookup = {}
    for wall, category in zip(walls, categories):
        key = _wall(wall)
        require(key not in lookup, "duplicate wall identity")
        require(type(category) is int and 0 <= category <= 6, "category must be integer 0..6")
        require(category not in lookup.values(), "ambiguous duplicate source category")
        lookup[key] = category
    require({0, 2} <= set(categories), "source category0 and category2 both required")
    require(len(behavior["WallName"]) == ntrials, "complete source trial labels required")
    require(len(behavior["ft_WallID"]) == len(behavior["ft_trInd"]) == nframes,
            "frame count mismatch: no implicit truncation or filtering")

    def category_for(wall):
        key = _wall(wall)
        require(key in lookup, "wall identity absent from source mapping")
        return lookup[key]

    trial_stimulus = [category_for(wall) for wall in behavior["WallName"]]
    frame_stimulus = [category_for(wall) for wall in behavior["ft_WallID"]]
    trial_ids = []
    for value in behavior["ft_trInd"]:
        index = _integer(value, "ft_trInd") - base
        require(0 <= index < ntrials, "frame trial index outside declared trial support")
        trial_ids.append(index)
    require(set(trial_ids) == set(range(ntrials)), "declared trial population missing from frames")
    require(all(stimulus == trial_stimulus[trial]
                for stimulus, trial in zip(frame_stimulus, trial_ids)),
            "frame/trial source stimulus disagreement")
    source_digest = _digest(source)
    return {
        "schema": OUTPUT_SCHEMA, "task_id": TASK_ID,
        "session_id": source["session_id"], "source_revision": SOURCE_REVISION,
        "declared_source_asset_sha256": source["source_asset_sha256"],
        "source_projection_sha256": source_digest,
        "source_trial_index_base": base,
        "neural_frame_count": nframes, "ntrials": ntrials,
        "source_mapping": [{"wall_identity": wall, "category_id": category}
                           for wall, category in zip(walls, categories)],
        "evaluator_fields": {"trial_id": trial_ids, "stimulus_id": frame_stimulus,
                             "trial_stimulus_id": trial_stimulus},
        "discarded_frames": 0, "discarded_trials": 0,
        "qualification": "internally_consistent_operator_projection_only",
        "source_payload_authenticated": False,
        "not_established": ["native_extraction_identity", "animal_and_phase_mapping",
                            "neural_behavior_alignment", "source_time_units",
                            "complete_native_cohort", "participant_access_mode"],
    }


def read_json(path, max_bytes=8 * 1024 * 1024):
    require(type(max_bytes) is int and 0 < max_bytes <= 64 * 1024 * 1024,
            "max_bytes must be a positive integer at most64MiB")
    with Path(path).open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    require(len(raw) <= max_bytes, "input exceeds declared byte bound")

    def object_pairs(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj

    def invalid(value):
        raise LabelError("nonfinite JSON token: " + value)

    try:
        return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LabelError("invalid UTF-8 JSON") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-input-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args()
    require(args.output.resolve() != args.input.resolve(), "output must not replace input")
    result = project_labels(read_json(args.input, args.max_input_bytes))
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
