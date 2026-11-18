"""Generated controls for full-panel numerical comparison; no authentic data."""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("NEURAL056_REPO", HERE.parents[4]))
PRECISION = REPO / "benchmarks/neural/NEURAL-056/implementations/precision-v1"
SOURCE = REPO / ("benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/"
                 "authoring/delivery-20261105/common/remaining-builds-wave37/"
                 "neural056-complete-program/successor-v3/package")
sys.path[:0] = [str(PRECISION), str(SOURCE)]
import numpy as np
import n056_precision
from n056.arrays import encode
from n056.core import digest
from n056.protocol import ARMS, PEOPLE, ROLES, SHAPE
from n056.runtime import tree

# The explicit file is this change's postimage in private construction and its
# ordinary package member after integration. Existing numerical dependencies
# are imported from the selected repository, not copied into the test fixture.
spec = importlib.util.spec_from_file_location("n056_precision.reconciliation", HERE / "n056_precision/reconciliation.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class Panel:
    def __init__(self, mean, constant=False):
        self.mean, self.constant, self.calls = mean, constant, []

    def outer_target(self, person):
        self.calls.append(person)
        mean = self.mean.copy()
        if self.constant and person == PEOPLE[-1]:
            mean[:, 0, 1] = 1.0
        return {"mean": mean, "half_odd": self.mean, "half_even": self.mean}


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="n056-revision-generated-")
        cls.protocol = {"generated_fixture": "revision-diagnostic-only"}
        cls.prediction = np.broadcast_to(np.repeat([0.0, 1.0], 100)[:, None, None], SHAPE).copy()
        cls.mean = cls.prediction.copy()
        cls.mean[:, 0, 0] = 1e308
        cls.mean[100:, 0, 0] = np.nextafter(1e308, np.inf)
        product = Path(cls.temp.name).resolve() / "product"
        product.mkdir()
        raw = encode({"prediction": cls.prediction})
        # Keep all generated disk output within the leaf evidence allocation.
        assert len(raw) < 16384
        (product / "prediction.npz").write_bytes(raw)
        cls.generated_bytes = len(raw)
        outputs = tree(product, 4_000_000, 1)
        cls.records = []
        for role in ROLES:
            for person in PEOPLE:
                for arm in ARMS:
                    train = {"complete": True, "completed_ns": 1, "outputs": {"generated": "model"},
                             "source": {"generated": "source"}, "inputs": [{"root": "generated-train"}]}
                    query = {"complete": True, "started_ns": 2, "model": train["outputs"],
                             "source": train["source"], "inputs": [{"root": "generated-query"}],
                             "exit_code": 0, "forced": False, "cleanup_empty": True,
                             "stream_eof": {"stdout": True, "stderr": True}, "outputs": outputs}
                    cls.records.append({"role": role, "person": person, "arm": arm, "train": train,
                                        "query": query, "protocol_id": digest(cls.protocol), "method_id": "generated"})

    @classmethod
    def tearDownClass(cls):
        print("generated_fixture_bytes=" + str(cls.generated_bytes))
        cls.temp.cleanup()

    def call(self, panel, records=None, revision=comparison.REVISION):
        return comparison.compare_versions(panel, self.records if records is None else records,
                                           self.protocol, None, numerical_revision=revision)

    def test_exact_regression_is_retained_for_all_blocks_and_reliability(self):
        panel = Panel(self.mean)
        result = self.call(panel)
        self.assertEqual(panel.calls, list(PEOPLE))
        self.assertFalse(result["observed_numerical_agreement"])
        self.assertEqual(result["all_final_blocks"], 120)
        for person in PEOPLE:
            for role in ROLES:
                for arm in ARMS:
                    block = result["blocks"][person][role][arm]
                    self.assertEqual(block["score"]["total_cells"], 1700)
                    self.assertEqual(block["score"]["finite_cells_beyond_tolerance"], 1)
                    self.assertEqual(block["score"]["changed_definedness_cells"], 0)
                    self.assertAlmostEqual(block["score"]["maximum_finite_absolute_difference"], 1 - 2 ** -0.5)
                    self.assertAlmostEqual(block["precision"]["mean"], 1.0)
        for role in ROLES:
            self.assertAlmostEqual(result["aggregates"]["precision"][role]["primary_equal_person_mean"]["representation"], 1.0)
            self.assertEqual(result["aggregates"]["precision"][role]["paired_controls"]["low_level"]["mean"], 0.0)
        self.assertFalse(result["programme_revision_selected"])
        self.assertFalse(result["legacy_collector_executed"])
        self.assertFalse(result["scientifically_qualified"])

    def test_reliability_only_difference_changes_overall_flag(self):
        panel = Panel(self.prediction)
        def targets(person):
            panel.calls.append(person)
            return {"mean": self.prediction, "half_odd": self.mean, "half_even": self.prediction}
        panel.outer_target = targets
        result = self.call(panel)
        self.assertEqual(panel.calls, list(PEOPLE))
        self.assertTrue(result["observed_prediction_numerical_agreement"])
        self.assertFalse(result["observed_reliability_numerical_agreement"])
        self.assertFalse(result["observed_numerical_agreement"])
        for person in PEOPLE:
            difference = result["descriptive_split_half_reliability"][person]["raw"]
            self.assertEqual(difference["finite_cells_beyond_tolerance"], 1)
            self.assertAlmostEqual(difference["maximum_finite_absolute_difference"], 1 - 2 ** -0.5)
        self.assertFalse(result["reliability_correction_applied"])

    def test_constant_target_keeps_full_primary_undefined(self):
        result = self.call(Panel(self.mean, constant=True))
        for version in ("predecessor", "precision"):
            for role in ROLES:
                for arm in ARMS:
                    self.assertIsNone(result["aggregates"][version][role]["primary_equal_person_mean"][arm])

    def test_wrong_revision_refuses_before_any_target(self):
        panel = Panel(self.mean)
        with self.assertRaises(ValueError):
            self.call(panel, revision="unselected-v2")
        self.assertEqual(panel.calls, [])

    def test_missing_and_duplicate_blocks_refuse_before_targets(self):
        for records in (self.records[:-1], self.records[:-1] + [self.records[0]]):
            panel = Panel(self.mean)
            with self.assertRaises(ValueError):
                self.call(panel, records)
            self.assertEqual(panel.calls, [])

    def test_last_product_corruption_refuses_before_targets(self):
        records = copy.deepcopy(self.records)
        records[-1]["query"]["outputs"]["members"][0]["sha256"] = "0" * 64
        panel = Panel(self.mean)
        with self.assertRaises(ValueError):
            self.call(panel, records)
        self.assertEqual(panel.calls, [])

    def test_undefined_transition_is_not_hidden_as_agreement(self):
        a, b = [None] * 1700, [None] * 1700
        b[-1] = 0.0
        result = comparison._delta(a, b)
        self.assertEqual(result["changed_definedness_cells"], 1)
        self.assertEqual(result["both_undefined_cells"], 1699)
        self.assertIsNone(result["maximum_finite_absolute_difference"])
        self.assertFalse(result["agrees_within_tolerance"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
