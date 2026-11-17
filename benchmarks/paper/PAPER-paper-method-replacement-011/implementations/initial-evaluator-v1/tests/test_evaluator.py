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
from scipy import stats

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("word_response", HERE / "evaluator.py")
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


def fixture(root, runs=("trial000",), electrodes=("E1", "E2")):
    recordings = []
    for rindex, run in enumerate(runs):
        word_ids = [f"w{i}" for i in range(5)]
        epochs = np.zeros((len(electrodes), 5, 3072))
        for ei in range(len(electrodes)):
            for wi, (a, b, c, d) in enumerate(evaluator.WINDOWS):
                epochs[ei, :, a+1024:b+1024] = np.arange(5)[:, None] + rindex
                # First window strongest; final weakest. Effects must follow min p.
                delta = (np.arange(5)+1) * (wi+1) + (20 if wi == 0 else 0)
                epochs[ei, :, c+1024:d+1024] = np.arange(5)[:, None] + rindex + delta[:, None]
        path = root / f"{run}.npz"
        np.savez(path, epochs=epochs, word_ids=np.array(word_ids), electrode_ids=np.array(electrodes), onset_samples=np.arange(5)*5000)
        recordings.append({"subject_id": "sub_1", "run_id": run, "path": path.name,
                           "sha256": evaluator.sha256(path), "n_words": 5,
                           "word_ids_sha256": hashlib.sha256(json.dumps(word_ids, separators=(",", ":")).encode()).hexdigest()})
    return {"schema_version": 1, "task_id": evaluator.TASK_ID, "scope": "engineering_control",
            "sample_rate_hz": 2048, "epoch_first_sample": -1024,
            "timing_sha256": "0"*64, "processing_sha256": "1"*64,
            "electrode_inventory_sha256": "2"*64,
            "processing_description": "Generated engineering controls; no native processing.",
            "selection_policy": "all_declared_electrodes_and_words",
            "subjects": [{"subject_id": "sub_1", "electrode_ids": list(electrodes), "run_ids": list(runs), "excluded_electrodes": []}],
            "recordings": recordings}


