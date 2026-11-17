"""Read original retrieval metadata/markers without loading EEG or fitting a model.

The label masks are the LMU 596 Figure 3a masks, not a final-paper scorer.
All source rows survive, including foils and nonbinary ExemplarAccuracy codes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

PARTICIPANTS = ("P02", "P05", "P07", "P09", "P11", "P12", "P13", "P14", "P15",
                "P16", "P19", "P21", "P22", "P25", "P26", "P29", "P30", "P31")
FIELDS = ("SubjectNumber", "Part", "Phase", "Run", "TrialNumber", "FixationDur",
          "Verb", "Image", "Art_Nat", "OldNew", "Answer1", "RT1", "Answer1Accuracy",
          "ExemplarResponse", "ExemplarAccuracy", "WriteOutTime", "TriggerTime",
          "TriggerTime2", "Clock")
INTEGER_FIELDS = {"SubjectNumber", "Part", "Run", "TrialNumber", "Art_Nat", "OldNew",
                  "Answer1Accuracy", "ExemplarAccuracy"}
FLOAT_FIELDS = {"FixationDur", "RT1", "WriteOutTime", "TriggerTime", "TriggerTime2"}
ARCHIVE_SHA256 = "22f245506d4c8a87887e1bd6cfbb47c133223fa5c2989963c27449bc0fcdcd1c"


def read_behavior(text: str) -> list[dict]:
    """Parse the 19-column retrieval log described by splitTrials_breathFeat.

    Require the source column order instead of guessing from partial headings.
    Retain negative/nonbinary integer codes verbatim; they are not booleans.
    """
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter="\t")
    header = next(reader, None)
    if header != list(FIELDS):
        raise ValueError("retrieval header must match the 19 native source columns")
    rows = []
    for ordinal, cells in enumerate(reader, start=1):
        if len(cells) != len(FIELDS):
            raise ValueError(f"metadata row {ordinal}: expected 19 tab-separated fields")
        row = dict(zip(FIELDS, cells))
        for field in INTEGER_FIELDS:
            if not re.fullmatch(r"[+-]?\d+", row[field]):
                raise ValueError(f"metadata row {ordinal}: {field} is not an integer")
            row[field] = int(row[field])
        for field in FLOAT_FIELDS:
            try:
                float(row[field])
            except ValueError as exc:
                raise ValueError(f"metadata row {ordinal}: invalid {field}") from exc
            # These fields do not participate in the source class masks. Keep
            # lexical tokens, including NaN/Inf missing-response conventions,
            # instead of introducing a new exclusion or invalid JSON numbers.
        rows.append(row)
    if not rows:
        raise ValueError("empty retrieval metadata")
    return rows


def read_cue_markers(text: str) -> list[dict]:
    """Keep literal S 41 markers in file order with one-based 1000-Hz samples.

    BrainVision uses \\1 to encode a literal comma inside a field. A cue's
    description is compared exactly, as in the author helper.
    """
    section = None
    seen = set()
    cues = []
    for line in text.lstrip("\ufeff").splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line
            continue
        if section != "[Marker Infos]":
            continue
        match = re.fullmatch(r"(Mk\d+)=(.*)", line)
        if not match:
            raise ValueError("malformed BrainVision marker entry")
        key, payload = match.groups()
        if key in seen:
            raise ValueError("duplicate BrainVision marker key")
        seen.add(key)
        values = [x.replace("\\1", ",") for x in payload.split(",")]
        if len(values) < 5:
            raise ValueError("incomplete BrainVision marker")
        if values[1] != "S 41":
            continue
        if not re.fullmatch(r"\d+", values[2]) or int(values[2]) < 1:
            raise ValueError("cue sample must be a positive one-based integer")
        sample = int(values[2])
        if cues and sample <= cues[-1]["sample_1000hz_one_based"]:
            raise ValueError("cue samples must increase strictly in marker-file order")
        cues.append({"marker_key": key, "sample_1000hz_one_based": sample})
    if not cues:
        raise ValueError("no literal S 41 retrieval cues")
    return cues


def label_group(row: dict) -> str | None:
    """Exact Figure 3a label mask; recognition accuracy is not an extra filter."""
    if row["OldNew"] != 1:
        return None
    if row["ExemplarAccuracy"] == 1:
        return "remembered"
    if row["ExemplarAccuracy"] == 0:
        return "not_remembered"
    return None


def join_session(rows: list[dict], cues: list[dict], participant: str,
                 category: str, block: str, recording_sample_rate_hz: int) -> dict:
    """Join the source's nth behavior row to nth cue, retaining that assumption.

    This fails on unequal counts and duplicate identities. Equal counts alone do
    not authenticate a positional join; continuous EEG/event reconciliation is
    explicitly still required.
    """
    if participant not in PARTICIPANTS:
        raise ValueError("participant is outside the original 18-person roster")
    if category not in {"object", "scene"} or block not in {"ret1", "ret2"}:
        raise ValueError("category must be object/scene and block ret1/ret2")
    if type(recording_sample_rate_hz) is not int or recording_sample_rate_hz <= 0:
        raise ValueError("declare a positive integer recording fsample from the native continuous input")
    if len(rows) != len(cues):
        raise ValueError("behavior/cue count mismatch; positional join refused")
    records, keys = [], set()
    for ordinal, (row, cue) in enumerate(zip(rows, cues), start=1):
        if row["SubjectNumber"] != int(participant[1:]):
            raise ValueError("SubjectNumber disagrees with the declared participant")
        key = f"{participant}/{category}/{block}/run-{row['Run']}/trial-{row['TrialNumber']}"
        if key in keys:
            raise ValueError("duplicate native trial identity")
        keys.add(key)
        group = label_group(row)
        # Source round(x / 1000 * fsample), for positive marker samples. Retain
        # original one-based samples; do not silently apply a zero-based offset.
        source_sample = (cue["sample_1000hz_one_based"] * recording_sample_rate_hz + 500) // 1000
        records.append({
            "trial_id": key, "source_row_one_based": ordinal,
            "participant_id": participant, "category": category, "block": block,
            "source_stimtype": 1 if category == "object" else 2,
            "source_metadata": dict(row), "cue": dict(cue),
            "source_cue_sample_at_recording_rate": source_sample,
            "label_group": group,
            "label_exclusion": None if group else (
                "OldNew_not_equal_to_1" if row["OldNew"] != 1
                else "ExemplarAccuracy_not_equal_to_0_or_1"),
        })
    counts = Counter(r["label_group"] or "excluded_by_labels" for r in records)
    return {"participant_id": participant, "category": category, "block": block,
            "declared_recording_sample_rate_hz": recording_sample_rate_hz,
            "join_policy": "nth behavior row to nth literal S 41 cue; source positional assumption",
            "all_rows": len(records),
            "label_counts": {k: counts[k] for k in ("remembered", "not_remembered", "excluded_by_labels")},
            "records": records}


def source_receipt(path: Path, contents: bytes) -> dict:
    return {"filename": path.name, "bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("behavior", type=Path)
    parser.add_argument("markers", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--participant", required=True, choices=PARTICIPANTS)
    parser.add_argument("--category", required=True, choices=("object", "scene"))
    parser.add_argument("--block", required=True, choices=("ret1", "ret2"))
    parser.add_argument("--recording-sample-rate-hz", required=True, type=int,
                        help="native continuous recording fsample; this declaration is not authentication")
    parser.add_argument("--data-kind", required=True,
                        choices=("authentic_public_source_metadata", "generated_engineering_control"))
    args = parser.parse_args()
    if args.output.resolve() in {args.behavior.resolve(), args.markers.resolve()}:
        parser.error("output must not overwrite either source file")
    behavior, markers = args.behavior.read_bytes(), args.markers.read_bytes()
    session = join_session(read_behavior(behavior.decode("utf-8-sig")),
                           read_cue_markers(markers.decode("utf-8-sig")),
                           args.participant, args.category, args.block, args.recording_sample_rate_hz)
    result = {
        "schema": "respiration-native-retrieval-metadata-v1",
        "data_kind": args.data_kind,
        "source_archive_sha256": ARCHIVE_SHA256,
        "inputs": {"behavior": source_receipt(args.behavior, behavior),
                   "markers": source_receipt(args.markers, markers)},
        "session": session,
        "scope": "source-label admission only; no EEG or respiratory-event admission",
        "remaining_requirements": [
            "continuous EEG and metadata/trigger identity reconciliation",
            "BreathMetrics exhalation detection, last strict 0<t<3 event and complete +/-3 s epochs",
            "all 18 participants and both categories/blocks, with original eligible trials",
            "source/final-publication version and native dependency reconciliation",
            "author AUC execution and frozen paired-participant improvement comparison",
        ],
    }
    # Exclusive creation protects existing source/output evidence against replacement.
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
