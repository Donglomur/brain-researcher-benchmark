"""Generated, non-fitting controls for the actual author-stage producer path."""
import copy
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "original-figure4-v1" / "tests"))
from test_figure4 import census, predictions
import producer as p


def bundle(data):
    return {"schema": "plexus-figure4-features/v1", "census_sha256": p.f.digest(data),
            "preprocessing_receipt_sha256": data["preprocessing_receipt_sha256"],
            "panels": [{"family": panel["family"], "donor": panel["donor"],
                        "observation_ids": [r["observation_id"] for r in panel["observations"]],
                        "upstream_stage": "source_post_tvn_and_required_aggregation_pre_classifier_scaler",
                        "dtype": "float64",
                        "matrix_source_sha256": "a" * 64,
                        "values": [[float(i), float(i % 7)] for i in range(len(panel["observations"]))]}
                       for panel in data["panels"]]}


class RecordingRuntime:
    def __init__(self, *, fail_fit=None, fail_predict=None, bad_classes=False,
                 warn_fit=False, invalid_probability=False):
        self.scaled, self.models, self.events = [], [], []
        owner = self

        class Scaler:
            def fit_transform(self, values):
                owner.scaled.append(values.copy())
                owner.events.append("scale")
                return values + 100

        class Classifier:
            def __init__(self, **params):
                self.number = len(owner.models)
                self.params = params
                self.classes_ = np.asarray([1, 0] if bad_classes else [0, 1])
                self.n_iter_ = np.asarray([3], dtype=int)
                owner.models.append(self)

            def fit(self, values, labels):
                owner.events.append(f"fit:{self.number}")
                self.train = values.copy()
                self.labels = labels.copy()
                if self.number == fail_fit:
                    raise ValueError("controlled fit failure")
                if warn_fit:
                    warnings.warn("controlled convergence diagnostic", UserWarning)
                return self

            def get_params(self, deep=False):
                return {**self.params, "C": 1.0, "tol": 0.0001}

            def predict_proba(self, values):
                owner.events.append(f"predict:{self.number}")
                self.test = values.copy()
                if self.number == fail_predict:
                    raise ValueError("controlled prediction failure")
                positive = np.asarray([(int(x) % 7) / 6 for x in values[:, 0]])
                if invalid_probability:
                    positive[0] = np.nan
                return np.column_stack((1 - positive, positive))

        self.factories = (Scaler, Classifier, "generated-recording-shim-not-sklearn")


def run(data, features, runtime=None):
    runtime = runtime or RecordingRuntime()
    return p._produce(data, features, p.f.digest(data), p.f.digest(features), runtime.factories)


