"""Identity-aligned full retinal endpoint; never an authenticity/admission issuer.

Targets belong to the operator. This module imports the preserved source metric,
not JAX/Jaxley, and runs no simulator, fitting, split generation, or network IO.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import types

CELL = "20161028_1"
N_SITES = 147
N_ROIS = 232
N_ROWS = 15 * 1024
SOURCE_HASHES = {
    "retina_inputs.py": "a9724675ee673f211cbb3cec0b7e5411a3c40913a3799a009c24d6d7d5e18e83",
    "retina_model.py": "102830b9474dff42c9dcb938d1fd463bb26934e0b22bc70f42f9febccac0993f",
}


class Refusal(ValueError):
    """The submitted records do not define the complete paired endpoint."""


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def exact_keys(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label + ":keys")


def digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def source_metrics():
    """Load only two pinned, call-local-import source modules in a private namespace."""
    directory = Path(__file__).resolve().parents[1] / "registered-runtime/programme/scientific"
    for name, expected in SOURCE_HASHES.items():
        require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected,
                "preserved_metric_source_changed:" + name)
    package_name = "_jaxley_retinal_heldout_102830b9474d"
    module_name = package_name + ".retina_model"
    if module_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(directory)]
        sys.modules[package_name] = package
        for stem in ("retina_inputs", "retina_model"):
            name = package_name + "." + stem
            spec = importlib.util.spec_from_file_location(name, directory / (stem + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
    return sys.modules[module_name].metrics


def site_key(site):
    return (site["field"], site["branch"], site["bin"])


def validate_sites(sites):
    require(type(sites) is list and len(sites) == N_SITES, "complete_147_sites")
    keys, rois = [], set()
    for site in sites:
        exact_keys(site, ("field", "branch", "bin", "raw_roi_ids"), "site")
        require(type(site["field"]) is int and 1 <= site["field"] <= 15, "site:field")
        require(type(site["branch"]) is int and site["branch"] >= 0, "site:branch")
        require(type(site["bin"]) is int and 0 <= site["bin"] < 4, "site:bin")
        ids = site["raw_roi_ids"]
        require(type(ids) is list and bool(ids), "site:raw_roi_ids")
        for roi in ids:
            require(type(roi) is int and roi > 0, "site:roi_id")
            key = (site["field"], roi)
            require(key not in rois, "duplicate_raw_roi")
            rois.add(key)
        keys.append(site_key(site))
    require(len(set(keys)) == N_SITES, "duplicate_site")
    require(len(rois) == N_ROIS, "complete_232_roi_lineage")
    require({key[0] for key in keys} == set(range(1, 16)), "complete_15_fields")
    return keys


def validate_split(splits):
    exact_keys(splits, ("train", "val", "test"), "splits")
    seen = set()
    for name, indices in splits.items():
        require(type(indices) is list and bool(indices), "split:nonempty:" + name)
        for row in indices:
            require(type(row) is int and 0 <= row < N_ROWS, "split:row_coordinate")
            require(row not in seen, "split:duplicate_or_overlap")
            seen.add(row)
    require(seen == set(range(N_ROWS)), "split:complete_15360_rows")
    # Historical allocation counts/seed are unresolved: never invent them here.
    return splits["test"]


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (type(value) is float or int(float(value)) == value)
    except (ValueError, OverflowError):
        return False


def matrix(values, rows, columns, label, unavailable=None):
    import numpy as np
    require(type(values) is list and len(values) == rows, label + ":rows")
    cleaned = []
    for i, row in enumerate(values):
        require(type(row) is list and len(row) == columns, label + ":columns")
        out = []
        for j, value in enumerate(row):
            if unavailable is not None and unavailable[i][j] and value is None:
                value = 0.0
            require(finite_number(value), label + ":finite_real_number")
            out.append(value)
        cleaned.append(out)
    return np.asarray(cleaned, dtype=np.float64)


def align_prediction(packet, row_ids, keys):
    import numpy as np
    exact_keys(packet, ("schema", "cell_id", "test_row_ids", "site_keys", "predictions"), "prediction")
    require(packet["schema"] == "jaxley-retinal-prediction-v1" and packet["cell_id"] == CELL,
            "prediction:cell_or_schema")
    rows = packet["test_row_ids"]
    require(type(rows) is list and all(type(x) is int for x in rows), "prediction:row_ids")
    require(len(rows) == len(row_ids) and len(set(rows)) == len(rows) and set(rows) == set(row_ids),
            "prediction:exact_test_rows")
    supplied = packet["site_keys"]
    require(type(supplied) is list and all(type(key) is list and len(key) == 3 and
            all(type(v) is int for v in key) for key in supplied), "prediction:site_keys")
    supplied = list(map(tuple, supplied))
    require(len(supplied) == N_SITES and len(set(supplied)) == N_SITES and set(supplied) == set(keys),
            "prediction:exact_147_sites")
    array = matrix(packet["predictions"], len(rows), N_SITES, "prediction")
    row_order, site_order = {v: i for i, v in enumerate(rows)}, {v: i for i, v in enumerate(supplied)}
    return array[np.ix_([row_order[v] for v in row_ids], [site_order[v] for v in keys])]


def compare(operator, author, candidate):
    """Compare predictions on operator-owned identities/targets; no win decision.

    Operator metadata validates internal consistency, not historic provenance.
    Both prediction packets may reorder their rows and columns independently.
    No record, recording site, or undefined correlation is dropped.
    """
    import numpy as np
    exact_keys(operator, ("schema", "cell_id", "sites", "splits", "labels", "mask"), "operator")
    require(operator["schema"] == "jaxley-retinal-target-v1" and operator["cell_id"] == CELL,
            "operator:cell_or_schema")
    keys = validate_sites(operator["sites"])
    rows = validate_split(operator["splits"])
    expected_mask = [[int(row // 1024 + 1 == key[0]) for key in keys] for row in rows]
    supplied_mask = matrix(operator["mask"], len(rows), N_SITES, "mask")
    require(np.array_equal(supplied_mask, expected_mask), "mask:original_field_support")
    labels = matrix(operator["labels"], len(rows), N_SITES, "labels",
                    unavailable=[[not v for v in row] for row in expected_mask])
    metric = source_metrics()
    results = []
    for packet in (author, candidate):
        predictions = align_prediction(packet, rows, keys)
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            try:
                result = metric(predictions, labels, supplied_mask)
            except FloatingPointError as exc:
                raise Refusal("metric:numerical_range") from exc
        for site in result["sites"]:
            for field in ("pearson", "mae", "mse"):
                require(site[field] is None or math.isfinite(site[field]), "metric:nonfinite_result")
        results.append(result)
    author_result, candidate_result = results
    site_results = []
    for key, baseline, proposed in zip(keys, author_result["sites"], candidate_result["sites"]):
        a, c = baseline["pearson"], proposed["pearson"]
        site_results.append({"site_key": list(key), "valid_count": baseline["count"],
                             "author_pearson": a, "candidate_pearson": c,
                             "delta": None if a is None or c is None else c - a,
                             "author_undefined": baseline["undefined"],
                             "candidate_undefined": proposed["undefined"]})
    a, c = author_result["mean_pearson"], candidate_result["mean_pearson"]
    return {"schema": "jaxley-retinal-comparison-v1", "cell_id": CELL,
            "recording_sites": N_SITES, "raw_roi_count": N_ROIS, "test_rows": len(rows),
            "author_mean_pearson": a, "candidate_mean_pearson": c,
            "paired_delta": None if a is None or c is None else c - a,
            "sites": site_results,
            "metric": "arithmetic mean of masked per-site Pearson r across all 147 sites",
            "undefined_sites_dropped": False,
            "identity_sha256": digest({"sites": operator["sites"], "splits": operator["splits"]}),
            "input_sha256": {"operator": digest(operator), "author": digest(author), "candidate": digest(candidate)},
            "metric_source_sha256": SOURCE_HASHES,
            "qualification": "software_comparison_only_historical_equivalence_unverified",
            "paper_win": None, "uncertainty": None,
            "population_scope": "one cell; sites and stimulus rows are not independent biological replicates"}


def read_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "json:duplicate_key")
            out[key] = value
        return out
    def constant(value):
        raise Refusal("json:nonfinite_constant:" + value)
    with Path(path).open() as stream:
        return json.load(stream, object_pairs_hook=pairs, parse_constant=constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, help="operator-private target JSON")
    parser.add_argument("--author", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True, help="operator-private new report path")
    args = parser.parse_args()
    try:
        report = compare(read_json(args.targets), read_json(args.author), read_json(args.candidate))
        with Path(args.output).open("x") as stream:
            json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    except (Refusal, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "retinal comparison refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
