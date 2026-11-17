"""Independent generated controls for continuous SMC benchmark interfaces.

All observations and predictions here are generated. A single shared, immutable
tiny material pair limits test writes. Original source input admission, paired
export/inspection, prediction validation and the pinned evaluator remain real.
Only reference/PDF/code identities are replaced by explicit generated fixtures.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager, redirect_stdout
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


SPEC = importlib.util.spec_from_file_location("smc_continuous_independent_tests", Path(__file__).with_name("benchmark.py"))
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)
KNOWN_WRITTEN_BYTES = 0


def charge(value):
    global KNOWN_WRITTEN_BYTES
    KNOWN_WRITTEN_BYTES += value


def write_bytes(path, data):
    Path(path).write_bytes(data)
    charge(len(data))


def write_json(path, data):
    write_bytes(path, (json.dumps(data, sort_keys=True, allow_nan=False) + "\n").encode())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def preserve(*paths):
    saved = {Path(path): Path(path).read_bytes() for path in paths}
    try:
        yield
    finally:
        for path, body in saved.items():
            write_bytes(path, body)


class ContinuousTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.inputs = cls.root / "inputs"
        cls.inputs.mkdir()
        cls.author = cls.root / "author"
        cls.author.mkdir()
        cls.operator = cls.root / "operator"
        cls.operator.mkdir()
        cls.submitted = cls.root / "submitted"
        cls.submitted.mkdir()
        cls.task = cls.root / "registered_task.json"
        write_json(cls.task, {"id": benchmark.TASK_ID, "generated_fixture": True,
            "continuous_outcomes_v1": {"version": 1, "policy_sha256": benchmark.POLICY_SHA256,
                "entrypoint": "implementations/continuous-outcomes-v1/benchmark.py"}})
        cls.task_sha = sha(cls.task)
        cls.budget = {outcome: {"cpu_seconds": 120, "wall_seconds": 180, "memory_bytes": 536870912, "threads": 1}
                      for outcome in ("reproduction", "improvement")}
        cls.budget_path = cls.root / "budget.json"
        write_json(cls.budget_path, cls.budget)
        cls.paper = cls.root / "paper.pdf"
        write_bytes(cls.paper, b"%PDF-1.4 generated test publication, no real paper text\n")
        write_bytes(cls.author / "LICENSE", b"Generated official-code license fixture\n")
        write_bytes(cls.author / "method.py", b"# Generated official-code fixture\n")
        (cls.author / "vi_rnn").mkdir()
        write_bytes(cls.author / "vi_rnn/__init__.py", b"")
        cls.code_manifest = cls.root / "source_manifest.json"
        write_json(cls.code_manifest, {"schema": "generated_source_fixture", "source_commit": benchmark.source.AUTHOR_COMMIT,
            "source_repo": "https://example.invalid/generated-only", "license": "generated",
            "files": [{"path": name, "role": "source", "bytes": (cls.author / name).stat().st_size,
                       "sha256": sha(cls.author / name)} for name in ("LICENSE", "method.py", "vi_rnn/__init__.py")]})
        cls.panels = {}
        for phase, n_train, n_eval in (("val", 4, 2), ("test", 6, 4)):
            cls.panels[phase] = cls.make_phase(phase, n_train, n_eval)
        for owner, name, value in (
            (benchmark.retained, "REFERENCE_TEST", cls.inputs / "mc_maze/test/panel.json"),
            (benchmark.retained, "REFERENCE_VAL", cls.inputs / "mc_maze/val/panel.json"),
            (benchmark.retained, "PAPER_SHA256", sha(cls.paper)),
            (benchmark.retained, "SOURCE_MANIFEST", cls.code_manifest),
            (benchmark.source, "REFERENCE_PANEL", cls.inputs / "mc_maze/test/panel.json"),
            (benchmark.retained.contract, "REFERENCE_PANEL", cls.inputs / "mc_maze/test/panel.json"),
        ):
            manager = patch.object(owner, name, value)
            manager.start()
            cls.addClassCleanup(manager.stop)
        cls.pair_root = cls.root / "pair"
        benchmark.export_pair(cls.inputs, cls.author, cls.paper, cls.task, cls.task_sha,
            cls.budget_path, cls.pair_root, max_bytes=8 * 1024**2, reserve_bytes=0)
        charge(sum(path.stat().st_size for path in cls.pair_root.rglob("*") if path.is_file()))
        cls.pair_path = cls.pair_root / "pair_manifest.json"
        cls.pair_sha = sha(cls.pair_path)
        cls.predictions = {}
        for index, key in enumerate(("causal", "noncausal", "offline")):
            path = cls.submitted / (key + ".h5")
            rng = np.random.default_rng(940 + index)
            with h5py.File(path, "w") as handle:
                group = handle.create_group(benchmark.source.DATASET)
                for name in sorted(benchmark.source.REQUIRED_KEYS):
                    group.create_dataset(name, data=rng.uniform(0.1, 3, cls.panels["test"]["expected_shapes"][name]).astype(np.float32))
            charge(path.stat().st_size)
            cls.predictions[key] = path

    @classmethod
    def make_phase(cls, phase, n_train, n_eval):
        root = cls.inputs / "mc_maze" / phase
        root.mkdir(parents=True)
        rng = np.random.default_rng(911 if phase == "val" else 912)
        panel = {"schema": "smc_nlb_panel_v1", "dataset": benchmark.source.DATASET, "phase": phase,
            "source_commit": benchmark.source.AUTHOR_COMMIT, "dandiset": "000128", "dandi_version": "0.220113.0400",
            "bin_ms": 20, "n_train": n_train, "n_eval": n_eval, "n_bins": 35, "forward_bins": 10,
            "n_heldin": 137, "n_heldout": 45, "condition_count": 108,
            "trial_indices_sha256": "1" * 64, "neuron_indices_sha256": "2" * 64, "conditions_sha256": "3" * 64,
            "tensor_trial_indices_sha256": "4" * 64, "condition_membership_sha256": "5" * 64,
            "split_counts": {"train": 4, "val": 2, "test": 4},
            "nwb_sources": [{"name": "generated_fixture", "sha256": "6" * 64}],
            "inputs_sha256": {}, "input_content_sha256": {}}
        panel["expected_shapes"] = {key: [n_train if key.startswith("train_") else n_eval,
            10 if key.endswith("_forward") else 35, 137 if "heldin" in key else 45]
            for key in benchmark.source.RATE_KEYS}
        for filename in ("train_input_20ms.h5", "eval_input_20ms.h5"):
            train = filename.startswith("train_")
            names = benchmark.retained.TRAIN_KEYS if train else ({"eval_spikes_heldin", "eval_spikes_heldout"}
                if phase == "val" else {"eval_spikes_heldin"})
            with h5py.File(root / filename, "w") as handle:
                for name in sorted(names):
                    shape = (n_train if train else n_eval, 10 if name.endswith("_forward") else 35,
                             2 if name == "train_behavior" else 45 if "heldout" in name else 137)
                    values = rng.normal(size=shape).astype(np.float32) if name == "train_behavior" else rng.poisson(0.8, shape).astype(np.int16)
                    item = handle.create_dataset(name, data=values)
                    panel["input_content_sha256"][filename + ":" + name] = benchmark.retained.canonical_content_hash(item)
            charge((root / filename).stat().st_size)
            panel["inputs_sha256"][filename] = sha(root / filename)
        if phase == "val":
            target = root / "eval_target_20ms.h5"
            cls.make_target(target, n_train, n_eval, 997)
            panel["validation_target_sha256"] = sha(target)
            with h5py.File(target, "r") as handle:
                panel["validation_target_shapes"] = {name: list(handle[benchmark.source.DATASET][name].shape)
                    for name in benchmark.retained.VAL_TARGET_KEYS}
        write_json(root / "panel.json", panel)
        return panel

    @classmethod
    def make_target(cls, path, n_train, n_eval, seed):
        rng = np.random.default_rng(seed)
        with h5py.File(path, "w") as handle:
            group = handle.create_group(benchmark.source.DATASET)
            for name, shape in (("eval_spikes_heldout", (n_eval, 35, 45)),
                                ("eval_spikes_heldin_forward", (n_eval, 10, 137)),
                                ("eval_spikes_heldout_forward", (n_eval, 10, 45))):
                group.create_dataset(name, data=rng.poisson(0.8, shape).astype(np.int16))
            group.create_dataset("train_behavior", data=rng.normal(size=(n_train, 35, 2)))
            group.create_dataset("eval_behavior", data=rng.normal(size=(n_eval, 35, 2)))
            group.create_dataset("psth", data=rng.uniform(0.1, 3, (1, 35, 182)))
            for name, count in (("eval_cond_idx", n_eval), ("train_cond_idx", n_train)):
                item = group.create_dataset(name, (1,), dtype=h5py.vlen_dtype(np.dtype("int64")))
                item[0] = np.arange(count, dtype=np.int64)
        charge(Path(path).stat().st_size)

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix="case-", dir=self.operator))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.case))
        self.target = self.case / "target.h5"
        self.result = self.case / "result.json"
        self.frozen = self.case / "frozen.json"
        self.declaration_path = self.case / "declaration.json"
        self.evaluator = benchmark.RETAINED / "third_party/nlb_tools_0_0_3/evaluation.py"
        self.condition = "paper_data"

    def inspect(self, pair_hash=None):
        return benchmark.inspect_pair(self.pair_path, pair_hash or self.pair_sha, self.task, self.task_sha,
                                      max_bytes=8 * 1024**2)

    def declaration(self, outcome, role="construction_control"):
        keys = ("causal", "noncausal") if outcome == "reproduction" else ("offline",)
        return {"schema": "smc_continuous_submission_declaration_v1", "role": role,
            "method_id": "generated-control-only", "outcome": outcome, "condition": self.condition,
            "methods": {key: {"source_sha256": "7" * 64, "seed": 17,
                "recipe": {"particles": 192, "repeats": 32, "smooth": False} if outcome == "reproduction" and role == "participant" else None,
                "behavior_guided_fitting": False, "behavior_guided_selection": False} for key in keys}}

    def freeze(self, outcome="reproduction", declaration=None, submissions=None):
        declaration = declaration or self.declaration(outcome)
        write_json(self.declaration_path, declaration)
        keys = ("causal", "noncausal") if outcome == "reproduction" else ("offline",)
        submissions = submissions if submissions is not None else {key: self.predictions[key] for key in keys}
        return benchmark.freeze(self.pair_path, self.pair_sha, self.task, self.task_sha,
            self.condition, outcome, submissions, self.declaration_path, self.frozen, max_bytes=8 * 1024**2)

    def score(self, freeze_hash=None, **overrides):
        options = {"scratch_bytes": 2 * 1024**2, "max_bytes": 8 * 1024**2}
        options.update(overrides)
        return benchmark.score(self.frozen, freeze_hash or sha(self.frozen), self.pair_path, self.pair_sha,
            self.task, self.task_sha, self.pair_root / self.condition, self.target, self.evaluator, self.result, **options)

    @contextmanager
    def mock_score(self, function=None):
        write_bytes(self.target, b"generated target stub, not neural data")
        if function is None:
            function = lambda target, prediction: [{benchmark.source.DATASET + "_split":
                {"co-bps": 0.35, "vel R2": 0.8, "psth R2": 0.5, "fp-bps": 0.2}}]
        with patch.object(benchmark.source, "TARGET_SHA256", sha(self.target)), \
             patch.object(benchmark.source, "load_original_scorer", return_value=types.SimpleNamespace(evaluate=function)):
            yield

    def test_reproduction_comparison_keeps_all_eight_independent_errors(self):
        values = {"causal": {"co-bps": 0.3, "vel R2": 0.8, "psth R2": 0.5, "fp-bps": 0.2},
                  "noncausal": {"co-bps": 0.35, "vel R2": 0.9, "psth R2": 0.6, "fp-bps": 0.25}}
        expected = {
            "causal": {"published": [0.3225, 0.8479, 0.5927, 0.2184],
                       "current": [0.3221297803678063, 0.8459605026793974, 0.5931377256416359, 0.21924211546771746]},
            "noncausal": {"published": [0.3407, 0.8902, 0.5963, 0.2417],
                          "current": [0.3410160879591172, 0.8898607459432769, 0.5958331235016836, 0.2418654447016941]},
        }
        report = benchmark.compare_metrics("reproduction", values)
        self.assertEqual(len(report["findings"]), 8)
        self.assertEqual(report["aggregation"], "none")
        self.assertEqual(report["binary_decision"], "not_applicable")
        for row in report["findings"]:
            index = list(benchmark.source.METRICS).index(row["metric"])
            pub, cur = (expected[row["arm"]][name][index] for name in ("published", "current"))
            self.assertEqual(row["published"], pub)
            self.assertEqual(row["current_release_reference"], cur)
            self.assertEqual(row["published_signed_difference"], row["observed"] - pub)
            self.assertEqual(row["current_signed_difference"], row["observed"] - cur)
            self.assertEqual(row["published_absolute_difference"], abs(row["observed"] - pub))
            self.assertEqual(row["current_absolute_difference"], abs(row["observed"] - cur))
        self.assertIsNone(report["uncertainty"]["confidence_intervals"])

    def test_improvement_selects_strongest_smc_and_exposes_companion_tradeoffs(self):
        values = {"co-bps": 0.35, "vel R2": 0.8, "psth R2": 0.5, "fp-bps": 0.2}
        report = benchmark.compare_metrics("improvement", {"offline": values})
        self.assertEqual(report["selected_smc_reference_id"], "current_release_noncausal")
        self.assertAlmostEqual(report["method_specific_smc_co_bps_difference"], 0.35 - 0.3410160879591172, places=14)
        self.assertAlmostEqual(report["source_paper_NDT_co_bps_difference"], 0.35 - 0.3597, places=14)
        self.assertEqual(len(report["comparisons"]), 6)
        for row in report["comparisons"]:
            self.assertEqual(set(row["signed_differences"]), set(benchmark.source.METRICS))
            self.assertEqual(set(row["negative_companion_differences"]), {"vel R2", "psth R2", "fp-bps"})
        self.assertEqual(report["binary_decision"], "not_applicable")
        self.assertNotIn("pass", report)

    def test_incomplete_nonfinite_metrics_and_untyped_budgets_fail(self):
        for value in (float("nan"), float("inf"), True):
            metrics = dict(zip(benchmark.source.METRICS, [value, 0.8, 0.6, 0.2]))
            with self.subTest(value=value), self.assertRaises(ValueError):
                benchmark.compare_metrics("improvement", {"offline": metrics})
        with self.assertRaises(ValueError):
            benchmark.compare_metrics("reproduction", {"causal": dict(zip(benchmark.source.METRICS, [0.3, 0.8, 0.6, 0.2]))})
        for outcome in ("reproduction", "improvement"):
            for change in ({"threads": True}, {"cpu_seconds": 0}, {"memory_bytes": 1.5}, {"extra": 1}):
                altered = copy.deepcopy(self.budget)
                altered[outcome].update(change)
                with self.subTest(outcome=outcome, change=change), self.assertRaises(ValueError):
                    benchmark.validate_budget(altered)
        with self.assertRaises(ValueError):
            benchmark.validate_budget({"reproduction": self.budget["reproduction"]})

    def test_actual_prepare_and_inspect_deliver_only_declared_shared_inputs(self):
        admission = self.inspect()
        self.assertTrue(admission["materials_valid"])
        self.assertTrue(admission["episode_budget_declared"])
        self.assertFalse(admission["execution_verified"])
        self.assertFalse(admission["AI_result"])
        pair = admission["pair"]
        self.assertEqual(pair["resource_budget"], self.budget)
        self.assertEqual(pair["code_condition_additions"], ["official_source/LICENSE", "official_source/method.py",
                         "official_source/vi_rnn/__init__.py", "official_source_manifest.json"])
        self.assertEqual((self.pair_root / "paper_data_author_code/official_source/vi_rnn/__init__.py").read_bytes(), b"")
        for relative in pair["shared_files"]:
            self.assertEqual((self.pair_root / "paper_data" / relative).read_bytes(),
                             (self.pair_root / "paper_data_author_code" / relative).read_bytes())
        self.assertFalse((self.pair_root / "paper_data/official_source").exists())
        self.assertFalse((self.pair_root / "paper_data/inputs/mc_maze/test/eval_target_20ms.h5").exists())
        self.assertTrue((self.pair_root / "paper_data/inputs/mc_maze/val/eval_target_20ms.h5").is_file())

    def test_old_pair_schema_cannot_be_relabelled_as_continuous_materials(self):
        with preserve(self.pair_path):
            pair = json.loads(self.pair_path.read_text())
            pair["schema"] = "smc_offline_paired_delivery_v1"
            write_json(self.pair_path, pair)
            with self.assertRaisesRegex(ValueError, "obsolete or wrong paired materials"):
                self.inspect(sha(self.pair_path))

    def test_actual_file_mutation_and_symlink_refuse_inspection(self):
        path = self.pair_root / "paper_data/paper.pdf"
        with preserve(path):
            write_bytes(path, b"changed fixture")
            with self.assertRaisesRegex(ValueError, "bound inventory"):
                self.inspect()
        link = self.pair_root / "unexpected-link"
        link.symlink_to(path)
        try:
            with self.assertRaisesRegex(ValueError, "symlink or special file"):
                self.inspect()
        finally:
            link.unlink()

    def test_rehashed_extra_payload_is_rejected_by_exact_allowlist(self):
        manifests = [self.pair_root / condition / "delivery_manifest.json" for condition in benchmark.CONDITIONS]
        extras = [self.pair_root / condition / "operator-predictions.h5" for condition in benchmark.CONDITIONS]
        with preserve(self.pair_path, *manifests):
            try:
                pair = json.loads(self.pair_path.read_text())
                for condition, manifest, extra in zip(benchmark.CONDITIONS, manifests, extras):
                    write_bytes(extra, b"forbidden generated payload")
                    doc = json.loads(manifest.read_text())
                    doc["files"].append({"path": extra.name, "bytes": extra.stat().st_size, "sha256": sha(extra)})
                    write_json(manifest, doc)
                    pair["condition_manifest_sha256"][condition] = sha(manifest)
                pair["shared_files"][extras[0].name] = sha(extras[0])
                write_json(self.pair_path, pair)
                with self.assertRaisesRegex(ValueError, "explicit participant allowlist"):
                    self.inspect(sha(self.pair_path))
            finally:
                for extra in extras:
                    if extra.exists():
                        extra.unlink()

    def test_both_reproduction_and_single_offline_freezes_are_target_blind(self):
        record = self.freeze()
        self.assertEqual(set(record["submissions"]), {"causal", "noncausal"})
        self.assertFalse(record["target_accessed"])
        self.assertFalse(record["AI_attribution_verified"])
        self.assertFalse(self.target.exists())
        self.frozen = self.case / "offline.json"
        record = self.freeze("improvement")
        self.assertEqual(set(record["submissions"]), {"offline"})
        self.assertFalse(record["execution_verified"])
        self.assertFalse(self.target.exists())

    def test_missing_arm_and_wrong_declaration_cannot_enter_freeze(self):
        with self.assertRaisesRegex(ValueError, "frozen together"):
            self.freeze(submissions={"causal": self.predictions["causal"]})
        declaration = self.declaration("reproduction", role="participant")
        declaration["methods"]["noncausal"]["recipe"]["repeats"] = 1
        with self.assertRaisesRegex(ValueError, "original source recipe"):
            self.freeze(declaration=declaration)
        declaration = self.declaration("reproduction")
        declaration["methods"]["noncausal"]["behavior_guided_fitting"] = None
        with self.assertRaisesRegex(ValueError, "behavior-guided"):
            self.freeze(declaration=declaration)
        self.assertFalse(self.frozen.exists())

    def test_changed_prediction_and_embedded_claims_fail_before_target(self):
        record = self.freeze()
        with preserve(self.predictions["noncausal"]):
            write_bytes(self.predictions["noncausal"], b"changed generated prediction")
            with self.assertRaises(ValueError):
                self.score()
        self.assertFalse(self.target.exists())
        for key in ("execution_verified", "AI_attribution_verified", "target_accessed"):
            with self.subTest(key=key):
                write_json(self.frozen, {**record, key: True})
                with self.assertRaisesRegex(ValueError, "unsupported provenance"):
                    self.score()
        write_json(self.frozen, {**record, "declaration": {**record["declaration"], "role": "author_calibration"}})
        with self.assertRaisesRegex(ValueError, "declaration schema"):
            self.score()
        self.assertFalse(self.target.exists())

    def test_second_arm_failure_never_emits_partial_report(self):
        self.freeze()
        calls = []
        def fail_second(target, prediction):
            calls.append(Path(prediction).stem)
            if len(calls) == 2:
                raise RuntimeError("generated second-arm failure")
            return [{benchmark.source.DATASET + "_split": dict(zip(benchmark.source.METRICS, [0.3, 0.8, 0.6, 0.2]))}]
        with self.mock_score(fail_second):
            with self.assertRaisesRegex(RuntimeError, "second-arm failure"):
                self.score()
        self.assertEqual(calls, ["causal", "noncausal"])
        self.assertFalse(self.result.exists())
        self.assertEqual(list(self.case.glob(".smc-continuous-score-*")), [])

    def test_improvement_score_keeps_role_behavior_and_continuous_tradeoffs(self):
        self.freeze("improvement")
        with self.mock_score():
            report = self.score()
        self.assertEqual(report["role"], "construction_control")
        self.assertFalse(report["AI_attribution_verified"])
        self.assertEqual(report["binary_decision"], "not_applicable")
        self.assertEqual(len(report["comparisons"]), 6)
        self.assertEqual(report["target_exposure"], "public_original_test_targets_released_2026_01")
        self.assertFalse(report["declaration"]["methods"]["offline"]["behavior_guided_fitting"])

    def test_all_complete_snapshots_precede_first_target_read(self):
        self.freeze()
        original_hash = benchmark.hash_file
        observed = []
        def watch(path, limit=benchmark.io.MAX_JSON_BYTES):
            if Path(path) == self.target:
                files = sorted(self.case.glob(".smc-continuous-score-*/*.h5"))
                self.assertEqual([path.name for path in files], ["causal.h5", "noncausal.h5"])
                observed.append(str(path))
            return original_hash(path, limit)
        with self.mock_score(), patch.object(benchmark, "hash_file", side_effect=watch):
            report = self.score()
        self.assertEqual(len(observed), 2)
        self.assertEqual(len(report["findings"]), 8)

    def test_complete_snapshot_budget_and_nonoverwriting_result(self):
        self.freeze()
        with self.assertRaises(ValueError):
            self.score(scratch_bytes=1)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.result.exists())
        write_bytes(self.result, b"previous result")
        with self.assertRaisesRegex(ValueError, "output already exists"):
            self.score()
        self.assertEqual(self.result.read_bytes(), b"previous result")

    def test_paired_budget_task_selector_and_export_capacity_are_enforced(self):
        obsolete = self.case / "old-task.json"
        write_json(obsolete, {"id": benchmark.TASK_ID})
        with self.assertRaisesRegex(ValueError, "has not selected"):
            benchmark.current_task(obsolete, sha(obsolete))
        with self.assertRaisesRegex(ValueError, "prepared inputs exceed export byte bound"):
            benchmark.export_pair(self.inputs, self.author, self.paper, self.task, self.task_sha,
                self.budget_path, self.case / "too-small", max_bytes=1, reserve_bytes=0)
        self.assertFalse((self.case / "too-small").exists())
        with self.assertRaisesRegex(ValueError, "bound"):
            benchmark.inspect_pair(self.pair_path, self.pair_sha, self.task, self.task_sha, max_bytes=1)

    def test_original_evaluator_produces_all_eight_measurements(self):
        self.make_target(self.target, 6, 4, 1134)
        self.freeze()
        with patch.object(benchmark.source, "TARGET_SHA256", sha(self.target)):
            report = self.score()
        self.assertEqual(len(report["findings"]), 8)
        self.assertEqual(report["binary_decision"], "not_applicable")
        with h5py.File(self.target, "r") as handle:
            counts = handle[benchmark.source.DATASET]["eval_spikes_heldout"][()].astype(float)
        baseline = counts.mean(axis=(0, 1), keepdims=True)
        for arm in ("causal", "noncausal"):
            with h5py.File(self.predictions[arm], "r") as handle:
                rates = handle[benchmark.source.DATASET]["eval_rates_heldout"][()].astype(float)
            expected = np.sum(counts * np.log(rates / baseline) + baseline - rates) / counts.sum() / np.log(2)
            self.assertAlmostEqual(report["metrics"][arm]["co-bps"], expected, places=11)
        self.assertFalse(report["execution_verified"])
        self.assertFalse(report["AI_attribution_verified"])

    def test_actual_cli_inspect_freeze_score(self):
        self.pair_root = self.case / "cli-pair"
        stream = io.StringIO()
        with redirect_stdout(stream):
            benchmark.main(["prepare", "--task", str(self.task), "--task-sha256", self.task_sha,
                "--max-bytes", str(8 * 1024**2), "--prepared-root", str(self.inputs),
                "--author-source", str(self.author), "--paper", str(self.paper),
                "--budget", str(self.budget_path), "--output", str(self.pair_root), "--reserve-bytes", "0"])
        self.pair_path = self.pair_root / "pair_manifest.json"
        self.pair_sha = sha(self.pair_path)
        self.assertEqual(json.loads(stream.getvalue()), json.loads(self.pair_path.read_text()))
        charge(sum(path.stat().st_size for path in self.pair_root.rglob("*") if path.is_file()))
        shared = ["--task", str(self.task), "--task-sha256", self.task_sha,
            "--max-bytes", str(8 * 1024**2), "--pair", str(self.pair_path), "--pair-sha256", self.pair_sha]
        stream = io.StringIO()
        with redirect_stdout(stream):
            benchmark.main(["inspect", *shared])
        self.assertTrue(json.loads(stream.getvalue())["materials_valid"])
        write_json(self.declaration_path, self.declaration("improvement"))
        stream = io.StringIO()
        with redirect_stdout(stream):
            benchmark.main(["freeze", *shared, "--condition", self.condition, "--outcome", "improvement",
                "--submission", "offline=" + str(self.predictions["offline"]),
                "--declaration", str(self.declaration_path), "--output", str(self.frozen)])
        self.assertEqual(set(json.loads(stream.getvalue())["submissions"]), {"offline"})
        stream = io.StringIO()
        with self.mock_score(), redirect_stdout(stream):
            benchmark.main(["score", *shared, "--frozen", str(self.frozen), "--frozen-sha256", sha(self.frozen),
                "--condition-root", str(self.pair_root / self.condition), "--target", str(self.target),
                "--evaluator", str(self.evaluator), "--output", str(self.result), "--scratch-bytes", str(2 * 1024**2)])
        report = json.loads(stream.getvalue())
        self.assertEqual(report, json.loads(self.result.read_text()))
        self.assertEqual(report["binary_decision"], "not_applicable")

    def test_production_policy_and_reference_report_are_exact(self):
        policy = benchmark.load_policy()
        self.assertEqual(sha(benchmark.HERE / "policy.json"), benchmark.POLICY_SHA256)
        self.assertEqual(sha(benchmark.CALIBRATION_REPORT), benchmark.CALIBRATION_SHA256)
        self.assertIsNone(policy["outcomes"]["reproduction"]["numeric_tolerance"])
        self.assertEqual(policy["uncertainty"]["target_resampling"], "not_allowed")
        self.assertEqual(policy["outcomes"]["improvement"]["selected_smc_reference_id"], "current_release_noncausal")

    def test_rehashed_pair_condition_panel_and_attribution_metadata_fail(self):
        manifests = [self.pair_root / condition / "delivery_manifest.json" for condition in benchmark.CONDITIONS]
        panels = [self.pair_root / condition / "inputs/mc_maze/test/panel.json" for condition in benchmark.CONDITIONS]
        attributions = [self.pair_root / condition / "attribution.json" for condition in benchmark.CONDITIONS]
        def rehash():
            pair = json.loads(self.pair_path.read_text())
            for condition, manifest in zip(benchmark.CONDITIONS, manifests):
                doc = json.loads(manifest.read_text())
                for row in doc["files"]:
                    path = self.pair_root / condition / row["path"]
                    row["bytes"], row["sha256"] = path.stat().st_size, sha(path)
                write_json(manifest, doc)
                pair["condition_manifest_sha256"][condition] = sha(manifest)
                if condition == "paper_data":
                    pair["shared_files"] = {row["path"]: row["sha256"] for row in doc["files"]}
            write_json(self.pair_path, pair)
        for kind, message in (("pair", "unexpected paired metadata"), ("condition", "unexpected condition metadata"),
                              ("panel", "undeclared metadata"), ("attribution", "attribution metadata differs")):
            with self.subTest(kind=kind), preserve(self.pair_path, *manifests, *panels, *attributions):
                paths = [self.pair_path] if kind == "pair" else manifests if kind == "condition" else panels if kind == "panel" else attributions
                for path in paths:
                    doc = json.loads(path.read_text())
                    doc["undeclared_generated_metadata"] = True
                    write_json(path, doc)
                rehash()
                with self.assertRaisesRegex(ValueError, message):
                    self.inspect(sha(self.pair_path))

    def test_embedded_digest_output_custody_and_native_metadata_bound(self):
        record = self.freeze()
        changed = copy.deepcopy(record)
        changed["declaration"]["method_id"] = "changed-but-otherwise-valid-method"
        write_json(self.frozen, changed)
        with self.assertRaisesRegex(ValueError, "embedded declaration differs"):
            self.score()
        write_json(self.frozen, record)
        outside = self.frozen
        self.frozen = self.pair_root / "paper_data/forbidden-freeze.json"
        try:
            with self.assertRaisesRegex(ValueError, "outside paired participant materials"):
                self.freeze()
            self.assertFalse(self.frozen.exists())
        finally:
            self.frozen = outside
        self.result = self.pair_root / "paper_data/forbidden-result.json"
        with self.assertRaisesRegex(ValueError, "outside paired participant materials"):
            self.score()
        self.assertFalse(self.result.exists())
        source_panel = self.inputs / "mc_maze/test/panel.json"
        with preserve(source_panel), patch.object(benchmark.retained, "admitted_phase") as admission:
            write_bytes(source_panel, b" " * (benchmark.io.MAX_JSON_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "byte bound"):
                benchmark.export_pair(self.inputs, self.author, self.paper, self.task, self.task_sha,
                    self.budget_path, self.case / "oversized-native", max_bytes=8 * 1024**2, reserve_bytes=0)
            admission.assert_not_called()
        self.assertFalse((self.case / "oversized-native").exists())
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print("KNOWN_GENERATED_WRITES_LOWER_BOUND=" + str(KNOWN_WRITTEN_BYTES))
