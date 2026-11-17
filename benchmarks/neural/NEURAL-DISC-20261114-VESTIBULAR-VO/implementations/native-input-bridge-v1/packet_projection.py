"""Pure projection of an operator-admitted complete prepared repeat inventory.

No MAT loader, physical-role inference, prior fitting, scoring or isolation is
provided here. Admission hashes bind exact operator evidence; they cannot prove
its biological meaning. No authentic admission currently accompanies this code.
The future physical loader must supply all fields from reviewed source bindings.

``project(prepared, admission, accepted_admission_sha256=..., id_key=...)``
returns separate ``public`` and ``protected`` objects. Only ``public`` may reach
a participant. ``tile_query`` returns all tiles to the trusted packager; each
invocation must later receive only one tile in a fresh isolated context.
"""

import copy
import hashlib
import hmac
import json
import math
from pathlib import Path
import types


EVALUATOR_SHA256 = "9defa828dd926b68f18cac01c60a096e8b6d5d0482492b7c319e2d3b86ec9d84"
SHIFT_PREDECESSOR_SHA256 = "bf96348b5c0e15f5219ce4488280739fccd3217974f420c2ad123d9e1b820c11"
COUNTS = {"D": (11, 6), "B": (34, 26), "O": (4, 3)}
TASK = "NEURAL-DISC-20261114-VESTIBULAR-VO"