class Controls(unittest.TestCase):
    def setUp(self):
        self.data = census()
        self.features = bundle(self.data)

    def test_full_panel_scaling_precedes_original_asymmetric_fit_and_predict_order(self):
        runtime = RecordingRuntime()
        report = run(self.data, self.features, runtime)
        plan = p.f.prepare(self.data)
        self.assertEqual(len(runtime.scaled), 4)
        model_index = 0
        for source_panel, panel, scaled in zip(self.data["panels"], plan["panels"], runtime.scaled):
            ids = {r["observation_id"]: i for i, r in enumerate(source_panel["observations"])}
            self.assertEqual(scaled[:, 0].tolist(), list(range(panel["n_observations"])))
            for endpoint in panel["endpoints"]:
                for fold in endpoint["folds"]:
                    model = runtime.models[model_index]
                    self.assertEqual(model.train[:, 0].tolist(), [ids[r["observation_id"]] + 100 for r in fold["train"]])
                    self.assertEqual(model.labels.tolist(), [r["label"] for r in fold["train"]])
                    self.assertEqual(model.test[:, 0].tolist(), [ids[r["observation_id"]] + 100 for r in fold["test"]])
                    self.assertEqual(model.params, {"max_iter": 1000, "random_state": 42,
                                                   "penalty": "elasticnet", "solver": "saga", "l1_ratio": 0.5})
                    model_index += 1
        self.assertEqual(runtime.events[:5], ["scale", "fit:0", "fit:1", "predict:0", "predict:1"])
        self.assertEqual(report["producer_status"], "complete_declared_plan")
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual(report["runtime"]["sklearn"], "generated-recording-shim-not-sklearn")

    def test_complete_reference_joins_candidate_without_losing_source_control_tasks(self):
        report = run(self.data, self.features)
        candidate = [r for r in predictions(self.data)["scores"] if r["method"] == "candidate"]
        submission = p.assemble_submission(self.data, report, candidate)
        scored = p.f.evaluate(self.data, submission, p.f.digest(self.data))
        self.assertEqual(len(scored["auroc_vector"]), 48)
        self.assertTrue(any(r["guide_id"].startswith("non-targeting") for r in report["scores"]))
        self.assertEqual(report["source_metadata_skips"][0]["guides"], p.f.prepare(self.data)["panels"][0]["skipped_guides"])

    def test_explicit_float32_and_float64_dtype_survive_scaling_and_classifier_input(self):
        for dtype in ("float32", "float64"):
            features = copy.deepcopy(self.features)
            for panel in features["panels"]:
                panel["dtype"] = dtype
            runtime = RecordingRuntime()
            report = run(self.data, features, runtime)
            self.assertTrue(all(str(x.dtype) == dtype for x in runtime.scaled))
            self.assertTrue(all(str(m.train.dtype) == dtype for m in runtime.models))
            self.assertTrue(all(x["input_dtype"] == dtype and x["scaled_dtype"] == dtype
                                for x in report["panel_records"]))
        features["panels"][0]["dtype"] = "int32"
        with self.assertRaisesRegex(p.f.InputError, "floating dtype"):
            run(self.data, features)

    def test_first_fit_failure_emits_neither_fold_and_still_records_remaining_guides(self):
        runtime = RecordingRuntime(fail_fit=0)
        report = run(self.data, self.features, runtime)
        failed = report["fit_records"][0]
        self.assertEqual(failed["failure_stage"], "fit_fold_1")
        self.assertNotIn("fit:1", runtime.events)
        self.assertNotIn("predict:0", runtime.events)
        self.assertEqual(len(report["fit_records"]), 16)
        self.assertFalse(any(r["method"] == failed["method"] and r["donor"] == failed["donor"]
                             and r["guide_id"] == failed["guide_id"] for r in report["scores"]))
        self.assertEqual(report["producer_status"], "incomplete_declared_plan")

    def test_reciprocal_fit_failure_discards_entire_guide_before_predictions(self):
        runtime = RecordingRuntime(fail_fit=1)
        report = run(self.data, self.features, runtime)
        self.assertEqual(report["fit_records"][0]["failure_stage"], "fit_fold_2")
        self.assertNotIn("predict:0", runtime.events)
        self.assertEqual(len(report["fit_records"][0]["folds"]), 1)
        with self.assertRaisesRegex(p.f.InputError, "incomplete producer"):
            p.assemble_submission(self.data, report, [])

    def test_second_prediction_failure_cannot_leave_first_fold_predictions(self):
        runtime = RecordingRuntime(fail_predict=1)
        report = run(self.data, self.features, runtime)
        first = report["fit_records"][0]
        self.assertEqual(first["failure_stage"], "predict_fold_2")
        self.assertIn("predict:0", runtime.events)
        self.assertFalse(any(r["method"] == first["method"] and r["donor"] == first["donor"]
                             and r["guide_id"] == first["guide_id"] for r in report["scores"]))

    def test_convergence_diagnostics_are_retained_without_inventing_source_exclusion(self):
        report = run(self.data, self.features, RecordingRuntime(warn_fit=True))
        self.assertEqual(report["producer_status"], "complete_declared_plan")
        self.assertEqual(len(report["fit_records"][0]["warnings"]), 2)
        self.assertEqual(report["fit_records"][0]["folds"][0]["n_iter"], [3])
        self.assertIn("tol", report["fit_records"][0]["folds"][0]["resolved_parameters"])

    def test_wrong_feature_order_population_or_upstream_stage_is_rejected_before_scaling(self):
        for change in (lambda b: b["panels"][0]["observation_ids"].reverse(),
                       lambda b: b["panels"].pop(),
                       lambda b: b["panels"][0].update(upstream_stage="raw_embeddings"),
                       lambda b: b.update(preprocessing_receipt_sha256="0" * 64),
                       lambda b: b["panels"][0].update(donor="mutant")):
            features = copy.deepcopy(self.features); change(features)
            runtime = RecordingRuntime()
            with self.assertRaises(p.f.InputError):
                run(self.data, features, runtime)
            self.assertEqual(runtime.scaled, [])

    def test_frozen_bundle_and_census_pins_are_enforced(self):
        runtime = RecordingRuntime()
        with self.assertRaisesRegex(p.f.InputError, "census pin"):
            p._produce(self.data, self.features, "0" * 64, p.f.digest(self.features), runtime.factories)
        with self.assertRaisesRegex(p.f.InputError, "feature bundle pin"):
            p._produce(self.data, self.features, p.f.digest(self.data), "0" * 64, runtime.factories)
        self.assertFalse(runtime.scaled)

    def test_ragged_boolean_and_nonfinite_features_rejected(self):
        for value in ([1], [True, 2], [float("nan"), 2], [float("inf"), 2]):
            features = copy.deepcopy(self.features); features["panels"][0]["values"][0] = value
            with self.assertRaises(p.f.InputError):
                run(self.data, features)

    def test_wrong_probability_column_or_nonfinite_prediction_cannot_be_scored(self):
        for runtime in (RecordingRuntime(bad_classes=True), RecordingRuntime(invalid_probability=True)):
            report = run(self.data, self.features, runtime)
            self.assertEqual(report["producer_status"], "incomplete_declared_plan")
            self.assertEqual(report["scores"], [])

    def test_assembly_rejects_candidate_author_injection_and_missing_support(self):
        report = run(self.data, self.features)
        candidate = [r for r in predictions(self.data)["scores"] if r["method"] == "candidate"]
        with self.assertRaisesRegex(p.f.InputError, "candidate-only"):
            p.assemble_submission(self.data, report, report["scores"][:1])
        with self.assertRaisesRegex(p.f.InputError, "coverage"):
            p.assemble_submission(self.data, report, candidate[:-1])
        bad = copy.deepcopy(report); bad["scores"][0]["method"] = "candidate"
        with self.assertRaisesRegex(p.f.InputError, "author-only"):
            p.assemble_submission(self.data, bad, candidate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
