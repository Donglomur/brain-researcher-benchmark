"""Evaluator-only NB prediction scoring for the prospective AHN extension.

This file neither fits models nor proves fold isolation. It must receive trusted
private truth and a separately audited full-cohort roster. Authentic R parity
and the protected runner are still admission gates; this is SOURCE construction.
"""
from collections import Counter
import argparse
import hashlib
import json
import math
from pathlib import Path

ANIMALS = 28
REGIONS = 452
GROUPS = {"Ctrl": 8, "NS": 10, "S": 10}
ROWS = ANIMALS * REGIONS


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(x, name, positive=False):
    need(type(x) in (int, float) and math.isfinite(x), name + " must be finite")
    if positive:
        need(x > 0, name + " must be positive")
    return float(x)


def text_id(x):
    return type(x) is str and 0 < len(x) <= 128 and not any(ord(c) < 32 for c in x)


def exact_keys(obj, keys, name):
    need(type(obj) is dict and set(obj) == set(keys), name + " fields mismatch")


def validate_roster(obj):
    exact_keys(obj, ("schema", "animals", "regions", "binding"), "roster")
    need(obj["schema"] == "ahn-evaluator-roster-v1", "roster schema")
    need(type(obj["animals"]) is list and len(obj["animals"]) == ANIMALS, "all 28 animals required")
    animals = {}
    for row in obj["animals"]:
        exact_keys(row, ("id", "group"), "animal")
        need(text_id(row["id"]) and row["id"] not in animals, "unique animal identifier required")
        need(row["group"] in GROUPS, "unknown animal group")
        animals[row["id"]] = row["group"]
    need(Counter(animals.values()) == Counter(GROUPS), "expected 8 Ctrl / 10 NS / 10 S")
    regions = obj["regions"]
    need(type(regions) is list and len(regions) == REGIONS, "all 452 regions required")
    need(all(text_id(r) for r in regions) and len(set(regions)) == REGIONS, "unique region identifiers required")
    need("AHN" in regions, "AHN absent")
    exact_keys(obj["binding"], ("input_manifest_sha256", "cohort_review_sha256"), "binding")
    for value in obj["binding"].values():
        need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             "binding requires SHA256")
    return animals, regions


def nb_logpmf(count, mean, size):
    """Stable per-count NB2 log recurrence; no lgamma ratio cancellation.

    The 1,000,000-count domain is an implementation limit, not a data exclusion:
    an out-of-domain real count holds admission for the entire task. Cost is
    O(count), so authentic execution must first budget the complete sum of counts.
    """
    need(type(count) is int and 0 <= count <= 1000000, "count outside supported integer domain")
    mean = number(mean, "mean", True)
    size = number(size, "size", True)
    if mean <= size:
        ratio = mean / size
        log_normalizer = math.log1p(ratio)
        # ratio can underflow at huge size; -mean is the correctly rounded
        # limiting term at that extreme, rather than falsely reporting log P0=0.
        base = -mean if ratio == 0 else -size * log_normalizer
        log_mean = math.log(mean)
        terms = (log_mean - math.log(j + 1) + math.log1p(j / size) - log_normalizer
                 for j in range(count))
    else:
        log_normalizer = math.log1p(size / mean)
        base = size * (math.log(size) - math.log(mean) - log_normalizer)
        terms = (math.log(size + j) - math.log(j + 1) - log_normalizer
                 for j in range(count))
    value = math.fsum((base, math.fsum(terms)))
    need(math.isfinite(value) and value <= 0, "NB numerical result invalid; no clipping allowed")
    return value


def table(obj, kind, animals, regions):
    exact_keys(obj, ("schema", "rows"), kind)
    expected_schema = {"truth": "ahn-count-truth-v1", "prediction": "ahn-nb-predictions-v1"}[kind]
    need(obj["schema"] == expected_schema, kind + " schema")
    need(type(obj["rows"]) is list and len(obj["rows"]) == ROWS, kind + " requires all 12656 rows")
    result = {}
    region_set = set(regions)
    for row in obj["rows"]:
        keys = ("animal", "region", "count") if kind == "truth" else ("animal", "region", "mean", "size")
        exact_keys(row, keys, kind + " row")
        need(text_id(row["animal"]) and row["animal"] in animals, "unknown animal")
        need(text_id(row["region"]) and row["region"] in region_set, "unknown region")
        key = (row["animal"], row["region"])
        need(key not in result, "duplicate animal-region pair")
        if kind == "truth":
            need(type(row["count"]) is int and 0 <= row["count"] <= 1000000, "invalid count")
            result[key] = row["count"]
        else:
            result[key] = (number(row["mean"], "mean", True), number(row["size"], "size", True))
    need(set(result) == {(a, r) for a in animals for r in regions}, "incomplete target universe")
    return result


