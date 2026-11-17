"""Generated controls for selection logic; no empirical arrays or native jobs."""
import hashlib
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "selector.py"
SPEC = importlib.util.spec_from_file_location("find024_selector", SOURCE)
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


def fixture():
    # rate, width, delay, shape, boundary, channel
    loss = np.full((2, 2, 1, 2, 1, 1), 20.0)
    # Shape 1 can have zero loss at both rates only with DIFFERENT widths.
    loss[0, 0, 0, 0, 0, 0] = 0
    loss[1, 1, 0, 0, 0, 0] = 0
    loss[:, 0, 0, 1, 0, 0] = 2
    return dict(loss=loss, intper_sec=[0.1, 0.3], delay_sec_start=[0],
                shape=[1, 2], boundstrength=[0], channel_ids=["electrode-A"],
                rates=[1 / math.sqrt(3), math.sqrt(3)])


class TestSelector(unittest.TestCase):
    def test_min_before_sum_preserves_rate_specific_widths(self):
        result = selector.select_tied_shape(**fixture())
        self.assertEqual([r["best_intper_sec_tiedshape"] for r in result["rows"]], [0.1, 0.3])
        self.assertEqual([r["best_shape_tiedshape"] for r in result["rows"]], [1, 1])
        self.assertEqual(result["shape_loss"], [[0], [4]])
        # Incorrect sum-before-min chooses shape 2 (loss4 versus20).
        wrong = fixture()["loss"].sum(axis=0).min(axis=(0, 1, 3))
        self.assertEqual(int(wrong.argmin()), 1)

    def test_independent_exhaustive_joint_search(self):
        rng = np.random.default_rng(2403)
        data = dict(loss=rng.uniform(-2, 2, (2, 2, 2, 3, 2, 3)),
                    intper_sec=[.05, .4], delay_sec_start=[0, .03], shape=[1, 2, 5],
                    boundstrength=[0, .5], channel_ids=["a", "b", "c"],
                    rates=[1 / math.sqrt(3), math.sqrt(3)])
        result = selector.select_tied_shape(**data)
        nuisance = list(itertools.product(range(2), repeat=3))
        # Oracle enumerates every pair of rate-specific parameter choices,
        # instead of implementing the selector's min-then-sum reduction.
        for ci in range(3):
            possibilities = []
            for si, p0, p1 in itertools.product(range(3), nuisance, nuisance):
                w0, d0, b0 = p0
                w1, d1, b1 = p1
                total = math.fsum([data["loss"][0, w0, d0, si, b0, ci],
                                   data["loss"][1, w1, d1, si, b1, ci]])
                possibilities.append((total, si, p0, p1))
            total, si, p0, p1 = min(possibilities)
            for ri, (wi, di, bi) in enumerate([p0, p1]):
                row = result["rows"][ci * 2 + ri]
                self.assertEqual(row["parameter_indices_zero_based"], [wi, di, si, bi])
                self.assertEqual(row["summed_rate_minimum_shape_loss"], total)

    def test_reordered_coordinates_preserve_selected_physical_values(self):
        data = fixture()
        expected = selector.select_tied_shape(**data)["rows"]
        data["loss"] = data["loss"][:, ::-1, :, ::-1]
        data["intper_sec"] = data["intper_sec"][::-1]
        data["shape"] = data["shape"][::-1]
        actual = selector.select_tied_shape(**data)["rows"]
        for left, right in zip(expected, actual):
            for key in ["best_intper_sec_tiedshape", "best_shape_tiedshape", "selected_loss"]:
                self.assertEqual(left[key], right[key])

    def test_ambiguous_shape_rejected(self):
        data = fixture()
        data["loss"][:, 0, 0, 1, 0, 0] = 0
        with self.assertRaisesRegex(selector.SelectionError, "ambiguous minimum in shared shape"):
            selector.select_tied_shape(**data)

    def test_ambiguous_nuisance_rejected(self):
        data = fixture()
        data["loss"][0, 1, 0, 0, 0, 0] = 0
        with self.assertRaisesRegex(selector.SelectionError, "ambiguous minimum in nuisance"):
            selector.select_tied_shape(**data)

    def test_nonfinite_complex_boolean_and_axis_errors_rejected(self):
        for invalid in [float("nan"), float("inf")]:
            data = fixture()
            data["loss"][0, 0, 0, 0, 0, 0] = invalid
            with self.assertRaises(selector.SelectionError):
                selector.select_tied_shape(**data)
        for kind in [complex, bool]:
            data = fixture()
            data["loss"] = data["loss"].astype(kind)
            with self.assertRaises(selector.SelectionError):
                selector.select_tied_shape(**data)
        for key, value in [("intper_sec", [.1, .1]), ("shape", [0, 1]),
                           ("rates", [math.sqrt(3), 1 / math.sqrt(3)]),
                           ("channel_ids", ["a", "a"]), ("boundstrength", [-1])]:
            data = fixture()
            data[key] = value
            with self.assertRaises(selector.SelectionError):
                selector.select_tied_shape(**data)
        data = fixture()
        data["loss"] = data["loss"].swapaxes(1, 2)
        with self.assertRaisesRegex(selector.SelectionError, "loss axes"):
            selector.select_tied_shape(**data)

    def test_negative_losses_not_clipped(self):
        data = fixture()
        data["loss"] -= 30
        result = selector.select_tied_shape(**data)
        self.assertEqual(result["shape_loss"], [[-60], [-56]])
        self.assertEqual([r["selected_loss"] for r in result["rows"]], [-30, -30])

    def test_overflow_rejected(self):
        data = fixture()
        data["loss"][:] = 1e308
        with self.assertRaisesRegex(selector.SelectionError, "overflows"):
            selector.select_tied_shape(**data)

    def test_offline_cli_hash_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.npz"
            output = Path(directory) / "selection.json"
            np.savez(path, **fixture())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            selector.main([str(path), str(output), "--expected-sha256", digest])
            result = json.loads(output.read_text())
            self.assertEqual(result["input_sha256"], digest)
            self.assertEqual(len(result["rows"]), 2)
            with self.assertRaisesRegex(selector.SelectionError, "SHA256 mismatch"):
                selector.main([str(path), str(output), "--expected-sha256", "0" * 64])

    def test_cli_loads_verified_bytes_when_input_path_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.npz"
            output = Path(directory) / "selection.json"
            np.savez(path, **fixture())
            original_bytes = path.read_bytes()
            digest = hashlib.sha256(original_bytes).hexdigest()
            replacement = fixture()
            replacement["intper_sec"] = [8., 9.]
            buffer = io.BytesIO()
            np.savez(buffer, **replacement)
            replacement_bytes = buffer.getvalue()
            native_load = np.load

            def replace_path_before_loading(operand, **kwargs):
                path.write_bytes(replacement_bytes)
                return native_load(operand, **kwargs)

            with patch.object(selector.np, "load", side_effect=replace_path_before_loading):
                selector.main([str(path), str(output), "--expected-sha256", digest])
            result = json.loads(output.read_text())
            self.assertEqual(path.read_bytes(), replacement_bytes)
            self.assertEqual(result["input_sha256"], digest)
            self.assertEqual([r["best_intper_sec_tiedshape"] for r in result["rows"]], [.1, .3])


if __name__ == "__main__":
    unittest.main()
