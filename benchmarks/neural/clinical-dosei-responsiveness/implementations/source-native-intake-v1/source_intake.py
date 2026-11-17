#!/usr/bin/env python3
"""Bounded DOSE-I source inspection, sparse native windows, and admission gates.

This is not a clinical model or a new benchmark definition. Original EVENT
grammar, biological-person identity, and assessment onset are not established.
Every output identifies that limitation; no admitted scorer policy is emitted.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import zipfile

SCHEMA = "dosei_source_native_intake_v1"
OLD_COUNTS = {"recordings": 171, "assessments": 7328, "transitions": 1129}
PINNED = {
    "metadata.zip": "a2e90c906969364e9def40a83b46843fcf7809324ac893a3d428a481481b2798",
    "static.zip": "1f4f2d114a58e7450a6e800ed8c545b2b5658b87abe647a7268a4cf4a1f61f3b",
    "artifacts.zip": "bb8d3f3b108529b20b192c889cbf22851080e1be3b8fa2315f599ec713ec103f",
}
METADATA_MEMBER = "metadata/DOSE-I_metadata.csv"
STATIC_MEMBER = "static/DOSE-I_static_data.csv"
STEP_MS = 4
WINDOW_MS = 30000
WINDOW_ROWS = WINDOW_MS // STEP_MS
MAX_SOURCE_BYTES = 1 << 30
MAX_ROWS = 4_000_000
MAX_ANNOTATIONS = 50_000
MAX_LINE_BYTES = 64 * 1024
MAX_JSON_BYTES = 16 << 20
MAX_ZIP_BYTES = 16 << 20
MAX_MEMBER_BYTES = 2 << 20
CHANNELS = ("Intellivue/EEG_1", "Intellivue/EEG_2")
CLINICAL = ("EVENT", "MOAAS", "SOC")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
CLOCK = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\Z")
ARTIFACT_CLOCK = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\Z")


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def sha256_file(path, expected, cap=MAX_SOURCE_BYTES):
    """Bind a regular, non-symlink input; a hash binds bytes, not authority."""
    require(isinstance(expected, str) and HEX.fullmatch(expected), "invalid expected SHA256")
    path = Path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "input must be a regular non-symlink file")
    require(info.st_size <= cap, "input exceeds whole-file byte ceiling")
    digest = hashlib.sha256()
    read = 0
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino) == (info.st_dev, info.st_ino), "input changed while opening")
        for block in iter(lambda: handle.read(1 << 20), b""):
            read += len(block)
            require(read <= cap, "input grew beyond ceiling")
            digest.update(block)
        after = os.fstat(handle.fileno())
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "input changed while hashing")
    require(read == info.st_size and digest.hexdigest() == expected, "input SHA256 mismatch")
    return expected


def archive_member(path, expected, member):
    sha256_file(path, expected, MAX_ZIP_BYTES)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) <= 512, "archive member ceiling")
        names = set()
        expanded = 0
        for info in entries:
            name = info.filename
            require(name not in names, "duplicate ZIP member")
            names.add(name)
            require(not name.startswith(("/", "\\")) and "\\" not in name and ".." not in name.split("/"), "unsafe ZIP member name")
            require(not stat.S_ISLNK(info.external_attr >> 16), "ZIP symlink refused")
            require(not info.flag_bits & 1, "encrypted ZIP refused")
            require(info.file_size <= MAX_MEMBER_BYTES, "ZIP member exceeds ceiling")
            expanded += info.file_size
        require(expanded <= MAX_ZIP_BYTES, "ZIP expanded-size ceiling")
        require(member in names, "required ZIP member absent")
        with archive.open(member) as handle:
            raw = handle.read(MAX_MEMBER_BYTES + 1)
        require(len(raw) <= MAX_MEMBER_BYTES, "expanded member exceeds ceiling")
    return raw


def csv_rows(raw):
    require(len(raw) <= MAX_MEMBER_BYTES, "small CSV exceeds ceiling")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        require(reader.fieldnames is not None, "missing CSV header")
        require(len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate CSV columns")
        rows = []
        for row in reader:
            require(None not in row and None not in row.values(), "ragged CSV row")
            rows.append(row)
            require(len(rows) <= MAX_ANNOTATIONS, "small CSV row ceiling")
    except (UnicodeError, csv.Error) as error:
        raise Refusal("invalid CSV encoding or syntax") from error
    return reader.fieldnames, rows


def integer(raw, *, nullable=False):
    if nullable and raw == "":
        return None
    require(isinstance(raw, str) and re.fullmatch(r"0|[1-9]\d*", raw), "invalid nonnegative integer")
    return int(raw)


def reconcile_metadata(metadata_zip, static_zip, metadata_sha=PINNED["metadata.zip"], static_sha=PINNED["static.zip"]):
    metadata_raw = archive_member(metadata_zip, metadata_sha, METADATA_MEMBER)
    static_raw = archive_member(static_zip, static_sha, STATIC_MEMBER)
    metadata_headers, metadata = csv_rows(metadata_raw)
    static_headers, static = csv_rows(static_raw)
    needed = {"", "MOAAS_sum", "SOC_trans", *(f"MOAAS{i}" for i in range(1, 6))}
    require(needed <= set(metadata_headers), "metadata schema mismatch")
    require("ID" in static_headers, "static ID column absent")
    records = {}
    for row in metadata:
        rid = str(integer(row[""]))
        require(rid not in records, "duplicate metadata recording ID")
        counts = {str(i): integer(row[f"MOAAS{i}"], nullable=True) for i in range(1, 6)}
        total = integer(row["MOAAS_sum"])
        known = sum(value for value in counts.values() if value is not None)
        require(known <= total, "category counts exceed metadata total")
        require(any(value is None for value in counts.values()) or known == total, "category count disagreement")
        records[rid] = {"recording_id": rid, "metadata_assessments": total,
                        "metadata_transitions": integer(row["SOC_trans"]),
                        "category_counts": counts,
                        "category_count_blanks_preserved": [key for key, value in counts.items() if value is None]}
    static_ids = [str(integer(row["ID"])) for row in static]
    require(len(static_ids) == len(set(static_ids)), "duplicate static recording ID")
    require(set(records) == set(static_ids), "metadata/static recording identity mismatch")
    require(len(records) == 171, "source release requires all 171 recording IDs")
    totals = {"recordings": len(records),
              "assessments": sum(row["metadata_assessments"] for row in records.values()),
              "transitions": sum(row["metadata_transitions"] for row in records.values())}
    pinned_release = metadata_sha == PINNED["metadata.zip"] and static_sha == PINNED["static.zip"]
    return {"schema": SCHEMA, "source_release": "zenodo:22145442/v2" if pinned_release else "unverified_fixture_or_operator_bytes",
            "source_release_authenticated": pinned_release,
            "metadata_sha256": metadata_sha, "static_sha256": static_sha,
            "metadata_member_sha256": hashlib.sha256(metadata_raw).hexdigest(),
            "static_member_sha256": hashlib.sha256(static_raw).hexdigest(),
            "recording_join": "exact_171_ID_set", "biological_person_join_verified": False,
            "metadata_aggregate_counts": totals, "original_EVENT_census_complete": False,
            "existing_scorer_declared_counts": OLD_COUNTS,
            "count_discrepancies": {key: {"metadata": totals[key], "scorer": value, "difference": totals[key] - value}
                                    for key, value in OLD_COUNTS.items() if totals[key] != value},
            "canonical_admission": "held",
            "recordings": [records[key] for key in sorted(records, key=int)]}


def timestamp_ms(raw, *, artifact=False):
    if artifact:
        require(isinstance(raw, str) and ARTIFACT_CLOCK.fullmatch(raw), "invalid artifact timestamp")
        raw += ".000"
    require(isinstance(raw, str) and CLOCK.fullmatch(raw), "invalid native millisecond timestamp")
    try:
        value = dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError as error:
        raise Refusal("impossible native timestamp") from error
    return value.toordinal() * 86_400_000 + ((value.hour * 60 + value.minute) * 60 + value.second) * 1000 + value.microsecond // 1000


def sample(raw):
    if raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise Refusal("invalid EEG value") from error
    require(math.isfinite(value), "non-finite EEG value")
    require(abs(value) <= 187.5, "EEG value outside documented hardware range; no sentinel conversion")
    return value


def native_rows(path, *, stop_before=None, stop_at_row=None):
    """Original CSV only. Caller authenticates bytes. No pEEG or resampling."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        def bounded_lines():
            while True:
                line = handle.readline(MAX_LINE_BYTES + 1)
                if not line:
                    return
                require(len(line.encode("utf-8")) <= MAX_LINE_BYTES, "native CSV physical line ceiling")
                yield line
        reader = csv.DictReader(bounded_lines(), strict=True)
        headers = reader.fieldnames
        require(headers is not None and len(headers) <= 512, "invalid native header")
        require(len(headers) == len(set(headers)), "duplicate native columns")
        require({"Time", *CLINICAL} <= set(headers), "original Time/EVENT/MOAAS/SOC columns required")
        eeg_headers = []
        for base in CHANNELS:
            matches = [name for name in headers if name.split("-", 1)[0] == base]
            require(len(matches) == 1, "missing or ambiguous native EEG channel")
            require(matches[0] in {base, base + "-uV", base + "-µV", base + "-μV"}, "unverified EEG unit suffix; no implicit rescaling")
            eeg_headers.append(matches[0])
        previous = None
        for index, row in enumerate(reader):
            require(index < MAX_ROWS, "native row ceiling; entire recording refused")
            require(None not in row and None not in row.values(), "ragged native row")
            clock = timestamp_ms(row["Time"])
            require(previous is None or clock - previous == STEP_MS, "native clock must be contiguous 4ms, with no duplicate or missing grid rows")
            previous = clock
            if stop_before is not None and clock >= stop_before:
                # Authenticate the marker's grid position, but do not even
                # parse its waveform/clinical payload or any future row.
                yield index, clock, (None, None), {name: "" for name in CLINICAL}
                return
            if stop_at_row is not None and index == stop_at_row:
                yield index, clock, (None, None), {name: row[name] for name in CLINICAL}
                return
            yield index, clock, tuple(sample(row[name]) for name in eeg_headers), {name: row[name] for name in CLINICAL}


