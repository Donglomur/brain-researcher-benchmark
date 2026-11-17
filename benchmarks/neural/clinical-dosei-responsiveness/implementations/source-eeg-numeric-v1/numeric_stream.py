"""Pure, bounded original-CSV projection core; no paths, acquisition or dispatch.

An admitted caller must authenticate inputs, meter reads/writes across workers,
cap CPU/wall/RAM, retain partials and finalize all three streams atomically via a
last success manifest. Passing this core's generated tests is not native proof.
"""
from collections import Counter
import csv
import datetime as dt
import hashlib
import re
import struct
import zlib

from numeric_policy import parse_sample

ANNOTATIONS = ("EVENT", "MOAAS", "SOC", "Misc", "Propofol", "Midazolam", "Endoscopy")
PRIMARY = ANNOTATIONS[:4]
CHANNELS = ("Intellivue/EEG_1", "Intellivue/EEG_2")
CLOCK = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}\Z")
MAX_LINE = 65536
MAX_FIELD = 4096
MAX_MEMBER = 67108864
MAX_ROWS = 4_000_000
MAX_TOKEN_KEYS = 64
MAX_TOKEN_RAW_BYTES = 8192


class ProjectionRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ProjectionRefusal(message)


def exact_time(raw):
    require(CLOCK.fullmatch(raw), "unexpected native timestamp spelling")
    try:
        value = dt.datetime.fromisoformat(raw)
    except ValueError as error:
        raise ProjectionRefusal("impossible native timestamp") from error
    require(value.isoformat(sep=" ", timespec="milliseconds") == raw,
            "native timestamp does not round-trip exactly")
    return (value.toordinal() * 86_400_000 +
            ((value.hour * 60 + value.minute) * 60 + value.second) * 1000 +
            value.microsecond // 1000)


def project_member(stream, *, expected, annotation_rows, sinks, block_rows=65536):
    """Project every source row, preserving sparse quality and exact ledger joins.

    `stream` is bounded authenticated member bytes, `annotation_rows` an already
    authenticated private ledger iterator, and sinks are owned capped writers.
    This function must not be used as a stand-alone execution/admission gate.
    """
    require(type(block_rows) is int and 1 <= block_rows <= 65536, "buffer row ceiling")
    require(set(sinks) == {"time", "eeg", "quality"}, "three projection sinks required")
    require(type(expected["expanded_bytes"]) is int and 0 < expected["expanded_bytes"] <= MAX_MEMBER,
            "expanded member bound")
    require(type(expected["source_rows"]) is int and 0 < expected["source_rows"] <= MAX_ROWS,
            "source row bound")
    require(type(expected["annotation_rows"]) is int and 0 <= expected["annotation_rows"] <= expected["source_rows"],
            "exact annotation row count required")
    require(type(expected["clock_issue_counts"]) is dict and
            set(expected["clock_issue_counts"]) <= {"duplicate_timestamp", "backward_timestamp", "non_4ms_forward_step"} and
            all(type(count) is int and 0 < count <= expected["source_rows"]
                for count in expected["clock_issue_counts"].values()), "exact known clock issue counts required")
    for key, length in (("member_sha256", 64), ("header_sha256", 64), ("crc32", 8)):
        require(re.fullmatch(r"[0-9a-f]{" + str(length) + "}", expected[key]), "invalid source pin")
    csv.field_size_limit(MAX_FIELD)
    source_digest = hashlib.sha256()
    source_crc = source_bytes = physical_lines = row_start_bytes = 0
    eof = False

    def lines():
        nonlocal source_crc, source_bytes, physical_lines, eof
        while True:
            remaining = MAX_LINE - (source_bytes - row_start_bytes)
            require(remaining >= 0, "logical CSV row ceiling")
            raw = stream.readline(remaining + 1)
            if not raw:
                eof = True
                return
            require(len(raw) <= remaining, "physical/logical CSV row ceiling")
            source_bytes += len(raw)
            require(source_bytes <= expected["expanded_bytes"], "expanded bytes exceed source binding")
            source_digest.update(raw)
            source_crc = zlib.crc32(raw, source_crc)
            physical_lines += 1
            if physical_lines == 1:
                require(raw.endswith(b"\n") and hashlib.sha256(raw).hexdigest() == expected["header_sha256"],
                        "source header mismatch")
                yield raw.decode("utf-8-sig")
            else:
                yield raw.decode("utf-8")

    reader = csv.reader(lines(), strict=True)
    header = next(reader, None)
    require(header is not None and 1 <= len(header) <= 512 and len(header) == len(set(header)),
            "invalid source header shape")
    require(all(len(value.encode("utf-8")) <= MAX_FIELD for value in header), "UTF8 header cell ceiling")
    require({"Time", *CHANNELS, *ANNOTATIONS} <= set(header), "missing exact source columns")
    positions = {key: header.index(key) for key in ("Time", *CHANNELS, *ANNOTATIONS)}
    row_start_bytes = source_bytes
    ledger = iter(annotation_rows)
    exhausted = object()

    def advance_annotation():
        value = next(ledger, exhausted)
        if value is exhausted:
            return value
        require(type(value) is dict and set(value) == {"source_row", "source_physical_line_end", "raw_time",
                                                      "recognized_time_ms", "timestamp_issues", "original_fields"},
                "malformed saved annotation envelope")
        require(type(value["source_row"]) is int and 0 <= value["source_row"] < MAX_ROWS and
                type(value["source_physical_line_end"]) is int and
                value["source_physical_line_end"] >= value["source_row"] + 2 and
                type(value["recognized_time_ms"]) is int and type(value["raw_time"]) is str,
                "saved annotation identity/time types must be exact")
        require(type(value["timestamp_issues"]) is list and len(value["timestamp_issues"]) <= 8 and
                all(type(issue) is str and len(issue) <= 128 for issue in value["timestamp_issues"]),
                "saved annotation issue types must be exact")
        require(type(value["original_fields"]) is dict and set(value["original_fields"]) == set(ANNOTATIONS) and
                all(type(token) is str for token in value["original_fields"].values()),
                "saved annotation fields must be exact strings")
        return value

    next_annotation = advance_annotation()
    buffers = {key: bytearray() for key in sinks}
    output_bytes = Counter({key: 0 for key in sinks})
    output_hashes = {key: hashlib.sha256() for key in sinks}
    source_rows = joined = buffered_rows = 0
    previous_time = None
    clock_issues = Counter()
    quality_counts = [Counter(), Counter()]
    tokens = {}
    token_raw_bytes = untracked_token_occurrences = 0

    def flush():
        nonlocal buffered_rows
        for key in ("time", "eeg", "quality"):
            data = buffers[key]
            if data:
                written = sinks[key].write(data)
                require(type(written) is int and written == len(data),
                        "short/unknown projection write; preserve partial member")
                output_bytes[key] += written
                output_hashes[key].update(data)
                data.clear()
        buffered_rows = 0

    for index, fields in enumerate(reader):
        require(index < expected["source_rows"] and len(fields) == len(header), "source row count/shape changed")
        require(all(len(value.encode("utf-8")) <= MAX_FIELD for value in fields), "UTF8 cell ceiling")
        row_start_bytes = source_bytes
        raw_time = fields[positions["Time"]]
        timestamp = exact_time(raw_time)
        issues = []
        if previous_time is not None and timestamp - previous_time != 4:
            delta = timestamp - previous_time
            issue = "duplicate_timestamp" if delta == 0 else "backward_timestamp" if delta < 0 else "non_4ms_forward_step"
            issues.append(issue)
            clock_issues[issue] += 1
        previous_time = timestamp
        raw_annotations = {name: fields[positions[name]] for name in ANNOTATIONS}
        if any(raw_annotations[field] != "" for field in PRIMARY):
            actual_annotation = {"source_row": index, "source_physical_line_end": physical_lines,
                                 "raw_time": raw_time, "recognized_time_ms": timestamp,
                                 "timestamp_issues": issues, "original_fields": raw_annotations}
            require(next_annotation == actual_annotation, "exact original row/clock/annotation ledger join mismatch")
            joined += 1
            next_annotation = advance_annotation()
        elif next_annotation is not exhausted:
            require(type(next_annotation.get("source_row")) is int and next_annotation["source_row"] > index,
                    "missing/reordered saved annotation row")

        values = []
        statuses = []
        for channel, name in enumerate(CHANNELS):
            raw = fields[positions[name]]
            value, status = parse_sample(raw)
            require(type(status) is int and 0 <= status < 128, "unsupported quality bits")
            values.append(value)
            statuses.append(status)
            quality_counts[channel][status] += 1
            if status:
                key = (channel, status, raw)
                if key in tokens:
                    tokens[key]["occurrences"] += 1
                elif len(tokens) < MAX_TOKEN_KEYS and token_raw_bytes + len(raw.encode("utf-8")) <= MAX_TOKEN_RAW_BYTES:
                    tokens[key] = {"channel_index": channel, "quality_bits": status, "raw_token": raw,
                                   "occurrences": 1, "first_source_row": index}
                    token_raw_bytes += len(raw.encode("utf-8"))
                else:
                    untracked_token_occurrences += 1
        buffers["time"].extend(struct.pack("<q", timestamp))
        buffers["eeg"].extend(struct.pack("<dd", *values))
        buffers["quality"].extend(bytes(statuses))
        source_rows += 1
        buffered_rows += 1
        if buffered_rows == block_rows:
            flush()

    require(eof and source_bytes == expected["expanded_bytes"] and source_rows == expected["source_rows"],
            "full source EOF/size/row census mismatch")
    require(source_digest.hexdigest() == expected["member_sha256"], "complete source member SHA mismatch")
    require(f"{source_crc & 0xffffffff:08x}" == expected["crc32"], "complete source CRC mismatch")
    require(next_annotation is exhausted and joined == expected["annotation_rows"], "saved annotation ledger not exhausted")
    require(dict(clock_issues) == expected["clock_issue_counts"], "source clock issue census changed")
    flush()
    require(output_bytes == {"time": source_rows * 8, "eeg": source_rows * 16, "quality": source_rows * 2},
            "three-stream output shape mismatch")
    return {
        "schema": "dosei_private_numeric_member_projection_v1", "status": "core_completed_not_finalized",
        "source_rows": source_rows, "expanded_bytes": source_bytes, "member_sha256": source_digest.hexdigest(),
        "member_crc32": f"{source_crc & 0xffffffff:08x}", "complete_EOF": True,
        "annotation_rows_joined": joined, "clock_issue_counts": dict(clock_issues),
        "outputs": {key: {"bytes": output_bytes[key], "sha256": output_hashes[key].hexdigest()} for key in sinks},
        "quality_combination_counts_by_channel": [dict(sorted(count.items())) for count in quality_counts],
        "bounded_private_token_audit": list(tokens.values()),
        "token_audit_policy": "first 64 distinct channel/status/token keys within 8192 raw UTF8 bytes; exact later counts of tracked keys",
        "untracked_token_occurrences": untracked_token_occurrences,
        "source_rows_repaired_dropped_or_interpolated": 0,
        "canonical_scoring_admitted": False,
    }
