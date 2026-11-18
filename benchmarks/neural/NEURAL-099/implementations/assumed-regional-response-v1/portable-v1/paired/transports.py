"""Source-only request envelopes for two matched current-trial conditions.

The native structured/no-tools and frozen-programme modes receive the exact
same canonical observation bytes. This module opens no provider, process,
packet, model or file. It does not enforce tool availability, frozen code,
fresh process state, chronological release, training restrictions or host
containment. Reset fields state requirements, never attest to enforcement.

The trusted controller supplies all frozen available regions of one released
trial. This codec cannot independently authenticate source completeness or
authorize a participant to release another case. A trial token is an opaque
correlation identifier, not a release capability. Predictions are outside this
module: the frozen scorer retains finite negative and large finite integer
predictions without clipping, rounding or transport-specific coercion.
Timing checks cover numeric bounds and agreement across regions; authentic
clock semantics and logical source chronology remain controller obligations.
"""

import hashlib
import json
import math


CASE_FIELDS = frozenset(("case_id", "animal_id", "asset_id", "region",
                         "source_trial_row", "source_cluster_count"))
TIMING_FIELDS = frozenset(("click_duration_seconds", "elapsed_since_first_click_seconds",
                           "previous_click_interval_seconds"))
REGIONS = frozenset(("BIC", "MGd", "MGm", "MGv", "MZMG", "SG"))
PROFILE_FIELDS = frozenset((
    "condition_id", "mode", "information_condition", "demonstration_labels",
    "benchmark_response_labels", "selection_training_refit", "state_scope",
    "feedback", "memory"))
CONDITIONS = {
    "direct-structured-zero-label-current-trial-v1": "native_structured_no_tools",
    "frozen-programme-zero-label-current-trial-v1": "frozen_programme",
}


def _identifier(value, field):
    if (type(value) is not str or not value or len(value) > 256
            or any(ord(character) < 32 for character in value)):
        raise ValueError("Invalid " + field)
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError("Invalid Unicode in " + field) from error
    return value


