"""Generated full-cohort paired role controls; no scientific data or execution."""
from __future__ import annotations

import copy
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
import n056_precision
# The same file runs both in the repository and against a task-local postimage.
n056_precision.__path__.insert(0, str(HERE / "n056_precision"))
import numpy as np
from n056.arrays import encode
from n056.core import digest
from n056.protocol import ARMS, PEOPLE, ROLES, SHAPE
from n056.runtime import tree
from n056_precision import evaluation


class Panel:
    def __init__(self, mean, constant_person=None):
        self.mean, self.constant_person, self.calls = mean, constant_person, []

    def outer_target(self, person):
        self.calls.append(person)
        mean = self.mean.copy()
        if person == self.constant_person:
            mean[:, 0, 0] = 7.0
        return {"mean": mean, "half_odd": self.mean, "half_even": self.mean}


def product_name(role, person, arm):
    if role == "reference_fixed":
        return "zero"
    if role == "reference_tuned":
        return "positive" if arm == "representation" else "zero"
    if role == "F":
        if arm == "representation":
            return "negative" if person in PEOPLE[:2] else "positive"
        return "positive" if arm == "low_level" else "zero"
    if arm == "representation":
        return "negative" if person == PEOPLE[-1] else "positive"
    return "zero" if arm == "low_level" else "negative"


class RoleComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="n056-role-comparison-")
        cls.base = np.broadcast_to(np.arange(200, dtype=np.float32)[:, None, None], SHAPE).copy()
        cls.protocol = {"generated_fixture": "paired-role-software-control-only"}
        products, cls.generated_bytes = {}, 0
        for name, array in (("positive", cls.base), ("negative", -cls.base),
                            ("zero", np.zeros(SHAPE, dtype=np.float32))):
            root = Path(cls.temp.name).resolve() / name
            root.mkdir()
            payload = encode({"prediction": array})
            cls.generated_bytes += len(payload)
            (root / "prediction.npz").write_bytes(payload)
            products[name] = tree(root, 4_000_000, 1)
        cls.records = []
        for role in ROLES:
            for person in PEOPLE:
                for arm in ARMS:
                    train = {"complete": True, "completed_ns": 1, "outputs": {"model": "generated"},
                             "source": {"program": "generated"}, "inputs": [{"root": "generated-train"}]}
                    query = {"complete": True, "started_ns": 2, "model": train["outputs"],
                             "source": train["source"], "inputs": [{"root": "generated-query"}],
                             "exit_code": 0, "forced": False, "cleanup_empty": True,
                             "stream_eof": {"stdout": True, "stderr": True},
                             "outputs": products[product_name(role, person, arm)]}
                    cls.records.append({"role": role, "person": person, "arm": arm,
                                        "train": train, "query": query,
                                        "protocol_id": digest(cls.protocol), "method_id": "generated-method"})

    @classmethod
    def tearDownClass(cls):
        print("generated_fixture_bytes=" + str(cls.generated_bytes))
        cls.temp.cleanup()

    def test_all_roles_people_and_arms_have_signed_paired_contrasts(self):
        panel = Panel(self.base)
        result = evaluation.grade(panel, self.records, self.protocol, None)
        self.assertEqual(panel.calls, list(PEOPLE))
        self.assertEqual(result["all_final_blocks"], 120)
        comparisons = result["paired_role_comparisons"]
        expected_pairs = {"I_minus_F", "F_minus_reference_fixed", "F_minus_reference_tuned",
                          "I_minus_reference_fixed", "I_minus_reference_tuned",
                          "reference_tuned_minus_reference_fixed"}
        self.assertEqual(set(comparisons), expected_pairs)
        for comparison in comparisons.values():
            self.assertEqual(comparison["direction"], "left_minus_right")
            self.assertEqual(set(comparison["arms"]), set(ARMS))
            for group in (comparison["arms"], comparison["control_effect_differences"]):
                for contrast in group.values():
                    self.assertEqual(list(contrast["by_person"]), list(PEOPLE))
        paired = comparisons["I_minus_F"]
        expected = dict(zip(PEOPLE, [2.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -2.0]))
        self.assertEqual(paired["arms"]["representation"]["by_person"], expected)
        self.assertAlmostEqual(paired["arms"]["representation"]["mean"], 0.2)
        self.assertEqual(paired["arms"]["low_level"]["mean"], -1.0)
        self.assertEqual(paired["arms"]["response_permuted"]["mean"], -1.0)
        for control in ("low_level", "response_permuted"):
            self.assertEqual(paired["control_effect_differences"][control]["by_person"],
                             {person: value + 1.0 for person, value in expected.items()})
            self.assertAlmostEqual(paired["control_effect_differences"][control]["mean"], 1.2)
        self.assertEqual(comparisons["reference_tuned_minus_reference_fixed"]["arms"]["representation"]["mean"], 1.0)
        for role, mean in (("reference_fixed", 0.0), ("reference_tuned", 1.0), ("F", 0.6), ("I", 0.8)):
            self.assertAlmostEqual(result["roles"][role]["primary_equal_person_mean"]["representation"], mean)
        self.assertFalse(result["scientifically_qualified"])
        self.assertFalse(result["correction_applied"])

    def test_undefined_person_is_retained_in_every_comparison(self):
        result = evaluation.grade(Panel(self.base, PEOPLE[-1]), self.records, self.protocol, None)
        for comparison in result["paired_role_comparisons"].values():
            for group in (comparison["arms"], comparison["control_effect_differences"]):
                for contrast in group.values():
                    self.assertEqual(len(contrast["by_person"]), 10)
                    self.assertIsNone(contrast["by_person"][PEOPLE[-1]])
                    self.assertIsNone(contrast["mean"])
                    self.assertIsNotNone(contrast["by_person"][PEOPLE[0]])

    def test_missing_or_duplicate_block_refuses_before_targets(self):
        for records in (self.records[:-1], self.records[:-1] + [self.records[0]]):
            panel = Panel(self.base)
            with self.assertRaises(ValueError):
                evaluation.grade(panel, records, self.protocol, None)
            self.assertEqual(panel.calls, [])

    def test_corrupt_final_product_refuses_before_targets(self):
        records = copy.deepcopy(self.records)
        records[-1]["query"]["outputs"]["members"][0]["sha256"] = "0" * 64
        panel = Panel(self.base)
        with self.assertRaises(ValueError):
            evaluation.grade(panel, records, self.protocol, None)
        self.assertEqual(panel.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
