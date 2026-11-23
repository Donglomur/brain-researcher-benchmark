"""Original Plexus Figure 4 metadata split reconstruction and prediction scoring.

No fitting, source download, numerical preprocessing, or readiness determination.
Input rows must already correspond to the author's post-preprocessing observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

SOURCE_SHA256 = "2c685db69e2604f1214e02eb2dec19c161e5732acd34aa51c32ec30039601af7"
DATA_RECORD = "10.5281/zenodo.15809433"
DONORS = ("WTC11", "Patient Line")
FAMILIES = ("manual_features", "plexus")
METHODS = {"author_manual_features": "manual_features", "author_plexus": "plexus", "candidate": "plexus"}
REPRODUCTION_METHODS = {"author_manual_features": "manual_features", "author_plexus": "plexus"}


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise InputError("canonical JSON requires finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def string(value, field):
    require(isinstance(value, str) and bool(value), f"{field}: nonempty string required")
    return value


def pin(value, field):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), f"{field}: SHA256 required")
    return value


def _location(row, family):
    well = string(row.get("well_id"), "well_id (source string conversion)")
    if family == "manual_features":
        plate = string(row.get("zarr_file"), "zarr_file")
        return well + "_" + plate, (well, plate)
    aggregate = string(row.get("aggregate_by"), "aggregate_by")
    prefix = "_".join(aggregate.split("_")[:2])
    return prefix + "_" + well, (prefix, well)


def _prepare_panel(panel):
    family, donor = panel.get("family"), panel.get("donor")
    require(family in FAMILIES and donor in DONORS and panel.get("tau_status") == "WT",
            "Only the original two WT donors and two source representation families are supported")
    pin(panel.get("observations_source_sha256"), "observations_source_sha256")
    observations = panel.get("observations")
    require(isinstance(observations, list) and observations, "ordered observations required")
    rows, identities, locations, guide_genes, aggregates = [], set(), {}, {}, set()
    for row in observations:
        require(isinstance(row, dict), "observation must be an object")
        oid = string(row.get("observation_id"), "observation_id")
        require(oid not in identities, "duplicate observation_id")
        identities.add(oid)
        gene = string(row.get("gene_id"), "gene_id")
        guide = string(row.get("guide_id"), "guide_id")
        require(guide not in guide_genes or guide_genes[guide] == gene, "guide maps to multiple genes")
        guide_genes[guide] = gene
        loc, components = _location(row, family)
        require(loc not in locations or locations[loc] == components,
                "source loc_id concatenation collision; resolve source identity before scoring")
        locations[loc] = components
        if family == "plexus":
            require(row["aggregate_by"] not in aggregates,
                    "Plexus rows must be after aggregate_by aggregation")
            aggregates.add(row["aggregate_by"])
        rows.append({"observation_id": oid, "gene_id": gene, "guide_id": guide, "loc_id": loc})

    # Source uses np.random.seed(0) on each function call, sorted np.unique,
    # and legacy choice. Never replace this with default_rng or well shuffles.
    rng = np.random.RandomState(0)
    controls = [r for r in rows if r["gene_id"] == "non-targeting"]
    control_wells = sorted({r["loc_id"] for r in controls})
    require(len(control_wells) >= 2, "author function has no estimable panel with fewer than two NTC wells")
    control_train_wells = set(rng.choice(control_wells, max(1, len(control_wells) // 2), replace=False))
    control_train = [r for r in controls if r["loc_id"] in control_train_wells]
    control_test = [r for r in controls if r["loc_id"] not in control_train_wells]
    endpoints, skips = [], []
    for guide in sorted(guide_genes):
        guide_rows = [r for r in rows if r["guide_id"] == guide]
        wells = sorted({r["loc_id"] for r in guide_rows})
        if len(wells) < 2:
            skips.append({"guide_id": guide, "reason": "fewer_than_two_guide_wells"})
            continue
        train_wells = set(rng.choice(wells, max(1, len(wells) // 2), replace=False))
        positive_train = [r for r in guide_rows if r["loc_id"] in train_wells]
        positive_test = [r for r in guide_rows if r["loc_id"] not in train_wells]
        # Literal substring rule from the source; gene labels alone are not equivalent.
        negative_train = [r for r in control_train if not ("non-targeting" in guide and r["guide_id"] == guide)]
        negative_test = [r for r in control_test if not ("non-targeting" in guide and r["guide_id"] == guide)]
        size = min(len(negative_train), len(positive_train))
        if size <= 8:
            skips.append({"guide_id": guide, "reason": "first_fold_min_class_count_at_most_eight"})
            continue
        original_train = negative_train + positive_train
        if len(negative_train) > size:
            negative_train = [negative_train[i] for i in rng.choice(len(negative_train), size, replace=False)]
        if len(positive_train) > size:
            positive_train = [positive_train[i] for i in rng.choice(len(positive_train), size, replace=False)]
        if not negative_test or not positive_test:
            # The source's second classifier cannot fit a one-class test set.
            skips.append({"guide_id": guide, "reason": "reciprocal_training_set_has_one_class"})
            continue
        balanced = negative_train + positive_train
        held = negative_test + positive_test
        def labeled(items):
            return [{"observation_id": r["observation_id"], "label": int(r["guide_id"] == guide)} for r in items]
        # Class membership is assigned by source array concatenation, so reject
        # ambiguous control guide naming rather than silently duplicating a row.
        require(len({r["observation_id"] for r in balanced + held}) == len(balanced + held),
                "guide overlaps its negative-control rows; source guide naming must be reconciled")
        keep = {r["observation_id"] for r in balanced}
        endpoints.append({"guide_id": guide, "gene_id": guide_genes[guide],
                          "first_train_wells": sorted(train_wells),
                          "discarded_by_balance": [r["observation_id"] for r in original_train if r["observation_id"] not in keep],
                          "folds": [{"fold": 1, "train": labeled(balanced), "test": labeled(held)},
                                    {"fold": 2, "train": labeled(held), "test": labeled(balanced)}]})
    require(endpoints, "no estimable guides in panel")
    return {"family": family, "donor": donor, "tau_status": "WT",
            "observations_source_sha256": panel["observations_source_sha256"],
            "ordered_observations_sha256": digest(observations), "n_observations": len(rows),
            "control_first_train_wells": sorted(control_train_wells),
            "endpoints": endpoints, "skipped_guides": skips}


def prepare(census):
    """Reconstruct metadata-only original folds; supplied census authenticity is external."""
    require(isinstance(census, dict) and census.get("schema") == "plexus-figure4-observations/v1", "observation schema mismatch")
    require(census.get("source_figure4_sha256") == SOURCE_SHA256, "author source pin mismatch")
    require(census.get("data_record") == DATA_RECORD, "data version mismatch")
    pin(census.get("preprocessing_receipt_sha256"), "preprocessing_receipt_sha256")
    panels = census.get("panels")
    require(isinstance(panels, list) and len(panels) == 4, "all four original family/donor panels required")
    keys = [(p.get("family"), p.get("donor")) for p in panels if isinstance(p, dict)]
    require(len(keys) == 4 and set(keys) == {(f, d) for f in FAMILIES for d in DONORS}, "duplicate or missing panel")
    return {"schema": "plexus-figure4-plan/v1", "census_sha256": digest(census),
            "source_figure4_sha256": SOURCE_SHA256, "data_record": DATA_RECORD,
            "preprocessing_receipt_sha256": census["preprocessing_receipt_sha256"],
            "numpy_version": np.__version__, "panels": [_prepare_panel(p) for p in panels],
            "scope": "metadata reconstruction; source identity and final-paper compatibility require external audit"}


def auroc(labels, probabilities):
    """Exact tie-aware Mann-Whitney equivalent of sklearn roc_curve followed by auc."""
    require(len(labels) == len(probabilities) and set(labels) == {0, 1}, "AUROC requires both classes")
    ranked = sorted(zip(probabilities, labels))
    positive_rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i + 1
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        positive_rank_sum += ((i + 1 + j) / 2) * sum(label for _, label in ranked[i:j])
        i = j
    n_positive = sum(labels)
    n_negative = len(labels) - n_positive
    return (positive_rank_sum - n_positive * (n_positive + 1) / 2) / (n_positive * n_negative)


def evaluate(census, submission, expected_census_sha256):
    """Score the full three-method vector on reconstructed original observation sets."""
    return _evaluate(census, submission, expected_census_sha256, METHODS,
                     "plexus-figure4-predictions/v1", "plexus-figure4-report/v1")


def evaluate_reproduction(census, submission, expected_census_sha256):
    """Recompute both original method panels without requiring a candidate arm.

    This is supplied-prediction scoring, not a numerical equivalence decision:
    authentic publication references and a justified tolerance remain external.
    """
    report = _evaluate(census, submission, expected_census_sha256, REPRODUCTION_METHODS,
                       "plexus-figure4-reproduction-predictions/v1",
                       "plexus-figure4-reproduction-report/v1")
    report["reproduction_decision"] = None
    return report


def _evaluate(census, submission, expected_census_sha256, methods, submission_schema, report_schema):
    pin(expected_census_sha256, "independently frozen census pin")
    require(digest(census) == expected_census_sha256, "census differs from independently frozen pin")
    plan = prepare(census)
    require(isinstance(submission, dict) and submission.get("schema") == submission_schema, "prediction schema mismatch")
    require(submission.get("plan_sha256") == digest(plan), "prediction plan mismatch")
    scores = submission.get("scores")
    require(isinstance(scores, list), "scores must be a list")
    expected, groups = {}, []
    for method, family in methods.items():
        for panel in plan["panels"]:
            if panel["family"] != family:
                continue
            for endpoint in panel["endpoints"]:
                for fold in endpoint["folds"]:
                    group = (method, panel["donor"], endpoint["guide_id"], fold["fold"])
                    groups.append((group, fold["test"]))
                    for row in fold["test"]:
                        expected[group + (row["observation_id"],)] = row["label"]
    actual = {}
    for row in scores:
        require(isinstance(row, dict), "score row must be an object")
        require(type(row.get("fold")) is int and row["fold"] in (1, 2), "fold must be integer 1 or 2")
        fields = ("method", "donor", "guide_id", "observation_id")
        for field in fields:
            string(row.get(field), field)
        key = (row["method"], row["donor"], row["guide_id"], row["fold"], row["observation_id"])
        require(key in expected and key not in actual, "unexpected or duplicate prediction identity")
        value = row.get("probability")
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1, "finite guide-positive probability in [0,1] required")
        actual[key] = value
    require(actual.keys() == expected.keys(), "incomplete original prediction coverage")
    output, lookup = [], {}
    for group, rows in groups:
        labels = [r["label"] for r in rows]
        value = auroc(labels, [actual[group + (r["observation_id"],)] for r in rows])
        lookup[group] = value
        output.append(dict(zip(("method", "donor", "guide_id", "fold"), group),
                           auroc=value, n_positive=sum(labels), n_negative=len(labels)-sum(labels)))
    differences = [{"donor": donor, "guide_id": guide, "fold": fold,
                    "candidate_minus_author_plexus": value - lookup[("author_plexus", donor, guide, fold)]}
                   for (method, donor, guide, fold), value in lookup.items() if method == "candidate"]
    report = {"schema": report_schema, "census_sha256": digest(census),
            "plan_sha256": digest(plan), "submission_sha256": digest(submission),
            "metric": "source-analysis-observation AUROC; two folds retained separately",
            "auroc_vector": output, "paired_descriptive_differences": differences,
            "source_skips": [{"family": p["family"], "donor": p["donor"], "guides": p["skipped_guides"]} for p in plan["panels"]],
            "qualification": "software score only; authentic cohort, baseline provenance, preprocessing exposure and final-paper equivalence unresolved",
            "inference": "No pooled scalar, interval, superiority test, or paper-win decision. Reciprocal folds and shared controls are dependent."}
    if "candidate" not in methods:
        del report["paired_descriptive_differences"]
    return report


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    def invalid(value):
        raise InputError(f"nonfinite JSON token: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "score", "score-reproduction"))
    parser.add_argument("--census", required=True)
    parser.add_argument("--census-sha256")
    parser.add_argument("--submission")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        census = read_json(args.census)
        if args.action == "prepare":
            result = prepare(census)
        else:
            require(args.census_sha256 and args.submission, "scoring requires --census-sha256 and --submission")
            scorer = evaluate_reproduction if args.action == "score-reproduction" else evaluate
            result = scorer(census, read_json(args.submission), args.census_sha256)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (InputError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"figure4: {exc}\n")


if __name__ == "__main__":
    main()
