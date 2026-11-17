"""Reduce complete operator-owned Kilosort4 Figs. 3–4 scoring exports.

This is downstream count/curve arithmetic, not a spike matcher, data issuer,
quality classifier, publication-parity certificate, or scientific win decision.
"""
from fractions import Fraction
from hashlib import sha256
import json
import math


HYBRIDS = (
    "3f6e25ae-c007-4dc3-aa77-450fd5705046",
    "fe380793-8035-414e-b000-09bfe5ece92a",
    "4ddb8a95-788b-48d0-8a0a-66c7c796da96",
)
SIMULATIONS = (
    "no_drift", "medium_drift", "high_drift", "fast_drift",
    "step_drift", "step_aligned",
)
CASES = HYBRIDS + SIMULATIONS
THRESHOLD = 0.8


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def pin(value):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), "invalid SHA256")
    return value


def identifier(value):
    require(isinstance(value, str) and 0 < len(value) <= 1024,
            "expected nonempty bounded string identity")
    return value


def roster(values):
    require(isinstance(values, list), "roster must be a list")
    checked = [identifier(x) for x in values]
    require(len(set(checked)) == len(checked), "duplicate identity")
    return checked


def keyed(rows, field):
    require(isinstance(rows, list), "rows must be a list")
    require(all(isinstance(r, dict) and field in r for r in rows), "missing identity field")
    ids = roster([r[field] for r in rows])
    return dict(zip(ids, rows))


def score_value(value):
    require(type(value) in (int, float) and math.isfinite(value), "expected finite binary64 scalar")
    return float(value)


def packed(value):
    return [value.numerator, value.denominator]


def validate_manifest(manifest):
    require(manifest.get("schema") == "kilosort4_original_recovery_inputs_v1", "manifest schema")
    require(manifest["observation_condition"] in {"paper+data", "paper+data+author-code"},
            "explicit participant observation condition required")
    profile = manifest["scoring_profile"]
    require(profile["name"] in {"R_source20", "R_paper40"}, "not an original metric profile")
    require(profile["score_encoding"] == "binary64", "source score encoding must be explicit")
    for key in ("implementation_sha256", "event_and_unit_matching_policy_sha256",
                "quality_definition_sha256"):
        pin(profile[key])
    cases = keyed(manifest["cases"], "case_id")
    require(set(cases) == set(CASES), "complete three-hybrid and six-simulation panel required")
    for case_id in CASES:
        case = cases[case_id]
        pin(case["source_input_sha256"])
        targets = roster(case["target_unit_ids"])
        background = roster(case["background_unit_ids"])
        hybrid = case_id in HYBRIDS
        require(len(targets) == (100 if hybrid else 600), "original target denominator")
        require(not set(targets) & set(background), "target/background role collision")
        require(case["kind"] == ("hybrid" if hybrid else "synthetic"), "case kind")
        if hybrid:
            require(not background, "natural hybrid background has no complete truth roster")
        else:
            require(len(background) == 600, "retain all 600 MUA construction identities")
            require(case["duration_seconds"] == 2700, "original 45-minute simulation")
    return profile, cases


def curve(rows):
    ordered = sorted(rows, key=lambda r: (r["score"], r["case_id"], r["unit_id"]))
    return {
        "target_count": len(rows),
        "recovered_count": sum(r["score"] > THRESHOLD for r in rows),
        "recovered_fraction": packed(Fraction(sum(r["score"] > THRESHOLD for r in rows), len(rows))),
        "ordered_unit_scores": ordered,
    }