def label_disposition(raw):
    """No imputation, recoding, or inference from EVENT/SOC/adjacent rows."""
    if raw == "":
        return {"label_status": "missing", "category": None}
    if raw in {"1", "2", "3", "4", "5"}:
        return {"label_status": "valid", "category": int(raw)}
    return {"label_status": "ambiguous", "category": None}


def scan_recording(path, expected_sha, recording_id):
    require(isinstance(recording_id, str) and re.fullmatch(r"[1-9]\d*", recording_id), "invalid recording ID")
    sha256_file(path, expected_sha)
    annotations = []
    counters = {"rows": 0, "nonempty_EVENT_rows": 0, "nonempty_MOAAS_rows": 0, "nonempty_SOC_rows": 0}
    observed = [0, 0]
    first = last = None
    for index, clock, eeg, clinical in native_rows(path):
        first = clock if first is None else first
        last = clock
        counters["rows"] += 1
        observed = [count + int(value is not None) for count, value in zip(observed, eeg)]
        for name, raw in clinical.items():
            counters[f"nonempty_{name}_rows"] += int(raw != "")
        if any(clinical.values()):
            require(len(annotations) < MAX_ANNOTATIONS, "annotation ceiling; recording refused")
            annotations.append({"source_row": index, "marker_time_ms": clock,
                                "original_fields": clinical,
                                "MOAAS_candidate": clinical["MOAAS"] != "",
                                **label_disposition(clinical["MOAAS"]),
                                "prior_native_grid_rows": min(index, WINDOW_ROWS),
                                "window_status": "complete" if index >= WINDOW_ROWS else "incomplete",
                                "timing_status": "unresolved", "artifact_status": "unresolved"})
    require(first is not None, "empty native recording")
    # Detect in-place edits between admission and processing; this is not a
    # sandbox against an adversary changing and restoring an input concurrently.
    sha256_file(path, expected_sha)
    return {"schema": SCHEMA, "recording_id": recording_id, "source_sha256": expected_sha,
            "source_release_authenticated": False,
            "first_time_ms": first, "last_time_ms": last, "observed_EEG_values": observed,
            "source_row_counts": counters, "protected_annotation_ledger": annotations,
            "original_EVENT_census_complete": False,
            "assessment_onset_verified": False, "biological_person_join_verified": False,
            "canonical_admission": "held",
            "holds": ["EVENT_grammar_not_authenticated", "nonempty_MOAAS_rows_are_candidates_not_complete_assessment_census",
                      "marker_time_is_not_verified_assessment_onset", "person_crosswalk_not_authenticated",
                      "native_sparse250Hz_grid_is_not_the_declared_dense125Hz_packet"]}


