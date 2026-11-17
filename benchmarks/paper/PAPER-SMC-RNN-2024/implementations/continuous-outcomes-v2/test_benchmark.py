"""Independent generated controls for official-assets SMC benchmark access.

All observations and predictions here are generated. A single shared, immutable
tiny material pair limits test writes. Original source input admission, paired
export/inspection, prediction validation and the pinned evaluator remain real.
Only fixture identities are replaced; the policy's scientific vectors remain
unchanged. All ten asset payloads are short opaque NONPICKLE bytes. No authentic
asset is read, loaded or deserialized. Historical version-one files are untouched.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
import pickle
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np


SPEC = importlib.util.spec_from_file_location("smc_official_assets_independent_tests", Path(__file__).with_name("benchmark.py"))
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


class AssetAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.production_policy_path = benchmark.POLICY_PATH
        cls.production_asset_path = benchmark.ASSET_ALLOWLIST
        cls.production_policy_sha = benchmark.POLICY_SHA256
        cls.production_asset_sha = benchmark.ASSET_SHA256
        cls.production_source_manifest = benchmark.retained.SOURCE_MANIFEST
        cls.production_source_manifest_sha = benchmark.SOURCE_PINS["source_manifest.json"]
        cls.production_policy = benchmark.load_policy()
        cls.production_assets = benchmark.asset_allowlist()
        cls.inputs = cls.root / "inputs"
        cls.inputs.mkdir()
        cls.author = cls.root / "author"
        cls.author.mkdir()
        cls.operator = cls.root / "operator"
        cls.operator.mkdir()
        cls.submitted = cls.root / "submitted"
        cls.submitted.mkdir()
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
        cls.assets = copy.deepcopy(cls.production_assets)
        for index, row in enumerate(cls.assets["files"]):
            path = cls.author / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            body = b"\x00NONPICKLE generated opaque asset " + str(index).encode() + b"\n"
            write_bytes(path, body)
            row["bytes"] = len(body)
            row["sha256"] = sha(path)
            row["git_blob_sha1"] = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        cls.assets["total_asset_bytes"] = sum(row["bytes"] for row in cls.assets["files"])
        cls.asset_path = cls.root / "asset_allowlist.json"
        write_json(cls.asset_path, cls.assets)
        cls.policy = copy.deepcopy(cls.production_policy)
        cls.policy["official_assets"]["allowlist_sha256"] = sha(cls.asset_path)
        cls.policy["official_assets"]["total_asset_bytes"] = cls.assets["total_asset_bytes"]
        cls.policy_path = cls.root / "policy.json"
        write_json(cls.policy_path, cls.policy)
        cls.code_manifest = cls.root / "source_manifest.json"
        write_json(cls.code_manifest, {"schema": "generated_source_fixture", "source_commit": benchmark.source.AUTHOR_COMMIT,
            "source_repo": "https://example.invalid/generated-only", "license": "generated",
            "files": [{"path": name, "role": "source", "bytes": (cls.author / name).stat().st_size,
                       "sha256": sha(cls.author / name)} for name in ("LICENSE", "method.py", "vi_rnn/__init__.py")]
                    + [{key: row[key] for key in ("path", "role", "bytes", "sha256")} for row in cls.assets["files"]]})
        cls.panels = {}
        for phase, n_train, n_eval in (("val", 4, 2), ("test", 6, 4)):
            cls.panels[phase] = cls.make_phase(phase, n_train, n_eval)
        for owner, name, value in (
            (benchmark.retained, "REFERENCE_TEST", cls.inputs / "mc_maze/test/panel.json"),
            (benchmark.retained, "REFERENCE_VAL", cls.inputs / "mc_maze/val/panel.json"),
            (benchmark.retained, "PAPER_SHA256", sha(cls.paper)),
            (benchmark.retained, "SOURCE_MANIFEST", cls.code_manifest),
            (benchmark, "POLICY_PATH", cls.policy_path),
            (benchmark, "POLICY_SHA256", sha(cls.policy_path)),
            (benchmark, "ASSET_ALLOWLIST", cls.asset_path),
            (benchmark, "ASSET_SHA256", sha(cls.asset_path)),
            (benchmark.source, "REFERENCE_PANEL", cls.inputs / "mc_maze/test/panel.json"),
            (benchmark.retained.contract, "REFERENCE_PANEL", cls.inputs / "mc_maze/test/panel.json"),
        ):
            manager = patch.object(owner, name, value)
            manager.start()
            cls.addClassCleanup(manager.stop)
        manager = patch.dict(benchmark.SOURCE_PINS, {"source_manifest.json": sha(cls.code_manifest)})
        manager.start()
        cls.addClassCleanup(manager.stop)
        cls.task = cls.root / "registered_task.json"
        write_json(cls.task, {"id": benchmark.TASK_ID, "generated_fixture": True,
            "continuous_outcomes_v2": {"version": 2, "policy_sha256": benchmark.POLICY_SHA256,
                "entrypoint": "implementations/continuous-outcomes-v2/benchmark.py"}})
        cls.task_sha = sha(cls.task)
        cls.pair_root = cls.root / "pair"
        with patch.object(pickle, "load", side_effect=AssertionError("assets must remain opaque")), \
             patch.object(pickle, "loads", side_effect=AssertionError("assets must remain opaque")):
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

    def usage(self, **changes):
        return [{"path": row["path"], "sha256": row["sha256"],
                 **dict.fromkeys(("loaded", "adapted", "fine_tuned", "retrained", "replaced"), False),
                 **changes} for row in self.assets["files"]]

    def inspect(self, pair_hash=None):
        return benchmark.inspect_pair(self.pair_path, pair_hash or self.pair_sha, self.task, self.task_sha,
                                      max_bytes=8 * 1024**2)

    def declaration(self, outcome, role="construction_control"):
        keys = ("causal", "noncausal") if outcome == "reproduction" else ("offline",)
        return {"schema": "smc_continuous_submission_declaration_v2", "role": role,
            "method_id": "generated-control-only", "outcome": outcome, "condition": self.condition,
            "methods": {key: {"source_sha256": "7" * 64, "seed": 17,
                "recipe": {"particles": 192, "repeats": 32, "smooth": False} if outcome == "reproduction" and role == "participant" else None,
                "behavior_guided_fitting": False, "behavior_guided_selection": False,
                "asset_usage": [] if self.condition == "paper_data" else self.usage()} for key in keys}}

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

    @contextmanager
    def manifests_preserved(self):
        paths = [self.pair_path, *(self.pair_root / condition / "delivery_manifest.json" for condition in benchmark.CONDITIONS)]
        with preserve(*paths):
            yield

    def rebind_pair_inventory(self):
        """A malicious rehasher cannot change the semantic allowlist."""
        pair = json.loads(self.pair_path.read_text())
        rows_by_condition = {}
        for condition in benchmark.CONDITIONS:
            root = self.pair_root / condition
            path = root / "delivery_manifest.json"
            manifest = json.loads(path.read_text())
            rows = [{"path": file.relative_to(root).as_posix(), "bytes": file.stat().st_size,
                     "sha256": sha(file)} for file in root.rglob("*")
                    if file.is_file() and file != path]
            rows.sort(key=lambda row: row["path"])
            rows_by_condition[condition] = {row["path"]: row for row in rows}
            manifest["files"] = rows
            write_json(path, manifest)
            pair["condition_manifest_sha256"][condition] = sha(path)
        left, right = (rows_by_condition[key] for key in benchmark.CONDITIONS)
        pair["shared_files"] = {key: value["sha256"] for key, value in left.items()}
        pair["code_condition_additions"] = sorted(set(right) - set(left))
        write_json(self.pair_path, pair)

    def asset_destination(self, index=0):
        return self.pair_root / benchmark.CONDITIONS[1] / "official_source" / self.assets["files"][index]["path"]

    def assert_rejected_after_rebind(self):
        self.rebind_pair_inventory()
        with self.assertRaises(ValueError):
            self.inspect(sha(self.pair_path))

    def test_production_metadata_and_scientific_vectors_remain_exact(self):
        with patch.object(benchmark, "POLICY_PATH", self.production_policy_path), \
             patch.object(benchmark, "POLICY_SHA256", self.production_policy_sha), \
             patch.object(benchmark, "ASSET_ALLOWLIST", self.production_asset_path), \
             patch.object(benchmark, "ASSET_SHA256", self.production_asset_sha), \
             patch.object(benchmark.retained, "SOURCE_MANIFEST", self.production_source_manifest), \
             patch.dict(benchmark.SOURCE_PINS, {"source_manifest.json": self.production_source_manifest_sha}):
            self.assertEqual(benchmark.load_policy(), self.production_policy)
            self.assertEqual(benchmark.asset_allowlist(), self.production_assets)
        self.assertEqual(self.production_assets["asset_count"], 10)
        self.assertEqual(self.production_assets["total_asset_bytes"], 3496380)
        restored = copy.deepcopy(self.policy)
        restored["official_assets"]["allowlist_sha256"] = self.production_asset_sha
        restored["official_assets"]["total_asset_bytes"] = 3496380
        self.assertEqual(restored, self.production_policy)
        for field in ("metrics", "smc_references", "source_paper_published_context", "outcomes", "uncertainty"):
            predecessor = json.loads((Path(__file__).parent.parent / "continuous-outcomes-v1/policy.json").read_text())
            self.assertEqual(self.production_policy[field], predecessor[field])

    def test_actual_pair_contains_ten_assets_only_in_assisted_condition(self):
        result = self.inspect()
        self.assertTrue(result["materials_valid"])
        self.assertFalse(result["AI_result"])
        self.assertEqual(result["conditions"], ["paper_data", "paper_data_author_code_and_weights"])
        self.assertEqual(result["pair"]["resource_budget"], self.budget)
        self.assertEqual(len(self.assets["files"]), 10)
        asset_metadata = self.pair_root / benchmark.CONDITIONS[1] / "official_asset_manifest.json"
        self.assertEqual(asset_metadata.read_bytes(), self.asset_path.read_bytes())
        participant_task = json.loads((self.pair_root / benchmark.CONDITIONS[1] / "task.json").read_text())
        self.assertEqual(self.pair_root / benchmark.CONDITIONS[1] / participant_task["official_assets"]["allowlist_path"],
                         asset_metadata)
        self.assertFalse((self.pair_root / "paper_data/official_asset_manifest.json").exists())
        for index, row in enumerate(self.assets["files"]):
            destination = self.asset_destination(index)
            self.assertEqual(destination.read_bytes(), (self.author / row["path"]).read_bytes())
            self.assertTrue(destination.read_bytes().startswith(b"\x00NONPICKLE"))
            self.assertFalse((self.pair_root / "paper_data/official_source" / row["path"]).exists())
        for relative in result["pair"]["shared_files"]:
            self.assertEqual((self.pair_root / benchmark.CONDITIONS[0] / relative).read_bytes(),
                             (self.pair_root / benchmark.CONDITIONS[1] / relative).read_bytes())
        self.assertFalse((self.pair_root / "paper_data/official_source").exists())
        self.assertFalse((self.pair_root / benchmark.CONDITIONS[1] / "inputs/mc_maze/test/eval_target_20ms.h5").exists())

    def test_prepare_and_inspect_never_deserialize_opaque_assets(self):
        output = self.case / "opaque-pair"
        with patch.object(pickle, "load", side_effect=AssertionError("pickle.load forbidden")), \
             patch.object(pickle, "loads", side_effect=AssertionError("pickle.loads forbidden")):
            benchmark.export_pair(self.inputs, self.author, self.paper, self.task, self.task_sha,
                self.budget_path, output, max_bytes=8 * 1024**2, reserve_bytes=0)
            benchmark.inspect_pair(output / "pair_manifest.json", sha(output / "pair_manifest.json"),
                self.task, self.task_sha, max_bytes=8 * 1024**2)
        charge(sum(path.stat().st_size for path in output.rglob("*") if path.is_file()))

    def test_missing_or_altered_source_asset_prevents_any_export(self):
        source_path = self.author / self.assets["files"][0]["path"]
        for mode in ("missing", "altered"):
            with self.subTest(mode=mode), preserve(source_path):
                if mode == "missing":
                    source_path.unlink()
                else:
                    write_bytes(source_path, b"altered opaque bytes")
                output = self.case / mode
                with self.assertRaises((ValueError, FileNotFoundError)):
                    benchmark.export_pair(self.inputs, self.author, self.paper, self.task, self.task_sha,
                        self.budget_path, output, max_bytes=8 * 1024**2, reserve_bytes=0)
                self.assertFalse(output.exists())

    def test_source_and_delivered_asset_symlinks_are_refused(self):
        source_path = self.author / self.assets["files"][0]["path"]
        destination = self.asset_destination()
        alternate = self.case / "ordinary-opaque.pkl"
        write_bytes(alternate, source_path.read_bytes())
        for path in (source_path, destination):
            with self.subTest(path=str(path)), preserve(path):
                path.unlink()
                path.symlink_to(alternate)
                try:
                    with self.assertRaises(ValueError):
                        if path == destination:
                            self.inspect()
                        else:
                            benchmark.export_pair(self.inputs, self.author, self.paper, self.task, self.task_sha,
                                self.budget_path, self.case / "symlink-export", max_bytes=8 * 1024**2, reserve_bytes=0)
                finally:
                    path.unlink()
        self.assertFalse((self.case / "symlink-export").exists())

    def test_asset_allowlist_rejects_duplicate_unknown_roles_and_source_mismatch(self):
        for change in ("duplicate", "unknown_path", "role", "sha", "size", "count"):
            with self.subTest(change=change), preserve(self.asset_path):
                doc = copy.deepcopy(self.assets)
                if change == "duplicate":
                    doc["files"][-1] = copy.deepcopy(doc["files"][0])
                elif change == "unknown_path":
                    doc["files"][0]["path"] = "models/unknown/checkpoints/unknown.pkl"
                elif change == "role":
                    doc["files"][0]["role"] = "source"
                elif change == "sha":
                    doc["files"][0]["sha256"] = "0" * 64
                elif change == "size":
                    doc["files"][0]["bytes"] += 1
                    doc["total_asset_bytes"] += 1
                else:
                    doc["asset_count"] = 9
                write_json(self.asset_path, doc)
                with patch.object(benchmark, "ASSET_SHA256", sha(self.asset_path)), self.assertRaises(ValueError):
                    benchmark.asset_allowlist()
        with preserve(self.code_manifest):
            doc = json.loads(self.code_manifest.read_text())
            next(row for row in doc["files"] if row["role"] == "checkpoint")["role"] = "source"
            write_json(self.code_manifest, doc)
            with patch.dict(benchmark.SOURCE_PINS, {"source_manifest.json": sha(self.code_manifest)}), self.assertRaises(ValueError):
                benchmark.asset_allowlist()

    def test_rehashed_missing_or_altered_delivered_asset_is_refused(self):
        destination = self.asset_destination()
        for mode in ("missing", "altered"):
            with self.subTest(mode=mode), self.manifests_preserved(), preserve(destination):
                if mode == "missing":
                    destination.unlink()
                else:
                    write_bytes(destination, b"rehashed altered asset")
                self.assert_rejected_after_rebind()

    def test_rehashed_unknown_models_and_extra_asset_paths_are_refused(self):
        for relative in ("official_source/models/unknown/model.pkl", "official_source/extra.pkl"):
            path = self.pair_root / benchmark.CONDITIONS[1] / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with self.subTest(relative=relative), self.manifests_preserved():
                write_bytes(path, b"unapproved opaque asset")
                try:
                    self.assert_rejected_after_rebind()
                finally:
                    path.unlink()

    def test_rehashed_targets_predictions_and_unassisted_assets_are_refused(self):
        cases = [((benchmark.CONDITIONS[1],), "operator-predictions.h5"),
                 (benchmark.CONDITIONS, "inputs/mc_maze/test/eval_target_20ms.h5"),
                 ((benchmark.CONDITIONS[0],), "official_source/" + self.assets["files"][0]["path"])]
        for conditions, relative in cases:
            with self.subTest(relative=relative), self.manifests_preserved():
                paths = [self.pair_root / condition / relative for condition in conditions]
                for path in paths:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    write_bytes(path, b"forbidden generated material")
                try:
                    self.assert_rejected_after_rebind()
                finally:
                    for path in paths:
                        path.unlink()

    def test_duplicate_inventory_or_rehashed_distributed_role_substitution_fails(self):
        assisted = benchmark.CONDITIONS[1]
        manifest = self.pair_root / assisted / "delivery_manifest.json"
        with self.manifests_preserved():
            doc = json.loads(manifest.read_text())
            doc["files"].append(copy.deepcopy(doc["files"][-1]))
            write_json(manifest, doc)
            pair = json.loads(self.pair_path.read_text())
            pair["condition_manifest_sha256"][assisted] = sha(manifest)
            write_json(self.pair_path, pair)
            with self.assertRaisesRegex(ValueError, "duplicate inventory"):
                self.inspect(sha(self.pair_path))
        metadata = self.pair_root / assisted / "official_source_manifest.json"
        with self.manifests_preserved(), preserve(metadata):
            doc = json.loads(metadata.read_text())
            doc["files"][0]["role"] = "checkpoint"
            write_json(metadata, doc)
            self.assert_rejected_after_rebind()
        metadata = self.pair_root / assisted / "official_asset_manifest.json"
        with self.manifests_preserved(), preserve(metadata):
            doc = json.loads(metadata.read_text())
            doc["files"][0]["role"] = "source"
            write_json(metadata, doc)
            self.assert_rejected_after_rebind()

    def test_old_schema_or_source_only_condition_cannot_be_relabelled(self):
        for key, value in (("schema", "smc_continuous_pair_v1"),
                           ("conditions", ["paper_data", "paper_data_author_code"])):
            with self.subTest(key=key), preserve(self.pair_path):
                doc = json.loads(self.pair_path.read_text())
                doc[key] = value
                write_json(self.pair_path, doc)
                with self.assertRaises(ValueError):
                    self.inspect(sha(self.pair_path))
        declaration = self.declaration("improvement")
        declaration["schema"] = "smc_continuous_submission_declaration_v1"
        with self.assertRaises(ValueError):
            benchmark.validate_declaration(declaration, "improvement", self.condition)

    def test_typed_participant_usage_tracks_each_asset_without_inferring_use(self):
        self.condition = benchmark.CONDITIONS[1]
        declaration = self.declaration("reproduction", role="participant")
        declaration["methods"]["causal"]["asset_usage"] = self.usage(loaded=True, adapted=True, fine_tuned=True)
        declaration["methods"]["noncausal"]["asset_usage"] = self.usage(retrained=True, replaced=True)
        self.assertEqual(benchmark.validate_declaration(declaration, "reproduction", self.condition), declaration)
        record = self.freeze(declaration=declaration)
        self.assertEqual(record["declaration"], declaration)
        self.assertFalse(record["execution_verified"])
        self.assertFalse(record["AI_attribution_verified"])
        self.assertFalse(record["target_accessed"])
        self.assertEqual(len(record["declaration"]["methods"]["causal"]["asset_usage"]), 10)

    def test_invalid_usage_types_dependencies_and_construction_claims_fail(self):
        self.condition = benchmark.CONDITIONS[1]
        cases = [("participant", "loaded", 1), ("participant", "adapted", True),
                 ("participant", "fine_tuned", True), ("construction_control", "loaded", True),
                 ("participant", "retrained", None)]
        for role, key, value in cases:
            declaration = self.declaration("improvement", role=role)
            declaration["methods"]["offline"]["asset_usage"][0][key] = value
            with self.subTest(role=role, key=key, value=value), self.assertRaises(ValueError):
                benchmark.validate_declaration(declaration, "improvement", self.condition)

    def test_usage_requires_complete_exact_identities_and_no_unassisted_claim(self):
        self.condition = benchmark.CONDITIONS[1]
        for mode in ("missing", "duplicate", "hash", "path", "extra_field"):
            declaration = self.declaration("improvement", role="participant")
            usage = declaration["methods"]["offline"]["asset_usage"]
            if mode == "missing":
                usage.pop()
            elif mode == "duplicate":
                usage[-1] = copy.deepcopy(usage[0])
            elif mode == "hash":
                usage[0]["sha256"] = "0" * 64
            elif mode == "path":
                usage[0]["path"] = "unknown.pkl"
            else:
                usage[0]["guessed"] = False
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                benchmark.validate_declaration(declaration, "improvement", self.condition)
        self.condition = "paper_data"
        declaration = self.declaration("improvement", role="participant")
        declaration["methods"]["offline"]["asset_usage"] = self.usage()
        with self.assertRaises(ValueError):
            benchmark.validate_declaration(declaration, "improvement", self.condition)

    def test_target_blind_freeze_requires_complete_prediction_arms(self):
        for condition in benchmark.CONDITIONS:
            self.condition = condition
            self.frozen = self.case / (condition + ".json")
            record = self.freeze()
            self.assertEqual(set(record["submissions"]), {"causal", "noncausal"})
            self.assertFalse(record["target_accessed"])
            self.assertFalse(record["execution_verified"])
            self.assertFalse(self.target.exists())
        self.frozen = self.case / "incomplete.json"
        with self.assertRaises(ValueError):
            self.freeze(submissions={"causal": self.predictions["causal"]})
        self.assertFalse(self.frozen.exists())

    def test_snapshots_gate_target_and_failed_second_arm_never_publishes(self):
        self.condition = benchmark.CONDITIONS[1]
        self.freeze()
        original_hash = benchmark.hash_file
        target_reads, calls = [], []
        def watch(path, limit=benchmark.io.MAX_JSON_BYTES):
            if Path(path) == self.target:
                files = sorted(self.case.glob(".smc-continuous-score-*/*.h5"))
                self.assertEqual([file.name for file in files], ["causal.h5", "noncausal.h5"])
                target_reads.append(str(path))
            return original_hash(path, limit)
        def fail_second(target, prediction):
            calls.append(Path(prediction).stem)
            if len(calls) == 2:
                raise RuntimeError("generated second-arm failure")
            return [{benchmark.source.DATASET + "_split": dict(zip(benchmark.source.METRICS, [0.3, 0.8, 0.6, 0.2]))}]
        with self.mock_score(fail_second), patch.object(benchmark, "hash_file", side_effect=watch):
            with self.assertRaisesRegex(RuntimeError, "second-arm failure"):
                self.score()
        self.assertEqual(calls, ["causal", "noncausal"])
        self.assertTrue(target_reads)
        self.assertFalse(self.result.exists())
        self.assertEqual(list(self.case.glob(".smc-continuous-score-*")), [])

    def test_original_evaluator_keeps_all_eight_metrics_and_opaque_usage(self):
        self.condition = benchmark.CONDITIONS[1]
        self.make_target(self.target, 6, 4, 1134)
        self.freeze()
        with patch.object(benchmark.source, "TARGET_SHA256", sha(self.target)), \
             patch.object(pickle, "load", side_effect=AssertionError("pickle.load forbidden")), \
             patch.object(pickle, "loads", side_effect=AssertionError("pickle.loads forbidden")):
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
            self.assertEqual(set(report["metrics"][arm]), set(benchmark.source.METRICS))
            self.assertEqual(report["declaration"]["methods"][arm]["asset_usage"], self.usage())
        self.assertFalse(report["execution_verified"])
        self.assertFalse(report["AI_attribution_verified"])

    def test_assisted_improvement_cli_freeze_score_preserves_usage_and_tradeoffs(self):
        self.condition = benchmark.CONDITIONS[1]
        write_json(self.declaration_path, self.declaration("improvement"))
        shared = ["--task", str(self.task), "--task-sha256", self.task_sha,
            "--max-bytes", str(8 * 1024**2), "--pair", str(self.pair_path), "--pair-sha256", self.pair_sha]
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
        self.assertEqual(len(report["comparisons"]), 6)
        self.assertEqual(report["declaration"]["methods"]["offline"]["asset_usage"], self.usage())
        self.assertGreater(report["method_specific_smc_co_bps_difference"], 0)
        self.assertLess(report["source_paper_NDT_co_bps_difference"], 0)
        self.assertEqual(report["binary_decision"], "not_applicable")

    def test_mutated_usage_prediction_and_unsafe_output_refuse_before_target(self):
        self.condition = benchmark.CONDITIONS[1]
        record = self.freeze()
        changed = copy.deepcopy(record)
        changed["declaration"]["method_id"] = "changed-body"
        write_json(self.frozen, changed)
        with self.assertRaises(ValueError):
            self.score()
        write_json(self.frozen, record)
        with preserve(self.predictions["noncausal"]):
            write_bytes(self.predictions["noncausal"], b"changed-prediction")
            with self.assertRaises(ValueError):
                self.score()
        self.result = self.pair_root / self.condition / "forbidden-result.json"
        with self.assertRaises(ValueError):
            self.score()
        self.assertFalse(self.result.exists())
        self.assertFalse(self.target.exists())
        self.result = self.case / "result.json"
        with self.assertRaises(ValueError):
            self.score(scratch_bytes=1)
        self.assertFalse(self.result.exists())

    def test_all_continuous_reference_differences_and_tradeoffs_are_preserved(self):
        values = {"co-bps": 0.35, "vel R2": 0.8, "psth R2": 0.5, "fp-bps": 0.2}
        reproduction = benchmark.compare_metrics("reproduction", {"causal": values, "noncausal": values})
        self.assertEqual(len(reproduction["findings"]), 8)
        self.assertEqual(reproduction["aggregation"], "none")
        for row in reproduction["findings"]:
            self.assertEqual(row["published_signed_difference"], row["observed"] - row["published"])
            self.assertEqual(row["published_absolute_difference"], abs(row["observed"] - row["published"]))
            self.assertEqual(row["current_signed_difference"], row["observed"] - row["current_release_reference"])
            self.assertEqual(row["current_absolute_difference"], abs(row["observed"] - row["current_release_reference"]))
        improvement = benchmark.compare_metrics("improvement", {"offline": values})
        self.assertEqual(improvement["selected_smc_reference_id"], "current_release_noncausal")
        self.assertAlmostEqual(improvement["method_specific_smc_co_bps_difference"], 0.35 - 0.3410160879591172, places=14)
        self.assertAlmostEqual(improvement["source_paper_NDT_co_bps_difference"], 0.35 - 0.3597, places=14)
        for row in improvement["comparisons"]:
            self.assertEqual(set(row["signed_differences"]), set(benchmark.source.METRICS))
            self.assertEqual(set(row["negative_companion_differences"]), {"vel R2", "psth R2", "fp-bps"})
        self.assertEqual(improvement["binary_decision"], "not_applicable")
        self.assertIsNone(improvement["uncertainty"]["confidence_intervals"])


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print("KNOWN_GENERATED_WRITES_LOWER_BOUND=" + str(KNOWN_WRITTEN_BYTES))