def reduce_case(case_id, expected, output, profile):
    require(output["source_input_sha256"] == expected["source_input_sha256"], "source input substitution")
    units = keyed(output["units"], "unit_id")
    require(set(units) == set(expected["target_unit_ids"]), "missing, extra, or substituted target")
    points = []
    for unit_id in expected["target_unit_ids"]:
        row = units[unit_id]
        require(row["role"] == "single-unit-target", "MUA is not a positive target")
        score, fp, fn = (score_value(row[k]) for k in ("score", "false_positive", "false_negative"))
        require(-1 <= score <= 1 and 0 <= fp <= 1 and 0 <= fn <= 1, "invalid score/error range")
        floor = row["source_initialized_zero"]
        require(type(floor) is bool, "source floor flag must be boolean")
        if profile["name"] == "R_source20":
            require(score >= 0 and floor == (score == 0),
                    "literal source20 uses a disclosed initialized-zero floor")
            if not floor:
                require(score == 1 - fn - fp, "source20 positive score/error arithmetic disagrees")
        if floor:
            require(profile["name"] == "R_source20" and score == fp == fn == 0,
                    "only literal release initialization can have zero score and zero errors")
        # Preserve the scorer's rounded value and both error companions. Do not
        # recalculate it in a different order or substitute event bookkeeping.
        points.append({"case_id": case_id, "unit_id": unit_id, "score": score,
                       "false_positive": fp, "false_negative": fn,
                       "source_initialized_zero": floor})
    summary = curve(points)
    summary["source_initialized_zero_count"] = sum(r["source_initialized_zero"] for r in points)
    # These classifications are supplied by the upstream admitted scorer. Do not
    # invent a new nearest-unit rule, injective assignment, or quality threshold.
    detected = keyed(output["detected_units"], "unit_id")
    require(profile["name"] != "R_source20" or detected,
            "literal source20 fails on an empty detected-unit roster; no zero-recovery substitution")
    require(set(detected) == set(roster(output["complete_detected_unit_ids"])),
            "complete detected-unit roster required")
    companion_rows = []
    for unit_id in output["complete_detected_unit_ids"]:
        row = detected[unit_id]
        require(type(row["good"]) is bool, "good classification must be boolean")
        matches = roster(row["matched_target_ids"])
        require(set(matches) <= set(units), "matched target outside original evaluation roster")
        require(all(score_value(units[u]["score"]) > THRESHOLD for u in matches),
                "a matched target must exceed the strict recovery threshold")
        companion_rows.append({"unit_id": unit_id, "good": row["good"], "matched_target_ids": matches})
    selected_targets = [u for row in companion_rows for u in row["matched_target_ids"]]
    require(len(selected_targets) == len(set(selected_targets)),
            "each recovered target must select one best detected unit")
    covered = set(selected_targets)
    require(covered == {u for u, row in units.items() if score_value(row["score"]) > THRESHOLD},
            "recovered-target and detected-match incidence disagree")
    matched = sum(bool(r["matched_target_ids"]) for r in companion_rows)
    good = sum(r["good"] for r in companion_rows)
    good_matched = sum(r["good"] and bool(r["matched_target_ids"]) for r in companion_rows)
    good_matched_targets = sum(len(r["matched_target_ids"]) for r in companion_rows if r["good"])
    summary["detected_units"] = companion_rows
    summary["detected_count"] = len(companion_rows)
    summary["matched_detected_count"] = matched
    summary["good_detected_count"] = good
    summary["good_matched_detected_count"] = good_matched
    # Fig. 4k's first bar is explicitly the same target count as Fig. 4j.
    # Do not replace it with the number of distinct detected units selected.
    summary["matched_target_count"] = summary["recovered_count"]
    summary["good_matched_target_count"] = good_matched_targets
    summary["unmatched_good_detected_count"] = None if case_id in HYBRIDS else good - good_matched
    summary["unmatched_good_interpretation"] = (
        "undefined: natural hybrid background is not completely labelled"
        if case_id in HYBRIDS else "quality-surrogate count; not biological false-positive truth")
    return summary


