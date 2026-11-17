"""Prospective, source-only conditional calcium evaluator. No authentic data bundled.

The immutable task defines the scientific question, not a numerical recipe. This
module supplies an explicit recipe; its outputs never establish qualification.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

TASK_ID = "NEURAL-DISC-20261114-WORM-PROPAGATION"
RELEASE = "DANDI:001075/0.240930.1859"
ROLES = ("train", "development", "held")
GATES = [
    "Complete immutable release/OSF condition and trace roster reconciliation",
    "Independent acquisition-to-trace-to-neuron and authenticated animal joins",
    "Authentic schema, clocks, units, missingness and stimulus QC",
    "Component rights, public exposure and protected assessment qualification",
    "Authentic reference qualification and full negative-control campaign",
    "Prospective numerical recipe and common horizon acceptance",
]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _trace(trace, lower, upper, name, strict_upper=False):
    _require(set(trace) == {"times_s", "values"}, name + " has unknown/missing fields")
    ts, values = trace["times_s"], trace["values"]
    _require(isinstance(ts, list) and isinstance(values, list) and len(ts) == len(values) > 0,
             name + " requires equally sized nonempty times/values")
    _require(all(_number(t) for t in ts) and all(a < b for a, b in zip(ts, ts[1:])),
             name + " times must be finite and strictly increasing")
    _require(ts[0] >= lower and (ts[-1] < upper if strict_upper else ts[-1] <= upper),
             name + " time window violation")
    _require(all(v is None or _number(v) for v in values), name + " values must be finite or null")


def pair_key(case):
    return case["condition"], case["source_id"], case["receiver_id"]


def trial_key(case):
    return case["worm_id"], case["acquisition_id"], case["trial_id"]


def validate_dataset(data):
    """Validate assertions and complete local roster, not authenticity of assertions."""
    _require(data.get("task_id") == TASK_ID and data.get("schema_version") == 1, "task/schema mismatch")
    _require(data.get("release_id") == RELEASE, "immutable release mismatch")
    for key in ("inventory_sha256", "identity_audit_sha256", "mask_policy_sha256"):
        _require(_digest(data.get(key)), "missing pinned " + key)
    _require(data.get("identity_authenticated") is True, "authenticated worm join is required")
    _require(data.get("mask_policy") == "acquisition_missingness_only", "target-effect masks forbidden")
    _require(_text(data.get("units")), "units required; values are not implicitly normalized")
    _require(data.get("horizon_s") == 30, "v1 retains the declared 0..30 s horizon")
    gap = data.get("max_interpolation_gap_s")
    _require(_number(gap) and gap > 0, "positive prospective interpolation gap required")
    roster = data.get("expected_case_ids")
    cases = data.get("cases")
    _require(isinstance(roster, list) and roster and all(_text(k) for k in roster)
             and len(set(roster)) == len(roster), "unique complete expected roster required")
    _require(isinstance(cases, list) and cases, "cases required")
    ids, worms, acquisitions, trials, identities = set(), {}, {}, {}, set()
    for c in cases:
        for key in ("case_id", "worm_id", "acquisition_id", "trial_id", "source_id", "receiver_id", "condition"):
            _require(_text(c.get(key)), "nonempty " + key + " required")
        _require(c["case_id"] not in ids, "duplicate case_id")
        ids.add(c["case_id"])
        _require(c.get("role") in ROLES, "invalid role")
        _require(worms.setdefault(c["worm_id"], c["role"]) == c["role"], "worm crosses roles")
        _require(acquisitions.setdefault(c["acquisition_id"], c["worm_id"]) == c["worm_id"],
                 "acquisition maps to multiple worms")
        identity = trial_key(c) + (c["receiver_id"],)
        _require(identity not in identities, "duplicate receiver in one stimulation")
        identities.add(identity)
        _require(isinstance(c.get("quality_flags"), list) and all(_text(x) for x in c["quality_flags"]),
                 "explicit quality flags required (empty allowed)")
        stimulus = c.get("stimulus_parameters")
        _require(isinstance(stimulus, dict) and set(stimulus) == {"duration_s", "power_mw"}
                 and all(_number(v) and v > 0 for v in stimulus.values()),
                 "stimulus parameters require only positive numeric duration_s and power_mw")
        _require(_number(c.get("stimulus_onset_acquisition_s")), "absolute stimulus onset required")
        provenance = c.get("provenance", {})
        _require(_digest(provenance.get("asset_sha256")), "asset checksum required")
        _require(_text(provenance.get("asset_id")), "asset id required")
        for key in ("source_index", "receiver_index", "stimulus_index"):
            _require(isinstance(provenance.get(key), int) and not isinstance(provenance[key], bool)
                     and provenance[key] >= 0, "nonnegative source indices required")
        _trace(c["source"], -10, 30, "source")
        _trace(c["receiver_pre"], -10, 0, "receiver_pre", strict_upper=True)
        _trace(c["target"], 0, 30, "target")
        stimulus_signature = json.dumps({k: c[k] for k in (
            "source_id", "condition", "source", "stimulus_parameters", "stimulus_onset_acquisition_s")}, sort_keys=True)
        _require(trials.setdefault(trial_key(c), stimulus_signature) == stimulus_signature,
                 "one stimulation has inconsistent source or timing")
    _require(ids == set(roster), "case roster incomplete or contains undeclared cases")
    _require(all(role in worms.values() for role in ROLES), "train/development/held worms required")
    return data


def interpolate(trace, t, max_gap):
    """Linear interpolation only between adjacent valid original samples; no fill."""
    times, values = trace["times_s"], trace["values"]
    i = bisect.bisect_left(times, t)
    if i < len(times) and times[i] == t:
        return values[i]
    if i == 0 or i == len(times):
        return None
    left, right = i - 1, i
    if values[left] is None or values[right] is None or times[right] - times[left] > max_gap:
        return None
    weight = (t - times[left]) / (times[right] - times[left])
    return values[left] * (1 - weight) + values[right] * weight


def persistence(case):
    values = [x for x in case["receiver_pre"]["values"] if x is not None]
    return mean(values) if values else None


class PairMean:
    """Training-worm balanced means on each requested actual timestamp."""
    def __init__(self, cases, max_gap):
        _require(cases and all(c["role"] == "train" for c in cases), "pair mean accepts training only")
        self.groups = defaultdict(list)
        self.max_gap = max_gap
        for c in cases:
            self.groups[pair_key(c)].append(c)

    def predict(self, case):
        output = []
        for t in case["target"]["times_s"]:
            worms = defaultdict(list)
            for train in self.groups.get(pair_key(case), []):
                x = interpolate(train["target"], t, self.max_gap)
                if x is not None:
                    worms[train["worm_id"]].append(x)
            output.append(mean(mean(v) for v in worms.values()) if worms else None)
        return output

    def variance(self, case):
        # Per-pair training-only population variance with each worm weighted equally.
        worms = defaultdict(list)
        for train in self.groups.get(pair_key(case), []):
            worms[train["worm_id"]].extend(v for v in train["target"]["values"] if v is not None)
        values = [v for v in worms.values() if v]
        if not values:
            return None
        mu = mean(mean(v) for v in values)
        return mean(mean((x - mu) ** 2 for x in v) for v in values)


def _features(case, t, lags, gap):
    baseline = persistence(case)
    pre = [v for s, v in zip(case["source"]["times_s"], case["source"]["values"])
           if s < 0 and v is not None]
    samples = [interpolate(case["source"], t - lag, gap) for lag in lags]
    if baseline is None or not pre or any(v is None for v in samples):
        return None
    source_zero = mean(pre)
    # Trapezoid quadrature on an explicitly supplied causal lag grid.
    widths = [(lags[1] - lags[0]) / 2]
    widths += [(lags[i + 1] - lags[i - 1]) / 2 for i in range(1, len(lags) - 1)]
    widths += [(lags[-1] - lags[-2]) / 2]
    return [(v - source_zero) * w for v, w in zip(samples, widths)], baseline


class Convolution:
    """Pair-specific regularized linear convolution; no pooled author kernels."""
    def __init__(self, train, lags, alpha, gap):
        import numpy as np
        _require(train and all(c["role"] == "train" for c in train), "kernel fit accepts training only")
        _require(len(lags) >= 2 and all(_number(x) for x in lags) and lags[0] == 0
                 and lags[-1] <= 10 and all(a < b for a, b in zip(lags, lags[1:])),
                 "causal lag grid must increase from 0 to at most 10 seconds")
        _require(_number(alpha) and alpha > 0, "positive ridge regularization required")
        self.lags, self.alpha, self.gap, self.weights = list(lags), alpha, gap, {}
        rows = defaultdict(list)
        for c in train:
            for t, target in zip(c["target"]["times_s"], c["target"]["values"]):
                f = _features(c, t, self.lags, gap)
                if target is not None and f is not None:
                    rows[pair_key(c)].append((c["worm_id"], f[0], target - f[1]))
        for key, samples in rows.items():
            counts = defaultdict(int)
            for worm, _, _ in samples:
                counts[worm] += 1
            scale = np.array([1 / math.sqrt(counts[w] * len(counts)) for w, _, _ in samples])
            x = np.array([f for _, f, _ in samples]) * scale[:, None]
            y = np.array([v for _, _, v in samples]) * scale
            # Augmented least squares avoids explicitly forming the normal matrix.
            self.weights[key] = np.linalg.lstsq(
                np.vstack([x, math.sqrt(alpha) * np.eye(len(lags))]),
                np.concatenate([y, np.zeros(len(lags))]), rcond=None)[0].tolist()

    def predict(self, case):
        weights = self.weights.get(pair_key(case))
        result = []
        for t in case["target"]["times_s"]:
            f = _features(case, t, self.lags, self.gap)
            result.append(f[1] + sum(w * x for w, x in zip(weights, f[0]))
                          if weights is not None and f is not None else None)
        return result


def select_kernel(train, development, lags, alphas, gap):
    _require(development and all(c["role"] == "development" for c in development),
             "regularization selection requires development cases")
    _require(not ({c["worm_id"] for c in train} & {c["worm_id"] for c in development}),
             "training and development animals overlap")
    _require(isinstance(alphas, list) and alphas and all(_number(a) and a > 0 for a in alphas),
             "positive nonempty regularization candidates required")
    candidates = []
    for alpha in sorted(set(alphas)):
        model = Convolution(train, lags, alpha, gap)
        rows = []
        for c in development:
            metrics = trace_metrics(c["target"], model.predict(c), gap)
            rows.append({**c, **metrics})
        # Require every development case with observed targets to be supported.
        supported = all(r["mse"] is not None for r in rows if r["valid_samples"] > 0)
        by_worm = aggregate(rows, "mse")
        value = mean(x for x in by_worm.values() if x is not None) if supported and any(
            x is not None for x in by_worm.values()) else None
        candidates.append({"alpha": alpha, "development_worm_mean_mse": value})
    supported = [c for c in candidates if c["development_worm_mean_mse"] is not None]
    if not supported:
        return None, {"status": "unsupported_development", "candidates": candidates}
    best = min(supported, key=lambda c: (c["development_worm_mean_mse"], c["alpha"]))
    return Convolution(train, lags, best["alpha"], gap), {
        "status": "selected_on_separate_development_worms", "selected_alpha": best["alpha"],
        "lags_s": list(lags), "candidates": candidates, "refit_development": False}


def trace_metrics(target, prediction, gap):
    """A comparator is unsupported if it misses any observed target sample."""
    _require(len(prediction) == len(target["values"]), "prediction length mismatch")
    valid = [i for i, y in enumerate(target["values"]) if y is not None]
    result = {"valid_samples": len(valid), "requested_samples": len(prediction),
              "missing_target_samples": len(prediction) - len(valid), "mse": None,
              "correlation": None, "correlation_status": "no_valid_targets",
              "area_error": None, "absolute_area_error": None, "area_supported_duration_s": 0.0,
              "prediction_supported_samples": sum(prediction[i] is not None for i in valid)}
    if not valid or any(prediction[i] is None for i in valid):
        if valid:
            result["correlation_status"] = "unsupported_prediction"
        return result
    truth, pred = [target["values"][i] for i in valid], [prediction[i] for i in valid]
    result["mse"] = mean((a - b) ** 2 for a, b in zip(truth, pred))
    a0, b0 = mean(truth), mean(pred)
    aa, bb = sum((x - a0) ** 2 for x in truth), sum((x - b0) ** 2 for x in pred)
    if aa > 0 and bb > 0:
        result["correlation"] = sum((a - a0) * (b - b0) for a, b in zip(truth, pred)) / math.sqrt(aa * bb)
        result["correlation_status"] = "defined"
    else:
        result["correlation_status"] = "zero_target_variance" if aa == 0 else "zero_prediction_variance"
    area, duration = 0.0, 0.0
    ts, ys = target["times_s"], target["values"]
    for i in range(1, len(ts)):
        dt = ts[i] - ts[i - 1]
        if ys[i] is not None and ys[i - 1] is not None and dt <= gap:
            area += dt * ((prediction[i] - ys[i]) + (prediction[i - 1] - ys[i - 1])) / 2
            duration += dt
    if duration:
        result.update(area_error=area, absolute_area_error=abs(area), area_supported_duration_s=duration)
    return result


def aggregate(rows, metric):
    """Equal samples within case, equal trials within pair, equal pairs within worm.

    A missing metric in an observed case propagates to the worm. Missing-target-only
    cases remain in coverage but cannot contribute a numerical response metric.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grouped[r["worm_id"]]  # retain all-missing animals
        if r["valid_samples"]:
            grouped[r["worm_id"]][pair_key(r)].append(r.get(metric))
    answer = {}
    for worm, pairs in grouped.items():
        values = [v for trials in pairs.values() for v in trials]
        answer[worm] = mean(mean(v) for v in pairs.values()) if values and all(
            v is not None for v in values) else None
    return answer


