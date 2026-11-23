#!/usr/bin/env python3
"""Operator-only paired detector comparison on the unchanged NEURAL-009 cohort.

Both submitted programmes must cover the same full recording support. This
component executes no detector and establishes no reference competence, causal
execution, statistical superiority or clinical validity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parent
PREDECESSOR = ROOT.parent / "seizure-events-v1"
PREDECESSOR_CLI_SHA256 = "3b5ca6fe922a5f674a0598cd6912bae62ca139524466c42f5603c5684ae77dca"
PREDECESSOR_MANIFEST_SHA256 = "6e97b56bd2043184f53e9e9be13317ce312bae10ee213dfdd54edaeb5b32fb62"
METRICS = {
    "f1": "higher",
    "sensitivity": "higher",
    "precision": "higher",
    "false_alarms_per_24_observed_hours": "lower",
}


def load_predecessor(predecessor=None):
    """Load the same reviewed scorer closure used by the existing supplement."""
    predecessor = Path(predecessor) if predecessor is not None else PREDECESSOR
    with (predecessor / "cli.py").open("rb") as stream:
        blob = stream.read(7747)
    if len(blob) != 7746 or hashlib.sha256(blob).hexdigest() != PREDECESSOR_CLI_SHA256:
        raise ValueError("Predecessor loader identity mismatch")
    cli = types.ModuleType("neural009_paired_predecessor_cli")
    cli.__file__ = str(predecessor / "cli.py")
    exec(compile(blob, cli.__file__, "exec"), cli.__dict__)
    core, _ = cli.load_verified_core(PREDECESSOR_MANIFEST_SHA256)
    return core, cli


def preflight(core, support, policy, reference, candidate, *,
              expected_policy_sha256, expected_reference_recipe_sha256,
              expected_candidate_recipe_sha256, limits):
    """Check both public prediction artifacts before any private scoring work."""
    for arm, value, expected_recipe in (
            ("reference", reference, expected_reference_recipe_sha256),
            ("candidate", candidate, expected_candidate_recipe_sha256)):
        core._digest(expected_recipe, "Expected " + arm + " recipe", core.CandidateError)
        core.prevalidate_candidate(value, policy, support,
            expected_policy_sha256=expected_policy_sha256, limits=limits)
        core._need(value["recipe_sha256"] == expected_recipe,
                   arm + " recipe differs from its frozen declaration", core.CandidateError)


def _differences(reference, candidate):
    return {name: {
        "direction": direction,
        "reference": reference[name],
        "candidate": candidate[name],
        "candidate_minus_reference": (
            candidate[name] - reference[name]
            if reference[name] is not None and candidate[name] is not None else None),
    } for name, direction in METRICS.items()}


def compare(admission, policy, support, reference, candidate, *,
            expected_policy_sha256, expected_reference_recipe_sha256,
            expected_candidate_recipe_sha256, limits, _core=None):
    """Score both complete arms with v1 and return descriptive person-paired deltas.

    `reference` is a submitted detector artifact, not the private annotations.
    Recipe commitments bind declarations only. Their provenance and competence
    require independent verification. The function never omits undefined people.
    """
    core = _core if _core is not None else load_predecessor()[0]
    preflight(core, support, policy, reference, candidate,
        expected_policy_sha256=expected_policy_sha256,
        expected_reference_recipe_sha256=expected_reference_recipe_sha256,
        expected_candidate_recipe_sha256=expected_candidate_recipe_sha256, limits=limits)
    # This is after both public arms pass. The complete protected support must
    # exactly project to the same observation declaration used for both arms.
    core._need(core.canonical_sha256(core.public_support(admission)) ==
               core.canonical_sha256(support), "Private admission and public support differ")
    outputs = {name: core.evaluate(admission, policy, value,
                   expected_policy_sha256=expected_policy_sha256, limits=limits)
               for name, value in (("reference", reference), ("candidate", candidate))}
    reference_result, candidate_result = outputs["reference"], outputs["candidate"]
    for field in ("source_index_sha256", "admission_sha256", "support_sha256", "policy_sha256"):
        core._need(reference_result[field] == candidate_result[field], "Scored arm support differs")
    people = []
    reference_people = reference_result["candidate"]["patients"]
    candidate_people = candidate_result["candidate"]["patients"]
    core._need(len(reference_people) == len(candidate_people) == 23,
               "Missing complete biological-person comparison")
    for ref, cand in zip(reference_people, candidate_people):
        core._need(ref["biological_person"] == cand["biological_person"] and
                   ref["observed_ticks"] == cand["observed_ticks"], "Paired person support differs")
        people.append({"biological_person": ref["biological_person"],
                       "observed_ticks": ref["observed_ticks"],
                       "event_metric_differences": _differences(ref["event_metrics"], cand["event_metrics"])})
    macros = _differences(reference_result["candidate"]["patient_macro_event_metrics"],
                          candidate_result["candidate"]["patient_macro_event_metrics"])
    undefined = {metric: [p["biological_person"] for p in people
                          if p["event_metric_differences"][metric]["candidate_minus_reference"] is None]
                 for metric in METRICS}
    for metric in METRICS:
        mean = (None if undefined[metric] else math.fsum(
            p["event_metric_differences"][metric]["candidate_minus_reference"] for p in people) / 23)
        delta = macros[metric]["candidate_minus_reference"]
        core._need((mean is None and delta is None) or
                   (mean is not None and delta is not None and math.isclose(mean, delta, rel_tol=1e-12, abs_tol=1e-12)),
                   "Macro difference disagrees with complete person pairing")
    return {
        "schema": "neural009_paired_detector_comparison_v1", "task_id": "NEURAL-009",
        "status": "complete_conditional_normalized_paired_comparison",
        "counts": {key: reference_result["counts"][key]
                   for key in ("recordings", "biological_people", "folds", "observed_ticks")},
        "primary": {"name": "patient_macro_event_f1",
                    **macros["f1"]},
        "patient_macro_event_metric_differences": macros,
        "paired_people": people,
        "undefined_paired_people": undefined,
        "pooled_diagnostic_differences": _differences(
            reference_result["candidate"]["pooled_diagnostic"]["event_metrics"],
            candidate_result["candidate"]["pooled_diagnostic"]["event_metrics"]),
        "evaluations": outputs,
        "reference_recipe_sha256": expected_reference_recipe_sha256,
        "candidate_recipe_sha256": expected_candidate_recipe_sha256,
        "predecessor_source_manifest_sha256": PREDECESSOR_MANIFEST_SHA256,
        "statistical_superiority": None, "scientific_qualification": False,
        "interpretation": "Descriptive paired differences on complete shared public-development support. "
            "The reference is a submitted detector, not established competent or independent. "
            "LOPO training sets overlap; no confidence interval, significance threshold, clinical "
            "timeliness or native-versus-tool conclusion is supplied. Both original evaluations "
            "and their failure-to-qualify flags remain available. Operator-private output only.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("admission", "reference", "candidate", "policy", "support", "limits", "output",
                 "expected-policy-sha256", "expected-reference-recipe-sha256",
                 "expected-candidate-recipe-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-input-bytes", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        core, io = load_predecessor()
        paths = [Path(getattr(args, name)).resolve() for name in
                 ("admission", "reference", "candidate", "policy", "support", "limits", "output")]
        io.need(len(set(paths)) == len(paths), "Input and output roles must be distinct paths")
        io.need(not Path(args.output).exists() and not Path(args.output).is_symlink(), "Output must be a new path")
        io.need(args.max_input_bytes > 0 and args.max_output_bytes > 0, "Positive byte budgets required")
        reference = io.read_json(args.reference, args.max_input_bytes)
        candidate = io.read_json(args.candidate, args.max_input_bytes)
        policy = io.read_json(args.policy, args.max_input_bytes)
        support = io.read_json(args.support, args.max_input_bytes)
        limits = io.read_json(args.limits, args.max_input_bytes)
        bindings = {"expected_policy_sha256": args.expected_policy_sha256,
                    "expected_reference_recipe_sha256": args.expected_reference_recipe_sha256,
                    "expected_candidate_recipe_sha256": args.expected_candidate_recipe_sha256,
                    "limits": limits}
        preflight(core, support, policy, reference, candidate, **bindings)
        # All candidate and reference-public checks precede the private read.
        admission = io.read_json(args.admission, args.max_input_bytes)
        result = compare(admission, policy, support, reference, candidate, _core=core, **bindings)
        io.write_output(args.output, result, args.max_output_bytes)
        print(json.dumps({"status": "written", "scientific_qualification": False}))
        return 0
    except (ValueError, OSError, ImportError, RecursionError, KeyError, TypeError, MemoryError) as exc:
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__, "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
