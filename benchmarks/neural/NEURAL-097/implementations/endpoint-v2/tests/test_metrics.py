"""Generated endpoint controls only: no recordings, protected roster or fits."""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT.parent / "registered-runtime/full-cogitate-meg-v1/n097"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


current = load("n097_endpoint_v2", ROOT / "metrics.py")
package = types.ModuleType("n097_endpoint_legacy_control")
package.__path__ = [str(LEGACY)]
sys.modules[package.__name__] = package
legacy = load(package.__name__ + ".metrics", LEGACY / "metrics.py")


def panel():
    targets, predictions = {}, {arm: {} for arm in current.ARMS}
    # Unequal class, participant and cell sizes are deliberate; no real data.
    for person in range(33):
        for relevance in current.RELEVANCES:
            for d, duration in enumerate(current.DURATIONS):
                for o, orientation in enumerate(current.ORIENTATIONS):
                    for y in (0, 1):
                        for repeat in range(1 + (person + d + o + y) % 3):
                            key = f"generated-{len(targets)}"
                            targets[key] = {"person_index": person, "y": y,
                                            "stratum": [relevance, duration, orientation]}
                            for a, arm in enumerate(current.ARMS):
                                predictions[arm][key] = ((person + 2 * d + o + y + repeat + a) % 9) / 8
    return targets, predictions


def remove(targets, predictions, keys):
    for key in keys:
        del targets[key]
        for arm in current.ARMS:
            del predictions[arm][key]


