"""Generated software controls. No recordings, models, or scientific trials."""
from __future__ import annotations

import copy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[4]
SOURCE = REPO / ("benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/"
                 "authoring/delivery-20261105/common/remaining-builds-wave37/"
                 "neural056-complete-program/successor-v3/package")
sys.path[:0] = [str(HERE), str(SOURCE)]

import numpy as np
from n056 import evaluation as predecessor
from n056.arrays import encode
from n056.bank_a import correlation as prior_correlation
from n056.core import digest
from n056.protocol import ARMS, PEOPLE, ROLES, SHAPE
from n056.runtime import tree
from n056_precision.correlation import correlation
from n056_precision import evaluation


def decimal_pearson(x, y):
    """Exact float conversion and independent high-precision textbook formula."""
    with localcontext() as context:
        context.prec = 1500
        xx = [Decimal.from_float(float(v)) for v in x]
        yy = [Decimal.from_float(float(v)) for v in y]
        mx, my = sum(xx) / len(xx), sum(yy) / len(yy)
        xx, yy = [v - mx for v in xx], [v - my for v in yy]
        numerator = sum(a * b for a, b in zip(xx, yy))
        denominator = (sum(a * a for a in xx) * sum(b * b for b in yy)).sqrt()
        return float(numerator / denominator)


def offset_case():
    x = np.full(200, 1e308)
    x[100:] = np.nextafter(1e308, np.inf)
    return x, np.repeat([0.0, 1.0], 100)


class PearsonTests(unittest.TestCase):
    def test_source_pins(self):
        pins = {
            "n056/bank_a.py": "c100cfdebba46761ccbad5116812039eaa18b00679a6f2a00d9914fe61ba6211",
            "n056/evaluation.py": "4a89e59af0c709df47a6899f73081e227a194a9415ed4923a157fcaeda7a6392",
            "n056/protocol.py": "711f22f72c13293f07f5e9a44d6e74714e99a68b0f2a5a318dd515beea8918f2",
        }
        for name, expected in pins.items():
            self.assertEqual(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(), expected)

    def test_large_offset_regression_against_decimal(self):
        x, y = offset_case()
        oracle = decimal_pearson(x, y)
        actual = correlation(x[:, None], y[:, None])["mean"]
        prior = prior_correlation(x[:, None], y[:, None])["mean"]
        self.assertAlmostEqual(actual, oracle, places=14)
        self.assertGreater(abs(prior - oracle), 0.01)

    def test_high_precision_extremes(self):
        maximum = np.finfo(np.float64).max
        tiny = np.nextafter(0.0, 1.0)
        cases = [
            ([-maximum, maximum, -maximum / 2, maximum / 4], [3.0, -1.0, 2.0, 0.0]),
            ([tiny, 2 * tiny, 4 * tiny, 8 * tiny], [4.0, 0.0, -3.0, 1.0]),
            ([1.0, np.nextafter(1.0, 2.0), 1.0, np.nextafter(1.0, 2.0)], [1.0, 0.0, 2.0, -3.0]),
            ([-maximum, tiny, maximum, -tiny], [1.0, 2.0, 0.0, 7.0]),
        ]
        for x, y in cases:
            with self.subTest(x=x):
                expected = decimal_pearson(x, y)
                actual = correlation(np.array(x)[:, None], np.array(y)[:, None])["mean"]
                self.assertAlmostEqual(actual, expected, places=14)

    def test_ordinary_full_support_matches_predecessor(self):
        rng = np.random.default_rng(5601)
        y = rng.normal(size=(200, 1700))
        p = 0.4 * y + rng.normal(size=y.shape)
        old, new = prior_correlation(y, p), correlation(y, p)
        np.testing.assert_allclose(new["raw"], old["raw"], atol=3e-15, rtol=3e-15)
        self.assertAlmostEqual(new["mean"], old["mean"], places=14)

    def test_affine_sign_and_row_order(self):
        x = np.array([1.0, 1.25, 1.5, 2.0, 2.5, 4.0])
        y = np.array([2.0, -1.0, 1.0, 0.0, -2.0, 3.0])
        expected = decimal_pearson(x, y)
        for power in [-1000, 0, 1000]:
            a, b = np.ldexp(x, power), -np.ldexp(y, power)
            actual = correlation(a[::-1, None], b[::-1, None])["mean"]
            self.assertAlmostEqual(actual, -expected, places=14)

    def test_constants_are_exact_and_not_excluded(self):
        y = np.column_stack((np.arange(200.0), np.ones(200), np.arange(200.0)))
        p = np.column_stack((np.ones(200), np.arange(200.0), -np.arange(200.0)))
        result = correlation(y, p)
        self.assertEqual(result["raw"], [None, None, -1.0])
        self.assertEqual(result["score"], [0.0, None, -1.0])
        self.assertEqual(result["constant_target"], 1)
        self.assertEqual(result["constant_prediction"], 1)
        self.assertIsNone(result["mean"])
        defined = correlation(y[:, [0, 2]], p[:, [0, 2]])
        self.assertEqual(defined["mean"], -0.5)

    def test_invalid_values_and_support(self):
        valid = np.ones((200, 1700))
        for invalid in [np.zeros((199, 1700)), np.zeros((200, 17, 100)),
                        np.full(valid.shape, np.nan), np.full(valid.shape, np.inf),
                        valid.astype(complex), np.array([["x", "y"]])]:
            with self.subTest(shape=invalid.shape, dtype=str(invalid.dtype)):
                with self.assertRaises(ValueError):
                    correlation(valid, invalid)
        with self.assertRaises(ValueError):
            correlation(np.empty((200, 0)), np.empty((200, 0)))

    def test_inputs_not_modified(self):
        x, y = offset_case()
        x, y = x[:, None], y[:, None]
        a, b = x.copy(), y.copy()
        correlation(x, y)
        np.testing.assert_array_equal(a, x)
        np.testing.assert_array_equal(b, y)


