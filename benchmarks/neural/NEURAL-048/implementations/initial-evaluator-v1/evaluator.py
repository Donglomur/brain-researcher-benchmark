"""NEURAL-048 prospective causal-history and paired worm log-loss component.

Fresh standard-library implementation; no native data adapter or trained model.
Run ``python evaluator.py reference.json predictions.json --output report.json``.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from statistics import fmean

TASK_ID = "NEURAL-048"
SOURCE_COMMIT = "c7e7e18a84cde5dc02df9d63492293b38402eb2c"
ARMS = ("behavior", "neural_history", "shifted_neural_history")
BEHAVIOR = ("curvature", "velocity", "odor_encounter")
POLICY = {
    "version": "neural048-direction-logloss-v1",
    "target": "postreversal_direction_dorsal_1_ventral_0",
    "probabilities": "strictly_between_zero_and_one_no_clipping",
    "primary": "equal_worm_mean_behavior_minus_neural_log_loss_nats",
    "within_worm": "equal_observation_mean",
    "uncertainty": "paired_worm_percentile_95",
    "small_sample_resampling": "exhaustive_ordered_bootstrap_for_2_to_5_worms",
    "large_sample_resampling": {"replicates": 10000, "seed": 1729},
    "data_scope": "public_development_only",
    "source_commit": SOURCE_COMMIT,
}
GATES = [
    "Freeze canonical target/selection/exclusion/fitting/access/resource protocol before outcomes",
    "Locate and validate public H5/MAT to aligned derivative conversion",
    "Verify exact animal identities and full selected source inventory",
    "Validate odor crossings and causal alignment/support of every preprocessing operation",
    "Validate public/private payload hashes, target privacy and rights",
    "Execute signal-derived reference and independent matched comparator under exact contract",
    "Independent native replication and prospective scientific admission criteria",
]


class ContractError(ValueError):
    """Input cannot support the frozen component's estimand."""


