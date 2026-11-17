"""Matched-FCz numerical error on the existing complete NEURAL-078 report.

This independent, stdlib-only companion leaves the historical 195-field grade
unchanged. It consumes operator-selected reports, not raw EEG or trial labels.
Reference identity is not evidence of reference or scientific qualification.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

PROTOCOL_SHA256 = "3424a79612d5a157377fd32615834652623edfb2fd662b56d89c2acf06fb71e2"
PEOPLE = tuple("sub-" + p for p in ("001", "002", "003", "004", "005", "006", "007", "010"))
STRATA = ("hand1_congruency1", "hand1_congruency2", "hand2_congruency1", "hand2_congruency2")
COUNTS = ("eligible_error_n", "eligible_correct_n", "matched_pairs_n")
NUMBERS = ("mean_RT_difference_ms", "max_abs_RT_difference_ms", "unmatched_FCz_contrast",
           "matched_FCz_contrast", "matched_HEOG_contrast", "matched_VEOG_contrast",
           "matched_preresponse_FCz_placebo")
AGGREGATE_NUMBERS = ("matched_FCz_equal_person_mean", "matched_FCz_between_person_descriptive_SE")
SUPPORT = COUNTS + ("pair_digest", "stratum_support", "status")
MAX_BYTES = 65536
AMPLITUDE_UNIT = "native_EEGLAB_amplitude"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_report(report):
    """Validate the complete original report shape without importing its runtime."""
    need(type(report) is dict and set(report) == {"schema", "protocol_sha256", "participants", "aggregate"},
         "Exact report keys required")
    need(report["schema"] == "neural078_contrast_submission_v1" and
         report["protocol_sha256"] == PROTOCOL_SHA256, "Exact report protocol required")
    rows = report["participants"]
    need(type(rows) is list and len(rows) == len(PEOPLE), "All eight participants required")
    seen = []
    for row in rows:
        need(type(row) is dict and set(row) == set(SUPPORT + NUMBERS + ("participant_id",)),
             "Exact participant fields required")
        person = row["participant_id"]
        need(type(person) is str and person in PEOPLE, "Known participant required")
        seen.append(person)
        for key in COUNTS:
            need(type(row[key]) is int and 0 <= row[key] <= 512, "Invalid count: " + key)
        need(row["eligible_error_n"] + row["eligible_correct_n"] <= 512, "Total trial bound exceeded")
        need(row["matched_pairs_n"] <= min(row["eligible_error_n"], row["eligible_correct_n"]),
             "Pair count exceeds eligible support")
        need(type(row["pair_digest"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["pair_digest"]),
             "Canonical pair digest required")
        strata = row["stratum_support"]
        need(type(strata) is dict and set(strata) == set(STRATA), "All four strata required")
        for values in strata.values():
            need(type(values) is dict and set(values) == {"error_n", "correct_n", "pairs_n"},
                 "Exact stratum fields required")
            need(all(type(v) is int and 0 <= v <= 512 for v in values.values()), "Invalid stratum counts")
            need(values["pairs_n"] <= min(values["error_n"], values["correct_n"]), "Invalid stratum pairs")
        for total, part in zip(COUNTS, ("error_n", "correct_n", "pairs_n")):
            need(row[total] == sum(s[part] for s in strata.values()), "Stratum totals disagree")
        supported = row["matched_pairs_n"] >= 10
        need(row["status"] == ("supported" if supported else "insufficient_matched_pairs"),
             "Status disagrees with ten-pair threshold")
        for key in NUMBERS:
            need(finite(row[key]) if supported else row[key] is None,
                 "Supported numbers must be finite; unsupported numbers must be null")
    need(len(set(seen)) == len(PEOPLE), "Duplicate or missing participant")
    aggregate = report["aggregate"]
    need(type(aggregate) is dict and set(aggregate) == set(AGGREGATE_NUMBERS + ("status",)),
         "Exact aggregate fields required")
    all_supported = all(row["status"] == "supported" for row in rows)
    need(aggregate["status"] == ("all_participants_supported" if all_supported else "not_all_participants_supported"),
         "Aggregate support status disagrees")
    for key in AGGREGATE_NUMBERS:
        need(finite(aggregate[key]) if all_supported else aggregate[key] is None,
             "Aggregate numbers must be finite or null according to support")
    need(not all_supported or aggregate["matched_FCz_between_person_descriptive_SE"] >= 0,
         "Descriptive SE must be nonnegative")
    return report


def _decimal(value):
    return Decimal(value) if type(value) is int else Decimal.from_float(value)


def _number(value):
    """Do not serialize an overflow or silently turn nonzero error into zero."""
    result = float(value)
    need(math.isfinite(result) and (result != 0 or value == 0), "Metric outside finite representable arithmetic range")
    return result


def _mean(values):
    return sum(values, Decimal(0)) / len(values) if values else None


def _sign(value):
    return (value > 0) - (value < 0)


def _unit(field):
    return "ms" if field in NUMBERS[:2] else AMPLITUDE_UNIT


def compare(candidate, gold):
    """Return target error; reject differing support instead of dropping cases.

    The primary is null if any reference participant lacks ten matched pairs.
    Subset diagnostics never replace that complete-cohort primary.
    """
    validate_report(candidate)
    validate_report(gold)
    predicted = {row["participant_id"]: row for row in candidate["participants"]}
    reference = {row["participant_id"]: row for row in gold["participants"]}
    for person in PEOPLE:
        for field in SUPPORT:
            need(predicted[person][field] == reference[person][field],
                 "Support identity differs: " + person + "/" + field)
    need(candidate["aggregate"]["status"] == gold["aggregate"]["status"], "Aggregate support identity differs")
    supported = [person for person in PEOPLE if reference[person]["status"] == "supported"]
    unsupported = [person for person in PEOPLE if person not in supported]
    # Exact decimal representations of finite binary64 inputs need at most 1074
    # fractional decimal places. This precision also covers opposite large signs.
    with localcontext() as context:
        context.prec = 2000
        errors = {field: [] for field in NUMBERS}
        participants = []
        signs = []
        for person in PEOPLE:
            row = {"participant_id": person, "status": reference[person]["status"],
                   "matched_pairs_n": reference[person]["matched_pairs_n"],
                   "absolute_errors": {field: None for field in NUMBERS},
                   "matched_FCz_sign_agreement": None}
            if person in supported:
                for field in NUMBERS:
                    difference = _decimal(predicted[person][field]) - _decimal(reference[person][field])
                    errors[field].append(abs(difference))
                    row["absolute_errors"][field] = _number(abs(difference))
                agreement = _sign(predicted[person]["matched_FCz_contrast"]) == _sign(reference[person]["matched_FCz_contrast"])
                row["matched_FCz_sign_agreement"] = agreement
                signs.append(int(agreement))
            participants.append(row)
        summaries = {field: {"unit": _unit(field), "supported_participants": len(supported),
                             "supported_subset_mae": _number(_mean(values)) if values else None}
                     for field, values in errors.items()}
        aggregate_errors = {field: None for field in AGGREGATE_NUMBERS}
        if not unsupported:
            for field in AGGREGATE_NUMBERS:
                aggregate_errors[field] = _number(abs(_decimal(candidate["aggregate"][field]) -
                                                       _decimal(gold["aggregate"][field])))
        primary = summaries["matched_FCz_contrast"]["supported_subset_mae"] if not unsupported else None
        zero_baseline = _number(_mean([abs(_decimal(reference[person]["matched_FCz_contrast"]))
                                       for person in PEOPLE])) if not unsupported else None
    return {
        "schema": "neural078_matched_fcz_error_v1", "protocol_sha256": PROTOCOL_SHA256,
        "status": "complete_cohort_scored" if not unsupported else "insufficient_reference_support",
        "primary": {"name": "matched_FCz_participant_macro_mae", "direction": "lower", "unit": AMPLITUDE_UNIT,
                    "value": primary, "required_participants": len(PEOPLE), "supported_participants": len(supported)},
        "unsupported_participants": unsupported, "support_commitments_equal": True,
        "fixed_zero_contrast_baseline": {"unit": AMPLITUDE_UNIT, "participant_macro_mae": zero_baseline},
        "participants": participants, "numeric_field_diagnostics": summaries,
        "aggregate_absolute_errors": {"unit": AMPLITUDE_UNIT, **aggregate_errors},
        "supported_subset_sign_agreement": sum(signs) / len(signs) if signs else None,
        "sign_is_diagnostic_only": True, "historical_grade_changed": False,
        "qualification": "Report error only; no raw-pairing, reference, runtime or scientific qualification."
    }


def parse_json(raw):
    need(type(raw) is bytes and len(raw) <= MAX_BYTES, "Report exceeds 64 KiB")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def invalid(_value):
        raise ValueError("Nonfinite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def read_bytes(path):
    """Bound the opened regular file; this is not filesystem isolation."""
    path = Path(path)
    need(not path.is_symlink(), "Input cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES, "Input must be a bounded regular file")
        raw = handle.read(MAX_BYTES + 1)
        after = os.fstat(handle.fileno())
    need(len(raw) <= MAX_BYTES and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
         "Input changed while being read or exceeds bound")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--gold-sha256", required=True, help="Operator-selected reference byte identity; not qualification")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        need(not args.output.exists() and not args.output.is_symlink(), "Fresh output path required")
        candidate_bytes = read_bytes(args.submission)
        candidate = validate_report(parse_json(candidate_bytes))
        need(re.fullmatch(r"[0-9a-f]{64}", args.gold_sha256), "Explicit canonical reference SHA256 required")
        # No reference access occurs before the complete candidate is valid.
        gold_bytes = read_bytes(args.gold)
        need(hashlib.sha256(gold_bytes).hexdigest() == args.gold_sha256, "Reference SHA256 mismatch")
        result = compare(candidate, validate_report(parse_json(gold_bytes)))
        result["submission_sha256"] = hashlib.sha256(candidate_bytes).hexdigest()
        result["reference_sha256"] = args.gold_sha256
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")
        return 0
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        print("NEURAL-078 metric refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
