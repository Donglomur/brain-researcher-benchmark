"""Complete event output decoding in the protected host; no score from candidates."""
from fractions import Fraction
from .protocol import require, identifier, integer, fraction, rational, unique, parse_json, digest, validate_pin


def decode_events(event_lines, roster, clock, bounds):
    """Consume all rows, retain duplicate events, enforce exact full-view clock.

    Inputs are already immutable admitted output bytes. A caller must not use
    candidate-declared counts as truth support, and must not stop at a cap and
    score the prefix. This function raises on any overrun instead.
    """
    ids = [identifier(x, "detected unit ID") for x in roster]
    require(len(ids) == len(set(ids)), "duplicate-output-unit", "roster")
    require(len(ids) <= bounds["max_units"], "unit-output-limit", "complete roster")
    fs = fraction(clock["sample_frequency"])
    origin = fraction(clock["sample_origin"])
    duration = fraction(clock["duration_seconds"])
    scale = fraction(clock["time_scale"])
    require(fs > 0 and duration > 0 and scale > 0, "invalid-output-clock", "positive scale/clock")
    result = {x: [] for x in ids}
    rows, byte_count = [], 0
    for index, body in enumerate(event_lines):
        require(index < bounds["max_events"], "event-output-limit", "no prefix scoring")
        byte_count += len(body)
        require(byte_count <= bounds["max_bytes"], "event-byte-limit", "no prefix scoring")
        row = parse_json(body, bounds["max_line_bytes"])
        require(set(row) == {"unit_id", "sample", "original_row"}, "event-output-schema", str(index))
        require(row["unit_id"] in result, "event-unit-not-in-roster", row["unit_id"])
        integer(row["original_row"], "original row")
        require(row["original_row"] == index, "event-row-identity", str(index))
        sample = Fraction(row["sample"]) if type(row["sample"]) is int else fraction(row["sample"])
        t = (sample - origin) / fs * scale
        require(0 <= t < duration, "event-outside-clock", str(index))
        result[row["unit_id"]].append(rational(t))
        rows.append({"unit_id": row["unit_id"], "original_row": index, "sample": rational(sample)})
    return {"detected": [{"unit_id": unit, "events": result[unit]} for unit in ids],
            "row_provenance": rows, "event_count": len(rows), "bytes_consumed": byte_count,
            "whole_output_consumed": True, "duplicate_events_removed": False}


def join_protected_case(case_metadata, truth_payload, decoded_output):
    truth = unique(truth_payload["units"], "unit_id")
    targets = {row["unit_id"] for row in case_metadata["unit_roles"]
               if row["role"] == "single-unit-target"}
    require(set(truth) == targets, "truth-role-join-mismatch", "complete designated single units")
    require(truth_payload["signal_view_id"] == case_metadata["signal_view_id"],
            "truth-signal-view-mismatch", case_metadata["id"])
    require(truth_payload["role_join_digest"] == case_metadata["role_join_digest"],
            "truth-provenance-mismatch", case_metadata["id"])
    require(truth_payload["clock_digest"] == digest(case_metadata["truth_clock"]),
            "truth-clock-mismatch", case_metadata["id"])
    require(decoded_output["binding"]["case_metadata_digest"] == digest(case_metadata)
            and decoded_output["binding"]["clock_digest"] == digest(case_metadata["output_clock"]),
            "decoded-case-clock-mismatch", case_metadata["id"])
    duration = fraction(case_metadata["duration_seconds"])
    for row in truth.values():
        for t in row["events"]:
            require(0 <= fraction(t) < duration, "truth-outside-full-view", row["unit_id"])
    return {"id": case_metadata["id"], "kind": case_metadata["kind"],
            "duration": case_metadata["duration_seconds"],
            "quality_bin_seconds": case_metadata["quality_bin_seconds"],
            "truth": list(truth.values()), "detected": decoded_output["detected"]}


def decode_selected_output(store, binding, case_metadata, seal, native, limits):
    """Decode only externally selected complete event bytes and metadata."""
    metadata = store.json(validate_pin(binding["output_metadata_pin"]), 1024 * 1024)
    clock = store.json(validate_pin(binding["clock_pin"]), 1024 * 1024)
    require(clock == case_metadata["output_clock"], "selected-output-clock-mismatch", case_metadata["id"])
    require(metadata["case_id"] == case_metadata["id"]
            and metadata["signal_view_id"] == case_metadata["signal_view_id"]
            and metadata["clock_digest"] == digest(clock)
            and metadata["candidate_seal_digest"] == digest(seal)
            and metadata["native_job_digest"] == native["job_digest"]
            and metadata["event_output_pin"] == binding["event_output_pin"],
            "output-metadata-binding", case_metadata["id"])
    pin = validate_pin(binding["event_output_pin"])
    require(pin["bytes"] <= limits["max_bytes"], "event-byte-limit", "before allocation")
    body = store.read(pin, retain=True)
    decoded = decode_events(body.splitlines(keepends=True), metadata["unit_ids"], clock, limits)
    require(decoded["event_count"] == metadata["event_count"], "output-event-count", case_metadata["id"])
    decoded["binding"] = {"case_metadata_digest": digest(case_metadata), "clock_digest": digest(clock),
                          "candidate_seal_digest": digest(seal), "native_receipt_pin": binding["native_receipt_pin"],
                          "event_output_pin": pin, "output_metadata_pin": binding["output_metadata_pin"]}
    return decoded
