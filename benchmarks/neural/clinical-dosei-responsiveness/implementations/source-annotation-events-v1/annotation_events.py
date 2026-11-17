"""Private, source-supported DoSEI marker projection; no EEG or scorer execution.

This adapter consumes authenticated original-source annotation-ledger records.
It does not authenticate arbitrary input by itself. The caller must bind the
complete source release, saved ledger bytes and the full recording population.
"""
from __future__ import annotations

import datetime as dt
import re

FIELDS = ("EVENT", "MOAAS", "SOC", "Misc", "Propofol", "Midazolam", "Endoscopy")
MOAAS_PAIRS = {f"MOAAS{i}": (f"{i}.0", i) for i in range(1, 6)}
SOC_PAIRS = {"LOC": ("0.0", 0), "ROC": ("1.0", 1)}
UNINTERPRETED_MARKERS = frozenset(("BEGIN", "END", "PARA", "PROP"))
CLOCK = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}\Z")
RECORDING = re.compile(r"0|[1-9][0-9]{0,8}\Z")


class AnnotationRefusal(ValueError):
    """Malformed envelope or repeated source identity; no silent row deletion."""


def _require(condition, message):
    if not condition:
        raise AnnotationRefusal(message)


def _time_ms(raw):
    if not CLOCK.fullmatch(raw):
        return None
    try:
        value = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (value.toordinal() * 86_400_000 +
            ((value.hour * 60 + value.minute) * 60 + value.second) * 1000 +
            value.microsecond // 1000)


def adapt_annotation(recording_id: str, row: dict) -> dict:
    """Preserve one source marker and derive only exact documented target pairs.

    Unknown, conflicting or unsupported spellings yield null targets plus
    reasons. Duplicate times and equal successive scores are never deduplicated.
    A recording identifier is never promoted to a biological-person identifier.
    """
    _require(isinstance(recording_id, str) and RECORDING.fullmatch(recording_id),
             "invalid recording identifier")
    _require(isinstance(row, dict), "annotation record must be an object")
    source_row = row.get("source_row")
    line_end = row.get("source_physical_line_end")
    _require(type(source_row) is int and 0 <= source_row < 4_000_000,
             "invalid original zero-based source row")
    _require(type(line_end) is int and line_end >= source_row + 2,
             "invalid original physical line end")
    raw_time = row.get("raw_time")
    time_ms = row.get("recognized_time_ms")
    issues = row.get("timestamp_issues")
    _require(isinstance(raw_time, str) and len(raw_time.encode("utf-8")) <= 4096,
             "invalid raw timestamp envelope")
    _require(time_ms is None or type(time_ms) is int, "invalid saved timestamp type")
    _require(isinstance(issues, list) and len(issues) <= 8 and
             all(isinstance(issue, str) and len(issue) <= 128 for issue in issues),
             "invalid timestamp issue envelope")
    raw = row.get("original_fields")
    _require(isinstance(raw, dict) and set(raw) == set(FIELDS),
             "all seven exact original annotation fields required")
    _require(all(isinstance(raw[field], str) and len(raw[field].encode("utf-8")) <= 4096
                 for field in FIELDS), "invalid original annotation cell")
    _require(any(raw[field] != "" for field in ("EVENT", "MOAAS", "SOC", "Misc")),
             "row is outside the primary annotation ledger")

    reasons = []
    recognized = _time_ms(raw_time)
    if recognized is None:
        reasons.append("unrecognized_source_time")
    elif recognized != time_ms:
        reasons.append("saved_time_disagrees_with_raw_source_time")
    marker = raw["EVENT"]
    kind = "unresolved_source_marker"
    moaas = soc = None
    if marker in MOAAS_PAIRS:
        expected, value = MOAAS_PAIRS[marker]
        kind = "moaas_assessment_marker"
        if raw["MOAAS"] != expected:
            reasons.append("moaas_marker_and_derived_field_disagree")
        if any(raw[field] != "" for field in FIELDS if field not in ("EVENT", "MOAAS")):
            reasons.append("unexpected_companion_annotation_for_moaas")
        if not reasons:
            moaas = value
    elif marker in SOC_PAIRS:
        expected, value = SOC_PAIRS[marker]
        kind = "soc_transition_marker"
        if raw["SOC"] != expected:
            reasons.append("soc_marker_and_derived_field_disagree")
        if any(raw[field] != "" for field in FIELDS if field not in ("EVENT", "SOC")):
            reasons.append("unexpected_companion_annotation_for_soc")
        if not reasons:
            soc = value
    elif marker in UNINTERPRETED_MARKERS:
        kind = "retained_ungraded_source_marker"
        reasons.append("non_target_marker_semantics_not_admitted")
        if raw["MOAAS"] != "" or raw["SOC"] != "":
            reasons.append("target_field_on_non_target_marker")
    else:
        reasons.append("unrecognized_or_missing_exact_EVENT_lexeme")

    return {
        "schema": "dosei_private_annotation_event_v1",
        "visibility": "evaluator_private",
        "source_event_id": f"recording:{recording_id}/row:{source_row}",
        "recording_id": recording_id,
        "biological_person_id": None,
        "source_row": source_row,
        "source_physical_line_end": line_end,
        "raw_time": raw_time,
        "recognized_time_ms": time_ms,
        "timestamp_issues": list(issues),
        "original_fields": dict(raw),
        "marker_kind": kind,
        "moaas_grouped_ordinal": moaas,
        "soc_transition_state": soc,
        "unresolved_reason_codes": reasons,
        "condition": "native_marker_relative_30s_v1",
        "assessment_onset_verified": False,
        "EEG_packet_eligibility": "not_constructed",
        "canonical_scoring_admitted": False,
    }


def adapt_recording(recording_id: str, rows):
    """Stream every source marker once, requiring increasing source row IDs.

    This ordering check does not sort, collapse equal scores, or collapse equal
    timestamps. A repeated/reordered row is an integrity failure, not an event
    inferred away. Empty or partial streams are not certified as a population.
    """
    previous_row = -1
    previous_physical_line = 0
    for row in rows:
        projected = adapt_annotation(recording_id, row)
        _require(projected["source_row"] > previous_row,
                 "duplicate or reordered original source row")
        _require(projected["source_physical_line_end"] > previous_physical_line,
                 "duplicate or reordered original physical line")
        previous_row = projected["source_row"]
        previous_physical_line = projected["source_physical_line_end"]
        yield projected
