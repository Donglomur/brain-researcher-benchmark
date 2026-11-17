"""Read-only admission and clock audit of the pinned native optogenetic release.

This is independent of the normalized scorer and the native delivery adapter.
It exports provenance summaries only, never trial values or endpoint targets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path

DATA_SHA256 = "9d2be90908a05684dff9871697f5c37bb4f93522af67bf2625219f12cb4fd19c"
DATA_BYTES = 9351260
SOURCE_REVISION = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
SESSIONS = {
    ("cfaVG1", "20210304_153342"): 264,
    ("cfaVG1", "20210305_153354"): 400,
    ("cfaVG1", "20210311_153800"): 431,
    ("cfaVG1", "20210312_150224"): 415,
    ("cfaVG4", "20210601_152047"): 476,
    ("cfaVG4", "20210602_145241"): 377,
    ("cfaVG4", "20210603_144703"): 521,
    ("cfaVG4", "20210604_134012"): 420,
}
FIELDS = (
    "animalID", "date", "trialNumber", "restThreshR", "LR", "restTouchR",
    "cycleTimes", "waterTime", "optoTrial", "optoProblem", "wrongGrabFirst",
    "success", "liftTimeC", "grabTimeC", "liftRT", "grabRT",
)
TIMING_FIELDS = ("waterTime", "liftTimeC", "grabTimeC", "liftRT", "grabRT")


class AuditError(ValueError):
    """The pinned population or native clock lineage could not be established."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def timing(value, field):
    # simplify_cells produces Python scalar values on this MAT-v5 schema.
    require(type(value) in (int, float), f"{field}: real scalar required")
    require(not math.isinf(value), f"{field}: infinity is not a missing event")
    return float(value)


def audit_records(rows, expected_sessions):
    """Check loaded native records; this alone does not authenticate a MAT file.

    expected_sessions is explicit so generated controls can test failures with
    small populations. Only audit_native() attaches the authentic input pin.
    No filtering, event locking, subtraction or rescaling changes these rows.
    """
    require(type(rows) is list and rows, "nonempty native record list required")
    identities, population = set(), Counter()
    missing = Counter({field: 0 for field in TIMING_FIELDS})
    clocks = {event: {"reaction_time_field": rt, "finite_identity_rows": 0,
                       "missing_event_rows": 0, "nonzero_water_time_rows": 0,
                       "maximum_absolute_identity_residual_ms": 0.0}
              for event, rt in (("liftTimeC", "liftRT"), ("grabTimeC", "grabRT"))}
    for row in rows:
        require(type(row) is dict and set(row) == set(FIELDS), "native field inventory mismatch")
        animal, session, trial = row["animalID"], row["date"], row["trialNumber"]
        require(type(animal) is str and type(session) is str, "native identity strings required")
        require(type(trial) is int and trial > 0, "native trialNumber must be a positive integer")
        require((animal, session) in expected_sessions, "unexpected native mouse/session timestamp")
        key = (animal, session, trial)
        require(key not in identities, "duplicate native identity")
        identities.add(key)
        population[(animal, session)] += 1
        for field in ("success", "optoProblem", "optoTrial", "wrongGrabFirst"):
            require(type(row[field]) in (int, bool) and row[field] in (0, 1), f"{field}: binary required")
        values = {field: timing(row[field], field) for field in TIMING_FIELDS}
        for field, value in values.items():
            missing[field] += math.isnan(value)
        for event, check in clocks.items():
            absolute, reaction = values[event], values[check["reaction_time_field"]]
            require(math.isnan(absolute) == math.isnan(reaction), f"{event}: event/RT missingness mismatch")
            if math.isnan(absolute):
                check["missing_event_rows"] += 1
                continue
            water = values["waterTime"]
            require(math.isfinite(water), f"{event}: finite event requires finite waterTime")
            residual = absolute - water - reaction
            require(math.isfinite(residual), f"{event}: clock identity overflow")
            # Exact equality is an observed property of this frozen release,
            # not a tolerance imposed on a newly collected timing experiment.
            require(residual == 0.0, f"{event}: native event minus waterTime does not equal RT")
            check["finite_identity_rows"] += 1
            check["nonzero_water_time_rows"] += water != 0.0
            check["maximum_absolute_identity_residual_ms"] = max(
                check["maximum_absolute_identity_residual_ms"], abs(residual))
    require(dict(population) == expected_sessions, "complete native session population required")
    expected_keys = {(animal, session, trial)
                     for (animal, session), count in expected_sessions.items()
                     for trial in range(1, count + 1)}
    require(identities == expected_keys, "complete native trial-number inventory required")
    identity_bytes = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
    return {
        "record_count": len(rows), "unique_identity_count": len(identities),
        "animal_counts": dict(sorted(Counter(k[0] for k in identities).items())),
        "sessions": [{"mouse": a, "session": s, "trials": count,
                      "trial_number_minimum": 1, "trial_number_maximum": count}
                     for (a, s), count in sorted(population.items())],
        "identity_fields": ["animalID", "date", "trialNumber"],
        "identity_serialization": "UTF-8 JSON sorted identity tuples; separators comma/colon; no newline",
        "identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
        "missing_native_event_counts": dict(missing), "clock_identities": clocks,
        "native_event_unit": "milliseconds",
        "native_clock_origin": "unspecified_acquisition_origin",
        "source_plot_transform": "grabTimeC / 1000",
        "source_plot_zero_label": "cue",
        "water_relative_transform": "(grabTimeC - waterTime) / 1000 == grabRT / 1000",
        "cue_clock_interpretation_validated": False,
        "clock_discrepancy_status": "unresolved_source_plot_vs_native_event_origin",
        "event_values_changed": False, "trial_values_exported": False,
        "endpoint_targets_exported": False,
    }


