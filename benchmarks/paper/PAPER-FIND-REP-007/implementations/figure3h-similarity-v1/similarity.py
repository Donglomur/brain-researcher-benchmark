"""Pinned Figure 3h source variant; projection-report reduction, not grading."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev

TASK = "PAPER-FIND-REP-007"
REVISION = "ba64ac697f5d9914926baac79399e80707a5f3a6"
AREAS = ("V1", "mHV", "lHV", "aHV")
EXPERIMENTS = ("naive_test1", "test1_after_grating",
               "unsup_train2_after_learning", "sup_train2_after_learning")
VARIANT = "pinned_fig3h_absolute_distance_leaf2_similarity"
INPUT_VARIANT = "pinned_code_percentile5_mean_population_projection"


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be nonempty text")
    return value


def _identity_list(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(label + " must be a list")
    for item in value:
        _text(item, label)
    if len(value) != len(set(value)):
        raise ValueError(label + " has duplicate identities")
    return value


def _value(value):
    if value is None:
        return None
    if type(value) not in (float, int):
        raise ValueError("projection values must be numeric or null")
    return float(value) if math.isfinite(value) else None


def _mean(values):
    if not values or any(value is None for value in values):
        return None
    result = mean(values)
    return float(result) if math.isfinite(result) else None


def _summary(values):
    average = _mean(values)
    sem = (stdev(values) / math.sqrt(len(values))
           if average is not None and len(values) > 1 else None)
    return {"source_record_count": len(values), "defined_record_count": sum(v is not None for v in values),
            "mean": average, "sample_sem": sem if sem is None or math.isfinite(sem) else None,
            "missing_values_propagate": True}


def _projection(stimulus, ntrial, code):
    if not isinstance(stimulus, dict):
        raise ValueError("stimulus slot must be an object")
    indices = stimulus.get("trial_indices")
    if (not isinstance(indices, list)
            or any(type(v) is not int or not 0 <= v < ntrial for v in indices)
            or indices != sorted(set(indices))
            or type(stimulus.get("trial_count")) is not int
            or stimulus["trial_count"] != len(indices)):
        raise ValueError("projection trial identities/count do not agree")
    expected_role = "odd_zero_based_reference_trials" if code in (0, 2) else "all_trials"
    if stimulus.get("trial_role") != expected_role or (code in (0, 2) and any(v % 2 != 1 for v in indices)):
        raise ValueError("source trial role changed")
    rows = stimulus.get("values")
    if not isinstance(rows, list) or len(rows) != len(indices):
        raise ValueError("projection rows must match the trial inventory")
    if any(not isinstance(row, list) or len(row) != 70 for row in rows):
        raise ValueError("projection must contain ten previous plus sixty current positions")
    present = stimulus.get("present_in_identity_map")
    if type(present) is not bool or (not present and (indices or stimulus.get("stimulus_name") is not None)):
        raise ValueError("invalid absent-stimulus identity")
    if present:
        _text(stimulus.get("stimulus_name"), "stimulus name")
    return indices, [[_value(v) for v in row[10:50]] for row in rows]


def record_similarity(projection):
    """Reduce one existing coding-direction report without discarding trials.

    utils.load_coding_direction subtracts the two population projections, takes
    mean positions 10:50 per trial, then means trials. Figure 3h applies its
    absolute-distance SI to those means. Previous/gray positions are excluded.
    """
    if (projection.get("schema") != "rep007-coding-direction-source-variant/v1"
            or projection.get("task_id") != TASK or projection.get("source_revision") != REVISION
            or projection.get("variant") != INPUT_VARIANT
            or projection.get("reference_ids") != [2, 0]
            or projection.get("percentile") != 5
            or projection.get("positions") != {"previous_trial_tail": 10, "current_trial": 60}):
        raise ValueError("projection source variant/reference/position identity changed")
    ntrial = projection.get("source_trial_count")
    if type(ntrial) is not int or ntrial < 1:
        raise ValueError("source trial count must be positive")
    areas = projection.get("areas")
    if not isinstance(areas, dict) or set(areas) != set(AREAS):
        raise ValueError("all four source areas are required")
    output = {}
    for area in AREAS:
        populations = areas[area].get("populations")
        if not isinstance(populations, dict) or set(populations) != {"first_reference", "second_reference"}:
            raise ValueError("both source populations are required")
        slots = [populations[key].get("stimuli") for key in ("first_reference", "second_reference")]
        if any(not isinstance(slot, dict) or set(slot) != set(map(str, range(7))) for slot in slots):
            raise ValueError("all seven labeled stimulus slots are required")
        summaries = {}
        for code in range(7):
            first, second = [slot[str(code)] for slot in slots]
            rows1, values1 = _projection(first, ntrial, code)
            rows2, values2 = _projection(second, ntrial, code)
            identity_fields = ("stimulus_name", "present_in_identity_map", "trial_role")
            if rows1 != rows2 or any(first.get(key) != second.get(key) for key in identity_fields):
                raise ValueError("population trial/stimulus identities do not agree")
            per_trial = [_mean([a - b if a is not None and b is not None else None
                                for a, b in zip(one, two)]) for one, two in zip(values1, values2)]
            summaries[str(code)] = {"stimulus_name": first.get("stimulus_name"),
                "trial_indices": rows1, "trial_count": len(rows1),
                "trial_texture_contrasts": per_trial, "mean_texture_contrast": _mean(per_trial)}
        circle, leaf1, leaf2 = [summaries[str(code)]["mean_texture_contrast"] for code in (0, 2, 3)]
        denominator = abs(leaf1 - circle) if leaf1 is not None and circle is not None else None
        numerator = abs(leaf2 - circle) - abs(leaf2 - leaf1) if all(v is not None for v in (circle, leaf1, leaf2)) else None
        if denominator is not None and not math.isfinite(denominator):
            denominator = None
        if numerator is not None and not math.isfinite(numerator):
            numerator = None
        value = numerator / denominator if numerator is not None and denominator not in (None, 0) else None
        if value is not None and not math.isfinite(value):
            value = None
        status = ("undefined_missing_or_nonfinite_projection" if numerator is None else
                  "undefined_zero_reference_separation" if denominator == 0 else
                  "undefined_nonfinite_similarity" if value is None else "source_variant_evaluated")
        output[area] = {"stimuli": summaries, "leaf2_similarity_index": value,
                        "numerator": numerator, "reference_separation": denominator, "status": status}
    return {"schema": "rep007-figure3h-record/v1", "variant": VARIANT, "areas": output,
            "scientific_qualification": "unknown", "scientific_improvement_assessed": False}


def evaluate_panel(panel_path):
    """Evaluate all owner-declared source records; completeness is not authenticated."""
    panel_path = Path(panel_path)
    raw = panel_path.read_bytes()
    panel = json.loads(raw)
    if panel.get("schema_version") != 1 or panel.get("task_id") != TASK:
        raise ValueError("unsupported Figure 3h panel identity")
    evidence = _text(panel.get("population_evidence"), "population_evidence")
    expected = panel.get("expected_record_ids")
    if not isinstance(expected, dict) or set(expected) != set(EXPERIMENTS):
        raise ValueError("all four original Figure 3h source conditions are required")
    for experiment in EXPERIMENTS:
        _identity_list(expected[experiment], experiment)
    flattened = [identity for experiment in EXPERIMENTS for identity in expected[experiment]]
    if len(flattened) != len(set(flattened)):
        raise ValueError("source record IDs must be globally unique")
    records = panel.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("source records are required")
    by_id = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("source record must be an object")
        identity = _text(record.get("record_id"), "record_id")
        _text(record.get("animal_id"), "animal_id")
        if identity in by_id or record.get("experiment") not in EXPERIMENTS:
            raise ValueError("duplicate source record or unknown experiment")
        by_id[identity] = record
    if set(by_id) != set(flattened):
        raise ValueError("supplied source records differ from the declared complete inventory")
    seen_hashes, groups = set(), {}
    for experiment in EXPERIMENTS:
        results = []
        for identity in expected[experiment]:
            record = by_id[identity]
            if record["experiment"] != experiment:
                raise ValueError("record experiment differs from its declared inventory")
            path = panel_path.parent / _text(record.get("projection_path"), "projection_path")
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if record.get("sha256") != digest:
                raise ValueError("projection content hash mismatch")
            if digest in seen_hashes:
                raise ValueError("same projection content reused as distinct source records")
            seen_hashes.add(digest)
            result = record_similarity(json.loads(data))
            results.append({"record_id": identity, "animal_id": record["animal_id"],
                            "projection_sha256": digest, "result": result})
        groups[experiment] = {"record_ids": expected[experiment], "records": results,
            "animal_ids": list(dict.fromkeys(record["animal_id"] for record in results)),
            "areas": {area: _summary([r["result"]["areas"][area]["leaf2_similarity_index"] for r in results]) for area in AREAS}}
    return {"schema": "rep007-figure3h-panel/v1", "task_id": TASK, "source_revision": REVISION,
        "variant": VARIANT, "panel_sha256": hashlib.sha256(raw).hexdigest(),
        "population_evidence": evidence, "conditions": groups,
        "aggregation": "equal source-record mean and sample SEM; repeated animal records retained without reweighting",
        "declared_inventory_complete": True, "original_cohort_verified": False,
        "native_source_parity_verified": False, "scientific_qualification": "unknown",
        "full_contract_complete": False, "scientific_improvement_assessed": False,
        "limitations": ["Owner-declared inventory is not an authenticated original cohort.",
            "Figure-specific paper/code similarity definitions remain unresolved; this is the pinned Figure 3h code variant.",
            "No numeric targets, agreement tolerance, inferential test, participant result or improvement criterion is established."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = evaluate_panel(args.panel)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
