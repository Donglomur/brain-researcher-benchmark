"""Generated controls for the real C4 capture and classwise scoring path.

No authentic data, source package, targets, training or inference are loaded.
Run in the shared lightweight test pool. --predecessor documents the original
silent denominator/weighting failures before applying the repair.
"""
import json
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if len(sys.argv) == 3 and sys.argv[1] == "--predecessor":
    predecessor = Path(sys.argv[2])
    assert hashlib.sha256(predecessor.read_bytes()).hexdigest() == "34307b260b10b175196df81e2e3374a0056f037994234074ced16d0f829c8ce3"
    spec = importlib.util.spec_from_file_location("programme.evaluation", predecessor)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

import numpy as np
from programme.artifacts import Outputs
from programme.captured_prediction import (
    ProbabilityCapture, capture_probabilities, read_prediction,
)
from programme.cohort import CLASSES, SupportError, UnitKey
from programme.evaluation import Prediction, probability_products


def key(number, species="mouse"):
    return UnitKey(species, "invented_lab", "invented_animal", "session",
                   "recording", str(number))


def outputs(root):
    return Outputs(root, max_bytes=8_000_000, max_files=16,
                   max_member=4_000_000, max_read_bytes=16_000_000)


def products(units, probabilities, models=(("generated_model", "one"),)):
    prediction = Prediction(tuple(units), CLASSES, np.asarray(probabilities),
                            "generated_source", tuple(models))
    targets = {unit: CLASSES[index % 5] for index, unit in enumerate(dict.fromkeys(units))}
    return probability_products(prediction, tuple(units), targets, (0, 2),
                                threshold_rule="paper_survival_gt")


def predecessor_demonstration():
    units = (key(0), key(0), key(1))
    p = [[1., 0., 0., 0., 0.]] * 3
    result = products(units, p)
    assert result["threshold_products"][0]["total"].tolist() == [2, 1, 0, 0, 0]
    with tempfile.TemporaryDirectory(prefix="c4-generated-predecessor-") as root:
        owner = outputs(root)
        tensor = np.array([[[1., 0.], [0., 1.], [0., 0.], [0., 0.], [0., 0.]]])
        repeated_model = ((0, key(7)), (0, key(7)))
        capture = capture_probabilities(owner, "repeated", tensor, (key(0),),
                                        CLASSES, "generated_source", repeated_model)
        restored = read_prediction(owner, capture, (key(0),), "generated_source")
        assert restored.probabilities.tolist() == [[0.5, 0.5, 0., 0., 0.]]
    print(json.dumps({"generated_only": True, "predecessor_duplicate_rows_accepted": True,
                      "predecessor_duplicate_models_accepted": True,
                      "inflated_class_denominators": [2, 1, 0, 0, 0]}))


