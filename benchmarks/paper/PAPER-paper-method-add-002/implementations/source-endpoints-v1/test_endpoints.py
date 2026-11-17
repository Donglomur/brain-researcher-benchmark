"""Generated controls only; optional exact cached author-code differential check."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("slice_endpoints", HERE / "endpoints.py")
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)
AUTHOR = None


def generated_movement():
    # Different coordinate offsets make accidentally pooling XY in SST detectable.
    t = np.arange(150, dtype=float)[:, None]
    k = np.arange(511, dtype=float)[None, :]
    return np.stack((1000 + k + t * (1 + k / 511), -500 - k + t * t / 150), axis=2)


def predictions_for(movement, condition, error_scale=0):
    plan = E.source_schedule(condition)
    prediction = np.stack([
        np.stack([movement[65:-5][:, indices].copy() for indices in repeat])
        for repeat in plan["test"]
    ])
    prediction[:, :, 1:] += error_scale
    return prediction, plan["test"]


class Endpoints(unittest.TestCase):
    def test_coordinate_centering_and_negative_score(self):
        y = np.array([[[100., -10.]], [[101., -8.]], [[102., -6.]]])
        p = y.copy()
        p[1:, 0, 0] += 10
        score = E.trajectory_r2(y, p)
        # SST = (1+0+1) + (4+0+4) = 10; SSE=200, so R²=-19.
        self.assertEqual(score["mean"], -19.)
        self.assertEqual(score["sst"].tolist(), [10.])
        self.assertEqual(score["sse"].tolist(), [200.])
        # Coordinate shifts cannot alter source R².
        np.testing.assert_allclose(E.trajectory_r2(y + [1e4, -2e4], p + [1e4, -2e4])["r2"], [-19])

    def test_xy_pooling_is_not_mean_of_coordinate_scores(self):
        y = np.array([[[0., 0.]], [[1., 10.]], [[2., 20.]]])
        p = y.copy()
        p[:, :, 0] = 0
        self.assertAlmostEqual(E.trajectory_r2(y, p)["mean"], 1 - 5 / 202)
        self.assertNotAlmostEqual(E.trajectory_r2(y, p)["mean"], (-1.5 + 1) / 2)

    def test_undefined_and_malformed_trials_are_not_dropped(self):
        with self.assertRaisesRegex(ValueError, "zero within-trial"):
            E.trajectory_r2(np.ones((3, 2, 2)), np.ones((3, 2, 2)))
        with self.assertRaises(ValueError):
            E.trajectory_r2(np.ones((3, 2, 2)), np.ones((3, 1, 2)))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            E.trajectory_r2(np.full((3, 2, 2), np.nan), np.ones((3, 2, 2)))

    def test_displacement_integration_keeps_initial_sample(self):
        initial = np.array([[10., -5.]])
        increments = np.array([[[2., 3.]], [[-1., 4.]]])
        np.testing.assert_array_equal(E.integrate_displacements(increments, initial),
                                      [[[10., -5.]], [[12., -2.]], [[11., 2.]]])

    def test_exact_source_windows(self):
        neural = np.broadcast_to(np.arange(150., dtype=float)[:, None, None], (150, 511, 182))
        movement = np.broadcast_to(np.arange(150., dtype=float)[:, None, None], (150, 511, 2))
        x, y = E.source_windows(neural, movement)
        self.assertEqual(x.shape, (80, 511, 182))
        self.assertEqual(y.shape, (80, 511, 2))
        np.testing.assert_array_equal(x[:, 0, 0], np.arange(55, 135))
        np.testing.assert_array_equal(y[:, 0, 0], np.arange(65, 145))
        with self.assertRaises(ValueError):
            E.source_windows(neural[:, :-1], movement[:, :-1])

    def test_folds_keep_remainder_and_global_rng_untouched(self):
        np.random.seed(91)
        before = np.random.get_state()
        for condition, n, width in (("straight", 265, 53), ("curved", 246, 49)):
            plan = E.source_schedule(condition)
            start, stop = E.CONDITIONS[condition]
            self.assertEqual(plan["test"].shape, (20, 5, width))
            for r in range(20):
                self.assertEqual(len(np.unique(plan["test"][r])), width * 5)
                for f in range(5):
                    train, test = plan["train"][r, f], plan["test"][r, f]
                    self.assertEqual(len(train), n - width)
                    self.assertFalse(np.intersect1d(train, test).size)
                    self.assertEqual(set(np.concatenate((train, test))), set(range(start, stop)))
                    self.assertTrue(set(plan["train_only"][r]).issubset(train))
        after = np.random.get_state()
        self.assertEqual(before[0], after[0])
        np.testing.assert_array_equal(before[1], after[1])
        self.assertEqual(before[2:], after[2:])

    def test_full_condition_aggregation_and_identity_rejection(self):
        y = generated_movement()
        for condition, occurrences in (("straight", 5300), ("curved", 4900)):
            prediction, indices = predictions_for(y, condition)
            summary, details = E.score_condition(y, condition, prediction, indices)
            self.assertEqual(summary["mean_trial_fold_repeat_r2"], 1.)
            self.assertEqual(summary["repeated_test_occurrences"], occurrences)
            self.assertEqual(int(details["trial_test_counts"].sum()), occurrences)
            np.testing.assert_array_equal(details["trial_mean_r2"], 1)
            wrong = indices.copy()
            wrong[0, 0, :2] = wrong[0, 0, :2][::-1]
            with self.assertRaisesRegex(ValueError, "fold order"):
                E.score_condition(y, condition, prediction, wrong)
            with self.assertRaises(ValueError):
                E.score_condition(y, condition, prediction[:-1], indices)
            prediction[0, 0, 0, 0, 0] += 1
            with self.assertRaisesRegex(ValueError, "true initial"):
                E.score_condition(y, condition, prediction, indices)

    def test_source_mask_denominator_and_edges(self):
        target = np.zeros((1, 1, 8))
        prediction = np.array([[[100., 10., 2., 3., 4., 5., 20., 100.]]])
        mask = np.array([[[1, 0, 0, 0, 0, 0, 0, 1]]])
        result = E.reconstruction_error(target, prediction, mask, cut_bins=1)
        self.assertEqual(result["heldout_entries_after_trim"], 4)
        self.assertEqual(result["heldout_sse"], 54)
        self.assertEqual(result["heldout_mse"], 13.5)
        self.assertAlmostEqual(result["source_cv_root_error"], np.sqrt(13.5))
        self.assertEqual(result["source_zero_filled_training_mse"], 2500)
        self.assertEqual(result["training_entry_mse"], 10000)
        # Separate zero blocks: the source trims only the outermost endpoints.
        fragmented = np.array([[[1, 0, 0, 1, 0, 0, 1]]])
        np.testing.assert_array_equal(E.source_trimmed_mask(fragmented, 1), [[[1, 1, 0, 1, 0, 1, 1]]])
        np.testing.assert_array_equal(fragmented, [[[1, 0, 0, 1, 0, 0, 1]]])

    def test_mask_empty_fractional_negative_cut_fail(self):
        y = np.zeros((1, 1, 3))
        for mask, cut in ((np.ones_like(y), 0), (np.zeros_like(y), 2),
                          (np.full_like(y, .5), 0), (np.zeros_like(y), -1)):
            with self.assertRaises(ValueError):
                E.reconstruction_error(y, y, mask, cut_bins=cut)

    def test_cli_reconstruction_uses_nonpickle_npz(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            np.savez(root / "input.npz", target=np.zeros((1, 1, 3)),
                     prediction=np.array([[[100., 2., 3.]]]), training_mask=np.array([[[1, 0, 0]]]))
            result = subprocess.run([sys.executable, "-I", "-B", str(HERE / "endpoints.py"),
                                     "score-reconstruction", "--input", str(root / "input.npz"),
                                     "--cut-bins", "0", "--summary", str(root / "report.json")],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / "report.json").read_text())["heldout_mse"], 6.5)

    def test_exact_author_differential(self):
        if AUTHOR is None:
            self.skipTest("pass --author-source-dir for pinned independent differential control")
        manifest = json.loads((HERE / "SOURCE_MAP.json").read_text())
        selected = {"functions.py": {"trial_wise_r2", "k_fold_cross_validated_r2", "velocity_decoding"},
                    "helper_functions.py": {"split", "flatten_mid_dims"}}
        namespace = {"np": np}
        for entry in manifest["sources"]:
            basename = Path(entry["repository_path"]).name
            data = (AUTHOR / entry["cache_basename"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            self.assertEqual(len(data), entry["bytes"])
            if basename not in selected:
                continue
            tree = ast.parse(data)
            nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in selected[basename]]
            self.assertEqual({node.name for node in nodes}, selected[basename])
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(basename), "exec"), namespace)
        y = generated_movement()
        for condition in E.CONDITIONS:
            start, stop = E.CONDITIONS[condition]
            movement = y[65:-5, start:stop]
            neural = np.broadcast_to(np.arange(start, stop)[None, :, None], (80, stop - start, 1))
            train_ids, test_ids, predictions = [], [], []

            def generated_decoder(data, target):
                # Deterministic generated control; not a fitted scientific model.
                train_ids.append(data[0, :, 0].astype(int))
                delta = np.diff(target, axis=0).mean(axis=1, keepdims=True)

                def decoder(x, initial):
                    test_ids.append(x[0, :, 0].astype(int))
                    prediction = E.integrate_displacements(np.broadcast_to(delta, (79, len(initial), 2)), initial)
                    predictions.append(prediction)
                    return prediction

                return None, decoder

            author_r2, author_sd = namespace["k_fold_cross_validated_r2"](
                neural, movement, generated_decoder, folds=5, sample_size=20, mean=False, seed=0)
            plan = E.source_schedule(condition)
            np.testing.assert_array_equal(np.array(train_ids).reshape(plan["train"].shape), plan["train"])
            np.testing.assert_array_equal(np.array(test_ids).reshape(plan["test"].shape), plan["test"])
            prediction = np.array(predictions).reshape((20, 5, 80, plan["test"].shape[-1], 2))
            summary, details = E.score_condition(y, condition, prediction, plan["test"])
            np.testing.assert_allclose(details["r2"], author_r2, rtol=0, atol=1e-14)
            self.assertAlmostEqual(summary["mean_within_fold_population_sd"], author_sd)
        # Also verify source integration without requiring sklearn or any fitting.
        namespace["decoding"] = lambda x, y, regularization: (np.array([[1.], [-2.]]), np.array([.5, 1.]))
        x = np.arange(8.).reshape(4, 2, 1)
        movement = np.zeros((4, 2, 2)) + [30., -7.]
        result, _ = namespace["velocity_decoding"](x, movement)
        expected = E.integrate_displacements(x[:-1] @ np.array([[1., -2.]]) + [.5, 1.], movement[0])
        np.testing.assert_array_equal(result, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-source-dir", type=Path)
    args, unittest_args = parser.parse_known_args()
    AUTHOR = args.author_source_dir
    unittest.main(argv=[sys.argv[0]] + unittest_args)