def marker_window(path, expected_sha, cutoff, case_id):
    """Return all native grid values in [marker-30s, marker), future excluded.

    The source marker is not established assessment onset. Source SHA belongs
    only in a private provenance sidecar, never in this participant projection.
    """
    require(isinstance(case_id, str) and IDENTIFIER.fullmatch(case_id), "invalid opaque case ID")
    sha256_file(path, expected_sha)
    cutoff_ms = timestamp_ms(cutoff)
    buffer = collections.deque(maxlen=WINDOW_ROWS)
    marker_seen = False
    for index, clock, eeg, clinical in native_rows(path, stop_before=cutoff_ms):
        if clock >= cutoff_ms:
            require(clock == cutoff_ms, "cutoff must be an original grid timestamp")
            marker_seen = True
            break
        if clock >= cutoff_ms - WINDOW_MS:
            buffer.append((clock, eeg))
    require(marker_seen, "cutoff absent from native source grid")
    require(len(buffer) == WINDOW_ROWS and buffer[0][0] == cutoff_ms - WINDOW_MS and buffer[-1][0] == cutoff_ms - STEP_MS,
            "incomplete prior 30-second native grid")
    sha256_file(path, expected_sha)
    return {"schema": "dosei_native_marker_window_v1", "case_id": case_id,
            "representation": "native_sparse_250Hz_grid_two_EEG_channels_no_resampling",
            "cutoff_role": "caller_supplied_native_grid_cutoff", "source_event_marker_verified": False,
            "assessment_onset_verified": False,
            "canonical_admission": "held", "source_release_authenticated": False,
            "channels": ["EEG_1", "EEG_2"], "units": "microvolt",
            "relative_time_ms": [clock - cutoff_ms for clock, _ in buffer],
            "values": [list(values) for _, values in buffer],
            "observed": [[value is not None for value in values] for _, values in buffer]}


