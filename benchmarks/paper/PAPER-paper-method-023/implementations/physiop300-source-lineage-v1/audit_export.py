"""Operator-only metadata audit of the pinned PhysioP300 converter's export keys.

No signal read, MNE execution, label inference beyond the pinned string rule,
converter repair, historical file recovery, or scientific qualification occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

PROBE_SUBJECTS = ("1", "2", "3", "4", "5", "6", "7", "9", "11")
CONVERTER_SUBJECTS = ("2", "3", "4", "5", "6", "7", "9", "11")
CONVERTER_SHA256 = "ac09445f2bd5cfb5605de8a86b0976be7ef12b34f3eef0d48959147c2cfa6fa8"
MAX_JSON_BYTES = 16 * 1024 * 1024


class Refusal(ValueError):
    """Input metadata cannot support the requested conditional audit."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def fields(value, names, context):
    require(type(value) is dict and set(value) == set(names), context)


def text(value, context):
    require(type(value) is str and 0 < len(value) <= 256
            and all(32 <= ord(c) < 127 for c in value), context)


def digest(value, context):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), context)


def integer(value, context):
    require(type(value) is int and 0 <= value < 2**63, context)


def commitment(document):
    """Commit canonical JSON metadata, not the underlying source or its truth."""
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def decode(data):
    require(type(data) is bytes and len(data) <= MAX_JSON_BYTES, "bounded JSON bytes")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise Refusal("nonfinite JSON value")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=nonfinite)


