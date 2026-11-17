"""Independent generated controls for NEURAL-025 construction.

Expected predictions below were derived before reading pipeline.py. They test
source behavior, not authentic calcium/kinematic agreement or qualification.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "benchmarks/neural/NEURAL-025/implementations/train-only-decoding-v1/pipeline.py"
SPEC = importlib.util.spec_from_file_location("calcium_pipeline_under_test", SOURCE)
PIPELINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PIPELINE
SPEC.loader.exec_module(PIPELINE)


class IndependentKernelControls(unittest.TestCase):
    def fit(self, X=None, Y=None, **overrides):
        if X is None:
            X = np.array([[-3., 0.], [-1., 0.], [1., 0.], [3., 0.]])
        if Y is None:
            Y = np.array([[-5.], [-1.], [3.], [7.]])
        options = dict(roi_ids=["signal", "constant"], cell_budget=2,
                       pca_components=1, ridge_alpha=0.)
        options.update(overrides)
        return PIPELINE.fit_train_only(X, Y, **options)

    def test_axis_pca_ols_matches_hand_derived_line(self):
        model = self.fit()
        actual = PIPELINE.predict(model, np.array([[2., 0.], [-2., 0.]]),
                                  roi_ids=["signal", "constant"])
        np.testing.assert_allclose(actual, [[5.], [-3.]], rtol=1e-13, atol=1e-13)
        np.testing.assert_allclose(model.mean_y, [1.], rtol=0, atol=0)

    def test_sum_loss_ridge_has_unpenalized_intercept(self):
        # sum x^2=20, sum x*(y-1)=40, beta=40/(20+2).
        model = self.fit(ridge_alpha=2.)
        actual = PIPELINE.predict(model, np.array([[2., 0.]]),
                                  roi_ids=["signal", "constant"])
        np.testing.assert_allclose(actual, [[51 / 11]], rtol=1e-13, atol=1e-13)

    def test_oblique_pca_ridge_uses_unscaled_training_covariance(self):
        # PC score=sqrt(5)*x, SS=100, covariance=40*sqrt(5).
        X = np.array([[-3., -6.], [-1., -2.], [1., 2.], [3., 6.]])
        model = self.fit(X=X, ridge_alpha=2.)
        actual = PIPELINE.predict(model, np.array([[2., 4.]]),
                                  roi_ids=["signal", "constant"])
        np.testing.assert_allclose(actual, [[251 / 51]], rtol=1e-13, atol=1e-13)

    def test_nonzero_center_multitarget_and_discarded_component(self):
        # Unique PC1 is x (SS8 versus SS2). Coefficients after alpha2
        # shrink 2 to1.6 and -1 to-0.8; target means remain3 and-4.
        X = np.array([[8., 20.], [12., 20.], [10., 19.], [10., 21.]])
        Y = np.array([[-1., -2.], [7., -6.], [-2., -11.], [8., 3.]])
        model = self.fit(X=X, Y=Y, ridge_alpha=2.)
        actual = PIPELINE.predict(model, np.array([[11., 100.], [11., -100.]]),
                                  roi_ids=["signal", "constant"])
        np.testing.assert_allclose(actual, [[23 / 5, -24 / 5], [23 / 5, -24 / 5]],
                                   rtol=1e-13, atol=1e-13)

    def test_roi_variance_ties_use_identifier_order(self):
        X = np.array([[-3., 3.], [-1., 1.], [1., -1.], [3., -3.]])
        model = self.fit(X=X, roi_ids=["zeta", "alpha"], cell_budget=1)
        self.assertEqual(list(model.selected_roi_ids), ["alpha"])
        actual = PIPELINE.predict(model, np.array([[2., -2.]]), roi_ids=["zeta", "alpha"])
        np.testing.assert_allclose(actual, [[5.]], rtol=1e-13, atol=1e-13)

    def test_prediction_does_not_mutate_fitted_state(self):
        model = self.fit()
        before = json.dumps(PIPELINE.model_record(model), sort_keys=True, allow_nan=False)
        PIPELINE.predict(model, np.array([[1e6, -1e6], [-1e6, 1e6]]),
                         roi_ids=["signal", "constant"])
        after = json.dumps(PIPELINE.model_record(model), sort_keys=True, allow_nan=False)
        self.assertEqual(before, after)

    def test_tiny_finite_training_target_scale_does_not_underflow(self):
        Y = np.array([[-1e-200], [1e-200], [-1e-200], [1e-200]])
        model = self.fit(Y=Y)
        np.testing.assert_allclose(model.training_target_sd, [1e-200], rtol=1e-14, atol=0.)

    def test_tiny_finite_feature_variance_preserves_roi_ranking(self):
        X = np.array([[-1e-200, -2e-200], [1e-200, 2e-200]])
        model = self.fit(X=X, Y=np.array([[-1.], [1.]]),
                         roi_ids=["a_small", "z_large"], cell_budget=1)
        self.assertEqual(list(model.selected_roi_ids), ["z_large"])
        actual = PIPELINE.predict(model, [[2e-200, 4e-200]], roi_ids=["a_small", "z_large"])
        np.testing.assert_allclose(actual, [[2.]], rtol=1e-13, atol=0.)

    def test_mixed_json_integer_is_checked_before_float_rounding(self):
        X = [[-3, 0.0], [-1, 0.0], [1, 0.0], [2**53 + 1, 0.0]]
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(X=X)

    def test_mixed_json_boolean_is_not_coerced_to_numeric_feature(self):
        X = [[True, 0.0], [-1, 0.0], [1, 0.0], [3, 0.0]]
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(X=X)

    def test_refuses_ragged_training_features(self):
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(X=[[-3., 0.], [-1.], [1., 0.], [3., 0.]])

    def test_refuses_nonfinite_training_features(self):
        for bad in [np.nan, np.inf, -np.inf]:
            with self.subTest(value=bad):
                X = np.array([[-3., 0.], [-1., 0.], [1., 0.], [3., bad]])
                with self.assertRaises(PIPELINE.Refusal):
                    self.fit(X=X)

    def test_refuses_nonfinite_training_targets(self):
        for bad in [np.nan, np.inf, -np.inf]:
            with self.subTest(value=bad):
                Y = np.array([[-5.], [-1.], [3.], [bad]])
                with self.assertRaises(PIPELINE.Refusal):
                    self.fit(Y=Y)

    def test_refuses_duplicate_roi_identity(self):
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(roi_ids=["same", "same"])

    def test_refuses_unmatched_training_sample_counts(self):
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(Y=np.array([[-5.], [-1.], [3.]]))

    def test_refuses_invalid_ridge_penalty(self):
        for bad in [-1., np.nan, np.inf]:
            with self.subTest(value=bad), self.assertRaises(PIPELINE.Refusal):
                self.fit(ridge_alpha=bad)

    def test_refuses_unavailable_cell_budget(self):
        with self.assertRaises(PIPELINE.Refusal):
            self.fit(cell_budget=3)

    def test_refuses_unrecognized_prediction_roi(self):
        model = self.fit()
        with self.assertRaises(PIPELINE.Refusal):
            PIPELINE.predict(model, np.array([[2., 0.]]), roi_ids=["another-session", "constant"])

    def test_refuses_nonfinite_candidate_features(self):
        model = self.fit()
        with self.assertRaises(PIPELINE.Refusal):
            PIPELINE.predict(model, np.array([[np.nan, 0.]]), roi_ids=["signal", "constant"])


# Source-domain facts are copied independently from the pinned author contract,
# not taken from the module under test when constructing accepted inputs.
EXPECTED_JOINTS = [
    "SHDRf", "SHDRa", "SHDRr", "ELBOf", "WRSTf", "WRSTd", "WRSTr",
    "MCP1f", "MCP2f", "MCP3f", "MCP4f", "MCP1a", "MCP2a", "MCP3a",
    "MCP4a", "MCP1o", "MCP4o", "P1P2", "P2P3", "P3P4", "PIP1f",
    "PIP2f", "PIP3f", "PIP4f",
]
EXPECTED_SESSIONS = {
    "cfa17_20200825_172828": ("cfa17", "M1"),
    "cfa17_20200827_165724": ("cfa17", "S1"),
    "cfa19_20200820_143508": ("cfa19", "M1"),
    "cfa19_20200826_191222": ("cfa19", "S1"),
    "cfa20_20201114_194635": ("cfa20", "M1"),
    "cfa20_20201118_200612": ("cfa20", "S1"),
    "cfa22_20220605_182006": ("cfa22", "M1"),
    "cfa22_20220611_174801": ("cfa22", "S1"),
    "cfa24_20220727_160603": ("cfa24", "M1"),
    "cfa24_20220724_155906": ("cfa24", "S1"),
}
EXPECTED_MICE = ["cfa17", "cfa19", "cfa20", "cfa22", "cfa24"]


def independent_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def fixture(*, unequal_trials=False, calibrated=False):
    """Invented complete-domain normalized arrays, never native-data evidence.

    Two training trials per session each contain [-1,+1] in every target;
    training SD is exactly1. Every trial has the same two-sample fixed window.
    """
    identity = dict(task_id="NEURAL-025", author_commit="815b610b3beddfed5a3abf611d3a465ab9e4ce5c",
                    joint_names=EXPECTED_JOINTS[:], target_field="jointAngles", target_units="degrees",
                    feature_variant="smoothed_deconvolved_events",
                    event_conditioning="retrospective_public_liftTimeDLC",
                    upstream_exposure_policy="processed_inputs_no_fold_safe_claim")
    protocol = dict(identity, schema="calcium_protocol_v1", metric_policy="train_sd_trial_session_mouse_macro_v1",
                    condition="calibrated_new_mouse_local_baseline" if calibrated else "within_mouse",
                    recipe_selection="fixed_before_evaluation_no_data_tuning",
                    window_ms=[0, 10], grid_step_ms=10, cell_budget=1,
                    pca_components=1, ridge_alpha=0.,
                    limits={"max_total_timepoints": 1000, "max_rois_per_session": 2,
                            "max_trials_per_session": 20}, sessions=[], new_mouse_cases=[])
    dataset = dict(identity, schema="calcium_normalized_v1", sessions=[])
    predictions = {}
    for sid, (mouse, region) in EXPECTED_SESSIONS.items():
        training = [sid + ":train0", sid + ":train1"]
        n_eval = 10 if unequal_trials and mouse != "cfa17" else 1
        evaluation = [sid + ":eval" + str(i) for i in range(n_eval)]
        all_ids = training + evaluation
        shared = dict(session_id=sid, mouse_id=mouse, region=region,
                      roi_ids=[sid + ":cell_signal", sid + ":cell_constant"],
                      native_neural_field="data", upstream_temporal_support_ms=[-70, 80])
        for field in ["source_asset_sha256", "clock_evidence_sha256",
                      "feature_provenance_sha256", "normalization_recipe_sha256", "upstream_exposure_sha256",
                      "trial_selection_policy_sha256"]:
            shared[field] = hashlib.sha256(("invented:" + sid + ":" + field).encode()).hexdigest()
        protocol["sessions"].append(dict(shared, all_trial_ids=all_ids,
                                         training_trial_ids=training, evaluation_trial_ids=evaluation,
                                         trial_census_sha256=independent_digest(all_ids)))
        trials = []
        for tid in all_ids:
            trials.append(dict(trial_id=tid, neural_trial_id=tid, target_trial_id=tid,
                               neural_time_ms=[0, 10], target_time_ms=[0, 10],
                               neural=[[-1., 0.], [1., 0.]],
                               targets=[[-1.] * 24, [1.] * 24]))
        dataset["sessions"].append(dict(shared, trials=trials))
        predictions[sid] = {tid: [[-1.] * 24, [1.] * 24] for tid in evaluation}
    if calibrated:
        for mouse in EXPECTED_MICE:
            protocol["new_mouse_cases"].append({
                "heldout_mouse": mouse,
                "development_mice": [m for m in EXPECTED_MICE if m != mouse],
                "transfer": "none_session_local_calibration_only",
                "calibration_label_access": "declared_training_trials_only",
                "calibration_trials": {s["session_id"]: s["training_trial_ids"]
                                       for s in protocol["sessions"] if s["mouse_id"] == mouse},
            })
    # JSON packets do not carry Python object aliases between fields/documents.
    return json.loads(json.dumps(dataset)), json.loads(json.dumps(protocol)), predictions


def control_fixture():
    """Whole-trial signal with independently derived control predictions.

    Each LR stratum has amplitude1 and3 training trials; evaluation amplitude2.
    Training SD=sqrt5; neural/phase/phase×LR are exact, target-only predicts0,
    and within-LR rotation produces slope3/5 and NRMSE4/(5sqrt5).
    """
    dataset, protocol, _ = fixture()
    context = {"schema": "calcium_reach_context_v1", "task_id": "NEURAL-025",
               "event_conditioning": "retrospective_public_liftTimeDLC", "sessions": []}
    for session, binding in zip(dataset["sessions"], protocol["sessions"]):
        sid = session["session_id"]
        settings = [("z-left-one", "left", 1., True), ("a-left-three", "left", 3., True),
                    ("q-right-one", "right", 1., True), ("b-right-three", "right", 3., True),
                    ("eval-left-two", "left", 2., False), ("eval-right-two", "right", 2., False)]
        trials, rows, training, evaluation = [], [], [], []
        for index, (label, direction, amplitude, is_training) in enumerate(settings):
            tid = sid + ":" + label
            (training if is_training else evaluation).append(tid)
            trials.append({"trial_id": tid, "neural_trial_id": tid, "target_trial_id": tid,
                           "neural_time_ms": [0, 10], "target_time_ms": [0, 10],
                           "neural": [[-amplitude, 0.], [amplitude, 0.]],
                           "targets": [[-amplitude] * 24, [amplitude] * 24]})
            rows.append({"trial_id": tid, "original_trial_number": 10 * (index + 1),
                         "reach_target": direction})
        binding["training_trial_ids"] = training
        binding["evaluation_trial_ids"] = evaluation
        binding["all_trial_ids"] = training + evaluation
        binding["trial_census_sha256"] = independent_digest(training + evaluation)
        session["trials"] = trials
        context["sessions"].append({"session_id": sid,
                                     "source_asset_sha256": binding["source_asset_sha256"],
                                     "native_target_mapping_sha256": hashlib.sha256(b"invented-LR-context-not-native-proof").hexdigest(),
                                     "trials": rows})
    return dataset, protocol, context


class WholeCohortControls(unittest.TestCase):
    def score(self, dataset, protocol, predictions):
        return PIPELINE.score_predictions(dataset, protocol, predictions,
                                           expected_protocol_sha256=independent_digest(protocol))

    def fit_score(self, dataset, protocol):
        return PIPELINE.run_pipeline(dataset, protocol,
                                     expected_protocol_sha256=independent_digest(protocol))

    def admit(self, dataset, protocol):
        return PIPELINE.admit(dataset, protocol,
                              expected_protocol_sha256=independent_digest(protocol))

    def test_source_domain_matches_pinned_independent_inventory(self):
        self.assertEqual(list(PIPELINE.JOINT_NAMES), EXPECTED_JOINTS)
        self.assertEqual(PIPELINE.SESSIONS, EXPECTED_SESSIONS)
        self.assertEqual(list(PIPELINE.MICE), EXPECTED_MICE)

    def test_complete_five_mouse_ten_session_fit_is_exact_on_linear_control(self):
        d, p, _ = fixture()
        out = self.fit_score(d, p)
        self.assertEqual(set(out["models"]), set(EXPECTED_SESSIONS))
        self.assertEqual(out["metrics"]["support"], {
            "mice": 5, "sessions": 10, "evaluation_trials": 10,
            "complete_declared_normalized_census": True})
        self.assertAlmostEqual(out["metrics"]["mouse_macro_nrmse"], 0., places=12)
        np.testing.assert_allclose(out["metrics"]["mouse_macro_r_squared_per_joint"], np.ones(24), atol=1e-12)
        self.assertTrue(all(value is False for value in out["metrics"]["verification"].values()))

    def test_mouse_macro_preserves_small_mouse_weight(self):
        d, p, predictions = fixture(unequal_trials=True)
        for sid, (mouse, _) in EXPECTED_SESSIONS.items():
            if mouse == "cfa17":
                for tid in predictions[sid]:
                    predictions[sid][tid] = [[0.] * 24, [0.] * 24]
        out = self.score(d, p, predictions)
        # First mouse NRMSE1, others0; sample pooling would give1/sqrt41.
        self.assertAlmostEqual(out["mouse_macro_nrmse"], .2, places=14)
        self.assertNotAlmostEqual(out["mouse_macro_nrmse"], 1 / np.sqrt(41), places=6)
        np.testing.assert_allclose(out["mouse_macro_r_squared_per_joint"], [.8] * 24, atol=1e-14)
        self.assertEqual(out["support"]["evaluation_trials"], 82)

    def test_sessions_have_equal_weight_despite_unequal_trial_counts(self):
        d, p, predictions = fixture()
        for session, binding in zip(d["sessions"], p["sessions"]):
            scale, error, count = (1., 1., 1) if session["region"] == "M1" else (2., 4., 3)
            sid = session["session_id"]
            training = [t for t in session["trials"] if t["trial_id"] in binding["training_trial_ids"]]
            for trial in training:
                trial["targets"] = [[-scale] * 24, [scale] * 24]
            evaluation = []
            for number in range(count):
                tid = sid + ":weighted-eval" + str(number)
                evaluation.append({"trial_id": tid, "neural_trial_id": tid, "target_trial_id": tid,
                                   "neural_time_ms": [0, 10], "target_time_ms": [0, 10],
                                   "neural": [[-1., 0.], [1., 0.]],
                                   "targets": [[-scale] * 24, [scale] * 24]})
            binding["evaluation_trial_ids"] = [t["trial_id"] for t in evaluation]
            binding["all_trial_ids"] = binding["training_trial_ids"] + binding["evaluation_trial_ids"]
            binding["trial_census_sha256"] = independent_digest(binding["all_trial_ids"])
            session["trials"] = training + evaluation
            predictions[sid] = {t["trial_id"]: [[-scale + error] * 24, [scale + error] * 24]
                                for t in evaluation}
        result = self.score(d, p, predictions)
        # Equal session weighting: NRMSE=(1/1+4/2)/2=1.5;
        # Session-local R2=(1-1/1+1-16/4)/2=-1.5 for every joint and mouse.
        self.assertAlmostEqual(result["mouse_macro_nrmse"], 1.5, places=14)
        np.testing.assert_allclose(result["mouse_macro_r_squared_per_joint"], [-1.5] * 24,
                                   rtol=1e-14, atol=1e-14)
        self.assertEqual(result["support"]["evaluation_trials"], 20)

    def test_heldout_target_changes_do_not_change_any_fit_state(self):
        d, p, _ = fixture()
        baseline = self.fit_score(d, p)
        changed = copy.deepcopy(d)
        for session, binding in zip(changed["sessions"], p["sessions"]):
            for trial in session["trials"]:
                if trial["trial_id"] in binding["evaluation_trial_ids"]:
                    trial["targets"] = (3 * np.asarray(trial["targets"]) + 100.).tolist()
        altered = self.fit_score(changed, p)
        self.assertEqual(baseline["models"], altered["models"])
        self.assertEqual(baseline["predictions"], altered["predictions"])
        self.assertAlmostEqual(altered["metrics"]["mouse_macro_nrmse"], np.sqrt(10004), places=12)

    def test_heldout_feature_changes_do_not_change_selection_pca_or_fit(self):
        d, p, _ = fixture()
        baseline = self.fit_score(d, p)
        changed = copy.deepcopy(d)
        for session, binding in zip(changed["sessions"], p["sessions"]):
            for trial in session["trials"]:
                if trial["trial_id"] in binding["evaluation_trial_ids"]:
                    trial["neural"] = [[-2., -1e6], [2., 1e6]]
        altered = self.fit_score(changed, p)
        self.assertEqual(baseline["models"], altered["models"])
        for sid, rows in altered["predictions"].items():
            np.testing.assert_allclose(next(iter(rows.values())), [[-2.] * 24, [2.] * 24], atol=1e-12)
            self.assertEqual(altered["models"][sid]["selected_roi_ids"], [sid + ":cell_signal"])

    def test_calibrated_new_mouse_has_five_explicit_local_cases(self):
        d, p, _ = fixture(calibrated=True)
        out = self.fit_score(d, p)
        self.assertEqual(out["metrics"]["condition"], "calibrated_new_mouse_local_baseline")
        self.assertFalse(out["metrics"]["verification"]["cross_animal_transfer_demonstrated"])
        self.assertAlmostEqual(out["metrics"]["mouse_macro_nrmse"], 0., places=12)

    def test_refuses_missing_calibration_and_outer_mouse_leakage(self):
        for mutation in ["missing_case", "leaked_development_mouse", "wrong_calibration_trial"]:
            with self.subTest(mutation=mutation):
                d, p, _ = fixture(calibrated=True)
                if mutation == "missing_case":
                    p["new_mouse_cases"].pop()
                elif mutation == "leaked_development_mouse":
                    p["new_mouse_cases"][0]["development_mice"][0] = "cfa17"
                else:
                    sid = next(iter(p["new_mouse_cases"][0]["calibration_trials"]))
                    p["new_mouse_cases"][0]["calibration_trials"][sid] = p["sessions"][0]["evaluation_trial_ids"]
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_partial_or_opto_cohort(self):
        for mutation in ["missing", "opto", "wrong_region"]:
            with self.subTest(mutation=mutation):
                d, p, _ = fixture()
                if mutation == "missing":
                    d["sessions"].pop()
                    p["sessions"].pop()
                elif mutation == "opto":
                    d["sessions"][0]["mouse_id"] = "cfaVG1"
                    p["sessions"][0]["mouse_id"] = "cfaVG1"
                else:
                    d["sessions"][0]["region"] = "S1"
                    p["sessions"][0]["region"] = "S1"
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_trial_leakage_or_incomplete_partition(self):
        for overlap in [True, False]:
            with self.subTest(overlap=overlap):
                d, p, _ = fixture()
                if overlap:
                    p["sessions"][0]["training_trial_ids"].append(p["sessions"][0]["evaluation_trial_ids"][0])
                else:
                    p["sessions"][0]["all_trial_ids"].append("omitted-whole-trial")
                    p["sessions"][0]["trial_census_sha256"] = independent_digest(p["sessions"][0]["all_trial_ids"])
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_time_grid_or_trial_identity_mismatch(self):
        for field, value in [("target_time_ms", [0, 11]), ("neural_time_ms", [0., 10.]),
                             ("neural_trial_id", "another-trial")]:
            with self.subTest(field=field):
                d, p, _ = fixture()
                d["sessions"][0]["trials"][0][field] = value
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_roi_identity_or_target_domain_mismatch(self):
        for mutation in ["roi", "target_field", "joint_order", "width"]:
            with self.subTest(mutation=mutation):
                d, p, _ = fixture()
                if mutation == "roi":
                    d["sessions"][0]["roi_ids"][0] = "different-session-cell"
                elif mutation == "target_field":
                    d["target_field"] = "jointVelocities"
                elif mutation == "joint_order":
                    d["joint_names"] = d["joint_names"][::-1]
                else:
                    d["sessions"][0]["trials"][0]["targets"][0].pop()
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_incompatible_target_units_or_unsupported_input_representation(self):
        for mutation in ["units", "representation", "upstream_support"]:
            with self.subTest(mutation=mutation):
                d, p, _ = fixture()
                if mutation == "units":
                    d["target_units"] = p["target_units"] = "radians"
                elif mutation == "representation":
                    d["feature_variant"] = p["feature_variant"] = "raw_calcium"
                else:
                    d["sessions"][0]["upstream_temporal_support_ms"] = [1, 9]
                    p["sessions"][0]["upstream_temporal_support_ms"] = [1, 9]
                with self.assertRaises(PIPELINE.Refusal):
                    self.admit(d, p)

    def test_refuses_wrong_source_or_external_protocol_digest(self):
        d, p, _ = fixture()
        d["sessions"][0]["clock_evidence_sha256"] = "0" * 64
        with self.assertRaises(PIPELINE.Refusal):
            self.admit(d, p)
        d, p, _ = fixture()
        with self.assertRaises(PIPELINE.Refusal):
            PIPELINE.admit(d, p, expected_protocol_sha256="0" * 64)

    def test_refuses_missing_prediction_support_and_nonfinite_values(self):
        for mutation in ["session", "trial", "nan", "width"]:
            with self.subTest(mutation=mutation):
                d, p, predictions = fixture()
                sid = next(iter(predictions)); tid = next(iter(predictions[sid]))
                if mutation == "session":
                    del predictions[sid]
                elif mutation == "trial":
                    del predictions[sid][tid]
                elif mutation == "nan":
                    predictions[sid][tid][0][0] = float("nan")
                else:
                    predictions[sid][tid][0].pop()
                with self.assertRaises(PIPELINE.Refusal):
                    self.score(d, p, predictions)

    def test_zero_training_sd_is_undefined_without_dropping_joint_or_mouse(self):
        d, p, predictions = fixture()
        for trial in d["sessions"][0]["trials"]:
            if trial["trial_id"] in p["sessions"][0]["training_trial_ids"]:
                for row in trial["targets"]:
                    row[0] = 0.
        out = self.score(d, p, predictions)
        self.assertIsNone(out["mouse_macro_nrmse"])
        self.assertEqual(out["primary_status"], "undefined_training_target_scale")
        self.assertIsNone(out["mice"]["cfa17"]["nrmse_per_joint"][0])
        self.assertEqual(out["sessions"][p["sessions"][0]["session_id"]]["undefined_normalization_joints"], [EXPECTED_JOINTS[0]])
        self.assertEqual(out["support"]["mice"], 5)

    def test_zero_evaluation_variance_is_undefined_even_for_perfect_prediction(self):
        d, p, predictions = fixture()
        for session, binding in zip(d["sessions"], p["sessions"]):
            if session["mouse_id"] != "cfa17":
                continue
            for trial in session["trials"]:
                if trial["trial_id"] in binding["evaluation_trial_ids"]:
                    for row in trial["targets"]:
                        # Between-session offsets must not manufacture R2 support.
                        row[0] = 2. if session["region"] == "M1" else 12.
                    predictions[session["session_id"]][trial["trial_id"]] = copy.deepcopy(trial["targets"])
        out = self.score(d, p, predictions)
        self.assertAlmostEqual(out["mouse_macro_nrmse"], 0., places=14)
        self.assertIsNone(out["mouse_macro_r_squared_per_joint"][0])
        self.assertEqual(out["mice"]["cfa17"]["undefined_r_squared_joints"], [EXPECTED_JOINTS[0]])
        np.testing.assert_allclose(out["mouse_macro_r_squared_per_joint"][1:], np.ones(23))

    def test_refuses_declared_timepoint_resource_overrun(self):
        d, p, _ = fixture()
        p["limits"]["max_total_timepoints"] = 59  # Full fixture contains60.
        with self.assertRaises(PIPELINE.Refusal):
            self.admit(d, p)


class MatchedReferenceControls(unittest.TestCase):
    def compare(self, dataset, protocol, context):
        return PIPELINE.run_reference_controls(dataset, protocol, context,
                                               expected_protocol_sha256=independent_digest(protocol),
                                               expected_context_sha256=independent_digest(context))

    def test_phase_target_and_shift_controls_match_independent_answers(self):
        d, p, c = control_fixture()
        result = self.compare(d, p, c)
        self.assertAlmostEqual(result["baseline"]["metrics"]["mouse_macro_nrmse"], 0., places=12)
        for name in ["phase_only", "phase_by_target"]:
            self.assertAlmostEqual(result["controls"][name]["metrics"]["mouse_macro_nrmse"], 0., places=12)
        self.assertAlmostEqual(result["controls"]["target_only"]["metrics"]["mouse_macro_nrmse"], 2 / np.sqrt(5), places=12)
        shifted = result["controls"]["within_target_trial_shift"]["metrics"]
        self.assertAlmostEqual(shifted["mouse_macro_nrmse"], 4 / (5 * np.sqrt(5)), places=12)
        np.testing.assert_allclose(shifted["mouse_macro_r_squared_per_joint"], [21 / 25] * 24, atol=1e-12)
        for sid, item in result["within_target_trial_shift_models"].items():
            self.assertEqual(item["rotation"], {
                sid + ":z-left-one": sid + ":a-left-three",
                sid + ":a-left-three": sid + ":z-left-one",
                sid + ":q-right-one": sid + ":b-right-three",
                sid + ":b-right-three": sid + ":q-right-one",
            })
            self.assertTrue(all(":eval-" not in key and ":eval-" not in value
                                for key, value in item["rotation"].items()))
        self.assertFalse(result["native_context_verified"])
        self.assertFalse(result["scientific_qualification"])

    def test_heldout_targets_do_not_change_control_predictions_or_null_fit(self):
        d, p, c = control_fixture()
        baseline = self.compare(d, p, c)
        altered = copy.deepcopy(d)
        for session, binding in zip(altered["sessions"], p["sessions"]):
            for trial in session["trials"]:
                if trial["trial_id"] in binding["evaluation_trial_ids"]:
                    trial["targets"] = (3 * np.asarray(trial["targets"]) + 100).tolist()
        changed = self.compare(altered, p, c)
        self.assertEqual(baseline["baseline"]["models"], changed["baseline"]["models"])
        self.assertEqual(baseline["within_target_trial_shift_models"], changed["within_target_trial_shift_models"])
        # Phase prediction±2 versus altered truths94/106 gives errors96/104.
        self.assertAlmostEqual(changed["controls"]["phase_only"]["metrics"]["mouse_macro_nrmse"],
                               np.sqrt(10016 / 5), places=12)

    def test_missing_target_category_support_never_scores_partial_population(self):
        d, p, c = control_fixture()
        for session, binding in zip(c["sessions"], p["sessions"]):
            for row in session["trials"]:
                if row["trial_id"] in binding["training_trial_ids"]:
                    row["reach_target"] = "left"
        result = self.compare(d, p, c)
        self.assertEqual(result["controls"]["phase_only"]["status"], "scored_normalized_source_only")
        for name in ["target_only", "phase_by_target", "within_target_trial_shift"]:
            self.assertEqual(result["controls"][name]["status"], "unsupported_complete_population")
            self.assertIsNone(result["controls"][name]["metrics"])
            self.assertFalse(result["controls"][name]["partial_population_scoring"])
            self.assertIsNone(result["paired_comparisons"][name])

    def test_context_must_have_complete_identified_original_trials(self):
        for mutation in ["missing_trial", "duplicate_number", "bad_target", "wrong_source"]:
            with self.subTest(mutation=mutation):
                d, p, c = control_fixture()
                if mutation == "missing_trial":
                    c["sessions"][0]["trials"].pop()
                elif mutation == "duplicate_number":
                    c["sessions"][0]["trials"][0]["original_trial_number"] = c["sessions"][0]["trials"][1]["original_trial_number"]
                elif mutation == "bad_target":
                    c["sessions"][0]["trials"][0]["reach_target"] = "posthoc_unknown"
                else:
                    c["sessions"][0]["source_asset_sha256"] = "0" * 64
                with self.assertRaises(PIPELINE.Refusal):
                    self.compare(d, p, c)

    def test_exact_paired_five_mouse_bootstrap_matches_binomial_counts(self):
        d, p, predictions = fixture()
        candidate = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        for sid, (mouse, _) in EXPECTED_SESSIONS.items():
            if mouse == "cfa17":
                for tid in predictions[sid]:
                    predictions[sid][tid] = [[0.] * 24, [0.] * 24]
        reference = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        result = PIPELINE.paired_mouse_uncertainty(candidate, reference)
        # K/5 withK~Binomial(5,.2); counts[1024,1280,640,160,20,1] /3125.
        self.assertAlmostEqual(result["mean_difference"], .2, places=14)
        np.testing.assert_allclose(result["percentile_interval_95"], [0., .6], rtol=0, atol=1e-14)
        self.assertEqual(result["bootstrap_resamples"], 3125)
        self.assertEqual(result["independent_biological_units"], 5)
        self.assertTrue(result["descriptive_exploratory_only"])
        self.assertFalse(result["coverage_validated"])

    def test_paired_bootstrap_refuses_incompatible_protocol_or_mouse_population(self):
        d, p, predictions = fixture()
        candidate = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        for mutation in ["protocol", "condition", "mouse", "nonfinite"]:
            with self.subTest(mutation=mutation):
                reference = copy.deepcopy(candidate)
                if mutation == "protocol":
                    reference["protocol_sha256"] = "0" * 64
                elif mutation == "condition":
                    reference["condition"] = "calibrated_new_mouse_local_baseline"
                elif mutation == "mouse":
                    del reference["mice"]["cfa24"]
                else:
                    reference["mice"]["cfa24"]["nrmse"] = float("nan")
                with self.assertRaises(PIPELINE.Refusal):
                    PIPELINE.paired_mouse_uncertainty(candidate, reference)

    def test_pairing_refuses_changed_numeric_payload_under_same_protocol(self):
        d, p, predictions = fixture()
        candidate = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        for field in ["neural", "targets"]:
            with self.subTest(field=field):
                altered = copy.deepcopy(d)
                evaluation_id = p["sessions"][0]["evaluation_trial_ids"][0]
                trial = next(t for t in altered["sessions"][0]["trials"] if t["trial_id"] == evaluation_id)
                trial[field][0][0] += 1.
                reference = PIPELINE.score_predictions(altered, p, predictions,
                                                       expected_protocol_sha256=independent_digest(p))
                self.assertEqual(candidate["protocol_sha256"], reference["protocol_sha256"])
                self.assertNotEqual(candidate["normalized_input_sha256"], reference["normalized_input_sha256"])
                with self.assertRaises(PIPELINE.Refusal):
                    PIPELINE.paired_mouse_uncertainty(candidate, reference)

    def test_equal_smallest_subnormal_mouse_differences_keep_nonzero_mean(self):
        d, p, predictions = fixture()
        for session, binding in zip(d["sessions"], p["sessions"]):
            for trial in session["trials"]:
                if trial["trial_id"] in binding["evaluation_trial_ids"]:
                    trial["targets"] = [[0.] * 24, [0.] * 24]
                    predictions[session["session_id"]][trial["trial_id"]] = [[0.] * 24, [0.] * 24]
        candidate = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        smallest = float.fromhex("0x0.0000000000001p-1022")
        for session in predictions.values():
            for tid in session:
                session[tid] = [[smallest] * 24, [smallest] * 24]
        reference = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        self.assertEqual(reference["mouse_macro_nrmse"], smallest)
        result = PIPELINE.paired_mouse_uncertainty(candidate, reference)
        self.assertEqual(list(result["mouse_differences"].values()), [smallest] * 5)
        self.assertEqual(result["mean_difference"], smallest)
        self.assertEqual(result["percentile_interval_95"], [smallest, smallest])
        self.assertEqual(result["bootstrap_resamples"], 3125)

    def test_paired_bootstrap_preserves_undefined_mouse(self):
        d, p, predictions = fixture()
        for session, binding in zip(d["sessions"], p["sessions"]):
            if session["mouse_id"] == "cfa17":
                for trial in session["trials"]:
                    if trial["trial_id"] in binding["training_trial_ids"]:
                        trial["targets"] = [[0.] * 24, [0.] * 24]
        metrics = PIPELINE.score_predictions(d, p, predictions, expected_protocol_sha256=independent_digest(p))
        result = PIPELINE.paired_mouse_uncertainty(metrics, metrics)
        self.assertEqual(result["status"], "undefined_full_mouse_support")
        self.assertIsNone(result["mean_difference"])
        self.assertIsNone(result["percentile_interval_95"])
        self.assertEqual(result["bootstrap_resamples"], 0)
        self.assertEqual(result["independent_biological_units"], 5)


class MetadataSplitControls(unittest.TestCase):
    def freeze(self, context, seed=17):
        return PIPELINE.freeze_within_mouse_splits(context,
                                                   expected_context_sha256=independent_digest(context), seed=seed)

    def test_metadata_only_split_is_complete_whole_trial_and_stratified(self):
        _, _, context = control_fixture()
        result = self.freeze(context)
        self.assertEqual(set(result["sessions"]), set(EXPECTED_SESSIONS))
        for session in context["sessions"]:
            split = result["sessions"][session["session_id"]]
            self.assertEqual(set(split["all_trial_ids"]), {r["trial_id"] for r in session["trials"]})
            self.assertEqual(set(split["training_trial_ids"]) | set(split["evaluation_trial_ids"]), set(split["all_trial_ids"]))
            self.assertFalse(set(split["training_trial_ids"]) & set(split["evaluation_trial_ids"]))
            labels = {r["trial_id"]: r["reach_target"] for r in session["trials"]}
            for label in ["left", "right"]:
                self.assertEqual(sum(labels[t] == label for t in split["evaluation_trial_ids"]), 1)
                self.assertEqual(sum(labels[t] == label for t in split["training_trial_ids"]), 2)
            self.assertEqual(split["trial_census_sha256"], independent_digest(split["all_trial_ids"]))
        self.assertFalse(result["frozen_before_outcomes_verified"])
        self.assertFalse(result["authentic_eligibility_verified"])
        self.assertFalse(result["scientific_qualification"])

    def test_input_record_order_does_not_choose_the_split(self):
        _, _, context = control_fixture()
        before = self.freeze(context)
        permuted = copy.deepcopy(context)
        permuted["sessions"].reverse()
        for session in permuted["sessions"]:
            session["trials"].reverse()
        after = self.freeze(permuted)
        self.assertEqual(before["sessions"], after["sessions"])
        self.assertNotEqual(before["context_sha256"], after["context_sha256"])
        self.assertNotEqual(before["sessions"], self.freeze(context, seed=18)["sessions"])

    def test_split_freezer_refuses_incomplete_context_or_insufficient_strata(self):
        for mutation in ["cohort", "stratum", "digest"]:
            with self.subTest(mutation=mutation):
                _, _, context = control_fixture()
                if mutation == "cohort":
                    context["sessions"].pop()
                elif mutation == "stratum":
                    context["sessions"][0]["trials"].pop(0)  # Threelefttrials become2.
                with self.assertRaises(PIPELINE.Refusal):
                    if mutation == "digest":
                        PIPELINE.freeze_within_mouse_splits(context, expected_context_sha256="0" * 64, seed=17)
                    else:
                        self.freeze(context)


class CommandLineControls(unittest.TestCase):
    def invoke(self, body, protocol, *, mode="fit-score", digest_override=None,
               max_input=None, max_output=1_000_000, context=None):
        with tempfile.TemporaryDirectory(prefix="calcium-generated-control-") as td:
            source = Path(td) / "request.json"
            source.write_bytes(body)
            context_args = [] if context is None else ["--expected-context-sha256", independent_digest(context)]
            return subprocess.run([
                sys.executable, "-B", str(SOURCE), mode, "--input", str(source),
                "--expected-input-sha256", digest_override or hashlib.sha256(body).hexdigest(),
                "--expected-protocol-sha256", independent_digest(protocol),
                "--max-input-bytes", str(len(body) if max_input is None else max_input),
                "--max-output-bytes", str(max_output), *context_args], capture_output=True, timeout=30)

    def test_fit_score_command_exercises_complete_generated_path(self):
        d, p, _ = fixture()
        body = json.dumps({"dataset": d, "protocol": p}).encode()
        completed = self.invoke(body, p)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertEqual(result["metrics"]["support"]["mice"], 5)
        self.assertAlmostEqual(result["metrics"]["mouse_macro_nrmse"], 0., places=12)
        self.assertFalse(result["metrics"]["verification"]["scientific_qualification"])

    def test_compare_controls_command_runs_complete_generated_controls(self):
        d, p, c = control_fixture()
        body = json.dumps({"dataset": d, "protocol": p, "context": c}).encode()
        completed = self.invoke(body, p, mode="compare-controls", context=c)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertAlmostEqual(result["controls"]["within_target_trial_shift"]["metrics"]["mouse_macro_nrmse"],
                               4 / (5 * np.sqrt(5)), places=12)
        self.assertFalse(result["scientific_qualification"])

    def test_large_admitted_input_cap_does_not_allocate_from_the_cap(self):
        d, p, _ = fixture()
        body = json.dumps({"dataset": d, "protocol": p}).encode()
        completed = self.invoke(body, p, max_input=sys.maxsize - 1)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertAlmostEqual(result["metrics"]["mouse_macro_nrmse"], 0., places=12)
        self.assertFalse(result["metrics"]["verification"]["scientific_qualification"])

    def test_command_refuses_identity_and_input_output_budget_failures(self):
        d, p, _ = fixture()
        body = json.dumps({"dataset": d, "protocol": p}).encode()
        for options in [{"digest_override": "0" * 64}, {"max_input": 16}, {"max_output": 16}, {"max_input": 2**100}]:
            with self.subTest(options=options):
                completed = self.invoke(body, p, **options)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, b"")
                diagnostic = json.loads(completed.stderr)
                self.assertEqual(diagnostic["status"], "refused")
                self.assertFalse(diagnostic["scientific_qualification"])

    def test_command_rejects_duplicate_keys_and_nonfinite_json(self):
        _, p, _ = fixture()
        for body in [b'{"dataset":{},"dataset":{}}', b'{"dataset":NaN}']:
            with self.subTest(body=body):
                completed = self.invoke(body, p)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, b"")
                self.assertEqual(json.loads(completed.stderr)["status"], "refused")



class CurrentSourceBindingControls(unittest.TestCase):
    descriptor_relative = "benchmarks/integrity/current-closures/construction-calcium-pipeline/SOURCE.json"
    verifier = SOURCE.with_name("verify_source.py")

    def descriptor(self):
        body = (ROOT / self.descriptor_relative).read_bytes()
        return body, json.loads(body), hashlib.sha256(body).hexdigest()

    def mirror(self, destination):
        body, descriptor, expected = self.descriptor()
        path = destination / self.descriptor_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        for row in descriptor["members"]:
            relative = row["path"]
            self.assertTrue(relative.startswith(("benchmarks/", "tests/")))
            source = (ROOT / relative).resolve()
            self.assertTrue(source.is_relative_to(ROOT))
            data = source.read_bytes()
            self.assertEqual(len(data), row["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
            target = destination / relative
            self.assertTrue(target.resolve().is_relative_to(destination.resolve()))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return expected

    def inspect(self, root, expected):
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(self.verifier),
                               "--repo-root", str(root), "--expected-sha256", expected],
                              capture_output=True, timeout=30)

    def test_reviewed_current_descriptor_verifies_without_importing_pipeline(self):
        _, descriptor, expected = self.descriptor()
        completed = self.inspect(ROOT, expected)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "current_source_inspection_passed")
        self.assertEqual(result["members"], len(descriptor["members"]))
        self.assertFalse(result["source_execution"])
        self.assertFalse(result["scientific_qualification"])

    def test_changed_pinned_pipeline_body_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="calcium-source-control-") as td:
            root = Path(td)
            expected = self.mirror(root)
            candidate = root / SOURCE.relative_to(ROOT)
            candidate.write_bytes(candidate.read_bytes() + b"\n# generated mutation control\n")
            completed = self.inspect(root, expected)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            self.assertIn("Current source member differs", json.loads(completed.stderr)["reason"])

    def test_unlisted_executable_in_package_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="calcium-source-control-") as td:
            root = Path(td)
            expected = self.mirror(root)
            added = root / SOURCE.parent.relative_to(ROOT) / "unlisted.py"
            added.write_text("raise RuntimeError('must never execute this source control')\n")
            completed = self.inspect(root, expected)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            self.assertIn("missing or extra members", json.loads(completed.stderr)["reason"])


if __name__ == "__main__":
    unittest.main()
