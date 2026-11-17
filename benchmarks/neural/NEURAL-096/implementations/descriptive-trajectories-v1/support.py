"""Consistency and complete support for the declared NEURAL-096 observations.

This module reads no files and authenticates no recording. A matching source
declaration is not proof of that source. The caller must authenticate the packet
and bind its numerical arrays independently before scientific use.
"""
from collections import Counter
import math


SOURCE = {
    "sha256": "6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198",
    "bytes": 14119912,
    "url": "https://api.dandiarchive.org/api/assets/c90cbccc-31a5-4815-88e6-822d8c5ca68c/download/",
    "dandiset": "000130",
    "version": "0.241017.1448",
    "license": "CC-BY-4.0",
    "animal": "Haydn",
    "session": "20161211",
}
SPLITS = ("train", "val")
SOURCE_SPLITS = {"train": 748, "val": 258, "none": 154}
SELECTED_SPLITS = {"train": 150, "val": 54}
SUPPORT_AXES = ["observation_segment", "is_eye", "theta", "is_short"]
SUPPORT_LEVELS = {"is_eye": [False, True], "theta": [0, 180], "is_short": [False, True]}
ROW_FIELDS = (
    "source_row", "trial_id", "source_split", "is_eye", "is_short", "theta",
    "nominal_sample_interval_ms", "start_time", "stop_time", "ready_time",
    "set_time", "go_time", "observation_segment", "actual_sample_interval_seconds",
    "observed_production_interval_seconds",
)