def _integer(value, field, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid " + field)
    return value


def _number(value, field):
    if type(value) not in (int, float):
        raise ValueError("Invalid " + field)
    try:
        finite = math.isfinite(value)
    except OverflowError as error:
        raise ValueError("Outside finite numeric range: " + field) from error
    if not finite:
        raise ValueError("Nonfinite " + field)
    # Preserve the original number and type. In particular, finite Python ints
    # are never routed through float, and floats are never rounded or clipped.
    return value


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _case(value):
    if type(value) is not dict or set(value) != CASE_FIELDS:
        raise ValueError("Case requires exactly the six permitted fields")
    case = {field: _identifier(value[field], field)
            for field in ("case_id", "animal_id", "asset_id", "region")}
    if case["region"] not in REGIONS:
        raise ValueError("Unsupported or unassigned source region")
    case["source_trial_row"] = _integer(value["source_trial_row"], "source trial row")
    case["source_cluster_count"] = _integer(value["source_cluster_count"], "source cluster count", 1)
    return case


def _timing(value):
    if type(value) is not dict or set(value) != TIMING_FIELDS:
        raise ValueError("Timing requires exactly the three permitted fields")
    duration = _number(value["click_duration_seconds"], "click duration")
    elapsed = _number(value["elapsed_since_first_click_seconds"], "elapsed click time")
    previous = value["previous_click_interval_seconds"]
    if duration <= 0 or elapsed < 0:
        raise ValueError("Invalid click duration or elapsed time")
    if previous is not None and _number(previous, "previous click interval") <= 0:
        raise ValueError("Previous click interval must be positive when supplied")
    return dict(value)


def canonical_observation_bytes(observations):
    """Canonical JSON array for one current trial's structured observations.

    Cases are sorted by literal region; object keys are sorted; JSON uses ASCII
    escapes, compact separators, UTF-8 bytes and no NaN/infinity extensions.
    Timing-only records are supported by this encoder, while the selected
    paired build_request requires timing_history. Mixing views is rejected.
    There is no numeric conversion, rounding, clipping or label-dependent step.
    """
    if type(observations) is not list or not 1 <= len(observations) <= len(REGIONS):
        raise ValueError("One trial requires one to six named-region observations")
    rows, case_ids, regions = [], set(), set()
    trial_identity, timing_identity, has_history = None, None, None
    for observation in observations:
        if type(observation) is not dict or set(observation) not in (
                {"case", "timing"}, {"case", "timing", "history_rates"}):
            raise ValueError("Observation contains missing, private or unknown fields")
        case = _case(observation["case"])
        timing = _timing(observation["timing"])
        identity = (case["animal_id"], case["asset_id"], case["source_trial_row"])
        timing_bytes = _json_bytes(timing)
        present = "history_rates" in observation
        if trial_identity is None:
            trial_identity, timing_identity, has_history = identity, timing_bytes, present
        if identity != trial_identity or timing_bytes != timing_identity:
            raise ValueError("All regions must share the same current trial and timing")
        if present != has_history:
            raise ValueError("One request cannot mix timing-only and history observations")
        if case["case_id"] in case_ids or case["region"] in regions:
            raise ValueError("Duplicate current-trial case or region")
        case_ids.add(case["case_id"])
        regions.add(case["region"])
        row = {"case": case, "timing": timing}
        if present:
            history = observation["history_rates"]
            if type(history) is not list or len(history) != 100:
                raise ValueError("History requires exactly 100 nominal one-millisecond bins")
            for rate in history:
                if _number(rate, "history rate") < 0:
                    raise ValueError("Deposited-event history rates must be nonnegative")
            row["history_rates"] = history[:]
        rows.append(row)
    rows.sort(key=lambda row: row["case"]["region"])
    return _json_bytes(rows)


def _profile(profile):
    if type(profile) is not dict or set(profile) != PROFILE_FIELDS:
        raise ValueError("Exact selected condition profile fields required")
    condition_id = _identifier(profile["condition_id"], "condition ID")
    if condition_id not in CONDITIONS:
        raise ValueError("Condition is outside the selected zero-label matched pair")
    expected = {
        "condition_id": condition_id,
        "mode": CONDITIONS[condition_id],
        "information_condition": "timing_history",
        "demonstration_labels": 0,
        "benchmark_response_labels": "none",
        "selection_training_refit": "none",
        "state_scope": "fresh_per_trial",
        "feedback": "none",
        "memory": "none",
    }
    for field, value in expected.items():
        if type(profile[field]) is not type(value) or profile[field] != value:
            raise ValueError("Condition violates the selected zero-label/stateless rule: " + field)
    return expected


def build_request(condition_profile, observations, study_id, trial_token):
    """Build a declarative request; it performs no participant/provider action.

    Only condition_id and mode differ between the paired arm envelopes. Given
    identical observations, study and trial IDs, their remaining fields and
    exact canonical payload bytes are identical. payload is a fresh JSON value;
    its checksum covers canonical_observation_bytes(payload), not an arbitrary
    later serializer's output. Providers must preserve this canonical payload.
    """
    profile = _profile(condition_profile)
    _identifier(study_id, "study ID")
    _identifier(trial_token, "trial token")
    payload_bytes = canonical_observation_bytes(observations)
    payload = json.loads(payload_bytes)
    if any("history_rates" not in row for row in payload):
        raise ValueError("The selected matched pair requires timing_history observations")
    return {
        "schema": "neural099-matched-current-trial-request/v1",
        "condition_id": profile["condition_id"],
        "mode": profile["mode"],
        "study_id": study_id,
        "trial_token": trial_token,
        "reset_requirements": {
            "demonstration_labels": 0,
            "benchmark_response_labels": "none",
            "selection_training_refit": "none",
            "state_scope": "fresh_per_trial",
            "feedback": "none",
            "memory": "none",
        },
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "payload": payload,
    }
