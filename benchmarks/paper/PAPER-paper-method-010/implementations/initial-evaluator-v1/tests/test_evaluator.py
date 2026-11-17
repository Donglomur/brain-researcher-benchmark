"""Bounded generated integration and failure controls; no empirical claims."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("evaluator", ROOT / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def case(role="hippocampus"):
    rng = np.random.default_rng(512)
    n, t = 17, 150
    behavior = rng.normal(size=(t, 2))
    activity = rng.normal(size=(n, 2)) @ behavior.T + rng.normal(size=(n, t)) * 0.05
    ids = [f"n{i:02d}" for i in range(n)]
    record = {"role": role, "activity": activity, "behavior": behavior,
              "timestamps": np.arange(t) * 0.2, "neuron_ids": ids,
              "input_sha256": "a" * 64}
    train = ev.temporal_split(t, 2)["train"]
    artifacts = []
    for name, role_name, embedding in [("candidate", "candidate", np.arange(n)),
                                        ("baseline", "baseline", rng.permutation(n))]:
        base = {"name": name, "role": role_name, "embedding": embedding.tolist(), "neuron_ids": ids,
                "input_sha256": record["input_sha256"], "train_index_sha256": ev.index_sha256(train),
                "seed": 1, "maximum_fit_lag": 2, "tuning_budget": 1,
                "access_condition": "paper_and_data"}
        repeat = {**base, "kind": "repeat_seed", "seed": 2, "fit_time_indices": train.tolist(),
                  "embedding": (-embedding).tolist()}
        subset = {**base, "kind": "neuron_subsample", "seed": 3, "fit_time_indices": train.tolist(),
                  "neuron_ids": ids[:-2], "embedding": embedding[:-2].tolist()}
        base["perturbations"] = [repeat, subset]
        artifacts.append(base)
    return record, artifacts


def evaluate(record, artifacts):
    return ev.evaluate_recording(record, artifacts, purge_samples=2, maximum_fit_lag=2,
                                 neighbor_k=3, engineering=True, row_block=4)


class IntegrationControls(unittest.TestCase):
    def test_complete_generated_panel_retains_holds_and_remainders(self):
        record, artifacts = case()
        report = evaluate(record, artifacts)
        self.assertFalse(report["scientifically_qualified"])
        self.assertIsNone(report["reproduction_pass"])
        self.assertEqual(report["population"]["scored"], 17)
        for method in report["methods"]:
            self.assertEqual(method["behavior"]["group_sizes"], [5, 5, 5, 2])
            self.assertEqual([p["absolute_kendall_tau_b"] for p in method["stability"]], [1.0, 1.0])
        json.dumps(report, allow_nan=False)

    def test_axis_reversal_keeps_behavior_partition_with_remainder(self):
        record, artifacts = case()
        before = evaluate(record, artifacts)
        reverse = copy.deepcopy(artifacts)
        for a in reverse:
            a["embedding"] = [-x for x in a["embedding"]]
        after = evaluate(record, reverse)
        self.assertEqual(before["methods"], after["methods"])

    def test_full_row_id_permutation_is_invariant(self):
        record, artifacts = case()
        expected = evaluate(record, artifacts)
        order = np.arange(len(record["neuron_ids"]))[::-1]
        record["activity"] = record["activity"][order]
        record["neuron_ids"] = [record["neuron_ids"][i] for i in order]
        observed = evaluate(record, artifacts)
        self.assertEqual(expected, observed)

    def test_population_and_provenance_rejection(self):
        record, artifacts = case()
        with self.assertRaisesRegex(ValueError, "population"):
            ev.evaluate_recording(record, artifacts, purge_samples=2)
        for field, value in [("input_sha256", "b" * 64), ("train_index_sha256", "b" * 64),
                             ("tuning_budget", 2), ("access_condition", "secret_labels")]:
            bad = copy.deepcopy(artifacts)
            bad[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                evaluate(record, bad)
        bad = copy.deepcopy(artifacts)
        bad[0]["neuron_ids"] = bad[0]["neuron_ids"][:-1]
        bad[0]["embedding"] = bad[0]["embedding"][:-1]
        with self.assertRaises(ValueError):
            evaluate(record, bad)

    def test_robustness_cannot_use_test_times(self):
        record, artifacts = case()
        for a in artifacts:
            p = a["perturbations"][0]
            p["fit_time_indices"][-1] = 149
            p["train_index_sha256"] = ev.index_sha256(np.array(p["fit_time_indices"]))
        with self.assertRaisesRegex(ValueError, "training-only"):
            evaluate(record, artifacts)

    def test_robustness_panel_is_required_and_paired(self):
        record, artifacts = case()
        for a in artifacts:
            a["perturbations"] = []
        with self.assertRaisesRegex(ValueError, "requires repeat-seed"):
            evaluate(record, artifacts)
        record, artifacts = case()
        artifacts[1]["perturbations"][0]["seed"] = 20
        with self.assertRaisesRegex(ValueError, "same declared robustness"):
            evaluate(record, artifacts)

    def test_source_nan_behavior_rows_are_accounted(self):
        record, artifacts = case()
        split = ev.temporal_split(150, 2)
        for indices in [split["train"], split["validation"], split["test"]]:
            record["behavior"][indices[1], 0] = np.nan
        report = evaluate(record, artifacts)
        for name, counts in report["methods"][0]["behavior"]["behavior_row_accounting"].items():
            self.assertEqual(counts["excluded_nonfinite"], 1)
            self.assertEqual(counts["included"], len(split[name]) - 1)

    def test_scalar_translation_does_not_change_knn(self):
        x = np.array([0, 1, 3, 8, 15], dtype=float)[:, None]
        np.testing.assert_array_equal(ev.knn_indices(x, 1), ev.knn_indices(x + 1e9, 1))

    def test_source_valid_tied_embeddings_have_tie_aware_stability(self):
        a = {"neuron_ids": ["a", "b", "c", "d"], "embedding": [0, 0, 1, 2]}
        b = {"neuron_ids": ["a", "b", "c", "d"], "embedding": [0, 0, -1, -2]}
        score = ev.order_stability(a, b)
        self.assertEqual(score["absolute_kendall_tau_b"], 1.0)
        self.assertEqual(score["comparable_pairs"], 5)
        self.assertEqual(score["reference_tied_pairs"], 1)
        b["embedding"] = [1, 1, 1, 1]
        self.assertIsNone(ev.order_stability(a, b)["absolute_kendall_tau_b"])

    def test_split_local_camera_alignment_does_not_extrapolate(self):
        record, _ = case("mouse")
        del record["behavior"]
        camera = np.arange(-0.1, 30.1, 0.1)
        record.update(camera_times=camera, camera_behavior=(2 * camera)[:, None], running=np.zeros(150))
        split = ev.temporal_split(150, 2)
        aligned = ev._aligned_behavior(record, split)
        self.assertTrue(np.isnan(aligned[split["embargo"], 0]).all())
        eligible = np.isfinite(aligned[:, 0])
        np.testing.assert_allclose(aligned[eligible, 0], 2 * record["timestamps"][eligible], atol=1e-12)
        changed = copy.deepcopy(record)
        changed["camera_behavior"][camera > record["timestamps"][split["train"][-1]]] = 1e9
        np.testing.assert_allclose(ev._aligned_behavior(changed, split)[split["train"]],
                                   aligned[split["train"]], equal_nan=True)

    def test_safe_source_adapter_and_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hip.npz"
            position = np.arange(40, dtype=float); position[4] = np.nan
            np.savez(path, spks=np.ones((4, 40)), loc_signed=position)
            loaded = ev.load_source_npz(path, "hippocampus", ev.file_sha256(path))
            self.assertTrue(np.isnan(loaded["behavior"][4, 0]))
            self.assertAlmostEqual(loaded["timestamps"][2], 0.4)
            with self.assertRaisesRegex(ValueError, "SHA256"):
                ev.load_source_npz(path, "hippocampus", "0" * 64)

    def test_cli_refuses_single_recording_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, out = Path(tmp) / "request.json", Path(tmp) / "report.json"
            path.write_text(json.dumps({"recordings": [{"role": "hippocampus"}]}))
            result = subprocess.run([sys.executable, str(ROOT / "evaluator.py"), str(path), "--output", str(out)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly one hippocampus and one mouse", result.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
