"""Operator-side metrics for the complete original REVE PhysioNet-MI test panel.

This module has no model or signal dependencies. ``score_predictions(rows, targets)``
joins predictions to operator-owned target records, each with ``event_id``, integer
``participant`` and integer ``label`` (0..3). A prediction has ``event_id`` and
exactly one of ``prediction`` (integer 0..3) or ``scores`` (four finite real
logits/probabilities in class order). Score ties select the first class, as argmax
does in the released evaluation code. All 20 original test participants are
required. Event completeness is relative to the authenticated target manifest;
the preparing operator must authenticate that manifest, not supply a subset.

Pooled event balanced accuracy is the primary endpoint. Per-participant metrics
and participant-cluster intervals are companions, never replacements for it.
Numerical comparison does not authenticate historical recipe or checkpoints and
cannot, by itself, establish reproduction, improvement, or current SOTA.
"""

from __future__ import annotations

import math
from numbers import Real
import random
import re
import statistics


TEST_PARTICIPANTS = tuple(range(90, 110))
CLASSES = (0, 1, 2, 3)
METRICS = ("balanced_accuracy", "cohen_kappa", "weighted_f1", "accuracy")
PUBLISHED_BASELINE = {
    "balanced_accuracy_mean": 0.6480,
    "balanced_accuracy_reported_sd": 0.0140,
    "source": "REVE NeurIPS 2025 Table 12, REVE-Base, PhysioNet-MI",
    "type": "published_aggregate_not_local_measurement",
    "run_roster_and_sd_ddof": "unresolved",
}


class MetricError(ValueError):
    """Inputs cannot be compared on the complete original test panel."""


def _require(condition, message):
    if not condition:
        raise MetricError(message)


def _event_id(row):
    _require(isinstance(row, dict), "each row must be an object")
    event_id = row.get("event_id")
    _require(isinstance(event_id, str) and bool(event_id.strip()),
             "event_id must be a nonempty string")
    return event_id


def _class(value, name):
    # bool is an int subclass but is not a valid scientific class encoding.
    _require(type(value) is int and value in CLASSES, name + " must be an integer in 0..3")
    return value


def _prediction(row):
    _require(("prediction" in row) != ("scores" in row),
             "each prediction requires exactly one of prediction or scores")
    if "prediction" in row:
        return _class(row["prediction"], "prediction")
    scores = row["scores"]
    _require(isinstance(scores, (tuple, list)) and len(scores) == 4,
             "scores must contain exactly four values in class order")
    _require(all(isinstance(value, Real) and not isinstance(value, bool)
                 and math.isfinite(value) for value in scores), "scores must be finite real values")
    return max(CLASSES, key=lambda index: scores[index])


def _join(rows, targets):
    target_map = {}
    for target in targets:
        event_id = _event_id(target)
        _require(event_id not in target_map, "duplicate target event_id: " + event_id)
        participant = target.get("participant")
        _require(type(participant) is int and participant in TEST_PARTICIPANTS,
                 "target participant must be an integer in original test IDs 90..109")
        target_map[event_id] = (participant, _class(target.get("label"), "target label"))
    _require({person for person, _ in target_map.values()} == set(TEST_PARTICIPANTS),
             "targets must contain every original test participant 90..109")
    _require({label for _, label in target_map.values()} == set(CLASSES),
             "pooled targets must contain all four original classes")
    prediction_map = {}
    for row in rows:
        event_id = _event_id(row)
        _require(event_id not in prediction_map, "duplicate prediction event_id: " + event_id)
        prediction_map[event_id] = _prediction(row)
    missing = set(target_map) - set(prediction_map)
    extra = set(prediction_map) - set(target_map)
    _require(not missing and not extra,
             f"prediction/target event IDs differ: {len(missing)} missing, {len(extra)} extra")
    return [(event_id, person, truth, prediction_map[event_id])
            for event_id, (person, truth) in target_map.items()]


def _empty_confusion():
    return [[0] * 4 for _ in CLASSES]


