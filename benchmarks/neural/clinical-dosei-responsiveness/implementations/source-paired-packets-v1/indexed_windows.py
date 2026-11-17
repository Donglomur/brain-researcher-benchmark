"""Compact private window indices and on-demand projections; no file I/O.

The caller must authenticate the complete clock census, accepted numerical
arrays, annotation events and index manifest. This module does not prove source
identity, grant native access, or finalize participant delivery.
"""
from bisect import bisect_right
from dataclasses import dataclass
import re

WINDOW_MS = 30000
MAX_ROWS = 4000000
CLOCK_FIELDS = frozenset(("first_time_ms", "row_count", "last_time_ms",
                         "duplicate_source_rows", "issue_counts"))
INDEX_FIELDS = frozenset(("schema", "visibility", "condition", "case_id",
                         "evaluator", "clock", "start_row", "end_row_exclusive",
                         "coverage", "source_authentication_required"))
EVALUATOR_FIELDS = frozenset(("schema", "visibility", "case_id", "source_event_id",
    "recording_id", "source_row", "marker_time_ms", "moaas_grouped_ordinal",
    "source_unresolved_reason_codes", "biological_person_id", "split",
    "canonical_scoring_admitted", "population_disposition"))


class IndexRefusal(ValueError):
    """Invalid/incomplete input; never a signal-quality population filter."""


def require(ok, message):
    if not ok:
        raise IndexRefusal(message)


def exact_int(value, low, high, description):
    require(type(value) is int and low <= value <= high, description)
    return value


@dataclass(frozen=True, slots=True)
class NativeClock:
    """Exact current-release clock representation from authenticated metadata.

    A duplicate at row d means time(d)==time(d-1). At most one is admitted.
    issue_counts must be the complete saved count dictionary, not a selection.
    Authentication of that completeness and source binding remains caller-owned.
    """
    first_time_ms: int
    row_count: int
    last_time_ms: int
    duplicate_source_rows: tuple
    issue_counts: dict

    def __post_init__(self):
        exact_int(self.first_time_ms, 0, 2**63-1, "invalid first source time")
        exact_int(self.row_count, 1, MAX_ROWS, "invalid complete source row count")
        exact_int(self.last_time_ms, 0, 2**63-1, "invalid last source time")
        require(type(self.duplicate_source_rows) is tuple and
                len(self.duplicate_source_rows) <= 1, "at most one exact duplicate position")
        for position in self.duplicate_source_rows:
            exact_int(position, 1, self.row_count-1, "invalid duplicate source position")
        require(type(self.issue_counts) is dict and all(type(k) is str and
                type(v) is int and v > 0 for k, v in self.issue_counts.items()),
                "exact complete clock counters required")
        expected = {"duplicate_timestamp": 1} if self.duplicate_source_rows else {}
        require(self.issue_counts == expected, "unadmitted or inconsistent clock anomaly")
        require(self.last_time_ms == self.first_time_ms + 4*(self.row_count-1) -
                4*len(self.duplicate_source_rows), "last source time differs")
        # Retain only immutable validated facts, not a caller-mutable dictionary.
        object.__setattr__(self, "issue_counts", tuple(sorted(expected.items())))

    def time(self, source_row):
        exact_int(source_row, 0, self.row_count-1, "source row outside recording")
        return (self.first_time_ms + 4*source_row -
                4*bisect_right(self.duplicate_source_rows, source_row))

    def lower_bound(self, time_ms):
        require(type(time_ms) is int, "integer boundary required")
        left, right = 0, self.row_count
        while left < right:
            middle = (left + right)//2
            if self.time(middle) < time_ms:
                left = middle + 1
            else:
                right = middle
        return left

    def binding(self):
        return {"first_time_ms": self.first_time_ms, "row_count": self.row_count,
                "last_time_ms": self.last_time_ms,
                "duplicate_source_rows": list(self.duplicate_source_rows),
                "issue_counts": dict(self.issue_counts)}

    @classmethod
    def from_binding(cls, value):
        require(type(value) is dict and set(value) == CLOCK_FIELDS, "clock binding shape")
        require(type(value["duplicate_source_rows"]) is list, "duplicate positions must be a list")
        return cls(value["first_time_ms"], value["row_count"], value["last_time_ms"],
                   tuple(value["duplicate_source_rows"]), value["issue_counts"])


def _coverage(clock, marker_ms, start, end):
    missing = max(0, min(WINDOW_MS, clock.first_time_ms-(marker_ms-WINDOW_MS)))
    return {"source_prefix_missing_ms": missing,
            "full_interval_recorded": missing == 0, "row_count": end-start}


def _target_and_reasons(target, reasons):
    require(target is None or (type(target) is int and 1 <= target <= 5),
            "invalid grouped responsiveness category")
    require(type(reasons) is list and len(reasons) <= 32 and
            all(type(value) is str and len(value.encode("utf-8")) <= 256 for value in reasons),
            "bounded exact source reason list required")
    return list(reasons)


