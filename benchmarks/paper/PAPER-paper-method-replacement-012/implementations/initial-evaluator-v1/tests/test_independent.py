"""Independent hand-derived metric and source-identity controls.

Authored from the canonical contract and primary NuCLR source without borrowing
implementation formulas; these generated controls do not qualify native science.
"""
import importlib.util
from fractions import Fraction
from pathlib import Path
import unittest


_SPEC = importlib.util.spec_from_file_location(
    "nuclr_independent_control_target", Path(__file__).resolve().parents[1] / "evaluator.py"
)
evaluator = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(evaluator)


class IndependentMetricControls(unittest.TestCase):
    def test_hand_derived_unequal_class_confusion(self):
        result = evaluator.classification_metrics(
            ["A", "A", "A", "B", "B", "C"],
            ["A", "A", "B", "B", "C", "C"],
        )
        # TP/support/predicted: A 2/3/2, B 1/2/2, C 1/1/2.
        self.assertAlmostEqual(result["accuracy"], float(Fraction(2, 3)))
        self.assertAlmostEqual(result["balanced_accuracy"], float(Fraction(13, 18)))
        self.assertAlmostEqual(result["macro_f1"], float(Fraction(59, 90)))

    def test_predicted_only_class_uses_different_metric_denominators(self):
        result = evaluator.classification_metrics(["A", "A", "B"], ["A", "C", "C"])
        self.assertAlmostEqual(result["accuracy"], float(Fraction(1, 3)))
        self.assertAlmostEqual(result["balanced_accuracy"], float(Fraction(1, 4)))
        self.assertAlmostEqual(result["macro_f1"], float(Fraction(2, 9)))

    def test_absent_declared_class_is_reported_without_changing_source_metric(self):
        result = evaluator.classification_metrics(["A", "B"], ["A", "B"], ["A", "B", "C"])
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["balanced_accuracy"], 1.0)
        self.assertEqual(result["macro_f1"], 1.0)
        self.assertEqual(result["absent_true_labels"], ["C"])
        self.assertEqual(result["per_class"]["C"]["support"], 0)

    def test_pooling_unequal_cv_folds_is_not_mean_of_fold_metrics(self):
        first = evaluator.classification_metrics(["A"], ["A"])
        second = evaluator.classification_metrics(["A"] * 9, ["B"] * 9)
        pooled = evaluator.classification_metrics(["A"] * 10, ["A"] + ["B"] * 9)
        self.assertEqual((first["macro_f1"] + second["macro_f1"]) / 2, 0.5)
        self.assertAlmostEqual(pooled["balanced_accuracy"], 0.1)
        self.assertAlmostEqual(pooled["macro_f1"], float(Fraction(1, 11)))

    def test_identity_preserving_row_permutation_leaves_metrics_unchanged(self):
        truth = ["B", "A", "B", "C", "A"]
        predicted = ["A", "A", "C", "C", "B"]
        original = evaluator.classification_metrics(truth, predicted)
        order = [4, 1, 3, 0, 2]
        permuted = evaluator.classification_metrics(
            [truth[i] for i in order], [predicted[i] for i in order]
        )
        self.assertEqual(original, permuted)

    def test_external_sklearn_metric_oracle(self):
        from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
        vectors = [
            (["A", "B", "C"], ["A", "B", "C"]),
            (["A", "A", "B", "C"], ["B", "C", "C", "A"]),
            (["A", "A", "A", "B", "C"], ["A", "A", "A", "A", "A"]),
        ]
        for truth, predicted in vectors:
            with self.subTest(truth=truth, predicted=predicted):
                result = evaluator.classification_metrics(truth, predicted)
                self.assertAlmostEqual(result["accuracy"], accuracy_score(truth, predicted))
                self.assertAlmostEqual(result["balanced_accuracy"], balanced_accuracy_score(truth, predicted))
                self.assertAlmostEqual(result["macro_f1"], f1_score(truth, predicted, average="macro"))


class IndependentIdentityControls(unittest.TestCase):
    def test_source_neuron_index_and_label_derivation(self):
        rows = evaluator.session_metadata("sb028_20191107", ["EC", "IN", "Pvalb-Tac1", "Lamp5-Npy"], 4)
        self.assertEqual([r["id"] for r in rows], [f"sb028_20191107_u{i}" for i in range(4)])
        self.assertEqual([r["ei_class"] for r in rows], ["EC", "IN", "IN", "IN"])
        self.assertEqual([r["subclass"] for r in rows], ["unknown", "unknown", "Pvalb", "Lamp5"])

    def test_activity_and_transcriptomic_row_count_mismatch_rejected(self):
        with self.assertRaises(evaluator.ContractError):
            evaluator.session_metadata("sb028_20191107", ["EC", "IN"], 3)

    def test_invalid_label_values_do_not_silently_drop_rows(self):
        for truth, prediction in [([], []), (["A"], []), (["A", None], ["A", "B"])]:
            with self.subTest(truth=truth, prediction=prediction):
                with self.assertRaises(evaluator.ContractError):
                    evaluator.classification_metrics(truth, prediction)

    def test_out_of_vocabulary_prediction_rejected(self):
        with self.assertRaises(evaluator.ContractError):
            evaluator.classification_metrics(["EC", "IN"], ["EC", "unknown"], ["EC", "IN"])


if __name__ == "__main__":
    unittest.main()
