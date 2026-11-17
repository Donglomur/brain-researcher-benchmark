"""Owner-only exact losses and explicit qualification refusal.

No metric from this module is a scientific result until the authentic task has
been admitted and run. Source construction performs neither operation.
"""
from __future__ import annotations

import math
import hashlib
import hmac
from dataclasses import dataclass

from helsinki_profile import COORDINATE_ID, profile_identity
from helsinki_fixture import FixtureCorpus, FIXTURE_PROTOCOL_ID, FIXTURE_COORDINATE_ID

from helsinki_intake import (Corpus, INFANTS, PROTOCOL_ID, FLAG_RULE, QualityFlags, Refusal,
                             canonical, digest, finite, require)
from helsinki_protocol import (CONDITIONS, Session, EngineeringSession, roles, _checked_lineage,
                              case_identifier, session_protocol_id)


STRATA = ("no_flagged_context", "earlier_context_flagged_final_unflagged", "final_second_flagged")


def original_case_record(session, case_id):
    original = session.issued[case_id]
    signed = {k: v for k, v in original.items() if k != "owner_hmac"}
    expected = hmac.new(session.key, canonical(signed), hashlib.sha256).hexdigest()
    require(hmac.compare_digest(original.get("owner_hmac", ""), expected),
            "issued_original_record_changed")
    require(original["case_id"] == case_id and original["quality_flags"]["rule"] == FLAG_RULE and
            original.get("protocol_sha256") == session.protocol_sha256 and
            original.get("lineage_sha256") == session.lineage_sha256 and
            original.get("profile_sha256") == session.profile_sha256,
            "issued_original_identity_mismatch")
    q = original["quality_flags"]
    flags = QualityFlags(tuple(q["zero_bipolar_seconds"]), tuple(q["any_flatline_seconds"]))
    require(flags.public() == q and flags.stratum() == original["quality_stratum"],
            "quality_flag_metadata_mismatch")
    return original


def _validate_predictions(corpus, sessions, corpus_type, session_type):
    """Validate the whole five-fold prediction census before any aggregation."""
    require(type(corpus) is corpus_type and all(type(s) is session_type for s in sessions),
            "score_domain_corpus_or_session_mismatch")
    require(len(sessions) == 5 and {s.fold for s in sessions} == set(range(5)),
            "requires_all_five_folds_once")
    arm = sessions[0].arm
    control = sessions[0].signal_condition
    model = sessions[0].model_revision
    lineage = digest(_checked_lineage(corpus))
    require(all(type(s) is session_type and s.corpus is corpus and s.arm == arm and
                s.signal_condition == control and s.model_revision == model and
                s.baseline.lineage_sha256 == lineage and s.complete() for s in sessions),
            "incomplete_or_mixed_protocol_predictions")
    results = {}
    for session in sessions:
        session.validate_identity()
        require(set(session.issued) == set(session.case_map), "issued_case_census_mismatch")
        expected = {(i, k) for i in roles(session.fold)["test"] for k in corpus.seconds(i)}
        require(set(session.case_map.values()) == expected and
                len(session.case_map) == len(expected), "case_support_changed")
        for case_id, location in session.case_map.items():
            require(location not in results, "repeated_case_or_infant_across_folds")
            infant, second = location
            expected_id = case_identifier(session.key, session.fold, infant, second,
                                          session.lineage_sha256, protocol_id=session_protocol_id(session))
            require(hmac.compare_digest(case_id, expected_id), "case_map_identity_changed")
            original = original_case_record(session, case_id)
            item = session.predictions[case_id]
            require(item["issued_original_sha256"] == digest(original) and
                    item["packet_sha256"] == original["packet_sha256"],
                    "prediction_original_packet_mismatch")
            signed = {key: value for key, value in item.items() if key != "owner_receipt_hmac"}
            expected_receipt = hmac.new(session.key, canonical(signed), hashlib.sha256).hexdigest()
            require(hmac.compare_digest(item.get("owner_receipt_hmac", ""), expected_receipt),
                    "prediction_modified_after_owner_commit")
            require(item["case_id"] == case_id and item["protocol_sha256"] == session.protocol_sha256 and
                    item.get("lineage_sha256") == lineage == session.lineage_sha256 and
                    item.get("profile_sha256") == session.profile_sha256 == digest(_checked_lineage(corpus)["profile"]),
                    "prediction_protocol_mismatch")
            require(len(item["packet_sha256"]) == 64, "unbound_prediction_packet")
            if arm == CONDITIONS[1]:
                require(item["program_sha256"] == session.program_sha256 and
                        session.program_sha256 is not None, "program_pin_mismatch")
            p = finite(item["probability"])
            require(0 <= p <= 1, "probability_out_of_range")
            results[location] = p
    full = {(i, k) for i in INFANTS for k in corpus.seconds(i)}
    require(set(results) == full, "full79_denominator_changed")
    return results