def audit_native(path):
    """Authenticate and inspect one bounded MAT-v5 object, with no downloads."""
    path = Path(path)
    require(path.is_file() and path.stat().st_size == DATA_BYTES, "native data byte count mismatch")
    # Parse the same bytes that were authenticated, avoiding a second file read.
    with path.open("rb") as stream:
        raw = stream.read(DATA_BYTES + 1)
    require(len(raw) == DATA_BYTES and hashlib.sha256(raw).hexdigest() == DATA_SHA256,
            "native data SHA256 mismatch")
    try:
        import scipy
        from scipy.io import loadmat, whosmat
    except ImportError as error:
        raise AuditError("SciPy is required; this audit does not install dependencies") from error
    inventory = whosmat(io.BytesIO(raw))
    require(inventory == [("optoData", (1, 3304), "struct")], "native MAT variable/shape mismatch")
    native = loadmat(io.BytesIO(raw), simplify_cells=True, verify_compressed_data_integrity=True)
    result = audit_records(native["optoData"], SESSIONS)
    result.update(
        schema="opto-native-clock-admission-v1", task_id="PAPER-FIND-REP-003",
        input_bytes=len(raw), input_sha256=DATA_SHA256,
        source_revision=SOURCE_REVISION,
        clock_source_path="preproc/loadEventTimes.m",
        clock_source_sha256="a4e32371dd857c2e80adb0a6d9efae1f3dca04489847e1ed32e5cf8b1ba9e215",
        native_variable="optoData", native_shape=[1, 3304], native_fields=list(FIELDS),
        scipy_version=scipy.__version__, complete_pinned_population_verified=True,
        scientific_qualification=False, full_contract_complete=False,
        source_numeric_endpoint_changed=False, solver_trials=0,
        scope="Native population and event-clock admission; no endpoint result or solver evaluation",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mat")
    parser.add_argument("--output", required=True, help="New admission receipt; never a normalized target artifact")
    args = parser.parse_args()
    result = audit_native(args.mat)
    # Preserve any previous receipt and make overwrite attempts explicit.
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