def candidate_window(path, expected_sha, source_row, case_id):
    """Bind the adopted retrospective window to an original coded candidate.

    Nonempty EVENT plus MOAAS proves candidate-row presence, not the unverified
    original EVENT grammar, unique-assessment identity or clinical onset.
    """
    require(type(source_row) is int and 0 <= source_row < MAX_ROWS, "invalid candidate source row")
    sha256_file(path, expected_sha)
    selected = None
    for index, clock, eeg, clinical in native_rows(path, stop_at_row=source_row):
        if index == source_row:
            require(clinical["EVENT"] != "" and clinical["MOAAS"] != "", "candidate row requires original EVENT and MOAAS cells")
            selected = clock
    require(selected is not None, "candidate source row absent")
    days, remainder = divmod(selected, 86_400_000)
    value = dt.datetime.combine(dt.date.fromordinal(days), dt.time()) + dt.timedelta(milliseconds=remainder)
    cutoff = value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    packet = marker_window(path, expected_sha, cutoff, case_id)
    packet.update({"source_condition": "native_marker_relative_30s_v1",
                   "cutoff_role": "original_coded_MOAAS_candidate_marker",
                   "source_event_marker_verified": True,
                   "original_EVENT_assessment_identity_verified": False,
                   "estimand": "retrospective_marker_associated_responsiveness",
                   "assessment_challenge_activity_may_be_present": True})
    return packet


def artifact_intervals(artifacts_zip, recording_id, expected_sha=PINNED["artifacts.zip"]):
    require(isinstance(recording_id, str) and re.fullmatch(r"[1-9]\d*", recording_id), "invalid recording ID")
    member = f"artifacts/artifacts/10-{int(recording_id):03d}_artifacts.csv"
    raw = archive_member(artifacts_zip, expected_sha, member)
    headers, rows = csv_rows(raw)
    require(headers == ["begin_idx", "end_idx", "is_artifact", "reason"], "artifact schema mismatch")
    result = []
    previous_end = None
    for row in rows:
        start = timestamp_ms(row["begin_idx"], artifact=True)
        end = timestamp_ms(row["end_idx"], artifact=True)
        require(end - start == 2000 and (previous_end is None or start == previous_end), "artifact intervals not contiguous 2-second epochs")
        require(row["is_artifact"] in {"True", "False"}, "artifact boolean syntax")
        reason = integer(row["reason"])
        flag = row["is_artifact"] == "True"
        require((flag and reason in range(1, 6)) or (not flag and reason == 0), "artifact reason mismatch")
        result.append({"start_ms": start, "end_ms": end, "is_artifact": flag, "reason": reason})
        previous_end = end
    return result


def artifact_window_audit(intervals, cutoff):
    """Private audit only. End-point-inclusive overlap is conservative, not QC."""
    end = timestamp_ms(cutoff)
    start = end - WINDOW_MS
    overlaps = [row for row in intervals if row["start_ms"] <= end and row["end_ms"] >= start]
    return {"schema": "dosei_private_artifact_overlap_v1", "window_start_ms": start, "window_end_ms": end,
            "endpoint_convention_verified": False, "causal_availability_verified": False,
            "participant_input_allowed": False, "artifact_status": "unresolved",
            "conservative_closed_interval_overlaps": overlaps}


