"""Paired literal-source and grouped spectral smoothing; no fitting or scoring.

The source applies a five-row/three-frequency uniform filter to linear power.
Both arms retain every input row, column, and its original output position.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

TASK_ID = "PAPER-ROOT-ADD-021"
SOURCE_COMMIT = "218f87e81d4aa8ac3658467f4a4c85ad1dc4128d"
SOURCE_SHA256 = "30ef3d9091ad53568d071dc15e21d28e23d55d8606946440f97f7ccc1cc9f629"
REGIONS = frozenset(("Postcentral_gyrus", "Precentral_gyrus", "Superior_temporal_gyrus",
                     "Middle_frontal_gyrus", "Middle_temporal_gyrus", "Supramarginal_gyrus"))
META = ("ID", "age", "region", "time")
FREQUENCIES = tuple(i / 2 for i in range(1, 201))


class InputError(ValueError):
    """An input changes the declared source table or observation coverage."""


def number(value, label):
    if isinstance(value, bool):
        raise InputError(f"Boolean {label}")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise InputError(f"Invalid {label}") from exc
    if not math.isfinite(result):
        raise InputError(f"Nonfinite {label}")
    return result


def read_table(data, packet):
    """Read an operator-pinned table, requiring exact group coverage and grid."""
    if not isinstance(packet, dict):
        raise InputError("Packet must be a JSON object")
    if packet.get("task_id") != TASK_ID or packet.get("source_commit") != SOURCE_COMMIT:
        raise InputError("Task/source pin mismatch")
    if packet.get("table_sha256") != hashlib.sha256(data).hexdigest():
        raise InputError("Table SHA-256 mismatch")
    assessment = packet.get("assessment_kind")
    if assessment not in ("generated_engineering_control", "unqualified_public_spectral_table"):
        raise InputError("Declare generated or unqualified public source table")
    roster = packet.get("expected_participants")
    if (not isinstance(roster, list) or not roster
            or any(not isinstance(p, str) or not p.strip() for p in roster)
            or len(roster) != len(set(roster))):
        raise InputError("Participant roster must contain unique nonempty strings")
    if assessment == "unqualified_public_spectral_table" and len(roster) != 13:
        raise InputError("Original public cohort requires thirteen declared participants")
    expected = {}
    declarations = packet.get("expected_groups")
    if not isinstance(declarations, list):
        raise InputError("Expected groups must be an explicit list")
    for entry in declarations:
        if not isinstance(entry, dict):
            raise InputError("Invalid expected group")
        key = (entry.get("ID"), entry.get("region"))
        count = entry.get("row_count")
        if (not all(isinstance(value, str) for value in key)
                or key[0] not in roster or key[1] not in REGIONS or key in expected
                or type(count) is not int or count < 1):
            raise InputError("Invalid/duplicate expected group or row count")
        age = number(entry.get("age"), "expected age")
        start = number(entry.get("start_time"), "expected start time")
        end = number(entry.get("end_time"), "expected end time")
        if age <= 0 or start < 0 or end < start:
            raise InputError("Invalid group age/time range")
        expected[key] = (count, age, start, end)
    if not expected or {key[0] for key in expected} != set(roster):
        raise InputError("Expected groups must cover the entire declared roster")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader)
    except (UnicodeError, StopIteration) as exc:
        raise InputError("Invalid or empty CSV") from exc
    if len(header) != 204 or len(set(header)) != 204 or tuple(header[:4]) != META:
        raise InputError("Require four native metadata columns and 200 unique frequency columns")
    if tuple(number(v, "frequency") for v in header[4:]) != FREQUENCIES:
        raise InputError("Require original ordered 0.5 through 100 Hz grid in 0.5 Hz steps")
    metadata, powers, groups, seen, ages = [], [], defaultdict(list), set(), {}
    for index, row in enumerate(reader):
        if len(row) != len(header):
            raise InputError("Ragged CSV row")
        pid, age, region, time = row[:4]
        key = (pid, region)
        age, time = number(age, "age"), number(time, "time")
        if key not in expected or age <= 0 or time < 0:
            raise InputError("Unexpected participant/region or invalid age/time")
        if (pid in ages and ages[pid] != age) or (pid, region, time) in seen:
            raise InputError("Contradictory age or duplicate participant/region/time")
        ages[pid] = age
        seen.add((pid, region, time))
        power = [number(v, "linear spectral power") for v in row[4:]]
        if min(power) < 0:
            raise InputError("Linear spectral power must be nonnegative")
        metadata.append(row[:4])
        powers.append(power)
        groups[key].append((time, index))
    if set(groups) != set(expected):
        raise InputError("Missing expected participant/region group")
    for key, entries in groups.items():
        entries.sort()
        count, age, start, end = expected[key]
        if (len(entries) != count or ages[key[0]] != age
                or entries[0][0] != start or entries[-1][0] != end):
            raise InputError("Declared group row count, age, or time bounds mismatch")
        if any(not math.isclose(b[0] - a[0], .25, rel_tol=0, abs_tol=1e-9)
               for a, b in zip(entries, entries[1:])):
            raise InputError("Missing or irregular original 0.25-second spectral window sequence")
    return header, metadata, np.asarray(powers, dtype=np.float64), groups


def paired_smoothing(metadata, powers, groups):
    """Run the exact source filter and its explicit grouped sensitivity together."""
    literal = uniform_filter(powers, size=(5, 3), mode="nearest")
    grouped = np.empty_like(literal)
    grouped_neighbors = {}
    for entries in groups.values():
        indices = [index for _, index in entries]
        grouped[indices] = uniform_filter(powers[indices], size=(5, 3), mode="nearest")
        for position, index in enumerate(indices):
            grouped_neighbors[index] = [indices[min(max(position + d, 0), len(indices) - 1)]
                                        for d in range(-2, 3)]
    if not np.isfinite(literal).all() or not np.isfinite(grouped).all():
        raise InputError("Nonfinite filter output; input magnitude exceeds numerical envelope")
    lineage = []
    nrows = len(metadata)
    for index, row in enumerate(metadata):
        neighbors = [min(max(index + d, 0), nrows - 1) for d in range(-2, 3)]
        foreign = [j for j in neighbors if (metadata[j][0], metadata[j][2]) != (row[0], row[2])]
        lineage.append({"row_index": index, "ID": row[0], "region": row[2],
                        "time_seconds": float(row[3]), "source_neighbor_rows": neighbors,
                        "grouped_neighbor_rows": grouped_neighbors[index],
                        "source_cross_boundary_rows": foreign})
    return literal, grouped, lineage


def csv_bytes(header, metadata, powers):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row, values in zip(metadata, powers):
        writer.writerow(row + [format(float(v), ".17g") for v in values])
    return buffer.getvalue().encode()


def prepare(data, packet):
    header, metadata, powers, groups = read_table(data, packet)
    literal, grouped, lineage = paired_smoothing(metadata, powers, groups)
    payloads = {"source_literal_smoothed.csv": csv_bytes(header, metadata, literal),
                "grouped_sensitivity_smoothed.csv": csv_bytes(header, metadata, grouped)}
    report = {
        "task_id": TASK_ID, "component": "paired_native_spectral_smoothing_v1",
        "assessment_kind": packet["assessment_kind"],
        "input_table_sha256": hashlib.sha256(data).hexdigest(),
        "source_commit": SOURCE_COMMIT, "source_fit_notebook_sha256": SOURCE_SHA256,
        "row_count": len(metadata), "participant_count": len(packet["expected_participants"]),
        "participant_region_count": len(groups), "frequency_count": 200,
        "input_unit": "participant/region/time spectral window; linear power of normalized bipolar traces",
        "time_step_seconds": .25, "filter_size_rows_frequency_bins": [5, 3],
        "boundary_mode": "nearest", "source_mode": "original CSV row order, across all groups",
        "sensitivity_mode": "time sorted within ID/region, restored to original CSV positions",
        "source_rows_touching_other_groups": sum(bool(r["source_cross_boundary_rows"]) for r in lineage),
        "lineage": lineage,
        "outputs": {name: {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
                    for name, blob in payloads.items()},
        "qualification": "generated-control-tested preprocessing component; original-finding reproduction and same-task superiority remain unqualified",
        "remaining_native_steps": ["58.5–61.5 Hz interpolation with author buffer=5",
                                   "custom FOOOF fitting and native parameter extraction"],
        "limits": ["Operator packet establishes declared coverage, not authentic source provenance.",
                   "Grouped arm changes source preprocessing and is a prospective sensitivity.",
                   "Neither arm resolves historical fitter revision or knee/alpha estimator discrepancies.",
                   "Faithful reproduction of the original descriptive findings is a valid benchmark outcome; maximizing those associations does not define source-paper superiority."]}
    return payloads, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectra", required=True, type=Path)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output_directory.exists():
            raise InputError("Output directory already exists")
        payloads, report = prepare(args.spectra.read_bytes(), json.loads(args.packet.read_text()))
        args.output_directory.mkdir(parents=True, exist_ok=False)
        for name, blob in payloads.items():
            (args.output_directory / name).write_bytes(blob)
        (args.output_directory / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (InputError, OSError, ValueError, TypeError, csv.Error) as exc:
        parser.exit(2, f"Input rejected: {exc}\n")


if __name__ == "__main__":
    main()