class Panel:
    def __init__(self, array, constant_person=None):
        self.array = array
        self.calls = []
        self.constant_person = constant_person

    def outer_target(self, person):
        self.calls.append(person)
        mean = self.array.copy()
        if person == self.constant_person:
            mean[:, 0, 0] = 7.0
        return {"mean": mean, "half_odd": self.array, "half_even": -self.array}


def records_for(protocol, products):
    records = []
    for role in ROLES:
        for person in PEOPLE:
            for arm in ARMS:
                output = products["zero" if arm == "low_level" else
                                  "negative" if arm == "response_permuted" or person == PEOPLE[0] else "positive"]
                train = {"complete": True, "completed_ns": 1, "outputs": {"model": "generated"},
                         "source": {"program": "generated"}, "inputs": [{"root": "generated-train"}]}
                query = {"complete": True, "started_ns": 2, "model": train["outputs"],
                         "source": train["source"], "inputs": [{"root": "generated-query"}],
                         "exit_code": 0, "forced": False, "cleanup_empty": True,
                         "stream_eof": {"stdout": True, "stderr": True}, "outputs": output}
                records.append({"role": role, "person": person, "arm": arm, "train": train,
                                "query": query, "protocol_id": digest(protocol), "method_id": "generated-method"})
    return records


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Three small generated products are read by the real NPZ/custody/roster
        # admission path. No candidate process or authentic data is launched.
        cls.temp = tempfile.TemporaryDirectory(prefix="n056-generated-")
        cls.base = np.broadcast_to(np.arange(200, dtype=np.float32)[:, None, None], SHAPE).copy()
        cls.protocol = {"generated_fixture": "software-control-only"}
        cls.products = {}
        for name, array in [("positive", cls.base), ("negative", -cls.base), ("zero", np.zeros(SHAPE, dtype=np.float32))]:
            root = Path(cls.temp.name).resolve() / name
            root.mkdir()
            (root / "prediction.npz").write_bytes(encode({"prediction": array}))
            cls.products[name] = tree(root, 4_000_000, 1)
        cls.records = records_for(cls.protocol, cls.products)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_120_blocks_actual_admission_and_paired_aggregation(self):
        panel = Panel(self.base)
        result = evaluation.grade(panel, self.records, self.protocol, None)
        self.assertEqual(panel.calls, list(PEOPLE))
        self.assertEqual(result["all_final_blocks"], 120)
        self.assertFalse(result["correction_applied"])
        for role in ROLES:
            scores = result["roles"][role]
            means = scores["primary_equal_person_mean"]
            self.assertAlmostEqual(means["representation"], 0.8, places=14)
            self.assertEqual(means["low_level"], 0.0)
            self.assertAlmostEqual(means["response_permuted"], -1.0, places=14)
            self.assertAlmostEqual(scores["paired_controls"]["low_level"]["mean"], 0.8, places=14)
            self.assertAlmostEqual(scores["paired_controls"]["response_permuted"]["mean"], 1.8, places=14)
            self.assertEqual(len(scores["participant_coordinate_results"]["representation"][PEOPLE[0]]["raw"]), 1700)
        for person in PEOPLE:
            self.assertAlmostEqual(result["split_half_reliability"][person]["mean"], -1.0, places=14)

    def test_final_corruption_never_opens_target(self):
        records = copy.deepcopy(self.records)
        records[-1]["query"]["outputs"]["members"][0]["sha256"] = "0" * 64
        panel = Panel(self.base)
        with self.assertRaises(ValueError):
            evaluation.grade(panel, records, self.protocol, None)
        self.assertEqual(panel.calls, [])

    def test_missing_duplicate_role_lifetime_and_method_refuse_before_target(self):
        cases = [self.records[:-1], self.records[:-1] + [self.records[0]]]
        for mutation in ("lifetime", "method", "protocol"):
            records = copy.deepcopy(self.records)
            if mutation == "lifetime":
                records[-1]["query"]["started_ns"] = 0
            elif mutation == "method":
                records[-1]["method_id"] = "different"
            else:
                records[-1]["protocol_id"] = "0" * 64
            cases.append(records)
        for records in cases:
            panel = Panel(self.base)
            with self.assertRaises(ValueError):
                evaluation.grade(panel, records, self.protocol, None)
            self.assertEqual(panel.calls, [])

    def test_constant_target_propagates_to_full_primary(self):
        # The complete admission path is independently tested above; reuse its
        # admitted values here to isolate the missingness/aggregation policy.
        admitted = predecessor.collect(self.records, self.protocol, None)
        with patch.object(evaluation, "collect", return_value=admitted):
            result = evaluation.grade(Panel(self.base, PEOPLE[-1]), self.records, self.protocol, None)
        for role in ROLES:
            for arm in ARMS:
                self.assertIsNone(result["roles"][role]["primary_equal_person_mean"][arm])
                self.assertEqual(result["roles"][role]["participant_coordinate_results"][arm][PEOPLE[-1]]["constant_target"], 1)

    def test_private_axes_are_not_silently_reshaped(self):
        with self.assertRaises(ValueError):
            evaluation._target_arrays({name: self.base.transpose(1, 0, 2) for name in ("mean", "half_odd", "half_even")})

    def test_development_mixed_outer_people_rejected_before_targets(self):
        rows = [{"packet": {"person": PEOPLE[0], "inner_person": p, "arm": a}}
                for p in PEOPLE[1:] for a in ARMS]
        rows[-1]["packet"]["person"] = PEOPLE[1]
        with patch.object(evaluation, "prediction") as predictor:
            with self.assertRaises(ValueError):
                evaluation.development(object(), rows, None)
            predictor.assert_not_called()


if __name__ == "__main__":
    x, y = offset_case()
    print(json.dumps({"generated_precision_control": {
        "decimal_pearson": decimal_pearson(x, y),
        "predecessor_pearson": prior_correlation(x[:, None], y[:, None])["mean"],
        "successor_pearson": correlation(x[:, None], y[:, None])["mean"],
    }, "numpy_version": np.__version__, "python_version": sys.version.split()[0]}), flush=True)
    unittest.main(verbosity=2)