def _metrics(matrix):
    """Rows are true classes; columns are predicted classes; missing recall is null."""
    support = [sum(row) for row in matrix]
    predicted = [sum(row[column] for row in matrix) for column in CLASSES]
    total = sum(support)
    _require(total > 0, "cannot score an empty confusion matrix")
    recall = [matrix[c][c] / support[c] if support[c] else None for c in CLASSES]
    f1 = [(2 * matrix[c][c] / (support[c] + predicted[c])
           if support[c] + predicted[c] else 0.0) for c in CLASSES]
    accuracy = sum(matrix[c][c] for c in CLASSES) / total
    expected_agreement = sum(support[c] * predicted[c] for c in CLASSES) / total**2
    return {
        "n_events": total,
        "balanced_accuracy": sum(recall) / 4 if all(value is not None for value in recall) else None,
        "cohen_kappa": ((accuracy - expected_agreement) / (1 - expected_agreement)
                        if expected_agreement != 1 else None),
        "weighted_f1": sum(support[c] * f1[c] for c in CLASSES) / total,
        "accuracy": accuracy,
        "class_support": support,
        "class_recall": recall,
        "class_f1": f1,
        "confusion_matrix": matrix,
    }


def _score_joined(joined):
    pooled = _empty_confusion()
    participant_matrices = {person: _empty_confusion() for person in TEST_PARTICIPANTS}
    for _, person, truth, predicted in joined:
        pooled[truth][predicted] += 1
        participant_matrices[person][truth][predicted] += 1
    return {
        "schema": "reve-original-physionet-score-v1",
        "primary_metric": "balanced_accuracy",
        "primary_aggregation": "pool_all_test_events_then_mean_four_class_recalls",
        "class_order": ["left_fist", "right_fist", "both_fists", "feet"],
        "pooled": _metrics(pooled),
        "per_participant": {str(person): _metrics(matrix)
                            for person, matrix in participant_matrices.items()},
        "historical_recipe_verified": False,
        "scientific_claim": "numeric_scoring_only",
    }


def score_predictions(rows, targets):
    """Score a complete event-ID bijection against an operator-owned test manifest.

    Target metadata beyond the required fields is ignored. All results are JSON
    serializable without NaN. A participant lacking a class has null balanced
    accuracy in its companion summary, rather than silently averaging fewer
    classes; the complete pooled panel must contain all four classes.
    """
    return _score_joined(_join(rows, targets))