def validate_predictions(corpus, sessions):
    return _validate_predictions(corpus, sessions, Corpus, Session)


def validate_engineering_predictions(corpus, sessions):
    return _validate_predictions(corpus, sessions, FixtureCorpus, EngineeringSession)


def _loss_kernel(corpus, predictions):
    """Private mathematics; caller must have validated all support and predictions."""
    rows = []
    for i in INFANTS:
        soft, disagreement, experts = [], [], [[], [], []]
        for k in corpus.seconds(i):
            p = predictions[(i, k)]
            votes = corpus.votes(i, k)
            require(len(votes) == 3 and all(type(a) is int and a in (0, 1) for a in votes),
                    "invalid_expert_reference")
            q = sum(votes) / 3.0
            soft.append((p - q) ** 2)
            disagreement.append(q * (1 - q))
            for expert, a in enumerate(votes):
                experts[expert].append((p - a) ** 2)
        count = len(corpus.seconds(i))
        require(count > 0 and len(soft) == count, "infant_denominator_missing")
        e = [math.fsum(v) / count for v in experts]
        brier = math.fsum(soft) / count
        d = math.fsum(disagreement) / count
        mean_expert = math.fsum(e) / 3
        require(math.isclose(mean_expert, brier + d, abs_tol=1e-12, rel_tol=1e-12),
                "soft_and_expert_brier_identity_failure")
        rows.append({"infant": i, "case_count": count, "soft_vote_brier": brier,
                     "expert_brier": e, "mean_expert_brier": mean_expert,
                     "expert_disagreement_constant": d})
    require(len(rows) == 79, "macro_denominator_not_79")
    macro = lambda key: math.fsum(r[key] for r in rows) / 79
    return {"infant_count": 79, "case_count": sum(r["case_count"] for r in rows),
            "soft_vote_brier": macro("soft_vote_brier"),
            "expert_brier": [math.fsum(r["expert_brier"][e] for r in rows) / 79
                             for e in range(3)],
            "mean_expert_brier": macro("mean_expert_brier"),
            "expert_disagreement_constant": macro("expert_disagreement_constant"),
            "owner_only_infant_rows": rows}


def coverage_strata(corpus, sessions, predictions):
    source = {}
    for session in sessions:
        for case_id, location in session.case_map.items():
            source[location] = original_case_record(session, case_id)
    result = {}
    for stratum in STRATA:
        rows = []
        for infant in INFANTS:
            seconds = tuple(k for k in corpus.seconds(infant)
                            if source[(infant, k)]["quality_stratum"] == stratum)
            losses = [(predictions[(infant, k)] - sum(corpus.votes(infant, k)) / 3) ** 2
                      for k in seconds]
            rows.append({"infant": infant, "case_count": len(seconds),
                         "full_primary_cases": len(corpus.seconds(infant)),
                         "coverage_fraction": len(seconds) / len(corpus.seconds(infant)),
                         "conditional_soft_vote_brier": math.fsum(losses) / len(losses)
                         if losses else None})
        # Do not hide empty-infant strata in an available-infant macro average.
        complete = all(r["case_count"] > 0 for r in rows)
        result[stratum] = {"descriptive_only": True, "required_infant_count": 79,
            "case_count": sum(r["case_count"] for r in rows),
            "infants_with_cases": sum(r["case_count"] > 0 for r in rows),
            "infant_macro_conditional_brier": math.fsum(
                r["conditional_soft_vote_brier"] for r in rows) / 79 if complete else None,
            "empty_infant_rule": "undefined full79 stratum macro; never substitute for primary",
            "owner_only_infant_rows": rows}
    require(sum(v["case_count"] for v in result.values()) == len(predictions),
            "stratum_denominator_mismatch")
    return result


def _validate_paired_arms(corpus, a_sessions, b_sessions, validator):
    validator(corpus, a_sessions)
    validator(corpus, b_sessions)
    require(all(s.arm == CONDITIONS[0] for s in a_sessions) and
            all(s.arm == CONDITIONS[1] for s in b_sessions), "wrong_paired_arm")
    a_by_fold, b_by_fold = {s.fold: s for s in a_sessions}, {s.fold: s for s in b_sessions}
    for fold in range(5):
        a, b = a_by_fold[fold], b_by_fold[fold]
        pa, pb = a.protocol_payload(), b.protocol_payload()
        pa.pop("arm")
        pb.pop("arm")
        require(pa == pb and a.case_map == b.case_map and a.order == b.order,
                "paired_protocol_input_or_baseline_mismatch")
        for case_id in a.order:
            x, y = original_case_record(a, case_id), original_case_record(b, case_id)
            require(x["packet_sha256"] == y["packet_sha256"] and
                    x["original_signal_sha256"] == y["original_signal_sha256"] and
                    x["quality_flags"] == y["quality_flags"], "paired_case_payload_mismatch")
    return {"paired_source_projection": "matched", "host_isolation_verified": False}


