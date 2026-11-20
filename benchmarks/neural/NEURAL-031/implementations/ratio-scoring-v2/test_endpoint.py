"""Generated cancellation regressions; no original ratios, fitting or native work."""
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("NEUROBENCH_SOURCE_ROOT", HERE.parents[4]))
ep = load("neural031_ratio_v2", HERE / "endpoint.py")
prior = load("neural031_ratio_prior", REPO / "benchmarks/neural/NEURAL-031/implementations/ratio-scoring-v1/endpoint.py")


def oracle(values):
    with localcontext() as context:
        context.prec = 1200
        return float(sum((Decimal.from_float(float(x)) for x in values), Decimal()) / len(values))


def cancellation_panel():
    support = {"schema": "neural031_ordinary_public_support_v1", "candidate_id": "NEURAL-031",
               "folds": [], "request_rows": 774, "query_targets_included": False}
    bundle = {"schema": "neural031_ordinary_submission_bundle_v1", "candidate_id": "NEURAL-031", "outputs": []}
    targets = {"schema": "neural031_ratio_targets_v1", "candidate_id": "NEURAL-031", "mice": list(ep.MICE), "rows": []}
    for fold in range(20):
        count, missing = (90, 24) if fold == 0 else (36, 1)
        ids = list(range(len(targets["rows"]), len(targets["rows"]) + count))
        views = {view: {kind: {"bytes": 1, "sha256": hashlib.sha256(f"{fold}/{view}/{kind}".encode()).hexdigest()}
                        for kind in ("data", "manifest")} for view in ep.VIEWS}
        support["folds"].append({"fold": fold, "rowids": ids, "views": views})
        for index, rowid in enumerate(ids):
            observed = int(index >= missing)
            targets["rows"].append({"rowid": rowid, "mouse": fold, "request": 1, "observed": observed,
                "y": 0.0 if observed else None, "baseline_new": index % 2, "compartment": int(index % 3 == 0)})
        pair = {0: (1e308, 0.0), 1: (0.0, 1e308), 2: (1e-300, 0.0)}.get(fold, (0.0, 0.0))
        for view, prediction in zip(ep.VIEWS, pair):
            bundle["outputs"].append({"schema": "neural031_ordinary_prediction_v1", "candidate_id": "NEURAL-031",
                "fold": fold, "view": view, "input_manifest": views[view]["manifest"],
                "rows": [{"row_id": rowid, "prediction": prediction} for rowid in ids]})
    for rowid in range(774, 1143):
        targets["rows"].append({"rowid": rowid, "mouse": rowid % 20, "request": 0, "observed": 0,
                               "y": None, "baseline_new": 0, "compartment": 0})
    return support, bundle, targets


class CancellationSafeRatioTests(unittest.TestCase):
    def test_representable_residual_survives_large_cancellation(self):
        values = [1e308, -1e308, 1e-300] + [0.0] * 17
        expected = oracle(values)
        self.assertGreater(expected, 0.0)
        self.assertEqual(prior.mean(values), 0.0)
        self.assertEqual(ep.mean(values), expected)

    def test_complete_twenty_mouse_primary_keeps_residual_gain(self):
        inputs = cancellation_panel()
        before = prior.score(*inputs)
        after = ep.score(*inputs)
        self.assertEqual(before["primary"], 0.0)
        expected = oracle([1e308, -1e308, 1e-300] + [0.0] * 17)
        self.assertEqual(after["primary"], expected)
        self.assertEqual(after["macro"]["baseline_minus_neural_mae"], expected)
        self.assertEqual(after["positive_mouse_differences"], 2)
        self.assertEqual((after["raw_rows"], after["request_rows"], after["scored_rows"]), (1143, 774, 731))
        self.assertEqual(after["primary_metric"], "equal_mouse_baseline_minus_neural_mae")

    def test_order_and_large_positive_values_do_not_change_the_mean(self):
        values = [1e308, -1e308, 1e-300] + [0.0] * 17
        for order in (values, list(reversed(values)), values[2:] + values[:2]):
            self.assertEqual(ep.mean(order), oracle(values))
        self.assertEqual(ep.mean([1e308] * 100), 1e308)
        self.assertEqual(ep.mean([math.ldexp(1.0, -1074)] * 20), math.ldexp(1.0, -1074))

    def test_exact_zero_and_invalid_metric_guards_are_preserved(self):
        for values in ([0.0] * 20, [1e308, -1e308], [1.0, -1.0, 0.0]):
            self.assertEqual(ep.mean(values), 0.0)
        for values in ([], [True], [math.inf], [math.nan], ["1"], [10 ** 400]):
            with self.subTest(values=str(values)[:50]), self.assertRaises(ValueError):
                ep.mean(values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