class ContractError(ValueError):
    """The declared observation metadata is internally inconsistent."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def _integer(value, message):
    require(type(value) is int, message)
    return value


def _real(value, message):
    # The original preparer casts these fields to binary64 floats before JSON
    # serialization. Do not validate a rounded integer and return the original.
    require(type(value) is float and math.isfinite(value), message)
    return value


def _counts(shape):
    return [_counts(shape[1:]) for _ in range(shape[0])] if shape else 0


def _valid_count_tree(value, shape):
    if not shape:
        return type(value) is int and value >= 0
    return (type(value) is list and len(value) == shape[0]
            and all(_valid_count_tree(item, shape[1:]) for item in value))


def _validate_census(metadata):
    census = metadata.get("census")
    require(type(census) is list and len(census) == 1160, "complete 1160-row source census required")
    seen_ids, split_counts, selected = set(), Counter(), {}
    for position, row in enumerate(census):
        require(type(row) is dict, "invalid source census row")
        source_row = _integer(row.get("source_row"), "source row must be an integer")
        require(source_row == position, "source census order or coverage changed")
        trial_id = _integer(row.get("trial_id"), "source trial ID must be an integer")
        require(trial_id not in seen_ids, "duplicate source trial ID")
        seen_ids.add(trial_id)
        split = row.get("source_split")
        require(type(split) is str and split in SOURCE_SPLITS, "unknown source split")
        split_counts[split] += 1
        chosen = row.get("nominal_selected")
        require(type(chosen) is bool, "source selection flag must be boolean")
        reason = ("nominal_800_train_val" if chosen else
                  "outside_source_train_val" if split == "none" else "nominal_interval_not_800")
        require(row.get("selection_reason") == reason, "source selection reason disagrees")
        if chosen:
            require(split in SPLITS, "source 'none' row cannot be selected")
            selected[source_row] = (trial_id, split)
    require(dict(split_counts) == SOURCE_SPLITS, "source split census changed")
    require(len(selected) == 204, "source selection must contain all 204 declared rows")
    require(metadata.get("parent_source_split_counts") == SOURCE_SPLITS,
            "declared parent split counts disagree")
    return selected


def validate_metadata(metadata):
    """Return a new, bounded support projection without copying unknown fields.

    Indices address the original ascending-Set row order. Every selected trial is
    retained exactly once. A cell is supported only when both prior groups are
    observed in that split, segment, effector and direction. Missing cells are
    data-support facts, not zero neural effects or statistical conclusions.
    """
    require(type(metadata) is dict, "metadata must be a dictionary")
    require(metadata.get("schema") == "neural096_full_set_go_observations_v1"
            and metadata.get("status") == "source_metadata_supported"
            and metadata.get("task_id") == "NEURAL-096", "unexpected observation schema or status")
    require(type(metadata.get("source")) is dict and metadata["source"] == SOURCE,
            "declared source identity changed")
    require(type(metadata.get("selected_trial_count")) is int
            and metadata["selected_trial_count"] == 204, "declared trial count changed")
    require(metadata.get("selected_split_counts") == SELECTED_SPLITS,
            "declared selected split counts changed")
    selected = _validate_census(metadata)

    unit_ids = metadata.get("unit_ids")
    require(type(unit_ids) is list and len(unit_ids) == 54
            and all(type(item) is int for item in unit_ids)
            and len(set(unit_ids)) == 54, "all 54 distinct integer unit IDs required")
    flags = metadata.get("nlb_heldout_unit_flags")
    require(type(flags) is list and len(flags) == 54
            and all(type(item) is bool for item in flags) and sum(flags) == 14,
            "complete original held-out-unit flags required")
    segments = metadata.get("observation_segments_seconds")
    require(type(segments) is list and len(segments) == 6, "six observation segments required")
    clean_segments = []
    for item in segments:
        require(type(item) in (list, tuple) and len(item) == 2, "invalid observation segment")
        left = _real(item[0], "nonfinite observation segment")
        right = _real(item[1], "nonfinite observation segment")
        require(left < right and (not clean_segments or clean_segments[-1][1] < left),
                "observation segments must be ordered disjoint unions")
        clean_segments.append([left, right])

    representation = metadata.get("representation")
    require(type(representation) is dict
            and type(representation.get("phase_bins")) is int
            and representation["phase_bins"] == 20
            and representation.get("interval") == "[native set_time, native go_time)"
            and representation.get("count_units") == "spikes per source unit per phase bin"
            and representation.get("exposure_units") == "seconds per phase bin"
            and representation.get("no_fitted_basis") is True
            and representation.get("no_smoothing") is True,
            "declared native count/exposure representation changed")

    rows = metadata.get("trials")
    require(type(rows) is list and len(rows) == 204, "complete 204-trial roster required")
    clean_rows, seen_rows, seen_ids, split_counts = [], set(), set(), Counter()
    counts = _counts((2, 6, 2, 2, 2))
    combined = _counts((6, 2, 2, 2))
    groups = {}
    previous_go = None
    for index, row in enumerate(rows):
        require(type(row) is dict and all(field in row for field in ROW_FIELDS),
                "required original trial fields missing")
        source_row = _integer(row["source_row"], "trial source row must be an integer")
        trial_id = _integer(row["trial_id"], "trial ID must be an integer")
        split = row["source_split"]
        require(type(split) is str and split in SPLITS, "unknown selected source split")
        require(source_row not in seen_rows and trial_id not in seen_ids, "duplicate selected trial")
        require(source_row in selected and selected[source_row] == (trial_id, split),
                "trial does not match its selected source census row")
        seen_rows.add(source_row)
        seen_ids.add(trial_id)
        split_counts[split] += 1
        require(type(row["is_eye"]) is bool and type(row["is_short"]) is bool,
                "prior and effector flags must be boolean")
        theta = _real(row["theta"], "direction must be finite and numeric")
        require(theta in (0.0, 180.0), "unknown response direction")
        nominal = _real(row["nominal_sample_interval_ms"], "invalid nominal interval")
        require(nominal == 800.0, "nominal interval must be 800 ms")
        event = {name: _real(row[name], "nonfinite or invalid native event")
                 for name in ("start_time", "ready_time", "set_time", "go_time", "stop_time")}
        require(event["start_time"] <= event["ready_time"] < event["set_time"]
                < event["go_time"] <= event["stop_time"], "native trial event order is invalid")
        require(previous_go is None or previous_go <= event["set_time"],
                "trial order changed or complete intervals overlap")
        previous_go = event["go_time"]
        segment = _integer(row["observation_segment"], "observation segment must be an integer")
        require(0 <= segment < 6, "unknown observation segment")
        left, right = clean_segments[segment]
        require(left <= event["set_time"] and event["go_time"] <= right,
                "complete Set-Go interval lacks declared observation support")
        actual = _real(row["actual_sample_interval_seconds"], "invalid actual sampled interval")
        produced = _real(row["observed_production_interval_seconds"], "invalid observed production interval")
        require(actual == event["set_time"] - event["ready_time"]
                and produced == event["go_time"] - event["set_time"],
                "native duration declarations disagree with events")
        s, e, d, p = SPLITS.index(split), int(row["is_eye"]), int(theta == 180.0), int(row["is_short"])
        counts[s][segment][e][d][p] += 1
        combined[segment][e][d][p] += 1
        groups.setdefault((s, segment, e, d, p), []).append(index)
        clean = {field: row[field] for field in ROW_FIELDS}
        clean_rows.append(clean)
    require(seen_rows == set(selected) and dict(split_counts) == SELECTED_SPLITS,
            "selected source membership or split counts changed")

    zero_cells = [[g, e, d, p] for g in range(6) for e in range(2)
                  for d in range(2) for p in range(2) if combined[g][e][d][p] == 0]
    old_support = metadata.get("support")
    require(type(old_support) is dict
            and old_support.get("axes") == SUPPORT_AXES
            and old_support.get("levels") == SUPPORT_LEVELS
            and _valid_count_tree(old_support.get("counts"), (6, 2, 2, 2))
            and old_support["counts"] == combined
            and old_support.get("zero_cells") == zero_cells
            and old_support.get("all_cells_present") is (not zero_cells),
            "declared original support does not match the complete trial roster")

    cells = []
    for s, split in enumerate(SPLITS):
        for segment in range(6):
            for e in range(2):
                for d in range(2):
                    long = list(groups.get((s, segment, e, d, 0), ()))
                    short = list(groups.get((s, segment, e, d, 1), ()))
                    missing = [name for name, indices in (("long", long), ("short", short)) if not indices]
                    cells.append({"cell_id": f"{split}-segment{segment}-eye{e}-direction{d * 180}",
                                  "source_split": split, "observation_segment": segment,
                                  "is_eye": bool(e), "theta": d * 180,
                                  "long_trial_indices": long, "short_trial_indices": short,
                                  "n_long": len(long), "n_short": len(short),
                                  "supported": not missing, "missing_priors": missing})
    split_zero_cells = [[s, g, e, d, p] for s in range(2) for g in range(6)
                        for e in range(2) for d in range(2) for p in range(2)
                        if counts[s][g][e][d][p] == 0]
    return {"schema": "neural096_descriptive_support_v1", "task_id": "NEURAL-096",
            "source_metadata_consistent": True, "source_authenticated": False,
            "source": dict(SOURCE), "trials": clean_rows, "trial_ids": [r["trial_id"] for r in clean_rows],
            "unit_ids": list(unit_ids), "nlb_heldout_unit_flags": list(flags),
            "observation_segments_seconds": clean_segments, "split_order": list(SPLITS),
            "split_counts": counts, "combined_counts": combined,
            "combined_zero_cells": zero_cells, "split_zero_cells": split_zero_cells,
            "cells": cells, "phase_bins": 20,
            "uncertainty_status": "not_qualified",
            "segment_role": "Recording observation support, not verified randomized assignment blocks."}
