"""Pure condition-isolated NEURAL-030 candidate inputs.

This module transforms the already prepared public object; it neither loads
native data nor authenticates identities, clocks, source preprocessing or QC.
The complete view is an operator assembly object. Use calibration_packet and
query_packet for separate delivery; these functions do not enforce model freeze,
process isolation, delivery order or state reset.
"""
import copy
import math
import re

TASK_ID = "NEURAL-030"
AVAILABILITY = "full_planned_window_retrospective"
ARMS = ("context_handle", "grc", "cf", "joint")
SPLITS = ("train", "development", "query")
CONDITIONS = {
    "one_second_expert": (1.0, 5),
    "two_second_novice": (2.0, 5),
    "two_second_expert": (2.0, 6),
}
PUBLIC_KEYS = frozenset(("schema", "cases", "view_scope", "query_target_feedback"))
CASE_KEYS = frozenset(("session_id", "condition", "delay_s", *SPLITS))
CONTEXT_TRIAL_KEYS = frozenset(("trial_id", "session_id", "trial_order", "delay_s",
                              "stage", "handle_time", "handle"))
ENVELOPE_FIELDS = ("schema", "task_id", "session_id", "condition", "delay_s", "arm", "availability")
ENVELOPE_KEYS = frozenset(ENVELOPE_FIELDS)
VIEW_KEYS = ENVELOPE_KEYS | frozenset((*SPLITS, "required_predictions"))
PLAN_KEYS = frozenset(("schema", "task_id", "availability", "cases"))
PLAN_CASE_KEYS = frozenset(("session_id", "condition", "delay_s", "required_predictions"))
OPAQUE_ID = re.compile(r"[0-9a-f]{32}\Z")


class Refusal(ValueError):
    """Input does not match the closed prepared-output contract."""


def require(value, reason):
    if not value:
        raise Refusal(reason)


def closed(value, keys, reason):
    require(type(value) is dict and set(value) == set(keys), reason)


def opaque_id(value):
    # Stricter than the generic low-level scorer: this API accepts the output
    # shape of source_binding.opaque. Syntax cannot authenticate an identity.
    require(type(value) is str and OPAQUE_ID.fullmatch(value) is not None,
            "prepared_opaque_id_32_lowercase_hex")
    return value


def number(value, reason):
    require(type(value) in (int, float), reason)
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    require(finite, reason)
    return value


def trial_keys(arm, split):
    require(type(arm) is str and arm in ARMS, "fixed_arm")
    require(split in SPLITS, "fixed_split")
    keys = set(CONTEXT_TRIAL_KEYS)
    if arm != "context_handle":
        keys.add("neural_time")
    if arm in ("grc", "joint"):
        keys.add("grc")
    if arm in ("cf", "joint"):
        keys.add("cf")
    if split != "query":
        keys.add("counts")
    return frozenset(keys)


def case_header(case):
    sid = opaque_id(case["session_id"])
    condition = case["condition"]
    require(type(condition) is str and condition in CONDITIONS, "known_source_condition")
    delay = number(case["delay_s"], "finite_planned_delay")
    require(delay == CONDITIONS[condition][0], "source_condition_delay_binding")
    return sid, condition, delay, int(delay * 10)


def clock(values, delay, reason):
    require(type(values) is list and len(values) >= 2, reason + "_list_support")
    previous = None
    for value in values:
        number(value, reason + "_finite")
        require(0 <= value < delay, reason + "_within_planned_window")
        require(previous is None or value > previous, reason + "_strict_increasing")
        previous = value
    # No interpolation, boundary snapping, rate recovery, per-bin sample
    # eligibility, physical clock or QC certification is performed here.
    return len(values)


def matrix(values, width, reason, *, channels=None, binary=False):
    require(type(values) is list and values, reason + "_channels")
    if channels is not None:
        require(len(values) == channels, reason + "_channel_count")
    for row in values:
        require(type(row) is list and len(row) == width, reason + "_clock_shape")
        for value in row:
            number(value, reason + "_finite")
            if binary:
                require(value in (0, 1), reason + "_binary")
    return len(values)


