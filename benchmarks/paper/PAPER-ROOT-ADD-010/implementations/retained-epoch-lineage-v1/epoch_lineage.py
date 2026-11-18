"""Project original event metadata through a supplied MNE Epochs.selection.

This operator-side component reads no MEG signals and does not extract or
authenticate Epochs.selection from FIF. Declared file pins are not upstream
authentication. It preserves the author's pre-rejection miniblock algorithm.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat

SOURCE_REVISION = "133669b577b5ae341cd0842dfb0e7f0af85c0020"
SUBJECTS = tuple(f"sub-{n:02}" for n in range(1, 21))
SHAPES = ("rectangle", "square", "isoTrapezoid", "parallelogram", "losange",
          "kite", "rightKite", "rustedHinge", "hinge", "trapezoid", "random")
HASH = re.compile(r"[0-9a-f]{64}\Z")
LIMITS = [
    "File bytes matched supplied pins, not independently authenticated upstream identities.",
    "Selection and prepared-FIF identity are supplied assertions, not extracted or verified here.",
    "The exact relation between complete BIDS events and MNE original epoch indexing remains an external source gate.",
    "Final-paper epoch grid, scaling, smoothing, strongest baseline and author outputs remain unresolved.",
    "No neural data, decoder fitting, scientific reproduction, improvement or readiness is established.",
    "Output contains evaluator-only target metadata and must not be exposed as candidate features.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def expected_runs(subject):
    require(subject in SUBJECTS, "unknown original subject")
    return tuple(range(1, 8 if subject in ("sub-10", "sub-11") else 9))


def check_pin(pin, path_required=True):
    keys = {"bytes", "sha256", "path"} if path_required else {"bytes", "sha256"}
    require(isinstance(pin, dict) and set(pin) == keys, "invalid file pin fields")
    require(type(pin["bytes"]) is int and pin["bytes"] > 0, "invalid file extent")
    require(isinstance(pin["sha256"], str) and HASH.fullmatch(pin["sha256"]), "invalid SHA256")


def parse_events(raw):
    """Read all TSV rows in their original order; never silently drop events."""
    require(isinstance(raw, bytes), "event input must be bytes")
    text = raw.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter="\t")
    header = reader.fieldnames
    require(header and len(header) == len(set(header)) and "trial_type" in header,
            "require unique TSV columns including trial_type")
    result = []
    for row in reader:
        require(None not in row and all(v is not None for v in row.values()), "ragged event row")
        token = row["trial_type"]
        require(isinstance(token, str), "missing trial_type")
        parts = token.split("/")
        require(len(parts) in (3, 4) and all(parts), "unrecognized trial_type grammar")
        require(parts[1] in SHAPES and parts[2] in ("reference", "outlier"),
                "unknown source shape or reference/outlier condition")
        if len(parts) == 4:
            require(re.fullmatch(r"[0-4]", parts[3]) is not None, "invalid outlier subtype")
        result.append({"shape": parts[1], "condition": parts[2]})
    require(result, "empty original run event table")
    return result


def project_subject(subject, runs, selection, prepared_epoch_pin):
    """Produce scorer-compatible rows and a separate evaluator-only lineage.

    `runs` contains all original event tables as {run, bytes, sha256, events},
    with parsed events returned by parse_events. This in-memory API validates
    declarations; load_cohort additionally checks the actual input file bytes.
    """
    check_pin(prepared_epoch_pin, path_required=False)
    require(isinstance(runs, list), "runs must be a list")
    by_run = {}
    for entry in runs:
        require(isinstance(entry, dict) and set(entry) == {"run", "bytes", "sha256", "events"},
                "invalid event run fields")
        run = entry["run"]
        require(type(run) is int and run not in by_run, "duplicate or noninteger run")
        check_pin({k: entry[k] for k in ("bytes", "sha256")}, path_required=False)
        require(isinstance(entry["events"], list) and entry["events"], "empty event run")
        by_run[run] = entry
    require(set(by_run) == set(expected_runs(subject)), "incomplete or extra original run inventory")
    require(isinstance(selection, list) and selection, "selection must be a nonempty integer list")
    require(all(type(i) is int for i in selection), "selection indices must be integers, not booleans")
    require(len(selection) == len(set(selection)), "duplicate retained selection index")
    # The source concatenates runs before computing this counter. Do NOT reset
    # at run boundaries or after rejected epochs. Preserve that behavior even
    # where it differs from an intuitive within-run miniblock interpretation.
    full = []
    last_shape, counter = None, 0
    for run in expected_runs(subject):
        entry = by_run[run]
        for row_index, event in enumerate(entry["events"]):
            require(isinstance(event, dict) and set(event) == {"shape", "condition"},
                    "invalid parsed event fields")
            shape, condition = event["shape"], event["condition"]
            require(shape in SHAPES and condition in ("reference", "outlier"), "unknown event condition")
            counter = (counter + 1) % 30 if shape == last_shape else 0
            last_shape = shape
            original_index = len(full)
            identity_bytes = json.dumps(["root010-source-event/v1", subject, run,
                                         row_index, entry["sha256"]], separators=(",", ":")).encode()
            full.append({"trial_id": hashlib.sha256(identity_bytes).hexdigest(),
                         "run": run, "shape": shape, "condition": condition,
                         "is_early": "early" if counter < 6 else "late",
                         "source_event_index": original_index,
                         "source_run_row_index": row_index,
                         "trial_number_from_miniblock": counter})
    require(all(0 <= i < len(full) for i in selection), "selection index outside full event support")
    retained = [full[i] for i in selection]
    fields = ("trial_id", "run", "shape", "condition", "is_early")
    return {"subject": subject,
            "trials": [{k: row[k] for k in fields} for row in retained],
            "retained_epoch_lineage": [dict(row, retained_epoch_index=i) for i, row in enumerate(retained)],
            "original_event_count": len(full), "retained_epoch_count": len(retained),
            "prepared_epoch_identity_declared_unverified": dict(prepared_epoch_pin),
            "event_file_pins": [{"run": run, "bytes": by_run[run]["bytes"],
                                 "sha256": by_run[run]["sha256"]} for run in expected_runs(subject)]}


class BoundedFiles:
    """Confined operator input reads; not an OS isolation or provenance service."""
    def __init__(self, root, max_file_bytes=8 * 1024**2, max_total_bytes=128 * 1024**2):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), "input root must be a directory")
        require(type(max_file_bytes) is int and max_file_bytes > 0, "invalid file byte bound")
        require(type(max_total_bytes) is int and max_total_bytes > 0, "invalid total byte bound")
        self.max_file_bytes, self.max_total_bytes = max_file_bytes, max_total_bytes
        self.read_bytes = 0

    def read(self, pin):
        check_pin(pin)
        name = pin["path"]
        require(isinstance(name, str) and name and "\\" not in name, "invalid relative input path")
        relative = Path(name)
        require(not relative.is_absolute() and all(p not in ("..", ".") for p in name.split("/"))
                and "" not in name.split("/"), "input path must be canonical relative path")
        target = self.root
        for part in relative.parts:
            target = target / part
            require(not target.is_symlink(), "input symlinks are not accepted")
        require(stat.S_ISREG(target.stat().st_mode), "input must be a regular file")
        require(pin["bytes"] <= self.max_file_bytes and
                self.read_bytes + pin["bytes"] + 1 <= self.max_total_bytes, "input byte bound exceeded")
        with target.open("rb") as handle:
            raw = handle.read(pin["bytes"] + 1)
        self.read_bytes += len(raw)
        require(len(raw) == pin["bytes"], "input extent mismatch")
        require(hashlib.sha256(raw).hexdigest() == pin["sha256"], "input SHA256 mismatch")
        return raw


def load_cohort(manifest, input_root):
    require(isinstance(manifest, dict) and set(manifest) == {"schema", "source_revision", "subjects"},
            "invalid lineage manifest fields")
    require(manifest["schema"] == "root010-epoch-lineage-input/v1" and
            manifest["source_revision"] == SOURCE_REVISION, "source or schema mismatch")
    require(isinstance(manifest["subjects"], list) and len(manifest["subjects"]) == 20,
            "require all twenty original participants")
    by_subject = {}
    for entry in manifest["subjects"]:
        require(isinstance(entry, dict) and set(entry) == {"subject", "events", "selection"},
                "invalid subject manifest fields")
        subject = entry["subject"]
        require(isinstance(subject, str) and subject in SUBJECTS and subject not in by_subject,
                "unknown or duplicate subject")
        require(isinstance(entry["events"], list), "event file entries must be a list")
        run_ids = []
        for event in entry["events"]:
            require(isinstance(event, dict) and set(event) == {"run", "file"}, "invalid event file entry")
            require(type(event["run"]) is int, "run must be an integer")
            check_pin(event["file"])
            run_ids.append(event["run"])
        require(len(run_ids) == len(set(run_ids)) and set(run_ids) == set(expected_runs(subject)),
                "incomplete or extra original run inventory")
        check_pin(entry["selection"])
        by_subject[subject] = entry
    files, output = BoundedFiles(input_root), []
    for subject in SUBJECTS:
        entry = by_subject[subject]
        require(isinstance(entry["events"], list), "event file entries must be a list")
        runs = []
        for event in entry["events"]:
            require(isinstance(event, dict) and set(event) == {"run", "file"}, "invalid event file entry")
            raw = files.read(event["file"])
            runs.append({"run": event["run"], "events": parse_events(raw),
                         "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        selected = strict_json(files.read(entry["selection"]))
        require(isinstance(selected, dict) and set(selected) == {"schema", "subject", "selection", "prepared_epochs"},
                "invalid selection export fields")
        require(selected["schema"] == "root010-mne-selection-export/v1" and selected["subject"] == subject,
                "selection subject or schema mismatch")
        result = project_subject(subject, runs, selected["selection"], selected["prepared_epochs"])
        result["selection_export_pin"] = dict(entry["selection"])
        output.append(result)
    return {"schema": "root010-epoch-lineage-output/v1", "source_revision": SOURCE_REVISION,
            "scope": "operator_metadata_projection_only", "research_qualified": False,
            "input_read_bytes": files.read_bytes, "subjects": output, "limits": list(LIMITS)}


def write_result(path, result):
    # Serialize first, so a schema/nonfinite failure cannot leave a truncated success file.
    raw = (json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n").encode()
    with Path(path).open("xb") as handle:
        handle.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.manifest.open("rb") as handle:
        raw = handle.read(1024**2 + 1)
    require(len(raw) <= 1024**2, "manifest exceeds one MiB")
    result = load_cohort(strict_json(raw), args.input_root)
    result["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    write_result(args.output, result)


if __name__ == "__main__":
    main()
