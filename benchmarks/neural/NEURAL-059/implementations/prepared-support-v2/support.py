"""Original-slot integrity for NEURAL-059 primary scoring.

This checks protected preparation operands, not participant inputs. It does not
authenticate recording bytes or authorize a native run. Diagnostic label/neural
permutations deliberately do not satisfy this primary-observation contract.
"""
import hashlib
import json
import math

from _retained import load

contracts, evaluation = load()
SPLITS = ("train", "val", "test")
SIGNED = (-1., -.25, -.125, -.0625, 0., .0625, .125, .25, 1.)
BLOCKS = (.2, .5, .8)


class SupportError(ValueError):
    """Stable failure code and position; never include a protected label."""
    def __init__(self, code, session_index=None, ordinal=None):
        self.code, self.session_index, self.ordinal = code, session_index, ordinal
        super().__init__(code)


def _need(ok, code, session_index=None, ordinal=None):
    if not ok:
        raise SupportError(code, session_index, ordinal)


def _finite(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except OverflowError:
        return False


def _same(a, b):
    # In identities, bools, integers and floats are intentionally distinct.
    return json.dumps(a, sort_keys=True, separators=(",", ":"), allow_nan=False) == \
        json.dumps(b, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _indicator(actual, width, index):
    return (type(actual) is list and len(actual) == width and
            all(type(v) in (int, float) and v == int(i == index)
                for i, v in enumerate(actual)))


def case_id(session_id, source_identity, ordinal):
    token = json.dumps([session_id, source_identity, ordinal],
                       sort_keys=True, separators=(",", ":"))
    return "case_" + hashlib.sha256(token.encode()).hexdigest()


def validate_session(session, session_index):
    """Rejoin every prepared case to its original slot and raw predecessor."""
    si = session_index
    _need(type(session) is dict, "session_object", si)
    _need(session.get("status") == "source_only_unqualified" and
          session.get("structural_holds") == [], "preparation_held_or_wrong_status", si)
    slots, cases, units = (session.get(k) for k in ("slots", "cases", "unit_ids"))
    _need(type(slots) is list and slots and type(cases) is list, "original_slot_census", si)
    _need(type(units) is list and units and all(type(u) is str and u for u in units)
          and len(set(units)) == len(units), "full_unit_axis", si)
    identity = session.get("source_identity")
    _need(type(identity) is dict and set(identity) ==
          {"repository", "revision", "pipeline_sha256", "source_sha256"}, "source_identity", si)
    _need(identity["repository"] == "brainbench-org/ibl-bwb" and
          identity["revision"] == "6fbd666fe8170a2165f5198c1f490911424a654d" and
          identity["pipeline_sha256"] == "931002bcf87e2ff88a8eb2e270d963b2479971a0a7dabc3659c5098a2bec0c29" and
          session.get("source_profile") == "reviewed_6fbd_structured_v1", "source_profile", si)
    sha = identity["source_sha256"]
    _need(sha is None or (type(sha) is str and len(sha) == 64 and
          all(c in "0123456789abcdef" for c in sha)), "source_sha256", si)
    n = len(slots)
    forward, inverse = session.get("sorted_to_raw"), session.get("raw_to_sorted")
    _need(type(forward) is list and len(forward) == n and
          all(type(i) is int for i in forward) and sorted(forward) == list(range(n)),
          "sorted_raw_bijection", si)
    _need(type(inverse) is list and len(inverse) == n and
          all(type(i) is int for i in inverse) and
          all(inverse[raw] == ordinal for ordinal, raw in enumerate(forward)),
          "raw_sorted_inverse", si)
    derived = session.get("derived_splits")
    _need(type(derived) is dict and set(derived) == set(SPLITS), "derived_split_schema", si)
    previous_end = None
    for split in SPLITS:
        intervals = derived[split]
        _need(type(intervals) is list and len(intervals) == 1 and
              type(intervals[0]) is list and len(intervals[0]) == 2 and
              all(_finite(t) for t in intervals[0]) and intervals[0][0] < intervals[0][1],
              "derived_split_interval", si)
        start, end = intervals[0]
        _need(previous_end is None or previous_end <= start, "derived_split_overlap", si)
        previous_end = end
    eligible = {}
    raw_rows = []
    excluded = {}
    for ordinal, slot in enumerate(slots):
        _need(type(slot) is dict and type(slot.get("ordinal")) is int and
              slot["ordinal"] == ordinal and type(slot.get("raw_index")) is int and
              slot["raw_index"] == forward[ordinal], "original_slot_identity", si, ordinal)
        _need(type(slot.get("prior_ordinal")) is int if ordinal else slot.get("prior_ordinal") is None,
              "original_predecessor_type", si, ordinal)
        _need(slot.get("prior_ordinal") == (ordinal - 1 if ordinal else None),
              "original_predecessor_ordinal", si, ordinal)
        normalized = slot.get("normalized")
        _need(type(normalized) is dict and type(normalized.get("raw")) is dict,
              "original_raw_trial", si, ordinal)
        raw = normalized["raw"]
        _need(type(normalized.get("ordinal")) is int and normalized["ordinal"] == ordinal and
              type(normalized.get("raw_index")) is int and normalized["raw_index"] == forward[ordinal] and
              type(raw.get("raw_index")) is int and raw["raw_index"] == forward[ordinal],
              "normalized_raw_join", si, ordinal)
        _need(raw.get("stored_ordinal") is None or
              (type(raw["stored_ordinal"]) is int and raw["stored_ordinal"] == ordinal),
              "stored_ordinal_join", si, ordinal)
        _need(type(slot.get("source_valid")) is bool and
              type(normalized.get("source_valid")) is bool and
              slot["source_valid"] == normalized["source_valid"], "source_validity_join", si, ordinal)
        for field, raw_name in (("movement_onset_time", "firstMovement_times"),
                                ("feedback_time", "feedback_times"), ("stim_on_time", "stimOn_times")):
            _need(raw_name in raw and _same(normalized.get(field), raw[raw_name]),
                  "source_clock_join", si, ordinal)
        for field, encoding, raw_name in (("choice", {-1: 0, 1: 1, 0: 2}, "choice"),
                                          ("reward", {-1: 0, 1: 1}, "feedbackType")):
            value = raw.get(raw_name)
            _need(value is None or type(value) is int, "source_behavior_type", si, ordinal)
            _need(_same(normalized.get(field), encoding.get(value)), "source_behavior_join", si, ordinal)
        reasons = slot.get("reasons")
        _need(type(reasons) is list and all(type(r) is str and r for r in reasons),
              "slot_disposition_reasons", si, ordinal)
        for reason in reasons:
            excluded[reason] = excluded.get(reason, 0) + 1
        if slot.get("disposition") == "eligible":
            _need(slot["source_valid"] and not reasons and slot.get("split") in SPLITS and
                  slot.get("case_id") == case_id(session["session_id"], identity, ordinal),
                  "eligible_slot_identity", si, ordinal)
            eligible[ordinal] = slot
        else:
            _need(slot.get("disposition") in ("source_invalid", "excluded_choice") and reasons and
                  slot.get("case_id") is None and slot.get("split") is None,
                  "excluded_slot_disposition", si, ordinal)
        raw_rows.append(raw)
    _need(all(type(c) is dict and type(c.get("ordinal")) is int for c in cases),
          "case_ordinal_type", si)
    _need([c["ordinal"] for c in cases] == list(eligible),
          "eligible_slot_case_bijection", si)
    split_counts = dict.fromkeys(SPLITS, 0)
    split_order = []
    for case in cases:
        ordinal = case["ordinal"]
        slot, raw = eligible[ordinal], raw_rows[ordinal]
        _need(case.get("case_id") == slot["case_id"] and case.get("split") == slot["split"],
              "case_slot_identity", si, ordinal)
        _need(type(case.get("y")) is int and case["y"] in (0, 1) and
              case["y"] == {-1: 0, 1: 1}.get(raw.get("choice")), "case_source_choice", si, ordinal)
        movement = raw.get("firstMovement_times")
        stimulus = raw.get("stimOn_times")
        _need(_finite(movement) and _finite(stimulus) and stimulus < movement and
              _same(case.get("window_start"), movement - 1.) and
              _same(case.get("window_end"), movement), "case_movement_window", si, ordinal)
        matching = [s for s in SPLITS if derived[s][0][0] <= movement - 1. and
                    movement <= derived[s][0][1]]
        _need(matching == [case["split"]], "case_whole_window_split", si, ordinal)
        _need(_same(case.get("unit_ids"), units), "case_unit_axis", si, ordinal)
        count_row = case.get("count_row")
        neural = case.get("N")
        _need(type(count_row) is list and len(count_row) == len(units) and
              all(type(v) is int and v >= 0 for v in count_row), "case_count_row", si, ordinal)
        _need(type(neural) is list and len(neural) == len(units) and
              all(_finite(x) and x == math.log1p(v) for x, v in zip(neural, count_row)),
              "case_log_count_join", si, ordinal)
        left, right = raw.get("contrastLeft"), raw.get("contrastRight")
        _need((left is None) != (right is None), "source_stimulus_side", si, ordinal)
        magnitude = right if left is None else left
        _need(_finite(magnitude) and magnitude in (0., .0625, .125, .25, 1.),
              "source_stimulus_magnitude", si, ordinal)
        signed = 0. if magnitude == 0 else -magnitude if left is None else magnitude
        _need(_indicator(case.get("S"), 9, SIGNED.index(signed)), "case_stimulus_join", si, ordinal)
        block = raw.get("probabilityLeft")
        _need(_finite(block) and block in BLOCKS and
              _indicator(case.get("B"), 3, BLOCKS.index(block)), "case_block_join", si, ordinal)
        available = False
        h_index = 0
        if ordinal:
            prior = raw_rows[ordinal - 1]
            choice = {-1: 0, 1: 1, 0: 2}.get(prior.get("choice"))
            reward = {-1: 0, 1: 1}.get(prior.get("feedbackType"))
            available = (_finite(prior.get("feedback_times")) and
                         prior["feedback_times"] < movement and choice is not None and reward is not None)
            if available:
                h_index = 1 + 2 * choice + reward
        reason = ("no_preceding_original_trial" if ordinal == 0 else
                  "feedback_strictly_before_cutoff" if available else "prior_feedback_or_behavior_unavailable")
        _need(type(case.get("history_available")) is bool and
              case["history_available"] == available and case.get("history_reason") == reason and
              _indicator(case.get("H"), 7, h_index), "original_predecessor_history", si, ordinal)
        previous = eligible.get(ordinal - 1)
        expected_prior = previous["case_id"] if previous is not None and available else None
        _need(_same(case.get("prior_case_id"), expected_prior), "original_predecessor_case_join", si, ordinal)
        split_counts[case["split"]] += 1
        split_order.append(SPLITS.index(case["split"]))
    _need(split_order == sorted(split_order), "case_split_chronology", si)
    counts = session.get("counts")
    _need(type(counts) is dict, "preparation_counts", si)
    expected_counts = {
        "original_trials": len(slots), "source_valid_trials": sum(s["source_valid"] for s in slots),
        "eligible_by_split": split_counts, "excluded_by_reason": excluded, "unit_count": len(units),
        "matrix": [c["count_row"] for c in cases], "case_ids": [c["case_id"] for c in cases],
    }
    for name, expected in expected_counts.items():
        _need(_same(counts.get(name), expected), "census_join:" + name, si)
    return {"original_slots": n, "eligible_by_split": split_counts, "unit_count": len(units)}


def validate_prepared(prepared_sessions):
    """The immutable 29-session/13-animal/7-lab primary scope only."""
    _need(type(prepared_sessions) is list and len(prepared_sessions) == len(evaluation.ROSTER),
          "complete_roster_size")
    summary = []
    for si, (session, (eid, subject, lab)) in enumerate(zip(prepared_sessions, evaluation.ROSTER)):
        _need(type(session) is dict and (session.get("session_id"), session.get("subject_id"),
              session.get("lab")) == (eid, subject, lab), "complete_ordered_roster_join", si)
        summary.append(validate_session(session, si))
    return summary


def score_panel(prepared_sessions, predictions, *, expected_methods):
    """Reject inconsistent primary support, then use unchanged endpoint math."""
    validate_prepared(prepared_sessions)
    return evaluation.score_panel(prepared_sessions, predictions, expected_methods=expected_methods)
