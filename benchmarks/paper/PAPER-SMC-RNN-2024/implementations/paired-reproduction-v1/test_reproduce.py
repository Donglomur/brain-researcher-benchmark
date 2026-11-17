"""Independent generated controls; no authentic signals, targets, or AI runs.

The complete-path numerical test invokes the byte-pinned, unchanged NLB evaluator
on generated arrays. Production reference admission remains the full original
panel; the small generated panel is substituted only inside these tests.
"""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np


SPEC = importlib.util.spec_from_file_location("smc_paired_reproduction_controls", Path(__file__).with_name("reproduce.py"))
reproduce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reproduce)
ORIGINAL_VERIFY_SOURCES = reproduce.verify_sources
ORIGINAL_SOURCE_PINS = dict(reproduce.SOURCE_PINS)
KNOWN_FIXTURE_BYTES = 0


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PairedReproductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.public = self.root / "participant"
        self.public.mkdir()
        self.operator = self.root / "operator"
        self.operator.mkdir()
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.predictions = {arm: self.public / (arm + ".h5") for arm in reproduce.ARMS}
        self.panel = self.root / "panel.json"
        self.reference = self.root / "generated-reference.json"
        self.episode_path = self.root / "episode.json"
        self.pair_path = self.root / "pair.json"
        self.delivery_path = self.root / "delivery.json"
        self.executions_path = self.root / "executions.json"
        self.freeze_path = self.root / "freeze.json"
        self.score_path = self.root / "score.json"
        self.target = self.operator / "generated-target.h5"
        self.condition = "paper_data"
        self.task_sha = digest(reproduce.TASK / "task.json")
        self.manifest = {
            "schema": "smc_nlb_panel_v1", "dataset": "mc_maze_20", "phase": "test",
            "source_commit": reproduce.source.AUTHOR_COMMIT, "dandiset": "000128",
            "dandi_version": "0.220113.0400", "bin_ms": 20,
            "n_train": 6, "n_eval": 4, "n_bins": 35, "forward_bins": 10,
            "n_heldin": 137, "n_heldout": 45, "condition_count": 108,
            "trial_indices_sha256": "1" * 64, "neuron_indices_sha256": "2" * 64,
            "conditions_sha256": "3" * 64, "tensor_trial_indices_sha256": "4" * 64,
            "condition_membership_sha256": "5" * 64, "split_counts": {"train": 4, "val": 2, "test": 4},
            "inputs_sha256": {"generated_fixture": "6" * 64},
            "input_content_sha256": {"generated_fixture": "7" * 64},
            "nwb_sources": [{"name": "generated_fixture", "sha256": "8" * 64}],
        }
        self.manifest["expected_shapes"] = {
            key: [6 if key.startswith("train_") else 4,
                  10 if key.endswith("_forward") else 35,
                  137 if "heldin" in key else 45]
            for key in reproduce.source.RATE_KEYS
        }
        self.write_json(self.panel, self.manifest)
        self.write_json(self.reference, self.manifest)
        self.use_patch(reproduce, "verify_sources", lambda: None)
        self.use_patch(reproduce, "SOURCE_PINS", {**ORIGINAL_SOURCE_PINS, "reference_panel.json": digest(self.reference)})
        self.use_patch(reproduce.source, "REFERENCE_PANEL", self.reference)
        for index, arm in enumerate(reproduce.ARMS):
            rng = np.random.default_rng(471 + index)
            with h5py.File(self.predictions[arm], "w") as handle:
                group = handle.create_group(reproduce.source.DATASET)
                for key in sorted(reproduce.source.REQUIRED_KEYS):
                    group.create_dataset(key, data=rng.uniform(0.1, 3, self.manifest["expected_shapes"][key]).astype(np.float32))
            self.charge(self.predictions[arm])
        self.delivery = {
            "schema": "smc_offline_participant_delivery_v1", "task_id": reproduce.TASK_ID,
            "condition": self.condition, "current_task_sha256": self.task_sha,
            "primary_contract_sha256": reproduce.PRIMARY_SHA256,
            "files": [
                {"path": "registered_task.json", "sha256": self.task_sha},
                {"path": "reproduction.v1.json", "sha256": reproduce.REPRODUCTION_SHA256},
                {"path": "author_baseline_protocol.json", "sha256": reproduce.SOURCE_PINS["protocol.json"]},
                {"path": "inputs/mc_maze/test/panel.json", "sha256": digest(self.panel)},
            ],
        }
        self.pair = {
            "schema": "smc_offline_paired_delivery_v1", "task_id": reproduce.TASK_ID,
            "conditions": list(reproduce.CONDITIONS), "current_task_sha256": self.task_sha,
            "primary_contract_sha256": reproduce.PRIMARY_SHA256,
        }
        self.episode = {
            "schema": "smc_paired_reproduction_policy_v1", "task_id": reproduce.TASK_ID,
            "outcome": "reproduction", "current_task_sha256": self.task_sha,
            "reproduction_contract_sha256": reproduce.REPRODUCTION_SHA256,
            "reference_panel_sha256": digest(self.reference),
            "author_protocol_sha256": reproduce.SOURCE_PINS["protocol.json"],
            **{key: "a" * 64 for key in (
                "materials_policy_sha256", "selection_adaptation_policy_sha256",
                "resource_budget_policy_sha256", "source_identity_review_sha256",
                "agreement_policy_sha256", "uncertainty_policy_sha256", "trusted_operator_review_sha256")},
        }
        self.executions = {
            "schema": "smc_ai_reproduction_execution_v1", "task_id": reproduce.TASK_ID,
            "outcome": "reproduction", "condition": self.condition,
            "method_id": "generated-independent-implementation", "arms": {
                arm: {"role": "ai_reproduction", "source_arm": arm,
                      "submission_sha256": digest(self.predictions[arm]),
                      "analysis_source_sha256": ("b" if arm == "causal" else "c") * 64,
                      "run_receipt_sha256": ("d" if arm == "causal" else "e") * 64,
                      "source_method_review_sha256": "f" * 64,
                      "granular_output_review_sha256": "0" * 64,
                      "seed": 12 + index, "particles": 192, "repeats": 32, "smooth": False,
                      "behavior_guided_fitting": False, "behavior_guided_selection": False}
                for index, arm in enumerate(reproduce.ARMS)
            },
        }
        self.bind_context()

    @staticmethod
    def charge(path):
        global KNOWN_FIXTURE_BYTES
        KNOWN_FIXTURE_BYTES += Path(path).stat().st_size

    def write_json(self, path, value):
        Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        self.charge(path)

    def use_patch(self, owner, name, value):
        manager = patch.object(owner, name, value)
        manager.start()
        self.addCleanup(manager.stop)

    def bind_context(self):
        self.write_json(self.delivery_path, self.delivery)
        manifests = {condition: "8" * 64 for condition in reproduce.CONDITIONS}
        manifests[self.condition] = digest(self.delivery_path)
        self.pair["condition_manifest_sha256"] = manifests
        self.write_json(self.pair_path, self.pair)
        self.episode["paired_delivery_sha256"] = digest(self.pair_path)
        self.episode["condition_manifest_sha256"] = manifests
        self.bind_episode()

    def bind_episode(self):
        self.write_json(self.episode_path, self.episode)
        self.episode_sha = digest(self.episode_path)
        self.executions["episode_policy_sha256"] = self.episode_sha
        self.bind_executions()

    def bind_executions(self):
        self.write_json(self.executions_path, self.executions)
        self.executions_sha = digest(self.executions_path)

    def common(self):
        return (self.predictions, self.panel, self.episode_path, self.episode_sha,
                self.pair_path, self.delivery_path, self.executions_path, self.executions_sha)

    def freeze(self):
        return reproduce.freeze_predictions(*self.common(), self.freeze_path, condition=self.condition)

    def validate(self):
        return reproduce.validate_freeze(*self.common(), self.freeze_path)

    def score(self, evaluator_path=None, **kwargs):
        if evaluator_path is None:
            evaluator_path = reproduce.RETAINED / "third_party" / "nlb_tools_0_0_3" / "evaluation.py"
        options = {"scratch_root": self.scratch, "scratch_budget_bytes": 2 * 1024 * 1024}
        options.update(kwargs)
        return reproduce.score_predictions(*self.common(), self.freeze_path, self.target,
            reproduce.source.TARGET_SHA256, evaluator_path, self.score_path, **options)

    def mock_target(self, function=None):
        self.target.write_bytes(b"generated target; no neural data")
        self.charge(self.target)
        self.use_patch(reproduce.source, "TARGET_SHA256", digest(self.target))
        self.use_patch(reproduce.importlib.metadata, "version", lambda unused: "generated-fixture")
        if function is None:
            function = lambda target, pred: [{reproduce.source.DATASET + "_split":
                dict(zip(reproduce.source.METRICS, (0.31, 0.8, 0.6, 0.2)))}]
        loader = patch.object(reproduce.source, "load_original_scorer",
                              return_value=types.SimpleNamespace(evaluate=function))
        mocked = loader.start()
        self.addCleanup(loader.stop)
        return mocked

    def test_joint_freeze_is_target_blind_with_six_scored_arrays(self):
        self.assertFalse(self.target.exists())
        record = self.freeze()
        self.assertEqual(set(record["submission_sha256"]), set(reproduce.ARMS))
        self.assertEqual(record["scientific_outcome"], "unknown")
        self.assertEqual(record["role"], "ai_reproduction")
        for arm in reproduce.ARMS:
            self.assertEqual(record["submission_sha256"][arm], digest(self.predictions[arm]))
        self.validate()
        self.assertFalse(self.target.exists())
        with self.assertRaises(FileExistsError):
            self.freeze()

    def test_optional_training_forward_arrays_remain_optional(self):
        with h5py.File(self.predictions["noncausal"], "a") as handle:
            for key in reproduce.source.OPTIONAL_KEYS:
                handle[reproduce.source.DATASET].create_dataset(key, data=np.ones(self.manifest["expected_shapes"][key], dtype=np.float32))
        self.executions["arms"]["noncausal"]["submission_sha256"] = digest(self.predictions["noncausal"])
        self.bind_executions()
        record = self.freeze()
        self.assertEqual(len(record["submission_sha256"]), 2)
        self.validate()

    def test_second_access_condition_is_supported_without_author_code_identity(self):
        self.condition = "paper_data_author_code"
        self.delivery["condition"] = self.condition
        self.executions["condition"] = self.condition
        self.bind_context()
        record = self.freeze()
        self.assertEqual(record["condition"], self.condition)
        self.assertNotEqual(self.executions["arms"]["causal"]["analysis_source_sha256"], reproduce.source.AUTHOR_COMMIT)
        self.validate()

    def test_both_source_arms_are_required(self):
        self.predictions.pop("noncausal")
        with self.assertRaisesRegex(ValueError, "both source-arm"):
            self.freeze()
        self.assertFalse(self.freeze_path.exists())

    def test_invalid_second_arm_refused_before_any_result(self):
        with h5py.File(self.predictions["noncausal"], "a") as handle:
            del handle[reproduce.source.DATASET]["eval_rates_heldout_forward"]
        with self.assertRaisesRegex(ValueError, "missing or extra"):
            self.freeze()
        self.assertFalse(self.freeze_path.exists())
        self.assertFalse(self.target.exists())

    def test_favorable_subset_and_extra_dataset_fail(self):
        with h5py.File(self.predictions["noncausal"], "a") as handle:
            group = handle[reproduce.source.DATASET]
            del group["eval_rates_heldout"]
            group.create_dataset("eval_rates_heldout", data=np.ones((1, 35, 45)))
        with self.assertRaisesRegex(ValueError, "incomplete or misaligned"):
            self.freeze()
        with h5py.File(self.predictions["noncausal"], "a") as handle:
            handle.create_group("another_panel")
        with self.assertRaisesRegex(ValueError, "exactly mc_maze_20"):
            self.freeze()

    def test_negative_nonfinite_and_indirect_predictions_fail(self):
        path = self.predictions["noncausal"]
        for invalid in (-1, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                with h5py.File(path, "a") as handle:
                    handle[reproduce.source.DATASET]["eval_rates_heldout"][0, 0, 0] = invalid
                with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                    self.freeze()
        with h5py.File(path, "a") as handle:
            group = handle[reproduce.source.DATASET]
            del group["eval_rates_heldout"]
            group["eval_rates_heldout"] = h5py.ExternalLink(str(self.target), "/private")
        with self.assertRaisesRegex(ValueError, "external or soft"):
            self.freeze()
        self.assertFalse(self.target.exists())

    def test_panel_order_identity_cannot_be_redeclared(self):
        self.manifest["trial_indices_sha256"] = "f" * 64
        self.write_json(self.panel, self.manifest)
        with self.assertRaisesRegex(ValueError, "complete source reference"):
            self.freeze()

    def test_calibration_and_improvement_execution_records_are_rejected(self):
        original = copy.deepcopy(self.executions)
        for key, value in (("schema", "smc_nlb_prediction_freeze_v1"), ("outcome", "improvement")):
            with self.subTest(key=key):
                self.executions = {**original, key: value}
                self.bind_executions()
                with self.assertRaisesRegex(ValueError, "not an AI reproduction"):
                    self.freeze()
        self.executions = copy.deepcopy(original)
        self.executions["arms"]["noncausal"]["role"] = "author_calibration"
        self.bind_executions()
        with self.assertRaisesRegex(ValueError, "execution fields or role"):
            self.freeze()

    def test_source_method_review_and_granular_evidence_are_required(self):
        for name in ("analysis_source_sha256", "run_receipt_sha256", "source_method_review_sha256", "granular_output_review_sha256"):
            with self.subTest(name=name):
                original = self.executions["arms"]["noncausal"][name]
                self.executions["arms"]["noncausal"][name] = None
                self.bind_executions()
                with self.assertRaisesRegex(ValueError, "missing execution evidence"):
                    self.freeze()
                self.executions["arms"]["noncausal"][name] = original

    def test_original_recipe_cannot_be_downsampled_or_smoothed(self):
        for key, value in (("particles", 64), ("repeats", 1), ("smooth", True), ("particles", True)):
            with self.subTest(key=key, value=value):
                original = self.executions["arms"]["noncausal"][key]
                self.executions["arms"]["noncausal"][key] = value
                self.bind_executions()
                with self.assertRaisesRegex(ValueError, "original source inference recipe"):
                    self.freeze()
                self.executions["arms"]["noncausal"][key] = original

    def test_execution_condition_arm_seed_and_behavior_cannot_be_ambiguous(self):
        original = copy.deepcopy(self.executions)
        changes = (("source_arm", "causal"), ("seed", True), ("behavior_guided_selection", None))
        for key, value in changes:
            with self.subTest(key=key):
                self.executions = copy.deepcopy(original)
                self.executions["arms"]["noncausal"][key] = value
                self.bind_executions()
                with self.assertRaises(ValueError):
                    self.freeze()
        self.executions = copy.deepcopy(original)
        self.executions["condition"] = "paper_data_author_code"
        self.bind_executions()
        with self.assertRaisesRegex(ValueError, "condition or policy differs"):
            self.freeze()

    def test_agreement_uncertainty_and_qualified_source_identity_are_not_defaulted(self):
        for key in ("agreement_policy_sha256", "uncertainty_policy_sha256", "source_identity_review_sha256"):
            with self.subTest(key=key):
                original = self.episode[key]
                self.episode[key] = None
                self.bind_episode()
                with self.assertRaisesRegex(ValueError, "missing policy identity"):
                    self.freeze()
                self.episode[key] = original

    def test_wrong_contract_panel_and_source_recipe_pins_fail(self):
        for key in ("reproduction_contract_sha256", "reference_panel_sha256", "author_protocol_sha256"):
            with self.subTest(key=key):
                original = self.episode[key]
                self.episode[key] = "0" * 64
                self.bind_episode()
                with self.assertRaisesRegex(ValueError, "wrong reproduction contract"):
                    self.freeze()
                self.episode[key] = original

    def test_bound_manifest_cannot_contradict_actual_task(self):
        self.delivery["current_task_sha256"] = "1" * 64
        self.bind_context()
        with self.assertRaisesRegex(ValueError, "condition delivery differs"):
            self.freeze()

    def test_bound_pair_cannot_drop_condition_or_change_contract(self):
        self.pair["conditions"] = ["paper_data"]
        self.bind_context()
        with self.assertRaisesRegex(ValueError, "paired delivery differs"):
            self.freeze()

    def test_delivered_reproduction_and_recipe_inventory_are_bound(self):
        self.delivery["files"][1]["sha256"] = "7" * 64
        self.bind_context()
        with self.assertRaisesRegex(ValueError, "delivered source identities differ"):
            self.freeze()
        self.delivery["files"].append(dict(self.delivery["files"][0]))
        self.bind_context()
        with self.assertRaisesRegex(ValueError, "duplicate delivery paths"):
            self.freeze()

    def test_trusted_episode_and_execution_pins_cannot_be_replaced(self):
        self.episode_sha = "0" * 64
        with self.assertRaisesRegex(ValueError, "trusted frozen identity"):
            self.freeze()
        self.episode_sha = digest(self.episode_path)
        self.executions_sha = "0" * 64
        with self.assertRaisesRegex(ValueError, "trusted frozen identity"):
            self.freeze()

    def test_changed_second_prediction_refused_before_scorer_or_target(self):
        self.freeze()
        with h5py.File(self.predictions["noncausal"], "a") as handle:
            handle[reproduce.source.DATASET]["eval_rates_heldout"][0, 0, 0] = 3
        with patch.object(reproduce.source, "load_original_scorer") as loader:
            with self.assertRaisesRegex(ValueError, "trusted execution output"):
                self.score()
            loader.assert_not_called()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.score_path.exists())

    def test_old_calibration_and_offline_freezes_cannot_be_relabelled(self):
        for schema in ("smc_nlb_prediction_freeze_v1", "smc_nlb_offline_prediction_freeze_v1"):
            with self.subTest(schema=schema):
                self.write_json(self.freeze_path, {"schema": schema, "task_id": reproduce.TASK_ID,
                    "role": "ai_reproduction", "outcome": "reproduction"})
                with self.assertRaisesRegex(ValueError, "not a joint AI reproduction freeze"):
                    self.validate()

    def test_freeze_exposure_outcome_timestamp_and_extra_fields_are_enforced(self):
        original = self.freeze()
        for key, value in (("target_exposure", "untouched_holdout"), ("scientific_outcome", "pass"),
                           ("unexpected", True), ("created_utc", "2026-11-17T00:00:00-08:00")):
            with self.subTest(key=key):
                self.write_json(self.freeze_path, {**original, key: value})
                with self.assertRaises(ValueError):
                    self.validate()

    def test_both_snapshots_exist_before_first_target_read(self):
        self.freeze()
        self.mock_target()
        original_hash = reproduce.hash_file
        target_reads = []
        def observe(path, limit=reproduce.MAX_JSON_BYTES):
            if Path(path) == self.target:
                snapshots = sorted(self.scratch.glob("*/" + "*.h5"))
                self.assertEqual([p.name for p in snapshots], ["causal.h5", "noncausal.h5"])
                for snapshot in snapshots:
                    self.assertEqual(digest(snapshot), digest(self.predictions[snapshot.stem]))
                target_reads.append(str(path))
            return original_hash(path, limit)
        with patch.object(reproduce, "hash_file", side_effect=observe):
            report = self.score()
        self.assertEqual(len(target_reads), 2)
        self.assertEqual(len(report["findings"]), 8)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_second_snapshot_failure_never_reads_target(self):
        self.freeze()
        first = reproduce._snapshot
        calls = []
        def broken(path, destination, expected, *, byte_budget):
            calls.append(Path(destination).name)
            if Path(destination).name == "noncausal.h5":
                raise ValueError("generated second-snapshot failure")
            return first(path, destination, expected, byte_budget=byte_budget)
        with patch.object(reproduce, "_snapshot", side_effect=broken), \
             patch.object(reproduce.source, "load_original_scorer", return_value=types.SimpleNamespace(evaluate=None)):
            with self.assertRaisesRegex(ValueError, "second-snapshot failure"):
                self.score()
        self.assertEqual(calls, ["causal.h5", "noncausal.h5"])
        self.assertFalse(self.target.exists())
        self.assertFalse(self.score_path.exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_second_evaluator_failure_has_no_partial_public_result(self):
        self.freeze()
        calls = []
        def failing(target, prediction):
            calls.append(Path(prediction).stem)
            if len(calls) == 2:
                raise RuntimeError("generated second-arm failure")
            return [{reproduce.source.DATASET + "_split": dict(zip(reproduce.source.METRICS, (0.3, 0.8, 0.6, 0.2)))}]
        self.mock_target(failing)
        with self.assertRaisesRegex(RuntimeError, "second-arm failure"):
            self.score()
        self.assertEqual(calls, ["causal", "noncausal"])
        self.assertFalse(self.score_path.exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_missing_companion_and_nonfinite_metric_refuse_whole_panel(self):
        self.freeze()
        for invalid in ({"co-bps": 0.4}, dict(zip(reproduce.source.METRICS, (float("nan"), 0.8, 0.6, 0.2)))):
            with self.subTest(invalid=invalid):
                self.target.write_bytes(b"generated target")
                with patch.object(reproduce.source, "TARGET_SHA256", digest(self.target)), \
                     patch.object(reproduce.source, "load_original_scorer", return_value=types.SimpleNamespace(
                         evaluate=lambda target, prediction: [{reproduce.source.DATASET + "_split": invalid}])):
                    with self.assertRaises(ValueError):
                        self.score()
                self.assertFalse(self.score_path.exists())

    def test_frozen_policy_or_execution_replacement_during_score_refuses_output(self):
        self.freeze()
        def replacing(target, prediction):
            self.executions["arms"]["noncausal"]["seed"] = 999
            self.write_json(self.executions_path, self.executions)
            return [{reproduce.source.DATASET + "_split": dict(zip(reproduce.source.METRICS, (0.3, 0.8, 0.6, 0.2)))}]
        self.mock_target(replacing)
        with self.assertRaisesRegex(ValueError, "record changed during scoring"):
            self.score()
        self.assertFalse(self.score_path.exists())

    def test_prediction_snapshot_mutation_during_score_refuses_output(self):
        self.freeze()
        def corrupt(target, prediction):
            with Path(prediction).open("ab") as handle:
                handle.write(b"changed")
            return [{reproduce.source.DATASET + "_split": dict(zip(reproduce.source.METRICS, (0.3, 0.8, 0.6, 0.2)))}]
        self.mock_target(corrupt)
        with self.assertRaisesRegex(ValueError, "snapshot changed during paired scoring"):
            self.score()
        self.assertFalse(self.score_path.exists())

    def test_target_mutation_during_score_refuses_output(self):
        self.freeze()
        def corrupt(target, prediction):
            Path(target).write_bytes(b"changed generated target")
            return [{reproduce.source.DATASET + "_split": dict(zip(reproduce.source.METRICS, (0.3, 0.8, 0.6, 0.2)))}]
        self.mock_target(corrupt)
        with self.assertRaisesRegex(ValueError, "target changed during paired scoring"):
            self.score()
        self.assertFalse(self.score_path.exists())

    def test_wrong_target_or_insufficient_scratch_refuse_before_loading(self):
        self.freeze()
        with patch.object(reproduce.source, "load_original_scorer") as loader:
            with self.assertRaisesRegex(ValueError, "snapshots exceed scratch budget"):
                self.score(scratch_budget_bytes=1)
            with self.assertRaisesRegex(ValueError, "scratch budget must be positive"):
                self.score(scratch_budget_bytes=True)
            with self.assertRaisesRegex(ValueError, "target must be original"):
                reproduce.score_predictions(*self.common(), self.freeze_path, self.target, "0" * 64,
                    "unused", self.score_path, scratch_root=self.scratch, scratch_budget_bytes=2 * 1024 * 1024)
            loader.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_output_never_overwrites_an_existing_record(self):
        self.freeze()
        self.score_path.write_text("previous result\n")
        with patch.object(reproduce.source, "load_original_scorer") as loader:
            with self.assertRaisesRegex(ValueError, "output already exists"):
                self.score()
            loader.assert_not_called()
        self.assertEqual(self.score_path.read_text(), "previous result\n")

    def test_output_hash_must_match_trusted_execution(self):
        self.executions["arms"]["noncausal"]["submission_sha256"] = "0" * 64
        self.bind_executions()
        with self.assertRaisesRegex(ValueError, "trusted execution output"):
            self.freeze()
        self.assertFalse(self.freeze_path.exists())

    def test_supplied_panel_must_be_exact_delivered_bytes(self):
        self.manifest["generated_extra_metadata"] = True
        self.write_json(self.panel, self.manifest)
        with self.assertRaisesRegex(ValueError, "delivered input panel"):
            self.freeze()

    def test_consistent_but_obsolete_task_identity_fails(self):
        self.episode["current_task_sha256"] = "1" * 64
        self.pair["current_task_sha256"] = "1" * 64
        self.delivery["current_task_sha256"] = "1" * 64
        self.delivery["files"][0]["sha256"] = "1" * 64
        self.bind_context()
        with self.assertRaisesRegex(ValueError, "current canonical task"):
            self.freeze()

    def test_scratch_budget_is_decremented_across_both_snapshots(self):
        self.freeze()
        self.mock_target()
        first = reproduce._snapshot
        budgets = []
        def observe(path, destination, expected, *, byte_budget):
            budgets.append(byte_budget)
            return first(path, destination, expected, byte_budget=byte_budget)
        sizes = [self.predictions[arm].stat().st_size for arm in reproduce.ARMS]
        with patch.object(reproduce, "_snapshot", side_effect=observe):
            self.score(scratch_budget_bytes=sum(sizes))
        self.assertEqual(budgets, [sum(sizes), sizes[1]])

    def test_growing_input_never_writes_over_remaining_budget(self):
        class GrowingReader(io.BytesIO):
            def read(self, unused=-1):
                return super().read(2)
        destination = self.root / "bounded-snapshot.h5"
        initial = types.SimpleNamespace(st_size=3)
        with patch.object(reproduce, "_open_file", return_value=(GrowingReader(b"abcd"), initial)):
            with self.assertRaisesRegex(ValueError, "grew beyond remaining scratch budget"):
                reproduce._snapshot(self.predictions["causal"], destination, "0" * 64, byte_budget=3)
        self.assertEqual(destination.read_bytes(), b"ab")
        self.charge(destination)

    def test_target_parent_alias_refused_before_target_read(self):
        self.freeze()
        alias = self.root / "participant-alias"
        alias.symlink_to(self.public, target_is_directory=True)
        self.target = alias / "missing-target.h5"
        with patch.object(reproduce.source, "load_original_scorer") as loader:
            with self.assertRaisesRegex(ValueError, "target must be separate"):
                self.score()
            loader.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_wrong_scorer_bytes_and_special_file_refused_before_import(self):
        self.freeze()
        fake = self.root / "fake-evaluation.py"
        fake.write_text("raise RuntimeError('must not import')\n")
        fifo = self.root / "scorer-fifo"
        os.mkfifo(fifo)
        with patch.object(reproduce.source, "load_original_scorer") as loader:
            with self.assertRaisesRegex(ValueError, "bounded original evaluator"):
                self.score(fake)
            with self.assertRaisesRegex(ValueError, "ordinary file"):
                self.score(fifo)
            loader.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_bounded_metadata_rejects_duplicate_nonfinite_symlink_and_oversize(self):
        sample = self.root / "bad.json"
        for contents in ('{"a": 1, "a": 2}', '{"a": NaN}', '[]'):
            with self.subTest(contents=contents):
                sample.write_text(contents)
                with self.assertRaises(ValueError):
                    reproduce.read_json(sample)
        sample.write_bytes(b" " * (reproduce.MAX_JSON_BYTES + 1))
        self.charge(sample)
        with self.assertRaisesRegex(ValueError, "byte bound"):
            reproduce.read_json(sample)
        link = self.root / "linked.json"
        link.symlink_to(self.episode_path)
        with self.assertRaises(OSError):
            reproduce.read_json(link)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "ordinary file"):
            reproduce.read_json(fifo)

    def test_cli_freeze_then_score_uses_complete_paired_path(self):
        arguments = []
        for name, path in (("causal", self.predictions["causal"]), ("noncausal", self.predictions["noncausal"]),
                           ("panel", self.panel), ("episode-policy", self.episode_path),
                           ("pair-manifest", self.pair_path), ("delivery-manifest", self.delivery_path),
                           ("executions", self.executions_path)):
            arguments.extend(["--" + name, str(path)])
        arguments.extend(["--episode-policy-sha256", self.episode_sha, "--executions-sha256", self.executions_sha])
        frozen_stdout = io.StringIO()
        with redirect_stdout(frozen_stdout):
            reproduce.main(["freeze", *arguments, "--condition", self.condition, "--output", str(self.freeze_path)])
        frozen = json.loads(frozen_stdout.getvalue())
        self.assertEqual(frozen, json.loads(self.freeze_path.read_text()))
        self.assertFalse(self.target.exists())
        self.mock_target()
        scored_stdout = io.StringIO()
        original = reproduce.RETAINED / "third_party" / "nlb_tools_0_0_3" / "evaluation.py"
        with redirect_stdout(scored_stdout):
            reproduce.main(["score", *arguments, "--freeze", str(self.freeze_path),
                "--target", str(self.target), "--target-sha256", reproduce.source.TARGET_SHA256,
                "--scorer-source", str(original), "--scratch-root", str(self.scratch),
                "--scratch-budget-bytes", str(2 * 1024 * 1024), "--output", str(self.score_path)])
        scored = json.loads(scored_stdout.getvalue())
        self.assertEqual(scored, json.loads(self.score_path.read_text()))
        self.assertEqual(len(scored["findings"]), 8)
        self.assertEqual(scored["submission_sha256"], frozen["submission_sha256"])
        self.assertEqual(scored["scientific_outcome"], "unknown")

    def test_official_evaluator_both_arms_and_independent_poisson_identities(self):
        """Actually executes unchanged scorer; expected likelihood is independent."""
        rng = np.random.default_rng(992)
        with h5py.File(self.target, "w") as handle:
            group = handle.create_group(reproduce.source.DATASET)
            group.create_dataset("eval_spikes_heldout", data=rng.poisson(0.8, (4, 35, 45)))
            group.create_dataset("eval_spikes_heldin_forward", data=rng.poisson(0.8, (4, 10, 137)))
            group.create_dataset("eval_spikes_heldout_forward", data=rng.poisson(0.8, (4, 10, 45)))
            group.create_dataset("train_behavior", data=rng.normal(size=(6, 35, 2)))
            group.create_dataset("eval_behavior", data=rng.normal(size=(4, 35, 2)))
            group.create_dataset("psth", data=rng.uniform(0.1, 3, (108, 35, 182)))
            conditions = group.create_dataset("eval_cond_idx", (108,), dtype=h5py.vlen_dtype(np.dtype("int64")))
            for index in range(108):
                conditions[index] = np.array([index] if index < 4 else [], dtype=np.int64)
        self.charge(self.target)
        self.use_patch(reproduce.source, "TARGET_SHA256", digest(self.target))
        self.freeze()
        original = reproduce.RETAINED / "third_party" / "nlb_tools_0_0_3" / "evaluation.py"
        self.assertEqual(digest(original), reproduce.source.SCORER_SHA256)
        report = self.score(original)
        self.assertEqual(len(report["findings"]), 8)
        self.assertEqual({row["id"] for row in report["findings"]}, {
            arm + "_" + suffix for arm in reproduce.ARMS
            for suffix in ("co_bps", "velocity_r2", "psth_r2", "forward_bps")})
        self.assertEqual(report["scientific_outcome"], "unknown")
        self.assertEqual(report["target_exposure"], reproduce.EXPOSURE)
        self.assertNotIn(str(self.target), self.score_path.read_text())
        with h5py.File(self.target, "r") as targets:
            target = targets[reproduce.source.DATASET]
            co_counts = target["eval_spikes_heldout"][()].astype(float)
            future_counts = np.concatenate([target["eval_spikes_heldin_forward"][()],
                                            target["eval_spikes_heldout_forward"][()]], axis=2).astype(float)
        for arm in reproduce.ARMS:
            with h5py.File(self.predictions[arm], "r") as predictions:
                pred = predictions[reproduce.source.DATASET]
                co_rates = pred["eval_rates_heldout"][()].astype(float)
                future_rates = np.concatenate([pred["eval_rates_heldin_forward"][()],
                                              pred["eval_rates_heldout_forward"][()]], axis=2).astype(float)
            for name, counts, rates in (("co-bps", co_counts, co_rates), ("fp-bps", future_counts, future_rates)):
                means = counts.mean(axis=(0, 1), keepdims=True)
                expected = np.sum(counts * np.log(rates / means) + means - rates) / counts.sum() / np.log(2)
                self.assertAlmostEqual(report["metrics"][arm][name], expected, places=11)
            for finding in [row for row in report["findings"] if row["arm"] == arm]:
                self.assertEqual(finding["published"], reproduce.source.PUBLISHED[arm][finding["metric"]])
                self.assertAlmostEqual(finding["signed_difference"], finding["observed"] - finding["published"], places=14)
                self.assertEqual(finding["scientific_outcome"], "unknown")
        self.assertNotEqual(report["metrics"]["causal"]["co-bps"], report["metrics"]["noncausal"]["co-bps"])


class ProductionBindingsTests(unittest.TestCase):
    def test_exact_retained_sources_and_reproduction_contract(self):
        ORIGINAL_VERIFY_SOURCES()
        self.assertEqual(reproduce.source.REFERENCE_PANEL, reproduce.RETAINED / "reference_panel.json")
        panel = json.loads(reproduce.source.REFERENCE_PANEL.read_text())
        self.assertEqual((panel["n_train"], panel["n_eval"], panel["n_heldin"], panel["n_heldout"]), (2295, 574, 137, 45))


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print("KNOWN_GENERATED_FIXTURE_BYTES=" + str(KNOWN_FIXTURE_BYTES))
