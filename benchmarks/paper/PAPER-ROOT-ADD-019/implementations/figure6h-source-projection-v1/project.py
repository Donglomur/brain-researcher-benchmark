"""Audit and project an operator-owned neutral export of Figure 6h inputs.

No MAT reader, percentile calculation, fitting, fold creation or source admission.
All return values are operator-private; this API is not a participant boundary.
"""
from functools import lru_cache
import hashlib
import importlib.util
import math
from pathlib import Path

TASK = "PAPER-ROOT-ADD-019"
SOURCE_SHA256 = "c963c8b204fee99ca40668a4651e90e0beab44ec4e986b9bb184e8cf93ff3f42"
LABEL_AUDIT_SHA256 = "8a325fb671bd86f15f0e1c949483a27a58d98a6c277adc3fbc37114baffa43c0"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, keys, where):
    need(isinstance(value, dict) and set(value) == set(keys), where + ": fields differ")


def pin(value, where):
    need(isinstance(value, str) and len(value) == 64 and
         all(c in "0123456789abcdef" for c in value), where + ": invalid SHA256")


def ids(value, where):
    need(isinstance(value, list) and value and
         all(isinstance(x, str) and x for x in value), where + ": nonempty IDs required")
    need(len(value) == len(set(value)), where + ": duplicate IDs")


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


@lru_cache(maxsize=1)
def label_audit_module():
    """Reuse the reviewed literal-label audit rather than repair labels here."""
    source = Path(__file__).resolve().parents[1] / "figure6h-oof-score-v1" / "score.py"
    body = source.read_bytes()
    need(hashlib.sha256(body).hexdigest() == LABEL_AUDIT_SHA256,
         "existing label audit changed; review the dependency before adoption")
    spec = importlib.util.spec_from_file_location("ach_fig6h_projection_label_audit", source)
    module = importlib.util.module_from_spec(spec)
    # Execute the bytes just authenticated, avoiding a second file read.
    exec(compile(body, str(source), "exec"), module.__dict__)
    return module