def score(roster, truth, prediction):
    animals, regions = validate_roster(roster)
    target = table(truth, "truth", animals, regions)
    pred = table(prediction, "prediction", animals, regions)
    truth_digest = hashlib.sha256()
    for (animal, region), count in sorted(target.items()):
        truth_digest.update((json.dumps([animal, region, count], ensure_ascii=True, separators=(",", ":")) + "\n").encode())
    binding = dict(roster["binding"], roster_sha256=hashlib.sha256(json.dumps(roster, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest(), truth_sha256=truth_digest.hexdigest())
    by_animal = []
    for animal, group in animals.items():
        masses = [nb_logpmf(target[animal, r], *pred[animal, r]) for r in regions]
        lpd = math.fsum(masses) / REGIONS
        by_animal.append({"animal": animal, "group": group, "regions": REGIONS, "mean_log_predictive_density": lpd})
    primary = math.fsum(x["mean_log_predictive_density"] for x in by_animal) / ANIMALS
    by_group = {}
    for group, n in GROUPS.items():
        rows = [x["mean_log_predictive_density"] for x in by_animal if x["group"] == group]
        need(len(rows) == n, "group denominator changed")
        by_group[group] = {"animals": n, "mean_log_predictive_density": math.fsum(rows) / n}
    return {"schema": "ahn-nb-score-v1", "higher_is_better": True,
            "primary": primary, "animals": ANIMALS, "regions": REGIONS, "targets": ROWS, "evaluator_binding": binding,
            "by_group": by_group, "by_animal": by_animal,
            "scope": "Mean marginal predictive density; not a joint network likelihood or evidence of causal effect.",
            "protected_runner_verified": False, "authentic_reference_parity_verified": False}


def paired_difference(candidate, baseline):
    """Full animal-paired descriptive contrast; no edge/cell pseudo-replication."""
    for obj in (candidate, baseline):
        need(obj.get("schema") == "ahn-nb-score-v1" and obj.get("targets") == ROWS, "score scope mismatch")
        need(len(obj.get("by_animal", [])) == ANIMALS, "score needs all 28 animal summaries")
    binding_fields = ("input_manifest_sha256", "cohort_review_sha256", "roster_sha256", "truth_sha256")
    for obj in (candidate, baseline):
        exact_keys(obj.get("evaluator_binding"), binding_fields, "score binding")
        for value in obj["evaluator_binding"].values():
            need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "invalid score binding")
        need(Counter(x["group"] for x in obj["by_animal"]) == Counter(GROUPS), "paired group denominator mismatch")
    need(candidate["evaluator_binding"] == baseline["evaluator_binding"], "different evaluator input/cohort/truth binding")
    left = {x["animal"]: x for x in candidate["by_animal"]}
    right = {x["animal"]: x for x in baseline["by_animal"]}
    need(len(left) == ANIMALS and set(left) == set(right), "paired animal identities mismatch")
    deltas = []
    for animal, row in left.items():
        other = right[animal]
        need(row["group"] == other["group"] and row["regions"] == other["regions"] == REGIONS, "pair mismatch")
        value = number(row["mean_log_predictive_density"], "candidate") - number(other["mean_log_predictive_density"], "baseline")
        need(math.isfinite(value), "nonfinite paired difference")
        deltas.append({"animal": animal, "group": row["group"], "delta_lpd": value})
    return {"schema": "ahn-paired-lpd-v1", "animals": ANIMALS,
            "delta_mean_lpd": math.fsum(x["delta_lpd"] for x in deltas) / ANIMALS,
            "by_animal": deltas,
            "inference": "Descriptive only. Outer LOAO folds overlap in training; a simple independent-t or binomial sign test is not certified."}


def unique_object(items):
    result = {}
    for key, value in items:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(path, limit):
    p = Path(path)
    need(p.stat().st_size <= limit, "JSON byte cap")
    data = p.read_bytes()
    need(len(data) <= limit, "JSON byte cap")
    return json.loads(data.decode("utf8"), object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON constant")))


def main():
    parser = argparse.ArgumentParser()
    for name in ("roster", "truth", "predictions", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = score(load(args.roster, 262144), load(args.truth, 8388608), load(args.predictions, 8388608))
    payload = (json.dumps(result, allow_nan=False, sort_keys=True, indent=2) + "\n").encode()
    need(len(payload) <= 65536, "score byte cap")
    with Path(args.output).open("xb") as out:
        out.write(payload)


if __name__ == "__main__":
    main()
