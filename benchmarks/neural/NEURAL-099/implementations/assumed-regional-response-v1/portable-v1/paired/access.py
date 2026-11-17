"""Metadata-only profiles and frozen grouping for the selected zero-label pair.

No history, counts, response labels, packets, providers or models are opened.
Five outer folds are grouping/completion barriers only in these profiles; they
do not authorize training, validation labels, selection or refitting. The
separate trained-programme condition is unchanged.

The exact namespace NEURAL-099|condition-b|outer-v1| is retained from the selected
condition-b schedule. UTF-8 animal IDs are ordered by their SHA-256 hex digest
and assigned by rank modulo five. Reusing this namespace does not expand the
zero-label profiles' information access.
"""

import hashlib
import json

from observations import ObservationAdapter
import transports


HASH_NAMESPACE = "NEURAL-099|condition-b|outer-v1|"
PRODUCTION_CASE_HASH = "508bdf026c6c223cc00c0a66c8ca56a6a70daed8e3acab57605e69e5c1ef4da3"
PRODUCTION_COUNTS = {
    "animals": 26, "assets": 26, "trials": 5238,
    "cells": 49, "clusters": 1387, "cases": 9867,
}
GENERATED_CASE_LIMIT = 128


def validate_profile(value):
    """Validate through the selected transport policy and return a fresh copy."""
    return transports._profile(value)


def profile(condition_id):
    """Create exactly one of the two selected nine-field condition profiles."""
    if type(condition_id) is not str or condition_id not in transports.CONDITIONS:
        raise ValueError("Unknown selected condition ID")
    return validate_profile({
        "condition_id": condition_id,
        "mode": transports.CONDITIONS[condition_id],
        "information_condition": "timing_history",
        "demonstration_labels": 0,
        "benchmark_response_labels": "none",
        "selection_training_refit": "none",
        "state_scope": "fresh_per_trial",
        "feedback": "none",
        "memory": "none",
    })


def _no_history(*args, **kwargs):
    raise AssertionError("Metadata scheduling must never request history or response values")


def _canonical_cases(private_cases):
    """Match frozen count_packet.validate_cases clock normalization and order.

    ObservationAdapter has already checked all field types and relationships.
    Production additionally requires the input list to be in the frozen packet
    order; this helper does not sort away a changed private packet ordering.
    """
    result = []
    for original in private_cases:
        case = dict(original)
        case["trial_start_seconds"] = float(case["trial_start_seconds"])
        case["trial_stop_seconds"] = float(case["trial_stop_seconds"])
        result.append(case)
    return result


def _canonical_case_hash(cases):
    """Exact frozen count_packet._case_hash recipe, over normalized ordered cases."""
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, case in enumerate(cases):
        if index:
            digest.update(b",")
        digest.update(json.dumps(case, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False).encode("utf-8"))
    digest.update(b"]")
    return digest.hexdigest()


def _animal_hash(animal_id):
    try:
        encoded = (HASH_NAMESPACE + animal_id).encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError("Animal ID is not valid UTF-8") from error
    return hashlib.sha256(encoded).hexdigest()


def schedule(private_cases, *, production=False):
    """Return trial groups {outer_fold, animal_id, asset_id, source_trial_row}.

    Default generated mode is NONPRODUCTION and accepts at most 128 metadata
    cases. It is never evidence that the real cohort is scheduled or ready.
    Production requires all frozen census totals plus the exact authenticated
    ordered private-case digest; matching totals alone cannot qualify a cohort.
    Both modes require one source asset per animal under the selected source
    mapping. Every animal belongs to one fold, and all its source rows occur
    once, in asset/row order. No per-region duplicate trial entries are emitted.
    """
    if type(production) is not bool:
        raise ValueError("Production mode must be an explicit boolean")
    if type(private_cases) is not list or not private_cases:
        raise ValueError("Nonempty private case metadata required")
    limit = PRODUCTION_COUNTS["cases"] if production else GENERATED_CASE_LIMIT
    if len(private_cases) > limit:
        raise ValueError("Metadata case count exceeds this mode's bound")
    # This constructor validates exactly nine fields, all available regional
    # support, source row identity and strict within-asset chronology. It has
    # only a callback that refuses value access, so scheduling cannot fetch data.
    adapter = ObservationAdapter(private_cases, _no_history)
    asset_animals, animal_assets, cells = {}, {}, {}
    for case in private_cases:
        asset, animal = case["asset_id"], case["animal_id"]
        asset_animals[asset] = animal
        animal_assets.setdefault(animal, set()).add(asset)
        cells[(asset, case["region"])] = case["source_cluster_count"]
    if any(len(assets) != 1 for assets in animal_assets.values()):
        raise ValueError("The selected source mapping requires exactly one asset per animal")
    trial_keys = adapter.keys()
    if production:
        observed = {
            "animals": len(animal_assets), "assets": len(asset_animals),
            "trials": len(trial_keys), "cells": len(cells),
            "clusters": sum(cells.values()), "cases": len(private_cases),
        }
        if observed != PRODUCTION_COUNTS:
            raise ValueError("Production metadata does not match the frozen source census")
        normalized = _canonical_cases(private_cases)
        coordinates = [(case["asset_id"], case["source_trial_row"], case["region"])
                       for case in normalized]
        if coordinates != sorted(coordinates):
            raise ValueError("Production private cases changed canonical packet ordering")
        if _canonical_case_hash(normalized) != PRODUCTION_CASE_HASH:
            raise ValueError("Production private cases fail the authenticated identity digest")
    animals = sorted(animal_assets, key=lambda animal: (_animal_hash(animal), animal))
    folds = {animal: rank % 5 for rank, animal in enumerate(animals)}
    rows_by_asset = {}
    for asset, row in trial_keys:
        rows_by_asset.setdefault(asset, []).append(row)
    result = []
    for outer_fold in range(5):
        for animal in animals:
            if folds[animal] != outer_fold:
                continue
            for asset in sorted(animal_assets[animal]):
                for row in rows_by_asset[asset]:
                    result.append({"outer_fold": outer_fold, "animal_id": animal,
                                   "asset_id": asset, "source_trial_row": row})
    return result
