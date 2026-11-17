"""NEURAL-086 arithmetic on an independently frozen, protected word census.

This evaluator component accepts already admitted predictions. It neither opens
campaign targets nor replaces the existing target-last admission barrier.
"""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

EPSILON = 1e-6
KEY_FIELDS = ("person", "item", "word_index", "label", "repetition_ordinal")
METADATA_FIELDS = ("block", "duration_seconds", "window_duration_ms")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def mean(values):
    return sum(values) / len(values)


def occurrence_key(row):
    require(type(row) is dict, "row_object")
    require(all(field in row for field in KEY_FIELDS), "occurrence_identity_fields")
    require(all(type(row[field]) is str and row[field] for field in ("person", "item")), "person_item_identity")
    require(type(row["word_index"]) is int and row["word_index"] >= 0, "original_word_position")
    require(type(row["label"]) is int and row["label"] in (0, 1), "source_condition")
    require(type(row["repetition_ordinal"]) is int and row["repetition_ordinal"] >= 0, "original_repeat_ordinal")
    return tuple(row[field] for field in KEY_FIELDS)


def indexed(rows, predictions):
    require(type(rows) is list, "rows_list")
    result = {}
    ids = set()
    for row in rows:
        key = occurrence_key(row)
        require(key not in result, "duplicate_source_occurrence")
        if "id" in row:
            require(type(row["id"]) is str and row["id"] and row["id"] not in ids, "duplicate_or_invalid_job_row_id")
            ids.add(row["id"])
        if predictions:
            require(finite_number(row.get("p")) and 0 <= row["p"] <= 1, "probability")
        for field in METADATA_FIELDS:
            if field in row and row[field] is not None:
                require(finite_number(row[field]), "source_metadata_number")
        result[key] = row
    return result


def log_loss(label, probability):
    q = min(1 - EPSILON, max(EPSILON, probability))
    return -math.log(q if label else 1 - q)


def cells(index):
    repetitions = defaultdict(list)
    for (person, item, word, label, _repeat), row in index.items():
        repetitions[person, item, word, label].append(row["p"])
    words = defaultdict(dict)
    for (person, item, word, label), probabilities in repetitions.items():
        words[person, item, word][label] = {
            "loss": mean([log_loss(label, p) for p in probabilities]),
            "accuracy": mean([int((p >= 0.5) == bool(label)) for p in probabilities]),
            "occurrences": len(probabilities),
        }
    by_cell = defaultdict(list)
    for (person, item, word), classes in words.items():
        require(set(classes) == {0, 1}, "unpaired_word_census")
        by_cell[person, item].append({
            "word": word,
            "loss": mean([classes[label]["loss"] for label in (0, 1)]),
            "accuracy": mean([classes[label]["accuracy"] for label in (0, 1)]),
            "occurrences": sum(classes[label]["occurrences"] for label in (0, 1)),
        })
    return {
        key: {
            "loss": mean([word["loss"] for word in words0]),
            "accuracy": mean([word["accuracy"] for word in words0]),
            "paired_words": len(words0),
            "occurrences": sum(word["occurrences"] for word in words0),
        }
        for key, words0 in by_cell.items()
    }


def percentile(values, quantile):
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)


def crossed(matrix, people, items):
    """Preserve the source seed, draw order, count and fixed-prediction scope."""
    person_means = {person: mean([matrix[person, item] for item in items]) for person in people}
    item_means = {item: mean([matrix[person, item] for person in people]) for item in items}
    rng = random.Random(194086)
    draws = []
    for _ in range(1000):
        sampled_people = [rng.randrange(18) for _ in range(18)]
        sampled_items = [rng.randrange(len(items)) for _ in items]
        draws.append(mean([matrix[people[person], items[item]] for person in sampled_people for item in sampled_items]))
    return {
        "mean": mean(list(person_means.values())),
        "person_means": person_means,
        "item_means": item_means,
        "descriptive_person_SE": statistics.stdev(person_means.values()) / math.sqrt(18),
        "descriptive_item_SE": statistics.stdev(item_means.values()) / math.sqrt(len(items)) if len(items) > 1 else None,
        "descriptive_crossed_resampling_interval95": [percentile(draws, 0.025), percentile(draws, 0.975)],
        "seed": 194086,
        "resamples": 1000,
        "model_refit": False,
        "population_coverage_claim": False,
    }