def project_session(record):
    """Preserve source selection and column-major flattening for one session.

    Input masks/labels must be captured from the specified original source;
    equality below is consistency, not proof of such an execution. Grid/row
    mismatches are refused, never resampled/reordered. Original filtering and
    quartile ambiguities are not adjudicated by this projection.
    """
    exact(record, ["schema", "task", "source_code_sha256", "source_export_sha256",
                   "session_id", "rat_id", "source_session_index_one_based",
                   "trial_ids", "units", "selection"], "session")
    need(record["schema"] == "ach_fig6h_projection_input_v1" and record["task"] == TASK,
         "wrong session schema/task")
    need(record["source_code_sha256"] == SOURCE_SHA256, "wrong original source code")
    pin(record["source_export_sha256"], "source export")
    for key in ("session_id", "rat_id"):
        need(isinstance(record[key], str) and record[key], key + ": nonempty string required")
    index = record["source_session_index_one_based"]
    need(type(index) is int and index >= 1, "source session index must be a positive integer")
    trial_ids = record["trial_ids"]
    ids(trial_ids, "source trial IDs")
    n = len(trial_ids)
    selected = record["selection"]
    exact(selected, ["is_fast", "is_slow", "trial_indices_one_based", "literal_labels"],
          "captured selection")
    fast, slow = selected["is_fast"], selected["is_slow"]
    need(isinstance(fast, list) and isinstance(slow, list) and len(fast) == n and len(slow) == n
         and all(type(x) is bool for x in fast + slow), "full source boolean masks required")
    audit = label_audit_module().audit_source_labels(fast, slow)
    retained = selected["trial_indices_one_based"]
    need(isinstance(retained, list) and retained and all(type(x) is int for x in retained)
         and retained == audit["trial_indices_one_based"],
         "retained trials must equal ascending original mask union")
    labels = selected["literal_labels"]
    need(isinstance(labels, list) and all(type(x) is int and x in (0, 1) for x in labels)
         and labels == audit["literal_native_labels"],
         "captured labels differ from literal source; corrected branches require separate admission")

    units = record["units"]
    need(isinstance(units, list) and len(units) >= 5, "source eligibility requires at least five units")
    unit_ids, clocks = [], []
    for unit in units:
        exact(unit, ["unit_id", "trial_ids", "son_time_s", "son_values"], "unit")
        unit_ids.append(unit["unit_id"])
        need(unit["trial_ids"] == trial_ids, "unit trial identity/order mismatch")
        clock = unit["son_time_s"]
        need(isinstance(clock, list) and len(clock) >= 2 and all(numeric(t) for t in clock),
             "finite native SON time grid required")
        need(all(b > a for a, b in zip(clock, clock[1:])), "SON grid must strictly increase")
        clocks.append(clock)
        values = unit["son_values"]
        need(isinstance(values, list) and len(values) == n and
             all(isinstance(row, list) and len(row) == len(clock) and
                 all(type(x) in (int, float) for x in row) for row in values),
             "complete numeric trial-by-native-time geometry required; rows cannot be dropped")
    ids(unit_ids, "source unit IDs")
    # Source chooses indices using SU{sess}{1}.xvec.SON for every unit.
    clock = clocks[0]
    need(all(other == clock for other in clocks),
         "source uses first-unit indices; unequal unit time grids require source adjudication")
    first = min(range(len(clock)), key=lambda i: abs(clock[i] - 0.0))
    last = min(range(len(clock)), key=lambda i: abs(clock[i] - 0.5))
    need(first <= last, "reversed source window")
    need(all(numeric(unit["son_values"][trial - 1][t])
             for trial in retained for t in range(first, last + 1) for unit in units),
         "selected source predictor is nonfinite; native missing-row policy remains unresolved")
    # MATLAB X(trial, unit, time), reshape(X, n_trials, []) varies units
    # inside time. Ordinary row-major flattening silently changes predictors.
    columns = [{"unit_id": unit_id, "native_time_index_one_based": t + 1,
                "time_s": clock[t]}
               for t in range(first, last + 1) for unit_id in unit_ids]
    matrix = [[unit["son_values"][trial - 1][t]
               for t in range(first, last + 1) for unit in units]
              for trial in retained]
    return {
        "schema": "ach_fig6h_projection_session_v1", "task": TASK,
        "session_id": record["session_id"], "rat_id": record["rat_id"],
        "source_session_index_one_based": index,
        "source_code_sha256": SOURCE_SHA256,
        "source_export_sha256": record["source_export_sha256"],
        "trial_ids": [trial_ids[i - 1] for i in retained], "unit_ids": unit_ids,
        "window_indices_one_based_inclusive": [first + 1, last + 1],
        "window_endpoint_seconds": [clock[first], clock[last]],
        "feature_columns": columns, "trial_by_predictor_matrix": matrix,
        "source_label_audit": audit,
        "two_literal_classes_present": set(labels) == {0, 1},
        "source_admission_established": False,
        "interpretation": "Operator-only source input projection; no fitting, folds, cohort authentication or scientific result.",
    }


def project_complete_panel(panel):
    """Project the declared full18/eight panel, without authenticating its IDs."""
    exact(panel, ["schema", "task", "source_cohort_manifest_sha256", "sessions"], "panel")
    need(panel["schema"] == "ach_fig6h_projection_panel_input_v1" and panel["task"] == TASK,
         "wrong panel schema/task")
    pin(panel["source_cohort_manifest_sha256"], "cohort manifest")
    sessions = panel["sessions"]
    need(isinstance(sessions, list) and len(sessions) == 18, "complete source18-session panel required")
    projected = [project_session(row) for row in sessions]
    ids([row["session_id"] for row in projected], "session IDs")
    source_indices = [row["source_session_index_one_based"] for row in projected]
    need(source_indices == sorted(set(source_indices)), "source session order/uniqueness changed")
    need(len({row["rat_id"] for row in projected}) == 8, "original eight-rat scope required")
    return {"schema": "ach_fig6h_projection_panel_v1", "task": TASK,
            "source_cohort_manifest_sha256": panel["source_cohort_manifest_sha256"],
            "sessions": projected, "source_admission_established": False,
            "readiness_promoted": False,
            "limits": ["Counts/hash consistency do not authenticate original observations or cohort.",
                       "Captured quartile masks/labels require an independently verified native source export.",
                       "No original CV realization, prediction, example trace or numerical paper score is created.",
                       "The entire return object is operator private, not a participant payload."]}
