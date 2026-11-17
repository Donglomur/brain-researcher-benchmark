"""Score the recovered Fig. 1 notebook branch; never fit or import author code.

Operator reference JSON contains positions. Candidate JSON contains predictions
only. This is a software component, not native preparation or a paper win rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

MICE = ("478", "481", "483", "485")
CONDITIONS = ("L", "R", "L from R", "R from L",
              "L from R Shuffled", "R from L Shuffled")
METRICS = ("source_modal_filtered_rmse", "full_bin_rmse",
           "author_support_rmse")


class ContractError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ContractError(message)


def keys(value, expected, label):
    need(isinstance(value, dict) and set(value) == set(expected), label + " fields")


def vector(values, label):
    need(isinstance(values, list) and len(values) > 0, label + " must be nonempty")
    need(all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
             for v in values), label + " must be finite normalized positions in [0,1]")
    return np.asarray(values, dtype=float)


def source_split(groups):
    """GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42) indices.

    Match its sorted unique groups, ceil group count, legacy RandomState
    permutation, and source-order returned sample indices. Do not split frames.
    """
    need(isinstance(groups, list) and len(groups) > 1, "trial groups required")
    strings = all(type(g) is str and bool(g) for g in groups)
    numbers = all(type(g) in (int, float) and math.isfinite(g) for g in groups)
    need(strings or numbers, "trial groups must be homogeneous finite scalars")
    unique, inverse = np.unique(groups, return_inverse=True)
    need(len(unique) >= 2, "at least two trial groups required")
    n_test = math.ceil(.2 * len(unique))
    order = np.random.RandomState(42).permutation(len(unique))
    test = np.flatnonzero(np.isin(inverse, order[:n_test]))
    train = np.flatnonzero(np.isin(inverse, order[n_test:]))
    return train, test


def _mode_mask(prediction):
    values, counts = np.unique(prediction, return_counts=True)
    # scipy.stats.mode selects the smallest value on a modal-frequency tie.
    modal = values[np.argmax(counts)]
    return prediction != modal


def _rmse(truth, prediction, mask):
    if not np.any(mask):
        return None
    return float(np.sqrt(np.mean((truth[mask] - prediction[mask]) ** 2)))


def source_error(truth, prediction, author_prediction):
    """Original prediction-dependent exclusion plus clearly separate controls."""
    truth = vector(truth, "truth")
    prediction = vector(prediction, "prediction")
    author = vector(author_prediction, "author prediction")
    need(truth.shape == prediction.shape == author.shape, "prediction length mismatch")
    retained = _mode_mask(prediction)
    author_retained = _mode_mask(author)
    return {
        "source_modal_filtered_rmse": _rmse(truth, prediction, retained),
        "full_bin_rmse": _rmse(truth, prediction, np.ones(len(truth), dtype=bool)),
        "author_support_rmse": _rmse(truth, prediction, author_retained),
        "total_frames": len(truth),
        "source_retained_frames": int(retained.sum()),
        "source_excluded_frames": int((~retained).sum()),
        "author_retained_frames": int(author_retained.sum()),
        "common_retained_frames": int((retained & author_retained).sum()),
    }


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _expected(arms):
    keys(arms, ("L", "R"), "arms")
    expected, lengths, split_report = {}, {}, {}
    for arm in ("L", "R"):
        data = arms[arm]
        keys(data, ("frame_ids", "trial_groups", "positions"), "arm")
        pos = vector(data["positions"], "arm positions")
        ids = data["frame_ids"]
        need(isinstance(ids, list) and len(ids) == len(pos) and
             all(type(v) is str and bool(v) for v in ids) and
             len(set(ids)) == len(ids), "unique frame identities required")
        need(isinstance(data["trial_groups"], list) and
             len(data["trial_groups"]) == len(pos), "trial/frame mismatch")
        train, test = source_split(data["trial_groups"])
        expected[arm] = ([ids[i] for i in test], pos[test].tolist())
        lengths[arm] = len(pos)
        split_report[arm] = {"train_frames": len(train), "test_frames": len(test),
                             "train_frame_ids_sha256": _digest([ids[i] for i in train]),
                             "test_frame_ids_sha256": _digest([ids[i] for i in test])}
    length = min(lengths.values())
    for target, source in (("L", "R"), ("R", "L")):
        name = target + " from " + source
        data = arms[target]
        expected[name] = (data["frame_ids"][:length], data["positions"][:length])
        expected[name + " Shuffled"] = expected[name]
    return expected, split_report


def _prediction(row, frame_ids, *, shuffle_id=None):
    fields = ("frame_ids", "positions") if shuffle_id is None else (
        "frame_ids", "positions", "shuffle_id")
    keys(row, fields, "prediction")
    need(row["frame_ids"] == frame_ids, "prediction frame identities/order mismatch")
    values = vector(row["positions"], "prediction")
    need(len(values) == len(frame_ids), "prediction length mismatch")
    if shuffle_id is not None:
        need(row["shuffle_id"] == shuffle_id, "shuffle identity/order mismatch")
    return row["positions"]


def _mean_complete(values):
    # Source mean propagates an undefined draw; no favorable null omission.
    return None if any(v is None for v in values) else float(np.mean(values))


def score(reference, candidate):
    keys(reference, ("schema_version", "kind", "phase", "mice"), "reference")
    keys(candidate, ("schema_version", "access_condition", "mice"), "candidate")
    need(type(reference["schema_version"]) is int and reference["schema_version"] == 1
         and type(candidate["schema_version"]) is int and candidate["schema_version"] == 1,
         "schema version")
    need(reference["kind"] in ("generated_control", "operator_prepared"), "reference kind")
    need(candidate["access_condition"] in ("paper_and_data", "paper_data_and_author_code"),
         "candidate access condition")
    need(reference["phase"] == "learned", "recovered notebook branch is learned")
    keys(reference["mice"], MICE, "complete source mouse roster")
    keys(candidate["mice"], MICE, "candidate mouse roster")
    result = {}
    for mouse in MICE:
        record = reference["mice"][mouse]
        keys(record, ("arms", "author", "shuffle_ids"), "mouse")
        keys(record["author"], CONDITIONS, "author conditions")
        keys(candidate["mice"][mouse], CONDITIONS, "candidate conditions")
        keys(record["shuffle_ids"], CONDITIONS[-2:], "shuffle condition roster")
        expected, splits = _expected(record["arms"])
        cells = {}
        for condition in CONDITIONS:
            ids, truth = expected[condition]
            baseline = record["author"][condition]
            submitted = candidate["mice"][mouse][condition]
            shuffled = condition.endswith(" Shuffled")
            if shuffled:
                shuffle_ids = record["shuffle_ids"][condition]
                need(isinstance(shuffle_ids, list) and len(shuffle_ids) == 50 and
                     all(type(v) is str and bool(v) for v in shuffle_ids) and
                     len(set(shuffle_ids)) == 50, "exactly 50 distinct frozen shuffle IDs required")
                need(isinstance(baseline, list) and isinstance(submitted, list) and
                     len(baseline) == len(submitted) == 50, "all 50 companion shuffles required")
            else:
                baseline, submitted, shuffle_ids = [baseline], [submitted], [None]
            pairs = []
            for a, b, shuffle_id in zip(baseline, submitted, shuffle_ids):
                author_pred = _prediction(a, ids, shuffle_id=shuffle_id)
                candidate_pred = _prediction(b, ids, shuffle_id=shuffle_id)
                discrepancy = np.asarray(candidate_pred) - np.asarray(author_pred)
                pairs.append({"author": source_error(truth, author_pred, author_pred),
                              "candidate": source_error(truth, candidate_pred, author_pred),
                              "reproduction_prediction_comparison": {
                                  "rmse_from_author": float(np.sqrt(np.mean(discrepancy ** 2))),
                                  "max_absolute_difference": float(np.max(np.abs(discrepancy)))}})
            summaries = {method: {metric: _mean_complete([p[method][metric] for p in pairs])
                                  for metric in METRICS}
                         for method in ("author", "candidate")}
            target = condition[0]
            source = condition.split(" from ")[1][0] if " from " in condition else target
            cells[condition] = {
                "rate_map_arm": source, "spike_and_truth_arm": target,
                "literal_source_rmse_key": condition,
                "literal_source_posterior_key": (
                    source + " from " + target + (" Shuffled" if shuffled else "")
                    if source != target else target),
                "evaluation_frame_ids_sha256": _digest(ids),
                "draw_count": len(pairs), "draws": pairs, "mean_over_draws": summaries,
                "improvement_candidate_minus_author": {
                    metric: None if summaries["candidate"][metric] is None or
                    summaries["author"][metric] is None else
                    summaries["candidate"][metric] - summaries["author"][metric]
                    for metric in METRICS},
            }
        result[mouse] = {"split": splits, "conditions": cells}
    panel = {}
    for condition in CONDITIONS:
        panel[condition] = {}
        for method in ("author", "candidate"):
            panel[condition][method] = {}
            for metric in METRICS:
                values = [result[m]["conditions"][condition]["mean_over_draws"][method][metric]
                          for m in MICE]
                panel[condition][method][metric] = {
                    "mouse_values": values, "mean": _mean_complete(values),
                    "population_std_ddof_0": None if any(v is None for v in values)
                    else float(np.std(values, ddof=0)),
                }
    return {
        "task_id": "PAPER-ROOT-ADD-007", "component": "fig1-position-scoring-v1",
        "qualification": "software_component_only", "native_preparation_verified": False,
        "paper_panel_identity_verified": False, "superiority_decision": None,
        "reproduction_decision": None, "access_condition": candidate["access_condition"],
        "reference_kind": reference["kind"], "phase": reference["phase"],
        "units": "normalized source position", "mouse_order": list(MICE),
        "condition_order": list(CONDITIONS), "mice": result, "panel": panel,
        "metric_note": "Source RMSE excludes each method's own modal prediction. Full-bin and fixed-author-support RMSE are separate diagnostics. No win rule is defined.",
    }


def _load(path):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            need(k not in out, "duplicate JSON key")
            out[k] = v
        return out
    def invalid(_):
        raise ContractError("nonfinite JSON")
    data = Path(path).read_bytes()
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid), hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", help="operator-owned reference JSON")
    parser.add_argument("candidate", help="frozen candidate predictions JSON")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        reference, ref_hash = _load(args.reference)
        candidate, candidate_hash = _load(args.candidate)
        report = score(reference, candidate)
        report["input_sha256"] = {"reference": ref_hash, "candidate": candidate_hash}
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (ContractError, ValueError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
