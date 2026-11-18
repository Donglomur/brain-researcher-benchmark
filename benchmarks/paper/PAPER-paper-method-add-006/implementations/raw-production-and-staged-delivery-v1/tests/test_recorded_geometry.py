"""Generated source-fidelity controls; estimator doubles never learn parameters."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recorded_geometry as M
from dependency_loader import R


class NonLearningSVC:
    """Record source calls and emit a fixed rule; fit performs no estimation."""

    instances = []
    emit_warnings = False
    prediction_mode = "binary"

    def __init__(self, *, dual, max_iter, random_state):
        self.parameters = {"dual": dual, "max_iter": max_iter,
                           "random_state": random_state}
        self.events = []
        self.__class__.instances.append(self)

    def fit(self, x, y):
        self.events.append(("fit", np.asarray(x).copy(), np.asarray(y).copy()))
        if self.emit_warnings:
            warnings.warn("fixture fit warning; output is retained", UserWarning)
        return self

    def predict(self, x):
        self.events.append(("predict", np.asarray(x).copy()))
        if self.emit_warnings:
            warnings.warn("fixture prediction warning", RuntimeWarning)
        if self.prediction_mode == "fractional":
            return np.full(len(x), 0.5)
        if self.prediction_mode == "bad_shape":
            return np.ones((len(x), 1))
        if self.prediction_mode == "nonfinite":
            return np.full(len(x), np.nan)
        if self.prediction_mode == "integer_precision_loss":
            return np.full(len(x), 2 ** 53 + 1, dtype=np.int64)
        if self.prediction_mode == "float32":
            return np.full(len(x), 0.5, dtype=np.float32)
        if self.prediction_mode == "complex":
            return np.full(len(x), 0.5 + 0.25j, dtype=np.complex128)
        if self.prediction_mode == "extended":
            return np.full(len(x), np.longdouble(1) + np.finfo(np.longdouble).eps,
                           dtype=np.longdouble)
        # Does not depend on fit labels or estimate any parameter.
        seed = self.parameters["random_state"]
        shift = 0 if seed is None else (seed % 5) - 2
        return ((np.asarray(x)[:, 0] + shift / 10) >= 0).astype(float)


class RecordedGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = np.random.RandomState(90210)
        cls.z = data.normal(size=(610, 4))
        cls.x = cls.z @ data.normal(size=(4, 25)) + data.normal(size=(610, 25))
        cls.rows = np.arange(5000, 5610, dtype=np.int64)
        cls.units = np.asarray(["unit-" + str(i) for i in range(25)])

    def setUp(self):
        NonLearningSVC.instances = []
        NonLearningSVC.emit_warnings = False
        NonLearningSVC.prediction_mode = "binary"

    def equal_tree(self, actual, expected):
        if isinstance(expected, np.ndarray):
            self.assertIsInstance(actual, np.ndarray)
            self.assertEqual(actual.dtype, expected.dtype)
            np.testing.assert_array_equal(actual, expected, strict=True)
        elif isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected))
            for key in expected:
                self.equal_tree(actual[key], expected[key])
        elif isinstance(expected, (tuple, list)):
            self.assertEqual(type(actual), type(expected))
            self.assertEqual(len(actual), len(expected))
            for a, b in zip(actual, expected):
                self.equal_tree(a, b)
        elif isinstance(expected, float) and np.isnan(expected):
            self.assertTrue(np.isnan(actual))
        else:
            self.assertEqual(actual, expected)

    def readout_pair(self, policy, *, warning=False, fractional=False):
        NonLearningSVC.emit_warnings = warning
        NonLearningSVC.prediction_mode = "fractional" if fractional else "binary"
        rng_a, rng_b = np.random.RandomState(771), np.random.RandomState(771)
        x, z = self.x[:500, :19], self.z[:500]
        with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
            original = R.readout(x, z, rng=rng_a, svc_policy=policy)
            original_instances = list(NonLearningSVC.instances)
            NonLearningSVC.instances = []
            recorded = M.readout_recorded(x, z, rng=rng_b, svc_policy=policy,
                                         max_prediction_bytes=800000)
            recorded_instances = list(NonLearningSVC.instances)
        self.equal_tree({k: v for k, v in recorded.items() if k != "svc_test_predictions"},
                        original)
        self.equal_tree(R.state(rng_a), R.state(rng_b))
        self.assertEqual(len(original_instances), len(recorded_instances))
        self.assertEqual(len(recorded_instances), len(recorded["valid_teacher_indices"]))
        for a, b in zip(original_instances, recorded_instances):
            self.equal_tree(a.parameters, b.parameters)
            self.equal_tree(a.events, b.events)
            self.assertEqual([e[0] for e in b.events], ["fit", "predict"])
            self.assertEqual(b.events[0][1].shape, (300, 19))
            self.assertEqual(b.events[0][2].shape, (300,))
            self.assertEqual(b.events[1][1].shape, (200, 19))
        return recorded, recorded_instances

    def test_seeded_readout_preserves_every_source_output_and_call(self):
        result, instances = self.readout_pair(R.SVC_POLICY)
        self.assertGreater(len(instances), 100)
        self.assertTrue(all(i.parameters["random_state"] is not None for i in instances))
        self.assertTrue(result["full500_row_task_balance_exposure"])

    def test_literal_readout_preserves_every_source_output_and_call(self):
        _, instances = self.readout_pair(R.SVC_LITERAL_POLICY)
        self.assertTrue(all(i.parameters["random_state"] is None for i in instances))

    def test_warning_outputs_are_retained_without_extra_calls(self):
        result, instances = self.readout_pair(R.SVC_POLICY, warning=True)
        self.assertEqual(len(result["warnings"]), 2 * len(instances))
        self.assertEqual(result["warnings"][0]["category"], "UserWarning")
        self.assertEqual(result["warnings"][1]["category"], "RuntimeWarning")

    def test_fractional_predictions_preserved_without_coercion(self):
        result, _ = self.readout_pair(R.SVC_LITERAL_POLICY, fractional=True)
        self.assertTrue(np.all(result["svc_test_predictions"] == 0.5))

    def test_raw_axes_and_original_errors_recomputed_independently(self):
        result, instances = self.readout_pair(R.SVC_POLICY)
        rng = np.random.RandomState(771)
        teachers = rng.randn(4, 500)
        labels = np.sign(self.z[:500] @ teachers)
        valid = np.flatnonzero(np.abs(labels.mean(axis=0)) < 0.25)
        train = rng.choice(500, 300, replace=False)
        test = np.setdiff1d(np.arange(500), train)
        np.testing.assert_array_equal(result["valid_teacher_indices"], valid)
        np.testing.assert_array_equal(result["training_positions"], train)
        np.testing.assert_array_equal(result["test_positions"], test)
        raw = result["svc_test_predictions"]
        self.assertEqual(raw.shape, (200, len(valid)))
        self.assertEqual(raw.dtype, np.float64)
        errors = np.mean(raw != (1 + labels[test][:, valid]) / 2, axis=0)
        np.testing.assert_array_equal(errors, result["svc_task_errors"])
        self.assertEqual(float(errors.mean()), result["svc_error"])
        for column, instance in enumerate(instances):
            seed = instance.parameters["random_state"]
            expected = (self.x[test, 0] + ((seed % 5) - 2) / 10 >= 0).astype(float)
            np.testing.assert_array_equal(raw[:, column], expected)
        self.assertNotEqual(raw.shape, raw.T.shape)

    def test_geometry_repetition_preserves_source_values_native_ids_and_rng(self):
        for policy in (R.SVC_POLICY, R.SVC_LITERAL_POLICY):
            with self.subTest(policy=policy):
                rng_a, rng_b = np.random.RandomState(943), np.random.RandomState(943)
                with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
                    original = R.geometry_repetition(
                        self.x, self.z, self.rows, self.units, rng=rng_a,
                        repetition=499, svc_policy=policy)
                    recorded = M.geometry_repetition_recorded(
                        self.x, self.z, self.rows, self.units, rng=rng_b,
                        repetition=499, svc_policy=policy, max_prediction_bytes=800000)
                without_raw = copy.deepcopy(recorded)
                del without_raw["readout"]["svc_test_predictions"]
                self.equal_tree(without_raw, original)
                self.equal_tree(R.state(rng_a), R.state(rng_b))
                self.assertEqual(recorded["row_ids"].shape, (500,))
                self.assertEqual(recorded["unit_ids"].shape, (19,))
                np.testing.assert_array_equal(recorded["training_row_ids"],
                    recorded["row_ids"][recorded["readout"]["training_positions"]])
                np.testing.assert_array_equal(recorded["test_row_ids"],
                    recorded["row_ids"][recorded["readout"]["test_positions"]])

    def test_prediction_budget_rejects_before_recording_allocation_or_estimator(self):
        rng = np.random.RandomState(771)
        expected = np.random.RandomState(771)
        expected.randn(4, 500)
        original_empty = np.empty
        def guarded_empty(shape, *args, **kwargs):
            if isinstance(shape, tuple) and len(shape) == 2 and shape[0] == 200:
                raise AssertionError("recording allocation attempted")
            return original_empty(shape, *args, **kwargs)
        with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC), \
                mock.patch.object(M.np, "empty", side_effect=guarded_empty):
            with self.assertRaisesRegex(R.ContractError, "exceeds max_prediction_bytes"):
                M.readout_recorded(self.x[:500, :19], self.z[:500], rng=rng,
                                   svc_policy=R.SVC_POLICY, max_prediction_bytes=1)
        self.assertEqual(NonLearningSVC.instances, [])
        # Budget depends on the retained teacher count. Failure advances only
        # teacher draws here; a caller must restore/discard this failed stream.
        self.assertEqual(R.state(rng), R.state(expected))

    def test_exact_prediction_budget_is_accepted(self):
        probe = np.random.RandomState(771)
        labels = np.sign(self.z[:500] @ probe.randn(4, 500))
        valid_count = int(np.sum(np.abs(labels.mean(axis=0)) < 0.25))
        exact = 200 * valid_count * 8
        with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
            result = M.readout_recorded(self.x[:500, :19], self.z[:500],
                rng=np.random.RandomState(771), svc_policy=R.SVC_POLICY,
                max_prediction_bytes=exact)
        self.assertEqual(result["svc_test_predictions"].nbytes, exact)

    def test_invalid_budget_rejected_without_rng_consumption(self):
        for budget in (0, -1, 1.0, True, None, np.int64(800000)):
            with self.subTest(budget=budget):
                rng = np.random.RandomState(771)
                before = R.state(rng)
                with self.assertRaisesRegex(R.ContractError, "positive integer"):
                    M.readout_recorded(self.x[:500, :19], self.z[:500], rng=rng,
                        svc_policy=R.SVC_POLICY, max_prediction_bytes=budget)
                self.assertEqual(before, R.state(rng))
        self.assertEqual(NonLearningSVC.instances, [])

    def test_invalid_raw_prediction_shape_rejected(self):
        modes = ["bad_shape", "integer_precision_loss", "float32", "complex"]
        if np.dtype(np.longdouble) != np.dtype(np.float64):
            modes.append("extended")
        for mode in modes:
            with self.subTest(mode=mode):
                NonLearningSVC.prediction_mode = mode
                with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
                    with self.assertRaisesRegex(R.ContractError, "one finite numeric value"):
                        M.readout_recorded(self.x[:500, :19], self.z[:500],
                            rng=np.random.RandomState(771), svc_policy=R.SVC_POLICY,
                            max_prediction_bytes=800000)

    def test_nonfinite_raw_predictions_rejected(self):
        NonLearningSVC.prediction_mode = "nonfinite"
        with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
            with self.assertRaisesRegex(R.ContractError, "one finite numeric value"):
                M.readout_recorded(self.x[:500, :19], self.z[:500],
                    rng=np.random.RandomState(771), svc_policy=R.SVC_POLICY,
                    max_prediction_bytes=800000)

    def test_original_shape_policy_and_repetition_guards_retained(self):
        for points, latents, policy in ((self.x[:499, :19], self.z[:499], R.SVC_POLICY),
                (self.x[:500, :18], self.z[:500], R.SVC_POLICY),
                (self.x[:500, :19], self.z[:500], "unknown")):
            with self.subTest(shape=points.shape, policy=policy):
                with self.assertRaises(R.ContractError):
                    M.readout_recorded(points, latents, rng=np.random.RandomState(771),
                                      svc_policy=policy, max_prediction_bytes=800000)
        with self.assertRaisesRegex(R.ContractError, "source repetition"):
            M.geometry_repetition_recorded(self.x, self.z, self.rows, self.units,
                rng=np.random.RandomState(943), repetition=500, svc_policy=R.SVC_POLICY,
                max_prediction_bytes=800000)
        self.assertEqual(NonLearningSVC.instances, [])


class RawProducerGeometryTests(unittest.TestCase):
    """Tiny explicit in-memory storage doubles, not a full-grid execution."""

    setUpClass = classmethod(RecordedGeometryTests.setUpClass.__func__)
    setUp = RecordedGeometryTests.setUp
    equal_tree = RecordedGeometryTests.equal_tree

    def prepared(self):
        return {"x": self.x, "z": self.z, "row_ids": self.rows, "unit_ids": self.units,
                "behavior": {"accuracy": None,
                             "status": "unavailable_complete_epoch_trial_table"},
                "t": np.arange(len(self.x), dtype=float),
                "trial": np.arange(len(self.x), dtype=np.int64)}

    def first_record(self):
        import raw_producer as RP
        job = next(R.geometry_plan())
        with mock.patch("sklearn.svm.LinearSVC", NonLearningSVC):
            result = M.geometry_repetition_recorded(self.x, self.z, self.rows, self.units,
                rng=np.random.RandomState(job["region_seed"]), repetition=job["repetition"],
                svc_policy=R.SVC_POLICY, max_prediction_bytes=800000)
        result.update(job=job, case_id=job["case_id"], packet_pin={"fixture": "tiny-generated"},
                      behavior=self.prepared()["behavior"])
        return RP, result

    def test_raw_reference_projection_matches_original_draw(self):
        RP, recorded = self.first_record()
        reference = RP.geometry_reference(self.prepared(), recorded,
            checkpoint_sha256="a" * 64, reference_chain=RP.GB.ReferenceChain())
        np.testing.assert_array_equal(reference["source_svc_predictions"],
                                      recorded["readout"]["svc_test_predictions"])
        np.testing.assert_array_equal(reference["row_ids"], recorded["row_ids"])
        np.testing.assert_array_equal(reference["unit_ids"], recorded["unit_ids"])
        np.testing.assert_array_equal(reference["training_positions"],
                                      recorded["readout"]["training_positions"])
        self.assertFalse(reference["qualification"])

    def test_summary_only_checkpoint_cannot_resume(self):
        RP, recorded = self.first_record()
        del recorded["readout"]["svc_test_predictions"]
        with self.assertRaisesRegex(ValueError, "summary-only checkpoints"):
            RP.validate_geometry_recorded(recorded)

    def test_malformed_raw_operands_refused_before_resume(self):
        RP, recorded = self.first_record()
        malformed = []
        nonfinite = copy.deepcopy(recorded)
        nonfinite["readout"]["svc_test_predictions"][0, 0] = np.nan
        malformed.append(nonfinite)
        wrong_native_training = copy.deepcopy(recorded)
        wrong_native_training["training_row_ids"][0] = recorded["test_row_ids"][0]
        malformed.append(wrong_native_training)
        duplicate_units = copy.deepcopy(recorded)
        duplicate_units["unit_ids"][1] = duplicate_units["unit_ids"][0]
        malformed.append(duplicate_units)
        for change in ("duplicate", "unsorted", "out_of_range", "floating"):
            item = copy.deepcopy(recorded)
            teachers = item["readout"]["valid_teacher_indices"].copy()
            if change == "duplicate":
                teachers[1] = teachers[0]
            elif change == "unsorted":
                teachers = teachers[::-1]
            elif change == "out_of_range":
                teachers[-1] = 500
            else:
                teachers = teachers.astype(float)
            item["readout"]["valid_teacher_indices"] = teachers
            malformed.append(item)
        for index, item in enumerate(malformed):
            with self.subTest(index=index), self.assertRaises(ValueError):
                RP.validate_geometry_recorded(item)

    def test_fractional_recording_is_not_silently_admitted_to_binary_bridge(self):
        RP, recorded = self.first_record()
        recorded["readout"]["svc_test_predictions"][:] = 0.5
        RP.validate_geometry_recorded(recorded)
        with self.assertRaisesRegex(ValueError, "encoded labels"):
            RP.geometry_reference(self.prepared(), recorded, checkpoint_sha256="a" * 64,
                                  reference_chain=RP.GB.ReferenceChain())

    def storage_context(self, directory, storage, *, size=100):
        """Mock persistence explicitly; source geometry execution remains real/doubled SVC."""
        from contextlib import ExitStack
        import raw_producer as RP
        stack = ExitStack()
        original_exists = Path.exists
        def save(path, result, binding, *, max_bytes):
            storage[str(path)] = copy.deepcopy(result)
            return {"bytes": size, "fixture_only": True}
        stack.enter_context(mock.patch.object(RP.P, "require_runtime"))
        stack.enter_context(mock.patch.object(RP, "execution_binding", return_value={"fixture": True}))
        stack.enter_context(mock.patch.object(RP.R, "prepare_geometry", return_value=self.prepared()))
        stack.enter_context(mock.patch.object(RP.P, "save_result", side_effect=save))
        stack.enter_context(mock.patch.object(RP.P, "load_result",
            side_effect=lambda path, binding, max_bytes: copy.deepcopy(storage[str(path)])))
        stack.enter_context(mock.patch.object(Path, "exists",
            lambda path: str(path) in storage or original_exists(path)))
        stack.enter_context(mock.patch("sklearn.svm.LinearSVC", NonLearningSVC))
        panel = mock.Mock()
        panel.load_session.return_value = {"packet_pin": {"fixture": "tiny-generated"}}
        return stack, RP, panel

    def test_prefix_storage_resume_preserves_rng_chain_and_refuses_tamper(self):
        # Directory only: P.save_result/load_result are explicit in-memory doubles.
        with tempfile.TemporaryDirectory() as directory:
            storage = {}
            stack, RP, panel = self.storage_context(directory, storage)
            with stack:
                first = RP.run_geometry(panel, directory, max_result_bytes=1048576,
                    max_total_bytes=2097152, max_prediction_bytes=800000, stop=2)
                self.assertEqual(first["written"], 2)
                self.assertFalse(first["qualification"])
                values = list(storage.values())
                self.assertEqual(values[1]["rng_before"], values[0]["rng_after"])
                NonLearningSVC.instances = []
                second = RP.run_geometry(panel, directory, max_result_bytes=1048576,
                    max_total_bytes=2097152, max_prediction_bytes=800000, stop=2)
                self.assertEqual(second["resumed"], 2)
                self.assertEqual(second["written"], 0)
                self.assertEqual(NonLearningSVC.instances, [])
                values[1]["rng_before"]["position"] = (values[1]["rng_before"]["position"] + 1) % 624
                with self.assertRaisesRegex(ValueError, "identical source stream"):
                    RP.run_geometry(panel, directory, max_result_bytes=1048576,
                        max_total_bytes=2097152, max_prediction_bytes=800000, stop=2)
                self.assertEqual(NonLearningSVC.instances, [])

    def test_write_allowance_stops_before_next_classifier(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = {}
            stack, RP, panel = self.storage_context(directory, storage)
            with stack:
                with self.assertRaisesRegex(ValueError, "before any new classifier"):
                    RP.run_geometry(panel, directory, max_result_bytes=1048576,
                        max_total_bytes=1048576, max_prediction_bytes=800000, stop=2)
                self.assertEqual(len(storage), 1)
                first = next(iter(storage.values()))
                self.assertEqual(len(NonLearningSVC.instances),
                                 len(first["readout"]["valid_teacher_indices"]))
                self.assertEqual(panel.load_session.call_count, 1)

    def test_original_metadata_geometry_census(self):
        jobs = list(R.geometry_plan())
        self.assertEqual(len(jobs), 64000)
        self.assertEqual(len({(j["case_id"], j["repetition"]) for j in jobs}), 64000)
        self.assertEqual(len({j["case_id"] for j in jobs}), 128)
        self.assertEqual(len({j["animal"] for j in jobs}), 8)
        self.assertEqual({j["repetition"] for j in jobs}, set(range(500)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
