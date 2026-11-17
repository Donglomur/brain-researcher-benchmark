"""Inspect complete NEURAL-034 results, including all comparator arithmetic.

This inspects trusted operator records only. It never opens targets, replays a
candidate, or attests the execution represented by those records.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import types


PREDECESSOR_SHA256 = "d349dac1455ac045c5437929b47c640db3426da79eae5f7b7738a8dae3ac009c"
PREDECESSOR = Path(__file__).resolve().parents[1] / "neural034-portable/check_result.py"
METRICS = {"balanced_accuracy", "log_loss"}
COMPARATORS = ("constant", "amplitude", "glial", "behavior", "combined", "time_scrambled")
DIRECTIONS = {"balanced_accuracy": "higher", "log_loss": "lower"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def predecessor():
    # Execute only the authenticated source bytes, rather than reopening the
    # path through an import loader after the content check.
    with PREDECESSOR.open("rb") as stream:
        body = stream.read(20001)
    need(len(body) <= 20000 and hashlib.sha256(body).hexdigest() == PREDECESSOR_SHA256,
         "reviewed predecessor inspector identity")
    module = types.ModuleType("neural034_predecessor_inspector")
    module.__file__ = str(PREDECESSOR)
    exec(compile(body, str(PREDECESSOR), "exec"), module.__dict__)
    return module


def metrics(value, label, *, signed=False):
    need(type(value) is dict and set(value) == METRICS, label + ": both metric fields")
    need(all(type(number) in (int, float) and math.isfinite(number)
             for number in value.values()), label + ": finite nonboolean metrics")
    if not signed:
        need(0 <= value["balanced_accuracy"] <= 1 and value["log_loss"] >= 0,
             label + ": metric domains")
    return value


def comparisons(grade):
    """Validate exact arithmetic from the original grader, without a tolerance."""
    primary = metrics(grade["co_primary_metrics"], "co-primary")
    need(metrics(grade.get("score"), "score alias") == primary,
         "score alias equals co-primary metrics")
    need(grade.get("directions") == DIRECTIONS, "both co-primary directions")
    references = grade.get("reference_metrics")
    differences = grade.get("signed_candidate_minus_reference")
    need(type(references) is dict and set(references) == set(COMPARATORS),
         "all six reference metric pairs")
    need(type(differences) is dict and set(differences) == set(COMPARATORS),
         "all six signed comparison pairs")
    for name in COMPARATORS:
        reference = metrics(references[name], name + " reference")
        difference = metrics(differences[name], name + " difference", signed=True)
        expected = {key: primary[key] - reference[key] for key in METRICS}
        need(difference == expected, name + ": exact candidate-minus-reference arithmetic")


def check(root):
    root = Path(root).absolute()
    previous = predecessor()
    read = previous.read
    grade_path = root / "attempt/grade/score.json"
    captured = []

    def capture(path, cap=300000):
        body = read(path, cap)
        if Path(path) == grade_path:
            captured.append(body)
        return body

    previous.read = capture
    receipt = previous.check(root)
    need(len(captured) == 1, "one authenticated grade inspected")
    # Use the exact grade bytes checked against the execution receipt by the
    # predecessor, rather than performing a separate unauthenticated reread.
    grade = previous.decode(captured[0])
    comparisons(grade)
    return {
        **receipt,
        "inspector_version": "neural034-result-integrity/v2",
        "co_primary_metrics": grade["co_primary_metrics"],
        "directions": DIRECTIONS.copy(),
        "per_mouse": sorted(grade["per_mouse"], key=lambda row: row["fold"]),
        "reference_metrics": {name: grade["reference_metrics"][name] for name in COMPARATORS},
        "signed_candidate_minus_reference": {
            name: grade["signed_candidate_minus_reference"][name] for name in COMPARATORS
        },
        "scope": "Consistency of trusted records for seven held mice and all six fixed controls; "
                 "does not recompute target scores, establish a neural contribution, or measure direct interpretation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(check(arguments.output), allow_nan=False))
