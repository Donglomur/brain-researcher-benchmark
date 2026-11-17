"""Select NEURAL-090's prescribed primary endpoints from a complete closed report.

No labels, probabilities, models, fitting, participant calls or data acquisition.
The caller remains responsible for the report's authentic scorer/custody chain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types


CLAIMS_SHA256 = "3902466dee7b45003c76e5a2821982da53f5d2c27e7ee0532fd60e6b95ded48d"
PRIMARY_STRATA = (("held_chapter", "full"), ("held_chapter", "1024"),
                  ("joint_person_held_chapter", "0"),
                  ("joint_person_held_chapter", "1024"))
MODES = ("frozen_program", "case_adaptive_equal_inputs_tools_compute")
UNIT = "nats_per_prediction"


def _validator():
    """Execute the captured, pinned existing validator, without a second read."""
    path = Path(__file__).resolve().parent.parent / "investigation-claims-v1" / "claims.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != CLAIMS_SHA256:
        raise ValueError("complete-report validator source pin mismatch")
    module = types.ModuleType("_n090_primary_claims")
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def endpoints(report):
    """Return eight independent primary endpoints, only after full validation.

    Accepts the existing scorer's dictionary, including trusted iterable scalar
    sections. All 76,800 invocation rows and every companion section are checked.
    An abbreviated table of ten-seed means is deliberately insufficient.
    """
    claims = _validator()
    values = claims.expected_claims(report)

    def value(axis, budget, mode, track, arm, metric="log_loss"):
        return values["mean/" + "/".join((axis, budget, mode, track, arm, metric))]

    primary = []
    for axis, budget in PRIMARY_STRATA:
        for mode in MODES:
            identity = "/".join((axis, budget, mode))
            candidate = value(axis, budget, mode, "candidate", "neural")
            reference = value(axis, budget, mode, "reference", "neural")
            primary.append({
                "id": identity,
                "axis": axis,
                "budget": budget,
                "mode": mode,
                "metric": "candidate_neural_log_loss",
                "value": candidate,
                "unit": UNIT,
                "direction": "lower",
                "independent_reference": {
                    "neural_log_loss": reference,
                    "reference_minus_candidate": reference - candidate,
                    "timing_minus_neural": value(axis, budget, mode, "reference", "timing") - reference,
                    "time_shifted_neural_minus_neural": value(
                        axis, budget, mode, "reference", "time_shifted_neural") - reference,
                    "unit": UNIT,
                    "ranked": False,
                },
                "candidate_macro_f1_fixed39": {
                    "value": value(axis, budget, mode, "candidate", "neural", "macro_f1_fixed39"),
                    "unit": "fraction",
                    "ranked": False,
                },
            })

    # Retain all original numerical claims as unranked descriptive values. Their
    # presence is not a second route to ranking, thresholding, or qualification.
    units = claims.claim_schema()
    return {
        "schema": "n090-primary-endpoints-v1",
        "task_id": "NEURAL-090",
        "primary": primary,
        "ranking_rule": "Compare lower candidate neural log loss within the exact same primary id only.",
        "aggregation": "Equal chapters within person, equal 32 people, equal 10 seeds.",
        "denominator": dict(claims.DENOMINATOR),
        "descriptive_claims": [
            {"id": key, "value": values[key], "unit": units[key], "ranked": False}
            for key in sorted(values)
        ],
        "inference_scope": "finite_cohort_point_estimates_only",
        "source_validator_sha256": CLAIMS_SHA256,
        "limitations": [
            "Arithmetic validation does not authenticate source events, private support or report custody.",
            "Independent reference competence and fixed-versus-adaptive participant policies need separate qualification.",
            "No cross-stratum aggregate, pass threshold, uncertainty interval or empirical qualification is defined.",
            "Programme endpoints do not establish direct-observation or typed-viewer interpretation.",
        ],
    }


def read_report(path):
    """Read a trusted operator report; reject ambiguous or nonstandard JSON."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate report JSON field: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite report JSON constant: " + value)

    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=pairs, parse_constant=constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="Complete trusted n090-broad-point-report-v1 JSON")
    parser.add_argument("--output", required=True, help="Fresh operator-local endpoint JSON path")
    args = parser.parse_args(argv)
    result = endpoints(read_report(args.report))
    # Validate everything before creating the destination; never overwrite an
    # earlier report or print its scalar contents into a shared terminal log.
    with Path(args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, allow_nan=False, sort_keys=True, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
