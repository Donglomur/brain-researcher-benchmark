"""Operator numerical-report checker for NEURAL-028; no participant transport."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

TASK_ID = "NEURAL-028"
SCHEMA = "neural028-numerical-claims/v1"
REFERENCE_SHA256 = "cc7ed7ef1d95de3b92a44cd429f7b3054a4e794dc090d100f8da846bc28ebe25"
ATOL = 1e-8
RTOL = 1e-6
HERE = Path(__file__).resolve().parent


class ClaimError(ValueError):
    """Malformed report or mismatched packet, not a numerical disagreement."""


def require(condition, message):
    if not condition:
        raise ClaimError(message)


def _backend():
    path = HERE.parent / "initial-evaluator-v1" / "evaluator.py"
    source = path.read_bytes()
    require(hashlib.sha256(source).hexdigest() == REFERENCE_SHA256,
            "numerical reference changed; review and version the checker before use")
    spec = importlib.util.spec_from_file_location("neural028_claim_reference", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the bytes just authenticated, without a second source read or a
    # timestamp-based bytecode cache that could contain a different reference.
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _phase_mean(values):
    # Never compute a mean after silently removing an undefined session.
    return None if any(value is None for value in values) else math.fsum(values) / len(values)


def _animal_rows(metrics, areas):
    """Expose both phase denominators even when one phase is undefined."""
    rows = {}
    for animal in sorted({row["mname"] for row in metrics}):
        selected = [row for row in metrics if row["mname"] == animal]
        phases = {phase: [row for row in selected if row["phase"] == phase]
                  for phase in ("before", "after")}
        regions = {}
        for area in areas:
            before, after = (_phase_mean([row["matched_selectivity"][area]["fraction"]
                                         for row in phases[phase]]) for phase in ("before", "after"))
            regions[area] = {"before": before, "after": after,
                             "delta": None if before is None or after is None else after - before}
        rows[animal] = {"regime": selected[0]["regime"],
                        "before_session_ids": sorted(row["session_id"] for row in phases["before"]),
                        "after_session_ids": sorted(row["session_id"] for row in phases["after"]),
                        "n_before_sessions": len(phases["before"]),
                        "n_after_sessions": len(phases["after"]), "regions": regions}
    return rows


def build_reference(packet):
    """Build answer-bearing operator truth from arrays, never from submitted estimates.

    This function is for operator construction and audit. Its return value must not
    be delivered as participant observations. Input authenticity remains unverified.
    """
    e = _backend()
    sessions, protocol = e.validate_packet(packet)
    common, weights = e.matching_weights(sessions)
    metrics = [e.session_metrics(session, weights[session["session_id"]],
                                float(protocol.get("selectivity_threshold", 0.3)))
               for session in sessions]
    # Preserve the frozen backend's bootstrap sequence, including preceding raw
    # metrics. Skipping those draws would silently change the matched intervals.
    contrasts = e.paired_contrasts(metrics, protocol)["matched_selectivity"]
    reference = {
        "schema": SCHEMA, "task_id": TASK_ID,
        "packet_sha256": e.digest(packet), "protocol_sha256": e.digest(protocol),
        "scope": {"endpoint": "common_support_stimulus_selectivity",
                  "activity_kind": "calcium_derived_activity",
                  "movement_kind": "source_framewise_vr_position_increment",
                  "independent_unit": "mname", "cell_identity": "session_local_only",
                  "inference": "observational_conditional_on_measured_covariates",
                  "reward_location_behavior_matched": False},
        "common_support": {"strata": [int(value) for value in common],
                           "weighting": "equal_stratum_mass_in_every_session_and_stimulus"},
        "sessions": {
            metric["session_id"]: {
                "mname": metric["mname"], "regime": metric["regime"], "phase": metric["phase"],
                "neurons": {str(i): {"area_id": int(session["area_ids"][i]),
                                      "matched_dprime": metric["matched_selectivity_dprime"][i],
                                      "raw_dprime": metric["source_selectivity_dprime"][i],
                                      "reward_location_dprime": metric["source_reward_dprime"][i]}
                            for i in range(len(session["area_ids"]))},
                "matched_regions": metric["matched_selectivity"],
                "support_by_stimulus": metric["matching"],
                "unmatched_companions": {"raw_selectivity_regions": metric["source_selectivity"],
                                         "reward_location_regions": metric["source_reward"],
                                         "reward_split": metric["reward_split"],
                                         "moving_gray_baseline": metric["baseline_activity"],
                                         "excluded_nonvisual_neurons": metric["excluded_nonvisual_neurons"]}}
            for session, metric in zip(sessions, metrics)},
        "animals": _animal_rows(metrics, e.AREAS),
        "regimes_by_region": {area: contrasts[area]["regimes"] for area in e.AREAS},
        "sup_minus_unsup_by_region": {area: contrasts[area]["between_regime"] for area in e.AREAS},
    }
    _check_json(reference, "reference")
    return reference


def _check_json(value, path="report"):
    """Reject NaN, tuples, bool-as-number and other non-JSON Python objects early."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        require(math.isfinite(value), f"{path}: nonfinite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _check_json(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        require(all(type(key) is str for key in value), f"{path}: object keys must be strings")
        for key, item in value.items():
            _check_json(item, f"{path}.{key}")
        return
    raise ClaimError(f"{path}: not a JSON value")


def _compare(expected, actual, path, counts, failures):
    """Complete identity-preserving structure; tolerance applies only to measurements."""
    if isinstance(expected, dict):
        require(type(actual) is dict, f"{path}: object required")
        require(set(actual) == set(expected), f"{path}: missing or unexpected keys")
        for key, value in expected.items():
            _compare(value, actual[key], f"{path}.{key}", counts, failures)
        return
    if isinstance(expected, list):
        require(type(actual) is list and len(actual) == len(expected),
                f"{path}: complete ordered list required")
        for index, value in enumerate(expected):
            _compare(value, actual[index], f"{path}[{index}]", counts, failures)
        return
    # Numerical nulls are legitimate reported answers, not omitted values.
    if expected is None or type(expected) is float:
        require(actual is None or type(actual) in (int, float), f"{path}: number or null required")
        if actual is not None:
            try:
                require(math.isfinite(actual), f"{path}: finite number required")
            except OverflowError as exc:
                raise ClaimError(f"{path}: number outside finite measurement range") from exc
        correct = actual is None if expected is None else (
            actual is not None and abs(actual - expected) <= ATOL + RTOL * abs(expected))
    else:
        require(type(actual) is type(expected), f"{path}: exact {type(expected).__name__} required")
        correct = actual == expected
    counts["checked"] += 1
    counts["correct"] += int(correct)
    if not correct:
        # Deliberately omit the expected value. This scorecard is still operator-only.
        failures.append(path)


def grade(packet, submission):
    """Recompute all requested claims from operator arrays and return a scorecard.

    There is no favored sign, minimum effect, or source-narrative agreement score.
    Malformed/incomplete submissions fail closed; well-formed wrong values score as
    incorrect. No reference result supplied by a candidate is accepted as truth.
    """
    _check_json(submission)
    expected = build_reference(packet)
    require(type(submission) is dict and set(submission) == set(expected),
            "report: complete numerical claim sections required")
    for field in ("schema", "task_id", "packet_sha256", "protocol_sha256"):
        require(submission[field] == expected[field], f"{field}: wrong report identity")
    sections, failures = {}, []
    for section in ("scope", "common_support", "sessions", "animals", "regimes_by_region",
                    "sup_minus_unsup_by_region"):
        counts = {"checked": 0, "correct": 0}
        _compare(expected[section], submission[section], section, counts, failures)
        counts["all_correct"] = counts["checked"] == counts["correct"]
        sections[section] = counts
    return {"schema": "neural028-numerical-scorecard/v1", "task_id": TASK_ID,
            "packet_sha256": expected["packet_sha256"],
            "protocol_sha256": expected["protocol_sha256"],
            "submission_sha256": hashlib.sha256(json.dumps(submission, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "reference_sha256": REFERENCE_SHA256, "absolute_tolerance": ATOL,
            "relative_tolerance": RTOL, "all_numerical_claims_correct": not failures,
            "sections": sections, "incorrect_claim_paths": failures,
            "qualification": "operator_generated_control_only_until_authentic_admission",
            "participant_access_mode": "not_assigned_by_this_checker",
            "not_graded": ["free_text_reasoning", "causal_mechanism", "behavior_matched_reward",
                           "held_animal_explanatory_predictions", "native_cohort_authenticity"],
            "feedback_policy": "operator_only_no_case_adaptive_participant_feedback"}


def _object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, f"duplicate JSON key: {key}")
        out[key] = value
    return out


def read_json(path):
    def invalid(value):
        raise ClaimError(f"nonfinite JSON token: {value}")
    value = json.loads(Path(path).read_text(), object_pairs_hook=_object, parse_constant=invalid)
    _check_json(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(args.output.resolve() not in {args.packet.resolve(), args.submission.resolve()},
            "scorecard must not overwrite packet or submission")
    result = grade(read_json(args.packet), read_json(args.submission))
    # Exclusive creation preserves the exact submitted report and previous grades.
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