def counts(values, bin_count):
    require(type(values) is list and len(values) == bin_count, "complete_calibration_count_bins")
    for value in values:
        number(value, "finite_calibration_count")
        require(0 <= value <= 2**53 - 1 and value == math.floor(value),
                "nonnegative_exact_integer_calibration_counts")


def validate_trial_splits(case, arm, global_trial_ids):
    sid, condition, delay, bins = case_header(case)
    last_order = 0
    channel_counts = {}
    for split in SPLITS:
        rows = case[split]
        require(type(rows) is list and rows, "nonempty_ordered_" + split)
        for trial in rows:
            closed(trial, trial_keys(arm, split), "closed_" + split + "_trial_fields")
            tid = opaque_id(trial["trial_id"])
            require(tid not in global_trial_ids, "globally_unique_disjoint_trial_ids")
            global_trial_ids.add(tid)
            require(trial["session_id"] == sid and trial["stage"] == condition,
                    "original_case_trial_context_binding")
            number(trial["delay_s"], "trial_delay_type")
            require(trial["delay_s"] == delay, "trial_planned_delay_binding")
            order = trial["trial_order"]
            require(type(order) is int and order > last_order, "strict_blocked_trial_order")
            last_order = order
            handle_width = clock(trial["handle_time"], delay, "handle_time")
            matrix(trial["handle"], handle_width, "handle", channels=2)
            if arm != "context_handle":
                neural_width = clock(trial["neural_time"], delay, "neural_time")
                for modality in ("grc", "cf"):
                    if modality not in trial_keys(arm, split):
                        continue
                    width = matrix(trial[modality], neural_width, modality, binary=modality == "cf")
                    require(modality not in channel_counts or channel_counts[modality] == width,
                            "same_record_" + modality + "_channel_count")
                    channel_counts[modality] = width
            if split != "query":
                counts(trial["counts"], bins)
    return [{"trial_id": trial["trial_id"], "bin_count": bins} for trial in case["query"]]


def validate_roster_headers(cases):
    require(type(cases) is list and len(cases) == 16, "complete_16_case_roster")
    seen_sessions = set()
    seen_conditions = {condition: 0 for condition in CONDITIONS}
    for case in cases:
        sid, condition, _, _ = case_header(case)
        require(sid not in seen_sessions, "unique_opaque_sessions")
        seen_sessions.add(sid)
        seen_conditions[condition] += 1
    require(all(seen_conditions[name] == expected[1]
                for name, expected in CONDITIONS.items()), "complete_source_group_5_5_6")


def _validate_public(public):
    closed(public, PUBLIC_KEYS, "closed_prepared_public_fields")
    require(public["schema"] == "neural030_cerebellar_public_v1", "prepared_public_schema")
    require(public["view_scope"] == "retrospective_processed_within_session_calibration"
            and public["query_target_feedback"] is False, "prepared_public_retrospective_scope")
    require(type(public["cases"]) is list, "prepared_cases_list")
    for case in public["cases"]:
        closed(case, CASE_KEYS, "closed_prepared_case_fields")
    validate_roster_headers(public["cases"])
    seen_trials = set()
    for case in public["cases"]:
        # Validate both full neural modalities before excluding either, including
        # inputs destined for the context-only arm. Malformed input is not repaired.
        validate_trial_splits(case, "joint", seen_trials)
    return public


def prediction_roster(rows, bins, seen):
    require(type(rows) is list and rows, "nonempty_required_predictions")
    for row in rows:
        closed(row, ("trial_id", "bin_count"), "closed_required_prediction_fields")
        tid = opaque_id(row["trial_id"])
        require(tid not in seen, "unique_required_prediction_trial")
        seen.add(tid)
        require(type(row["bin_count"]) is int and row["bin_count"] == bins,
                "complete_10_or_20_prediction_bins")


