#!/usr/bin/env python3
"""Recompute the original OpenMIIR matched-support question from pinned metadata.

This audits stimulus design, not EEG or model performance. Exact equality here
means equality of recorded numeric metadata, not physical rhythm equivalence.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
from itertools import combinations
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
COMMIT = "f3418202d8ae9311e9d69238fba694dc437232f8"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
IDS = (1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24)
# These paired compositions are explicitly identified in the author Table 1,
# not inferred by stripping words from a filename or EEG label.
COMPOSITION = {i: i - 10 if i in (11, 12, 13, 14) else i for i in IDS}
SUBJECTS = {1: ["P01", "P04", "P05", "P06", "P07"],
            2: ["P09", "P11", "P12", "P13", "P14"]}
COLUMNS = {"A": "id", "B": "label", "C": "audio_file",
           "D": "song_plus_cue_seconds", "E": "cue_seconds",
           "F": "song_seconds", "G": "cue_file_seconds",
           "H": "cue_bpm", "I": "beats_per_bar",
           "O": "num_bars", "P": "cue_bars", "Q": "measured_bpm"}
NUMERIC = set(COLUMNS.values()) - {"label", "audio_file"}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def numeric(value):
    require(isinstance(value, str), "metadata numbers must retain their source decimal text")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid metadata decimal") from exc
    require(result.is_finite() and result > 0, "metadata values must be finite and positive")
    return result


def workbook_rows(data):
    """Parse the pinned workbook's first sheet without running macros/formulas.

    Numeric values are the source XML's cached decimal strings. No new rounding
    tolerance or estimate from audio is applied.
    """
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        strings = ["".join(t.text or "" for t in item.findall(".//s:t", NS))
                   for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    result = []
    for row in sheet.findall(".//s:row", NS):
        index = int(row.attrib["r"])
        if not 2 <= index <= 13:
            continue
        cells = {}
        for cell in row.findall("s:c", NS):
            column = "".join(c for c in cell.attrib["r"] if c.isalpha())
            if column not in COLUMNS:
                continue
            value = cell.find("s:v", NS)
            require(value is not None and value.text is not None, "missing pinned workbook value")
            text = strings[int(value.text)] if cell.attrib.get("t") == "s" else value.text
            cells[COLUMNS[column]] = text
        require(set(cells) == set(COLUMNS.values()), "incomplete source metadata row")
        for key in NUMERIC:
            numeric(cells[key])
        identifier = numeric(cells["id"])
        require(identifier == identifier.to_integral_value(), "noninteger stimulus ID")
        cells["id"] = int(identifier)
        result.append(cells)
    validate_rows(result)
    return result


def validate_rows(rows):
    require(isinstance(rows, list) and len(rows) == 12, "all 12 original stimuli are required")
    require(all(isinstance(row, dict) and type(row.get("id")) is int for row in rows),
            "stimulus IDs must be integers")
    require(sorted(row["id"] for row in rows) == sorted(IDS), "duplicate or wrong stimulus roster")
    for row in rows:
        require(set(row) == set(COLUMNS.values()), "unexpected or missing metadata fields")
        for key in NUMERIC - {"id"}:
            numeric(row[key])
        require(all(isinstance(row[key], str) and row[key] for key in ("label", "audio_file")),
                "missing source label or audio filename")


def matching_pairs(rows, tempo_field, *, duration):
    keys = [tempo_field, "beats_per_bar"] + (["song_seconds"] if duration else [])
    result = []
    for left, right in combinations(sorted(rows, key=lambda row: row["id"]), 2):
        if all(numeric(left[key]) == numeric(right[key]) for key in keys):
            pair = [left["id"], right["id"]]
            result.append({"stimulus_ids": pair,
                           "same_composition": COMPOSITION[pair[0]] == COMPOSITION[pair[1]]})
    return result


def audit_version(rows, version):
    validate_rows(rows)
    require(type(version) is int and version in (1, 2), "explicit original stimulus version is required")
    # The author's metadata loader uses measured_bpm for v1, cue_bpm for v2.
    effective = "measured_bpm" if version == 1 else "cue_bpm"
    comparisons = {}
    for label, field in (("cue_tempo", "cue_bpm"), ("author_effective_tempo", effective)):
        pairs = matching_pairs(rows, field, duration=False)
        joint = matching_pairs(rows, field, duration=True)
        comparisons[label] = {
            "tempo_field": field,
            "meter_tempo_pairs": pairs,
            "meter_tempo_duration_pairs": joint,
            "different_composition_meter_tempo_pairs": [p for p in pairs if not p["same_composition"]],
            "different_composition_joint_pairs": [p for p in joint if not p["same_composition"]],
        }
    return {
        "version": version, "released_participants": SUBJECTS[version],
        "complete_stimulus_count": len(rows), "enumerated_unordered_pairs": 66,
        "original_duration_values_unique": len({numeric(row["song_seconds"]) for row in rows}) == 12,
        "comparisons": comparisons,
        "source_rows": sorted(rows, key=lambda row: row["id"]),
    }


def audit(source_root, metadata_loader):
    source_root = Path(source_root).resolve()
    source = json.loads((HERE / "source_manifest.json").read_text())
    require(source["commit"] == COMMIT, "incorrect source revision")
    loader_record = source["author_metadata_loader"]
    loader_bytes = Path(metadata_loader).read_bytes()
    require(len(loader_bytes) == loader_record["bytes"]
            and digest(loader_bytes) == loader_record["sha256"],
            "author metadata loader differs from the pinned version semantics")
    verified, contents = [], {}
    for record in source["files"]:
        path = source_root / record["path"]
        require(path.is_file() and not path.is_symlink(), "required regular source file missing")
        data = path.read_bytes()
        require(len(data) == record["bytes"] and digest(data) == record["sha256"],
                "source bytes differ: " + record["path"])
        git_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(git_blob == record["git_blob_sha1"], "source Git blob differs")
        verified.append(record)
        contents[record["path"]] = data
    versions = [audit_version(workbook_rows(contents[f"meta/Stimuli_Meta.v{version}.xlsx"]), version)
                for version in (1, 2)]
    return {
        "schema": "openmiir_original_matched_support_v1",
        "source_repository": source["repository"], "source_commit": COMMIT,
        "source_files": verified,
        "author_metadata_loader": loader_record,
        "units": {"tempo": "beats/minute", "meter": "beats/bar", "durations": "seconds"},
        "comparison_rule": "Exact equality of the recorded source decimal values, separately within each stimulus version. No tolerance, cross-version pooling, rounding to the paper table, or time-warping.",
        "versions": versions,
        "conclusion": "Original OpenMIIR does not supply different-composition alternatives with matched declared tempo and meter. Full recorded song-duration matching supplies no alternatives at all. Equal-duration cropping cannot create the missing cross-composition tempo support.",
        "interpretation_limits": [
            "Recorded tempo/meter equality is not proof that the physiological rhythm, beat onsets, or imagined timing are identical.",
            "Same-composition lyric/instrumental classification is a different endpoint; these pairs do not identify a melody contrast.",
            "The source presentation displays the requested song name and lyric state before imagery. If full instruction identity is supplied to a nuisance comparator, it determines the requested excerpt by design. This is a design argument, not an observed classification score.",
            "If a future task exposes only rhythmic clicks, that narrower observation contract must be explicit; the unmatched melody support remains unresolved.",
            "Full stimulus durations identify the source excerpts in this table; fixed equal windows must not carry original-duration or source-ID leakage.",
            "No EEG file, neural target, participant prediction, fitted model, or current protected answer was opened. No scientific neural-performance finding follows.",
        ],
        "neural_performance": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path,
                        help="Pinned original openmiir source tree containing the two metadata workbooks")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata-loader", required=True, type=Path,
                        help="Pinned deepthought/datasets/openmiir/metadata.py; verified, never imported")
    args = parser.parse_args(argv)
    report = audit(args.source_root, args.metadata_loader)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"metadata_versions": len(report["versions"]), "stimuli_per_version": 12,
                      "distinct_composition_match_count": sum(
                          len(v["comparisons"]["author_effective_tempo"]["different_composition_joint_pairs"])
                          for v in report["versions"]), "neural_performance": None}))


if __name__ == "__main__":
    main()
