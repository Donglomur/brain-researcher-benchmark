"""Operator-only paired FCz report error; no direct-observation admission."""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

_SPEC = importlib.util.spec_from_file_location("neural078_paired_metric", Path(__file__).with_name("score.py"))
metric = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(metric)


def validate_pair(first, second):
    """Admit both full reports and their support identity without a reference."""
    metric.validate_report(first)
    metric.validate_report(second)
    rows = [{row["participant_id"]: row for row in report["participants"]}
            for report in (first, second)]
    for person in metric.PEOPLE:
        for field in metric.SUPPORT:
            metric.need(rows[0][person][field] == rows[1][person][field],
                        "Paired support identity differs: " + person + "/" + field)
    metric.need(first["aggregate"]["status"] == second["aggregate"]["status"],
                "Paired aggregate support identity differs")
    return rows


def _decimal(value):
    return Decimal(value) if type(value) is int else Decimal.from_float(value)


def _number(value):
    result = float(value)
    metric.need(math.isfinite(result) and (result != 0 or value == 0),
                "Paired metric outside finite representable arithmetic range")
    return result


def compare_pair(first, second, gold):
    """Equal-person first-minus-second absolute error on one fixed reference.

    Negative values favor the first report. This is a descriptive comparison
    for the eight fixed people, not a population interval or causal effect.
    The dictionary API does not authenticate reports or authorize reference use.
    """
    candidates = validate_pair(first, second)
    scores = [metric.compare(report, gold) for report in (first, second)]
    reference = {row["participant_id"]: row for row in gold["participants"]}
    differences, participants = [], []
    with localcontext() as context:
        context.prec = 2000
        for person in metric.PEOPLE:
            target = reference[person]
            row = {"participant_id": person, "status": target["status"],
                   "matched_pairs_n": target["matched_pairs_n"],
                   "first_absolute_error": None, "second_absolute_error": None,
                   "first_minus_second_absolute_error": None}
            if target["status"] == "supported":
                errors = [abs(_decimal(candidate[person]["matched_FCz_contrast"]) -
                              _decimal(target["matched_FCz_contrast"])) for candidate in candidates]
                difference = errors[0] - errors[1]
                differences.append(difference)
                row.update(first_absolute_error=_number(errors[0]), second_absolute_error=_number(errors[1]),
                           first_minus_second_absolute_error=_number(difference))
            participants.append(row)
        subset = _number(sum(differences, Decimal(0)) / len(differences)) if differences else None
    complete = len(differences) == len(metric.PEOPLE)
    return {
        "schema": "neural078_paired_matched_fcz_error_v1", "protocol_sha256": metric.PROTOCOL_SHA256,
        "status": "complete_cohort_compared" if complete else "insufficient_reference_support",
        "condition_scores": {"first": scores[0], "second": scores[1]},
        "paired_primary": {"name": "first_minus_second_matched_FCz_participant_macro_mae",
                           "unit": metric.AMPLITUDE_UNIT, "value": subset if complete else None,
                           "negative_favors": "first", "positive_favors": "second",
                           "required_participants": len(metric.PEOPLE), "supported_participants": len(differences)},
        "participants": participants,
        "supported_subset_mean_error_difference_diagnostic": subset,
        "unsupported_participants": scores[0]["unsupported_participants"],
        "support_commitments_equal": True, "historical_grade_changed": False,
        "qualification": "Descriptive paired report error only; no population inference, direct-observation, reference, runtime or scientific qualification."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--gold-sha256", required=True, help="Independently selected reference identity, not admission")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        metric.need(not args.output.exists() and not args.output.is_symlink(), "Fresh output path required")
        first_bytes, second_bytes = metric.read_bytes(args.first), metric.read_bytes(args.second)
        first, second = metric.parse_json(first_bytes), metric.parse_json(second_bytes)
        validate_pair(first, second)
        metric.need(re.fullmatch(r"[0-9a-f]{64}", args.gold_sha256), "Explicit canonical reference SHA256 required")
        # Both reports and their complete support commitments precede any target read.
        gold_bytes = metric.read_bytes(args.gold)
        metric.need(hashlib.sha256(gold_bytes).hexdigest() == args.gold_sha256, "Reference SHA256 mismatch")
        result = compare_pair(first, second, metric.parse_json(gold_bytes))
        result["input_sha256"] = {"first": hashlib.sha256(first_bytes).hexdigest(),
                                  "second": hashlib.sha256(second_bytes).hexdigest(), "reference": args.gold_sha256}
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")
        return 0
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        print("NEURAL-078 paired metric refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