def make_case_index(clock, event, *, secret, core):
    """Return a private assessment index, or None for an accepted other marker.

    No EEG is read. The event's original row and timestamp must exactly match
    the complete accepted clock model; this is not inferred assessment onset.
    """
    require(type(clock) is NativeClock, "validated native clock required")
    require(type(event) is dict, "private source event required")
    rid, row = event.get("recording_id"), event.get("source_row")
    case_id = core.opaque_case_id(secret, rid, row)
    marker = clock.time(row)
    require(event.get("schema") == "dosei_private_annotation_event_v1" and
            event.get("visibility") == "evaluator_private" and
            event.get("source_event_id") == f"recording:{rid}/row:{row}" and
            type(event.get("recognized_time_ms")) is int and
            event["recognized_time_ms"] == marker and
            event.get("condition") == core.CONDITION, "source event/clock join differs")
    if event.get("marker_kind") != "moaas_assessment_marker":
        return None
    reasons = _target_and_reasons(event.get("moaas_grouped_ordinal"),
                                 event.get("unresolved_reason_codes"))
    require(event.get("biological_person_id") is None and
            event.get("assessment_onset_verified") is False,
            "unadmitted person or onset assertion")
    start, end = clock.lower_bound(marker-WINDOW_MS), clock.lower_bound(marker)
    require(0 <= start <= end <= row and end-start <= 7501, "window bounds")
    private = {
        "schema": "dosei_private_case_binding_v1", "visibility": "evaluator_private",
        "case_id": case_id, "source_event_id": event["source_event_id"],
        "recording_id": rid, "source_row": row, "marker_time_ms": marker,
        "moaas_grouped_ordinal": event.get("moaas_grouped_ordinal"),
        "source_unresolved_reason_codes": reasons, "biological_person_id": None,
        "split": None, "canonical_scoring_admitted": False,
        "population_disposition": "retained_without_signal_quality_filtering",
    }
    return {"schema": "dosei_private_window_index_v1", "visibility": "evaluator_private",
            "condition": core.CONDITION, "case_id": case_id, "evaluator": private,
            "clock": clock.binding(), "start_row": start, "end_row_exclusive": end,
            "coverage": _coverage(clock, marker, start, end),
            "source_authentication_required": True}


def validate_index(index, *, secret, core):
    """Recompute compact geometry and HMAC binding, without source payload access."""
    require(type(index) is dict and set(index) == INDEX_FIELDS, "index shape")
    require(index["schema"] == "dosei_private_window_index_v1" and
            index["visibility"] == "evaluator_private" and
            index["condition"] == core.CONDITION and
            index["source_authentication_required"] is True, "private index scope")
    clock = NativeClock.from_binding(index["clock"])
    e = index["evaluator"]
    require(type(e) is dict and set(e) == EVALUATOR_FIELDS, "evaluator binding shape")
    require(type(index["case_id"]) is str and
            re.fullmatch("[0-9a-f]{64}", index["case_id"]) is not None, "opaque case ID")
    expected_id = core.opaque_case_id(secret, e["recording_id"], e["source_row"])
    marker = clock.time(e["source_row"])
    require(e["schema"] == "dosei_private_case_binding_v1" and
            e["visibility"] == "evaluator_private" and
            e["case_id"] == index["case_id"] == expected_id and
            e["source_event_id"] == f"recording:{e['recording_id']}/row:{e['source_row']}" and
            type(e["marker_time_ms"]) is int and e["marker_time_ms"] == marker and
            e["biological_person_id"] is None and e["split"] is None and
            e["canonical_scoring_admitted"] is False and
            e["population_disposition"] == "retained_without_signal_quality_filtering",
            "evaluator identity or scope differs")
    _target_and_reasons(e["moaas_grouped_ordinal"], e["source_unresolved_reason_codes"])
    start, end = clock.lower_bound(marker-WINDOW_MS), clock.lower_bound(marker)
    require(type(index["start_row"]) is int and type(index["end_row_exclusive"]) is int and
            index["start_row"] == start and index["end_row_exclusive"] == end and
            0 <= start <= end <= e["source_row"] and end-start <= 7501, "index window differs")
    expected = _coverage(clock, marker, start, end)
    coverage = index["coverage"]
    require(type(coverage) is dict and set(coverage) == set(expected) and
            type(coverage["source_prefix_missing_ms"]) is int and
            type(coverage["row_count"]) is int and type(coverage["full_interval_recorded"]) is bool and
            coverage == expected, "index coverage differs")
    return clock, marker, start, end, expected


def project_window(index, rows, *, secret, core, policy):
    """Consume only rows[start:end] once and return the identical public packet.

    Each supplied row is the existing core's six-field native tuple. Completion
    requires exact EOF, checked with one extra iterator request but without
    interpreting an unexpected row. No marker/future numeric value is required.
    Any exception means no packet; the caller retains the failure receipt.
    Authentication/final delivery and enforcing bounded source seeks are caller
    obligations. This pure function opens nothing and stores no projection.
    """
    clock, marker, start, end, coverage = validate_index(index, secret=secret, core=core)
    relative, values, masks, endpoints = [], [], [], []
    iterator = iter(rows)
    sentinel = object()
    for expected_row in range(start, end):
        row = next(iterator, sentinel)
        require(row is not sentinel, "missing observation row")
        require(type(row) is tuple and len(row) == 6, "six-field native tuple required")
        source_row, time_ms, value1, value2, quality1, quality2 = row
        require(type(source_row) is int and source_row == expected_row and
                type(time_ms) is int and time_ms == clock.time(expected_row),
                "observation source row/clock differs")
        require(marker-WINDOW_MS <= time_ms < marker, "observation outside half-open window")
        left = core.observe(value1, quality1, policy)
        right = core.observe(value2, quality2, policy)
        relative.append(time_ms-marker)
        values.append([left[0], right[0]])
        masks.append([left[1], right[1]])
        endpoints.append([left[2], right[2]])
    require(next(iterator, sentinel) is sentinel, "extra observation row")
    result = {
        "schema": "dosei_paired_observation_v1", "condition": core.CONDITION,
        "case_id": index["case_id"], "channels": list(core.CHANNELS),
        "units": "microvolt", "interval_ms": [-WINDOW_MS, 0],
        "relative_time_ms": relative, "values_uv": values,
        "observation_mask": masks, "source_endpoint_mask": endpoints, "coverage": coverage,
    }
    require(set(result) == core.PUBLIC_FIELDS, "participant allowlist differs")
    return result