class Invalid(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Invalid(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def canonical_sha256(value):
    """Canonical logical identity, not a claim about original MAT bytes."""
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def load_evaluator():
    """Reuse only pinned schema helpers/constants; never call a scoring API."""
    path = Path(__file__).resolve().parent.parent / "condition-evaluator-v2" / "evaluate.py"
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == EVALUATOR_SHA256, "evaluator source pin")
    module = types.ModuleType("vestibular_projection_schema_authority")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _identities(e, values, message):
    need(isinstance(values, list), message)
    for value in values:
        e.identifier(value)
    need(len(set(values)) == len(values), message)
    return values


def _census(e, census):
    e.fields(census, ("animals", "neurons", "pairs", "groups", "excluded_pairs",
                     "excluded_neurons", "conditions", "additional_conditions",
                     "coverage", "complete_source_record_ids"))
    need(set(_identities(e, census["animals"], "animal identities")) == set(COUNTS),
         "complete D/B/O animal census")
    neurons = e.unique_rows(census["neurons"], 49)
    pairs = e.unique_rows(census["pairs"], 35)
    groups = e.unique_rows(census["groups"])
    need(groups, "recording groups required")
    for neuron in neurons.values():
        e.fields(neuron, ("id", "animal_id"))
        need(neuron["animal_id"] in COUNTS, "unknown neuron animal")
    relationships = set()
    for pair in pairs.values():
        e.fields(pair, ("id", "animal_id", "neuron_ids", "simultaneity_evidence_sha256"))
        members = _identities(e, pair["neuron_ids"], "pair members")
        need(pair["animal_id"] in COUNTS and len(members) == 2
             and all(n in neurons and neurons[n]["animal_id"] == pair["animal_id"] for n in members),
             "genuine within-animal pair required")
        relationship = (pair["animal_id"], tuple(sorted(members)))
        need(relationship not in relationships, "duplicate genuine pair aliases")
        relationships.add(relationship)
        e.digest(pair["simultaneity_evidence_sha256"])
    for animal, (n, p) in COUNTS.items():
        need(sum(x["animal_id"] == animal for x in neurons.values()) == n
             and sum(x["animal_id"] == animal for x in pairs.values()) == p,
             "complete animal-specific neuron/pair counts")
    physical, used_neurons, used_pairs = set(), set(), set()
    for group in groups.values():
        e.fields(group, ("id", "animal_id", "session_id", "recording_id", "stratum", "neuron_ids", "pair_id"))
        e.identifier(group["session_id"])
        e.identifier(group["recording_id"])
        members = _identities(e, group["neuron_ids"], "group members")
        need(group["animal_id"] in COUNTS
             and all(n in neurons and neurons[n]["animal_id"] == group["animal_id"] for n in members),
             "group biological membership")
        if group["stratum"] == "simultaneous_pair":
            pair = pairs.get(group["pair_id"])
            need(pair is not None and len(members) == 2
                 and set(members) == set(pair["neuron_ids"])
                 and group["animal_id"] == pair["animal_id"], "group genuine pair membership")
            used_pairs.add(pair["id"])
        else:
            need(group["stratum"] == "single_neuron" and len(members) == 1
                 and group["pair_id"] is None, "separate single-neuron stratum")
        key = (group["animal_id"], group["session_id"], group["recording_id"], tuple(sorted(members)))
        need(key not in physical, "duplicate physical recording group")
        physical.add(key)
        used_neurons.update(members)
    e.reasons(census["excluded_pairs"], set(pairs) - used_pairs)
    e.reasons(census["excluded_neurons"], set(neurons) - used_neurons)
    conditions = _identities(e, census["conditions"], "complete condition list")
    need(set(e.CONDITIONS) <= set(conditions), "all nine documented motion conditions")
    e.reasons(census["additional_conditions"], set(conditions) - set(e.CONDITIONS))
    _identities(e, census["complete_source_record_ids"], "complete source record order")
    return neurons, pairs, groups


def _active_geometry(e, row, group):
    ticks, times = row["sample_ticks"], row["sample_times_s"]
    need(isinstance(ticks, list) and ticks and all(type(t) is int for t in ticks)
         and all(a < b for a, b in zip(ticks, ticks[1:])), "exact ordered integer sample ticks")
    need(isinstance(times, list) and len(times) == len(ticks), "complete documented time grid")
    duration = e.finite(row["duration_s"])
    clock = row["clock"]
    e.fields(clock, ("id", "origin_tick", "seconds_numerator", "seconds_denominator", "tick_unit",
                     "target_unit", "axis", "measurement_kind", "units_evidence_sha256",
                     "alignment_evidence_sha256"))
    for key in ("id", "tick_unit", "target_unit", "axis"):
        e.identifier(clock[key])
    for key in ("units_evidence_sha256", "alignment_evidence_sha256"):
        e.digest(clock[key])
    need(clock["measurement_kind"] == "measured_angular_head_velocity", "measured velocity role required")
    need(type(clock["origin_tick"]) is int
         and type(clock["seconds_numerator"]) is int and clock["seconds_numerator"] > 0
         and type(clock["seconds_denominator"]) is int and clock["seconds_denominator"] > 0,
         "documented exact rational tick scale")
    relative_ticks = [t - clock["origin_tick"] for t in ticks]
    for tick, time in zip(relative_ticks, times):
        e.finite(time)
        need(tick >= 0, "sample before documented repeat origin")
        try:
            expected = tick * clock["seconds_numerator"] / clock["seconds_denominator"]
        except OverflowError:
            raise Invalid("clock conversion outside finite support") from None
        need(math.isfinite(expected) and time == expected, "sample seconds disagree with documented tick scale")
    need(all(a < b for a, b in zip(times, times[1:])) and duration > times[-1],
         "whole-repeat duration and ordered seconds")
    channels = row["channels"]
    need(isinstance(channels, list) and len(channels) == len(group["neuron_ids"]), "all genuine channels required")
    seen = set()
    for channel in channels:
        e.fields(channel, ("neuron_id", "clock_id", "alignment_evidence_sha256",
                           "event_times_s", "input_valid_intervals_s"))
        neuron = channel["neuron_id"]
        need(neuron in group["neuron_ids"] and neuron not in seen, "unique complete channel membership")
        seen.add(neuron)
        need(channel["clock_id"] == clock["id"]
             and channel["alignment_evidence_sha256"] == clock["alignment_evidence_sha256"],
             "channels must share the documented acquired/aligned clock")
        events = channel["event_times_s"]
        need(isinstance(events, list), "explicit complete event list")
        for event in events:
            e.finite(event)
        need(all(0 <= t < duration for t in events)
             and all(a <= b for a, b in zip(events, events[1:])), "ordered complete event support")
        intervals = channel["input_valid_intervals_s"]
        need(isinstance(intervals, list), "input validity intervals")
        last = 0
        for interval in intervals:
            need(isinstance(interval, list) and len(interval) == 2, "validity interval shape")
            a, b = (e.finite(value) for value in interval)
            need(last <= a < b <= duration, "nonoverlapping original validity intervals")
            last = b
    target, mask = row["target"], row["valid_mask"]
    need(isinstance(mask, list) and len(mask) == len(ticks)
         and all(type(v) is bool for v in mask) and any(mask), "fixed nonempty target support")
    need(isinstance(target, list) and len(target) == len(ticks), "complete target vector")
    for use, value in zip(mask, target):
        if use or value is not None:
            e.finite(value)
    return relative_ticks


def _coverage(e, census, groups, records):
    expected = {(r["group_id"], r["condition"], r["repeat_id"])
                for r in records if r["partition"] == "query"}
    need(expected, "at least one held repeat required")
    observed, cells = set(), set()
    need(isinstance(census["coverage"], list), "complete operator coverage list")
    for cell in census["coverage"]:
        e.fields(cell, ("animal_id", "condition", "stratum", "status", "group_repeats", "unavailable_groups"), ("reason",))
        key = (cell["animal_id"], cell["condition"], cell["stratum"])
        need(key[0] in COUNTS and key[1] in census["conditions"] and key[2] in e.STRATA
             and key not in cells, "unique animal-condition-stratum cell")
        cells.add(key)
        eligible = {g for g, row in groups.items() if (row["animal_id"], row["stratum"]) == (key[0], key[2])}
        need(isinstance(cell["group_repeats"], list), "explicit held group repeats")
        selected = set()
        for member in cell["group_repeats"]:
            e.fields(member, ("group_id", "repeat_ids"))
            group = member["group_id"]
            need(group in eligible and group not in selected, "unique eligible group in coverage")
            selected.add(group)
            repeats = _identities(e, member["repeat_ids"], "complete held repeat identities")
            need(repeats, "nonempty held repeat list")
            observed.update((group, key[1], repeat) for repeat in repeats)
        e.reasons(cell["unavailable_groups"], eligible - selected)
        if selected:
            need(cell["status"] == "available" and "reason" not in cell, "available cell status")
        else:
            need(cell["status"] == "unavailable", "explicit unavailable cell")
            e.identifier(cell.get("reason"))
    need(cells == {(a, c, s) for a in COUNTS for c in census["conditions"] for s in e.STRATA},
         "complete animal-condition-stratum decisions")
    need(observed == expected, "complete held repeats match the frozen census")
    need(any(groups[g]["stratum"] == "simultaneous_pair" for g, _, _ in expected), "primary pair case required")


def validate(prepared, admission, *, accepted_admission_sha256):
    """Validate exact joins to separately supplied operator admission evidence.

    The trusted caller supplies the accepted admission identity independently of
    participant material. This identity is an integrity join, not proof of source
    roles, eligibility, scientific validity or independent review.
    """
    e = load_evaluator()
    e.fields(prepared, ("schema", "task_id", "source_sha256", "census", "records"))
    need(prepared["schema"] == "vestibular_prepared_repeats_v1" and prepared["task_id"] == TASK,
         "prepared repeat schema")
    e.digest(prepared["source_sha256"])
    e.fields(admission, ("schema", "kind", "source_sha256", "prepared_sha256", "census_sha256",
                         "role_binding_sha256", "split_sha256", "protocol_sha256", "review_evidence_sha256"))
    need(admission["schema"] == "vestibular_native_bridge_admission_v1"
         and admission["kind"] in ("generated_control", "assessor_admitted_native"), "explicit native-bridge admission")
    for key, value in admission.items():
        if key.endswith("sha256"):
            e.digest(value)
    e.digest(accepted_admission_sha256)
    need(canonical_sha256(admission) == accepted_admission_sha256, "unaccepted operator admission identity")
    need(admission["source_sha256"] == prepared["source_sha256"]
         and admission["prepared_sha256"] == canonical_sha256(prepared)
         and admission["census_sha256"] == canonical_sha256(prepared["census"]), "admission does not bind this complete preparation")
    neurons, pairs, groups = _census(e, prepared["census"])
    records_by_id = e.unique_rows(prepared["records"])
    order = prepared["census"]["complete_source_record_ids"]
    need(set(order) == set(records_by_id), "every original source record remains accounted for")
    records = [records_by_id[key] for key in order]
    presentations, repeat_keys, calibration, query_groups = {}, set(), set(), set()
    seen_groups, relative_ticks, shared_channels, presentation_geometry = set(), {}, {}, {}
    active_presentations = set()
    for row in records:
        common = ("id", "group_id", "condition", "repeat_id", "presentation_id", "partition")
        if row.get("partition") == "excluded":
            e.fields(row, common + ("exclusion_reason", "exclusion_evidence_sha256"))
            e.identifier(row["exclusion_reason"])
            e.digest(row["exclusion_evidence_sha256"])
        else:
            e.fields(row, common + ("sample_ticks", "sample_times_s", "duration_s", "clock", "channels", "target", "valid_mask"))
            need(row["partition"] in ("train", "query"), "declared record partition")
        for key in ("group_id", "condition", "repeat_id", "presentation_id"):
            e.identifier(row[key])
        need(row["group_id"] in groups and row["condition"] in prepared["census"]["conditions"], "known group and condition")
        group = groups[row["group_id"]]
        seen_groups.add(group["id"])
        repeat_key = (group["id"], row["condition"], row["repeat_id"])
        need(repeat_key not in repeat_keys, "duplicate source repeat aliases")
        repeat_keys.add(repeat_key)
        presentation_key = (row["partition"], group["animal_id"], group["session_id"], group["recording_id"], row["condition"])
        previous = presentations.setdefault(row["presentation_id"], presentation_key)
        need(previous == presentation_key, "one source presentation cannot cross partitions or acquisitions")
        if row["partition"] == "excluded":
            continue
        acquired_view = (group["id"], row["condition"], row["presentation_id"])
        need(acquired_view not in active_presentations, "duplicate active acquired presentation within group")
        active_presentations.add(acquired_view)
        relative_ticks[row["id"]] = _active_geometry(e, row, group)
        geometry = (row["sample_ticks"], row["sample_times_s"], row["duration_s"], row["clock"], row["target"])
        old_geometry = presentation_geometry.setdefault(row["presentation_id"], geometry)
        need(old_geometry == geometry, "one acquired presentation must retain common target geometry")
        # Repeated pair views of the same acquired channel must agree exactly.
        for channel in row["channels"]:
            key = (row["presentation_id"], channel["neuron_id"])
            payload = (row["sample_ticks"], row["sample_times_s"], row["duration_s"], row["clock"],
                       row["target"], channel)
            old = shared_channels.setdefault(key, payload)
            need(old == payload, "inconsistent shared-neuron presentation view")
        key = (group["id"], row["condition"])
        (calibration if row["partition"] == "train" else query_groups).add(key)
    need(seen_groups == set(groups), "all original recording groups accounted for")
    need(query_groups <= calibration, "each held group-condition needs separate complete training repeats")
    _coverage(e, prepared["census"], groups, records)
    return {"neurons": neurons, "pairs": pairs, "groups": groups, "records": records,
            "relative_ticks": relative_ticks}


def project(prepared, admission, *, accepted_admission_sha256, id_key):
    """Strict public whitelist plus a separate operator-owned target inventory."""
    need(type(id_key) is bytes and len(id_key) >= 32, "operator-only opaque-ID key of at least32 bytes")
    plan = validate(prepared, admission, accepted_admission_sha256=accepted_admission_sha256)

    def opaque(kind, original):
        payload = json.dumps([kind, original], separators=(",", ":")).encode()
        return hmac.new(id_key, payload, hashlib.sha256).hexdigest()

    training, queries, targets, identity_map = [], [], [], []
    for row in plan["records"]:
        identity_map.append({"record_id": row["id"], "case_id": opaque("case", row["id"]),
                             "group_id": row["group_id"], "public_group_id": opaque("group", row["group_id"]),
                             "partition": row["partition"]})
        if row["partition"] == "excluded":
            continue
        clock = row["clock"]
        channels = {channel["neuron_id"]: channel for channel in row["channels"]}
        ordered = [channels[neuron] for neuron in plan["groups"][row["group_id"]]["neuron_ids"]]
        item = {"case_id": opaque("case", row["id"]), "group_id": opaque("group", row["group_id"]),
                "condition": row["condition"], "duration_s": row["duration_s"],
                "sample_ticks": list(plan["relative_ticks"][row["id"]]),
                "sample_times_s": list(row["sample_times_s"]),
                "clock": {key: clock[key] for key in ("tick_unit", "seconds_numerator", "seconds_denominator", "target_unit", "axis")},
                "channel_ids": [opaque("neuron", channel["neuron_id"]) for channel in ordered],
                "event_times_s": [copy.deepcopy(channel["event_times_s"]) for channel in ordered],
                "input_valid_intervals_s": [copy.deepcopy(channel["input_valid_intervals_s"]) for channel in ordered]}
        if row["partition"] == "train":
            item["calibration_velocity"] = copy.deepcopy(row["target"])
            item["calibration_valid_mask"] = list(row["valid_mask"])
            training.append(item)
        else:
            queries.append(item)
            # Exact v2 case fields except prior, which requires later qualification.
            targets.append({"id": item["case_id"], "group_id": row["group_id"], "condition": row["condition"],
                            "repeat_id": row["repeat_id"], "sample_ticks": list(item["sample_ticks"]),
                            "valid_mask": list(row["valid_mask"]), "target": copy.deepcopy(row["target"])})
    public = {"schema": "vestibular_public_complete_events_v1", "task_id": TASK,
              "information_condition": "full-repeat-v1", "representation": "complete spike events",
              "time_unit": "s", "calibration": training, "queries": queries}
    protected = {"schema": "vestibular_protected_target_inventory_v1", "task_id": TASK,
                 "admission": copy.deepcopy(admission), "admission_sha256": accepted_admission_sha256,
                 "qualification": "Operator identity join only; source-role, scientific and isolation evidence remain separately reviewed.",
                 "prior_attached": False, "evaluator_sha256": EVALUATOR_SHA256,
                 "census": copy.deepcopy(prepared["census"]), "source_records": copy.deepcopy(plan["records"]),
                 "cases": targets, "identity_map": identity_map,
                 "neuron_public_ids": {n: opaque("neuron", n) for n in plan["neurons"]}}
    return {"public": public, "protected": protected}


def tile_query(query, max_core_samples, past_s, future_s):
    """Return all one-coordinate tiles to the operator, never one model prompt.

    Half-open event support and clipped validity exactly preserve the accepted
    logical endpoint. This function does not establish context isolation.
    """
    need(type(max_core_samples) is int and max_core_samples == 1 and number(past_s) and past_s >= 0
         and number(future_s) and future_s >= 0, "tile parameters require one coordinate")
    expected = {"case_id", "group_id", "condition", "duration_s", "sample_ticks", "sample_times_s",
                "clock", "channel_ids", "event_times_s", "input_valid_intervals_s"}
    need(isinstance(query, dict) and set(query) == expected, "only a projected query may be tiled")
    clock_keys = ("tick_unit", "seconds_numerator", "seconds_denominator", "target_unit", "axis")
    clock = query["clock"]
    need(isinstance(clock, dict) and set(clock) == set(clock_keys), "exact public clock fields required")
    e = load_evaluator()
    for key in ("tick_unit", "target_unit", "axis"):
        e.identifier(clock[key])
    need(all(type(clock[key]) is int and clock[key] > 0 for key in ("seconds_numerator", "seconds_denominator")),
         "public rational clock scale")
    public_clock = {key: clock[key] for key in clock_keys}
    times, out = query["sample_times_s"], []
    for start in range(len(times)):
        low = max(0, times[start] - past_s)
        high = min(query["duration_s"], times[start] + future_s)
        out.append({"case_id": query["case_id"], "core_start": start, "core_end": start + 1,
                    "information_condition": "bounded-single-core-v1",
                    "sample_times_s": times[start:start + 1], "sample_ticks": query["sample_ticks"][start:start + 1],
                    "history_start_s": low, "extent_end_s": high,
                    "group_id": query["group_id"], "condition": query["condition"],
                    "clock": dict(public_clock), "channel_ids": list(query["channel_ids"]),
                    "event_times_s": [[v for v in ch if low <= v < high] for ch in query["event_times_s"]],
                    "input_valid_intervals_s": [[[max(a, low), min(b, high)] for a, b in channel if max(a, low) < min(b, high)]
                                                for channel in query["input_valid_intervals_s"]],
                    "past_support_s": past_s, "future_support_s": future_s,
                    "context_rule": "One coordinate per fresh isolated context/workspace; no sibling tiles, complete query or query memory. Projection alone does not provide this isolation."})
    return out


def paired_shift(events, intervals, duration_s, shift_s, history_s, sample_times):
    """Unchanged predecessor algorithm: common shift, past-history seam mask.

    Adapted only for formatting from the authored logical endpoint identified by
    SHIFT_PREDECESSOR_SHA256. It does not qualify any future-context model.
    Inputs must be complete validated event/validity records, not tile fragments.
    """
    need(number(duration_s) and duration_s > 0 and number(shift_s) and 0 < shift_s < duration_s
         and number(history_s) and 0 <= history_s < min(shift_s, duration_s - shift_s), "shift_support")
    need(len(events) == len(intervals), "shift_validity_channels")
    shifted = [sorted((t + shift_s) % duration_s for t in ch) for ch in events]
    shifted_intervals = []
    for channel in intervals:
        moved = []
        for a, b in channel:
            low = (a + shift_s) % duration_s
            high = low + b - a
            if high <= duration_s:
                moved.append([low, high])
            else:
                moved.extend([[low, duration_s], [0, high - duration_s]])
        shifted_intervals.append(sorted(moved))

    def distance(t, point):
        return min(abs(t - point), duration_s - abs(t - point))

    def supported(channel, t):
        return any(a <= t - history_s and t <= b for a, b in channel)

    mask = [distance(t, 0) > history_s and distance(t, shift_s) > history_s
            and all(supported(ch, t) for ch in intervals + shifted_intervals) for t in sample_times]
    need(any(mask), "shift_no_valid_core")
    return shifted, shifted_intervals, mask
