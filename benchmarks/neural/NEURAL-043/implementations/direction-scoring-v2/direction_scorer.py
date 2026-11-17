"""Evaluator-only NEURAL-043 direction scoring; no data loading or fitting.

The caller owns immutable submissions, target isolation, a source-authenticated
case roster, and recording/grid equivalence. This module verifies their numerical
join. It does not establish participant delivery in any declared access mode.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from statistics import fmean, stdev

TASK = "NEURAL-043"
CLAIMS = ("held_block_within_session", "held_mouse_anatomical_alignment")
MODES = ("direct_observation", "typed_viewer", "tool_assisted", "frozen_program")
FEATURES = ("history_time", "neural", "neural_history_time")


class ScoringError(ValueError):
    """A submission, target join or cohort comparison is not scoreable."""


def _require(condition, message):
    if not condition:
        raise ScoringError(message)


def _fields(value, required, name):
    _require(type(value) is dict and set(required) <= value.keys(),
             name + " missing required fields")


def _texts(values, name, *, unique=False):
    _require(type(values) is list and bool(values), name + " must be a nonempty list")
    _require(all(type(v) is str and bool(v) for v in values), name + " must contain text")
    if unique:
        _require(len(set(values)) == len(values), "duplicate " + name)


def _index(packets, expected, name):
    _require(type(packets) is list, name + " must be a list")
    index = {}
    for packet in packets:
        _fields(packet, ("case_id",), name)
        key = packet["case_id"]
        _require(type(key) is str and bool(key), name + " case identity")
        _require(key not in index, "duplicate " + name + " case")
        index[key] = packet
    _require(set(index) == set(expected), name + " does not match complete expected case roster")
    return index


def _validate_case(submission, public, private):
    _fields(public, ("task", "case_id", "classes", "claim", "feature_kind", "ids"), "public")
    _fields(submission, ("case_id", "classes", "ids", "probabilities"), "submission")
    _fields(private, ("case_id", "ids", "labels", "units"), "private")
    _require(public["task"] == TASK, "wrong task")
    _require(public["claim"] in CLAIMS, "unknown split claim")
    _require(public["feature_kind"] in FEATURES, "unknown feature family")
    classes, ids = public["classes"], public["ids"]
    _texts(classes, "classes", unique=True)
    _require(len(classes) in (16, 25), "retain all 16 or 25 native directions")
    _texts(ids, "trial IDs", unique=True)
    _require(submission["case_id"] == public["case_id"] == private["case_id"], "case identity mismatch")
    _require(type(submission["classes"]) is list and submission["classes"] == classes, "class order mismatch")
    _require(type(submission["ids"]) is list and type(private["ids"]) is list
             and submission["ids"] == ids == private["ids"], "trial ID/order mismatch")
    labels, units = private["labels"], private["units"]
    _texts(labels, "private labels")
    _texts(units, "private mouse units")
    _require(len(labels) == len(units) == len(ids), "per-case private target/unit count mismatch")
    _require(set(labels) <= set(classes), "target outside native class space")
    _require(len(set(units)) == 1, "one held block or held mouse must have one mouse unit")
    probabilities = submission["probabilities"]
    _require(type(probabilities) is list and len(probabilities) == len(ids), "prediction count mismatch")
    for row in probabilities:
        _require(type(row) is list and len(row) == len(classes), "probability width mismatch")
        _require(all(type(v) in (float, int) and 0 <= v <= 1 and math.isfinite(v) for v in row),
                 "probabilities must be finite numbers in [0,1]")
        _require(abs(math.fsum(row) - 1) <= 1e-8, "probability simplex mismatch")


def _interval(values):
    if len(values) < 2:
        return None
    # Same prospective approximate mouse t interval as the registered scorer.
    # scipy is loaded only for this retained uncertainty calculation.
    from scipy.stats import t
    mean = fmean(values)
    radius = float(t.ppf(.975, len(values) - 1)) * stdev(values) / math.sqrt(len(values))
    return {"n_mice": len(values), "mean": mean, "ci95": [mean - radius, mean + radius],
            "method": "mouse t interval; approximate independent-mouse sampling, not causal proof"}


def score_cohort(submissions, public_packets, private_packets, *, expected_case_ids, access_mode):
    """Score every expected case, pooling trials within mice before class recall.

    Lists may arrive in any case order; each packet's trial order remains exact.
    The expected roster must be fixed before predictions by the evaluator. It is
    not inferred from received successful submissions. Excluded source folds and
    their reasons remain the preparation owner's responsibility.
    """
    _require(access_mode in MODES, "unknown access mode")
    _texts(expected_case_ids, "expected cases", unique=True)
    submissions = _index(submissions, expected_case_ids, "submission")
    public = _index(public_packets, expected_case_ids, "public")
    private = _index(private_packets, expected_case_ids, "private")
    groups = defaultdict(list)
    class_orders, trial_facts, seen, families = {}, {}, set(), set()
    for case_id in expected_case_ids:
        s, p, q = submissions[case_id], public[case_id], private[case_id]
        _validate_case(s, p, q)
        classes = tuple(p["classes"])
        families.add(p["feature_kind"])
        # Only the two externally verified physical layouts are supported. A
        # changed class order cannot manufacture an extra, separately scored stratum.
        _require(class_orders.setdefault(len(classes), classes) == classes,
                 "class identity/order differs within native layout")
        key = (len(classes), p["claim"])
        for trial_id, label, mouse, probabilities in zip(p["ids"], q["labels"], q["units"], s["probabilities"]):
            fact = (classes, label, mouse)
            _require(trial_facts.setdefault(trial_id, fact) == fact,
                     "same held-out trial has inconsistent target, mouse or layout")
            occurrence = (p["claim"], trial_id)
            _require(occurrence not in seen, "duplicate held-out trial within split claim")
            seen.add(occurrence)
            groups[key].append((case_id, trial_id, mouse, classes.index(label), probabilities))
    _require(len(families) == 1, "feature families must be scored separately")
    strata = []
    for (width, claim), rows in sorted(groups.items()):
        classes = class_orders[width]
        by_mouse = defaultdict(list)
        for row in rows:
            by_mouse[row[2]].append(row)
        mice = []
        for mouse, observations in sorted(by_mouse.items()):
            support, correct, losses = [0] * width, [0] * width, []
            for _, _, _, label, probabilities in observations:
                # First maximum is the registered deterministic tie convention.
                predicted = max(range(width), key=probabilities.__getitem__)
                support[label] += 1
                correct[label] += predicted == label
                losses.append(-math.log(max(probabilities[label], 1e-15)))
            present = [i for i, count in enumerate(support) if count]
            mice.append({"mouse": mouse,
                         "balanced_accuracy": fmean(correct[i] / support[i] for i in present),
                         "log_loss": fmean(losses), "n_trials": len(observations),
                         "n_cases": len({row[0] for row in observations}),
                         "observed_classes": [classes[i] for i in present],
                         "missing_classes": [classes[i] for i in range(width) if not support[i]],
                         "class_support": support})
        strata.append({"classes": list(classes), "claim": claim, "mouse_values": mice,
                       "n_mice": len(mice), "n_trials": len(rows),
                       "balanced_accuracy": fmean(m["balanced_accuracy"] for m in mice),
                       "log_loss": fmean(m["log_loss"] for m in mice),
                       "uncertainty": {metric: _interval([m[metric] for m in mice])
                                       for metric in ("balanced_accuracy", "log_loss")}})
    roster_hash = hashlib.sha256(json.dumps(sorted(expected_case_ids), separators=(",", ":")).encode()).hexdigest()
    return {"task": TASK, "access_mode": access_mode, "feature_kind": next(iter(families)),
            "expected_case_roster_sha256": roster_hash, "n_cases": len(expected_case_ids),
            "strata": strata, "unlike_class_spaces_pooled": False,
            "access_mode_delivery_verified": False, "scientific_qualification": False}


def score_matched_features(submissions_by_feature, public_by_feature, private_packets, *,
                           expected_case_ids, access_mode):
    """Paired neural/history differences on the exact same held trials and mice.

    A single declared access mode applies to the entire comparison. This function
    cannot compare a direct observer against a frozen program as a feature effect.
    Targets are shared once, and are never returned in results.
    """
    _require(type(submissions_by_feature) is dict and type(public_by_feature) is dict
             and set(submissions_by_feature) == set(public_by_feature) == set(FEATURES),
             "all three matched feature families are required")
    _texts(expected_case_ids, "expected cases", unique=True)
    indexed = {family: _index(public_by_feature[family], expected_case_ids, family + " public")
               for family in FEATURES}
    for case_id in expected_case_ids:
        baseline = indexed["history_time"][case_id]
        for family in FEATURES:
            packet = indexed[family][case_id]
            _fields(packet, ("feature_kind", "ids", "classes", "claim"), family + " public")
            _require(packet["feature_kind"] == family, "feature-family binding mismatch")
            _require(all(packet[field] == baseline[field] for field in ("ids", "classes", "claim")),
                     "paired features must have identical held trials, classes and split")
    scores = {family: score_cohort(submissions_by_feature[family], public_by_feature[family], private_packets,
                                   expected_case_ids=expected_case_ids, access_mode=access_mode)
              for family in FEATURES}
    comparisons = []
    for family in ("neural", "neural_history_time"):
        for candidate, baseline in zip(scores[family]["strata"], scores["history_time"]["strata"]):
            effects = [{"mouse": left["mouse"], "n_trials": left["n_trials"],
                        **{metric: left[metric] - right[metric] for metric in ("balanced_accuracy", "log_loss")}}
                       for left, right in zip(candidate["mouse_values"], baseline["mouse_values"])]
            comparisons.append({"contrast": family + "_minus_history_time", "classes": candidate["classes"],
                                "claim": candidate["claim"], "mouse_differences": effects,
                                "n_mice": len(effects),
                                **{metric: fmean(row[metric] for row in effects)
                                   for metric in ("balanced_accuracy", "log_loss")},
                                "uncertainty": {metric: _interval([row[metric] for row in effects])
                                                for metric in ("balanced_accuracy", "log_loss")}})
    return {"task": TASK, "access_mode": access_mode, "scores": scores, "paired_differences": comparisons,
            "difference_direction": {"balanced_accuracy": "positive favors neural feature family",
                                     "log_loss": "negative favors neural feature family"},
            "scientific_qualification": False, "access_mode_delivery_verified": False}
