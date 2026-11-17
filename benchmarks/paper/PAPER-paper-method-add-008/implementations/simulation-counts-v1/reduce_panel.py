"""Reduce evaluator-owned native spike counts for the original Figure 7 panel.

This is not a spike matcher or a submission grader. See README.md for the
unresolved native dependency and publication-reference boundaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

DATASET = "Neuropixels1-384_500_1800.s"
SEEDS = (2205, 2406, 2308, 1110, 2512)
MOTIONS = ("static", "drifting")
SORTERS = ("kilosort4", "tridesclous2", "spykingcircus2", "lupin")
COMPANIONS = ("num_well_detected", "num_false_positive", "num_redundant", "num_overmerged")


class InvalidPanel(ValueError):
    """A native export or independent owner manifest is incomplete/inconsistent."""


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise InvalidPanel(f"{name}: expected exactly {sorted(expected)}")


def integer(value, name):
    if type(value) is not int or value < 0:
        raise InvalidPanel(f"{name}: expected a nonnegative integer")
    return value


def sha256(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise InvalidPanel(f"{name}: expected lowercase SHA256")


def identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise InvalidPanel(f"{name}: expected a nonempty string")


def accuracy(tp, fn, fp):
    """Corrected paper ratio TP / (Ni + Nj - TP) = TP / (TP + FN + FP).

    A zero denominator is retained as null, not assigned a native convention.
    Resolving that convention requires the publication-compatible comparator.
    """
    for name, count in (("tp", tp), ("fn", fn), ("fp", fp)):
        integer(count, name)
    denominator = tp + fn + fp
    return tp / denominator if denominator else None


def validate_manifest(manifest):
    keys(manifest, {"schema", "dataset", "candidate_method", "evaluator_identity", "seeds"}, "manifest")
    if manifest["schema"] != "figure7-native-counts-owner/v1" or manifest["dataset"] != DATASET:
        raise InvalidPanel("manifest: wrong schema or original dataset")
    candidate = manifest["candidate_method"]
    if candidate is not None:
        identifier(candidate, "candidate_method")
        if candidate in SORTERS:
            raise InvalidPanel("candidate_method must not overwrite a source sorter")
    identity = manifest["evaluator_identity"]
    keys(identity, {"spikeinterface_source_sha256", "environment_sha256", "effective_matching_parameters", "effective_count_parameters"}, "evaluator_identity")
    for field in ("spikeinterface_source_sha256", "environment_sha256"):
        sha256(identity[field], field)
    for field in ("effective_matching_parameters", "effective_count_parameters"):
        if not isinstance(identity[field], dict) or not identity[field]:
            raise InvalidPanel(f"{field}: record resolved native parameters, not omitted defaults")
    # Reject non-JSON values/nonfinite numbers even for direct Python callers.
    try:
        canonical_bytes(identity)
    except (TypeError, ValueError) as error:
        raise InvalidPanel("evaluator identity must be finite JSON") from error
    if not isinstance(manifest["seeds"], list) or len(manifest["seeds"]) != 5:
        raise InvalidPanel("manifest must retain all five original seeds")
    inventory = {}
    for entry in manifest["seeds"]:
        keys(entry, {"seed", "sorting_sha256", "recording_sha256", "units"}, "seed entry")
        seed = entry["seed"]
        if type(seed) is not int or seed not in SEEDS or seed in inventory:
            raise InvalidPanel("unknown or duplicate seed")
        sha256(entry["sorting_sha256"], "sorting_sha256")
        keys(entry["recording_sha256"], MOTIONS, "recording_sha256")
        for motion in MOTIONS:
            sha256(entry["recording_sha256"][motion], "recording_sha256")
        units = entry["units"]
        if not isinstance(units, list) or len(units) != 500:
            raise InvalidPanel("each seed must retain all 500 original ground-truth units")
        unit_counts = {}
        for unit in units:
            keys(unit, {"unit_id", "num_spikes"}, "owner unit")
            identifier(unit["unit_id"], "unit_id")
            if unit["unit_id"] in unit_counts:
                raise InvalidPanel("duplicate owner ground-truth unit")
            unit_counts[unit["unit_id"]] = integer(unit["num_spikes"], "num_spikes")
        inventory[seed] = (entry, unit_counts)
    return inventory


def reduce_panel(manifest, native_export, expected_manifest_sha256):
    """Return every unit's accuracy, companion counts and optional paired deltas.

    Native exports must come from the evaluator owner, not from candidates.
    expected_manifest_sha256 must be supplied independently of those exports.
    """
    sha256(expected_manifest_sha256, "expected_manifest_sha256")
    if digest(manifest) != expected_manifest_sha256:
        raise InvalidPanel("owner manifest digest mismatch")
    inventory = validate_manifest(manifest)
    keys(native_export, {"schema", "owner_manifest_sha256", "cases"}, "native export")
    if native_export["schema"] != "figure7-native-counts-export/v1":
        raise InvalidPanel("wrong native export schema")
    if native_export["owner_manifest_sha256"] != expected_manifest_sha256:
        raise InvalidPanel("native export is bound to a different owner manifest")
    methods = SORTERS + ((manifest["candidate_method"],) if manifest["candidate_method"] is not None else ())
    expected = {(method, motion, seed) for method in methods for motion in MOTIONS for seed in SEEDS}
    cases = native_export["cases"]
    if not isinstance(cases, list) or len(cases) != len(expected):
        raise InvalidPanel("incomplete original panel: expected every method, motion and seed")
    reduced = {}
    for case in cases:
        keys(case, {"method", "motion", "seed", "status", "sorting_sha256", "recording_sha256", "evaluator_identity_sha256", "native_output_sha256", "runtime_seconds", "unit_counts", "units"}, "case")
        method, motion, seed = case["method"], case["motion"], case["seed"]
        if not isinstance(method, str) or not isinstance(motion, str) or type(seed) is not int:
            raise InvalidPanel("invalid case identity types")
        key = method, motion, seed
        if key not in expected or key in reduced:
            raise InvalidPanel("duplicate or non-original case identity")
        if case["status"] != "computed":
            raise InvalidPanel("failed or absent native run cannot become a zero-accuracy case")
        owner, unit_counts = inventory[seed]
        if case["sorting_sha256"] != owner["sorting_sha256"] or case["recording_sha256"] != owner["recording_sha256"][motion]:
            raise InvalidPanel("case does not use its original paired recording and ground truth")
        if case["evaluator_identity_sha256"] != digest(manifest["evaluator_identity"]):
            raise InvalidPanel("case evaluator identity differs from the frozen owner identity")
        sha256(case["native_output_sha256"], "native_output_sha256")
        runtime = case["runtime_seconds"]
        if type(runtime) not in (float, int) or not math.isfinite(runtime) or runtime <= 0:
            raise InvalidPanel("runtime_seconds must be finite and positive")
        keys(case["unit_counts"], COMPANIONS, "unit_counts")
        for name in COMPANIONS:
            integer(case["unit_counts"][name], name)
        units = case["units"]
        if not isinstance(units, list) or len(units) != 500:
            raise InvalidPanel("all ground-truth units, including unmatched units, are required")
        scores = {}
        for unit in units:
            keys(unit, {"unit_id", "tp", "fn", "fp"}, "native unit")
            uid = unit["unit_id"]
            if not isinstance(uid, str) or uid not in unit_counts or uid in scores:
                raise InvalidPanel("missing, duplicate or foreign ground-truth unit")
            score = accuracy(unit["tp"], unit["fn"], unit["fp"])
            if unit["tp"] + unit["fn"] != unit_counts[uid]:
                raise InvalidPanel("TP + FN must equal the frozen ground-truth spike count")
            scores[uid] = {**unit, "accuracy": score}
        reduced[key] = {
            "method": method, "motion": motion, "seed": seed,
            "native_output_sha256": case["native_output_sha256"],
            "runtime_seconds": runtime, "unit_counts": dict(case["unit_counts"]),
            "units": [scores[uid] for uid in unit_counts],
        }
    ordered_cases = [reduced[method, motion, seed] for method in methods for motion in MOTIONS for seed in SEEDS]
    paired_differences = []
    if manifest["candidate_method"] is not None:
        candidate = manifest["candidate_method"]
        for method in SORTERS:
            for motion in MOTIONS:
                for seed in SEEDS:
                    candidate_case, baseline = reduced[candidate, motion, seed], reduced[method, motion, seed]
                    deltas = []
                    for c, b in zip(candidate_case["units"], baseline["units"]):
                        delta = None if c["accuracy"] is None or b["accuracy"] is None else c["accuracy"] - b["accuracy"]
                        deltas.append({"unit_id": c["unit_id"], "accuracy_difference": delta})
                    paired_differences.append({
                        "candidate_method": candidate, "source_method": method,
                        "motion": motion, "seed": seed, "units": deltas,
                        "unit_count_differences": {name: candidate_case["unit_counts"][name] - baseline["unit_counts"][name] for name in COMPANIONS},
                        "runtime_seconds_difference": candidate_case["runtime_seconds"] - baseline["runtime_seconds"],
                    })
    return {
        "schema": "figure7-native-counts-reduction/v1", "dataset": DATASET,
        "owner_manifest_sha256": expected_manifest_sha256,
        "native_export_sha256": digest(native_export),
        "accuracy_definition": "tp / (tp + fn + fp); zero denominator retained as null",
        "cases": ordered_cases, "paired_candidate_minus_source": paired_differences,
        "scope": "count arithmetic and complete original panel; native matching, published reference comparison, figure binning and scientific decision are external",
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPanel(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    def reject(value):
        raise InvalidPanel(f"nonfinite JSON constant: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object, parse_constant=reject)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--native-export", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise InvalidPanel("output already exists")
    report = reduce_panel(read_json(args.owner_manifest), read_json(args.native_export), args.expected_manifest_sha256)
    # Serialize completely before opening output, so validation cannot leave a partial report.
    payload = canonical_bytes(report) + b"\n"
    with output.open("xb") as stream:
        stream.write(payload)


if __name__ == "__main__":
    main()
