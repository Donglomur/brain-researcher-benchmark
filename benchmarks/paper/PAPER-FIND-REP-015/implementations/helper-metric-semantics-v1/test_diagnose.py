"""Generated definition controls; no observations, fits or empirical grades."""
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diagnose import diagnose_counts


class MetricDefinitionTests(unittest.TestCase):
    def test_imbalance_exposes_all_three_definition_differences(self):
        result = diagnose_counts(dict(tp=8, tn=1, fp=9, fn=2))
        self.assertEqual(result["accuracy"], 9 / 20)
        self.assertAlmostEqual(result["reward_class"]["recall"], 8 / 10)
        self.assertAlmostEqual(result["fixed_two_class_macro"]["recall"], 9 / 20)
        self.assertAlmostEqual(result["reward_class"]["precision"], 8 / 17)
        self.assertAlmostEqual(result["fixed_two_class_macro"]["precision"], 41 / 102)
        self.assertAlmostEqual(result["reward_class"]["f1"], 16 / 27)
        self.assertAlmostEqual(result["fixed_two_class_macro"]["f1"], 131 / 351)
        self.assertEqual(result["definitions_differ"], dict(recall=True, precision=True, f1=True))

    def test_label_exchange_changes_reward_metric_but_not_macro(self):
        original = diagnose_counts(dict(tp=8, tn=1, fp=9, fn=2))
        exchanged = diagnose_counts(dict(tp=1, tn=8, fp=2, fn=9))
        self.assertNotEqual(original["reward_class"], exchanged["reward_class"])
        self.assertEqual(original["fixed_two_class_macro"], exchanged["fixed_two_class_macro"])
        self.assertEqual(original["accuracy"], exchanged["accuracy"])

    def test_perfect_and_inverted_nonempty_classes(self):
        for counts, expected in [(dict(tp=3, tn=9, fp=0, fn=0), 1.0),
                                 (dict(tp=0, tn=0, fp=9, fn=3), 0.0)]:
            with self.subTest(counts=counts):
                result = diagnose_counts(counts)
                self.assertEqual(set(result["reward_class"].values()), {expected})
                self.assertEqual(result["reward_class"], result["fixed_two_class_macro"])
                self.assertFalse(any(result["definitions_differ"].values()))

    def test_absent_class_does_not_invent_library_label_or_zero_policy(self):
        result = diagnose_counts(dict(tp=5, tn=0, fp=0, fn=0))
        self.assertEqual(set(result["reward_class"].values()), {1.0})
        self.assertEqual(set(result["fixed_two_class_macro"].values()), {None})
        self.assertEqual(set(result["definitions_differ"].values()), {None})
        self.assertEqual(result["historical_helper_equivalence"], "unresolved")

    def test_undefined_precision_does_not_erase_defined_recall_or_f1(self):
        result = diagnose_counts(dict(tp=0, tn=3, fp=0, fn=7))
        self.assertIsNone(result["fixed_two_class_macro"]["precision"])
        self.assertEqual(result["fixed_two_class_macro"]["recall"], 0.5)
        self.assertAlmostEqual(result["fixed_two_class_macro"]["f1"], 3 / 13)
        self.assertEqual(result["undefined_macro_metrics"], ["precision"])

    def test_reward_profile_matches_existing_registered_metric_component(self):
        default = HERE.parent / "source-svm-v1" / "score.py"
        path = Path(os.environ.get("CEREBELLAR_EXISTING_SCORE_PATH", str(default)))
        spec = importlib.util.spec_from_file_location("cerebellar_existing_score", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # An asymmetric, named trial roster; never read source observations.
        labels = {"a": 1, "b": 1, "c": 1, "d": 0, "e": 0, "f": 0, "g": 0}
        decisions = {"a": 1, "b": 1, "c": 0, "d": 1, "e": 1, "f": 1, "g": 0}
        existing = module._metrics(labels, decisions)
        diagnostic = diagnose_counts(existing["confusion"])
        self.assertEqual(existing["accuracy"], diagnostic["accuracy"])
        for original, new in [("sensitivity", "recall"), ("precision", "precision"), ("f1", "f1")]:
            self.assertTrue(math.isclose(existing[original], diagnostic["reward_class"][new]))
        self.assertTrue(diagnostic["definitions_differ"]["recall"])

    def test_rejects_missing_extra_negative_boolean_and_empty_counts(self):
        invalid = [None, [], {}, dict(tp=1, tn=0, fp=0),
                   dict(tp=1, tn=0, fp=0, fn=0, accuracy=1),
                   dict(tp=True, tn=1, fp=0, fn=0),
                   dict(tp=1.0, tn=1, fp=0, fn=0),
                   dict(tp=-1, tn=2, fp=0, fn=0),
                   dict(tp=0, tn=0, fp=0, fn=0)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                diagnose_counts(value)


if __name__ == "__main__":
    unittest.main(verbosity=1)