def audit_export(inventory, captures):
    """Audit normalized operator metadata; caller assertions are not attestation.

    Inventory spans all nine nominal probe tokens. Captures span exactly the
    eight tokens visited by the released converter. Each capture retains the
    full events array passed to Epochs, event_id, selection, and drop_log.
    No epochs selection/reset/reindex operation may precede capture.
    """
    fields(inventory, ("schema", "recordings"), "inventory fields")
    require(inventory["schema"] == "physiop300_recording_inventory_v1", "inventory schema")
    rows = inventory["recordings"]
    require(type(rows) is list and 0 < len(rows) <= 512, "bounded nonempty recording inventory")
    by_id, members, subjects = {}, set(), set()
    for row in rows:
        fields(row, ("recording_id", "subject_id", "source_member", "source_bytes", "source_sha256"),
               "recording descriptor fields")
        rid, sub = row["recording_id"], row["subject_id"]
        text(rid, "recording identity")
        text(sub, "nominal subject token")
        text(row["source_member"], "source member identity")
        integer(row["source_bytes"], "source extent")
        require(row["source_bytes"] > 0, "nonempty source extent")
        digest(row["source_sha256"], "source SHA256 descriptor")
        require(rid not in by_id and row["source_member"] not in members,
                "duplicate recording or source member")
        require(sub in PROBE_SUBJECTS, "outside selected nine nominal source tokens")
        by_id[rid] = row
        members.add(row["source_member"])
        subjects.add(sub)
    require(subjects == set(PROBE_SUBJECTS), "inventory must retain all nine nominal probe tokens")

    fields(captures, ("schema", "inventory_commitment", "converter_source_sha256", "recordings"),
           "capture document fields")
    require(captures["schema"] == "physiop300_converter_epoch_metadata_v1", "capture schema")
    require(captures["inventory_commitment"] == commitment(inventory), "inventory commitment mismatch")
    require(captures["converter_source_sha256"] == CONVERTER_SHA256, "different converter source")
    records = captures["recordings"]
    require(type(records) is list, "capture recording list")
    expected = {rid for rid, row in by_id.items() if row["subject_id"] in CONVERTER_SUBJECTS}
    seen, outputs, dropped, skipped = set(), [], [], []
    record_summaries = []
    for record in records:
        fields(record, ("recording_id", "source_sha256", "event_id", "events", "selection", "drop_log"),
               "full unreset Epochs metadata fields")
        rid = record["recording_id"]
        text(rid, "captured recording identity")
        require(rid in expected and rid not in seen, "unexpected or repeated converter recording")
        seen.add(rid)
        row = by_id[rid]
        require(record["source_sha256"] == row["source_sha256"], "recording source mismatch")
        event_id, events = record["event_id"], record["events"]
        require(type(event_id) is dict and event_id, "complete event_id mapping")
        reverse = {}
        targets = []
        for description, code in event_id.items():
            text(description, "annotation description")
            integer(code, "MNE event code")
            require(code > 0 and code not in reverse, "unique positive MNE event codes")
            reverse[code] = description
            if description.startswith("#Tgt"):
                require(len(description) > 4, "target annotation lacks character")
                targets.append(description[4])
        require(len(targets) == 1, "exactly one target description required; no order-based target choice")
        target = targets[0]
        require(type(events) is list and 0 < len(events) <= 10000, "bounded original events")
        sample_previous, observed_codes, first_at_sample = -1, set(), {}
        for original_index, event in enumerate(events):
            require(type(event) is list and len(event) == 3, "MNE event row [sample, previous, code]")
            for value in event:
                integer(value, "integer MNE event element")
            require(event[0] >= sample_previous and event[2] in reverse, "ordered mapped original event")
            sample_previous = event[0]
            observed_codes.add(event[2])
            first_at_sample.setdefault(event[0], original_index)
        require(observed_codes == set(reverse), "event_id must describe the complete captured events")
        selection, log = record["selection"], record["drop_log"]
        require(type(selection) is list and type(log) is list and len(log) == len(events),
                "selection and full original-event drop log")
        for index in selection:
            integer(index, "selected original-event index")
            require(index < len(events), "selected index outside original events")
        require(selection == sorted(set(selection)), "selection must preserve unique original order")
        selected = set(selection)
        for index, reasons in enumerate(log):
            require(type(reasons) is list, "drop reasons list")
            for reason in reasons:
                text(reason, "drop reason")
            require((not reasons) == (index in selected), "drop_log/selection contradiction")
            if reasons:
                dropped.append({"recording_id": rid, "original_event_index": index,
                                "sample": events[index][0], "description": reverse[events[index][2]],
                                "reasons": list(reasons)})
        retained_samples = [events[i][0] for i in selection]
        require(retained_samples == sorted(set(retained_samples)),
                "event_repeated=drop cannot retain duplicate sample rows")
        require(all(first_at_sample[events[i][0]] == i for i in selection),
                "event_repeated=drop retains only the first row at each sample")
        n_output = 0
        for ordinal, index in enumerate(selection):
            event = events[index]
            description = reverse[event[2]]
            lineage = {"recording_id": rid, "subject_id": row["subject_id"],
                       "original_event_index": index, "retained_epoch_ordinal": ordinal,
                       "sample": event[0]}
            if description.startswith("#"):
                skipped.append({**lineage, "description": description})
                continue
            label = int(target in description)
            outputs.append({**lineage, "target": label,
                            "legacy_output_key": f"{label}/{ordinal}.sub{row['subject_id']}"})
            n_output += 1
        record_summaries.append({"recording_id": rid, "original_events": len(events),
                                 "retained_epochs": len(selection), "intended_writes": n_output})
    require(seen == expected, "complete eight-token converter recording coverage required")
    by_key = {}
    for output in outputs:
        by_key.setdefault(output["legacy_output_key"], []).append(output)
    collisions = [{"legacy_output_key": key, "events": by_key[key]}
                  for key in sorted(by_key) if len(by_key[key]) > 1]
    return {
        "schema": "physiop300_converter_lineage_audit_v1",
        "inventory_commitment": commitment(inventory),
        "capture_commitment": commitment(captures),
        "probe_nominal_subjects": list(PROBE_SUBJECTS),
        "converter_nominal_subjects": list(CONVERTER_SUBJECTS),
        "unvisited_probe_recordings": sorted(rid for rid in by_id if rid not in expected),
        "recordings": sorted(record_summaries, key=lambda x: x["recording_id"]),
        "intended_writes": outputs,
        "metadata_epochs_skipped": skipped,
        "dropped_original_events": dropped,
        "colliding_output_keys": collisions,
        "unique_legacy_output_keys": len(by_key),
        "displaced_writes_if_all_writes_completed": len(outputs) - len(by_key),
        "historical_surviving_events": None,
        "historical_converter_execution_verified": False,
        "source_metadata_authenticated_by_this_audit": False,
        "source_selection_complete_by_this_audit": False,
        "scientific_readiness": False,
        "interpretation": "Conditional metadata arithmetic only. No os.listdir order, actual writes, "
                          "MNE version/preprocessing parity, event completeness or biological identities "
                          "are recovered. Operator-only output contains protected target labels.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--epoch-metadata", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        docs = []
        for path in (args.inventory, args.epoch_metadata):
            with path.open("rb") as stream:
                docs.append(decode(stream.read(MAX_JSON_BYTES + 1)))
        result = audit_export(*docs)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"source-lineage audit refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
