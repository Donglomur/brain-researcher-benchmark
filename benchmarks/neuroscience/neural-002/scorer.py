"""Trusted full32-person scoring; no labels or scores go to candidate workers."""
import math
import random
from collections import Counter
from contract import PEOPLE, CELLS, CLASSES, require, finite, integer


def _targets(targets):
    require(isinstance(targets, list) and len(targets) == 9984, "full target count")
    lookup, counts = {}, Counter()
    for row in targets:
        require(isinstance(row, dict) and set(row) == {"id", "participant", "cell", "label"}, "target schema")
        uid = row["id"]
        require(isinstance(uid, str) and len(uid) == 64 and all(c in "0123456789abcdef" for c in uid)
                and uid not in lookup, "unique opaque target ID")
        require(row["participant"] in PEOPLE and row["cell"] in CELLS, "target group")
        integer(row["label"], 0, 25, "target class")
        counts[row["participant"], row["cell"], row["label"]] += 1
        lookup[uid] = row
    require(set(counts) == {(p, c, y) for p in PEOPLE for c in CELLS for y in range(CLASSES)}
            and set(counts.values()) == {2}, "complete32×6×26×2 scoring support")
    return lookup


def score(targets, predictions):
    lookup = _targets(targets)
    require(isinstance(predictions, list) and len(predictions) == len(lookup), "prediction count")
    hits, loss, seen, confusion = Counter(), Counter(), set(), {}
    for row in predictions:
        require(isinstance(row, dict) and set(row) == {"id", "probabilities"}, "prediction schema")
        uid, probs = row["id"], row["probabilities"]
        require(isinstance(uid, str) and uid in lookup and uid not in seen, "unknown/duplicate prediction ID")
        seen.add(uid)
        require(isinstance(probs, list) and len(probs) == CLASSES, "26 probabilities required")
        probs = [finite(x, "probabilities must be finite numbers") for x in probs]
        require(all(0 <= x <= 1 for x in probs) and abs(math.fsum(probs) - 1) <= 1e-6,
                "probability simplex")
        truth = lookup[uid]
        p, c, y = truth["participant"], truth["cell"], truth["label"]
        predicted = max(range(CLASSES), key=lambda i: probs[i])  # lowest-index tie
        hits[p, c, y] += int(predicted == y)
        loss[p, c] += -math.log(max(probs[y], 1e-15))
        confusion.setdefault((p, c), [[0] * CLASSES for _ in range(CLASSES)])[y][predicted] += 1
    require(seen == set(lookup), "missing predictions")
    cells, persons = [], {}
    for p in PEOPLE:
        balances = []
        for c in CELLS:
            ba = math.fsum(hits[p, c, y] / 2 for y in range(CLASSES)) / CLASSES
            balances.append(ba)
            cells.append({"participant": p, "cell": c, "n": 52,
                          "balanced_accuracy": ba, "log_loss": loss[p, c] / 52,
                          "confusion": confusion[p, c]})
        persons[p] = math.fsum(balances) / len(CELLS)
    return {"primary": math.fsum(persons.values()) / len(PEOPLE),
            "metric": "equal-person mean of equal-six-cell balanced accuracy",
            "participant_scores": persons, "cells": cells, "n": len(lookup),
            "chance": 1 / CLASSES, "probability_tie": "lowest class index",
            "qualification": False}


def paired_interval(candidate_scores, reference_scores, *, seed=2002, repetitions=10000):
    require(set(candidate_scores) == set(reference_scores) == set(PEOPLE), "paired all32-person scores")
    integer(seed, 0, 2**63 - 1, "bootstrap seed")
    integer(repetitions, 1000, 100000, "bootstrap repetitions")
    differences = [finite(candidate_scores[p], "candidate score") -
                   finite(reference_scores[p], "reference score") for p in PEOPLE]
    rng = random.Random(seed)
    draws = sorted(math.fsum(rng.choice(differences) for _ in PEOPLE) / len(PEOPLE)
                   for _ in range(repetitions))
    return {"paired_difference": math.fsum(differences) / len(PEOPLE),
            "percentile95": [draws[int(.025 * repetitions)], draws[int(.975 * repetitions) - 1]],
            "unit": "participant", "repetitions": repetitions, "seed": seed,
            "interpretation": "descriptive paired participant bootstrap; not a preregistered significance claim"}
