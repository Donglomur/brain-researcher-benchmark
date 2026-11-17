"""Scientific invariants for the complete Hybrid candidate score.

This is an operator-side replacement for result_contract.reconcile_candidate.
It does not inspect observations, predictions, or private labels. The caller
must retain the existing authenticated result/containment/provenance checks.
"""
import json
import math


class ScoreError(ValueError):
    """A complete reported score is inconsistent with the fixed task."""


COUNTS = {"participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135}
TEXT = {
    "schema": "hybrid-protected-main-score-v1",
    "scoring_unit_for_uncertainty": "participant, not row/fold/coding",
    "claim": "conditional next-action prediction on selected completed two-option trials",
}
LOSS_NAMES = (
    "primary_subject_session_mean_nll", "trial_balanced_nll", "decision_weighted_nll",
)
RATE_NAMES = ("accuracy", "macro_action_recall", "stop_brier")
KEYS = frozenset(COUNTS) | frozenset(TEXT) | frozenset(LOSS_NAMES + RATE_NAMES) | {
    "subject_mean_nll", "session_mean_nll", "per_action_recall", "confusion",
    "benchmark_ready", "scientific_count_delta",
}


def need(condition, message):
    if not condition:
        raise ScoreError(message)


def number(value, name, *, rate=False):
    # These are outputs of the pinned scorer, which always emits Python floats.
    need(type(value) is float and math.isfinite(value) and value >= 0,
         name + ": finite nonnegative scorer float required")
    if rate:
        need(value <= 1, name + ": value exceeds one")
    return value


def validate_score(score):
    """Validate the actual 20-person/80-session score, with no subset override.

    Return the four true-action supports. Exact equality is intentional for
    arithmetic computed by the same pinned Python scorer. This is not a
    tolerance-based importer for independently rounded table values.
    """
    need(type(score) is dict and set(score) == KEYS, "exact complete score schema")
    for key, value in COUNTS.items():
        need(type(score[key]) is int and score[key] == value, "complete population: " + key)
    for key, value in TEXT.items():
        need(type(score[key]) is str and score[key] == value, "unchanged score policy: " + key)
    need(score["benchmark_ready"] is False, "score cannot qualify benchmark readiness")
    need(type(score["scientific_count_delta"]) is int and score["scientific_count_delta"] == 0,
         "unchanged scientific count")
    for key in LOSS_NAMES:
        number(score[key], key)
    for key in RATE_NAMES:
        number(score[key], key, rate=True)

    subjects, sessions = score["subject_mean_nll"], score["session_mean_nll"]
    need(type(subjects) is dict and set(subjects) == {str(s) for s in range(1, 21)},
         "all 20 named participants required")
    need(type(sessions) is dict and
         set(sessions) == {str(s) + ":" + str(k) for s in range(1, 21) for k in range(1, 5)},
         "all 80 named held sessions required")
    for key, value in sessions.items():
        number(value, "session NLL " + key)
    for s in range(1, 21):
        key = str(s)
        number(subjects[key], "participant NLL " + key)
        need(subjects[key] == math.fsum(sessions[key + ":" + str(k)] for k in range(1, 5)) / 4,
             "equal four-session participant aggregation")
    need(score["primary_subject_session_mean_nll"] == math.fsum(subjects.values()) / 20,
         "equal 20-participant primary aggregation")
    # The decision-weighted score is a positive weighted mean of session means.
    # Eight ULPs allow the separate fsum/division paths used by the scorer.
    lower, upper = min(sessions.values()), max(sessions.values())
    rounding = 8 * math.ulp(upper)
    need(lower - rounding <= score["decision_weighted_nll"] <= upper + rounding,
         "decision-weighted NLL lies outside session NLL range")

    matrix = score["confusion"]
    need(type(matrix) is list and len(matrix) == 4, "four-action confusion matrix")
    for row in matrix:
        need(type(row) is list and len(row) == 4 and
             all(type(x) is int and x >= 0 for x in row),
             "four nonnegative integer confusion counts per action")
    supports = tuple(sum(row) for row in matrix)
    need(sum(supports) == COUNTS["decisions"], "confusion accounts for every decision")
    # consumer.validate_decisions requires one final class-3/4 decision, and
    # forbids any preceding terminal decision, in each completed trial.
    need(supports[2] + supports[3] == COUNTS["trials"],
         "exactly one terminal action per completed trial")
    recalls = score["per_action_recall"]
    need(type(recalls) is list and len(recalls) == 4, "four action recalls required")
    defined = []
    for i, support in enumerate(supports):
        if support == 0:
            need(recalls[i] is None, "absent-action recall must remain undefined")
        else:
            number(recalls[i], "action recall " + str(i + 1), rate=True)
            need(recalls[i] == matrix[i][i] / support, "action recall disagrees with confusion")
            defined.append(recalls[i])
    need(score["macro_action_recall"] == math.fsum(defined) / len(defined),
         "macro recall averages exactly the defined actions")
    need(score["accuracy"] == sum(matrix[i][i] for i in range(4)) / COUNTS["decisions"],
         "accuracy disagrees with confusion")
    return supports


def reconcile_candidate(score, historical, comparison, scoring):
    """Drop-in reconciliation signature; retain the original bootstrap exactly.

    ``scoring`` must be the existing authenticated runner/scoring.py module.
    Nothing here chooses a comparator, imposes an improvement threshold, or
    changes the outer evaluator's candidate completion/containment conditions.
    """
    support = validate_score(score)
    reference_support = validate_score(historical)
    need(support == reference_support, "candidate/reference true-action support differs")
    expected = scoring.paired_comparison(score, historical)
    try:
        encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        matches = encode(comparison) == encode(expected)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ScoreError("finite JSON paired comparison required") from exc
    need(matches, "trusted recomputed paired participant comparison")
    return expected