def _percentile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return values[lo] * (hi - pos) + values[hi] * (pos - lo) if hi != lo else values[lo]


def paired_interval(values, seed=0, draws=2000):
    """Percentile bootstrap of authenticated worms, not individual cases."""
    _require(isinstance(draws, int) and not isinstance(draws, bool) and draws >= 100,
             "at least 100 bootstrap draws required")
    if len(values) < 2:
        return {"status": "fewer_than_two_supported_worms", "n_worms": len(values), "ci95": None}
    rng = random.Random(seed)
    samples = [mean(rng.choices(values, k=len(values))) for _ in range(draws)]
    return {"status": "engineering_prospective_percentile_worm_bootstrap", "n_worms": len(values),
            "mean": mean(values), "ci95": [_percentile(samples, .025), _percentile(samples, .975)],
            "seed": seed, "draws": draws}


def public_packet(data, role):
    """Strict allowlist: held/development responses never leave evaluator custody."""
    validate_dataset(data)
    _require(role in ROLES, "invalid packet role")
    output = {k: copy.deepcopy(data[k]) for k in ("task_id", "schema_version", "release_id", "units", "horizon_s")}
    output["role"] = role
    output["cases"] = []
    for c in data["cases"]:
        if c["role"] != role:
            continue
        packet = {k: copy.deepcopy(c[k]) for k in (
            "case_id", "worm_id", "acquisition_id", "trial_id", "source_id", "receiver_id", "condition",
            "source", "receiver_pre", "stimulus_parameters", "stimulus_onset_acquisition_s")}
        # QC flags/provenance can contain response-derived knowledge: custody only.
        packet["response_times_s"] = list(c["target"]["times_s"])
        if role == "train":
            packet["training_response"] = copy.deepcopy(c["target"])
        output["cases"].append(packet)
    return output


