"""NEURAL-097's fixed, protected endpoint; no source/data loading or fitting.

Call only after the trusted controller has admitted predictions and joined the
complete protected case universe. This module cannot authenticate that join.
The historical registered-runtime implementation remains unchanged.
"""
import math

ARMS = ("SIGNAL", "PRE", "NUISANCE", "SIGNAL_NUISANCE", "PRE_NUISANCE")
RELEVANCES = ("Irrelevant", "Relevant non-target")
DURATIONS = ("500ms", "1000ms", "1500ms")
ORIENTATIONS = ("Center", "Left", "Right")
METRICS = ("balanced_accuracy", "legacy_logloss", "balanced_logloss", "balanced_brier")


class EndpointError(ValueError):
    """Malformed endpoint input; never an invitation to omit a case."""


def _need(condition, message):
    if not condition:
        raise EndpointError(message)


def _mean(values):
    return (math.fsum(values) / len(values)
            if values and all(value is not None for value in values) else None)


def _index(targets, predictions):
    _need(type(targets) is dict and targets, "Complete private target map required")
    _need(all(type(key) is str and key for key in targets), "Nonempty string case identities required")
    _need(type(predictions) is dict and set(predictions) == set(ARMS), "All five prediction arms required")
    expected = set(targets)
    for arm in ARMS:
        supplied = predictions[arm]
        _need(type(supplied) is dict and set(supplied) == expected,
              "Every arm must have the exact complete case identities")
        _need(all(type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)
                  for value in supplied.values()), "Finite nonboolean probabilities in [0,1] required")

    # One target pass. Every valid row enters one and only one fixed cell.
    cells = {(person, rel, duration, orientation): ([], [[], []])
             for person in range(33) for rel in RELEVANCES
             for duration in DURATIONS for orientation in ORIENTATIONS}
    people = set()
    for key, row in targets.items():
        _need(type(row) is dict and {"person_index", "y", "stratum"} <= set(row),
              "Target row requires participant, class and stratum")
        person, y, stratum = row["person_index"], row["y"], row["stratum"]
        _need(type(person) is int and 0 <= person < 33, "Participant index must be an integer in [0,32]")
        _need(type(y) is int and y in (0, 1), "Face-positive integer class required")
        _need(type(stratum) is list and len(stratum) == 3,
              "Stratum must be exactly [relevance, duration, orientation]")
        _need(all(type(value) is str for value in stratum)
              and stratum[0] in RELEVANCES and stratum[1] in DURATIONS
              and stratum[2] in ORIENTATIONS, "Unknown stratum value")
        ids, groups = cells[(person, *stratum)]
        ids.append(key)
        groups[y].append(key)
        people.add(person)
    _need(people == set(range(33)), "All 33 independent participants required")
    return cells


def evaluate(targets, predictions):
    """Return the historical metric/report structure on a pre-admitted panel.

    Five matched arms; 33 participants; two relevances; nine cells per person.
    Both image halves must already be pooled exactly once by the controller.
    Missing support yields nulls without changing the panel denominator.
    Additional trusted target metadata is ignored and never returned.
    """
    index = _index(targets, predictions)
    people = []
    full_support = all(all(groups) for _, groups in index.values())
    for person_index in range(33):
        person = {"person_index": person_index, "arms": {}}
        for arm in ARMS:
            supplied = predictions[arm]
            per_relevance = {}
            for relevance in RELEVANCES:
                cells = []
                for duration in DURATIONS:
                    for orientation in ORIENTATIONS:
                        ids, groups = index[(person_index, relevance, duration, orientation)]
                        recalls, losses, briers = [], [], []
                        for y, group in enumerate(groups):
                            recalls.append(_mean([float((supplied[key] >= .5) == bool(y)) for key in group]))
                            losses.append(_mean([-math.log(max(1e-15, supplied[key] if y else 1 - supplied[key]))
                                                 for key in group]))
                            briers.append(_mean([(supplied[key] - y) ** 2 for key in group]))
                        legacy = _mean([-math.log(max(1e-15, supplied[key] if targets[key]["y"]
                                                       else 1 - supplied[key])) for key in ids])
                        cells.append({
                            "duration": duration, "orientation": orientation, "n": len(ids),
                            "class_counts": [len(group) for group in groups],
                            "balanced_accuracy": _mean(recalls), "legacy_logloss": legacy,
                            "balanced_logloss": _mean(losses), "balanced_brier": _mean(briers),
                            "unavailable_reasons": [] if all(groups) else ["missing_class_support"],
                        })
                per_relevance[relevance] = {
                    "cells": cells, **{metric: _mean([cell[metric] for cell in cells]) for metric in METRICS}
                }
            person["arms"][arm] = per_relevance
        people.append(person)
    macro = {arm: {rel: {metric: _mean([person["arms"][arm][rel][metric] for person in people])
                          for metric in METRICS} for rel in RELEVANCES} for arm in ARMS}
    return {
        "persons": people, "macro": macro,
        "primary_value": macro["SIGNAL"]["Irrelevant"]["balanced_accuracy"],
        "expected_report_cells_per_arm": 594, "expected_class_counts_per_arm": 1188,
        "full_support_complete": full_support,
        "population_or_theory_verdict": False, "scientific_qualification": False,
    }
