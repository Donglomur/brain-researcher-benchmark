#!/usr/bin/env python3
"""NEURAL-015 prospective, complete-cohort word-onset grid evaluator.

Original implementation; no author code, recordings, transcripts or media bundled.
This module validates engineering contracts. It cannot certify native provenance.
"""
import argparse
from bisect import bisect_left
import hashlib
import json
import math
from pathlib import Path
import random
import sys

TASK = "NEURAL-015"
PROFILE = "prospective-onset-uniform-grid-v1"
CATALOG = json.loads(Path(__file__).with_name("catalog.json").read_text())
IDENTITIES = {r["recording_id"]: r for r in CATALOG["recordings"]}
HOLDS = [
    "prospective protocol and onset/boundary/balancing choices require admission before outcomes",
    "native HDF5 calibration, electrodes, complete onset extraction and trigger alignment unvalidated",
    "target-independent continuous acoustic/visual feature extraction and reference fitting unexecuted",
    "public development only; protected evaluation and independent native replication unavailable",
    "unversioned payload hashes, source-code licensing and media redistribution unresolved",
]


class ContractError(ValueError):
    """A malformed or scientifically incomparable input was supplied."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(obj, keys, name):
    require(isinstance(obj, dict) and set(obj) == set(keys), f"{name}: exact fields required: {sorted(keys)}")


def integer(value, name, minimum=None):
    require(type(value) is int, f"{name}: integer required")
    require(minimum is None or value >= minimum, f"{name}: minimum is {minimum}")
    return value


def finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name}: finite number required")
    return value


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(value, name):
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{name}: lowercase SHA256 required")


def unique_strings(values, name):
    require(isinstance(values, list) and all(isinstance(v, str) and v for v in values), f"{name}: string list required")
    require(len(values) == len(set(values)), f"{name}: duplicate IDs")
    return set(values)


def validate_protocol(p):
    exact(p, ["profile", "sample_rate_hz", "grid_step_samples", "tolerance_samples", "feature_lags_samples", "guard_samples", "latency_shift_samples", "probability_clip", "bootstrap_draws", "bootstrap_seed", "fitting_recipe_sha256", "acoustic_visual_recipe_sha256"], "protocol")
    require(p["profile"] == PROFILE, "unsupported prospective profile")
    require(type(p["sample_rate_hz"]) is int and p["sample_rate_hz"] == 2048, "author-source rate must be 2048 Hz; calibration remains held")
    step = integer(p["grid_step_samples"], "grid_step_samples", 1)
    tol = integer(p["tolerance_samples"], "tolerance_samples", 0)
    require(isinstance(p["feature_lags_samples"], list) and p["feature_lags_samples"], "feature lags must explicitly cover every neural/control lag")
    lags = [integer(x, "feature lag") for x in p["feature_lags_samples"]]
    require(all(x <= 0 for x in lags), "future neural/context lags are prohibited by this profile")
    guard = integer(p["guard_samples"], "guard_samples", 0)
    require(guard >= max(abs(x) for x in lags), "guard does not cover all feature lags")
    shift = integer(p["latency_shift_samples"], "latency_shift_samples")
    require(shift % step == 0 and abs(shift) > tol + max(abs(x) for x in lags), "latency shift must be whole bins and exceed tolerance plus feature support")
    eps = finite(p["probability_clip"], "probability_clip")
    require(0 < eps < 0.5, "probability_clip must be in (0, 0.5)")
    integer(p["bootstrap_draws"], "bootstrap_draws", 0)
    require(p["bootstrap_draws"] <= 100000, "bootstrap_draws exceeds bounded evaluator limit")
    integer(p["bootstrap_seed"], "bootstrap_seed", 0)
    for k in ("fitting_recipe_sha256", "acoustic_visual_recipe_sha256"):
        sha(p[k], k)


def validate_reference(ref):
    exact(ref, ["task_id", "protocol", "folds", "recordings"], "private reference")
    require(ref["task_id"] == TASK, "task ID mismatch")
    validate_protocol(ref["protocol"])
    require(isinstance(ref["folds"], list) and ref["folds"], "folds required")
    coverage, fold_ids = [], set()
    for fold in ref["folds"]:
        exact(fold, ["fold_id", "train", "test", "unused"], "fold")
        fid = fold["fold_id"]
        require(isinstance(fid, str) and fid and fid not in fold_ids, "fold ID missing or repeated")
        fold_ids.add(fid)
        train = unique_strings(fold["train"], "train")
        test = unique_strings(fold["test"], "test")
        unused = unique_strings(fold["unused"], "unused")
        require(train and test, "each fold needs nonempty train and test")
        require(not (train & test or train & unused or test & unused), "fold partitions overlap")
        require(train | test | unused == set(IDENTITIES), "each fold must account for all 26 recordings")
        for field in ("participant_id", "movie_id"):
            require(not ({IDENTITIES[r][field] for r in train} & {IDENTITIES[r][field] for r in test}), f"{field} leakage between train and test")
        coverage.extend(test)
    require(len(coverage) == len(IDENTITIES) and set(coverage) == set(IDENTITIES), "every source recording must be tested exactly once")
    for field in ("participant_id", "movie_id"):
        test_folds = {}
        for fold in ref["folds"]:
            for rid in fold["test"]:
                group = IDENTITIES[rid][field]
                require(group not in test_folds or test_folds[group] == fold["fold_id"], f"{field} split across test folds")
                test_folds[group] = fold["fold_id"]
    require(isinstance(ref["recordings"], list), "recordings list required")
    by_id = {}
    for rec in ref["recordings"]:
        exact(rec, ["recording_id", "sample_count", "word_onset_samples", "neural_sha256", "alignment_sha256", "transcript_sha256", "acoustic_visual_probabilities"], "reference recording")
        rid = rec["recording_id"]
        require(isinstance(rid, str) and rid in IDENTITIES and rid not in by_id, "unknown/duplicate reference recording ID")
        n = integer(rec["sample_count"], "sample_count", 1)
        require(n > 2 * ref["protocol"]["guard_samples"], "recording has no interior after guard")
        require(len(grid(rec, ref["protocol"])) > abs(ref["protocol"]["latency_shift_samples"] // ref["protocol"]["grid_step_samples"]), "recording has no paired latency-control interior")
        onsets = rec["word_onset_samples"]
        require(isinstance(onsets, list), "onset array required, including empty arrays")
        for t in onsets:
            finite(t, "word onset sample")
            require(0 <= t < n, "onset outside full recording")
        require(onsets == sorted(onsets), "onsets must be sorted; duplicate onsets represent coincident words")
        for k in ("neural_sha256", "alignment_sha256", "transcript_sha256"):
            sha(rec[k], k)
        control = rec["acoustic_visual_probabilities"]
        require(isinstance(control, list) and len(control) == len(grid(rec, ref["protocol"])), "operator control must cover the exact full grid")
        for value in control:
            require(0 <= finite(value, "operator acoustic/visual probability") <= 1, "operator control probability outside [0,1]")
        by_id[rid] = rec
    require(set(by_id) == set(IDENTITIES), "reference must contain all 26 recordings, without selection")
    return by_id


def grid(rec, protocol):
    g = protocol["guard_samples"]
    return range(g, rec["sample_count"] - g, protocol["grid_step_samples"])


def onset_labels(times, onsets, tolerance):
    """Binary window occupancy, inclusive distance, without nearest-bin reassignment."""
    labels = []
    for t in times:
        j = bisect_left(onsets, t)
        near = onsets[max(0, j - 1):j + 1]
        labels.append(int(any(abs(t - onset) <= tolerance for onset in near)))
    return labels


def public_query(ref):
    """Allowlist export; never expose transcript, target, movie ID, or private hashes."""
    recs = validate_reference(ref)
    fold_for = {rid: f["fold_id"] for f in ref["folds"] for rid in f["test"]}
    return {"task_id": TASK, "profile": PROFILE, "protocol_sha256": digest(ref["protocol"]), "recordings": [
        {"recording_id": rid, "fold_id": fold_for[rid], "grid_start_sample": ref["protocol"]["guard_samples"],
         "grid_stop_sample_exclusive": recs[rid]["sample_count"] - ref["protocol"]["guard_samples"],
         "grid_step_samples": ref["protocol"]["grid_step_samples"], "n_grid_points": len(grid(recs[rid], ref["protocol"]))}
        for rid in sorted(recs)]}


def average_precision(y, scores, weights=None):
    """Noninterpolated AP: sum of recall increments times precision, ties grouped."""
    require(len(y) == len(scores) and len(y) > 0, "AP arrays must align and be nonempty")
    require(all(type(v) is int and v in (0, 1) for v in y), "AP labels must be binary integers")
    weights = [1.0] * len(y) if weights is None else weights
    require(len(weights) == len(y), "AP weights must align")
    for s, w in zip(scores, weights):
        finite(s, "AP score")
        require(finite(w, "AP weight") > 0, "AP weights must be positive")
    positives = math.fsum(w for label, w in zip(y, weights) if label)
    if positives == 0:
        return None
    order = sorted(range(len(y)), key=lambda i: scores[i], reverse=True)
    tp = total = result = 0.0
    j = 0
    while j < len(order):
        end = j + 1
        while end < len(order) and scores[order[end]] == scores[order[j]]:
            end += 1
        group = order[j:end]
        gained = math.fsum(weights[i] for i in group if y[i])
        tp += gained
        total += math.fsum(weights[i] for i in group)
        result += (gained / positives) * (tp / total)
        j = end
    return result


def metrics(y, scores, eps, balanced=False):
    require(len(y) == len(scores) and y, "metric arrays must align and be nonempty")
    require(all(type(v) is int and v in (0, 1) for v in y), "metric labels must be binary integers")
    require(0 < finite(eps, "probability clip") < .5, "probability clip must be in (0,0.5)")
    for p in scores:
        require(0 <= finite(p, "probability") <= 1, "probability outside [0,1]")
    positive = sum(y)
    negative = len(y) - positive
    if balanced and (not positive or not negative):
        return None
    weights = [(0.5 / positive if label else 0.5 / negative) for label in y] if balanced else [1.0 / len(y)] * len(y)
    # Clip the probability of the observed class, avoiding log1p(-1) when
    # a tiny valid epsilon makes (1 - epsilon) round to exactly 1.0.
    loss = math.fsum(w * -math.log(max(eps, min(1 - eps, p if label else 1 - p))) for label, p, w in zip(y, scores, weights))
    return {"average_precision": average_precision(y, scores, weights), "log_loss_nats": loss,
            "constant_output": len(set(scores)) == 1, "n_bins": len(y), "n_positive_bins": positive,
            "positive_prevalence": positive / len(y), "clipped_probabilities": sum(p < eps or 1 - p < eps for p in scores)}


def percentile(values, q):
    values = sorted(values)
    x = (len(values) - 1) * q
    low = int(x)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (x - low)


def summarize(participants, protocol):
    keys = ("neural_average_precision", "control_average_precision", "incremental_log_loss_nats")
    require(participants, "no participants")
    out = {k: math.fsum(p[k] for p in participants) / len(participants) if all(p[k] is not None for p in participants) else None for k in keys}
    draws = protocol["bootstrap_draws"]
    ci = {k: None for k in keys}
    if draws:
        rng = random.Random(protocol["bootstrap_seed"])
        distributions = {k: [] for k in keys if out[k] is not None}
        for _ in range(draws):
            sample = [participants[rng.randrange(len(participants))] for _ in participants]
            for k in distributions:
                distributions[k].append(math.fsum(p[k] for p in sample) / len(sample))
        ci.update({k: [percentile(v, 0.025), percentile(v, 0.975)] for k, v in distributions.items()})
    return {"participant_macro": out, "paired_participant_bootstrap_95_percentile": ci,
            "n_participants": len(participants), "undefined_participants_not_dropped": True}


def compare(y, neural, control, p, balanced=False):
    a, b = metrics(y, neural, p["probability_clip"], balanced), metrics(y, control, p["probability_clip"], balanced)
    if a is None or b is None:
        return {"neural_average_precision": None, "control_average_precision": None, "incremental_log_loss_nats": None, "neural": a, "control": b}
    return {"neural_average_precision": a["average_precision"], "control_average_precision": b["average_precision"],
            "incremental_log_loss_nats": b["log_loss_nats"] - a["log_loss_nats"], "neural": a, "control": b}


def evaluate(ref, submission):
    recs = validate_reference(ref)
    exact(submission, ["task_id", "query_sha256", "predictions"], "submission")
    require(submission["task_id"] == TASK and submission["query_sha256"] == digest(public_query(ref)), "submission not bound to exact public query")
    require(isinstance(submission["predictions"], list), "prediction list required")
    predictions = {}
    fold_by_id = {rid: f["fold_id"] for f in ref["folds"] for rid in f["test"]}
    for row in submission["predictions"]:
        exact(row, ["recording_id", "fold_id", "neural"], "prediction")
        rid = row["recording_id"]
        require(isinstance(rid, str) and rid in recs and rid not in predictions, "unknown/duplicate prediction ID")
        require(row["fold_id"] == fold_by_id[rid], "prediction fold mismatch")
        n = len(grid(recs[rid], ref["protocol"]))
        for arm in ("neural",):
            require(isinstance(row[arm], list) and len(row[arm]) == n, "prediction must cover every fixed-grid timestamp in order")
            for value in row[arm]:
                require(0 <= finite(value, arm) <= 1, "probability outside [0,1]")
        predictions[rid] = row
    require(set(predictions) == set(recs), "missing recordings cannot be omitted or imputed")
    p = ref["protocol"]
    grouped, session_reports = {}, []
    shift = p["latency_shift_samples"] // p["grid_step_samples"]
    for rid in sorted(recs):
        y = onset_labels(grid(recs[rid], p), recs[rid]["word_onset_samples"], p["tolerance_samples"])
        pred = predictions[rid]
        control = recs[rid]["acoustic_visual_probabilities"]
        subject = IDENTITIES[rid]["participant_id"]
        group = grouped.setdefault(subject, {k: [] for k in ("y", "n", "a", "shift_y", "shift_n", "shift_control")})
        for k, values in (("y", y), ("n", pred["neural"]), ("a", control)):
            group[k].extend(values)
        indices = [i for i in range(len(y)) if 0 <= i - shift < len(y)]
        require(indices, "latency shift leaves a recording without paired interior bins")
        group["shift_y"].extend(y[i] for i in indices)
        group["shift_n"].extend(pred["neural"][i] for i in indices)
        group["shift_control"].extend(pred["neural"][i - shift] for i in indices)
        session_reports.append({"recording_id": rid, "participant_id": subject, "fold_id": fold_by_id[rid],
                                "n_bins": len(y), "n_positive_bins": sum(y), "n_latency_control_bins": len(indices),
                                "neural_constant": len(set(pred["neural"])) == 1, "acoustic_visual_constant": len(set(control)) == 1})
    primary, balanced, shifted = [], [], []
    for subject in sorted(grouped, key=int):
        g = grouped[subject]
        primary.append({"participant_id": subject, **compare(g["y"], g["n"], g["a"], p)})
        balanced.append({"participant_id": subject, **compare(g["y"], g["n"], g["a"], p, balanced=True)})
        shifted.append({"participant_id": subject, **compare(g["shift_y"], g["shift_n"], g["shift_control"], p)})
    return {"task_id": TASK, "profile": PROFILE, "scope": "construction-only public-development evaluator",
            "scientific_qualification": "unknown", "admitted": False, "holds": HOLDS,
            "reference_sha256": digest(ref), "submission_sha256": digest(submission),
            "catalog_sha256": digest(CATALOG), "population": {"participants": len(grouped), "recordings": len(recs), "unique_movies": len({r["movie_id"] for r in IDENTITIES.values()})},
            "primary_uniform_grid": {**summarize(primary, p), "participants": primary},
            "balanced_class_weight_diagnostic": {**summarize(balanced, p), "participants": balanced},
            "latency_shift_common_interior_diagnostic": {**summarize(shifted, p), "participants": shifted,
                "shift_samples": p["latency_shift_samples"], "no_circular_wrap": True}, "recordings": session_reports}


def align_onsets(movie_times, triggers, max_clock_residual_samples):
    """Source-informed nearest-anchor, 2048 Hz, Python round; strict coverage added.

    Trigger keys are operator-normalized movie_time_seconds and neural_sample_index.
    All triggers and times must be from one recording. No data is silently dropped.
    """
    finite(max_clock_residual_samples, "maximum clock residual")
    require(max_clock_residual_samples >= 0, "clock residual limit cannot be negative")
    require(isinstance(triggers, list) and len(triggers) >= 2, "at least two triggers required")
    for t in triggers:
        exact(t, ["movie_time_seconds", "neural_sample_index"], "trigger")
        finite(t["movie_time_seconds"], "trigger time")
        integer(t["neural_sample_index"], "trigger index", 0)
    ts = [t["movie_time_seconds"] for t in triggers]
    ns = [t["neural_sample_index"] for t in triggers]
    require(all(a < b for a, b in zip(ts, ts[1:])) and all(a < b for a, b in zip(ns, ns[1:])), "trigger clocks must be strictly increasing")
    residuals = [(b - a) - 2048 * (d - c) for a, b, c, d in zip(ns, ns[1:], ts, ts[1:])]
    require(all(abs(r) <= max_clock_residual_samples for r in residuals), "adjacent trigger residual exceeds declared clock bound")
    require(isinstance(movie_times, list), "movie onset times list required")
    aligned = []
    for t in movie_times:
        finite(t, "movie onset time")
        require(ts[0] <= t <= ts[-1], "word onset outside trigger coverage; extrapolation forbidden")
        i = bisect_left(ts, t)
        candidates = range(max(0, i - 1), min(len(ts), i + 1))
        nearest = min(candidates, key=lambda j: (abs(ts[j] - t), j))
        aligned.append(round(ns[nearest] + (t - ts[nearest]) * 2048))
    require(movie_times == sorted(movie_times), "movie onset times must be sorted before rounding")
    require(aligned == sorted(aligned), "aligned onsets are not monotonic")
    return {"word_onset_samples": aligned, "adjacent_clock_residual_samples": residuals,
            "native_alignment_validated": False, "coverage_rule": "inclusive trigger span; no extrapolation"}


def load_json(path):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, f"duplicate JSON key: {k}")
            out[k] = v
        return out
    def bad_constant(s):
        raise ContractError(f"nonfinite JSON constant: {s}")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["query", "score", "align", "validate"])
    parser.add_argument("input", help="private reference, or alignment JSON")
    parser.add_argument("--submission")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        data = load_json(args.input)
        if args.command == "query":
            result = public_query(data)
        elif args.command == "validate":
            validate_reference(data)
            result = {"reference_sha256": digest(data), "valid_construction_contract": True, "admitted": False, "holds": HOLDS}
        elif args.command == "align":
            exact(data, ["movie_times", "triggers", "max_clock_residual_samples"], "alignment input")
            result = align_onsets(**data)
        else:
            require(args.submission is not None, "score requires --submission")
            result = evaluate(data, load_json(args.submission))
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ContractError, OSError, json.JSONDecodeError) as e:
        print(f"NEURAL-015 input rejected: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
