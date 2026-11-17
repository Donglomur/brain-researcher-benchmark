#!/usr/bin/env python3
"""Independent generated controls for the adopted processed-input condition.

No original arrays, scientific fitting, model execution, or v1 test runs. The
v1 serializer is reused by exact source pin; generated raw identities are
deliberately one-based and are not repairs to any authentic trial identities.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
HELPER = BASE / "locked-mat-admission-v1" / "test_admission.py"
HELPER_SHA256 = "a07fb69edf60aada458f474894a45428620ff5da00476020d55c91773ea9c41b"
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError("Independent v1 fixture writer source changed")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


F = load("calcium_v2_pinned_fixture_writer", HELPER)
A = load("calcium_v2_independent_admission", HERE / "admission.py")
P = A.pipeline()
D = load("calcium_v2_independent_delivery", BASE / "participant-delivery-v2" / "delivery.py")
C = P.source_condition
F.BUDGET = 4 * 1024 * 1024
SOURCE_PATHS = [HERE / "admission.py", BASE / "train-only-decoding-v2" / "pipeline.py",
                BASE / "train-only-decoding-v2" / "source_condition.py",
                BASE / "participant-delivery-v2" / "delivery.py", HELPER]


def source_pins():
    return {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE_PATHS}


START_PINS = source_pins()
TRIALS = [1, 2, 4, 5, 7, 8, 9]


def write_json(path, value):
    content = A.canonical(value)
    if F.WRITTEN + len(content) > F.BUDGET:
        raise RuntimeError("Independent fixture-write budget would be exceeded")
    path.write_bytes(content)
    F.charge(path)
    return F.pin(path)


def radical_document(sid):
    mouse, date = P.SESSIONS[sid][0], sid.split("_", 1)[1]
    # These fixtures originate with raw trialNumber == physical row position.
    # Ineligible rows 3, 6, 10 are retained in raw R; locked IDs remain sparse.
    raw = [{"trialNumber": n, "animalID": mouse, "date": date, "success": n in TRIALS,
            "grabTimeC": 5., "liftRT": 100., "goodDLC": True, "wrongZoneFirst": False,
            "movementTime": 200., "timeToContact": 300., "has_radical": True} for n in range(1, 11)]
    neural, kinematics = [], []
    sample = np.arange(101, dtype=float)
    for i, n in enumerate(TRIALS):
        valid = i < 6
        # A non-linear sequence distinguishes exact copies from unintended
        # events substitution or additional Gaussian smoothing.
        neural.append({"trialNumber": n, "locked": valid,
                       "data": np.column_stack((sample + n, -sample - n)) if valid else np.empty((0, 0)),
                       "radical_rates": np.column_stack((n + sample ** 2, -n - sample)) if valid else np.empty((0, 0))})
        kinematics.append({"trialNumber": n, "locked": valid, "animalID": mouse, "date": date,
                           "eventName": "liftTimeDLC", "tPts": F.GRID, "LR": 1 + i % 2,
                           "jointAngles": n + F.GRID.T / 8 + np.arange(24)[None, :] if valid else np.empty((0, 0))})
    return {"R": raw, "neurons": neural, "kinematics": kinematics, "M": F.fixture_document(sid)["M"]}


class SourceConditionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="calcium-v2-controls-", dir=os.environ.get("CALCIUM_CONTROL_TMP"))
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.sid = next(iter(P.SESSIONS))
        recipe = {"target_field": "jointAngles", "feature_variant": "radical", "window_ms": [-100, 400],
                  "grid_step_ms": 10, "cell_budget": 2, "pca_components": 1, "ridge_alpha": 1.,
                  "split_seed": 240926,
                  "limits": {"max_total_timepoints": 4000, "max_rois_per_session": 2, "max_trials_per_session": 7}}
        entries = []
        for sid in P.SESSIONS:
            path = cls.root / (sid + ".mat")
            F.write_mat(path, radical_document(sid))
            condition = C.build_source_condition("radical")
            provenance = {key: hashlib.sha256((sid + key).encode()).hexdigest() for key in A.PROVENANCE}
            provenance.update(source_asset_sha256=F.pin(path)["sha256"], upstream_exposure_sha256=P.digest(condition))
            entries.append(dict(F.pin(path), session_id=sid, original_trial_numbers=TRIALS,
                                excluded_unlocked_trial_numbers=[9], source_condition=condition, provenance=provenance))
        cls.manifest = {"schema": "calcium_locked_mat73_manifest_v2", "author_commit": P.AUTHOR_COMMIT,
                        "recipe": recipe, "io_limits": {"max_file_bytes": 1024 * 1024,
                        "max_decoded_elements_per_file": 40000, "max_raw_report_bytes": 100000}, "sessions": entries}
        cls.raw_manifest = {"schema": "calcium_raw_mat73_manifest_v1", "author_commit": P.AUTHOR_COMMIT,
                            "limits": {"max_file_bytes": 1024 * 1024, "max_decoded_elements_per_file": 10000,
                                       "max_trials_per_session": 10}, "sessions": entries}
        generated_assets = {e["session_id"]: {"filename": e["path"], "bytes": e["bytes"],
                            "published_md5": hashlib.md5((cls.root / e["path"]).read_bytes()).hexdigest(),
                            "figshare_file_id": i} for i, e in enumerate(entries)}
        # Only the expected published inventory is replaced for generated
        # inputs. Full-file hashing, HDF5 reads and eligibility remain real.
        with patch.object(A, "primary_assets", return_value=generated_assets):
            cls.raw_report = A.inspect_raw(cls.raw_manifest, cls.root)
        cls.manifest["raw_inspection"] = write_json(cls.root / "raw-generated.json", cls.raw_report)
        cls.result = A.normalize_locked(cls.manifest, cls.root)
        cls.packet, cls.index = D.prepare(cls.result["dataset"], cls.result["protocol"], cls.result["context"],
                                          expected_protocol_sha256=cls.result["protocol_sha256"],
                                          expected_context_sha256=cls.result["context_sha256"])

    @classmethod
    def tearDownClass(cls):
        end = source_pins()
        print(json.dumps({"independent_fixture_bytes_written": F.WRITTEN, "fixture_budget_bytes": F.BUDGET,
                          "authentic_arrays_read": 0, "model_fits": 0, "source_start_sha256": START_PINS,
                          "source_end_sha256": end, "python": sys.version, "numpy": np.__version__,
                          "h5py": h5py.__version__}, sort_keys=True))
        if end != START_PINS:
            raise RuntimeError("Production sources changed during independent controls")

    def admit(self, dataset, protocol):
        return P.admit(dataset, protocol, expected_protocol_sha256=P.digest(protocol))

    def test_complete_radical_hdf5_axes_values_identity_and_census(self):
        self.assertEqual(len(self.result["dataset"]["sessions"]), 10)
        self.assertEqual(self.result["receipt"]["complete_mice"], 5)
        for row, receipt, raw, context in zip(self.result["dataset"]["sessions"], self.result["receipt"]["sessions"],
                                              self.raw_report["sessions"], self.result["context"]["sessions"]):
            self.assertIs(raw["trial_numbers_equal_one_based_positions"], True)
            self.assertEqual(raw["selected_trial_numbers"], TRIALS)
            self.assertEqual(receipt["included_trial_numbers"], TRIALS[:-1])
            self.assertEqual(receipt["excluded_trials"], [{"original_trial_number": 9, "reason": "both_native_lock_flags_false"}])
            self.assertEqual(receipt["source_grid_ms"], list(range(-200, 801, 10)))
            self.assertEqual(receipt["selected_source_rows_zero_based"], list(range(10, 61)))
            self.assertEqual(row["native_neural_field"], "radical_rates")
            self.assertEqual([r["original_trial_number"] for r in context["trials"]], TRIALS[:-1])
            self.assertEqual([r["reach_target"] for r in context["trials"]], ["left", "right"] * 3)
            for i, trial in zip(TRIALS, row["trials"]):
                self.assertEqual(trial["trial_id"], row["session_id"] + f":trial-{i}")
                self.assertEqual(trial["neural"], [[float(i + j*j), float(-i-j)] for j in range(10, 61)])
                self.assertEqual(trial["neural_time_ms"], list(range(-100, 401, 10)))
                self.assertEqual(trial["target_time_ms"], trial["neural_time_ms"])
                self.assertEqual(len(trial["targets"]), 51)
                self.assertEqual(len(trial["targets"][0]), 24)
            self.assertEqual(row["trials"][0]["targets"][0], [-11.5 + j for j in range(24)])
        self.assertEqual(self.result["dataset"]["target_units"], "degrees")
        self.assertFalse(self.result["receipt"]["scientific_qualification"])

    def test_actual_normalization_cli_and_output_binding(self):
        manifest_path = self.root / "manifest-v2.json"
        manifest_pin = write_json(manifest_path, self.manifest)
        output = self.root / "cli-normalized.json"
        run = subprocess.run([sys.executable, "-B", str(HERE / "admission.py"), "normalize-locked",
                              "--manifest", str(manifest_path), "--expected-manifest-sha256", manifest_pin["sha256"],
                              "--input-root", str(self.root), "--output", str(output), "--max-manifest-bytes", "100000",
                              "--max-output-bytes", str(F.BUDGET - F.WRITTEN)], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        F.charge(output)
        receipt = json.loads(run.stdout)
        self.assertEqual(receipt["output_sha256"], F.pin(output)["sha256"])
        self.assertEqual(json.loads(output.read_bytes()), self.result)

    def test_radical_raw_index_gate_refuses_false_and_boolean_aliases(self):
        noncontiguous = F.fixture_document(self.sid)["R"]
        raw = A.raw_census(noncontiguous, self.sid, P)
        self.assertIs(raw["trial_numbers_equal_one_based_positions"], False)
        for value in (False, 1, "true", None):
            with self.subTest(value=value):
                report = copy.deepcopy(self.raw_report)
                report["sessions"][0]["trial_numbers_equal_one_based_positions"] = value
                manifest = copy.deepcopy(self.manifest)
                manifest["raw_inspection"] = write_json(self.root / "raw-gate.json", report)
                with self.assertRaisesRegex(A.Refusal, "R\\(trialNumber\\)"):
                    A.normalize_locked(manifest, self.root)

    def test_unknown_exposure_and_conflicting_evidence_preserved(self):
        for row in self.result["dataset"]["sessions"]:
            condition = row["source_condition"]
            self.assertEqual(row["upstream_exposure_sha256"], P.digest(condition))
            model = condition["model_input_and_inference_context"]
            self.assertIsNone(model["actual_input_or_inference_interval_ms"])
            self.assertEqual(model["status"], "unverified_conflicting_source_evidence")
            self.assertFalse(model["locked_grid_establishes_model_exposure"])
            self.assertEqual(model["source_statements"]["possible_symmetric_padded_context_ms"], [-200, 900])
            self.assertEqual(model["source_statements"]["paper_model_window_ms"], [-100, 800])
            exposure = condition["fitted_trial_training_exposure"]
            self.assertEqual(exposure["status"], "unknown")
            self.assertEqual(exposure["evaluation_trial_exposure"], "unknown")
            self.assertEqual(exposure["fold_safety_status"], "unknown")
            self.assertIsNone(exposure["training_trial_ids"])
            self.assertTrue(all(v is False for v in condition["qualification"].values()))

    def test_numerical_and_split_functions_have_unchanged_ast(self):
        def functions(version):
            source = (BASE / version / "pipeline.py").read_text()
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        before, after = functions("train-only-decoding-v1"), functions("train-only-decoding-v2")
        for name in ("fit_train_only", "predict", "model_record", "paired_mouse_uncertainty",
                     "run_reference_controls", "freeze_within_mouse_splits"):
            with self.subTest(function=name):
                self.assertEqual(before[name], after[name])

    def test_events_preprocessing_kept_separate_from_radical(self):
        events = C.build_source_condition("smoothed_deconvolved_events")
        radical = C.build_source_condition("radical")
        self.assertEqual(events["preprocessing_support"]["additional_gaussian_smoothing_sd_ms"], 35)
        self.assertEqual(events["preprocessing_support"]["source_requested_resampling_grid_ms"], list(range(-270, 871, 10)))
        self.assertIsNone(radical["preprocessing_support"]["additional_gaussian_smoothing_sd_ms"])
        self.assertIsNone(radical["preprocessing_support"]["source_requested_resampling_grid_ms"])
        for record in (events, radical):
            self.assertIsNone(record["preprocessing_support"]["actual_raw_frame_dependency_interval_ms"])
            self.assertFalse(record["preprocessing_support"]["requested_grid_is_full_raw_dependency_bound"])
            self.assertEqual(C.validate_source_condition(record, record["feature_variant"]), P.digest(record))
        with self.assertRaises(ValueError):
            C.validate_source_condition(events, "radical")

    def test_invented_exposure_bound_safety_and_training_claims_refused(self):
        edits = [("model_input_and_inference_context", "actual_input_or_inference_interval_ms", [-200, 800]),
                 ("model_input_and_inference_context", "actual_input_or_inference_interval_ms", [-200, 900]),
                 ("model_input_and_inference_context", "locked_grid_establishes_model_exposure", True),
                 ("preprocessing_support", "actual_raw_frame_dependency_interval_ms", [-270, 870]),
                 ("preprocessing_support", "requested_grid_is_full_raw_dependency_bound", True),
                 ("preprocessing_support", "additional_gaussian_smoothing_sd_ms", 35),
                 ("fitted_trial_training_exposure", "status", "verified"),
                 ("fitted_trial_training_exposure", "evaluation_trial_exposure", "excluded"),
                 ("fitted_trial_training_exposure", "fold_safety_status", "safe"),
                 ("fitted_trial_training_exposure", "training_trial_ids", []),
                 ("qualification", "bounded_raw_observation_qualified", True),
                 ("qualification", "upstream_fold_safety_qualified", True),
                 ("qualification", "scientific_qualification", True),
                 ("qualification", "causal_or_online_qualified", 0)]
        for section, field, value in edits:
            with self.subTest(section=section, field=field, value=value):
                condition = C.build_source_condition("radical")
                condition[section][field] = value
                with self.assertRaises(ValueError):
                    C.validate_source_condition(condition, "radical")
        condition = C.build_source_condition("radical")
        condition["decoder_output_grid_ms"][10] = False
        with self.assertRaises(ValueError):
            C.validate_source_condition(condition, "radical")

    def test_source_body_and_digest_are_enforced_at_each_admission_layer(self):
        for tamper_body in (False, True):
            with self.subTest(tamper_body=tamper_body):
                manifest = copy.deepcopy(self.manifest)
                if tamper_body:
                    manifest["sessions"][0]["source_condition"]["qualification"]["scientific_qualification"] = True
                    manifest["sessions"][0]["provenance"]["upstream_exposure_sha256"] = P.digest(manifest["sessions"][0]["source_condition"])
                else:
                    manifest["sessions"][0]["provenance"]["upstream_exposure_sha256"] = "a" * 64
                with self.assertRaises(ValueError):
                    A.normalize_locked(manifest, self.root)
                dataset, protocol = copy.deepcopy(self.result["dataset"]), copy.deepcopy(self.result["protocol"])
                for doc in (dataset, protocol):
                    if tamper_body:
                        doc["sessions"][0]["source_condition"]["model_input_and_inference_context"]["actual_input_or_inference_interval_ms"] = [-200, 800]
                        doc["sessions"][0]["upstream_exposure_sha256"] = P.digest(doc["sessions"][0]["source_condition"])
                    else:
                        doc["sessions"][0]["upstream_exposure_sha256"] = "a" * 64
                with self.assertRaises(ValueError):
                    self.admit(dataset, protocol)

    def test_legacy_exposure_field_refused_even_nested(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["extra"] = [{"upstream_temporal_support_ms": [-200, 900]}]
        with self.assertRaisesRegex(ValueError, "Legacy"):
            A.normalize_locked(manifest, self.root)
        for side in ("dataset", "protocol"):
            with self.subTest(side=side):
                docs = {k: copy.deepcopy(self.result[k]) for k in ("dataset", "protocol")}
                docs[side]["extra"] = [{"upstream_temporal_support_ms": [-200, 800]}]
                with self.assertRaises(ValueError):
                    self.admit(**docs)

    def test_complete_population_and_exact_grid_remain_required(self):
        for change in ("short_manifest", "short_dataset", "short_target", "shift_window", "wrong_units"):
            with self.subTest(change=change):
                if change == "short_manifest":
                    manifest = copy.deepcopy(self.manifest)
                    manifest["sessions"].pop()
                    with self.assertRaises(ValueError):
                        A.normalize_locked(manifest, self.root)
                    continue
                dataset, protocol = copy.deepcopy(self.result["dataset"]), copy.deepcopy(self.result["protocol"])
                if change == "short_dataset":
                    dataset["sessions"].pop()
                elif change == "short_target":
                    dataset["sessions"][0]["trials"][0]["targets"].pop()
                elif change == "shift_window":
                    protocol["window_ms"] = [-100, 800]
                else:
                    dataset["target_units"] = "radians"
                with self.assertRaises(ValueError):
                    self.admit(dataset, protocol)

    def test_query_labels_do_not_change_public_packet(self):
        dataset = copy.deepcopy(self.result["dataset"])
        bindings = {s["session_id"]: s for s in self.result["protocol"]["sessions"]}
        for row in dataset["sessions"]:
            ids = set(bindings[row["session_id"]]["evaluation_trial_ids"])
            for trial in row["trials"]:
                if trial["trial_id"] in ids:
                    trial["targets"] = (np.asarray(trial["targets"]) + 12345).tolist()
        packet, index = D.prepare(dataset, self.result["protocol"], self.result["context"],
                                  expected_protocol_sha256=self.result["protocol_sha256"],
                                  expected_context_sha256=self.result["context_sha256"])
        self.assertEqual(P.canonical_bytes(packet), P.canonical_bytes(self.packet))
        self.assertNotEqual(index["normalized_input_sha256"], self.index["normalized_input_sha256"])
        for session in packet["sessions"]:
            self.assertTrue(all("targets" in t for t in session["training"]))
            self.assertTrue(all("targets" not in t for t in session["query"]))
            training = session["source_condition"]["fitted_trial_training_exposure"]
            self.assertEqual(training, {"status": "unknown", "evaluation_trial_exposure": "unknown", "fold_safety_status": "unknown"})
            self.assertNotIn("source_evidence", session["source_condition"])

    def response(self):
        targets = {s["session_id"]: {t["trial_id"]: t["targets"] for t in s["trials"]} for s in self.result["dataset"]["sessions"]}
        predictions = {sid: {case: targets[mapping["session_id"]][tid] for case, tid in mapping["query"].items()}
                       for sid, mapping in self.index["sessions"].items()}
        return {"schema": D.RESPONSE_SCHEMA, "task_id": P.TASK_ID, "packet_sha256": P.digest(self.packet),
                "mode": "direct_observation", "predictions": predictions,
                **{k: copy.deepcopy(self.packet[k]) for k in ("target_field", "target_units", "joint_names", "time_ms")}}

    def collection(self, response):
        return D.collect_response(response, self.packet, self.index, expected_packet_sha256=P.digest(self.packet),
                                  expected_index_sha256=P.digest(self.index), expected_mode="direct_observation")

    def test_full_collection_scoring_unchanged_and_incomplete_response_refused(self):
        response = self.response()
        collected = self.collection(response)
        self.assertEqual(set(collected), set(P.SESSIONS))
        self.assertEqual(sum(len(v) for v in collected.values()), 20)
        score = D.score_response(self.result["dataset"], self.result["protocol"], response, self.packet, self.index,
                                 expected_protocol_sha256=self.result["protocol_sha256"],
                                 expected_packet_sha256=P.digest(self.packet), expected_index_sha256=P.digest(self.index),
                                 expected_mode="direct_observation")["metrics"]
        self.assertEqual(score["mouse_macro_nrmse"], 0.)
        self.assertEqual(score["mouse_macro_r_squared_per_joint"], [1.] * 24)
        self.assertEqual(score["support"]["evaluation_trials"], 20)
        self.assertFalse(score["verification"]["scientific_qualification"])
        for change in ("session", "trial", "grid", "shape", "nan"):
            with self.subTest(change=change):
                response = copy.deepcopy(self.response())
                sid = next(iter(response["predictions"]))
                case = next(iter(response["predictions"][sid]))
                if change == "session":
                    response["predictions"].pop(sid)
                elif change == "trial":
                    response["predictions"][sid].pop(case)
                elif change == "grid":
                    response["time_ms"][-1] = 800
                elif change == "shape":
                    response["predictions"][sid][case].pop()
                else:
                    response["predictions"][sid][case][0][0] = float("nan")
                with self.assertRaises(ValueError):
                    self.collection(response)


if __name__ == "__main__":
    unittest.main(verbosity=2)
