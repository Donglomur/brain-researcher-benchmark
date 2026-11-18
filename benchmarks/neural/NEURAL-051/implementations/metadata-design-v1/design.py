"""Operator-only THINGS metadata preparation; never opens neural/image values."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "retrieval-scorer-v1" / "legacy" / "public"
FIELDS = ("trial_type", "session", "run", "subject_id", "trial_id", "stimulus", "concept")
INTEGER_FIELDS = ("session", "run", "subject_id", "trial_id")
SOURCE_LIMIT = 500_000  # Original builder's per-person metadata byte limit.


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


protocol = _module("neural051_metadata_protocol", LEGACY / "protocol.py")
file_io = _module("neural051_metadata_io", LEGACY / "io_utils.py")


def _pins(pins):
    if not isinstance(pins, dict) or set(pins) != set(protocol.SUBJECTS):
        raise ValueError("exact three-person source pins required")
    if any(not isinstance(v, str) or len(v) != 64 or
           any(c not in "0123456789abcdef" for c in v) for v in pins.values()):
        raise ValueError("source pins must be SHA256 hex")


def parse_metadata(raw):
    """Preserve source trial IDs, rejecting lossy CSV parsing and type coercion."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= SOURCE_LIMIT:
        raise ValueError("bounded metadata bytes required")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError("exact unique metadata column names required")
    rows = []
    for record in reader:
        if set(record) != set(FIELDS) or any(v is None for v in record.values()):
            raise ValueError("exact metadata row width required")
        for field in INTEGER_FIELDS:
            value = record[field]
            if not value or not value.isascii() or not value.isdecimal():
                raise ValueError("unsigned decimal source index required")
            record[field] = int(value)
        rows.append(record)
        if len(rows) > 9840:
            raise ValueError("source trial count exceeds frozen support")
    return rows


def _validate_rows(rows_by_person):
    if not isinstance(rows_by_person, dict) or set(rows_by_person) != set(protocol.SUBJECTS):
        raise ValueError("exact three-person metadata required")
    for person, rows in rows_by_person.items():
        if not isinstance(rows, list) or len(rows) != 9840:
            raise ValueError("complete 9840 source rows per person required")
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(FIELDS):
                raise ValueError("exact source fields required")
            if any(type(row[k]) is not int for k in INTEGER_FIELDS):
                raise ValueError("integer source indices required, not bool or floats")
            if any(not isinstance(row[k], str) or not row[k] for k in ("trial_type", "stimulus", "concept")):
                raise ValueError("nonempty source text fields required")
            if any(c in row["stimulus"] for c in ("/", "\\", "\x00", "\n", "\r")):
                raise ValueError("source stimulus must be one ordinary filename")


