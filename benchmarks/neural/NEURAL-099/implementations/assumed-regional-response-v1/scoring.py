"""Pure reference arithmetic for the assumed-support NEURAL-099 condition.

This module opens no files and does not authenticate a dataset, biological
identity map, split, observation interval or participant sandbox. The caller
must supply the complete sealed case roster. No target is read until the whole
prediction object has been admitted. Fractions preserve finite results through
otherwise overflowing intermediate differences, squares and weighted sums.
Runtime on the authentic cohort has not been measured.
"""

from fractions import Fraction
import math


CASE_FIELDS = frozenset(("case_id", "animal_id", "asset_id", "region",
                         "source_trial_row", "source_cluster_count"))
NAMED_REGIONS = frozenset(("BIC", "MGd", "MGm", "MGv", "MZMG", "SG"))
QUANTITY = (
    "Deposited spike events per retained source cluster per nominal second, "
    "conditional on the explicit observation-support assumption"
)


def _identifier(value, field):
    if (type(value) is not str or not value or len(value) > 256
            or any(ord(character) < 32 for character in value)):
        raise ValueError("Invalid " + field)
    return value


def _integer(value, field, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid " + field)
    return value


def _number(value, field):
    if type(value) not in (int, float):
        raise ValueError("Invalid " + field)
    try:
        finite = math.isfinite(value)
    except OverflowError as error:
        raise ValueError("Invalid " + field) from error
    if not finite:
        raise ValueError("Nonfinite " + field)
    return Fraction(value)


def _case(case):
    if type(case) is not dict or set(case) != CASE_FIELDS:
        raise ValueError("Invalid case descriptor fields")
    result = {field: _identifier(case[field], field)
              for field in ("case_id", "animal_id", "asset_id", "region")}
    if result["region"] not in NAMED_REGIONS:
        raise ValueError("Unsupported or unassigned source region")
    result["source_trial_row"] = _integer(case["source_trial_row"], "source_trial_row")
    result["source_cluster_count"] = _integer(
        case["source_cluster_count"], "source_cluster_count", 1)
    return result


def validate_cases(cases):
    """Validate supplied ragged support; the caller seals its source completeness.

    Regions may differ across assets. Within each supplied asset, every listed
    region must include the same set of trial rows. A different region cannot
    silently replace an absent response on one trial. An asset has one declared
    animal identity and a fixed cluster count per region. Biological identity is
    accepted from the caller, never inferred here from an asset or name.
    """
    if type(cases) is not list or not cases:
        raise ValueError("Cases must be a nonempty list")
    by_id, coordinates, assets, support = {}, set(), {}, {}
    for value in cases:
        case = _case(value)
        key = case["case_id"]
        if key in by_id:
            raise ValueError("Duplicate case_id")
        coordinate = (case["asset_id"], case["region"], case["source_trial_row"])
        if coordinate in coordinates:
            raise ValueError("Duplicate asset/region/trial coordinate")
        coordinates.add(coordinate)
        asset = case["asset_id"]
        animal = case["animal_id"]
        if asset in assets and assets[asset] != animal:
            raise ValueError("Asset has conflicting animal identities")
        assets[asset] = animal
        cell = support.setdefault((asset, case["region"]), {
            "clusters": case["source_cluster_count"], "trials": set()})
        if cell["clusters"] != case["source_cluster_count"]:
            raise ValueError("Cluster denominator changes within an asset/region")
        cell["trials"].add(case["source_trial_row"])
        by_id[key] = case
    for asset in assets:
        sets = [value["trials"] for (owner, _), value in support.items() if owner == asset]
        if any(trials != sets[0] for trials in sets[1:]):
            raise ValueError("Incomplete trial support across an asset's regions")
    return by_id


def _widths(edges_seconds):
    if type(edges_seconds) is not list or len(edges_seconds) < 2:
        raise ValueError("At least two explicit bin edges are required")
    # Bin coordinates are protocol decimal numbers. Read the shortest decimal
    # representation of a supplied finite int/float, rather than subtracting
    # binary floats: the selected 0.001-second grid has exactly 1-ms exposure.
    # Prediction floats, in contrast, retain their exact supplied binary value.
    for edge in edges_seconds:
        _number(edge, "bin edge")
    edges = [Fraction(str(edge)) for edge in edges_seconds]
    widths = [right - left for left, right in zip(edges, edges[1:])]
    if any(width <= 0 for width in widths):
        raise ValueError("Bin edges must strictly increase")
    return widths


def admit_predictions(cases, predictions, *, edges_seconds):
    """Return copied finite vectors after complete identity/shape admission.

    Negative finite predictions are scored as supplied, without clipping.
    This function has no gold argument and does not access outcome content.
    """
    by_id = validate_cases(cases)
    size = len(_widths(edges_seconds))
    if type(predictions) is not list or len(predictions) != len(by_id):
        raise ValueError("Complete prediction list required")
    output = {}
    for row in predictions:
        if type(row) is not dict or set(row) != {"case_id", "rates"}:
            raise ValueError("Invalid prediction row fields")
        key = _identifier(row["case_id"], "prediction case_id")
        if key not in by_id or key in output:
            raise ValueError("Unknown or duplicate prediction case_id")
        rates = row["rates"]
        if type(rates) is not list or len(rates) != size:
            raise ValueError("Prediction vector has wrong shape")
        for rate in rates:
            _number(rate, "prediction rate")
        output[key] = rates[:]
    if set(output) != set(by_id):
        raise ValueError("Prediction identities do not match complete support")
    return output


def _gold(cases, gold, widths):
    by_id = validate_cases(cases)
    if type(gold) is not list or len(gold) != len(by_id):
        raise ValueError("Complete gold list required")
    output = {}
    for row in gold:
        if type(row) is not dict or set(row) != {"case", "counts"}:
            raise ValueError("Invalid gold row fields")
        case = _case(row["case"])
        key = case["case_id"]
        if key not in by_id or key in output or case != by_id[key]:
            raise ValueError("Gold identity differs from sealed case descriptor")
        counts = row["counts"]
        if type(counts) is not list or len(counts) != len(widths):
            raise ValueError("Gold count vector has wrong shape")
        for count in counts:
            _integer(count, "deposited count")
        output[key] = [Fraction(count, case["source_cluster_count"]) / width
                       for count, width in zip(counts, widths)]
    if set(output) != set(by_id):
        raise ValueError("Gold identities do not match complete support")
    return output


def _float(value):
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Value is outside finite float range") from error
    if not math.isfinite(result):
        raise ValueError("Value is outside finite float range")
    return result


def rates_from_gold(cases, gold, *, edges_seconds):
    """Convert authenticated-by-caller counts to finite JSON-compatible rates.

    This is for training/preparation use, not query disclosure. The reference
    scorer retains rational targets internally and can report final range
    overflow without prematurely requiring each target rate to fit a float.
    """
    exact = _gold(cases, gold, _widths(edges_seconds))
    return {key: [_float(value) for value in values] for key, values in exact.items()}


def _mean(values):
    if not values:
        raise ValueError("An empty mean is unsupported")
    return sum(values, Fraction()) / len(values)


def _vector_mean(vectors):
    if not vectors or not vectors[0] or any(len(v) != len(vectors[0]) for v in vectors):
        raise ValueError("Invalid mean vector shape")
    return [_mean([row[index] for row in vectors]) for index in range(len(vectors[0]))]


def _range_report(value):
    # Every admitted input yields a mathematically finite rational value.
    # An overflow here is a serialization range issue, never NaN or infinity.
    try:
        converted = _float(value)
    except ValueError:
        return {"value": None, "state": "outside_float_range"}
    state = "underflow_to_zero" if value and converted == 0 else "finite"
    return {"value": converted, "state": state}


def _losses(cases_by_id, predictions, targets):
    grouped = {}
    for key, case in cases_by_id.items():
        errors = [prediction - target
                  for prediction, target in zip(predictions[key], targets[key])]
        mse = _mean([error * error for error in errors])
        mae = _mean([abs(error) for error in errors])
        grouped.setdefault(case["animal_id"], {}).setdefault(case["region"], []).append((mse, mae))
    animals, summary = {}, {}
    for animal, regions in grouped.items():
        regional = [(_mean([pair[0] for pair in rows]), _mean([pair[1] for pair in rows]))
                    for rows in regions.values()]
        mse, mae = _mean([pair[0] for pair in regional]), _mean([pair[1] for pair in regional])
        animals[animal] = (mse, mae)
        summary[animal] = {
            "available_regions": sorted(regions),
            "cases": sum(len(rows) for rows in regions.values()),
            "mse": _range_report(mse), "mae": _range_report(mae)}
    return {
        "animal_macro_mse": _range_report(_mean([pair[0] for pair in animals.values()])),
        "animal_macro_mae": _range_report(_mean([pair[1] for pair in animals.values()])),
        "per_animal": summary}


def _coarsen(values, widths, factor):
    result = []
    for offset in range(0, len(widths), factor):
        local_widths = widths[offset:offset + factor]
        total = sum(local_widths, Fraction())
        result.append(sum((value * width for value, width in
                           zip(values[offset:offset + factor], local_widths)), Fraction()) / total)
    return result


def score(cases, predictions, gold, *, edges_seconds, coarsening_factor=None):
    """Equal animal -> available region -> case/trial -> bin MSE and MAE.

    All sessions of an animal/region pool their trials before that region's
    mean. The frozen roster, rather than output availability, defines support.
    Coarsening merges adjacent intervals with exposure/time-weighted rates;
    this equals arithmetic averaging when widths are equal. The factor must
    divide the bin count, and coarse bins receive equal weight in that separate
    secondary score. This function selects no time window, split or factor.
    """
    widths = _widths(edges_seconds)
    if coarsening_factor is not None:
        _integer(coarsening_factor, "coarsening factor", 1)
        if len(widths) % coarsening_factor:
            raise ValueError("Coarsening factor must divide the full bin count")
    admitted = admit_predictions(cases, predictions, edges_seconds=edges_seconds)
    # Keep this ordering: no gold iteration or count conversion before the
    # entire participant prediction has passed identity/shape/numeric checks.
    targets = _gold(cases, gold, widths)
    by_id = validate_cases(cases)
    exact_predictions = {key: [Fraction(rate) for rate in rates]
                         for key, rates in admitted.items()}
    result = {
        "schema": "neural099-assumed-support-score/v1",
        "admitted": True,
        "quantity": QUANTITY,
        "source_cluster_is_individual_neuron": False,
        "observation_coverage_verified": False,
        "empirical_readiness_claim": False,
        "direction": "lower_is_better",
        "weighting": "equal animal, then available region, then supplied trial/case, then bin",
        "animals": len({case["animal_id"] for case in by_id.values()}),
        "animal_region_cells": len({(case["animal_id"], case["region"]) for case in by_id.values()}),
        "assets": len({case["asset_id"] for case in by_id.values()}),
        "cases": len(by_id),
        "bins_per_case": len(widths),
        "native_resolution": _losses(by_id, exact_predictions, targets),
        "coarsened_resolution": None,
    }
    if coarsening_factor is not None:
        merged_predictions = {key: _coarsen(values, widths, coarsening_factor)
                              for key, values in exact_predictions.items()}
        merged_targets = {key: _coarsen(values, widths, coarsening_factor)
                          for key, values in targets.items()}
        result["coarsened_resolution"] = {
            "adjacent_bin_factor": coarsening_factor,
            "bins_per_case": len(widths) // coarsening_factor,
            "aggregation": "nominal-time weighted adjacent rates; equal coarse-bin score weights",
            **_losses(by_id, merged_predictions, merged_targets)}
    return result


def training_mean_baseline(training_cases, training_gold, query_cases, *, edges_seconds):
    """Fit only supplied training counts; produce region means and flagged fallback.

    Each training animal gets equal weight within a region after its trials are
    averaged. For a region absent from training, the fixed fallback first
    averages available regions within each training animal, then animals.
    Query animal identities must be entirely absent from training. Neither
    query gold nor held-out histories are accepted by this interface.
    """
    widths = _widths(edges_seconds)
    train = validate_cases(training_cases)
    query = validate_cases(query_cases)
    train_animals = {case["animal_id"] for case in train.values()}
    query_animals = {case["animal_id"] for case in query.values()}
    if train_animals & query_animals:
        raise ValueError("Baseline training and query animals overlap")
    train_assets = {case["asset_id"] for case in train.values()}
    query_assets = {case["asset_id"] for case in query.values()}
    if train_assets & query_assets or set(train) & set(query):
        raise ValueError("Baseline training and query identities overlap")
    values = _gold(training_cases, training_gold, widths)
    grouped = {}
    for key, case in train.items():
        grouped.setdefault(case["animal_id"], {}).setdefault(case["region"], []).append(values[key])
    animal_regions = {animal: {region: _vector_mean(vectors) for region, vectors in regions.items()}
                      for animal, regions in grouped.items()}
    region_names = sorted({region for regions in animal_regions.values() for region in regions})
    region_means = {
        region: _vector_mean([regions[region] for regions in animal_regions.values() if region in regions])
        for region in region_names}
    fallback = _vector_mean([_vector_mean(list(regions.values())) for regions in animal_regions.values()])
    predictions, fallback_cells = [], set()
    for key, case in query.items():
        region = case["region"]
        if region not in region_means:
            fallback_cells.add((case["animal_id"], case["asset_id"], region))
        predictions.append({"case_id": key,
                            "rates": [_float(value) for value in region_means.get(region, fallback)]})
    return {
        "schema": "neural099-assumed-support-training-mean/v1",
        "quantity": QUANTITY,
        "observation_coverage_verified": False,
        "empirical_readiness_claim": False,
        "training_animals": sorted(train_animals),
        "query_animals": sorted(query_animals),
        "training_regions": region_names,
        "predictions": predictions,
        "fallback_cells": [{"animal_id": animal, "asset_id": asset, "region": region}
                           for animal, asset, region in sorted(fallback_cells)],
        "fallback_rule": "mean available regions within training animal, then equal training animals",
    }
