"""Operator-side PhysioP300 metric cells; not an admitted paper-win grader.

No scientific libraries, raw signals, fitting, epoch selection, or fold/run
reduction. Targets belong only in the operator roster, never predictions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path


SUBJECTS = ("1", "2", "3", "4", "5", "6", "7", "9", "11")
SOURCE_METHODS = ("EEGPT", "BENDR", "BIOT", "LaBraM")
METHODS = ("candidate",) + SOURCE_METHODS
METRICS = ("auroc", "balanced_accuracy", "cohen_kappa")


class PanelError(ValueError):
    """Malformed or incomplete paired support."""


def require(condition, message):
    if not condition:
        raise PanelError(message)


def fields(value, expected, context):
    require(type(value) is dict and set(value) == set(expected),
            context + ": exact fields required")


def token(value, context):
    require(type(value) is str and 0 < len(value) <= 256
            and not any(ord(c) < 32 for c in value), context + ": invalid identity")
    return value


def content_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def binary_metrics(targets, scores):
    """Pooled event AUROC with half-credit ties; both 0.5 boundary conventions.

    The pinned author code delegates BAC/kappa to an unpinned PyHealth version.
    Report both boundary conventions instead of inventing exact-tie parity.
    Missing fixed class support is unavailable, never the author's zero fallback.
    """
    targets, scores = list(targets), list(scores)
    require(len(targets) == len(scores) and len(targets) > 0, "nonempty paired vectors required")
    require(all(type(y) is int and y in (0, 1) for y in targets), "binary integer targets required")
    require(all(type(p) in (int, float) and 0 <= p <= 1 and math.isfinite(p)
                for p in scores), "finite class-1 probabilities in [0, 1] required")
    positives = sum(targets)
    negatives = len(targets) - positives
    result = {"events": len(targets), "class_support": [negatives, positives],
              "threshold": 0.5, "threshold_ties": scores.count(0.5)}
    if not positives or not negatives:
        return {**result, "status": "undefined_fixed_class_support", "auroc": None,
                "threshold_metrics": {comparison: {"balanced_accuracy": None,
                    "cohen_kappa": None, "confusion_true_by_predicted": None}
                    for comparison in ("ge", "gt")}}

    # Integer pair counts avoid materializing every positive-negative pair.
    below_negatives = 0
    twice_wins = 0
    for _, group in itertools.groupby(sorted(zip(scores, targets)), key=lambda row: row[0]):
        labels = [row[1] for row in group]
        group_positive = sum(labels)
        group_negative = len(labels) - group_positive
        twice_wins += group_positive * (2 * below_negatives + group_negative)
        below_negatives += group_negative

    threshold_metrics = {}
    n = len(targets)
    for comparison in ("ge", "gt"):
        matrix = [[0, 0], [0, 0]]
        for y, p in zip(targets, scores):
            predicted = int(p >= 0.5) if comparison == "ge" else int(p > 0.5)
            matrix[y][predicted] += 1
        tn, fp = matrix[0]
        fn, tp = matrix[1]
        # Integer form of (observed - expected) / (1 - expected).
        expected_numerator = negatives * (tn + fn) + positives * (fp + tp)
        kappa = (n * (tn + tp) - expected_numerator) / (n * n - expected_numerator)
        threshold_metrics[comparison] = {
            "balanced_accuracy": (tn / negatives + tp / positives) / 2,
            "cohen_kappa": kappa, "confusion_true_by_predicted": matrix}
    return {**result, "status": "computed", "auroc": twice_wins / (2 * positives * negatives),
            "threshold_metrics": threshold_metrics}


def validate_roster(roster):
    fields(roster, ("schema", "subjects"), "operator roster")
    require(roster["schema"] == "physiop300_operator_roster_v1", "operator roster schema")
    require(type(roster["subjects"]) is list, "subject list required")
    subjects = {}
    all_events = set()
    recording_subjects = {}
    for subject in roster["subjects"]:
        fields(subject, ("subject_id", "events"), "subject")
        sid = token(subject["subject_id"], "subject")
        require(sid in SUBJECTS and sid not in subjects, "unexpected or duplicate subject")
        require(type(subject["events"]) is list and subject["events"], "nonempty event list required")
        events = {}
        for event in subject["events"]:
            fields(event, ("event_id", "recording_id", "target"), "operator event")
            eid = token(event["event_id"], "event")
            rid = token(event["recording_id"], "recording")
            require(eid not in all_events, "event identity duplicated across roster")
            require(rid not in recording_subjects or recording_subjects[rid] == sid,
                    "recording assigned to multiple nominal subjects")
            require(type(event["target"]) is int and event["target"] in (0, 1),
                    "target must be integer 0 or 1")
            events[eid] = event
            all_events.add(eid)
            recording_subjects[rid] = sid
        subjects[sid] = events
    require(set(subjects) == set(SUBJECTS), "complete nine nominal source-subject roster required")
    return subjects


def _metric_cells(roster, predictions, methods, prediction_schema):
    """Validate and compute exactly one operator-selected method roster.

    Exact event joins prevent row order from becoming identity. Completeness
    means relative to the supplied roster, whose historical authenticity this
    component cannot establish. Nominal subject tokens are not proof of people.
    """
    subjects = validate_roster(roster)
    fields(predictions, ("schema", "repetitions", "cells"), "prediction panel")
    require(predictions["schema"] == prediction_schema, "prediction schema")
    repetitions = predictions["repetitions"]
    require(type(repetitions) is list and len(repetitions) == 3, "three repetition identities required")
    for repetition in repetitions:
        token(repetition, "repetition")
    require(len(set(repetitions)) == 3, "distinct repetition identities required")
    require(type(predictions["cells"]) is list, "cell list required")
    expected = set(itertools.product(SUBJECTS, repetitions, methods))
    indexed = {}
    for cell in predictions["cells"]:
        fields(cell, ("subject_id", "repetition", "method", "probabilities"), "prediction cell")
        for name in ("subject_id", "repetition", "method"):
            token(cell[name], name)
        key = cell["subject_id"], cell["repetition"], cell["method"]
        require(key in expected and key not in indexed, "unexpected or duplicate panel cell")
        require(type(cell["probabilities"]) is list, "probability row list required")
        by_event = {}
        for row in cell["probabilities"]:
            fields(row, ("event_id", "p_target"), "prediction row")
            eid = token(row["event_id"], "prediction event")
            require(eid not in by_event, "duplicate predicted event")
            by_event[eid] = row["p_target"]
        require(set(by_event) == set(subjects[key[0]]),
                "every method/repetition must predict the exact same complete subject event set")
        indexed[key] = by_event
    require(set(indexed) == expected,
            "all %d cells required: nine subjects x three repetitions x %d methods"
            % (len(expected), len(methods)))

    cells = []
    computed = {}
    supports = []
    for sid in SUBJECTS:
        events = subjects[sid]
        eids = sorted(events)
        support_digest = content_digest([[eid, events[eid]["recording_id"]] for eid in eids])
        supports.append({"subject_id": sid, "events": len(events),
                         "recordings": len({e["recording_id"] for e in events.values()}),
                         "event_recording_identity_sha256": support_digest})
        for repetition, method in itertools.product(repetitions, methods):
            key = sid, repetition, method
            measured = binary_metrics([events[eid]["target"] for eid in eids],
                                      [indexed[key][eid] for eid in eids])
            computed[key] = measured
            cells.append({"subject_id": sid, "repetition": repetition, "method": method,
                          "event_recording_identity_sha256": support_digest, **measured})

    return repetitions, cells, computed, supports


def score_panel(roster, predictions):
    """Compute the retained 135-cell candidate-plus-four-reference comparison."""
    repetitions, cells, computed, supports = _metric_cells(
        roster, predictions, METHODS, "physiop300_predictions_v1")
    deltas = []
    for sid, repetition, method in itertools.product(SUBJECTS, repetitions, SOURCE_METHODS):
        candidate = computed[sid, repetition, "candidate"]
        baseline = computed[sid, repetition, method]
        available = candidate["status"] == baseline["status"] == "computed"
        deltas.append({"subject_id": sid, "repetition": repetition, "reference": method,
            "auroc": candidate["auroc"] - baseline["auroc"] if available else None,
            "threshold_metrics": {comparison: {
                metric: candidate["threshold_metrics"][comparison][metric]
                - baseline["threshold_metrics"][comparison][metric] if available else None
                for metric in METRICS[1:]} for comparison in ("ge", "gt")}})
    undefined = sum(cell["status"] != "computed" for cell in cells)
    return {"schema": "physiop300_metric_cells_v1", "task_id": "PAPER-paper-method-023",
            "status": "complete_metric_cells" if not undefined else "complete_panel_with_undefined_metrics",
            "qualification": "software_component_only_not_source_calibrated",
            "support": supports, "repetitions": repetitions, "methods": list(METHODS),
            "cells": cells, "candidate_minus_reference": deltas,
            "undefined_cells": undefined, "source_panel_aggregate": None,
            "aggregate_limit": "Source epoch selection and fold-to-run reduction remain unresolved; no pooling or mean invented.",
            "input_limit": "Exact support relative to operator roster only; source event coverage, biological identity, LOSO training, exposure and model provenance require separate qualification.",
            "threshold_limit": "Both >=0.5 (ge) and >0.5 (gt) are reported until source PyHealth dependency parity is established.",
            "independent_unit": "biological participant, unresolved mapping from nominal subject tokens",
            "paper_improvement_established": False}



def score_reproduction_panel(roster, predictions):
    """Compute the original four-method 108-cell reproduction input panel.

    Method names describe the submitted outputs; they do not authenticate model
    execution or AI provenance. This route adds no candidate or copied fifth
    method and does not invent the unresolved fold-to-run aggregate.
    """
    repetitions, cells, _computed, supports = _metric_cells(
        roster, predictions, SOURCE_METHODS, "physiop300_reproduction_predictions_v1")
    undefined = sum(cell["status"] != "computed" for cell in cells)
    return {"schema": "physiop300_reproduction_metric_cells_v1",
            "task_id": "PAPER-paper-method-023", "panel_role": "original_four_method_reproduction",
            "status": "complete_metric_cells" if not undefined else "complete_panel_with_undefined_metrics",
            "qualification": "software_component_only_not_source_calibrated",
            "support": supports, "repetitions": repetitions, "methods": list(SOURCE_METHODS),
            "cells": cells, "undefined_cells": undefined, "source_panel_aggregate": None,
            "aggregate_limit": "Source epoch selection, fold-to-run reduction and repetition SD remain unresolved; no aggregate or reproduced finding is inferred.",
            "input_limit": "Exact support relative to operator roster only; source event coverage, biological identity, LOSO training, exposure and model provenance require separate qualification.",
            "threshold_limit": "Both >=0.5 (ge) and >0.5 (gt) are reported until source PyHealth dependency parity is established.",
            "independent_unit": "biological participant, unresolved mapping from nominal subject tokens",
            "paper_reproduction_established": False}


def load_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON member")
            value[key] = item
        return value

    def reject_constant(value):
        raise PanelError("nonfinite JSON constant")

    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=reject_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-roster", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--panel", choices=("improvement", "reproduction"), default="improvement",
                        help="135 candidate/reference cells or original 108 method cells; no scientific win decision")
    args = parser.parse_args()
    try:
        scorer = score_panel if args.panel == "improvement" else score_reproduction_panel
        result = scorer(load_json(args.operator_roster), load_json(args.predictions))
    except (PanelError, OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(2, "Panel rejected: " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