def paired_contrast(base, plus, people, items, expected_support):
    """Compute loss(base)-loss(plus) with exact arm/census occurrence equality.

    `expected_support` is the protected, source-derived eligible query census,
    frozen before predictions. It must not be inferred from either submitted arm.
    Job-specific HMAC row IDs differ by arm and are not cross-arm identities.
    """
    require(type(people) is list and len(people) == 18 and all(type(p) is str and p for p in people), "eighteen_people")
    require(len(set(people)) == 18, "distinct_people")
    require(type(items) is list and items and all(type(i) is str and i for i in items), "nonempty_items")
    require(len(set(items)) == len(items), "distinct_items")
    expected = indexed(expected_support, predictions=False)
    left = indexed(base, predictions=True)
    right = indexed(plus, predictions=True)
    require(set(left) == set(expected), "base_census_support")
    require(set(right) == set(expected), "plus_census_support")
    rectangle = {(person, item) for person in people for item in items}
    require(all(key[:2] in rectangle for key in expected), "extra_comparison_cell")
    classes = defaultdict(set)
    for key, source in expected.items():
        classes[key[:3]].add(key[3])
        for row in (left[key], right[key]):
            for field in METADATA_FIELDS:
                require((field in source) == (field in row) and source.get(field) == row.get(field), "source_occurrence_metadata")
    require(all(labels == {0, 1} for labels in classes.values()), "unpaired_word_census")
    # Fixed ordering makes row permutations immaterial without changing the
    # source's explicitly ordered person/item resampling axes.
    left = {key: left[key] for key in sorted(left)}
    right = {key: right[key] for key in sorted(right)}
    a, b = cells(left), cells(right)
    missing = sorted(rectangle - set(a))
    matrix = {key: a[key]["loss"] - b[key]["loss"] for key in sorted(a)}
    ordered_rectangle = [(person, item) for person in people for item in items]
    support_body = [{field: source[field] for field in KEY_FIELDS + METADATA_FIELDS if field in source} for _, source in sorted(expected.items())]
    support_digest = hashlib.sha256(json.dumps(support_body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "base_loss": None if missing else mean([a[key]["loss"] for key in ordered_rectangle]),
        "plus_loss": None if missing else mean([b[key]["loss"] for key in ordered_rectangle]),
        "base_balanced_accuracy": None if missing else mean([a[key]["accuracy"] for key in ordered_rectangle]),
        "plus_balanced_accuracy": None if missing else mean([b[key]["accuracy"] for key in ordered_rectangle]),
        "signed_difference": None if missing else mean(list(matrix.values())),
        "complete_support": not missing,
        "missing_cells": [list(key) for key in missing],
        "expected_person_item_cells": len(rectangle),
        "supported_person_item_cells": len(a),
        "expected_word_occurrences": len(expected),
        "support_sha256": support_digest,
        "paired_cell_matrix": [{
            "person": person, "item": item,
            "base_loss": a[person, item]["loss"],
            "plus_loss": b[person, item]["loss"],
            "difference": matrix[person, item],
            "paired_words": a[person, item]["paired_words"],
            "word_occurrences": a[person, item]["occurrences"],
        } for person, item in sorted(a)],
        "uncertainty": None if missing else crossed(matrix, people, items),
        "interpretation": "finite observed-panel procedure contrast; not conditional information, neural origin or causal demand",
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_JSON_key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    packet = json.loads(args.packet.read_text(), object_pairs_hook=unique_object,
                        parse_constant=lambda _value: require(False, "nonfinite_JSON"))
    require(type(packet) is dict and set(packet) == {"base", "plus", "people", "items", "expected_support"}, "packet_keys")
    report = paired_contrast(**packet)
    # Refusals do not create an output. Existing results cannot be overwritten.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, allow_nan=False, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