def reduce_panel(manifest, exports):
    """Return complete per-condition results and paired integer differences.

    Both documents must originate from operator custody. Hash joins establish
    internal identity, not authenticity or competence of either supplied arm.
    """
    profile, cases = validate_manifest(manifest)
    require(exports.get("schema") == "kilosort4_paired_scoring_exports_v1", "export schema")
    require(exports["manifest_sha256"] == digest(manifest), "manifest hash join")
    arms = keyed(exports["arms"], "arm")
    require(set(arms) == {"reference", "candidate"}, "paired reference/candidate arms required")
    results = {}
    for name in ("reference", "candidate"):
        arm = arms[name]
        identifier(arm["method_id"])
        pin(arm["method_artifact_sha256"])
        require(arm["scoring_profile_sha256"] == digest(profile), "shared frozen scoring profile required")
        outputs = keyed(arm["cases"], "case_id")
        require(set(outputs) == set(CASES), "both arms require every original case")
        per_case = {case_id: reduce_case(case_id, cases[case_id], outputs[case_id], profile)
                    for case_id in CASES}
        pooled = curve([r for c in HYBRIDS for r in per_case[c]["ordered_unit_scores"]])
        results[name] = {"method_id": arm["method_id"], "method_artifact_sha256": arm["method_artifact_sha256"],
                         "cases": per_case, "hybrid_300_pooled": pooled}
    differences = []
    reproduction = []
    for case_id in CASES:
        reference = results["reference"]["cases"][case_id]
        candidate = results["candidate"]["cases"][case_id]
        fields = ("recovered_count", "matched_target_count", "good_matched_target_count",
                  "matched_detected_count", "good_detected_count", "good_matched_detected_count")
        delta = {field: candidate[field] - reference[field] for field in fields}
        delta["unmatched_good_detected_count"] = (None if case_id in HYBRIDS else
            candidate["unmatched_good_detected_count"] - reference["unmatched_good_detected_count"])
        differences.append({"case_id": case_id, "candidate_minus_reference": delta})
        left = keyed(reference["ordered_unit_scores"], "unit_id")
        right = keyed(candidate["ordered_unit_scores"], "unit_id")
        reproduction.append({
            "case_id": case_id, "paired_target_count": len(left),
            "score_difference_unit_ids": [u for u in left if left[u]["score"] != right[u]["score"]],
            "false_positive_difference_unit_ids": [u for u in left if left[u]["false_positive"] != right[u]["false_positive"]],
            "false_negative_difference_unit_ids": [u for u in left if left[u]["false_negative"] != right[u]["false_negative"]],
            "source_floor_difference_unit_ids": [u for u in left if left[u]["source_initialized_zero"] != right[u]["source_initialized_zero"]],
            "max_absolute_score_difference": max(abs(left[u]["score"] - right[u]["score"]) for u in left),
            "interpretation": "exact binary64 comparison only; no historical reproduction tolerance or success inferred",
        })
    return {
        "schema": "kilosort4_original_recovery_report_v1", "manifest_sha256": digest(manifest),
        "exports_sha256": digest(exports), "scoring_profile": profile,
        "observation_condition": manifest["observation_condition"],
        "recovery_rule": "binary64 score > binary64(0.8)", "unit": "ground-truth single unit, nested in source recording/simulation",
        "target_count_per_arm": 3900, "simulation_background_units_per_arm": 3600,
        "results": results, "paired_case_differences": differences,
        "reproduction_diagnostics": reproduction,
        "qualification": "count-and-curve reduction only; source authenticity and publication parity unestablished",
        "paper_improvement_decision": None,
        "paper_reproduction_decision": None,
        "limits": ["No original score exports or native sorter execution were supplied by this component.",
                   "R_source20 is release scoring, not the unresolved R_paper40 publication metric.",
                   "Matching incidence and good labels are upstream outputs, not reconstructed here.",
                   "No equal-family aggregate, meaningful-effect threshold, confidence interval, or SOTA decision is invented.",
                   "Other original panels, biophysical controls, ablations, runtime and source lineage remain mandatory."],
    }


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("exports", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = reduce_panel(json.loads(args.manifest.read_text()), json.loads(args.exports.read_text()))
    # Never overwrite an existing report or its evidence.
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