def source_reassignment(data, seed):
    """Whole-trace derangement of matched stimulations, shared by all receivers."""
    validate_dataset(data)
    out, rng = copy.deepcopy(data), random.Random(seed)
    trials, groups = {}, defaultdict(list)
    for c in out["cases"]:
        key = trial_key(c)
        if key in trials:
            continue
        trials[key] = c
        match = (c["worm_id"], c["condition"], c["source_id"],
                 json.dumps(c["stimulus_parameters"], sort_keys=True), tuple(c["source"]["times_s"]))
        groups[match].append(key)
    assigned, log = {}, []
    for keys in groups.values():
        keys.sort()
        if len(keys) == 1:
            log.append({"trial": list(keys[0]), "status": "unmatched_singleton_unchanged"})
            continue
        rng.shuffle(keys)
        for destination, source in zip(keys, keys[1:] + keys[:1]):
            assigned[destination] = copy.deepcopy(trials[source]["source"])
            log.append({"trial": list(destination), "source_trial": list(source), "status": "reassigned"})
    for c in out["cases"]:
        if trial_key(c) in assigned:
            c["source"] = copy.deepcopy(assigned[trial_key(c)])
    return out, {"seed": seed, "unit": "whole_stimulation_trace", "assignments": log,
                 "interpretation": "control copy; source provenance is reassigned per audit log"}