def validate_person_join(join, recording_ids):
    """Logical completeness only. A caller-provided hash is not person proof."""
    require(type(join) is dict and set(join) == {"schema", "source_sha256", "rows"}, "person join fields")
    require(join["schema"] == "dosei_recording_person_crosswalk_v1", "person join schema")
    require(isinstance(join["source_sha256"], str) and HEX.fullmatch(join["source_sha256"]), "person join source hash")
    require(type(join["rows"]) is list and len(join["rows"]) == len(recording_ids), "person join completeness")
    seen = set()
    people = collections.defaultdict(list)
    for row in join["rows"]:
        require(type(row) is dict and set(row) == {"recording_id", "person_id"}, "person join row fields")
        rid, pid = row["recording_id"], row["person_id"]
        require(rid in recording_ids and rid not in seen, "unknown or duplicate person-join recording")
        require(isinstance(pid, str) and IDENTIFIER.fullmatch(pid), "invalid opaque person ID")
        seen.add(rid)
        people[pid].append(rid)
    require(seen == set(recording_ids), "incomplete person crosswalk")
    return {"logical_join_complete": True, "biological_person_join_verified": False,
            "source_sha256": join["source_sha256"],
            "person_groups": {key: sorted(value, key=int) for key, value in sorted(people.items())}}


def cohort_report(metadata, recording_reports):
    expected = {row["recording_id"]: row for row in metadata["recordings"]}
    actual = {}
    for report in recording_reports:
        rid = report["recording_id"]
        require(rid in expected and rid not in actual, "unknown or duplicate cohort recording")
        actual[rid] = report
    require(set(actual) == set(expected), "all source recording reports required; no cohort truncation")
    checks = []
    for rid in sorted(expected, key=int):
        source = actual[rid]["source_row_counts"]
        checks.append({"recording_id": rid,
                       "nonempty_MOAAS_rows": source["nonempty_MOAAS_rows"],
                       "metadata_assessments": expected[rid]["metadata_assessments"],
                       "nonempty_SOC_rows": source["nonempty_SOC_rows"],
                       "metadata_transitions": expected[rid]["metadata_transitions"],
                       "equal_counts_do_not_prove_complete_EVENT_census": True})
    return {"schema": "dosei_source_cohort_reconciliation_v1", "recordings": checks,
            "metadata_aggregate_counts": metadata["metadata_aggregate_counts"],
            "observed_nonempty_coded_rows": {"MOAAS": sum(row["nonempty_MOAAS_rows"] for row in checks),
                                            "SOC": sum(row["nonempty_SOC_rows"] for row in checks)},
            "existing_scorer_discrepancies": metadata["count_discrepancies"],
            "original_EVENT_census_complete": False, "canonical_admission": "held"}


def project_existing_scorer(*args, **kwargs):
    """Intentionally cannot turn source candidates into an admitted policy."""
    raise Refusal("legacy canonical projection held: inherited counts, original EVENT census, biological-person crosswalk, pre-onset timing and dense representation do not admit this retrospective source condition; successor population/scorer not delivered; no targets or policy emitted")


def write_fresh_json(path, value):
    raw = (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(len(raw) <= MAX_JSON_BYTES, "output exceeds ceiling; no partial scientific report")
    # Data/provenance reports are evaluator-private. Parent directory protection
    # remains the operator's responsibility; no world-readable files are made.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser("metadata", help="reconcile authenticated complete v2 metadata/static IDs")
    meta.add_argument("--metadata-zip", required=True)
    meta.add_argument("--static-zip", required=True)
    meta.add_argument("--output", required=True)
    for name in ("scan", "packet", "candidate-packet"):
        item = sub.add_parser(name)
        item.add_argument("--csv", required=True)
        item.add_argument("--source-sha256", required=True)
        item.add_argument("--output", required=True)
        if name == "scan":
            item.add_argument("--recording-id", required=True)
        else:
            item.add_argument("--case-id", required=True)
            if name == "packet":
                item.add_argument("--cutoff", required=True)
            else:
                item.add_argument("--source-row", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        require(not Path(args.output).exists() and not Path(args.output).is_symlink(), "fresh output path required")
        if args.command == "metadata":
            result = reconcile_metadata(args.metadata_zip, args.static_zip)
        elif args.command == "scan":
            result = scan_recording(args.csv, args.source_sha256, args.recording_id)
        elif args.command == "packet":
            result = marker_window(args.csv, args.source_sha256, args.cutoff, args.case_id)
        else:
            result = candidate_window(args.csv, args.source_sha256, args.source_row, args.case_id)
        write_fresh_json(args.output, result)
    except (Refusal, OSError, csv.Error, UnicodeError, zipfile.BadZipFile) as error:
        parser.exit(2, f"REFUSED: {error}\n")


if __name__ == "__main__":
    main()
