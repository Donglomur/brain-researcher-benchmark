"""Trusted-owner reduction of the original ephys decoder's complete row outputs.

No neural data, fitting, baseline authenticity, candidate isolation or inferential
paper-win rule is supplied here. Owner index artifacts contain target information.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import fmean

TASK_ID = "PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113"
SOURCE_COMMIT = "8c62c1cfe91644e3030a35d3ebb45e3bee94c3c8"
CONTEXTS = ("LS", "SL", "SS")
SESSIONS = {
    "SL_only_shaping": (
        "M2_2202025_g0", "M2_2212025_g0", "M1_2182025_g0", "M1_2202025_g0",
        "M4_2252025_g0", "M4_2272025_g1", "M5_2272025_g0", "M5_3012025_g0",
    ),
    "standard_shaping": (
        "AC01_01292025_g0", "j2_05092024_g0", "AB02_08272024_g0",
        "AB02_08282024_g0", "AB04_09092024_g0",
    ),
}
INDEX_FIELDS = ("trial", "type", "result", "time_bin")


class ScoreError(ValueError):
    """An artifact does not preserve the complete declared original panel."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ScoreError("missing or unrecognized fields")


def _sha(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ScoreError("expected lowercase SHA256")
    return value


def _scalar(value):
    if type(value) not in (str, int, float) or (isinstance(value, str) and not value):
        raise ScoreError("trial/result must be nonempty strings or finite numbers")
    if isinstance(value, float) and not math.isfinite(value):
        raise ScoreError("nonfinite trial/result")
    return value


def _bin(value):
    if type(value) is not int or not 0 <= value < 40:
        raise ScoreError("time classes must be integer bins 0..39; booleans are invalid")
    return value


def circular_error(predicted, actual):
    """The consumer minimizes squared distance to t, t+20 and t-20 seconds."""
    d = abs(_bin(predicted) - _bin(actual))
    return min(d, 40 - d) ** 2 / 4


def _row_key(row):
    if row["type"] not in CONTEXTS:
        raise ScoreError("source context outside LS/SL/SS; do not silently filter")
    return (_scalar(row["trial"]), row["type"], _scalar(row["result"]), _bin(row["time_bin"]))


def _session_map(sessions):
    if not isinstance(sessions, list) or len(sessions) != 13:
        raise ScoreError("all thirteen original Figure 6f sessions are required")
    by_id = {}
    for session in sessions:
        if not isinstance(session, dict) or not isinstance(session.get("session_id"), str):
            raise ScoreError("session_id must be a string")
        sid = session["session_id"]
        if sid in by_id:
            raise ScoreError("duplicate session")
        by_id[sid] = session
    if set(by_id) != {sid for group in SESSIONS.values() for sid in group}:
        raise ScoreError("missing or unexpected original session")
    return by_id


def validate_index(owner_index):
    """Validate native Y.index exports without inventing zero-event trials.

    First occurrence in the supplied Y.index defines y.index.unique('trial').
    Native preparation must authenticate this index and the feature-byte digest.
    """
    _fields(owner_index, ("schema", "source_commit", "evidence_kind", "sessions"))
    if owner_index["schema"] != "structured-original-index/v1" or owner_index["source_commit"] != SOURCE_COMMIT:
        raise ScoreError("unsupported original index/source revision")
    if owner_index["evidence_kind"] not in ("generated_engineering_control", "owner_source_index"):
        raise ScoreError("explicit index evidence kind required")
    sessions = _session_map(owner_index["sessions"])
    validated = {}
    for sid, session in sessions.items():
        _fields(session, ("session_id", "feature_sha256", "rows"))
        _sha(session["feature_sha256"])
        if not isinstance(session["rows"], list) or not session["rows"]:
            raise ScoreError("nonempty original feature index required")
        keys, trials, trial_contexts, groups = set(), {}, defaultdict(set), defaultdict(set)
        for row in session["rows"]:
            _fields(row, INDEX_FIELDS)
            key = _row_key(row)
            if key in keys:
                raise ScoreError("duplicate source index row")
            keys.add(key)
            trials.setdefault(key[0], len(trials))
            trial_contexts[key[0]].add(key[1])
            groups[key[:3]].add(key[3])
        if len(trials) < 10:
            raise ScoreError("original ten-fold decoder requires nonempty test folds")
        if any(bins != set(range(40)) for bins in groups.values()):
            raise ScoreError("source trial/type/result group must contain all forty bins")
        if {key[1] for key in keys} != set(CONTEXTS):
            raise ScoreError("complete three-context source panel required")
        quotient, remainder = divmod(len(trials), 10)
        trial_order, folds, start = list(trials), {}, 0
        for fold in range(10):
            stop = start + quotient + (fold < remainder)
            for trial in trial_order[start:stop]:
                folds[trial] = fold
            training_contexts = {context for trial in trial_order[:start] + trial_order[stop:]
                                 for context in trial_contexts[trial]}
            if training_contexts != set(CONTEXTS):
                raise ScoreError("a source training fold lacks a required decoder context")
            start = stop
        # A query fold need not contain every context. This is not the old LOOM plan.
        validated[sid] = {"keys": keys, "folds": folds, "trial_count": len(trials)}
    return validated


def score(owner_index, predictions):
    """Compute original row-weighted session/context MSE, with no scalar win."""
    index = validate_index(owner_index)
    _fields(predictions, ("schema", "owner_index_sha256", "run_receipt_sha256", "sessions"))
    if predictions["schema"] != "structured-original-predictions/v1":
        raise ScoreError("unsupported predictions schema")
    if _sha(predictions["owner_index_sha256"]) != digest(owner_index):
        raise ScoreError("predictions bound to a different original feature/index universe")
    _sha(predictions["run_receipt_sha256"])
    sessions = _session_map(predictions["sessions"])
    summaries, tables = [], {}
    for group, session_ids in SESSIONS.items():
        for sid in session_ids:
            session = sessions[sid]
            _fields(session, ("session_id", "rows"))
            if not isinstance(session["rows"], list):
                raise ScoreError("prediction rows must be a list")
            seen, errors, optional_all = set(), defaultdict(list), defaultdict(list)
            all_present = None
            for row in session["rows"]:
                _fields(row, INDEX_FIELDS + ("split", "predictions"))
                key = _row_key(row)
                if key not in index[sid]["keys"] or key in seen:
                    raise ScoreError("unexpected or duplicate prediction row")
                seen.add(key)
                if type(row["split"]) is not int or row["split"] != index[sid]["folds"][key[0]]:
                    raise ScoreError("prediction split differs from source ordered ten folds")
                values = row["predictions"]
                _fields(values, CONTEXTS, ("all",))
                has_all = "all" in values
                if all_present is not None and has_all != all_present:
                    raise ScoreError("optional all-context decoder must cover the complete session")
                all_present = has_all
                for source in CONTEXTS:
                    errors[(source, key[1])].append(circular_error(values[source], key[3]))
                if has_all:
                    optional_all[key[1]].append(circular_error(values["all"], key[3]))
            if seen != index[sid]["keys"]:
                raise ScoreError("missing original query rows")
            matrix = {source: {test: fmean(errors[source, test]) for test in CONTEXTS} for source in CONTEXTS}
            tables[sid] = matrix
            within = fmean(matrix[context][context] for context in CONTEXTS)
            across = fmean(matrix[source][test] for source in CONTEXTS for test in CONTEXTS if source != test)
            summary = {"session_id": sid, "shaping_group": group,
                       "query_row_count": len(seen), "trial_count": index[sid]["trial_count"],
                       "context_row_counts": {test: len(errors["LS", test]) for test in CONTEXTS},
                       "within_mse_seconds2": within, "across_mse_seconds2": across,
                       "signed_across_minus_within_seconds2": across - within,
                       "absolute_biological_gap_seconds2": abs(across - within)}
            if all_present:
                summary["all_context_decoder_diagnostic_seconds2"] = {test: fmean(optional_all[test]) for test in CONTEXTS}
            summaries.append(summary)
    return {"schema": "structured-original-score/v1", "task_id": TASK_ID,
            "owner_index_sha256": digest(owner_index), "predictions_sha256": digest(predictions),
            "evidence_kind": owner_index["evidence_kind"], "units": "seconds_squared",
            "endpoint": "original_session_by_source_by_test_context_error_vector",
            "context_pair_mse_seconds2": tables, "sessions": summaries,
            "qualification": "row_scoring_component_only",
            "paper_win": None, "source_native_parity_established": False,
            "limits": ["source provenance and complete native input support need independent authentication",
                       "run receipts are bindings, not proof of fresh source LDA or compliant candidate fitting",
                       "mouse-level uncertainty, meaningful effect and original-score decision rule remain unresolved",
                       "biological gaps and optional all-context diagnostics are not optimization targets"]}


def compare(owner_index, candidate, baseline):
    """Retain every paired original error cell without inventing a win rule."""
    c, b = score(owner_index, candidate), score(owner_index, baseline)
    deltas = {sid: {source: {test: b["context_pair_mse_seconds2"][sid][source][test] -
                                      c["context_pair_mse_seconds2"][sid][source][test]
                            for test in CONTEXTS} for source in CONTEXTS}
              for sid in c["context_pair_mse_seconds2"]}
    return {"schema": "structured-original-comparison/v1", "candidate": c, "baseline": b,
            "baseline_minus_candidate_seconds2": deltas, "paper_win": None,
            "interpretation": "positive cells mean lower candidate error; no aggregate superiority or uncertainty claim"}


def _native_scalar(value):
    # NumPy scalar conversion is needed for pandas index exports, without a dependency here.
    return value.item() if hasattr(value, "item") else value


def export_index_rows(native_index):
    """Export a freshly prepared native Y.index; never reconstruct it from predictions."""
    if list(native_index.names) != list(INDEX_FIELDS):
        raise ScoreError("native feature index must be trial/type/result/time_bin")
    return [{field: _native_scalar(value) for field, value in zip(INDEX_FIELDS, values)}
            for values in native_index.tolist()]


def export_prediction_rows(native_frame):
    """Convert original model_0 frames, preserving native split/index identities."""
    fields = ("split",) + INDEX_FIELDS
    if list(native_frame.index.names) != list(fields):
        raise ScoreError("native predictions need split/trial/type/result/time_bin index")
    columns = list(native_frame.columns)
    if len(set(columns)) != len(columns) or set(columns) not in (set(CONTEXTS), set(CONTEXTS) | {"all"}):
        raise ScoreError("native predictions need exactly LS/SL/SS and optional all columns")
    return [dict(zip(fields, map(_native_scalar, key)),
                 predictions={column: _native_scalar(value) for column, value in zip(columns, values)})
            for key, values in zip(native_frame.index.tolist(), native_frame.itertuples(index=False, name=None))]


def load(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ScoreError("duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise ScoreError("nonfinite JSON constant: " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner_index")
    parser.add_argument("predictions")
    parser.add_argument("output")
    parser.add_argument("--baseline")
    args = parser.parse_args(argv)
    owner_index, predictions = load(args.owner_index), load(args.predictions)
    result = compare(owner_index, predictions, load(args.baseline)) if args.baseline else score(owner_index, predictions)
    # Owner-only, exclusive output. This is not a candidate runtime security boundary.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