class EndpointTests(unittest.TestCase):
    def test_predecessor_identity_and_numerical_parity(self):
        self.assertEqual(hashlib.sha256((LEGACY / "metrics.py").read_bytes()).hexdigest(),
                         "57f6d07b8012d76d95fd82571e742ffd6d2402b0aa31eb2a4134ebf32f31bc0f")
        targets, predictions = panel()
        self.assertEqual(current.evaluate(targets, predictions), legacy.evaluate(targets, predictions))

    def test_independent_equal_cell_and_person_weighting(self):
        targets, predictions = panel()
        # Every cell is perfect except p0/Irrelevant/500ms/Center, completely wrong.
        for key, row in targets.items():
            bad = row["person_index"] == 0 and row["stratum"] == ["Irrelevant", "500ms", "Center"]
            for arm in current.ARMS:
                predictions[arm][key] = 1 - row["y"] if bad else row["y"]
        result = current.evaluate(targets, predictions)
        self.assertAlmostEqual(result["primary_value"], 1 - 1 / (33 * 9))
        metric = result["macro"]["SIGNAL"]["Irrelevant"]
        self.assertAlmostEqual(metric["balanced_logloss"], -math.log(1e-15) / (33 * 9))
        self.assertAlmostEqual(metric["balanced_brier"], 1 / (33 * 9))
        self.assertEqual(result["macro"]["SIGNAL"]["Relevant non-target"]["balanced_accuracy"], 1)

    def test_balanced_and_legacy_loss_differ(self):
        targets, predictions = panel()
        for key, row in targets.items():
            for arm in current.ARMS:
                predictions[arm][key] = .75 if row["y"] else .5
        result = current.evaluate(targets, predictions)
        cell = result["persons"][0]["arms"]["SIGNAL"]["Irrelevant"]["cells"][0]
        self.assertEqual(cell["class_counts"], [1, 2])
        self.assertAlmostEqual(cell["balanced_logloss"], (-math.log(.5) - math.log(.75)) / 2)
        self.assertAlmostEqual(cell["legacy_logloss"], (-math.log(.5) - 2 * math.log(.75)) / 3)
        self.assertAlmostEqual(cell["balanced_brier"], (.5 ** 2 + .25 ** 2) / 2)

    def test_missing_class_nulls_only_corresponding_relevance(self):
        targets, predictions = panel()
        keys = [key for key, row in targets.items() if row["person_index"] == 0 and row["y"] == 1
                and row["stratum"] == ["Irrelevant", "500ms", "Center"]]
        remove(targets, predictions, keys)
        result = current.evaluate(targets, predictions)
        self.assertEqual(result, legacy.evaluate(targets, predictions))
        self.assertFalse(result["full_support_complete"])
        self.assertIsNone(result["primary_value"])
        self.assertIsNotNone(result["macro"]["SIGNAL"]["Irrelevant"]["legacy_logloss"])
        self.assertIsNotNone(result["macro"]["SIGNAL"]["Relevant non-target"]["balanced_accuracy"])
        self.assertEqual(len(result["persons"]), 33)

    def test_empty_cell_also_nulls_legacy_loss(self):
        targets, predictions = panel()
        keys = [key for key, row in targets.items() if row["person_index"] == 0
                and row["stratum"] == ["Irrelevant", "500ms", "Center"]]
        remove(targets, predictions, keys)
        result = current.evaluate(targets, predictions)
        self.assertEqual(result, legacy.evaluate(targets, predictions))
        self.assertTrue(all(value is None for value in result["macro"]["SIGNAL"]["Irrelevant"].values()))

    def test_chance_boundary_and_complete_support_counts(self):
        targets, predictions = panel()
        for arm in current.ARMS:
            predictions[arm] = dict.fromkeys(targets, .5)
        result = current.evaluate(targets, predictions)
        self.assertEqual(result["primary_value"], .5)
        self.assertAlmostEqual(result["macro"]["SIGNAL"]["Irrelevant"]["balanced_logloss"], math.log(2))
        self.assertEqual(result["macro"]["SIGNAL"]["Irrelevant"]["balanced_brier"], .25)
        self.assertTrue(result["full_support_complete"])
        self.assertEqual(sum(len(person["arms"]["SIGNAL"][rel]["cells"])
                             for person in result["persons"] for rel in current.RELEVANCES), 594)

    def test_malformed_target_identity_and_strata_refused(self):
        targets, predictions = panel()
        key = next(iter(targets))
        mutations = [
            ("person_index", False), ("person_index", 0.0), ("person_index", -1), ("person_index", 33),
            ("y", True), ("y", 0.0), ("y", 2),
            ("stratum", ["Irrelevant", "500ms", "Center", "extra"]),
            ("stratum", ("Irrelevant", "500ms", "Center")),
            ("stratum", ["Irrelevant", "500ms"]),
            ("stratum", ["Irrelevant", "500ms", "unknown"]),
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(targets)
                changed[key][field] = value
                with self.assertRaises(current.EndpointError):
                    current.evaluate(changed, predictions)
        # The historical bug accepted bool/float equality as participant identity.
        changed = copy.deepcopy(targets)
        changed[key]["person_index"] = False
        self.assertTrue(legacy.evaluate(changed, predictions)["full_support_complete"])

    def test_missing_participant_and_case_identity_fail(self):
        targets, predictions = panel()
        remove(targets, predictions, [key for key, row in targets.items() if row["person_index"] == 32])
        with self.assertRaises(current.EndpointError):
            current.evaluate(targets, predictions)
        targets, predictions = panel()
        del predictions["PRE"][next(iter(targets))]
        with self.assertRaises(current.EndpointError):
            current.evaluate(targets, predictions)
        targets, predictions = panel()
        predictions["PRE"]["extra-case"] = .5
        with self.assertRaises(current.EndpointError):
            current.evaluate(targets, predictions)
        del predictions["PRE"]
        with self.assertRaises(current.EndpointError):
            current.evaluate(targets, predictions)

    def test_nonfinite_out_of_range_or_boolean_probabilities_fail(self):
        targets, predictions = panel()
        key = next(iter(targets))
        for invalid in (True, float("nan"), float("inf"), -.1, 1.1, "0.5", 10 ** 400):
            with self.subTest(invalid=type(invalid).__name__):
                predictions["PRE"][key] = invalid
                with self.assertRaises(current.EndpointError):
                    current.evaluate(targets, predictions)

    def test_arm_distinction_and_target_metadata_not_exposed(self):
        targets, predictions = panel()
        for key, row in targets.items():
            row["private_source_join"] = "generated-secret-sentinel"
            predictions["SIGNAL"][key] = row["y"]
            predictions["PRE"][key] = 1 - row["y"]
        before = copy.deepcopy((targets, predictions))
        result = current.evaluate(targets, predictions)
        self.assertEqual(result["primary_value"], 1)
        self.assertEqual(result["macro"]["PRE"]["Irrelevant"]["balanced_accuracy"], 0)
        self.assertNotIn("generated-secret-sentinel", repr(result))
        self.assertEqual((targets, predictions), before)


if __name__ == "__main__":
    unittest.main()
