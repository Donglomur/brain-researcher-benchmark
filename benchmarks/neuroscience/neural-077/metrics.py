"""Continuous arbitrary-candidate ERP score; no reference-family acceptance.

All arithmetic uses scalar math.fsum. Prediction values are untouched; only
the temporary log-loss argument is clipped at the declared 1e-15 boundary.
"""
from __future__ import annotations

import math

import numpy as np


REFERENCE_ARMS = ("prior", "eeg", "eog_site", "gross_amplitude",
                  "behavioral_history", "eeg_history")
EPSILON = 1e-15


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _probabilities(ordered):
    require(isinstance(ordered, dict) and len(ordered) == 2,
            "Both development cases required before private loading")
    result = {}
    for case, value in ordered.items():
        require(isinstance(case, str) and bool(case), "Nonempty case ID required")
        p = np.asarray(value)
        require(p.ndim == 1 and 2 <= len(p) <= 256
                and p.dtype.kind == "f" and p.dtype.itemsize in (4, 8)
                and np.isfinite(p).all() and np.all((p >= 0.0) & (p <= 1.0)),
                "Finite complete probability vectors required before private loading")
        result[case] = [float(v) for v in p]
    return result


def _real(value, lower, upper, name, allow_none=False):
    if value is None and allow_none:
        return None
    require(type(value) in (float, int) and math.isfinite(value)
            and lower <= value <= upper, "Invalid saved reference " + name)
    return float(value)


def _reference_reports(reference_scores, probabilities):
    """Consume only the frozen core score's arms structure, never a guessed wrapper."""
    require(isinstance(reference_scores, dict)
            and isinstance(reference_scores.get("arms"), dict)
            and set(reference_scores["arms"]) == set(REFERENCE_ARMS),
            "Saved score must contain exactly all six reference arms")
    people = sorted(probabilities)
    reports = {}
    support = None
    for arm in REFERENCE_ARMS:
        saved = reference_scores["arms"][arm]
        require(isinstance(saved, dict) and isinstance(saved.get("per_person"), list)
                and len(saved["per_person"]) == 2, "Two saved reference people required")
        rows = saved["per_person"]
        require([r.get("person_id") for r in rows] == people,
                "Reference person identities/order differ from public cases")
        by_person = {}
        current_support = {}
        for row in rows:
            case = row["person_id"]
            n = len(probabilities[case])
            require(type(row.get("n")) is int and row["n"] == n,
                    "Reference trial count differs from complete candidate case")
            n1, n0 = row.get("n_target"), row.get("n_non_target")
            require(type(n1) is int and type(n0) is int and n1 >= 0 and n0 >= 0
                    and n1 + n0 == n, "Invalid reference class support")
            defined = n1 > 0 and n0 > 0
            ba = _real(row.get("balanced_accuracy"), 0.0, 1.0, "BA", allow_none=not defined)
            require(defined == (ba is not None), "Reference BA definition/support mismatch")
            loss = _real(row.get("log_loss"), 0.0, 40.0, "log loss")
            current_support[case] = (n1, n0)
            by_person[case] = {"person_id": case, "n": n, "n_target": n1,
                               "n_non_target": n0, "balanced_accuracy": ba, "log_loss": loss}
        require(support is None or current_support == support,
                "Reference arms use different class support")
        support = current_support
        values = [by_person[c]["balanced_accuracy"] for c in people]
        mean_ba = None if any(v is None for v in values) else math.fsum(values) / 2
        mean_loss = math.fsum(by_person[c]["log_loss"] for c in people) / 2
        stored_ba = saved.get("participant_macro_balanced_accuracy")
        stored_loss = _real(saved.get("participant_macro_log_loss"), 0.0, 40.0, "macro log loss")
        if mean_ba is None:
            require(stored_ba is None, "Undefined reference macro BA must be None")
        else:
            stored_ba = _real(stored_ba, 0.0, 1.0, "macro BA")
            require(abs(stored_ba - mean_ba) <= 1e-12, "Saved macro BA inconsistent with people")
        require(abs(stored_loss - mean_loss) <= 1e-12, "Saved macro log loss inconsistent with people")
        reports[arm] = {"per_person": [by_person[c] for c in people],
                        "participant_macro_balanced_accuracy": mean_ba,
                        "participant_macro_log_loss": mean_loss}
    return reports, support