def build_rows(rows_by_person, seed, source_pins):
    """Trusted in-memory builder; pins are declarations until capture verifies them."""
    _pins(source_pins)
    if (not isinstance(seed, str) or not 32 <= len(seed.encode("utf-8")) <= 4096
            or any(ord(c) < 32 or ord(c) == 127 for c in seed)):
        raise ValueError("private operator seed requires 32..4096 bytes without controls")
    _validate_rows(rows_by_person)
    # Exact preserved source split: globally remove query and validation images.
    splits, candidates, concepts = protocol.split(rows_by_person, strict=True)
    candidate_ids = [protocol.image_id(name) for name in candidates]
    if len(set(candidate_ids)) != 3700:
        raise ValueError("candidate hash collision or incomplete candidate support")
    candidate_concepts = [concepts[name] for name in candidates]
    if Counter(Counter(candidate_concepts).values()) != Counter({5: 620, 6: 100}):
        raise ValueError("frozen 720-concept distractor census required")
    candidate_lookup = {name: i for i, name in enumerate(candidates)}
    cases, roster, all_query_ids = [], {}, set()
    query_union = set(candidates)
    validation_union = {r["stimulus"] for split in splits.values() for r in split["validation"]}
    for person in protocol.SUBJECTS:
        split = splits[person]
        if {r["stimulus"] for r in split["train"]} & (query_union | validation_union):
            raise ValueError("cross-person image leakage into training")
        if {r["stimulus"] for r in split["validation"]} & query_union:
            raise ValueError("cross-person query image leakage into development")
        groups = {}
        for row in split["query"]:
            groups.setdefault(row["stimulus"], []).append(row["trial_id"])
        if Counter(map(len, groups.values())) != Counter({1: 1440, 2: 100}):
            raise ValueError("frozen singleton/two-presentation query support required")
        # Retain the original construction's ordering and IDs exactly. These are
        # private-seeded hashes, not an assertion of cryptographic anonymity.
        order = sorted(groups, key=lambda name: hashlib.sha256((seed + "|" + person + "|" + name).encode()).digest())
        queries = [{"id": "q" + hashlib.sha256((seed + "query|" + person + "|" + name).encode()).hexdigest()[:24],
                    "trial_ids": sorted(groups[name]), "candidate_index": candidate_lookup[name]} for name in order]
        qids = [row["id"] for row in queries]
        if len(set(qids)) != 1540 or all_query_ids.intersection(qids):
            raise ValueError("query hash collision")
        all_query_ids.update(qids)
        for roi in protocol.ROIS:
            key = f"sub-{person}_{roi}"
            cases.append({"id": key, "person": person, "roi": roi,
                          "train_trial_ids": [r["trial_id"] for r in split["train"]],
                          "train_images": [r["stimulus"] for r in split["train"]],
                          "validation_trial_ids": [r["trial_id"] for r in split["validation"]],
                          "validation_images": [r["stimulus"] for r in split["validation"]],
                          "queries": copy.deepcopy(queries)})
            roster[key] = {"query_ids": qids.copy(), "candidate_ids": candidate_ids.copy()}
    design = {"schema": "neural051-design-v1", "candidates": candidates,
              "candidate_ids": candidate_ids, "candidate_concepts": candidate_concepts,
              "cases": cases, "source_pins": dict(source_pins), "full_canonical_split": True}
    return design, roster


def _ordinary_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink path ancestry is not accepted")
    return path


def capture_design(metadata, pins, seed):
    """Authenticate all three bounded metadata bodies before constructing maps."""
    _pins(pins)
    root = _ordinary_path(metadata)
    rows, captured = {}, {}
    for person in protocol.SUBJECTS:
        raw, digest = file_io.capture(root / f"sub-{person}_StimulusMetadata.csv", SOURCE_LIMIT, pins[person])
        rows[person] = parse_metadata(raw)
        captured[person] = digest
    design, roster = build_rows(rows, seed, captured)
    return design, roster


def _json(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def write_bundle(output, design, roster):
    """Create an operator-private directory; never overwrite existing outputs."""
    output = _ordinary_path(output)
    if not output.parent.is_dir():
        raise ValueError("existing ordinary output parent required")
    payloads = {"design.json": _json(design), "roster.json": _json(roster)}
    if sum(map(len, payloads.values())) > 5_000_000:
        raise ValueError("metadata output byte cap")
    receipt = {"schema": "neural051-metadata-preparation-v1", "task_id": "NEURAL-051",
               "status": "metadata_mapping_only", "source_pins": design["source_pins"],
               "files": {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in payloads.items()},
               "canonical_roster_sha256": hashlib.sha256(json.dumps(roster, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
               "source_response_join_verified": False, "neural_arrays_read": False,
               "image_pixels_read": False, "runtime_qualified": False,
               "native_understanding_evidence": False}
    payloads["PREPARATION.json"] = _json(receipt)
    output.mkdir(mode=0o700, exist_ok=False)
    for name, raw in payloads.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("metadata", "pins", "seed-file", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    pins = file_io.decode(file_io.capture(_ordinary_path(args.pins), 2048)[0])
    seed = file_io.capture(_ordinary_path(args.seed_file), 4096)[0].decode("utf-8").strip()
    design, roster = capture_design(args.metadata, pins, seed)
    write_bundle(args.output, design, roster)


if __name__ == "__main__":
    main()
