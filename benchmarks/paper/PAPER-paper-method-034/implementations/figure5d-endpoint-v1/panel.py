"""Complete three-method numerical Figure 5d panel on one frozen row support.

No representation fitting, source qualification or independent-sample inference.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "marble_figure5d_endpoint", Path(__file__).with_name("score.py"))
endpoint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(endpoint)

METHODS = ("cebra-time", "cebra-behaviour", "marble")


def decode_panel(support, methods):
    """Decode all three methods before any protected-target file is opened."""
    endpoint.support_check(support)
    endpoint.require(type(methods) is dict and set(methods) == set(METHODS),
                     "all three Figure 5d methods are required")
    positions = None
    for method in METHODS:
        operands = methods[method]
        endpoint.require(type(operands) is dict and set(operands) == {"training", "query"},
                         "each method requires training and query operands")
        training = operands["training"]
        endpoint.require(type(training) is dict and "position_m" in training,
                         "each method requires training positions")
        if positions is None:
            positions = training["position_m"]
        else:
            endpoint.require(training["position_m"] == positions,
                             "methods must use identical training positions")
    return {method: endpoint.decode(support, methods[method]["training"],
                                    methods[method]["query"])
            for method in METHODS}


def summarize_panel(support, predictions, targets):
    """Keep each complete-support score and descriptive paired differences."""
    endpoint.require(type(predictions) is dict and set(predictions) == set(METHODS),
                     "all three Figure 5d predictions are required")
    scores = {method: endpoint.error_summary(support, predictions[method], targets)
              for method in METHODS}
    # Signed differences use the same 2,000 target rows for both methods.
    # No Wilcoxon convention, independence assumption or effect threshold is
    # invented while historical contrasts and dependence units are unresolved.
    truth = endpoint.numbers(targets["position_m"], endpoint.QUERY_COUNT, "query position")
    errors = {method: abs(endpoint.numbers(predictions[method], endpoint.QUERY_COUNT,
                                          "prediction") - truth)
              for method in METHODS}
    comparisons = {}
    for comparator in METHODS[:-1]:
        differences = errors["marble"] - errors[comparator]
        mean = math.fsum(float(value) for value in differences) / endpoint.QUERY_COUNT
        endpoint.require(math.isfinite(mean), "paired mean difference overflow")
        comparisons["marble_minus_" + comparator] = {
            "paired_rows": endpoint.QUERY_COUNT,
            "mean_absolute_error_difference_m": mean,
            "direction": "negative means lower MARBLE error on this supplied support",
        }
    return {
        "schema": "marble_figure5d_method_panel_v1", "task_id": endpoint.TASK_ID,
        "panel": "Figure 5d", "animal": "rat1", "unit": "m",
        "method_order": list(METHODS),
        "decoder": {"neighbors": endpoint.NEIGHBORS, "metric": "cosine",
                    "weights": "uniform", "embedding_dimension": endpoint.DIMENSION},
        "method_scores": scores, "paired_descriptive_comparisons": comparisons,
        "inference": "Descriptive only; no p-value, confidence interval or independence assumption.",
        "qualification": "numerical_method_panel_only_original_support_unqualified",
        "historical_source_support_verified": False, "author_baseline_qualified": False,
        "complete_original_figure5_reproduction": False, "scientific_improvement_awarded": None,
    }


def score_panel(support, methods, targets):
    # The caller already holds targets and must enforce its own custody.
    return summarize_panel(support, decode_panel(support, methods), targets)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("support", "methods", "targets"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--support-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        endpoint.digest(args.support_sha256)
        support, support_pin = endpoint.read_json(args.support, 4 << 20)
        endpoint.require(support_pin["sha256"] == args.support_sha256, "support digest mismatch")
        endpoint.support_check(support)
        methods, methods_pin = endpoint.read_json(args.methods, 96 << 20)
        predictions = decode_panel(support, methods)
        targets, targets_pin = endpoint.read_json(args.targets, 1 << 20)
        result = summarize_panel(support, predictions, targets)
        import numpy
        import sklearn
        result["input_pins"] = {"support": support_pin, "methods": methods_pin,
                                "targets": targets_pin}
        result["runtime"] = {"numpy": numpy.__version__, "scikit_learn": sklearn.__version__}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