def _validate_control_alignment(corpus, raw_sessions, control_sessions, validator):
    validator(corpus, raw_sessions)
    validator(corpus, control_sessions)
    require(all(s.signal_condition == "recorded_eeg" for s in raw_sessions),
            "control_reference_must_be_recorded_eeg")
    raw = {s.fold: s for s in raw_sessions}
    for control in control_sessions:
        reference = raw[control.fold]
        p, q = reference.protocol_payload(), control.protocol_payload()
        for k in ("signal_condition", "noise_fit"):
            p.pop(k)
            q.pop(k)
        require(p == q and reference.case_map == control.case_map and
                reference.order == control.order, "control_protocol_mismatch")
        for case_id in reference.order:
            x, y = original_case_record(reference, case_id), original_case_record(control, case_id)
            require(x["original_signal_sha256"] == y["original_signal_sha256"] and
                    x["quality_flags"] == y["quality_flags"], "control_changed_original_flags")
    return {"original_inputs_and_flags": "matched", "host_isolation_verified": False}


def validate_paired_arms(corpus, a_sessions, b_sessions):
    return _validate_paired_arms(corpus, a_sessions, b_sessions, validate_predictions)


def validate_engineering_paired_arms(corpus, a_sessions, b_sessions):
    return _validate_paired_arms(corpus, a_sessions, b_sessions, validate_engineering_predictions)


def validate_control_alignment(corpus, raw_sessions, control_sessions):
    return _validate_control_alignment(corpus, raw_sessions, control_sessions, validate_predictions)


def validate_engineering_control_alignment(corpus, raw_sessions, control_sessions):
    return _validate_control_alignment(corpus, raw_sessions, control_sessions, validate_engineering_predictions)


def _score_full79(corpus, sessions, validator, protocol_id, coordinate_id, engineering_only):
    """Recorded-grid scorer; returns owner losses, never qualification.

    Earlier protocols remain preserved. This version scores the author-exported
    record grid; quality flags are not verified missingness or physical-clock timing.
    """
    try:
        predictions = validator(corpus, sessions)
        losses = _loss_kernel(corpus, predictions)
        strata = coverage_strata(corpus, sessions, predictions)
    except Refusal as exc:
        return {"status": "UNESTABLISHED", "protocol_id": protocol_id,
                "primary_score": None, "required_infant_count": 79,
                "reason": str(exc), "available_case_score": None,
                "engineering_only": engineering_only, "scientifically_qualified": False}
    return {"status": "SYNTHETIC_ENGINEERING_LOSS_ONLY" if engineering_only else "OWNER_LOSS_ONLY_NOT_QUALIFIED", "protocol_id": protocol_id,
            "primary_name": "recorded_grid_infant_macro_soft_vote_brier",
            "time_coordinate_id": coordinate_id, "source_grid_only": True,
            "physical_clock_verified": False,
            "lineage_sha256": digest(_checked_lineage(corpus)),
            "profile_sha256": digest(_checked_lineage(corpus)["profile"]),
            "losses": losses, "flag_based_strata": strata,
            "engineering_only": engineering_only, "scientifically_qualified": False, "original_v3_result": False,
            "unresolved_host_gates": ["target_and_network_isolation",
                "fresh_case_process_and_model_context", "no_state_between_folds_arms_controls",
                "verified_resource_accounting", "authentic_baseline_reproduction",
                "authentic_intake_and_flag_audit", "whole_task_execution"]}


def score_full79(corpus, sessions):
    return _score_full79(corpus, sessions, validate_predictions, PROTOCOL_ID, COORDINATE_ID, False)


def score_engineering_full79(corpus, sessions):
    return _score_full79(corpus, sessions, validate_engineering_predictions,
                         FIXTURE_PROTOCOL_ID, FIXTURE_COORDINATE_ID, True)


def _score_paired_full79(corpus, a_sessions, b_sessions, pair_validator, score_fn, protocol_id, engineering_only):
    try:
        pair = pair_validator(corpus, a_sessions, b_sessions)
    except Refusal as exc:
        return {"status": "UNESTABLISHED", "protocol_id": protocol_id,
                "primary_comparison": None, "reason": str(exc),
                "engineering_only": engineering_only, "scientifically_qualified": False}
    return {"protocol_id": protocol_id, "pair_admission": pair,
            "A": score_fn(corpus, a_sessions), "B": score_fn(corpus, b_sessions),
            "engineering_only": engineering_only, "scientifically_qualified": False}


def score_paired_full79(corpus, a_sessions, b_sessions):
    return _score_paired_full79(corpus, a_sessions, b_sessions, validate_paired_arms,
                               score_full79, PROTOCOL_ID, False)


def score_engineering_paired_full79(corpus, a_sessions, b_sessions):
    return _score_paired_full79(corpus, a_sessions, b_sessions, validate_engineering_paired_arms,
                               score_engineering_full79, FIXTURE_PROTOCOL_ID, True)
