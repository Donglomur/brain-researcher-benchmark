#!/usr/bin/env python3
"""Score one complete original Volume native export against operator metadata."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import binding as b

PROFILE = "original-volume-native-score-v1"


def binary_metrics(labels, probabilities):
    """Native index-1 ROC-AUC and F1, including half-credit score ties.

    Work directly in the author's native class orientation. Inverting tiny
    probabilities with 1-p can destroy ranking information. The caller validates
    the native labels against independently supplied operator labels first.
    """
    b.require(isinstance(labels, list) and isinstance(probabilities, list) and
              len(labels) == len(probabilities) and labels, "metric arrays differ or are empty")
    b.require(all(type(y) is int and y in (0, 1) for y in labels), "invalid binary labels")
    b.require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1
                  for p in probabilities), "invalid probabilities")
    positives = sum(labels)
    negatives = len(labels) - positives
    b.require(positives and negatives, "ROC-AUC requires both classes")

    ordered = sorted(zip(probabilities, labels))
    wins_twice = 0
    negatives_below = 0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        positive_ties = sum(y for _, y in ordered[index:end])
        negative_ties = end - index - positive_ties
        wins_twice += positive_ties * (2 * negatives_below + negative_ties)
        negatives_below += negative_ties
        index = end

    # np.round(p), used by the source task, rounds exactly 0.5 to 0.
    # For finite probabilities in [0,1] it is equivalent to p > 0.5.
    tp = sum(y == 1 and p > 0.5 for y, p in zip(labels, probabilities))
    fp = sum(y == 0 and p > 0.5 for y, p in zip(labels, probabilities))
    fn = positives - tp
    return {"roc_auc": wins_twice / (2 * positives * negatives),
            "f1_native_index1": 2 * tp / (2 * tp + fp + fn),
            "n_test_rows": len(labels), "n_native_index1": positives,
            "n_native_index0": negatives}


def score_native(binding, native):
    """Validate and score all 49 original subject/count runs for one method.

    This is a numeric component, not complete method/control-panel admission.
    Historical authenticity and runtime identity remain the binder's limitations.
    """
    bound = b.bind_native(binding, native)
    per_run = []
    by_count = {str(count): [] for count in b.COUNTS}
    for subject in b.TRIALS:
        for count in b.COUNTS:
            run = native["runs"][f"{subject}/{count}"]
            metrics = binary_metrics(run["labels"], run["predicts"])
            per_run.append({"subject": subject, "electrode_count": count,
                            "native_high_rms_index": run["label2idx"]["True"], **metrics})
            by_count[str(count)].append(metrics["roc_auc"])

    summaries = []
    for count in b.COUNTS:
        values = by_count[str(count)]
        n = len(values)
        mean = math.fsum(values) / n
        # Explicit sample-SEM convention. Paper states SEM but does not expose
        # the exact estimator/seed treatment; do not imply historical parity.
        sem = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (n * (n - 1)))
        summaries.append({"electrode_count": count, "n_subjects": n,
                          "subject_mean_roc_auc": mean,
                          "subject_sem_ddof1_roc_auc": sem})
    return {"task_id": b.TASK, "profile": PROFILE, "source_revision": b.REVISION,
            "binding_sha256": binding["binding_sha256"],
            "native_content_sha256": bound["native_content_sha256"],
            "endpoint": "rms", "per_subject_count": per_run,
            "by_electrode_count": summaries, "primary_electrode_count": 90,
            "aggregation": "equal_subject_mean_no_word_pooling",
            "sem_convention": "sample_subject_sd_ddof1_divided_by_sqrt_7",
            "historical_sem_estimator_verified": False,
            "scope": "one_method_numeric_scores_not_reproduction_or_improvement_admission"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binding", help="operator-only binding from binding.py prepare")
    parser.add_argument("native", help="complete native-runs JSON consumed by binding.py bind-native")
    parser.add_argument("output", help="numeric summary JSON; keep operator-controlled")
    args = parser.parse_args()
    result = score_native(b.read_json(args.binding)[0], b.read_json(args.native)[0])
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
