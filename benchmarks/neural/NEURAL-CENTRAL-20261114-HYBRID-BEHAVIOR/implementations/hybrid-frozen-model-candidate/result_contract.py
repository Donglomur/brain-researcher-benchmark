"""Complete 4,884-episode successor result; no subset scoring or gain requirement."""
from source_binding import need
import math
import json
import time


STATUS = "COMPLETE_HISTORICAL_REFERENCE_PROTECTED_REPLAY"
CANDIDATE_STATUS = "COMPLETE_FROZEN_MODEL_CANDIDATE_EVALUATION"


def validate_candidate(value, lock_sha, identity):
    """Preserve every original completion guard, with a distinct candidate status."""
    need(type(value) is dict and value.get("status") == CANDIDATE_STATUS and
         value.get("evaluation_arm") == "candidate_frozen_models" and
         value.get("candidate_program") == identity and type(identity) is dict,
         "complete bound candidate arm")
    reference_shape = dict(value, status=STATUS)
    validate(reference_shape, lock_sha)
    score = value["participant_summary"]
    expected = {"participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135}
    need(all(type(score.get(k)) is int and score[k] == n for k, n in expected.items()),
         "exact full candidate population")
    need(set(score.get("subject_mean_nll", {})) == {str(s) for s in range(1, 21)} and
         set(score.get("session_mean_nll", {})) == {str(s) + ":" + str(k) for s in range(1, 21) for k in range(1, 5)},
         "all candidate people and sessions")
    return True


# Arithmetic integrated from ../hybrid-candidate-score-reconciliation-v2.
# Historical result/containment and reference replay functions remain unchanged.
_CANDIDATE_COUNTS = {"participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135}
_CANDIDATE_TEXT = {
    "schema": "hybrid-protected-main-score-v1",
    "scoring_unit_for_uncertainty": "participant, not row/fold/coding",
    "claim": "conditional next-action prediction on selected completed two-option trials",
}
_CANDIDATE_LOSS_NAMES = (
    "primary_subject_session_mean_nll", "trial_balanced_nll", "decision_weighted_nll",
)
_CANDIDATE_RATE_NAMES = ("accuracy", "macro_action_recall", "stop_brier")
_CANDIDATE_KEYS = frozenset(_CANDIDATE_COUNTS) | frozenset(_CANDIDATE_TEXT) | frozenset(_CANDIDATE_LOSS_NAMES + _CANDIDATE_RATE_NAMES) | {
    "subject_mean_nll", "session_mean_nll", "per_action_recall", "confusion",
    "benchmark_ready", "scientific_count_delta",
}


def _candidate_number(value, name, *, rate=False):
    # These are outputs of the pinned scorer, which always emits Python floats.
    need(type(value) is float and math.isfinite(value) and value >= 0,
         name + ": finite nonnegative scorer float required")
    if rate:
        need(value <= 1, name + ": value exceeds one")
    return value


def validate_candidate_score(score):
    """Validate the actual 20-person/80-session score, with no subset override.

    Return the four true-action supports. Exact equality is intentional for
    arithmetic computed by the same pinned Python scorer. This is not a
    tolerance-based importer for independently rounded table values.
    """
    need(type(score) is dict and set(score) == _CANDIDATE_KEYS, "exact complete score schema")
    for key, value in _CANDIDATE_COUNTS.items():
        need(type(score[key]) is int and score[key] == value, "complete population: " + key)
    for key, value in _CANDIDATE_TEXT.items():
        need(type(score[key]) is str and score[key] == value, "unchanged score policy: " + key)
    need(score["benchmark_ready"] is False, "score cannot qualify benchmark readiness")
    need(type(score["scientific_count_delta"]) is int and score["scientific_count_delta"] == 0,
         "unchanged scientific count")
    for key in _CANDIDATE_LOSS_NAMES:
        _candidate_number(score[key], key)
    for key in _CANDIDATE_RATE_NAMES:
        _candidate_number(score[key], key, rate=True)

    subjects, sessions = score["subject_mean_nll"], score["session_mean_nll"]
    need(type(subjects) is dict and set(subjects) == {str(s) for s in range(1, 21)},
         "all 20 named participants required")
    need(type(sessions) is dict and
         set(sessions) == {str(s) + ":" + str(k) for s in range(1, 21) for k in range(1, 5)},
         "all 80 named held sessions required")
    for key, value in sessions.items():
        _candidate_number(value, "session NLL " + key)
    for s in range(1, 21):
        key = str(s)
        _candidate_number(subjects[key], "participant NLL " + key)
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
    need(sum(supports) == _CANDIDATE_COUNTS["decisions"], "confusion accounts for every decision")
    # consumer.validate_decisions requires one final class-3/4 decision, and
    # forbids any preceding terminal decision, in each completed trial.
    need(supports[2] + supports[3] == _CANDIDATE_COUNTS["trials"],
         "exactly one terminal action per completed trial")
    recalls = score["per_action_recall"]
    need(type(recalls) is list and len(recalls) == 4, "four action recalls required")
    defined = []
    for i, support in enumerate(supports):
        if support == 0:
            need(recalls[i] is None, "absent-action recall must remain undefined")
        else:
            _candidate_number(recalls[i], "action recall " + str(i + 1), rate=True)
            need(recalls[i] == matrix[i][i] / support, "action recall disagrees with confusion")
            defined.append(recalls[i])
    need(score["macro_action_recall"] == math.fsum(defined) / len(defined),
         "macro recall averages exactly the defined actions")
    need(score["accuracy"] == sum(matrix[i][i] for i in range(4)) / _CANDIDATE_COUNTS["decisions"],
         "accuracy disagrees with confusion")
    return supports



def reconcile_candidate(score, historical, comparison, scoring):
    """Drop-in reconciliation signature; retain the original bootstrap exactly.

    ``scoring`` is the existing authenticated runner/scoring.py module.
    Nothing here chooses a comparator, imposes an improvement threshold, or
    changes the outer evaluator's candidate completion/containment conditions.
    """
    support = validate_candidate_score(score)
    reference_support = validate_candidate_score(historical)
    need(support == reference_support, "candidate/reference true-action support differs")
    expected = scoring.paired_comparison(score, historical)
    try:
        encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        matches = encode(comparison) == encode(expected)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("finite JSON paired comparison required") from exc
    need(matches, "trusted recomputed paired participant comparison")
    return expected


def validate(value, lock_sha):
    need(type(value) is dict and value.get("status") == STATUS and value.get("error") is None,
         "natural successful complete worker")
    need(value.get("source_lock_sha256") == lock_sha and value.get("new_fits") == 0 and
         type(value.get("new_fits")) is int and value.get("reused_folds") == 80,
         "exact no-refit successor")
    need(value.get("signals_received") == [] and value.get("episodes_registered") == 4884 and
         value.get("all_registered_episodes_closed") is True, "complete owned episode family")
    need(value.get("participant_campaign_run") is True and value.get("scientific_count_delta") == 0,
         "one existing task; actual complete participant path")
    need(value.get("reuse_receipt") and value.get("participant_result"), "mandatory complete result and origin receipts")
    summary = value["participant_summary"]
    need((summary["participants"], summary["sessions"], summary["trials"], summary["decisions"]) ==
         (20, 80, 4884, 163135), "complete scientific score population")
    need(value["outer_recovery_still_required"] is True, "worker cannot self-certify outer recovery")
    return True


def reconcile_score(score, historical):
    """Reference replay construction parity, not an improvement threshold."""
    need(set(score) == set(historical), "unchanged complete score schema")
    def same(left, right):
        if type(left) is dict and type(right) is dict:
            return set(left) == set(right) and all(same(left[k], right[k]) for k in left)
        if type(left) is list and type(right) is list:
            return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
        if type(left) is float and type(right) is float:
            return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= 1e-11
        return type(left) is type(right) and left == right
    need(same(score, historical), "whole reference replay score parity within admitted scalar tolerance")
    return True


def finish(outcome, eligible, deadline, signals, capture, emit, *, clock=time.monotonic, announce=print):
    """Terminal conjunction: durable decision + natural zero exit + no invalidation.

    A provisional OUTCOME is never sufficient. Late time/signal observations
    after either durable write or terminal stdout invalidate the decision and
    return nonzero. The external caller must also observe natural zero exit.
    """
    def admitted():
        return not signals and clock() < deadline
    ready = eligible and admitted()
    outcome["status"] = "PROVISIONAL_COMPLETE" if ready else "FAILED_PRESERVED"
    outcome["original_deadline"] = deadline
    outcome_pin = emit(capture / "OUTCOME.json", outcome)
    ready = ready and admitted()
    decision = {"schema": "hybrid-terminal-complete-decision-v1",
        "status": "COMPLETE" if ready else "FAILED_PRESERVED", "outcome": outcome_pin,
        "original_deadline": deadline, "decision_monotonic": clock(),
        "natural_outer_zero_exit_also_required": True,
        "absence_of_terminal_invalidation_also_required": True}
    emit(capture / "FINAL_DECISION.json", decision)
    invalidated = False
    def invalidate():
        nonlocal invalidated
        if not invalidated:
            emit(capture / "TERMINAL_INVALIDATION.json", {"schema": "hybrid-terminal-invalidation-v1",
                "status": "FAILED_PRESERVED", "reason": "late deadline or signal at terminal checkpoint",
                "observed_monotonic": clock(), "original_deadline": deadline, "signals_received": list(signals)})
            invalidated = True
    ready = ready and admitted()
    if decision["status"] == "COMPLETE" and not ready:
        invalidate()
    announce(json.dumps({"status": "COMPLETE" if ready else "FAILED_PRESERVED", "new_fits": 0, "no_retry": True}))
    if ready and not admitted():
        ready = False
        invalidate()
    return 0 if ready else 1
