"""Owner-side Figure 3c arithmetic; no loading pickles, fitting, or win decision.

Input None represents source NaN. Output tagged values preserve NaN and signed
infinity rather than treating undefined standardization as zero or dropping mice.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

TASK = "PAPER-EXP-20261113-004"
COMMIT = "adf0f9ed3defa22275d92fa0ed996f47008e05b3"
ANIMALS = ("GCAMP3", "GCAMP4", "GCAMP7", "GCAMP11", "GCAMP12", "GCAMP13",
           "GCAMP14", "GCAMP15", "GCAMP17", "GCAMP18", "GCAMP19")
DAYS = (3, 5, 7, 8, 10, 12, 14)
CELL_TYPES = ("rr", "track", "nonreward_remap")
MODELS = ("train0_test1", "train1_test0")
EDGES = tuple(-math.pi + i * (2 * math.pi / 44) for i in range(44)) + (math.pi,)
CENTERS = tuple(x + (EDGES[-1] - EDGES[-2]) / 2 for x in EDGES[:-1])
SCHEMA = "reward-relative-fig3c-input-v1"


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def exact(obj, fields, name):
    require(type(obj) is dict and set(obj) == set(fields), name + ": unexpected fields")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def valid_hash(value, name):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), name + ": invalid SHA256")


def angle(value):
    if value is None:
        return None
    require(type(value) in (int, float), "angles must be numbers or null for source NaN")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise InputError("invalid angle") from None
    require(math.isfinite(number) and -math.pi <= number <= math.pi,
            "angle outside finite [-pi,pi]; use null only for source NaN")
    return number


def tagged(number):
    if math.isnan(number):
        return {"value": None, "state": "nan"}
    if math.isinf(number):
        return {"value": None, "state": "positive_infinity" if number > 0 else "negative_infinity"}
    return {"value": number, "state": "finite"}


def _nanmean(values):
    values = [x for x in values if not math.isnan(x)]
    if not values:
        return math.nan
    if math.inf in values and -math.inf in values:
        return math.nan
    if math.inf in values:
        return math.inf
    if -math.inf in values:
        return -math.inf
    return statistics.fmean(values)


def _nanstd(values):
    values = [x for x in values if not math.isnan(x)]
    if not values or any(math.isinf(x) for x in values):
        return math.nan
    # Population SD (ddof=0), matching the source mathematical definition.
    # Floating-point reduction order is not asserted bitwise equal to NumPy.
    return statistics.pstdev(values)


def _divide(numerator, denominator):
    if math.isnan(numerator) or math.isnan(denominator):
        return math.nan
    if denominator == 0:
        return math.nan if numerator == 0 else math.copysign(math.inf, numerator)
    return numerator / denominator


def fold_profile(actual, predicted):
    """44 source intervals, with separate occupancy and finite-prediction counts."""
    require(type(actual) is list and type(predicted) is list and len(actual) == len(predicted),
            "actual/prediction lengths differ")
    buckets = [[] for _ in range(44)]
    occupancy = [0] * 44
    missing_actual = right_endpoint = 0
    for raw_actual, raw_predicted in zip(actual, predicted):
        a, p = angle(raw_actual), angle(raw_predicted)
        if a is None:
            missing_actual += 1
            continue
        if a == math.pi:
            right_endpoint += 1
            continue
        index = bisect.bisect_right(EDGES, a) - 1
        require(0 <= index < 44, "invalid source position bin")
        occupancy[index] += 1
        if p is not None:
            buckets[index].append(math.cos(p - a))
    return {"means": [_nanmean(x) for x in buckets], "occupancy": occupancy,
            "valid_predictions": [len(x) for x in buckets],
            "missing_actual": missing_actual, "excluded_positive_pi": right_endpoint}


def _folds(folds):
    require(type(folds) is list and len(folds) == 10, "exactly ten source folds required")
    seen, support, profiles, lengths = set(), [], [], []
    for fold in folds:
        exact(fold, ("sample_ids", "actual", "predicted"), "fold")
        ids = fold["sample_ids"]
        require(type(ids) is list and ids and all(type(x) is str and x for x in ids),
                "nonempty ordered sample identities required")
        require(len(ids) == len(set(ids)) and not (seen & set(ids)), "duplicate sample across source folds")
        seen.update(ids)
        require(type(fold["actual"]) is list and len(fold["actual"]) == len(ids), "target/sample length mismatch")
        profiles.append(fold_profile(fold["actual"], fold["predicted"]))
        support.append({"sample_ids": ids, "actual": [angle(x) for x in fold["actual"]]})
        lengths.append(len(ids))
    q, r = divmod(sum(lengths), 10)
    require(lengths == [q + (i < r) for i in range(10)], "source array_split fold ordering mismatch")
    return profiles, support, seen


def _profile_row(row):
    exact(row, ("animal", "day", "cell_type", "model", "folds", "shuffles"), "row")
    require(row["animal"] in ANIMALS and type(row["animal"]) is str, "unknown animal")
    require(type(row["day"]) is int and row["day"] in DAYS, "unknown switch day")
    require(type(row["cell_type"]) is str and row["cell_type"] in CELL_TYPES, "unknown cell class")
    require(type(row["model"]) is str and row["model"] in MODELS, "cross-switch model required")
    real, support, sample_ids = _folds(row["folds"])
    require(type(row["shuffles"]) is list and len(row["shuffles"]) == 100,
            "all100 source shuffle repeats required")
    repeat_means, repeat_counts = [], []
    for shuffle in row["shuffles"]:
        profiles, shuffled_support, _ = _folds(shuffle)
        require(shuffled_support == support, "shuffle changed source targets, sample identities or order")
        repeat_means.append([_nanmean(p["means"][b] for p in profiles) for b in range(44)])
        repeat_counts.append([sum(not math.isnan(p["means"][b]) for p in profiles) for b in range(44)])
    real_mean = [_nanmean(p["means"][b] for p in real) for b in range(44)]
    shuffle_mean = [_nanmean(p[b] for p in repeat_means) for b in range(44)]
    shuffle_sd = [_nanstd([p[b] for p in repeat_means]) for b in range(44)]
    z = [_divide(a - s, sd) for a, s, sd in zip(real_mean, shuffle_mean, shuffle_sd)]
    result = {k: row[k] for k in ("animal", "day", "cell_type", "model")}
    result.update({
        "row_input_sha256": digest(row), "test_support_sha256": digest(support),
        "real_fold_cosine": [[tagged(x) for x in p["means"]] for p in real],
        "real_fold_occupancy": [p["occupancy"] for p in real],
        "real_fold_valid_predictions": [p["valid_predictions"] for p in real],
        "real_fold_missing_actual": [p["missing_actual"] for p in real],
        "real_fold_excluded_positive_pi": [p["excluded_positive_pi"] for p in real],
        "shuffle_repeat_mean_cosine": [[tagged(x) for x in p] for p in repeat_means],
        "shuffle_repeat_valid_fold_counts": repeat_counts,
        "real_mean_cosine": [tagged(x) for x in real_mean],
        "shuffle_mean_cosine": [tagged(x) for x in shuffle_mean],
        "shuffle_population_sd": [tagged(x) for x in shuffle_sd],
        "zscore": [tagged(x) for x in z],
        "real_valid_fold_counts": [sum(not math.isnan(p["means"][b]) for p in real) for b in range(44)],
        "shuffle_valid_repeat_counts": [sum(not math.isnan(p[b]) for p in repeat_means) for b in range(44)],
    })
    return result, z, support, sample_ids


def profile_row(row):
    """Partial arithmetic API, not a complete cohort result or admission gate."""
    return _profile_row(row)[0]


def cohort_statistics(values):
    """Author mean/SEM for exactly11 mice; source SEM uses the full axis size."""
    require(type(values) is list and len(values) == 11, "all11 mouse values required")
    numbers = []
    for value in values:
        if value is None:
            numbers.append(math.nan)
        else:
            require(type(value) in (int, float), "invalid cohort number")
            numbers.append(float(value))
    return {"mean": tagged(_nanmean(numbers)),
            "sem": tagged(_nanstd(numbers) / math.sqrt(10)),
            "total_mice": 11, "non_nan_mice": sum(not math.isnan(x) for x in numbers),
            "finite_mice": sum(math.isfinite(x) for x in numbers)}


def score_panel(panel):
    exact(panel, ("schema", "source_commit", "preparation_sha256", "fold_receipt_sha256", "rows"), "panel")
    require(panel["schema"] == SCHEMA and panel["source_commit"] == COMMIT, "wrong source/schema")
    for field in ("preparation_sha256", "fold_receipt_sha256"):
        valid_hash(panel[field], field)
    require(type(panel["rows"]) is list and len(panel["rows"]) == 462,
            "all11mice x7days x3classes x2cross-switch directions required")
    expected = {(a, d, c, m) for a in ANIMALS for d in DAYS for c in CELL_TYPES for m in MODELS}
    keys = []
    for row in panel["rows"]:
        require(type(row) is dict, "invalid row")
        key = tuple(row.get(k) for k in ("animal", "day", "cell_type", "model"))
        require(all(type(x) in (str, int) for x in key), "invalid condition identity")
        keys.append(key)
    require(len(set(keys)) == len(keys) and set(keys) == expected, "duplicate or missing cohort condition")
    results, zscores, shared_support, observed = [], {}, {}, {}
    for row in panel["rows"]:
        result, z, support, ids = _profile_row(row)
        key = tuple(row[k] for k in ("animal", "day", "cell_type", "model"))
        condition = (row["animal"], row["day"], row["model"])
        fingerprint = digest(support)
        require(condition not in shared_support or shared_support[condition] == fingerprint,
                "ordered test support differs across cell populations")
        shared_support[condition] = fingerprint
        observed[condition] = ids
        results.append(result)
        zscores[key] = z
    for a in ANIMALS:
        for d in DAYS:
            require(not (observed[a, d, MODELS[0]] & observed[a, d, MODELS[1]]),
                    "before and after test support overlaps")
    means, source_export = [], []
    for d in DAYS:
        for c in CELL_TYPES:
            for m in MODELS:
                means.append({"day": d, "cell_type": c, "model": m,
                              "bins": [cohort_statistics([zscores[a, d, c, m][b] for a in ANIMALS])
                                       for b in range(44)]})
            if d in (3, 14):
                for a in ANIMALS:
                    source_export.append({"animal": a, "mouse_num": int(a.removeprefix("GCAMP")),
                                          "switch": 1 if d == 3 else 7, "day": d, "cell_type": c,
                                          "model": MODELS[0],
                                          "zscore": [tagged(x) for x in zscores[a, d, c, MODELS[0]]]})
    return {"schema": "reward-relative-fig3c-profile-result-v1", "task_id": TASK,
            "source_commit": COMMIT, "input_sha256": digest(panel),
            "preparation_sha256": panel["preparation_sha256"],
            "fold_receipt_sha256": panel["fold_receipt_sha256"],
            "position_edges_radians": list(EDGES), "position_centers_radians": list(CENTERS),
            "rows": sorted(results, key=lambda x: (x["animal"], x["day"], x["cell_type"], x["model"])),
            "cohort_profiles": means, "figure3c_source_export": source_export,
            "qualification": "owner-side arithmetic only; source/native reference and nonfinite admission unresolved",
            "paper_win": None, "scientific_readiness": "unknown"}


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    def reject(value):
        raise InputError("nonfinite JSON constant; encode source NaN as null: " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=_pairs, parse_constant=reject)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = score_panel(read_json(args.panel))
    with Path(args.output).open("x") as handle:
        json.dump(result, handle, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


if __name__ == "__main__":
    main()