class DenominatorChecks(unittest.TestCase):
    def test_full_original_sized_loo_capture(self):
        units = tuple(key(i) for i in range(202))
        models = tuple((repeat, unit) for repeat in range(10) for unit in units)
        support = {"layout": "unit_loo_10", "row_model_indices":
                   tuple(tuple(repeat * 202 + row for repeat in range(10))
                         for row in range(202))}
        raw = np.zeros((202, 5, 10))
        for row in range(202):
            raw[row, row % 5, :] = 1
        with tempfile.TemporaryDirectory(prefix="c4-generated-loo-") as root:
            owner = outputs(root)
            capture = capture_probabilities(owner, "loo", raw, units, CLASSES,
                                            "generated_source", models, member_support=support)
            restored = read_prediction(owner, capture, units, "generated_source")
            targets = {unit: CLASSES[row % 5] for row, unit in enumerate(units)}
            report = probability_products(restored, units, targets, (0, 2),
                                          threshold_rule="paper_survival_gt")
            self.assertEqual(len(restored.model_identity), 2020)
            self.assertEqual(report["threshold_products"][0]["total"].tolist(), [41, 41, 40, 40, 40])
            self.assertEqual(report["threshold_products"][1]["retained"].sum(), 202)

    def test_complete_transfer_and_boundary_conventions(self):
        units = (key(1000, "macaque"), key(1001, "macaque"))
        models = tuple((repeat, key(unit)) for repeat in range(10) for unit in range(202))
        # Binary-exact probabilities: row 0 has confidence exactly 2; row 1
        # has infinite confidence. The means preserve these values exactly.
        raw = np.repeat(np.array([[.5, .25, .125, .0625, .0625], [0., 1., 0., 0., 0.]])[:, :, None], 2020, axis=2)
        with tempfile.TemporaryDirectory(prefix="c4-generated-transfer-") as root:
            owner = outputs(root)
            capture = capture_probabilities(owner, "transfer", raw, units, CLASSES,
                                            "generated_source", models)
            restored = read_prediction(owner, capture, units, "generated_source")
            targets = dict(zip(units, CLASSES[:2]))
            strict = probability_products(restored, units, targets, (0, 2), threshold_rule="paper_survival_gt")
            inclusive = probability_products(restored, units, targets, (2,), threshold_rule="released_prediction_ge")
            self.assertEqual(strict["threshold_products"][0]["retained"].tolist(), [1, 1, 0, 0, 0])
            self.assertEqual(strict["threshold_products"][1]["retained"].tolist(), [0, 1, 0, 0, 0])
            self.assertEqual(inclusive["threshold_products"][0]["retained"].tolist(), [1, 1, 0, 0, 0])
            self.assertTrue(np.isnan(strict["threshold_products"][1]["row_percent"][0]).all())

    def test_duplicate_biological_rows_refused_before_score(self):
        with self.assertRaises(SupportError):
            products((key(0), key(0), key(1)), [[1., 0., 0., 0., 0.]] * 3)

    def test_empty_population_refused(self):
        with self.assertRaises(SupportError):
            products((), np.empty((0, 5)))

    def test_incomplete_biological_identity_refused(self):
        with self.assertRaises(SupportError):
            products((UnitKey("mouse", "lab", "", "session", "rec", "0"),), [[1., 0., 0., 0., 0.]])

    def test_duplicate_models_refused_before_capture(self):
        with tempfile.TemporaryDirectory(prefix="c4-generated-duplicate-") as root:
            owner = outputs(root)
            raw = np.ones((1, 5, 2)) / 5
            with self.assertRaises(SupportError):
                capture_probabilities(owner, "duplicate", raw, (key(0),), CLASSES,
                                      "generated_source", ((0, key(7)), (0, key(7))))
            self.assertEqual(owner.records, [])

    def test_serialized_alias_duplicate_models_refused(self):
        with self.assertRaises(SupportError):
            products((key(0),), [[1., 0., 0., 0., 0.]],
                     ((0, key(7)), [0, key(7).__dict__]))

    def test_duplicate_models_refused_on_authenticated_read(self):
        with tempfile.TemporaryDirectory(prefix="c4-generated-readback-") as root:
            owner = outputs(root)
            body = owner.array("raw.npy", np.ones((1, 5, 2)) / 5)
            identity = owner.json("identity.json", {
                "schema": "c4_probability_capture_v3", "units": (key(0),),
                "classes": CLASSES, "source_identity": "generated_source",
                "models": ((0, key(7)), (0, key(7))), "tensor": body,
                "shape": (1, 5, 2), "reduction": "equal_member_mean_axis2",
                "member_support": {"layout": "global_members", "row_model_indices": None}})
            with self.assertRaises(SupportError):
                read_prediction(owner, ProbabilityCapture(body, identity), (key(0),), "generated_source")

    def test_grouped_composite_capture_remains_distinct(self):
        with tempfile.TemporaryDirectory(prefix="c4-generated-grouped-") as root:
            owner = outputs(root)
            capture = capture_probabilities(owner, "grouped", np.ones((1, 5, 1)) / 5,
                (key(0),), CLASSES, "generated_source", (("cross_fitted_group_reference", "a" * 64),))
            restored = read_prediction(owner, capture, (key(0),), "generated_source")
            self.assertEqual(restored.probabilities.tolist(), [[.2] * 5])


if __name__ == "__main__":
    if sys.argv[1:2] == ["--predecessor"]:
        predecessor_demonstration()
    else:
        unittest.main()
