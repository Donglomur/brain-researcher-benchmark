"""Frozen patient-balanced anatomical prevalence reference; operator-only inputs.

One fit reads labels for exactly four training patients. It cannot ingest a
held-patient label row. Assembly reads five frozen fits, never any target file.
No waveform, anatomical mapping, model selection or authentic-data qualification.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types


def _primary():
    path = Path(__file__).resolve().parent.parent / "clinical-ccep-artifact-grading/score.py"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != 14609:
            raise ValueError("primary source identity")
        body = stream.read(14610)
    if hashlib.sha256(body).hexdigest() != "2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32":
        raise ValueError("primary source identity")
    module = types.ModuleType("fixed_ccep_primary")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


P = _primary()
METHOD = "equal-training-patient-empirical-prevalence-no-smoothing-v1"


def encoded(value):
    body = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    P.require(len(body) <= P.MAX_BYTES, "complete output exceeds reader ceiling")
    return body


def _policy(path, expected):
    P.sha(expected)
    policy, digest = P.read_document(path, expected)
    cases, groups = P.validate_policy(policy)
    P.require(all(c["coverage"] == "ready" for c in cases.values()), "unresolved complete coverage")
    return policy, digest, cases, groups


def _probabilities(counts):
    # The objective equally weights patients, then blocks within each patient.
    # This is its empirical constant-predictor distribution on training patients.
    exact = [sum((Fraction(row[k], sum(row)) for row in counts), Fraction()) / 4
             for k in range(4)]
    return [float(value) for value in exact]


def fit(policy_path, policy_sha256, held_patient, labels_path, labels_sha256):
    """Fit one fold using a separately admitted training-only label artifact."""
    P.sha(labels_sha256)
    policy, ph, cases, groups = _policy(policy_path, policy_sha256)
    P.token(held_patient)
    P.require(held_patient in groups, "held patient outside complete roster")
    labels, lh = P.read_document(labels_path, labels_sha256)
    P.keys(labels, {"schema", "task_id", "policy_sha256", "held_patient", "class_order", "rows"},
           "training labels")
    P.require(labels["schema"] == "ccep-training-prevalence-labels-v1" and
              labels["task_id"] == P.TASK and labels["policy_sha256"] == ph and
              labels["held_patient"] == held_patient and labels["class_order"] == list(P.CLASSES),
              "training label binding")
    training = {name: c for name, c in cases.items() if c["patient"] != held_patient}
    # Reuse the primary's strict exact-case label admission on training support only.
    admitted = P.validate_targets({"schema": "ccep-targets-v1", "task_id": P.TASK,
                                   "rows": labels["rows"]}, training)
    counts = [{"patient": patient,
               "class_counts": [sum(admitted[name] == k for name in groups[patient]) for k in range(4)]}
              for patient in policy["patients"] if patient != held_patient]
    result = {"schema": "ccep-prevalence-fold-v1", "task_id": P.TASK,
              "method": METHOD, "policy_sha256": ph, "held_patient": held_patient,
              "training_labels_sha256": lh, "class_order": list(P.CLASSES),
              "training_patient_class_counts": counts,
              "probabilities": _probabilities([row["class_counts"] for row in counts])}
    _validate_fit(result, policy, ph, groups)
    encoded(result)
    return result


def _validate_fit(value, policy, ph, groups):
    P.keys(value, {"schema", "task_id", "method", "policy_sha256", "held_patient",
                   "training_labels_sha256", "class_order", "training_patient_class_counts",
                   "probabilities"}, "frozen prevalence fit")
    P.require(value["schema"] == "ccep-prevalence-fold-v1" and value["task_id"] == P.TASK and
              value["method"] == METHOD and value["policy_sha256"] == ph and
              value["class_order"] == list(P.CLASSES), "frozen fit binding")
    held = P.token(value["held_patient"])
    P.require(held in groups, "frozen held patient")
    P.sha(value["training_labels_sha256"])
    training = [person for person in policy["patients"] if person != held]
    rows = value["training_patient_class_counts"]
    P.require(type(rows) is list and len(rows) == 4, "four training patients")
    counts = []
    for person, row in zip(training, rows):
        P.keys(row, {"patient", "class_counts"}, "training counts")
        P.require(row["patient"] == person, "complete training patients in policy order")
        c = row["class_counts"]
        P.require(type(c) is list and len(c) == 4 and
                  all(type(n) is int and 0 <= n <= P.MAX_CASES for n in c) and
                  sum(c) == len(groups[person]), "complete training block class counts")
        counts.append(c)
    probabilities = value["probabilities"]
    P.require(type(probabilities) is list and len(probabilities) == 4, "four prior probabilities")
    # Type checks precede equality so True cannot stand in for 1.0.
    probabilities = [P.number(n) for n in probabilities]
    P.require(probabilities == _probabilities(counts), "fixed empirical prior; no tuning or repair")
    P.require(abs(math.fsum(probabilities) - 1) <= policy["numeric_policy"]["sum_tolerance"],
              "prior rounding exceeds frozen tolerance")
    return held, probabilities


def assemble(policy_path, policy_sha256, fold_paths, fold_sha256):
    """Produce exact primary-scorer rows for all five held patients; no labels."""
    P.require(len(fold_paths) == len(fold_sha256) == 5, "five frozen fold artifacts")
    for digest in fold_sha256:
        P.sha(digest)
    policy, ph, cases, groups = _policy(policy_path, policy_sha256)
    by_patient = {}
    for path, digest in zip(fold_paths, fold_sha256):
        value, _ = P.read_document(path, digest)
        held, probabilities = _validate_fit(value, policy, ph, groups)
        P.require(held not in by_patient, "duplicate held patient fit")
        by_patient[held] = probabilities
    P.require(set(by_patient) == set(groups), "complete five held patients")
    result = {"schema": "ccep-predictions-v1", "task_id": P.TASK,
              "policy_sha256": ph, "class_order": list(P.CLASSES),
              "condition": "original_full_scope",
              "rows": [{"case_id": c["case_id"], "probabilities": by_patient[c["patient"]][:]}
                       for c in policy["cases"]]}
    P.validate_predictions(result, policy, ph, cases)
    encoded(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fit", "assemble"):
        command = commands.add_parser(name)
        command.add_argument("--policy", required=True)
        command.add_argument("--policy-sha256", required=True)
        if name == "fit":
            command.add_argument("--held-patient", required=True)
            command.add_argument("--training-labels", required=True)
            command.add_argument("--training-labels-sha256", required=True)
        else:
            command.add_argument("--folds", nargs=5, required=True)
            command.add_argument("--fold-sha256", nargs=5, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fit":
            result = fit(args.policy, args.policy_sha256, args.held_patient,
                         args.training_labels, args.training_labels_sha256)
        else:
            result = assemble(args.policy, args.policy_sha256, args.folds, args.fold_sha256)
        body = encoded(result)
    except (P.Invalid, OSError, TypeError, ValueError, OverflowError, RecursionError):
        print('{"schema":"ccep-prevalence-refusal-v1","status":"invalid_or_incomplete"}')
        return 2
    sys.stdout.buffer.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
