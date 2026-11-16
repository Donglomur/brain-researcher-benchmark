"""Original CCEP artifact grader. Operator policy/targets are private trusted inputs.

This implements a prospective numeric policy, not an author BPC classifier.
No waveform loading, reference fitting, anatomy inference or qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

TASK = "clinical-ccep-stimulation-attribution"
CONTRACT = "71ffec5855733039437c65a2b26fb1e7236ecb61e259211f517b5b94d3c4783b"
CLASSES = ("hippocampus", "amygdala", "lateral_temporal_cortex", "other_mixed")
MAX_BYTES = 8 * 1024 * 1024  # Per document; never silently truncate a census.
MAX_CASES = 20000            # Engineering ceiling, not an eligible-case selection.
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
COVERAGE = {"ready", "unsupported_anatomy", "invalid_signal", "ambiguous_timing",
            "context_overflow", "other_unresolved"}


class Invalid(ValueError):
    """Invalid or incomplete construction/submission; no primary score."""


def require(ok, message):
    if not ok:
        raise Invalid(message)


def keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected), name + ": fields")


def token(value):
    require(type(value) is str and TOKEN.fullmatch(value) is not None, "opaque ID")
    return value


def sha(value):
    require(type(value) is str and SHA.fullmatch(value) is not None, "SHA256")
    return value


def number(value):
    require(type(value) in (int, float), "numeric type")
    try:
        v = float(value)
    except (OverflowError, ValueError):
        raise Invalid("numeric domain") from None
    require(math.isfinite(v), "finite number")
    return v


def unique(values, name):
    require(type(values) is list and all(type(v) is str for v in values), name)
    require(len(set(values)) == len(values), name + ": duplicate")
    return values


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def _constant(value):
    raise Invalid("nonfinite JSON constant")


def read_document(path, expected=None):
    """Bound regular-file read and authenticate exact bytes before parsing."""
    if expected is not None:
        sha(expected)
    before = os.stat(path, follow_symlinks=False)
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_BYTES,
            "document file/size")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        require(stat.S_ISREG(st.st_mode) and 0 < st.st_size <= MAX_BYTES,
                "document file/size")
        body = stream.read(MAX_BYTES + 1)
    require(len(body) == st.st_size and len(body) <= MAX_BYTES, "document size changed")
    digest = hashlib.sha256(body).hexdigest()
    require(expected is None or digest == expected, "document identity")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise Invalid("document syntax") from error
    return value, digest


def validate_policy(p):
    keys(p, {"schema", "task_id", "contract_sha256", "release", "class_order",
             "patients", "folds", "cases", "numeric_policy", "provenance",
             "targets_sha256", "scope_assertion"}, "operator policy")
    require(p["schema"] == "ccep-operator-policy-v1" and p["task_id"] == TASK,
            "policy schema/task")
    require(p["contract_sha256"] == CONTRACT and p["release"] == "ds004457:1.0.2",
            "policy contract/release")
    require(p["class_order"] == list(CLASSES), "full four-compartment class order")
    patients = unique(p["patients"], "patients")
    require(len(patients) == 5, "full five-patient roster")
    for patient in patients:
        token(patient)
    require(p["scope_assertion"] == "all_five_patients_all_VTC_contacts_all_site_blocks_all_repetitions",
            "full census assertion")
    keys(p["provenance"], {"source_census_sha256", "anatomical_mapping_sha256",
                           "packet_manifest_sha256", "exposure_audit_sha256"}, "provenance")
    for value in p["provenance"].values():
        sha(value)
    sha(p["targets_sha256"])
    n = p["numeric_policy"]
    keys(n, {"log_base", "loss_floor", "sum_tolerance", "tie_break", "calibration_bins"},
         "numeric policy")
    require(n["log_base"] == "natural" and n["tie_break"] == "first_class_in_frozen_order",
            "log/tie policy")
    require(type(n["calibration_bins"]) is int and n["calibration_bins"] == 10,
            "ten fixed equal-width calibration bins")
    require(0 < number(n["loss_floor"]) < .25, "operator probability floor")
    require(0 <= number(n["sum_tolerance"]) <= 1e-8, "normalization tolerance")
    require(type(p["folds"]) is list and len(p["folds"]) == 5, "five LOPO folds")
    fold_patients = []
    for fold in p["folds"]:
        keys(fold, {"held_patient", "training_patients"}, "fold")
        held = token(fold["held_patient"])
        training = unique(fold["training_patients"], "training patients")
        require(held in patients and set(training) == set(patients) - {held}, "LOPO separation")
        fold_patients.append(held)
    require(len(set(fold_patients)) == 5, "unique LOPO folds")
    require(type(p["cases"]) is list and 5 <= len(p["cases"]) <= MAX_CASES,
            "complete census size/engineering ceiling")
    cases, block_keys, patient_cases = {}, set(), {v: [] for v in patients}
    for c in p["cases"]:
        keys(c, {"case_id", "patient", "session", "site_block", "VTC_contact",
                 "repetitions", "packet_sha256", "coverage", "coverage_reason"}, "case")
        for name in ("case_id", "patient", "session", "site_block", "VTC_contact"):
            token(c[name])
        require(c["patient"] in patients and c["case_id"] not in cases, "case identity")
        block = tuple(c[k] for k in ("patient", "session", "site_block", "VTC_contact"))
        require(block not in block_keys, "duplicate site-contact block")
        require(type(c["repetitions"]) is int and 0 < c["repetitions"] <= 1000000,
                "complete repetition count")
        sha(c["packet_sha256"])
        require(type(c["coverage"]) is str and c["coverage"] in COVERAGE, "coverage status")
        require(type(c["coverage_reason"]) is str and len(c["coverage_reason"]) <= 256,
                "coverage reason")
        require((c["coverage"] == "ready") == (c["coverage_reason"] == ""),
                "explicit unresolved coverage reason")
        cases[c["case_id"]] = c
        block_keys.add(block)
        patient_cases[c["patient"]].append(c["case_id"])
    require(all(patient_cases.values()), "every patient has full declared blocks")
    return cases, patient_cases


def validate_predictions(s, p, policy_hash, cases):
    keys(s, {"schema", "task_id", "policy_sha256", "class_order", "condition", "rows"},
         "submission")
    require(s["schema"] == "ccep-predictions-v1" and s["task_id"] == TASK,
            "submission schema/task")
    require(s["policy_sha256"] == policy_hash and s["class_order"] == p["class_order"],
            "submission policy/class identity")
    require(s["condition"] == "original_full_scope", "primary original condition only")
    require(type(s["rows"]) is list and len(s["rows"]) == len(cases), "complete predictions")
    rows = {}
    for row in s["rows"]:
        keys(row, {"case_id", "probabilities"}, "prediction")
        name = token(row["case_id"])
        require(name in cases and name not in rows, "prediction ID set")
        v = row["probabilities"]
        require(type(v) is list and len(v) == 4, "four class probabilities")
        v = [number(x) for x in v]
        require(all(0 <= x <= 1 for x in v), "probability range")
        require(abs(math.fsum(v) - 1) <= p["numeric_policy"]["sum_tolerance"],
                "probability normalization; no repair")
        rows[name] = v
    require(set(rows) == set(cases), "complete prediction IDs")
    return rows


def validate_targets(t, cases):
    keys(t, {"schema", "task_id", "rows"}, "private targets")
    require(t["schema"] == "ccep-targets-v1" and t["task_id"] == TASK, "target schema/task")
    require(type(t["rows"]) is list and len(t["rows"]) == len(cases), "complete target rows")
    targets = {}
    for row in t["rows"]:
        keys(row, {"case_id", "class_index"}, "target")
        name, k = token(row["case_id"]), row["class_index"]
        require(name in cases and name not in targets, "target ID set")
        require(type(k) is int and 0 <= k < 4, "authenticated anatomy class index")
        targets[name] = k
    require(set(targets) == set(cases), "complete target IDs")
    return targets


def summarize(p, groups, predictions, targets):
    reports = []
    floor = p["numeric_policy"]["loss_floor"]
    for patient in p["patients"]:
        ids = groups[patient]
        confusion = [[0] * 4 for _ in range(4)]
        support, training_support, losses = [0] * 4, [0] * 4, []
        reliability = [[[] for _ in range(10)] for _ in range(4)]
        for other in p["patients"]:
            if other != patient:
                for name in groups[other]:
                    training_support[targets[name]] += 1
        for name in ids:
            target, v = targets[name], predictions[name]
            losses.append(-math.log(max(v[target], floor)))
            support[target] += 1
            predicted = max(range(4), key=lambda k: v[k])
            confusion[target][predicted] += 1
            for k in range(4):
                reliability[k][min(int(v[k] * 10), 9)].append((v[k], int(target == k)))
        recall = [confusion[k][k] / support[k] if support[k] else None for k in range(4)]
        supported = [v for v in recall if v is not None]
        bins = []
        for k in range(4):
            bins.append([{"count": len(cell),
                          "mean_probability": math.fsum(v[0] for v in cell) / len(cell) if cell else None,
                          "observed_fraction": sum(v[1] for v in cell) / len(cell) if cell else None}
                         for cell in reliability[k]])
        reports.append({"patient": patient, "blocks": len(ids),
                        "log_loss": math.fsum(losses) / len(ids),
                        "confusion_true_by_predicted": confusion,
                        "held_class_support": support, "outer_training_class_support": training_support,
                        "unsupported_training_classes": [CLASSES[k] for k in range(4) if not training_support[k]],
                        "recall_by_class": recall,
                        "macro_recall_observed_classes": math.fsum(supported) / len(supported),
                        "macro_recall_all_four_classes": math.fsum(supported) / 4 if len(supported) == 4 else None,
                        "calibration_by_class_and_fixed_bin": bins})
    return {"primary_patient_macro_log_loss": math.fsum(x["log_loss"] for x in reports) / 5,
            "secondary_patient_macro_recall_observed_classes":
                math.fsum(x["macro_recall_observed_classes"] for x in reports) / 5,
            "patient_folds": reports}


def score_files(policy_path, expected_policy_sha256, submission_path, targets_path):
    """Operator API. Contestant must not control policy path or its expected SHA."""
    sha(expected_policy_sha256)  # Mandatory even through the Python API.
    policy, policy_hash = read_document(policy_path, expected_policy_sha256)
    cases, groups = validate_policy(policy)
    submission, submission_hash = read_document(submission_path)
    predictions = validate_predictions(submission, policy, policy_hash, cases)
    coverage = {patient: {status: sum(c["patient"] == patient and c["coverage"] == status
                                     for c in cases.values()) for status in sorted(COVERAGE)}
                for patient in policy["patients"]}
    base = {"schema": "ccep-score-v1", "task_id": TASK, "policy_sha256": policy_hash,
            "submission_sha256": submission_hash, "condition": "original_full_scope",
            "class_order": list(CLASSES), "patients": 5, "blocks": len(cases),
            "coverage_by_patient": coverage, "numeric_policy": policy["numeric_policy"],
            "scientifically_qualified": False, "source_completeness_authenticated_by_scorer": False,
            "report_audience": "private evaluator; no automatic contestant feedback"}
    if any(c["coverage"] != "ready" for c in cases.values()):
        return {**base, "status": "construction_unestablished", "primary_patient_macro_log_loss": None,
                "targets_opened": False,
                "unresolved_cases": [{"case_id": c["case_id"], "coverage": c["coverage"],
                                      "reason": c["coverage_reason"]}
                                     for c in cases.values() if c["coverage"] != "ready"]}
    # Protected target bytes are not opened until the entire artifact is admitted.
    targets_doc, target_hash = read_document(targets_path, policy["targets_sha256"])
    targets = validate_targets(targets_doc, cases)
    return {**base, "status": "scored_operator_supplied_complete_roster", "targets_opened": True,
            "targets_sha256": target_hash, **summarize(policy, groups, predictions, targets)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--expected-policy-sha256", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--targets", required=True)
    args = ap.parse_args(argv)
    try:
        report = score_files(args.policy, args.expected_policy_sha256, args.submission, args.targets)
    except (Invalid, OSError, ValueError, OverflowError, RecursionError):
        # No supplied values, protected labels, file contents or local paths in failure output.
        print(json.dumps({"schema": "ccep-score-v1", "task_id": TASK,
                          "status": "invalid_or_incomplete", "primary_patient_macro_log_loss": None}))
        return 2
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "scored_operator_supplied_complete_roster" else 3


if __name__ == "__main__":
    sys.exit(main())
