"""Prepare the full source retrieval metadata census without opening EEG arrays.

The 72 declared participant/category/block cells do not authenticate the source
inputs, original trial completeness, respiratory admission, or final-paper fit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import native_trials as native

SCHEMA = "respiration-native-retrieval-cohort-inputs-v1"
CATEGORIES = ("object", "scene")
BLOCKS = ("ret1", "ret2")
CELLS = tuple((p, c, b) for p in native.PARTICIPANTS for c in CATEGORIES for b in BLOCKS)
DATA_KINDS = ("authentic_public_source_metadata", "generated_engineering_control")
LABELS = ("remembered", "not_remembered", "excluded_by_labels")


def input_path(value: str, root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("behavior and markers must be nonempty file paths")
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def plan_inputs(manifest: dict, root: Path) -> list[dict]:
    """Check the complete original cell roster before opening any input files."""
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if manifest.get("data_kind") not in DATA_KINDS:
        raise ValueError("declare authentic_public_source_metadata or generated_engineering_control")
    entries = manifest.get("sessions")
    if not isinstance(entries, list):
        raise ValueError("sessions must contain the complete 72 source cells")
    cells = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each source cell must be an object")
        cell = tuple(entry.get(k) for k in ("participant_id", "category", "block"))
        if cell not in CELLS:
            raise ValueError(f"unexpected source cell: {cell!r}")
        if cell in cells:
            raise ValueError(f"duplicate source cell: {cell!r}")
        rate = entry.get("recording_sample_rate_hz")
        if type(rate) is not int or rate <= 0:
            raise ValueError("each source cell requires a positive integer native recording fsample")
        cells[cell] = {
            "cell": cell, "rate": rate,
            "behavior": input_path(entry.get("behavior"), root),
            "markers": input_path(entry.get("markers"), root),
        }
    missing = ["/".join(cell) for cell in CELLS if cell not in cells]
    if missing:
        raise ValueError("incomplete source cohort; missing cells: " + ", ".join(missing))
    return [cells[cell] for cell in CELLS]


def prepare(manifest: dict, root: Path) -> dict:
    """Run the existing single-session source adapter on every original cell."""
    sessions = []
    for entry in plan_inputs(manifest, root):
        behavior = entry["behavior"].read_bytes()
        markers = entry["markers"].read_bytes()
        participant, category, block = entry["cell"]
        session = native.join_session(
            native.read_behavior(behavior.decode("utf-8-sig")),
            native.read_cue_markers(markers.decode("utf-8-sig")),
            participant, category, block, entry["rate"],
        )
        sessions.append({
            "inputs": {
                "behavior": native.source_receipt(entry["behavior"], behavior),
                "markers": native.source_receipt(entry["markers"], markers),
            },
            "session": session,
        })
    participants = []
    for participant in native.PARTICIPANTS:
        rows = [s["session"] for s in sessions if s["session"]["participant_id"] == participant]
        counts = Counter()
        for row in rows:
            counts.update(row["label_counts"])
        participants.append({
            "participant_id": participant, "session_count": len(rows),
            "all_rows": sum(row["all_rows"] for row in rows),
            "label_counts": {label: counts[label] for label in LABELS},
        })
    return {
        "schema": "respiration-native-retrieval-cohort-v1",
        "data_kind": manifest["data_kind"],
        "source_archive_sha256": native.ARCHIVE_SHA256,
        "scope": "complete declared source-cell metadata census; no EEG or respiratory-event admission",
        "scientifically_qualified": False,
        "participant_ids": list(native.PARTICIPANTS),
        "session_count": len(sessions),
        "all_rows": sum(p["all_rows"] for p in participants),
        "label_counts": {label: sum(p["label_counts"][label] for p in participants) for label in LABELS},
        "participants": participants,
        "sessions": sessions,
        "remaining_requirements": [
            "authenticate the manifest declarations and original trial inventory against source files",
            "continuous EEG and metadata/trigger identity reconciliation",
            "BreathMetrics exhalation detection, last strict 0<t<3 event and complete +/-3 s epochs",
            "independent localizer preparation and original eligible trial/channel support",
            "source/final-publication version and native dependency reconciliation",
            "author AUC execution and frozen paired-participant improvement comparison",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    root = args.manifest.resolve().parent
    entries = plan_inputs(manifest, root)
    sources = {args.manifest.resolve()} | {entry[k] for entry in entries for k in ("behavior", "markers")}
    if args.output.resolve() in sources:
        parser.error("output must not overwrite the manifest or any source file")
    if args.output.exists():
        parser.error("output already exists; evidence is never replaced")
    result = prepare(manifest, root)
    result["input_manifest"] = native.source_receipt(args.manifest, raw)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
