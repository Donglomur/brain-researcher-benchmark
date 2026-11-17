#!/usr/bin/env python3
"""Private complete-row word-start preparation; no model or native qualification.

The source's unrelated per-word features never decide target inclusion. Outputs
contain targets and must remain in operator storage, never participant packets.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys


BASE = Path(__file__).resolve().parents[1] / "initial-evaluator-v1"
PINS = {
    "evaluator.py": "366dff43d2624a1cbdf7651a7f0ef00f0dad6cae01480e75d600a7c969096f2a",
    "catalog.json": "31aab0168d2f6dcf2c230a6649320d03f53f415b726991eb8f12c02d3a800942",
}
for filename, expected in PINS.items():
    if hashlib.sha256((BASE / filename).read_bytes()).hexdigest() != expected:
        raise RuntimeError("NEURAL-015 predecessor source changed: " + filename)
_spec = importlib.util.spec_from_file_location("neural015_preparation_base", BASE / "evaluator.py")
e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e)
ContractError = e.ContractError


def extract_word_starts(payload, expected_sha256):
    """Parse every CSV data record; row identity is (exact file hash, ordinal).

    Only the source column `start` determines a word onset. `end`, text, sentence
    positions and acoustic/visual features do not filter rows. UTF-8 with an
    optional BOM is accepted; the digest covers the original bytes including BOM.
    Returned starts are sorted stably while preserving original record numbers.
    """
    e.require(type(payload) is bytes, "transcript payload must be bytes")
    e.sha(expected_sha256, "expected transcript SHA256")
    actual = hashlib.sha256(payload).hexdigest()
    e.require(actual == expected_sha256, "transcript bytes differ from frozen SHA256")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractError("transcript must be UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    rows = []
    try:
        header = next(reader, None)
        e.require(header is not None and len(header) > 0, "transcript header is missing")
        e.require(len(set(header)) == len(header), "duplicate transcript column names")
        e.require("start" in header, "source transcript must contain exact start column")
        start_column = header.index("start")
        for ordinal, row in enumerate(reader, 1):
            e.require(len(row) == len(header), "CSV record %d has wrong field count" % ordinal)
            token = row[start_column].strip()
            e.require(bool(token), "CSV record %d has missing word start" % ordinal)
            try:
                value = float(token)
            except (ValueError, OverflowError) as exc:
                raise ContractError("CSV record %d has invalid word start" % ordinal) from exc
            e.require(math.isfinite(value) and value >= 0,
                      "CSV record %d needs finite nonnegative seconds" % ordinal)
            rows.append({"source_record_number": ordinal, "movie_time_seconds": value})
    except csv.Error as exc:
        raise ContractError("malformed transcript CSV") from exc
    e.require(rows, "transcript has no word records")
    rows.sort(key=lambda row: row["movie_time_seconds"])
    return {
        "task_id": e.TASK,
        "format": "private-complete-word-starts/v1",
        "transcript_sha256": actual,
        "transcript_bytes": len(payload),
        "source_record_count": len(rows),
        "word_count": len(rows),
        "word_starts": rows,
    }


def prepare_unpaused_recording(payload, spec):
    """Map every word to an operator-declared, unpaused recording, or reject.

    No clipping, transcript subset, pause inference, replay selection, missing
    onset imputation or fallback to sentence onsets is performed. Source IDs and
    hashes check declared joins; authentic correspondence remains unverified.
    """
    e.exact(spec, ["recording_id", "movie_id", "sample_count", "transcript_sha256",
                   "triggers", "max_clock_residual_samples"], "alignment specification")
    rid = spec["recording_id"]
    e.require(isinstance(rid, str) and rid in e.IDENTITIES, "unknown recording ID")
    e.require(spec["movie_id"] == e.IDENTITIES[rid]["movie_id"], "recording/movie identity mismatch")
    n = e.integer(spec["sample_count"], "sample_count", 1)
    extracted = extract_word_starts(payload, spec["transcript_sha256"])
    triggers = spec["triggers"]
    aligned = e.align_onsets([row["movie_time_seconds"] for row in extracted["word_starts"]],
                             triggers, spec["max_clock_residual_samples"])
    e.require(all(t["neural_sample_index"] < n for t in triggers), "trigger outside recording")
    samples = aligned["word_onset_samples"]
    e.require(all(0 <= sample < n for sample in samples), "aligned word start outside recording")
    return {
        "task_id": e.TASK,
        "format": "private-unpaused-word-onsets/v1",
        "recording_id": rid,
        "sample_count": n,
        "sample_rate_hz": 2048,
        "transcript_sha256": extracted["transcript_sha256"],
        "alignment_spec_sha256": e.digest(spec),
        "source_record_count": extracted["source_record_count"],
        "word_count": extracted["word_count"],
        "word_onset_samples": samples,
        "source_record_numbers_in_sample_order": [row["source_record_number"] for row in extracted["word_starts"]],
        "adjacent_clock_residual_samples": aligned["adjacent_clock_residual_samples"],
        "native_alignment_validated": False,
        "alignment_scope": "all transcript rows within one operator-declared unpaused clock span",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="extract every private word start in seconds")
    extract.add_argument("transcript")
    extract.add_argument("--expected-sha256", required=True)
    extract.add_argument("--output", required=True, help="new private operator JSON; never a participant path")
    align = sub.add_parser("align", help="prepare every word for an explicitly unpaused recording")
    align.add_argument("transcript")
    align.add_argument("--spec", required=True)
    align.add_argument("--output", required=True, help="new private operator JSON; never a participant path")
    args = parser.parse_args(argv)
    try:
        payload = Path(args.transcript).read_bytes()
        if args.command == "extract":
            result = extract_word_starts(payload, args.expected_sha256)
        else:
            result = prepare_unpaused_recording(payload, e.load_json(args.spec))
        encoded = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
        # Refuse overwrite and create target-bearing output with owner-only mode.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print("NEURAL-015 preparation rejected: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