def _quantile(values, probability):
    values = sorted(values)
    index = (len(values) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _cluster_bootstrap(candidate, author, samples, seed):
    _require(type(samples) is int and 2 <= samples <= 100_000,
             "bootstrap_samples must be an integer from 2 to 100000, or 0 to disable")
    _require(type(seed) is int and 0 <= seed < 2**64,
             "bootstrap_seed must be an integer in 0..2**64-1")
    generator = random.Random(seed)
    differences = {metric: [] for metric in METRICS}
    undefined = {metric: 0 for metric in METRICS}
    for _ in range(samples):
        selected = generator.choices(TEST_PARTICIPANTS, k=len(TEST_PARTICIPANTS))
        results = []
        for scored in (candidate, author):
            pooled = _empty_confusion()
            for person in selected:
                matrix = scored["per_participant"][str(person)]["confusion_matrix"]
                for truth in CLASSES:
                    for predicted in CLASSES:
                        pooled[truth][predicted] += matrix[truth][predicted]
            results.append(_metrics(pooled))
        for metric in METRICS:
            left, right = results[0][metric], results[1][metric]
            if left is None or right is None:
                undefined[metric] += 1
            else:
                differences[metric].append(left - right)
    return {
        "method": "paired_participant_cluster_percentile_bootstrap",
        "resampled_unit": "participant",
        "replicates": samples,
        "seed": seed,
        "confidence_level": 0.95,
        "quantile_method": "linear_interpolation_at_(n-1)*p",
        "estimand": "candidate_minus_author_pooled_event_metric",
        "training_seed_uncertainty_included": False,
        "interpretation": "descriptive_interval_not_a_predeclared_paper_win_rule",
        "intervals": {
            metric: {
                "low": _quantile(values, 0.025) if not undefined[metric] else None,
                "high": _quantile(values, 0.975) if not undefined[metric] else None,
                "undefined_replicates": undefined[metric],
            }
            for metric, values in differences.items()
        },
    }


def compare_predictions(candidate_rows, author_rows, targets, *, panel_identity,
                        candidate_panel_identity, author_panel_identity,
                        bootstrap_samples=2000, bootstrap_seed=0):
    """Compare frozen predictions on one manifest, without declaring a paper win.

    Panel identities are the same authenticated preparation-receipt SHA-256, as
    verified by the caller. This numerical function checks identity equality; it
    does not independently prove model/checkpoint or receipt authenticity. The
    optional bootstrap resamples the same 20 participants for both methods and
    recomputes pooled metrics, preserving unequal participant event counts.
    """
    for value in (panel_identity, candidate_panel_identity, author_panel_identity):
        _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
                 "panel identities must be lowercase SHA-256 strings")
    _require(panel_identity == candidate_panel_identity == author_panel_identity,
             "candidate, author and targets must use the same frozen panel")
    targets = list(targets)
    candidate = score_predictions(candidate_rows, targets)
    author = score_predictions(author_rows, targets)
    _require(type(bootstrap_samples) is int and bootstrap_samples >= 0,
             "bootstrap_samples must be a nonnegative integer")
    result = {
        "schema": "reve-original-physionet-comparison-v1",
        "panel_identity": panel_identity,
        "published_baseline": dict(PUBLISHED_BASELINE),
        "candidate": candidate,
        "author": author,
        "candidate_minus_author": {
            metric: candidate["pooled"][metric] - author["pooled"][metric]
            for metric in METRICS
        },
        "candidate_minus_published_balanced_accuracy": candidate["pooled"]["balanced_accuracy"] - 0.6480,
        "author_minus_published_balanced_accuracy": author["pooled"]["balanced_accuracy"] - 0.6480,
        "historical_recipe_verified": False,
        "paper_win": None,
        "scientific_claim": "paired_numeric_comparison_only",
        "uncertainty": None,
    }
    if bootstrap_samples:
        result["uncertainty"] = _cluster_bootstrap(candidate, author, bootstrap_samples, bootstrap_seed)
    return result


def aggregate_runs(rows):
    """Describe an explicit run roster without choosing the paper's unknown ddof.

    Each row requires a unique ``run_id``, a distinct integer ``seed``, and the
    four scalar ``METRICS`` from that run's pooled score. Both population and
    sample SD are returned; sample SD is null for a single run. Checkpoint and
    recipe qualification remain the enclosing operator's responsibility.
    """
    rows = list(rows)
    _require(bool(rows), "at least one run is required")
    ids, seeds = set(), set()
    for row in rows:
        _require(isinstance(row, dict), "run rows must be objects")
        run_id, seed = row.get("run_id"), row.get("seed")
        _require(isinstance(run_id, str) and bool(run_id.strip()) and run_id not in ids,
                 "run_id must be nonempty and unique")
        _require(type(seed) is int and seed >= 0 and seed not in seeds,
                 "independent run seeds must be nonnegative and distinct")
        ids.add(run_id)
        seeds.add(seed)
        for metric in METRICS:
            value = row.get(metric)
            lower = -1 if metric == "cohen_kappa" else 0
            _require(isinstance(value, Real) and not isinstance(value, bool)
                     and math.isfinite(value) and lower <= value <= 1,
                     "invalid run metric: " + metric)
    return {
        "schema": "reve-original-physionet-run-summary-v1",
        "n_runs": len(rows),
        "run_roster": [{"run_id": row["run_id"], "seed": row["seed"]} for row in rows],
        "metrics": {
            metric: {
                "mean": statistics.fmean(row[metric] for row in rows),
                "sd_population_ddof0": statistics.pstdev(row[metric] for row in rows),
                "sd_sample_ddof1": statistics.stdev(row[metric] for row in rows) if len(rows) > 1 else None,
            }
            for metric in METRICS
        },
        "historical_run_roster_and_sd_ddof": "unresolved",
        "published_baseline": dict(PUBLISHED_BASELINE),
        "scientific_claim": "explicit_roster_summary_only",
    }