def _person(p, y, case):
    tn = fp = fn = tp = 0
    losses = []
    for probability, label in zip(p, y, strict=True):
        predicted = probability >= 0.5
        if label:
            tp += int(predicted)
            fn += int(not predicted)
        else:
            fp += int(predicted)
            tn += int(not predicted)
        metric_probability = min(max(probability, EPSILON), 1.0 - EPSILON)
        losses.append(-math.log(metric_probability) if label else -math.log1p(-metric_probability))
    ba = None if tp + fn == 0 or tn + fp == 0 else math.fsum((tp / (tp + fn), tn / (tn + fp))) / 2
    return {"person_id": case, "n": len(y), "n_target": tp + fn,
            "n_non_target": tn + fp, "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            "balanced_accuracy": ba, "log_loss": math.fsum(losses) / len(losses)}


def _difference(a, b):
    return None if a is None or b is None else a - b


def score_candidate(orderedp, private_loader, reference_scores):
    """Score a previously publicly validated candidate and retain signed results.

    private_loader(case) is a trusted, hash/identity-checking operator closure.
    It returns binary integer labels in the fixed public order for that case.
    Use validator.validate_and_score as the arbitrary-file entry point; direct
    calls cannot themselves prove that caller-provided values came from an NPZ.
    """
    p = _probabilities(orderedp)  # Check BOTH cases before the first loader call.
    references, support = _reference_reports(reference_scores, p)
    require(callable(private_loader), "Trusted private loader required")
    people = sorted(p)
    rows = []
    loads = 0
    for case in people:
        labels = np.asarray(private_loader(case))
        loads += 1
        require(labels.shape == (len(p[case]),) and labels.dtype.kind in "biu"
                and np.isin(labels, (0, 1)).all(), "Exact binary private label vector required")
        y = [int(v) for v in labels]
        require((sum(y), len(y) - sum(y)) == support[case],
                "Private label class support differs from frozen reference")
        rows.append(_person(p[case], y, case))
    values = [row["balanced_accuracy"] for row in rows]
    candidate = {"per_person": rows,
                 "participant_macro_balanced_accuracy": (None if any(v is None for v in values)
                                                          else math.fsum(values) / 2),
                 "participant_macro_log_loss": math.fsum(row["log_loss"] for row in rows) / 2}
    differences = {}
    for arm in REFERENCE_ARMS:
        ref = references[arm]
        differences[arm] = {
            "participant_macro_balanced_accuracy": _difference(
                candidate["participant_macro_balanced_accuracy"], ref["participant_macro_balanced_accuracy"]),
            "participant_macro_log_loss": _difference(
                candidate["participant_macro_log_loss"], ref["participant_macro_log_loss"]),
            "per_person": [
                {"person_id": case,
                 "balanced_accuracy": _difference(a["balanced_accuracy"], b["balanced_accuracy"]),
                 "log_loss": _difference(a["log_loss"], b["log_loss"])}
                for case, a, b in zip(people, rows, ref["per_person"], strict=True)
            ],
        }
    return {"status": "scored", "comparison_defined": candidate["participant_macro_balanced_accuracy"] is not None,
            "candidate": candidate, "reference_values": references,
            "candidate_minus_reference": differences,
            "primary_metric": "participant_macro_balanced_accuracy",
            "secondary_metric": "participant_macro_log_loss", "decision_threshold": 0.5,
            "log_loss_clip_epsilon": EPSILON, "prediction_values_modified": False,
            "positive_log_loss_difference_is_worse": True, "scientific_pass_threshold": None,
            "target_loader_invocations": loads, "population_confidence_interval": False}
