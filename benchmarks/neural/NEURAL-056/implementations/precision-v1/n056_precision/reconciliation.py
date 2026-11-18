"""Compare declared Pearson implementations on the same complete admitted study.

This operator diagnostic does not replace the preserved legacy collector, select
the new kernel in a programme, or turn arithmetic agreement into qualification.
It never treats a tolerance match as proof of historical paper reproduction.
"""
from __future__ import annotations

from n056.bank_a import correlation as predecessor_correlation, macro
from n056.core import digest, need
from n056.evaluation import collect
from n056.protocol import ARMS, PEOPLE, ROLES

from .correlation import correlation
from .evaluation import _target_arrays

REVISION = "neural056-pearson-precision-v1"
TOLERANCE = 1e-12


def _delta(old, new):
    """Retain undefined transitions and finite differences without dropping cells."""
    need(len(old) == len(new) == 1700, "all 1700 numerical comparison cells")
    finite = [(a, b) for a, b in zip(old, new) if a is not None and b is not None]
    changed_definedness = sum((a is None) != (b is None) for a, b in zip(old, new))
    differences = [abs(a - b) for a, b in finite]
    return {
        "total_cells": 1700,
        "both_defined_cells": len(finite),
        "both_undefined_cells": sum(a is None and b is None for a, b in zip(old, new)),
        "changed_definedness_cells": changed_definedness,
        "finite_cells_beyond_tolerance": sum(d > TOLERANCE for d in differences),
        "maximum_finite_absolute_difference": max(differences, default=None),
        "agrees_within_tolerance": not changed_definedness and all(d <= TOLERANCE for d in differences),
    }


def _aggregate(means):
    primary = {arm: macro([means[arm][person] for person in PEOPLE]) for arm in ARMS}
    controls = {}
    for control in ("low_level", "response_permuted"):
        by_person = {
            person: None if means["representation"][person] is None or means[control][person] is None
            else means["representation"][person] - means[control][person]
            for person in PEOPLE
        }
        controls[control] = {"by_person": by_person, "mean": macro(list(by_person.values()))}
    return {"primary_equal_person_mean": primary, "paired_controls": controls}


def compare_versions(panel, records, protocol, budget, *, numerical_revision):
    """Admit all 120 original products before opening any protected target.

    Both declared kernels receive the same measured target and prediction arrays.
    The result exposes arithmetic disagreements, including definedness changes;
    it does not waive or relabel the old legacy reconciliation's equality gate.
    Actual operation/storage bounds must be admitted separately by the operator.
    """
    need(numerical_revision == REVISION, "explicit supported numerical revision required")
    admitted = collect(records, protocol, budget)
    expected = {(role, person, arm) for role in ROLES for person in PEOPLE for arm in ARMS}
    need(set(admitted) == expected, "complete distinct admitted numerical-comparison roster")
    means = {version: {role: {arm: {} for arm in ARMS} for role in ROLES}
             for version in ("predecessor", "precision")}
    blocks, reliability = {}, {}
    for person in PEOPLE:
        targets = _target_arrays(panel.outer_target(person))
        blocks[person] = {}
        for role in ROLES:
            blocks[person][role] = {}
            for arm in ARMS:
                prediction = admitted[(role, person, arm)]
                old = predecessor_correlation(targets["mean"], prediction)
                new = correlation(targets["mean"], prediction)
                means["predecessor"][role][arm][person] = old["mean"]
                means["precision"][role][arm][person] = new["mean"]
                blocks[person][role][arm] = {
                    "raw": _delta(old["raw"], new["raw"]),
                    "score": _delta(old["score"], new["score"]),
                    "predecessor": {k: old[k] for k in ("constant_target", "constant_prediction", "mean")},
                    "precision": {k: new[k] for k in ("constant_target", "constant_prediction", "mean")},
                }
        old = predecessor_correlation(targets["half_odd"], targets["half_even"])
        new = correlation(targets["half_odd"], targets["half_even"])
        reliability[person] = {
            "raw": _delta(old["raw"], new["raw"]),
            "predecessor_mean": None if old["constant_target"] or old["constant_prediction"] else old["mean"],
            "precision_mean": None if new["constant_target"] or new["constant_prediction"] else new["mean"],
        }
    summaries = {version: {role: _aggregate(means[version][role]) for role in ROLES} for version in means}
    prediction_agreement = all(
        blocks[person][role][arm][kind]["agrees_within_tolerance"]
        for person in PEOPLE for role in ROLES for arm in ARMS for kind in ("raw", "score")
    )
    reliability_agreement = all(reliability[person]["raw"]["agrees_within_tolerance"] for person in PEOPLE)
    return {
        "schema": "neural056_numerical_revision_comparison_v1",
        "protocol_id": digest(protocol),
        "predecessor": "preserved_n056.bank_a.correlation",
        "numerical_revision": REVISION,
        "tolerance": TOLERANCE,
        "all_final_blocks": 120,
        "cells_per_block": 1700,
        "images_per_block": 200,
        "observed_numerical_agreement": prediction_agreement and reliability_agreement,
        "observed_prediction_numerical_agreement": prediction_agreement,
        "observed_reliability_numerical_agreement": reliability_agreement,
        "blocks": blocks,
        "aggregates": summaries,
        "descriptive_split_half_reliability": reliability,
        "reliability_correction_applied": False,
        "legacy_collector_executed": False,
        "programme_revision_selected": False,
        "historical_score_reproduction": False,
        "scientifically_qualified": False,
        "interpretation": "Same admitted predictions and target arrays evaluated by two declared kernels; disagreements are recorded, not waived.",
    }
