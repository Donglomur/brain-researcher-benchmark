#!/usr/bin/env python3
"""Operator-side metrics for the complete Dataset-1 Figure 5 LOSO panel.

This consumes frozen labels and already produced predictions. It neither fits a
model nor determines the authentic window/behavior mapping or paper superiority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-signal-add-012"
PANEL = "figure5_dataset1_loso"
SUBJECT_COUNT = 19


def _identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _binary(value, name):
    if type(value) is not int or value not in (0, 1):
        raise ValueError(f"{name} must be integer 0 (LOR) or 1 (awake)")
    return value


def _digest(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SHA256 must be 64 lowercase hexadecimal characters")
    return value


def _decode(blob):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON number: {value}")

    document = json.loads(blob, object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ValueError("expected JSON object with schema_version 1")
    return document


def _key(row):
    if not isinstance(row, dict):
        raise ValueError("observation must be an object")
    return (_identifier(row.get("participant_id"), "participant_id"),
            _identifier(row.get("window_id"), "window_id"))


def _targets(document):
    if document.get("task_id") != TASK_ID or document.get("panel") != PANEL:
        raise ValueError("only the original Dataset-1 Figure 5 LOSO panel is supported")
    roster = document.get("participant_ids")
    if not isinstance(roster, list) or len(roster) != SUBJECT_COUNT:
        raise ValueError("all 19 original participant identities are required")
    for participant in roster:
        _identifier(participant, "participant_id")
    if len(set(roster)) != SUBJECT_COUNT:
        raise ValueError("participant identities must be unique")
    _digest(document.get("source_binding_sha256"))
    rows = document.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty frozen target observations are required")
    lookup = {}
    by_subject = {participant: [] for participant in roster}
    for row in rows:
        key = _key(row)
        if key[0] not in by_subject or key in lookup:
            raise ValueError("unknown participant or duplicate target observation")
        lookup[key] = _binary(row.get("awake"), "awake")
        by_subject[key[0]].append(key)
    for keys in by_subject.values():
        if {lookup[key] for key in keys} != {0, 1}:
            raise ValueError("each of the 19 participants must have both awake and LOR targets")
    return roster, lookup, by_subject


def _predictions(document, target_digest, expected, arm):
    if document.get("target_manifest_sha256") != target_digest:
        raise ValueError("predictions do not bind the exact frozen target manifest")
    allowed_conditions = ("author_reference",) if arm == "author" else ("paper_data", "paper_data_author_code")
    if document.get("access_condition") not in allowed_conditions:
        raise ValueError(f"{arm} access_condition must be one of {allowed_conditions}")
    rows = document.get("observations")
    if not isinstance(rows, list):
        raise ValueError("prediction observations must be an array")
    lookup = {}
    for row in rows:
        key = _key(row)
        if key in lookup or key not in expected:
            raise ValueError("duplicate or unexpected prediction observation")
        if row.get("held_out_participant_id") != key[0]:
            raise ValueError("prediction must name its participant as the held-out LOSO fold")
        prediction = _binary(row.get("predicted_awake"), "predicted_awake")
        score = row.get("score_awake")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("score_awake must be a finite numeric score, higher for awake")
        lookup[key] = (prediction, score)
    if lookup.keys() != expected.keys():
        raise ValueError("predictions must cover every frozen target observation exactly once")
    return lookup


def _roc_curve(ranked, positives, negatives):
    """Exact empirical curve from ascending (score, label) pairs.

    Equal scores enter together under score >= threshold. The initial null
    threshold denotes a cutoff above every finite score, not a numeric cutoff.
    No interpolation, pruning, pooling or cross-participant averaging occurs.
    """
    points = [{"threshold": None, "false_positive_rate": 0.0, "true_positive_rate": 0.0}]
    tp = fp = 0
    stop = len(ranked)
    while stop:
        start = stop - 1
        while start and ranked[start - 1][0] == ranked[stop - 1][0]:
            start -= 1
        new_positives = sum(label for _, label in ranked[start:stop])
        tp += new_positives
        fp += stop - start - new_positives
        points.append({"threshold": ranked[start][0],
                       "false_positive_rate": fp / negatives,
                       "true_positive_rate": tp / positives})
        stop = start
    return points


def binary_metrics(labels, predictions, scores):
    """BA from declared hard decisions; AUC from tie-correct score ranks.

    AUC is P(awake score > LOR score) + 0.5 P(equal). Hard decisions are
    supplied by the frozen method; no threshold is selected using targets.
    The exact empirical ROC curve is retained as an operator-only diagnostic.
    """
    if not labels or len(labels) != len(predictions) or len(labels) != len(scores):
        raise ValueError("nonempty equal-length labels, decisions and scores required")
    for value in labels:
        _binary(value, "label")
    for value in predictions:
        _binary(value, "prediction")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in scores):
        raise ValueError("scores must be finite numbers")
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise ValueError("both classes are required for balanced accuracy and ROC AUC")
    tp = sum(label == prediction == 1 for label, prediction in zip(labels, predictions))
    tn = sum(label == prediction == 0 for label, prediction in zip(labels, predictions))
    sensitivity, specificity = tp / positives, tn / negatives
    ranked = sorted(zip(scores, labels))
    positive_rank_sum = 0.0
    start = 0
    while start < len(ranked):
        stop = start + 1
        while stop < len(ranked) and ranked[stop][0] == ranked[start][0]:
            stop += 1
        mean_rank = (start + 1 + stop) / 2
        positive_rank_sum += mean_rank * sum(label for _, label in ranked[start:stop])
        start = stop
    auc = (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
    return {"n_awake": positives, "n_lor": negatives, "true_awake": tp,
            "true_lor": tn, "sensitivity_awake": sensitivity,
            "specificity_lor": specificity,
            "balanced_accuracy": (sensitivity + specificity) / 2, "roc_auc": auc,
            "roc_curve": _roc_curve(ranked, positives, negatives)}


def _summary(values):
    mean = math.fsum(values) / len(values)
    sem = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1) / len(values))
    return {"mean": mean, "descriptive_subject_sem": sem}


def score_panel(target_blob, author_blob, candidate_blob, *, expected_target_sha256):
    """Score all subjects on exactly the same operator-frozen observation set.

    Byte hashes authenticate supplied files, not their scientific provenance.
    The source binding and model/sampling provenance need independent review.
    """
    digest = hashlib.sha256(target_blob).hexdigest()
    if digest != _digest(expected_target_sha256):
        raise ValueError("target manifest digest differs from the operator's frozen digest")
    targets = _decode(target_blob)
    roster, labels, by_subject = _targets(targets)
    documents = {"author": _decode(author_blob), "candidate": _decode(candidate_blob)}
    arms = {name: _predictions(document, digest, labels, name) for name, document in documents.items()}
    scores = {}
    for name, lookup in arms.items():
        records = []
        for participant in roster:
            keys = by_subject[participant]
            metrics = binary_metrics([labels[key] for key in keys],
                                     [lookup[key][0] for key in keys],
                                     [lookup[key][1] for key in keys])
            records.append({"participant_id": participant, **metrics})
        scores[name] = {"participants": records,
                       "summary": {metric: _summary([row[metric] for row in records])
                                   for metric in ("balanced_accuracy", "roc_auc")}}
    paired = []
    for author, candidate in zip(scores["author"]["participants"], scores["candidate"]["participants"]):
        paired.append({"participant_id": author["participant_id"],
                       **{metric: candidate[metric] - author[metric]
                          for metric in ("balanced_accuracy", "roc_auc")}})
    return {"schema_version": 1, "task_id": TASK_ID, "panel": PANEL,
            "scope": "operator_supplied_predictions_on_frozen_complete_roster",
            "target_manifest_sha256": digest,
            "source_binding_sha256": targets["source_binding_sha256"],
            "prediction_sha256": {"author": hashlib.sha256(author_blob).hexdigest(),
                                  "candidate": hashlib.sha256(candidate_blob).hexdigest()},
            "participant_count": SUBJECT_COUNT, "observation_count": len(labels),
            "aggregation": "equal participant means; never pooled window accuracy",
            "positive_class": "awake", "arms": scores,
            "roc_curve_convention": "Per-participant empirical score_awake >= threshold; initial null threshold is above all finite scores. No pooled or averaged curve is inferred.",
            "declared_access_conditions": {name: doc["access_condition"] for name, doc in documents.items()},
            "reproduction_offsets_from_rounded_source": {
                name: {metric: scores[name]["summary"][metric]["mean"] - anchor
                       for metric, anchor in (("balanced_accuracy", .93), ("roc_auc", .984))}
                for name in scores},
            "paired_candidate_minus_author": paired,
            "mean_paired_difference": {metric: math.fsum(row[metric] for row in paired) / SUBJECT_COUNT
                                       for metric in ("balanced_accuracy", "roc_auc")},
            "published_rounded_anchors": {"balanced_accuracy": 0.93, "roc_auc": 0.984},
            "qualification_limits": [
                "Input identities, behavioral timing, original window coverage and source binding require independent authentication.",
                "Held-out fold names do not prove absence of training leakage; model and sampling provenance require independent review.",
                "This arithmetic scorer does not reproduce the author classifier, select thresholds, calibrate stochastic runs, or establish source AUC curve-averaging equivalence.",
                "Access conditions are declarations requiring independent enforcement; paired conditions must reuse the same frozen target/source protocol.",
                "Rounded-source offsets are not a reproduction verdict; descriptive SEM is not a paired uncertainty test or improvement decision. Original controls, source precision, reproduction/calibration tolerance and meaningful effect remain required."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True, help="operator-only frozen target manifest")
    parser.add_argument("--expected-target-sha256", required=True)
    parser.add_argument("--author", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="operator-only detailed report")
    args = parser.parse_args()
    paths = (args.targets, args.author, args.candidate)
    if (args.output.resolve() in {path.resolve() for path in paths}
            or (args.output.exists() and any(args.output.samefile(path) for path in paths))):
        parser.error("output must not overwrite a source input")
    report = score_panel(*(path.read_bytes() for path in paths),
                         expected_target_sha256=args.expected_target_sha256)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
