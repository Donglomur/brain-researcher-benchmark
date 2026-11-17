"""Generated source-recipe controls; no original MEG features or fits are used."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fc_source_classifier", HERE / "classifier.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def generated_rows():
    result = []
    for number, participant in enumerate(C._scorer().published_participants()):
        for label, offset in (("face", -2), ("false", 4), ("letter", 7), ("object", 2)):
            result.append({"id": f"fixture-{participant}-{label}", "participant": participant,
                           "label": label, "value": offset + (number % 11)/20})
    return result


class ScalerControls(unittest.TestCase):
    def test_source_iqr_expression_and_batch_range(self):
        values = np.array([0., 1., 2., 4., 20.])
        fitted = C.mixed_sigmoid_fit(values)
        self.assertEqual(fitted["median"], 2)
        self.assertEqual(fitted["q25"], 1)
        self.assertEqual(fitted["q75"], 4)
        actual, details = C.mixed_sigmoid_transform(values, fitted)
        unscaled = np.array([1/(1+math.e**(-((x-2)/3/1.35))) for x in values])
        expected = (unscaled-unscaled.min())/(unscaled.max()-unscaled.min())
        np.testing.assert_allclose(actual, expected, atol=0, rtol=1e-15)
        wrong = np.array([1/(1+math.e**(-((x-2)/(3/1.35)))) for x in values])
        wrong = (wrong-wrong.min())/(wrong.max()-wrong.min())
        self.assertGreater(float(np.max(np.abs(actual-wrong))), 0.01)
        self.assertEqual(details["branch"], "median_iqr_then_1.35")
        self.assertEqual(details["range_scope"], "this_transform_batch")

    def test_zero_iqr_uses_population_sd_and_mean(self):
        fitted = C.mixed_sigmoid_fit([0, 0, 0, 0, 1])
        self.assertEqual(fitted["iqr"], 0)
        self.assertAlmostEqual(fitted["mean"], 0.2)
        self.assertAlmostEqual(fitted["sd_ddof0"], 0.4)
        actual, details = C.mixed_sigmoid_transform([-1, 0, 1], fitted)
        expected = np.array([1/(1+math.e**(-((x-.2)/.4))) for x in (-1, 0, 1)])
        expected = (expected-expected.min())/np.ptp(expected)
        np.testing.assert_allclose(actual, expected, rtol=1e-15)
        self.assertEqual(details["branch"], "mean_sd")

    def test_held_out_batch_controls_its_own_extrema(self):
        fitted = C.mixed_sigmoid_fit([-2, -1, 0, 1, 2])
        first, _ = C.mixed_sigmoid_transform([.2, .4, .6], fitted)
        changed, _ = C.mixed_sigmoid_transform([.2, .4, 20], fitted)
        self.assertEqual(first[0], 0)
        self.assertEqual(first[-1], 1)
        self.assertNotEqual(first[1], changed[1])
        one, _ = C.mixed_sigmoid_transform([.4], fitted)
        self.assertGreater(one[0], .5)
        self.assertLess(one[0], 1)

    def test_constant_fit_fails_without_silent_epsilon(self):
        fitted = C.mixed_sigmoid_fit([2, 2, 2])
        with self.assertRaisesRegex(C.ClassifierError, "divides by zero"):
            C.mixed_sigmoid_transform([1, 2, 3], fitted)

    def test_nonfinite_or_nonvector_source_refused(self):
        for values in ([1, np.nan], [1, np.inf], [], [[1], [2]]):
            with self.subTest(values=values), self.assertRaises(C.ClassifierError):
                C.mixed_sigmoid_fit(values)


class BlockControls(unittest.TestCase):
    def test_complete_four_class_screening_preserves_selected_order(self):
        rows = generated_rows()[::-1]
        selected, values, qc = C.prepare_source_block(rows)
        expected = [row for row in rows if row["label"] in ("face", "object")]
        self.assertEqual([r["id"] for r in selected], [r["id"] for r in expected])
        np.testing.assert_array_equal(values, [row["value"] for row in expected])
        self.assertEqual(qc["source_block_rows"], 376)
        self.assertEqual(qc["participants"], 94)
        self.assertEqual(len(selected), 188)
        self.assertAlmostEqual(qc["sample_sd_before_imputation"], np.std([r["value"] for r in rows], ddof=1))

    def test_null_and_nan_imputation_use_all_classes_before_pair_selection(self):
        rows = generated_rows()
        rows[0]["value"] = None
        rows[4]["value"] = float("nan")
        expected_mean = np.mean([r["value"] for r in rows if r["value"] is not None and math.isfinite(r["value"])])
        selected, values, qc = C.prepare_source_block(rows)
        self.assertAlmostEqual(qc["imputed_mean"], expected_mean)
        self.assertEqual(qc["missing_count"], 2)
        self.assertEqual(values[0], expected_mean)
        self.assertEqual(values[2], expected_mean)
        self.assertEqual(qc["imputed_observation_ids"], [rows[0]["id"], rows[4]["id"]])
        # Nonselected letter observations still affect the pre-pair imputation.
        changed = [dict(r) for r in rows]
        for row in changed:
            if row["label"] == "letter":
                row["value"] += 100
        _, _, changed_qc = C.prepare_source_block(changed)
        self.assertNotEqual(qc["imputed_mean"], changed_qc["imputed_mean"])

    def test_source_exclusion_thresholds_not_repaired(self):
        rows = generated_rows()
        for row in rows[:38]:
            row["value"] = None
        with self.assertRaisesRegex(C.ClassifierError, "missing_fraction_above_0.1"):
            C.prepare_source_block(rows)
        rows = generated_rows()
        for row in rows[:340]:
            row["value"] = 1
        with self.assertRaisesRegex(C.ClassifierError, "mode_fraction_above_0.9"):
            C.prepare_source_block(rows)
        for i, row in enumerate(rows):
            row["value"] = i * 1e-15
        with self.assertRaisesRegex(C.ClassifierError, "sample_sd_below_1e-10"):
            C.prepare_source_block(rows)

    def test_exact_ten_percent_nan_preserves_source_failure(self):
        rows = generated_rows()
        # Retain every person/category and add24 explicit rows to reach400.
        rows += [{**row, "id": row["id"] + "-repeat"} for row in rows[:24]]
        for row in rows[:40]:
            row["value"] = None
        with self.assertRaisesRegex(C.ClassifierError, "10percent boundary"):
            C.prepare_source_block(rows)

    def test_finite_values_cannot_emit_nonfinite_qc_statistics(self):
        rows = generated_rows()
        for i, row in enumerate(rows):
            row["value"] = (-1 if i % 2 else 1) * 1e308
        with self.assertRaisesRegex(C.ClassifierError, "block SD is nonfinite"):
            C.prepare_source_block(rows)

    def test_missing_categories_participants_duplicates_or_foreign_rows_refused(self):
        original = generated_rows()
        cases = [original[1:], original[4:], original + [dict(original[0])],
                 [{**original[0], "participant": "foreign"}] + original[1:],
                 [{**original[0], "label": "False"}] + original[1:],
                 [{**original[0], "value": True}] + original[1:],
                 [{**original[0], "value": np.inf}] + original[1:],
                 [{**original[0], "extra": "ignored"}] + original[1:]]
        for rows in cases:
            with self.subTest(rows=len(rows)), self.assertRaises(C.ClassifierError):
                C.prepare_source_block(rows)

    def test_explicit_repeated_source_rows_are_retained(self):
        rows = generated_rows()
        rows += [{**row, "id": row["id"] + "-repeat"} for row in rows[:4]]
        selected, _, qc = C.prepare_source_block(rows)
        self.assertEqual(qc["source_block_rows"], 380)
        self.assertEqual(len(selected), 190)
        self.assertEqual(selected[-2]["id"], rows[-4]["id"])


class OOFControls(unittest.TestCase):
    def test_real_generated_grouped_fit_connects_original_scorer(self):
        from sklearn.model_selection import StratifiedGroupKFold
        from sklearn.metrics import roc_auc_score
        rows = generated_rows()
        report = C.source_oof(rows, row_order_evidence="generated row order only")
        observations = report["observations"]
        self.assertEqual(len(observations), 188)
        self.assertEqual(report["score"]["participants"], 94)
        self.assertEqual(report["score"]["observations"], 188)
        self.assertEqual(report["fold_origin"], "new_source_style_StratifiedGroupKFold_realization")
        self.assertEqual(report["scientific_qualification"], "unestablished")
        self.assertEqual(report["source_environment_parity"], "unverified")
        selected, values, _ = C.prepare_source_block(rows)
        expected_folds = {}
        y = np.array([r["label"] for r in selected])
        groups = np.array([r["participant"] for r in selected])
        for fold, (_, held) in enumerate(StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=127).split(values[:, None], y, groups)):
            for i in held:
                expected_folds[selected[i]["id"]] = fold
        self.assertEqual({r["id"]: r["fold"] for r in observations}, expected_folds)
        predicted = report["probabilities_object"]
        actual_fold_accuracy, actual_fold_auc = [], []
        for fold in range(10):
            test = [r for r in observations if r["fold"] == fold]
            hits = [r["label"] == ("object" if predicted[r["id"]] > .5 else "face") for r in test]
            actual_fold_accuracy.append(sum(hits)/len(hits))
            actual_fold_auc.append(roc_auc_score([r["label"] == "object" for r in test],
                                                 [predicted[r["id"]] for r in test]))
            record = report["fold_records"][fold]
            train_ids, held_ids = set(record["training_observation_ids"]), set(record["held_out_observation_ids"])
            self.assertEqual(train_ids & held_ids, set())
            self.assertEqual(train_ids | held_ids, set(predicted))
            train_groups = {r["participant"] for r in observations if r["id"] in train_ids}
            held_groups = {r["participant"] for r in observations if r["id"] in held_ids}
            self.assertEqual(train_groups & held_groups, set())
            train_values = [v for r, v in zip(selected, values) if r["id"] in train_ids]
            self.assertAlmostEqual(record["source_scaler_fit"]["mean"], np.mean(train_values))
        self.assertAlmostEqual(report["score"]["accuracy"], np.mean(actual_fold_accuracy))
        self.assertAlmostEqual(report["score"]["accuracy_SD"], np.std(actual_fold_accuracy, ddof=0))
        self.assertEqual(report["score"]["fold_AUC"], actual_fold_auc)
        self.assertAlmostEqual(report["score"]["AUC"], np.mean(actual_fold_auc))
        self.assertAlmostEqual(report["score"]["AUC_SD"], np.std(actual_fold_auc, ddof=0))
        self.assertEqual(set(report["dependency_versions"]), {"numpy", "pandas", "scikit-learn", "scipy", "tslearn"})
        parameters = report["classifier_parameters"]
        self.assertEqual({key: parameters[key] for key in ("penalty", "C", "solver", "class_weight", "random_state")},
                         {"penalty": "l1", "C": 1, "solver": "liblinear", "class_weight": "balanced", "random_state": 127})

    def test_explicit_folds_preserved_without_authentication_claim(self):
        rows = generated_rows()[::-1]
        folds = {p: i % 10 for i, p in enumerate(C._scorer().published_participants())}
        report = C.source_oof(rows, row_order_evidence="explicit generated reverse order", folds=folds,
                              fold_evidence="generated illustration, not author folds")
        self.assertEqual(report["participant_to_fold"], folds)
        self.assertEqual(report["fold_origin"], "externally_supplied_unverified_realization")
        self.assertEqual([r["id"] for r in report["observations"]],
                         [r["id"] for r in rows if r["label"] in ("face", "object")])

    def test_bad_fold_declarations_refused_before_fitting(self):
        rows = generated_rows()
        folds = {p: i % 10 for i, p in enumerate(C._scorer().published_participants())}
        first = next(iter(folds))
        cases = [({p: f for p, f in folds.items() if p != first}, "missing"),
                 ({**folds, first: True}, "boolean"),
                 ({**folds, first: 10}, "range"),
                 ({p: 0 for p in folds}, "one fold"), (folds, None)]
        with patch("sklearn.linear_model.LogisticRegression.fit", side_effect=AssertionError("fit reached")):
            for bad, evidence in cases:
                with self.subTest(evidence=evidence), self.assertRaises(C.ClassifierError):
                    C.source_oof(rows, row_order_evidence="generated", folds=bad, fold_evidence=evidence)
            with self.assertRaises(C.ClassifierError):
                C.source_oof(rows, row_order_evidence="generated", fold_evidence="unbound")


if __name__ == "__main__":
    unittest.main()
