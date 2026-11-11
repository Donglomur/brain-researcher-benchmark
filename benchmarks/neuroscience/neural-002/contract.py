"""Original source contract; no authentic data are bundled or read at import."""
import math

TASK_ID = "NEURAL-002"
SOURCE_COMMIT = "d2e09f610d267b8b3679997f8bc4e52fe6ca402a"
PEOPLE = tuple(f"sub-{n:02d}" for n in range(1, 33))
TASKS = ("dotcount", "firstlast")
SPEEDS = ("15CPM", "30CPM", "40CPM")
CELLS = tuple(f"{task}/{speed}" for task in TASKS for speed in SPEEDS)
RATE, CHANNELS, SAMPLES, CLASSES = 600, 62, 301, 26
NOMINAL_TRIALS = 9984
GATES = (
    "authentic_exact_source_intake", "all32_identity_and_complete_class_coverage",
    "raw_marker_and_channel_schema", "known_bad_channel_policy",
    "source_target_privacy_and_contamination", "matched_resource_budget",
    "native_reference_and_null_controls", "independent_scoring_replication",
    "qualified_process_isolation", "scientific_interpretation_review",
    "prefix_identifiability_and_order_controls",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, name)
    return value


def finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value), name)
    return float(value)


def vocabulary(cell):
    require(cell in CELLS, "unknown task/speed cell")
    offset = SPEEDS.index(cell.split("/")[1]) * CLASSES
    # Opaque raw trigger IDs, not a character-equivalence assertion.
    return tuple(str(n) for n in range(offset + 1, offset + CLASSES + 1))


def scope():
    return {"participants": list(PEOPLE), "cells": list(CELLS),
            "nominal_trials": NOMINAL_TRIALS, "class_count_per_cell": CLASSES,
            "repetitions_per_class": 2, "shape": [CHANNELS, SAMPLES],
            "sampling_hz": RATE, "window": "marker 0 through 500 ms inclusive",
            "benchmark_count": 1, "outer_folds": 32,
            "endpoint": "retrospective stimulus-ID decoding, not comprehension"}
