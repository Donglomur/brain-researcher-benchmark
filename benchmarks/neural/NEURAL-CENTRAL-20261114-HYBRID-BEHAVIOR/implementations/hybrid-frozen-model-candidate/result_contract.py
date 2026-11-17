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


def reconcile_candidate(score, historical, comparison, scoring):
    """No gain threshold: use the pinned scorer's original paired-person bootstrap."""
    def shape(left, right):
        if type(right) is dict:
            return type(left) is dict and set(left) == set(right) and all(shape(left[k], right[k]) for k in right)
        if type(right) is list:
            return type(left) is list and len(left) == len(right) and all(shape(a, b) for a, b in zip(left, right))
        if type(right) is float:
            return type(left) is float and math.isfinite(left)
        if type(right) is int:
            return type(left) is int and left >= 0
        return type(left) is type(right) and left == right
    need(shape(score, historical), "complete finite candidate score schema")
    for name in ("participants", "sessions", "trials", "decisions", "scientific_count_delta"):
        need(type(score[name]) is int and score[name] == historical[name], "unchanged candidate population/policy")
    subject = score["subject_mean_nll"]
    sessions = score["session_mean_nll"]
    need(set(subject) == {str(s) for s in range(1, 21)} and
         set(sessions) == {str(s) + ":" + str(k) for s in range(1, 21) for k in range(1, 5)},
         "complete candidate scored support")
    need(all(x >= 0 for x in subject.values()) and all(x >= 0 for x in sessions.values()), "nonnegative candidate NLL")
    need(all(subject[str(s)] == math.fsum(sessions[str(s) + ":" + str(k)] for k in range(1, 5)) / 4
             for s in range(1, 21)) and score["primary_subject_session_mean_nll"] == math.fsum(subject.values()) / 20,
         "unchanged equal-person/session aggregation")
    expected = scoring.paired_comparison(score, historical)
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    need(encode(comparison) == encode(expected), "trusted recomputed candidate paired comparison")
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
