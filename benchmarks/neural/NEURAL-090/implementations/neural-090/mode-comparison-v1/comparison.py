"""Pair the existing Broad execution modes on complete validated scalar reports.

Operator postprocessing only. No recordings, targets, model calls or inference
about equal information, native isolation or policy semantics is performed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import types


CLAIMS_SHA256 = "3902466dee7b45003c76e5a2821982da53f5d2c27e7ee0532fd60e6b95ded48d"
VALIDATOR_PATH = Path(__file__).resolve().parent.parent / "investigation-claims-v1" / "claims.py"
PRIMARY_STRATA = (("held_chapter", "full"), ("held_chapter", "1024"),
                  ("joint_person_held_chapter", "0"),
                  ("joint_person_held_chapter", "1024"))
MODES = ("frozen_program", "case_adaptive_equal_inputs_tools_compute")


def validator():
    body = VALIDATOR_PATH.read_bytes()
    if hashlib.sha256(body).hexdigest() != CLAIMS_SHA256:
        raise ValueError("complete-report validator source pin mismatch")
    module = types.ModuleType("_n090_mode_claims")
    exec(compile(body, str(VALIDATOR_PATH), "exec"), module.__dict__)
    return module


def compare(report):
    """Validate all 76,800 observations, then emit four paired primary strata.

    Trusted streaming sections are consumed once. The projection is collected
    only after the original validator accepts each individual chapter row.
    All remaining original report sections must validate before output exists.
    """
    claims = validator()
    if type(report) is not dict:
        raise ValueError("complete report object required")
    captured, supports = {}, {}

    def chapters():
        for row in report.get("chapter_seed_distribution", ()):
            yield row  # The original validator checks this row before resuming.
            identity = (row["person"], row["chapter"])
            support = tuple(row["per_class_support"])
            if identity in supports and supports[identity] != support:
                raise ValueError("same person/chapter requires identical reported class support across all conditions")
            supports[identity] = support
            stratum = (row["axis"], row["budget"])
            if stratum in PRIMARY_STRATA and row["track"] == "candidate" and row["arm"] == "neural":
                key = (*stratum, row["seed"], int(row["person"]), int(row["chapter"]), row["mode"])
                captured[key] = row["log_loss"]

    checked = dict(report)
    checked["chapter_seed_distribution"] = chapters()
    expected = claims.expected_claims(checked)
    strata = []
    for axis, budget in PRIMARY_STRATA:
        chapter_pairs, person_seeds, seed_means, person_means = [], [], [], []
        for seed in range(10):
            for person in range(1, 33):
                pair = []
                for chapter in (11, 12):
                    losses = [captured[(axis, budget, seed, person, chapter, mode)] for mode in MODES]
                    delta = losses[0] - losses[1]
                    chapter_pairs.append(dict(seed=seed, person=str(person), chapter=str(chapter),
                                              frozen_log_loss=losses[0], adaptive_log_loss=losses[1],
                                              frozen_minus_adaptive=delta))
                    pair.append(delta)
                person_seeds.append(dict(seed=seed, person=str(person),
                                         frozen_minus_adaptive=math.fsum(pair) / 2))
        for seed in range(10):
            seed_means.append(dict(seed=seed, frozen_minus_adaptive=math.fsum(
                row["frozen_minus_adaptive"] for row in person_seeds if row["seed"] == seed) / 32))
        for person in range(1, 33):
            person_means.append(dict(person=str(person), frozen_minus_adaptive=math.fsum(
                row["frozen_minus_adaptive"] for row in person_seeds if row["person"] == str(person)) / 10))
        means = [expected["mean/" + "/".join((axis, budget, mode, "candidate", "neural", "log_loss"))]
                 for mode in MODES]
        delta = math.fsum(row["frozen_minus_adaptive"] for row in seed_means) / 10
        if not claims.close(delta, means[0] - means[1]):
            raise ValueError("paired difference must equal complete original endpoint difference")
        strata.append(dict(id=axis + "/" + budget, axis=axis, budget=budget,
                           unit="nats_per_prediction", frozen_log_loss=means[0], adaptive_log_loss=means[1],
                           frozen_minus_adaptive=delta, chapter_pairs=chapter_pairs,
                           person_seed_pairs=person_seeds, seed_means=seed_means, person_means=person_means,
                           biological_people=32, chapter_pairs_per_stratum=640))
    return dict(schema="n090-paired-mode-comparison-v1", task_id="NEURAL-090", comparisons=strata,
                modes=list(MODES), denominator=dict(claims.DENOMINATOR),
                difference_definition="frozen_program minus case_adaptive_equal_inputs_tools_compute candidate neural log loss; positive favors adaptive",
                aggregation="Equal two chapters within each person, equal 32 people, equal all 10 seeds; no cross-stratum aggregate.",
                inference_scope="finite_cohort_point_estimates_only", source_validator_sha256=CLAIMS_SHA256,
                input_binding={"kind": "trusted_in_memory_report", "exact_input_bytes_sha256": None,
                               "caller_custody_required": True},
                reported_class_support_consistent=True, original_event_support_authenticated=False,
                equal_information_authenticated=False, participant_policy_difference_authenticated=False,
                direct_or_no_tools_comparison=False, campaign_qualified=False,
                limitations=["Class-count agreement does not establish identical event IDs, probabilities, observations or custody.",
                             "The original CaptureBook must establish exact private event support and protected-first sealing.",
                             "Both mode names use the action-capable controller; policy freezing, input equality and resource equality need independent evidence.",
                             "No confidence interval, p-value, population inference, pass threshold or authentic performance is established."])


def read_report(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate report JSON field: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite report JSON constant: " + value)

    # Parse and hash the same captured bytes; do not reopen the report for its pin.
    body = Path(path).read_bytes()
    report = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    binding = {"kind": "exact_cli_input_bytes", "bytes": len(body),
               "exact_input_bytes_sha256": hashlib.sha256(body).hexdigest(),
               "caller_custody_required": True}
    return report, binding


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="Complete trusted operator report")
    parser.add_argument("--output", required=True, help="Fresh operator-local output path")
    args = parser.parse_args(argv)
    report, binding = read_report(args.report)
    result = compare(report)
    result["input_binding"] = binding
    with Path(args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, allow_nan=False, sort_keys=True, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
