"""Closed paired deployment policy; declarations do not prove native custody.

No production resource values are supplied here. The trusted controller must
commit this plan and authenticate authoring receipts before assessment staging,
enforce each reserved request and native ceiling, and separately review P0
training-only semantics. File isolation alone cannot prove nontransductive code.
"""

import copy
import math
import re

SETTINGS = ("target20", "transfer0", "target100", "other_session20")
ARMS = ("EEG", "CONTEXT", "PERMUTED_EEG")
PANELS = ("frozen_program", "case_adaptive", "reference")
MODEL_FIELDS = ("identity", "configuration_sha256", "prompt_sha256",
                "procedure_sha256", "tool_protocol_sha256")


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _exact(value, fields, name):
    _need(type(value) is dict and set(value) == set(fields), name + ": exact fields required")


def _integer(value, name, minimum=1):
    _need(type(value) is int and value >= minimum, name + ": integer lower bound required")
    return value


def _digest(value, name):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), name + ": SHA256 required")


def _pin(value, name):
    _exact(value, ("bytes", "sha256"), name)
    _integer(value["bytes"], name + ".bytes")
    _digest(value["sha256"], name + ".sha256")


def _panel_contexts(panel):
    """Check only policy-relevant support; unchanged scorer does full admission.

    The caller supplies the incumbent canonical projection. This helper does
    not authenticate its source or duplicate the scorer's trial/output rules.
    """
    _exact(panel, ("schema", "generation", "settings", "arms", "cases"), "panel")
    _need(panel["schema"] == "neural083_panel_v1", "Original panel schema")
    _digest(panel["generation"], "panel.generation")
    _need(panel["settings"] == list(SETTINGS) and panel["arms"] == list(ARMS), "Original settings and arms")
    _need(type(panel["cases"]) is list and len(panel["cases"]) == 108, "All 108 cases required")
    cases, people, contexts = set(), {}, []
    for row in panel["cases"]:
        _exact(row, ("case", "person", "session", "query"), "panel case")
        for key in ("case", "person"):
            _need(type(row[key]) is str and re.fullmatch(key + r"_[0-9a-f]{24}", row[key]), "Opaque " + key)
        _need(row["case"] not in cases, "Distinct cases")
        cases.add(row["case"])
        _need(type(row["session"]) is int and row["session"] in (1, 2), "Two original sessions")
        sessions = people.setdefault(row["person"], set())
        _need(row["session"] not in sessions, "Unique person/session")
        sessions.add(row["session"])
        _need(type(row["query"]) is list and len(row["query"]) == 100, "100 queries per case")
        contexts.extend((row["case"], setting, arm) for setting in SETTINGS for arm in ARMS)
    _need(len(people) == 54 and all(s == {1, 2} for s in people.values()), "Full 54-person/two-session support")
    return contexts


def validate_plan(plan, panel):
    """Validate explicit equal ceilings and return a detached plan.

    Calls and tokens are strictly positive ceilings, not a requirement to spend
    the ceiling. Every adaptive context has a committed allocation; their sums
    equal global frozen-program authoring ceilings. Frozen numerical fit/infer
    stages receive zero runtime model calls. All three panels share native
    phase ceilings. storage_bytes denotes the output volume only; additional
    helper, /tmp and shared-memory limits require the separate native binding.
    wall_seconds denotes the whole stage including cleanup. Semantic P0 and
    actual enforcement require outer admission; positive/equal declarations do
    not assert that arbitrary values are supported by the incumbent worker.
    """
    _exact(plan, ("schema", "generation", "model", "frozen_program", "adaptive_allocations",
                  "condition_limits", "p0", "accounting"), "plan")
    _need(plan["schema"] == "neural083_paired_policy_v1", "Paired policy schema")
    contexts = _panel_contexts(panel)
    _need(plan["generation"] == panel["generation"], "Same canonical generation")
    model = plan["model"]
    _exact(model, MODEL_FIELDS, "model")
    _need(type(model["identity"]) is str and 0 < len(model["identity"]) <= 256 and
          model["identity"].strip() == model["identity"], "Explicit bounded model identity")
    for name in MODEL_FIELDS[1:]:
        _digest(model[name], name)
    frozen = plan["frozen_program"]
    _exact(frozen, ("artifact", "authoring_ceiling", "runtime_model_calls"), "frozen_program")
    _pin(frozen["artifact"], "frozen artifact")
    _exact(frozen["authoring_ceiling"], ("calls", "tokens"), "authoring_ceiling")
    for key in ("calls", "tokens"):
        _integer(frozen["authoring_ceiling"][key], "authoring " + key)
    _need(type(frozen["runtime_model_calls"]) is int and frozen["runtime_model_calls"] == 0,
          "Frozen numerical stages cannot call a runtime model")
    allocations = plan["adaptive_allocations"]
    _need(type(allocations) is list and len(allocations) == 1296, "Exactly 1296 adaptive allocations")
    sums = {"calls": 0, "tokens": 0}
    for expected, allocation in zip(contexts, allocations):
        _exact(allocation, ("case", "setting", "arm", "calls", "tokens"), "adaptive allocation")
        _need(tuple(allocation[k] for k in ("case", "setting", "arm")) == expected,
              "Exact committed context order and identity")
        for key in sums:
            sums[key] += _integer(allocation[key], "adaptive " + key)
    _need(sums == frozen["authoring_ceiling"], "Equal total model call/token ceilings")
    limits = plan["condition_limits"]
    _exact(limits, PANELS, "condition_limits")
    for name in PANELS:
        _exact(limits[name], ("fit", "infer"), name + " phase limits")
        for phase in ("fit", "infer"):
            row = limits[name][phase]
            _exact(row, ("cpu_count", "memory_bytes", "wall_seconds", "storage_bytes"), phase + " limits")
            for key in ("cpu_count", "memory_bytes", "storage_bytes"):
                _integer(row[key], phase + "." + key)
            wall = row["wall_seconds"]
            _need(type(wall) in (int, float), "Positive finite wall ceiling")
            try:
                valid_wall = math.isfinite(wall) and wall > 0
            except OverflowError:
                valid_wall = False
            _need(valid_wall, "Positive finite wall ceiling")
    _need(limits["frozen_program"] == limits["case_adaptive"] == limits["reference"],
          "Exactly equal per-condition phase ceilings for all three panels")
    expected_p0 = {"fit_on_training_only": True, "query_batch_visible": 100,
                   "query_batch_fitting": False, "seal_before_query": True,
                   "cross_context_state": False}
    _exact(plan["p0"], expected_p0, "P0")
    _need(all(type(plan["p0"][k]) is type(v) and plan["p0"][k] == v for k, v in expected_p0.items()),
          "Preserve P0 training-only fitting, sealed state and full query visibility")
    _exact(plan["accounting"], ("preparation_included", "failed_requests_included", "authoring_usage_included"),
           "accounting")
    _need(all(v is True for v in plan["accounting"].values()), "All preparation, failed and authoring usage counted")
    return copy.deepcopy(plan)


