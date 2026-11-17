"""Generated software controls only; these fixtures are not neural observations.

The original-scorer numerical control always runs against the vendored, unchanged
MIT evaluator from the authenticated official nlb-tools==0.0.3 wheel. Provenance
and its license are in third_party/nlb_tools_0_0_3. CI must install NumPy, SciPy,
scikit-learn and h5py; missing dependencies are failures, never silent skips.
The production loader independently requires evaluation.py SHA256
05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476.
This mandatory control calls the unchanged scorer on generated arrays only.
CI dependency versions may differ from the source-qualification environment in
requirements-cpu.txt; CI establishes generated compatibility, not paper scores.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np


SPEC = importlib.util.spec_from_file_location("smc_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pred = self.root / "submission.h5"
        self.manifest_path = self.root / "manifest.json"
        self.reference = self.root / "generated_reference.json"
        self.reference_patch = patch.object(scorer, "REFERENCE_PANEL", self.reference)
        self.reference_patch.start()
        self.protocol = self.root / "protocol.json"
        self.frozen = self.root / "freeze.json"
        self.result = self.root / "result.json"
        private = self.root / "operator"
        private.mkdir()
        self.target = private / "target.h5"
        self.protocol.write_text('{"generated_fixture": true}\n')
        self.manifest = {
            "schema": "smc_nlb_panel_v1", "dataset": "mc_maze_20", "phase": "test",
            "source_commit": scorer.AUTHOR_COMMIT, "dandiset": "000128",
            "dandi_version": "0.220113.0400", "bin_ms": 20,
            "n_train": 6, "n_eval": 4, "n_bins": 35, "forward_bins": 10,
            "n_heldin": 137, "n_heldout": 45, "condition_count": 108,
            "trial_indices_sha256": "1" * 64, "neuron_indices_sha256": "2" * 64,
            "conditions_sha256": "4" * 64, "split_counts": {"train": 4, "val": 2, "test": 4},
            "tensor_trial_indices_sha256": "7" * 64, "condition_membership_sha256": "8" * 64,
            "inputs_sha256": {"generated_fixture": "3" * 64},
            "input_content_sha256": {"generated_fixture": "5" * 64},
            "nwb_sources": [{"name": "generated_fixture", "sha256": "6" * 64}],
        }
        self.manifest["expected_shapes"] = {
            key: [6 if key.startswith("train_") else 4,
                  10 if key.endswith("_forward") else 35,
                  137 if "heldin" in key else 45]
            for key in scorer.RATE_KEYS
        }
        self.write_manifest()
        self.reference.write_text(json.dumps(self.manifest))
        rng = np.random.default_rng(42)
        with h5py.File(self.pred, "w") as handle:
            group = handle.create_group(scorer.DATASET)
            for key, shape in self.manifest["expected_shapes"].items():
                group.create_dataset(key, data=rng.uniform(0.1, 3, shape))

    def tearDown(self):
        self.reference_patch.stop()
        self.tmp.cleanup()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def freeze(self, **kwargs):
        options = dict(arm="causal", method_id="generated-control", role="author_calibration",
                       seed=0, particles=192, repeats=32)
        options.update(kwargs)
        return scorer.freeze_predictions(self.pred, self.manifest_path, self.protocol,
                                         self.frozen, **options)

    def validate(self):
        return scorer.validate_freeze(self.pred, self.manifest_path, self.protocol, self.frozen)

    def score(self, source="unused"):
        # Generated scorer tests replace the source-target digest only in-process.
        # Production CLI always enforces the immutable published LFS object hash.
        with patch.object(scorer, "TARGET_SHA256", scorer.sha256(self.target)):
            return scorer.score_predictions(self.pred, self.manifest_path, self.protocol,
                                            self.frozen, self.target, scorer.sha256(self.target),
                                            source, self.result)

    def test_freeze_is_target_blind_and_nonoverwriting(self):
        self.assertFalse(self.target.exists())
        record = self.freeze()
        self.assertEqual(record["submission_sha256"], scorer.sha256(self.pred))
        self.validate()
        with self.assertRaises(FileExistsError):
            self.freeze()

    def test_source_recipe_cannot_be_downsampled(self):
        with self.assertRaisesRegex(scorer.ContractError, "192 particles"):
            self.freeze(repeats=1)
        self.freeze(role="candidate", particles=None, repeats=None)

    def test_omitted_forward_predictions_fail(self):
        with h5py.File(self.pred, "a") as handle:
            del handle[scorer.DATASET]["eval_rates_heldout_forward"]
        with self.assertRaisesRegex(scorer.ContractError, "missing or extra"):
            self.freeze()

    def test_extra_panel_fails(self):
        with h5py.File(self.pred, "a") as handle:
            handle.create_group("mc_maze_small_20")
        with self.assertRaisesRegex(scorer.ContractError, "exactly mc_maze_20"):
            self.freeze()

    def test_favorable_subset_fails(self):
        with h5py.File(self.pred, "a") as handle:
            group = handle[scorer.DATASET]
            del group["eval_rates_heldout"]
            group.create_dataset("eval_rates_heldout", data=np.ones((1, 5, 45)))
        with self.assertRaisesRegex(scorer.ContractError, "incomplete or misaligned"):
            self.freeze()

    def test_negative_and_nonfinite_fail(self):
        for invalid in (-1, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                with h5py.File(self.pred, "a") as handle:
                    handle[scorer.DATASET]["eval_rates_heldout"][0, 0, 0] = invalid
                with self.assertRaisesRegex(scorer.ContractError, "finite and nonnegative"):
                    self.freeze()

    def test_zero_rate_uses_original_scorer_semantics(self):
        with h5py.File(self.pred, "a") as handle:
            handle[scorer.DATASET]["eval_rates_heldout"][0, 0, 0] = 0
        self.freeze()

    def test_candidate_does_not_need_unused_train_forward_arrays(self):
        with h5py.File(self.pred, "a") as handle:
            for key in scorer.OPTIONAL_KEYS:
                del handle[scorer.DATASET][key]
        with self.assertRaisesRegex(scorer.ContractError, "missing or extra"):
            self.freeze()
        self.freeze(role="candidate", particles=None, repeats=None)

    def test_canonical_target_digest_is_mandatory(self):
        self.freeze()
        with self.assertRaisesRegex(scorer.ContractError, "pinned January 2026"):
            scorer.score_predictions(self.pred, self.manifest_path, self.protocol,
                                     self.frozen, self.target, "4" * 64, "unused", self.result)

    def test_hdf5_external_links_fail_before_following_them(self):
        with h5py.File(self.pred, "a") as handle:
            group = handle[scorer.DATASET]
            del group["eval_rates_heldout"]
            group["eval_rates_heldout"] = h5py.ExternalLink(str(self.target), "/protected")
        with self.assertRaisesRegex(scorer.ContractError, "external or soft"):
            self.freeze()

    def test_changed_prediction_protocol_and_manifest_fail(self):
        self.freeze()
        for path in (self.pred, self.protocol, self.manifest_path, self.reference):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(scorer.ContractError, "frozen content changed"):
                    self.validate()
                path.write_bytes(original)

    def test_missing_provenance_and_duplicate_json_fail(self):
        self.manifest.pop("trial_indices_sha256")
        self.write_manifest()
        with self.assertRaisesRegex(scorer.ContractError, "complete source reference"):
            self.freeze()
        self.manifest_path.write_text('{"schema": 1, "schema": 2}')
        with self.assertRaisesRegex(scorer.ContractError, "duplicate JSON"):
            scorer.read_json(self.manifest_path)

    def test_panel_manifest_cannot_redefine_complete_cohort(self):
        self.manifest["n_eval"] = 1
        self.write_manifest()
        with self.assertRaisesRegex(scorer.ContractError, "complete source reference: n_eval"):
            self.freeze()

    def test_qualification_reference_must_exist(self):
        self.reference.unlink()
        with self.assertRaisesRegex(scorer.ContractError, "has not been qualified"):
            self.freeze()

    def test_unverified_scorer_fails(self):
        fake = self.root / "evaluation.py"
        fake.write_text("raise RuntimeError('must not execute unverified code')\n")
        with self.assertRaisesRegex(scorer.ContractError, "byte-verified"):
            scorer.load_original_scorer(fake)

    def test_invalid_freeze_never_reads_target(self):
        self.freeze()
        self.protocol.write_text("changed")
        with patch.object(scorer, "load_original_scorer") as loader:
            with self.assertRaisesRegex(scorer.ContractError, "frozen content changed"):
                scorer.score_predictions(self.pred, self.manifest_path, self.protocol,
                                         self.frozen, self.target, scorer.TARGET_SHA256,
                                         "unused", self.result)
            loader.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_aggregate_report_has_companion_metrics_no_claim(self):
        self.freeze()
        self.target.write_bytes(b"generated operator file")
        fake = types.SimpleNamespace(evaluate=lambda target, pred:
                                     [{scorer.DATASET + "_split": dict(zip(scorer.METRICS, (0.3, 0.8, 0.5, 0.2)))}])
        # This generated mock does not execute scientific dependencies. Its
        # version metadata must not make generic CI require scikit-learn.
        with patch.object(scorer, "load_original_scorer", return_value=fake), \
                patch.object(scorer.importlib.metadata, "version", return_value="generated-fixture-only"):
            report = self.score()
        self.assertEqual(set(report["metrics"]), set(scorer.METRICS))
        self.assertAlmostEqual(report["difference_from_published"]["co-bps"], -0.0225)
        self.assertIn("reproduction is calibration", report["interpretation"])
        self.assertNotIn(str(self.target), self.result.read_text())

    def test_missing_companion_metric_fails(self):
        self.freeze()
        self.target.write_bytes(b"generated operator file")
        fake = types.SimpleNamespace(evaluate=lambda target, pred:
                                     [{scorer.DATASET + "_split": {"co-bps": 0.4}}])
        with patch.object(scorer, "load_original_scorer", return_value=fake):
            with self.assertRaisesRegex(scorer.ContractError, "companion metrics"):
                self.score()

    def test_original_scorer_generated_numerical_control(self):
        """Runs the actual unchanged scorer, not a mirror implementation."""
        rng = np.random.default_rng(73)
        with h5py.File(self.target, "w") as handle:
            group = handle.create_group(scorer.DATASET)
            group.create_dataset("eval_spikes_heldout", data=rng.poisson(0.8, (4, 35, 45)))
            group.create_dataset("eval_spikes_heldin_forward", data=rng.poisson(0.8, (4, 10, 137)))
            group.create_dataset("eval_spikes_heldout_forward", data=rng.poisson(0.8, (4, 10, 45)))
            group.create_dataset("train_behavior", data=rng.normal(size=(6, 35, 2)))
            group.create_dataset("eval_behavior", data=rng.normal(size=(4, 35, 2)))
            group.create_dataset("psth", data=rng.uniform(0.1, 3, (108, 35, 182)))
            conditions = group.create_dataset("eval_cond_idx", (108,), dtype=h5py.vlen_dtype(np.dtype("int64")))
            for index in range(108):
                conditions[index] = np.array([index] if index < 4 else [], dtype=np.int64)
        self.freeze()
        original = Path(__file__).parent / "third_party" / "nlb_tools_0_0_3" / "evaluation.py"
        provenance = scorer.read_json(original.parent / "PROVENANCE.json")
        for name, identity in provenance["files"].items():
            self.assertEqual(scorer.sha256(original.parent / name), identity["sha256"])
            self.assertEqual((original.parent / name).stat().st_size, identity["bytes"])
        report = self.score(original)
        with h5py.File(self.target, "r") as target, h5py.File(self.pred, "r") as pred:
            counts = target[scorer.DATASET]["eval_spikes_heldout"][()]
            rates = pred[scorer.DATASET]["eval_rates_heldout"][()]
        mean = counts.mean(axis=(0, 1), keepdims=True)
        # Factorial terms cancel; this independent identity checks rate units and log base.
        expected = np.sum(counts * np.log(rates / mean) + mean - rates) / counts.sum() / np.log(2)
        self.assertAlmostEqual(report["metrics"]["co-bps"], expected, places=11)
        self.assertTrue(all(np.isfinite(list(report["metrics"].values()))))


if __name__ == "__main__":
    unittest.main()