def evaluate(data, predictions, *, lags=(0., 1., 2., 4.), alphas=(.01, .1, 1.), seed=0, draws=2000):
    validate_dataset(data)
    held = [c for c in data["cases"] if c["role"] == "held"]
    _require(predictions.get("units") == data["units"], "prediction units mismatch")
    entries = predictions.get("cases")
    _require(isinstance(entries, list), "prediction cases required")
    by_id = {}
    for p in entries:
        _require(_text(p.get("case_id")) and p["case_id"] not in by_id, "duplicate/invalid prediction id")
        by_id[p["case_id"]] = p
    _require(set(by_id) == {c["case_id"] for c in held}, "predictions must match complete held roster")
    for c in held:
        p = by_id[c["case_id"]]
        _require(isinstance(p.get("times_s"), list) and all(_number(t) for t in p["times_s"])
                 and p["times_s"] == c["target"]["times_s"], "prediction grid must match exact original times")
        _require(isinstance(p.get("values"), list) and len(p["values"]) == len(p["times_s"])
                 and all(_number(v) for v in p["values"]), "all predictions must be finite, including missing targets")
    train = [c for c in data["cases"] if c["role"] == "train"]
    development = [c for c in data["cases"] if c["role"] == "development"]
    gap = data["max_interpolation_gap_s"]
    reference = PairMean(train, gap)
    kernel, selection = select_kernel(train, development, list(lags), list(alphas), gap)
    rows = []
    for c in held:
        p = by_id[c["case_id"]]["values"]
        model = trace_metrics(c["target"], p, gap)
        pair = trace_metrics(c["target"], reference.predict(c), gap)
        flat = trace_metrics(c["target"], [persistence(c)] * len(p), gap)
        conv = trace_metrics(c["target"], kernel.predict(c) if kernel else [None] * len(p), gap)
        variance = reference.variance(c)
        row = {k: c[k] for k in ("case_id", "worm_id", "acquisition_id", "trial_id", "source_id", "receiver_id", "condition", "quality_flags")}
        row.update(model)
        row.update(training_variance=variance, pair_mean_mse=pair["mse"], persistence_mse=flat["mse"],
                   convolution_mse=conv["mse"], target_first_s=c["target"]["times_s"][0],
                   target_last_s=c["target"]["times_s"][-1], target_tail_unobserved_s=30 - c["target"]["times_s"][-1])
        row["normalized_mse"] = model["mse"] / variance if variance is not None and variance > 0 and model["mse"] is not None else None
        row["normalization_status"] = "defined" if row["normalized_mse"] is not None else "missing_or_zero_training_variance_or_target"
        row["paired_mse_difference"] = model["mse"] - pair["mse"] if model["mse"] is not None and pair["mse"] is not None else None
        for raw, normalized in (("pair_mean_mse", "normalized_pair_mean_mse"),
                                ("paired_mse_difference", "normalized_paired_mse_difference")):
            row[normalized] = row[raw] / variance if variance is not None and variance > 0 and row[raw] is not None else None
        rows.append(row)
    metrics = ("mse", "normalized_mse", "pair_mean_mse", "persistence_mse", "convolution_mse",
               "paired_mse_difference", "normalized_pair_mean_mse", "normalized_paired_mse_difference",
               "correlation", "area_error", "absolute_area_error")
    aggregates = {metric: aggregate(rows, metric) for metric in metrics}
    worms = [{"worm_id": w, **{m: aggregates[m][w] for m in metrics}} for w in sorted(aggregates["mse"])]
    diffs = [w["paired_mse_difference"] for w in worms if w["paired_mse_difference"] is not None]
    all_supported = len(diffs) == len(worms)
    normalized_diffs = [w["normalized_paired_mse_difference"] for w in worms
                        if w["normalized_paired_mse_difference"] is not None]
    def interval(values):
        if len(values) != len(worms):
            return {"status": "incomplete_held_worm_support", "ci95": None,
                    "supported_worms": len(values), "declared_held_worms": len(worms)}
        return {**paired_interval(values, seed, draws), "scope": "complete_declared_held_worm_roster"}
    return {"task_id": TASK_ID, "implementation": "initial-evaluator-v1", "scientific_qualification": "unknown",
            "submission_ready": False, "interpretation": "retrospective conditional response; not forecasting or connectivity",
            "prospective_recipe": True, "remaining_gates": GATES, "kernel_selection": selection,
            "case_rows": rows, "worm_rows": worms,
            "coverage": {"declared_cases_all_roles": len(data["cases"]), "held_cases": len(held),
                         "held_worms": len(worms), "held_cases_no_valid_target": sum(not r["valid_samples"] for r in rows),
                         "paired_supported_worms": len(diffs), "all_held_worms_paired_supported": all_supported,
                         "quality_flag_counts": {f: sum(f in r["quality_flags"] for r in rows)
                                                 for f in sorted({f for r in rows for f in r["quality_flags"]})}},
            "paired_worm_interval": interval(diffs),
            "normalized_paired_worm_interval": interval(normalized_diffs),
            "complete_roster_primary_mean_difference": mean(diffs) if all_supported and diffs else None,
            "input_sha256": hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="write physical role packets and separate protected evaluator data")
    export.add_argument("dataset", type=Path)
    export.add_argument("output_directory", type=Path)
    score = sub.add_parser("score")
    score.add_argument("dataset", type=Path)
    score.add_argument("predictions", type=Path)
    score.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text())
    validate_dataset(data)
    if args.command == "export":
        args.output_directory.mkdir(parents=True, exist_ok=False)
        for role in ROLES:
            (args.output_directory / (role + ".json")).write_text(json.dumps(public_packet(data, role), indent=2, allow_nan=False) + "\n")
        private = args.output_directory / "evaluator-only"
        private.mkdir(mode=0o700)
        path = private / "protected.json"
        path.touch(mode=0o600)
        path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    else:
        result = evaluate(data, json.loads(args.predictions.read_text()))
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
