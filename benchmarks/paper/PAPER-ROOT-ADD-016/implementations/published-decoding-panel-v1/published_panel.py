"""Import the complete public Figure 3 ECG-decoding result table.

This reads reported author scores; it neither computes ECG reconstruction scores
from time series nor accepts candidate submissions as evidence of improvement.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics

SOURCE_URL = "https://osf.io/download/fm5t8/?revision=1"
SOURCE_SHA256 = "97ce1f3546cbc7cf447cdc6efa785b87037853039d0df88bc4de62d475797368"
SOURCE_BYTES = 5222
HEADER = ["", "subject_id", "device", "condition", "r"]
DEVICES = ("eeg", "meg")
# Fixed after authenticating the original public source, not candidate-supplied.
CONDITIONS = ("ECG_components", "ECG_not_rejected", "ECG_rejected")
N_SUBJECTS = 20
SUBJECTS = frozenset(str(i) for i in range(N_SUBJECTS))


class SourceError(ValueError):
    """The complete original published panel was not recovered."""


def _require(condition, message):
    if not condition:
        raise SourceError(message)


def _parse(data: bytes) -> list[dict]:
    """Strict structural parser, also used with generated software controls."""
    try:
        text = data.decode("utf-8")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        _require(next(reader, None) == HEADER, "Unexpected source CSV header")
        records = []
        seen = set()
        for row in reader:
            _require(len(row) == len(HEADER), "Malformed CSV row")
            index, subject, device, condition, value = row
            _require(re.fullmatch(r"[0-9]+", index) is not None, "Invalid source row index")
            _require(subject and subject == subject.strip() and len(subject) <= 128,
                     "Invalid participant identifier")
            _require(device in DEVICES, "Unknown modality")
            _require(condition in CONDITIONS, "Unknown ICA condition")
            _require(value == value.strip() and value, "Invalid correlation text")
            r = float(value)
            _require(math.isfinite(r) and -1 <= r <= 1, "Pearson r must be finite in [-1, 1]")
            key = (subject, device, condition)
            _require(key not in seen, "Duplicate participant/modality/condition cell")
            seen.add(key)
            records.append({"subject_id": subject, "device": device,
                            "condition": condition, "r": r})
    except (UnicodeError, csv.Error, ValueError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError("Malformed source table") from exc
    subjects = {row["subject_id"] for row in records}
    _require(len(subjects) == N_SUBJECTS, "Expected the original 20-participant panel")
    _require(subjects == SUBJECTS, "Unexpected published participant identifiers")
    expected = {(s, d, c) for s in subjects for d in DEVICES for c in CONDITIONS}
    _require(seen == expected and len(records) == 120,
             "Every participant must have all six modality/condition cells")
    return records


def load_published(path: Path) -> list[dict]:
    # Read at most one byte beyond the authenticated source size; do not load an
    # arbitrarily large file before rejecting it.
    with path.open("rb") as stream:
        data = stream.read(SOURCE_BYTES + 1)
    _require(len(data) == SOURCE_BYTES, "Source byte count mismatch")
    _require(hashlib.sha256(data).hexdigest() == SOURCE_SHA256, "Source SHA-256 mismatch")
    return _parse(data)


def report(records: list[dict]) -> dict:
    """Descriptive arithmetic over author-reported per-participant Pearson r."""
    subjects = sorted({row["subject_id"] for row in records})
    cells = []
    for device in DEVICES:
        for condition in CONDITIONS:
            selected = sorted((r for r in records if r["device"] == device
                               and r["condition"] == condition), key=lambda r: r["subject_id"])
            values = [r["r"] for r in selected]
            cells.append({"device": device, "condition": condition, "n_participants": len(values),
                          "arithmetic_mean_r": statistics.fmean(values),
                          "sample_sd_r": statistics.stdev(values),
                          "scores": [{"subject_id": r["subject_id"], "r": r["r"]}
                                     for r in selected]})
    roster = json.dumps(subjects, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"schema": "cardiac_published_decoding_panel_v1", "task_id": "PAPER-ROOT-ADD-016",
            "source": {"version_download_url": SOURCE_URL, "version": 1, "bytes": SOURCE_BYTES,
                       "sha256": SOURCE_SHA256},
            "n_participants": len(subjects), "n_rows": len(records),
            "participant_roster_sha256": hashlib.sha256(roster).hexdigest(),
            "participant_roster_hash_encoding": "UTF-8 compact JSON of lexicographically sorted exact string IDs",
            "metric": "author-reported Pearson r", "independent_unit": "participant",
            "cells": cells,
            "qualification": "published_results_recovered_only",
            "limits": ["Reported scores are public source results, not protected time-series targets.",
                       "Means and sample SD are computed from the released scores; original figure CIs are not reconstructed.",
                       "Original recordings, exact fold boundaries and author inference are not authenticated here.",
                       "No scalar combines modalities/conditions; no candidate comparison or superiority decision is made."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="External original dec_r_ecg.csv")
    parser.add_argument("--out", required=True, type=Path, help="New external JSON report, includes full public score panel")
    args = parser.parse_args(argv)
    result = report(load_published(args.source))
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"qualification": result["qualification"],
                      "n_participants": result["n_participants"], "n_rows": result["n_rows"]}))


if __name__ == "__main__":
    main()