def digest(value):
    """Stable JSON binding; non-finite numbers are never serializable."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _mapping(value, name):
    _require(isinstance(value, dict), f"{name}: object required")
    return value


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), f"{name}: nonempty string required")
    return value


def _integer(value, name):
    _require(type(value) is int, f"{name}: exact integer required (no float clocks or booleans)")
    return value


def _finite(value, name):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite, f"{name}: finite number required")
    return float(value)


def _ids(values, name, *, nonempty=True):
    _require(isinstance(values, list), f"{name}: list required")
    for value in values:
        _text(value, name)
    _require(len(values) == len(set(values)), f"{name}: duplicate identity")
    _require(bool(values) or not nonempty, f"{name}: empty")
    return set(values)


def _sha(value, name):
    _require(isinstance(value, str) and len(value) == 64 and
             all(c in "0123456789abcdef" for c in value), f"{name}: SHA256 required")


def causal_histories(samples, events, lags_ns, neural_shift_ns, max_age_ns):
    """Build matched past-only histories on exact clocks without interpolation.

    Each sample belongs to a (worm_id, session_id), has time_ns,
    available_ns, support_end_ns, all three BEHAVIOR fields, and a nonempty
    neural vector. Every event supplies id, worm_id, session_id, cutoff_ns.
    For lag L choose the latest sample at or before cutoff-L. Neural controls
    use cutoff-L-neural_shift_ns. No wrap, padding, dropping, cross-session
    borrowing or future availability is permitted. All requested events must
    succeed. Explicit age limits reject gaps instead of hiding missingness.
    """
    _require(isinstance(lags_ns, list) and bool(lags_ns), "history lags required")
    for lag in lags_ns:
        _require(_integer(lag, "lag") > 0, "lags must be strictly past")
    _require(lags_ns == sorted(set(lags_ns)), "lags must be unique ascending integers")
    _require(_integer(neural_shift_ns, "neural_shift_ns") > max(lags_ns),
             "shift must exceed the history span")
    _require(_integer(max_age_ns, "max_age_ns") >= 0, "max_age_ns must be nonnegative")
    grouped = defaultdict(list)
    widths = {}
    _require(isinstance(samples, list) and isinstance(events, list), "samples and events must be lists")
    for sample in samples:
        _mapping(sample, "sample")
        key = (_text(sample.get("worm_id"), "worm_id"),
               _text(sample.get("session_id"), "session_id"))
        t = _integer(sample.get("time_ns"), "time_ns")
        available = _integer(sample.get("available_ns"), "available_ns")
        support = _integer(sample.get("support_end_ns"), "support_end_ns")
        _require(t <= support <= available, "sample time/support/availability ordering invalid")
        behavior = [_finite(sample.get(name), name) for name in BEHAVIOR]
        neural = sample.get("neural")
        _require(isinstance(neural, list) and bool(neural), "nonempty neural vector required")
        neural = [_finite(v, "neural") for v in neural]
        _require(key not in widths or widths[key] == len(neural), "neural width changed in session")
        widths[key] = len(neural)
        grouped[key].append((t, available, support, behavior, neural))
    clocks = {}
    for key, rows in grouped.items():
        rows.sort(key=lambda r: r[0])
        clocks[key] = [r[0] for r in rows]
        _require(len(set(clocks[key])) == len(rows), "duplicate sample clock")

    def take(key, query):
        _require(key in grouped, "event has no matching worm/session signal")
        idx = bisect_right(clocks[key], query) - 1
        _require(idx >= 0, "insufficient history; complete matched set cannot be scored")
        row = grouped[key][idx]
        _require(query - row[0] <= max_age_ns, "history gap exceeds frozen max_age_ns")
        _require(row[1] <= query and row[2] <= query,
                 "future-derived alignment or unavailable sample")
        return row

    output = []
    seen = set()
    for event in events:
        _mapping(event, "event")
        event_id = _text(event.get("id"), "event id")
        _require(event_id not in seen, "duplicate event id")
        seen.add(event_id)
        key = (_text(event.get("worm_id"), "worm_id"),
               _text(event.get("session_id"), "session_id"))
        cutoff = _integer(event.get("cutoff_ns"), "cutoff_ns")
        normal = [take(key, cutoff - lag) for lag in lags_ns]
        shifted = [take(key, cutoff - lag - neural_shift_ns) for lag in lags_ns]
        _require(all(a[0] - b[0] == neural_shift_ns for a, b in zip(normal, shifted)),
                 "irregular sampling prevents exact neural time translation")
        behavior = [value for row in normal for value in row[3]]
        output.append({
            "id": event_id, "worm_id": key[0], "session_id": key[1],
            "cutoff_ns": cutoff, "behavior": behavior,
            "neural_history": behavior + [v for row in normal for v in row[4]],
            "shifted_neural_history": behavior + [v for row in shifted for v in row[4]],
            "behavior_sample_times_ns": [r[0] for r in normal],
            "neural_sample_times_ns": [r[0] for r in normal],
            "shifted_neural_sample_times_ns": [r[0] for r in shifted],
        })
    _require(bool(output), "empty event inventory")
    return output


def validate_reference(reference):
    """Validate sealed operator labels, biological partitions and full inventory."""
    _mapping(reference, "reference")
    _require(reference.get("task_id") == TASK_ID, "wrong task identity")
    _require(reference.get("policy") == POLICY, "policy differs from prospective v1")
    _sha(reference.get("source_manifest_sha256"), "source_manifest_sha256")
    _sha(reference.get("behavior_history_sha256"), "behavior_history_sha256")
    population = _ids(reference.get("population_worm_ids"), "population_worm_ids")
    test_worms = _ids(reference.get("evaluation_worm_ids"), "evaluation_worm_ids")
    _require(test_worms <= population, "unknown evaluation worm")
    folds = reference.get("folds")
    _require(isinstance(folds, list) and bool(folds), "folds required")
    fold_map, tested = {}, set()
    for fold in folds:
        _mapping(fold, "fold")
        fid = _text(fold.get("id"), "fold id")
        _require(fid not in fold_map, "duplicate fold id")
        train = _ids(fold.get("train_worm_ids"), "train_worm_ids")
        valid = _ids(fold.get("validation_worm_ids"), "validation_worm_ids", nonempty=False)
        test = _ids(fold.get("test_worm_ids"), "test_worm_ids")
        _require(not (train & valid or train & test or valid & test), "whole-worm split leakage")
        _require(train | valid | test == population, "fold does not account for full selected population")
        _require(not (tested & test), "worm tested more than once")
        tested |= test
        fold_map[fid] = test
    _require(tested == test_worms, "evaluation worm coverage mismatch")
    inventory = reference.get("episode_inventory")
    _require(isinstance(inventory, list) and bool(inventory), "complete episode inventory required")
    expected, episodes = {}, set()
    for episode in inventory:
        _mapping(episode, "episode")
        worm = _text(episode.get("worm_id"), "worm_id")
        session = _text(episode.get("session_id"), "session_id")
        eid = _text(episode.get("episode_id"), "episode_id")
        key = (worm, session, eid)
        _require(worm in test_worms, "inventory contains non-evaluation worm")
        _require(key not in episodes, "duplicate complete episode")
        episodes.add(key)
        for oid in _ids(episode.get("observation_ids"), "observation_ids"):
            _require(oid not in expected, "observation assigned to multiple episodes")
            expected[oid] = key
    observations = reference.get("observations")
    _require(isinstance(observations, list) and bool(observations), "observations required")
    observed, worm_coverage, physical_events = {}, set(), set()
    for row in observations:
        _mapping(row, "observation")
        oid = _text(row.get("id"), "observation id")
        _require(oid not in observed, "duplicate observation")
        key = (row.get("worm_id"), row.get("session_id"), row.get("episode_id"))
        _require(expected.get(oid) == key, "observation differs from frozen episode inventory")
        fid = _text(row.get("fold_id"), "observation fold_id")
        _require(fid in fold_map and key[0] in fold_map[fid],
                 "observation outside its worm-held-out fold")
        _require(type(row.get("dorsal")) is int and row["dorsal"] in (0, 1), "binary direction label required")
        cutoff = _integer(row.get("cutoff_ns"), "cutoff_ns")
        target_start = _integer(row.get("target_start_ns"), "target_start_ns")
        target_end = _integer(row.get("target_end_ns"), "target_end_ns")
        _require(cutoff < target_start <= target_end, "target must follow predictor cutoff")
        physical = (key[0], key[1], cutoff)
        _require(physical not in physical_events, "duplicate physical observation under a new id")
        physical_events.add(physical)
        observed[oid] = row
        worm_coverage.add(key[0])
    _require(set(observed) == set(expected), "incomplete episode observation coverage")
    _require(worm_coverage == test_worms, "missing evaluation worm")
    return observed


def _quantile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = math.floor(position)
    hi = math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def paired_interval(contrasts):
    """Paired biological-unit percentile interval, never pseudo-replicated rows."""
    n = len(contrasts)
    _require(n > 0, "no worm contrasts")
    for value in contrasts:
        _finite(value, "worm contrast")
    if n == 1:
        return {"interval_95": None, "method": "single_worm_descriptive_only", "resamples": 0}
    if n <= 5:
        means = [fmean(draw) for draw in itertools.product(contrasts, repeat=n)]
        method = "exhaustive_ordered_paired_worm_bootstrap_percentile"
    else:
        rng = random.Random(POLICY["large_sample_resampling"]["seed"])
        means = [fmean(contrasts[rng.randrange(n)] for _ in range(n))
                 for _ in range(POLICY["large_sample_resampling"]["replicates"])]
        method = "seeded_paired_worm_bootstrap_percentile"
    return {"interval_95": [_quantile(means, .025), _quantile(means, .975)],
            "method": method, "resamples": len(means),
            "interpretation": "descriptive development uncertainty; small-n intervals are not admission evidence"}


def score(reference, submission):
    observations = validate_reference(reference)
    _mapping(submission, "submission")
    _require(submission.get("task_id") == TASK_ID, "wrong prediction task")
    _require(submission.get("reference_sha256") == digest(reference), "reference binding mismatch")
    _require(submission.get("policy_sha256") == digest(POLICY), "policy binding mismatch")
    receipts = submission.get("arm_receipts")
    _require(isinstance(receipts, dict) and set(receipts) == set(ARMS), "all three arm receipts required")
    for arm in ARMS:
        receipt = _mapping(receipts[arm], "arm receipt")
        _require(receipt.get("split_sha256") == digest(reference["folds"]), "arm split mismatch")
        _require(receipt.get("behavior_history_sha256") == reference["behavior_history_sha256"],
                 "unmatched behavior/odor/motion histories")
        _sha(receipt.get("frozen_recipe_sha256"), "frozen_recipe_sha256")
        _require(_finite(receipt.get("cpu_seconds"), "cpu_seconds") >= 0, "negative resource usage")
        _require(_integer(receipt.get("peak_memory_bytes"), "peak_memory_bytes") >= 0, "negative memory")
    rows = submission.get("predictions")
    _require(isinstance(rows, list), "prediction rows required")
    losses = defaultdict(lambda: defaultdict(list))
    probabilities = {arm: [] for arm in ARMS}
    seen = set()
    episode_losses = defaultdict(lambda: defaultdict(list))
    for prediction in rows:
        _mapping(prediction, "prediction")
        oid = _text(prediction.get("id"), "prediction id")
        _require(oid in observations and oid not in seen, "unknown or duplicate prediction id")
        _require(set(prediction) == {"id", *ARMS}, "prediction row must contain exact matched arms")
        seen.add(oid)
        target = observations[oid]
        for arm in ARMS:
            p = _finite(prediction[arm], f"{arm} probability")
            _require(0 < p < 1, "probabilities must be in open interval (0,1); no silent clipping")
            loss = -math.log(p) if target["dorsal"] else -math.log1p(-p)
            losses[target["worm_id"]][arm].append(loss)
            episode_losses[(target["worm_id"], target["session_id"], target["episode_id"])][arm].append(loss)
            probabilities[arm].append(p)
    _require(seen == set(observations), "missing predictions; no selective matched-set dropping")
    worm_rows = []
    for worm in sorted(losses):
        row = {"worm_id": worm, "observations": len(losses[worm]["behavior"]),
               "log_loss_nats": {arm: fmean(losses[worm][arm]) for arm in ARMS}}
        ll = row["log_loss_nats"]
        row["behavior_minus_neural"] = ll["behavior"] - ll["neural_history"]
        row["behavior_minus_shifted"] = ll["behavior"] - ll["shifted_neural_history"]
        row["shifted_minus_neural"] = ll["shifted_neural_history"] - ll["neural_history"]
        worm_rows.append(row)
    contrasts = {}
    for name in ("behavior_minus_neural", "behavior_minus_shifted", "shifted_minus_neural"):
        values = [row[name] for row in worm_rows]
        contrasts[name] = {"mean_nats_per_observation": fmean(values), **paired_interval(values)}
    return {
        "task_id": TASK_ID, "component": "initial-evaluator-v1", "policy": POLICY,
        "reference_sha256": digest(reference), "submission_sha256": digest(submission),
        "primary": contrasts["behavior_minus_neural"], "contrasts": contrasts,
        "worms": worm_rows,
        "episodes": [{"worm_id": key[0], "session_id": key[1], "episode_id": key[2],
                      "observations": len(value["behavior"]),
                      "log_loss_nats": {arm: fmean(value[arm]) for arm in ARMS}}
                     for key, value in sorted(episode_losses.items())],
        "constant_probability_arms": [arm for arm in ARMS if len(set(probabilities[arm])) == 1],
        "resource_receipts": receipts,
        "validation_scope": {
            "verified": ["JSON bindings", "declared worm split disjointness", "declared complete episode coverage",
                         "label/cutoff chronology", "probability validity", "paired natural-log scoring"],
            "not_verified": ["source authenticity/completeness", "actual model fitting and resource receipts",
                             "actual feature construction/causality", "actual shifted-trace construction"],
            "history_builder": "causal_histories is a separate callable; score does not execute or attest it",
        },
        "status": "engineering_component_only_public_development",
        "admission": {"runnable_native": False, "research_qualified": False, "submission_ready": False},
        "remaining_gates": GATES,
    }


def _load(path):
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            _require(key not in out, f"duplicate JSON key: {key}")
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"nonfinite JSON: {value}")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("predictions")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = score(_load(args.reference), _load(args.predictions))
        Path(args.output).write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"NEURAL-048 input rejected: {exc}\n")


if __name__ == "__main__":
    main()