def validate_authoring_usage(receipt, plan):
    """Check accounting of an already source/authentication-bound authoring receipt.

    ``plan`` must first pass validate_plan. Every dispatched request charges its full
    prospectively selected reserved_tokens, without refund, matching the adaptive
    broker. Success requires known actual usage; failed actual usage may remain
    unknown when its complete maximum reservation is known. Actual usage is
    reported separately and never increases the remaining reservation budget.
    Caller broker must enforce reservations before requests and authenticate
    completeness and pre-staging chronology; a Boolean flag is not proof.
    """
    _exact(receipt, ("schema", "model", "artifact", "authoring_precedes_staging", "requests"), "authoring receipt")
    _need(receipt["schema"] == "neural083_frozen_authoring_usage_v1", "Authoring receipt schema")
    _exact(receipt["model"], MODEL_FIELDS, "receipt model")
    _pin(receipt["artifact"], "receipt artifact")
    _need(receipt["model"] == plan["model"] and receipt["artifact"] == plan["frozen_program"]["artifact"],
          "Receipt must bind the frozen artifact and all model configuration")
    _need(receipt["authoring_precedes_staging"] is True, "Authoring must precede assessment staging")
    requests = receipt["requests"]
    ceiling = plan["frozen_program"]["authoring_ceiling"]
    _need(type(requests) is list and len(requests) <= ceiling["calls"], "Authoring call ceiling")
    totals = {"calls": len(requests), "tokens": 0, "failed_calls": 0, "failed_tokens": 0,
              "preparation_calls": 0, "preparation_tokens": 0, "unknown_usage_calls": 0}
    known_input = known_output = 0
    identities = set()
    for row in requests:
        _exact(row, ("request_id", "status", "reserved_tokens", "input_tokens", "output_tokens", "preparation"),
               "authoring request")
        identity = row["request_id"]
        _need(type(identity) is str and 0 < len(identity) <= 256 and identity not in identities,
              "Unique bounded request identity")
        identities.add(identity)
        _need(row["status"] in ("complete", "failed") and type(row["preparation"]) is bool,
              "Explicit request outcome and preparation membership")
        reserved = _integer(row["reserved_tokens"], "reserved request tokens")
        _need(totals["tokens"] + reserved <= ceiling["tokens"], "Pre-request reservation fits remaining authoring ceiling")
        usage = (row["input_tokens"], row["output_tokens"])
        for value in usage:
            if value is not None:
                _integer(value, "observed token usage", 0)
        unknown = any(value is None for value in usage)
        _need(not unknown or row["status"] == "failed", "Successful requests require known token usage")
        _need(sum(v for v in usage if v is not None) <= reserved, "Observed usage must fit pre-request reservation")
        charged = reserved
        known_input += 0 if usage[0] is None else usage[0]
        known_output += 0 if usage[1] is None else usage[1]
        totals["tokens"] += charged
        _need(totals["tokens"] <= ceiling["tokens"], "Authoring token ceiling")
        if unknown:
            totals["unknown_usage_calls"] += 1
        if row["status"] == "failed":
            totals["failed_calls"] += 1
            totals["failed_tokens"] += charged
        if row["preparation"]:
            totals["preparation_calls"] += 1
            totals["preparation_tokens"] += charged
    return {"schema": "neural083_frozen_authoring_accounting_v2", **totals,
            "accounting": "all_dispatched_reservations_no_refund",
            "reported_known_input_tokens": known_input,
            "reported_known_output_tokens": known_output,
            "actual_usage_complete": totals["unknown_usage_calls"] == 0,
            "actual_tokens": None if totals["unknown_usage_calls"] else known_input + known_output,
            "ceiling": copy.deepcopy(ceiling), "receipt_authenticated": False,
            "native_enforcement_proven": False}
