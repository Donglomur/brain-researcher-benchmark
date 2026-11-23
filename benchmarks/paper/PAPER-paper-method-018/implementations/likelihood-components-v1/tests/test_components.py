"""Generated arithmetic and submission controls; no neural data or fitting."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "components.py"
SPEC = importlib.util.spec_from_file_location("components", MODULE)
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


class ComponentsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

        def artifact(name, key, array):
            path = self.root / name
            np.savez(path, **{key: array})
            return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

        counts = [artifact("counts-first.npz", "counts", np.full((2, 1, 2), 2)),
                  artifact("counts-tail.npz", "counts", np.zeros((2, 1, 1), dtype=int))]
        predictions = [{}, {}]
        for index, variant in enumerate(c.VARIANTS):
            for batch, trials in enumerate((2, 1)):
                rate = index + 1 + 2 * batch
                predictions[batch][variant] = artifact(f"{variant}-{batch}.npz", "log_rate",
                                                       np.full((2, 1, trials), math.log(rate)))
        sessions = []
        for sid in c.SESSION_IDS:
            sessions.append({"session_id": sid, "neuron_ids": ["generated-neuron"],
                             "time_bin_indices": [50, 51], "train_trial_ids": ["train"],
                             "validation_trial_ids": ["validation"], "test_trial_ids": ["a", "b", "c"],
                             "model_runs": {v: {"checkpoint_sha256": hashlib.sha256(v.encode()).hexdigest(),
                                                 "recipe_sha256": "a" * 64, "model_stage": "generated-stage"}
                                            for v in c.VARIANTS},
                             "batches": [{"trial_ids": trial_ids, "counts": counts[i],
                                          "predictions": copy.deepcopy(predictions[i])}
                                         for i, trial_ids in enumerate((["a", "b"], ["c"]))]})
        self.manifest = {"schema_version": 1, "task_id": c.TASK_ID, "source_commit": c.SOURCE_COMMIT,
                         "run_id": "generated-run", "inference_policy": c.INFERENCE_POLICY,
                         "bin_width_seconds": 0.002, "sessions": sessions}
        self.path = self.root / "manifest.json"

    def collect(self):
        self.path.write_text(json.dumps(self.manifest))
        return c.collect(self.path)

    def test_all_five_variants_native_tail_and_factorial_constant(self):
        result = self.collect()
        self.assertEqual(len(result["sessions"]), 10)
        self.assertFalse(result["scientifically_qualified"])
        self.assertIsNone(result["paper_score"])
        self.assertIsNone(result["paper_standard_error"])
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        for session in result["sessions"]:
            self.assertEqual(session["observation_count"], 6)
            self.assertEqual([b["trial_ids"] for b in session["batches"]], [["a", "b"], ["c"]])
            for index, variant in enumerate(c.VARIANTS):
                rate = index + 1
                expected_without = 4 * (rate - 2 * math.log(rate)) + 2 * (rate + 2)
                terms = session["declared_session_totals"][variant]
                self.assertAlmostEqual(terms["poisson_without_constant_sum"], expected_without)
                self.assertAlmostEqual(terms["log_factorial_sum"], 4 * math.log(2))
                self.assertAlmostEqual(terms["poisson_with_constant_sum"], expected_without + 4 * math.log(2))

    def test_missing_original_variant_is_rejected(self):
        del self.manifest["sessions"][0]["batches"][0]["predictions"]["no_trial_wise_latent"]
        with self.assertRaisesRegex(c.ComponentError, "predictions"):
            self.collect()

    def test_missing_or_duplicate_session_is_rejected(self):
        self.manifest["sessions"][-1] = copy.deepcopy(self.manifest["sessions"][0])
        with self.assertRaisesRegex(c.ComponentError, "session"):
            self.collect()

    def test_split_overlap_and_test_order_are_rejected(self):
        session = self.manifest["sessions"][0]
        session["train_trial_ids"] = ["a"]
        with self.assertRaisesRegex(c.ComponentError, "overlap"):
            self.collect()
        session["train_trial_ids"] = ["train"]
        session["batches"][0]["trial_ids"] = ["b", "a"]
        with self.assertRaisesRegex(c.ComponentError, "ordered test trials"):
            self.collect()

    def test_counts_must_match_frozen_axes(self):
        self.manifest["sessions"][0]["neuron_ids"].append("extra")
        with self.assertRaisesRegex(c.ComponentError, "native axes"):
            self.collect()

    def test_changed_artifact_is_rejected(self):
        with (self.root / "counts-first.npz").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(c.ComponentError, "digest mismatch"):
            self.collect()

    def test_authenticated_bytes_survive_path_replacement(self):
        record = self.manifest["sessions"][0]["batches"][0]["counts"]
        target = self.root / record["path"]
        original_read = Path.read_bytes

        def capture_then_replace(path):
            raw = original_read(path)
            if path == target:
                np.savez(target, counts=np.full((2, 1, 2), 999))
            return raw

        with mock.patch.object(Path, "read_bytes", capture_then_replace):
            actual = c.read_array(self.root, record, "counts")
        np.testing.assert_array_equal(actual, np.full((2, 1, 2), 2))

    def test_arithmetic_rejects_invalid_counts_rates_and_shapes(self):
        for counts, log_rate in (([-1], [0]), ([0.5], [0]), ([2**54], [0]),
                                 ([0], [math.nan]), ([1], [1000])):
            with self.subTest(counts=counts, log_rate=log_rate), self.assertRaises(c.ComponentError):
                c.likelihood_components(np.array(counts).reshape(1, 1, 1),
                                        np.array(log_rate).reshape(1, 1, 1))
        with self.assertRaisesRegex(c.ComponentError, "shape"):
            c.likelihood_components(np.zeros((1, 1, 2)), np.zeros((1, 1, 1)))

    def test_artifact_cannot_leave_manifest_directory(self):
        record = self.manifest["sessions"][0]["batches"][0]["counts"]
        record["path"] = "../counts-first.npz"
        with self.assertRaisesRegex(c.ComponentError, "unconfined"):
            self.collect()

    def test_duplicate_json_keys_are_rejected(self):
        self.path.write_text('{"schema_version": 1, "schema_version": 1}')
        with self.assertRaisesRegex(c.ComponentError, "duplicate JSON key"):
            c.collect(self.path)

    def test_cli_writes_once_and_preserves_existing_output(self):
        self.path.write_text(json.dumps(self.manifest))
        output = self.root / "report.json"
        self.assertEqual(c.main(["--manifest", str(self.path), "--output", str(output)]), 0)
        first = output.read_bytes()
        with self.assertRaises(SystemExit) as error:
            c.main(["--manifest", str(self.path), "--output", str(output)])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(output.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