def validate_plan(plan):
    """Validate a target-free 16-case roster; no biological identity authentication."""
    closed(plan, PLAN_KEYS, "closed_candidate_plan_fields")
    require(plan["schema"] == "neural030_candidate_plan_v1" and plan["task_id"] == TASK_ID,
            "candidate_plan_identity")
    require(plan["availability"] == AVAILABILITY, "retrospective_availability")
    require(type(plan["cases"]) is list, "plan_cases_list")
    for case in plan["cases"]:
        closed(case, PLAN_CASE_KEYS, "closed_candidate_plan_case")
    validate_roster_headers(plan["cases"])
    seen = set()
    for case in plan["cases"]:
        _, _, _, bins = case_header(case)
        prediction_roster(case["required_predictions"], bins, seen)
    return plan


def validate_view(view):
    """Validate one arm's assembly object, retaining the supplied ordered support."""
    closed(view, VIEW_KEYS, "closed_candidate_view_fields")
    require(view["schema"] == "neural030_candidate_view_v1" and view["task_id"] == TASK_ID,
            "candidate_view_identity")
    require(view["availability"] == AVAILABILITY, "retrospective_availability")
    require(type(view["arm"]) is str and view["arm"] in ARMS, "fixed_arm")
    expected = validate_trial_splits(view, view["arm"], set())
    _, _, _, bins = case_header(view)
    prediction_roster(view["required_predictions"], bins, set())
    require(view["required_predictions"] == expected, "exact_ordered_query_prediction_roster")
    return view


def _project_trial(trial, arm, split):
    permitted = trial_keys(arm, split)
    # Copy each field separately. Even aliased input containers cannot create
    # a link back to input data or between separately projected trial fields.
    return {key: copy.deepcopy(value) for key, value in trial.items() if key in permitted}


def compile_panel(public):
    """Validate the complete prepared16-case object, then create all64 arm views.

    Cases retain input order; each case emits context_handle, grc, cf, joint.
    All intervals are the full retrospective planned windows. Unknown/private
    fields and query counts are errors, not silently discarded data.
    """
    _validate_public(public)
    plan = {"schema": "neural030_candidate_plan_v1", "task_id": TASK_ID,
            "availability": AVAILABILITY, "cases": []}
    views = []
    for case in public["cases"]:
        sid, condition, delay, bins = case_header(case)
        required = [{"trial_id": row["trial_id"], "bin_count": bins} for row in case["query"]]
        plan["cases"].append({"session_id": sid, "condition": condition,
                              "delay_s": delay, "required_predictions": copy.deepcopy(required)})
        for arm in ARMS:
            view = {"schema": "neural030_candidate_view_v1", "task_id": TASK_ID,
                    "session_id": sid, "condition": condition, "delay_s": delay,
                    "arm": arm, "availability": AVAILABILITY}
            for split in SPLITS:
                view[split] = [_project_trial(row, arm, split) for row in case[split]]
            view["required_predictions"] = copy.deepcopy(required)
            views.append(view)
    # Construction uses closed fields only, but verify the emitted shape as part
    # of the public API rather than assuming a downstream caller will do it.
    validate_plan(plan)
    for view in views:
        validate_view(view)
    return {"plan": plan, "views": views}


def _packet(view, schema, payload_keys):
    validate_view(view)
    result = {key: copy.deepcopy(view[key]) for key in ENVELOPE_FIELDS}
    result["schema"] = schema
    for key in payload_keys:
        result[key] = copy.deepcopy(view[key])
    return result


def calibration_packet(view):
    """Train/development-only packet for a later separately enforced fit stage."""
    return _packet(view, "neural030_calibration_v1", ("train", "development"))


def query_packet(view):
    """Query inputs and full ordered predictions only; no labels or fit-stage data."""
    return _packet(view, "neural030_query_v1", ("query", "required_predictions"))
