"""Pure NEURAL-030 inputs and finite precommitted recipe selection.

candidate_views is a trusted implementation dependency supplied by the parent's
closed captured-source namespace, never a candidate-selected module or callback.
No transport, worker, fitted state, source bundle or payload file is opened here.
"""
import copy
import json
import math
import re
from types import ModuleType

TASK_ID = "NEURAL-030"
AVAILABILITY = "full_planned_window_retrospective"
ARMS = ("context_handle", "grc", "cf", "joint")
SPLITS = ("train", "development", "query")
ENVELOPE = ("schema", "task_id", "session_id", "condition", "delay_s", "arm", "availability")
SOURCE_ROLES = {"select": "select.py", "fit": "fit.py", "infer": "infer.py"}
OPAQUE_ID = re.compile(r"[0-9a-f]{32}\Z")


class Refusal(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Refusal(reason)


def closed(value, keys, reason):
    require(type(value) is dict and all(type(key) is str for key in value)
            and set(value) == set(keys), reason)


def _implementation(candidate_views):
    require(type(candidate_views) is ModuleType, "trusted_candidate_views_module")
    require(getattr(candidate_views, "TASK_ID", None) == TASK_ID
            and getattr(candidate_views, "ARMS", None) == ARMS
            and getattr(candidate_views, "AVAILABILITY", None) == AVAILABILITY,
            "selected_candidate_view_contract")
    for name in ("validate_plan", "validate_view", "calibration_packet", "query_packet"):
        require(callable(getattr(candidate_views, name, None)), "accepted_candidate_view_api")
    return candidate_views


def _same(left, right):
    # Typed JSON content equality also distinguishes a changed integer/float
    # representation or signed zero. Dict insertion order is not data order.
    return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_panel(panel, *, candidate_views):
    """Validate the complete16-case×4-arm mapping before stage serialization.

    This rechecks all accepted view/plan schemas, exact case-major arm order,
    identical ordered context/labels and every permitted neural value across
    arms, and disjoint original trials across cases. It does not add eligibility.
    """
    api = _implementation(candidate_views)
    closed(panel, ("plan", "views"), "closed_compiled_panel")
    api.validate_plan(panel["plan"])
    require(type(panel["views"]) is list and len(panel["views"]) == 64,
            "complete_64_candidate_views")
    original_trials = set()
    for index, case in enumerate(panel["plan"]["cases"]):
        block = panel["views"][index * 4:(index + 1) * 4]
        for arm, view in zip(ARMS, block):
            api.validate_view(view)
            require(view["arm"] == arm and view["session_id"] == case["session_id"],
                    "exact_plan_case_major_arm_order")
            for field in ("session_id", "condition", "delay_s", "required_predictions"):
                require(_same(view[field], case[field]), "plan_view_binding_" + field)
        joint = block[3]
        for split in SPLITS:
            for trial in joint[split]:
                require(trial["trial_id"] not in original_trials,
                        "all_original_trials_globally_disjoint")
                original_trials.add(trial["trial_id"])
            for view in block:
                require(len(view[split]) == len(joint[split]), "same_ordered_trial_support_all_arms")
                for projected, full in zip(view[split], joint[split]):
                    require(all(key in full for key in projected), "arm_fields_are_joint_projection")
                    expected = {key: full[key] for key in projected}
                    require(_same(projected, expected), "same_permitted_trial_values_all_arms")
    return panel


def training_packet(view, *, candidate_views):
    """Final-fit inputs contain train only, never development or query data."""
    api = _implementation(candidate_views)
    api.validate_view(view)
    result = {key: copy.deepcopy(view[key]) for key in ENVELOPE}
    result["schema"] = "neural030_training_v1"
    result["train"] = copy.deepcopy(view["train"])
    return result


def stage_packets(view, *, candidate_views):
    """Derive detached stage inputs from an operator-only complete assembly.

    The parent must validate the full panel and enforce select→fit→infer mounts
    and source/state commitments. Returning these objects grants no delivery or
    execution authority and makes no fitted-state freezing claim.
    """
    api = _implementation(candidate_views)
    api.validate_view(view)
    return {
        "calibration": api.calibration_packet(view),
        "training": training_packet(view, candidate_views=api),
        "query": api.query_packet(view),
    }


def _ordinary_json(value):
    """Accept finite serializable JSON values; reject objects and reference cycles."""
    active = set()
    stack = [(value, False)]
    while stack:
        current, leaving = stack.pop()
        kind = type(current)
        if leaving:
            active.remove(id(current))
            continue
        if kind in (dict, list):
            require(id(current) not in active, "acyclic_recipe_config")
            active.add(id(current))
            stack.append((current, True))
            if kind is dict:
                require(all(type(key) is str for key in current), "json_recipe_string_keys")
                for key in current:
                    try:
                        key.encode("utf8")
                    except UnicodeEncodeError as error:
                        raise Refusal("ordinary_recipe_unicode") from error
                stack.extend((child, False) for child in current.values())
            else:
                stack.extend((child, False) for child in current)
        elif kind is str:
            try:
                current.encode("utf8")
            except UnicodeEncodeError as error:
                raise Refusal("ordinary_recipe_unicode") from error
        elif kind is float:
            require(math.isfinite(current), "finite_recipe_number")
        else:
            require(current is None or kind in (bool, int), "plain_json_recipe_value")
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise Refusal("finite_serializable_recipe_config") from error


def validate_procedure(procedure):
    """Validate fixed metadata; parent authenticates source/grid before any data.

    The nonempty finite grid consists of precommitted JSON-object configurations.
    Their parameter keys are defined by that frozen grid, not by a response from
    selection. No recipe normalization, source discovery or artifact loading occurs.
    """
    closed(procedure, ("schema", "task_id", "source_roles", "recipes"),
           "closed_frozen_procedure")
    require(procedure["schema"] == "neural030_frozen_procedure_v1"
            and procedure["task_id"] == TASK_ID, "frozen_procedure_identity")
    closed(procedure["source_roles"], SOURCE_ROLES, "exact_three_source_roles")
    require(all(type(value) is str for value in procedure["source_roles"].values())
            and procedure["source_roles"] == SOURCE_ROLES, "fixed_select_fit_infer_filenames")
    recipes = procedure["recipes"]
    require(type(recipes) is list and recipes, "precommitted_nonempty_finite_grid")
    for recipe in recipes:
        require(type(recipe) is dict, "recipe_json_object")
        _ordinary_json(recipe)
    return procedure


def validate_selection(response, procedure, session_id, arm):
    """Return only a detached configuration already present at the selected index.

    Selection supplies no recipe body, learned state, file path, metric report or
    artifact. The parent's source commitment establishes which procedure is frozen.
    """
    validate_procedure(procedure)
    require(type(session_id) is str and OPAQUE_ID.fullmatch(session_id) is not None,
            "expected_opaque_session")
    require(type(arm) is str and arm in ARMS, "expected_fixed_arm")
    closed(response, ("schema", "session_id", "arm", "recipe_index"),
           "closed_selection_response")
    require(response["schema"] == "neural030_selection_v1", "selection_schema")
    require(type(response["session_id"]) is str and response["session_id"] == session_id
            and type(response["arm"]) is str and response["arm"] == arm,
            "selection_case_arm_binding")
    index = response["recipe_index"]
    require(type(index) is int and 0 <= index < len(procedure["recipes"]),
            "selection_index_into_frozen_grid")
    return {"recipe_index": index, "recipe": copy.deepcopy(procedure["recipes"][index])}