class NumericTests(unittest.TestCase):
    def test_independent_reference_control(self):
        # Contract worker derived Student t by hand and distinguished pooled effect from dz.
        moment = evaluator.PairedMoments()
        moment.add(np.zeros(5), np.arange(1, 6))
        row = moment.result()
        self.assertAlmostEqual(row["paired_t"], -4.242640687119285)
        self.assertAlmostEqual(row["p_two_sided"], 0.0132355995636827)
        self.assertAlmostEqual(row["source_pooled_sd_effect"], -1.6641005886756874)
        self.assertNotAlmostEqual(row["source_pooled_sd_effect"], -1.8973665961010275)

    def test_streaming_matches_independent_scipy(self):
        pre = np.array([3, 1, 7, 2, -1, 5, 9, 3.5, 7.5]) + 1e5
        post = pre + np.array([1, 2, -2, 5, 0.5, 7, -1, 3, 4])
        moment = evaluator.PairedMoments()
        for a, b in ((0, 2), (2, 6), (6, 9)):
            moment.add(pre[a:b], post[a:b])
        result = moment.result()
        ref = stats.ttest_rel(pre, post)
        self.assertAlmostEqual(result["paired_t"], ref.statistic, places=10)
        self.assertAlmostEqual(result["p_two_sided"], ref.pvalue, places=10)
        self.assertAlmostEqual(result["source_pooled_sd_effect"], (pre.mean()-post.mean())/np.concatenate((pre, post)).std(), places=10)

    def test_exact_half_open_slices(self):
        epochs = np.arange(-1024, 2048, dtype=float)[None, None, :]
        pre, post = evaluator.window_means(epochs, -1024)
        np.testing.assert_allclose(pre[0, 0], [-922, -717, -512, -307, -102.5])
        np.testing.assert_allclose(post[0, 0], [1125.5, 1330, 1535, 1740, 1945])
        with self.assertRaisesRegex(ValueError, "complete"):
            evaluator.window_means(epochs[..., :-1], -1024)

    def test_finite_input_arithmetic_overflow_rejected(self):
        moment = evaluator.PairedMoments()
        with np.errstate(over="ignore", invalid="ignore"):
            with self.assertRaisesRegex(ValueError, "overflow"):
                moment.add(np.array([1e308, 1e308]), np.array([-1e308, -1e308]))

    def test_zero_noise_is_explicit(self):
        for value in (0, 2):
            moment = evaluator.PairedMoments()
            moment.add(np.arange(5), np.arange(5)+value)
            self.assertIsNone(moment.result()["p_two_sided"])
            self.assertEqual(moment.result()["status"], "zero_difference_variance")
        with self.assertRaises(ValueError):
            evaluator.window_means(np.full((1, 2, 3072), np.nan), -1024)


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manifest = fixture(self.root, runs=("trial000", "trial001"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_family_merge_and_minimum_effect(self):
        result = evaluator.evaluate(self.manifest, self.root)
        self.assertEqual(result["multiplicity"]["family_size"], 10)
        self.assertEqual(len(result["results"]), 10)
        self.assertEqual(len(result["per_run_descriptive_results"]), 20)
        first = result["results"][0]
        self.assertEqual(first["n_words"], 10)
        self.assertEqual(first["p_global_bonferroni"], min(1, first["p_two_sided"]*10))
        self.assertEqual(result["electrodes"][0]["minimum_p_window"], 0)
        self.assertEqual(result["electrodes"][0]["effect_at_minimum_p"], first["source_pooled_sd_effect"])
        self.assertFalse(result["authentic_population_verified"])
        self.assertTrue(all(v is False for v in result["admission"].values()))

    def test_no_silent_inventory_or_word_shrinkage(self):
        mutations = [lambda m: m["recordings"].pop(),
                     lambda m: m["recordings"].append(m["recordings"][0]),
                     lambda m: m["subjects"][0]["electrode_ids"].reverse(),
                     lambda m: m["subjects"][0]["electrode_ids"].append("E1"),
                     lambda m: m["recordings"][0].update(n_words=4),
                     lambda m: m["recordings"][0].update(word_ids_sha256="f"*64),
                     lambda m: m.update(scope="declared_source_population"),
                     lambda m: m.update(selection_policy="top_k_electrodes"),
                     lambda m: m.update(sample_rate_hz=1000)]
        for mutate in mutations:
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with self.assertRaises(ValueError):
                evaluator.evaluate(manifest, self.root)

    def test_integrity_and_path_escape(self):
        for patch in ({"path": "../elsewhere.npz"}, {"sha256": "a"*64}):
            manifest = copy.deepcopy(self.manifest)
            manifest["recordings"][0].update(patch)
            with self.assertRaises(ValueError):
                evaluator.evaluate(manifest, self.root)

    def test_degenerate_windows_remain_in_family(self):
        for recording in self.manifest["recordings"]:
            path = self.root / recording["path"]
            with np.load(path) as data:
                contents = {k: data[k] for k in data.files}
            contents["epochs"][1] = 0
            np.savez(path, **contents)
            recording["sha256"] = evaluator.sha256(path)
        result = evaluator.evaluate(self.manifest, self.root)
        self.assertEqual(result["multiplicity"]["family_size"], 10)
        self.assertEqual(sum(r["status"] != "ok" for r in result["results"]), 5)

    def test_unsigned_descending_onsets_rejected(self):
        recording = self.manifest["recordings"][0]
        path = self.root / recording["path"]
        with np.load(path) as data:
            contents = {k: data[k] for k in data.files}
        contents["onset_samples"] = np.array([10, 5, 20, 30, 40], dtype=np.uint64)
        np.savez(path, **contents)
        recording["sha256"] = evaluator.sha256(path)
        with self.assertRaisesRegex(ValueError, "chronological"):
            evaluator.evaluate(self.manifest, self.root)

    def test_cli_json_and_manifest_receipt(self):
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest))
        output = self.root / "result.json"
        subprocess.run([sys.executable, "-B", str(HERE / "evaluator.py"), str(manifest_path),
                        "--input-root", str(self.root), "--output", str(output)], check=True)
        result = json.loads(output.read_text())
        self.assertEqual(result["manifest_sha256"], evaluator.sha256(manifest_path))
        self.assertEqual(result["source_revision"], evaluator.SOURCE_REVISION)


if __name__ == "__main__":
    unittest.main()
