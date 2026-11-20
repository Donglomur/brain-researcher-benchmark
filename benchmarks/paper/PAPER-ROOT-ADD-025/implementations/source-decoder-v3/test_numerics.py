"""Focused numerical successor controls; generated arrays, no native data or fit."""
import importlib.util
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact_correlation(a, b):
    """Independent exact-rational covariance of the supplied binary floats."""
    a, b = [Fraction(float(x)) for x in a], [Fraction(float(x)) for x in b]
    am, bm = sum(a) / len(a), sum(b) / len(b)
    a, b = [x - am for x in a], [x - bm for x in b]
    cross = sum(x * y for x, y in zip(a, b))
    energy = sum(x*x for x in a) * sum(x*x for x in b)
    if not energy:
        return None
    return (-1.0 if cross < 0 else 1.0) * math.sqrt(float(cross*cross / energy))

import copy
import hashlib
import numpy as np

HERE = Path(__file__).parent
decoder = load("park_decoder_v3_numerics", HERE / "decoder.py")
old = load("park_decoder_v2_numerics", HERE.parent / "source-decoder-v2/decoder.py")
panel = load("park_panel_v2_numerics", HERE.parent / "paired-panel-v2/panel.py")


def generated_behavior():
    n = 30
    samples = np.arange(1., n + 1.)[:, None] * np.tile([1., -1.], 6)[None, :]
    return dict(trial_ids=np.array([f"generated-{i}" for i in range(n)]), sess=np.full(n, 3),
                samples=samples, binary_choices=np.ones(n), interm_cues=np.ones(n),
                estimations=1e308 + np.arange(n) * math.ulp(1e308), gen_means=np.zeros(n),
                consistent_samples=np.where(samples > 0, samples, np.nan),
                inconsistent_samples=np.where(samples < 0, samples, np.nan))


def generated_perfect_predictions(design, behavior):
    """Target-derived generated oracle; never a scientific candidate."""
    result = []
    for cell in design["cells"]:
        start = 2 * (cell["pair"] - 1)
        targets = [behavior["samples"][:, start:start+2].reshape(-1, order="F"),
                   np.tile(behavior["estimations"], 2)]
        values = []
        for target in targets:
            repeats = []
            for selection in cell["repeats"]:
                x = target[selection["pooled_row_indices"]]
                repeats.append(np.broadcast_to(x[:, None, None], (len(x), 1, 129)).copy())
            values.append(np.stack(repeats))
        result.append(dict(pair=cell["pair"], consistency=cell["consistency"],
                           repeats=copy.deepcopy(cell["repeats"]), stimulus=values[0], estimate=values[1]))
    return result


class FiniteOffsetDecoderTests(unittest.TestCase):
    def test_near_constant_offset_agrees_with_exact_rational_correlation(self):
        target = np.array([0., 0., 1.])
        positive = np.array([1., 1., math.nextafter(1., math.inf)])
        predicted = np.stack((positive, -positive), axis=1)[:, :, None]
        previous = old._pearson(target, predicted)
        self.assertGreater(abs(previous[0, 0] - 1.), .01)
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            actual = decoder._pearson(target, predicted)
        for pc in range(2):
            self.assertAlmostEqual(actual[pc, 0], exact_correlation(target, predicted[:, pc, 0]), places=14)

    def test_finite_extremes_do_not_become_undefined_or_overflow(self):
        large = 1e308
        step = math.ulp(large)
        for target, predicted in [
            ([large, large + step, large + 3*step], [0., 1., 3.]),
            ([0., 1., 3.], [large, large + step, large + 3*step]),
            ([-large, 0., large], [1., 0., -1.]),
            ([0., 0., 1.], [5e-324, 5e-324, 1e-323]),
        ]:
            target, predicted = np.asarray(target), np.asarray(predicted)[:, None, None]
            with self.subTest(target=target.tolist(), predicted=predicted[:, 0, 0].tolist()):
                with np.errstate(over="raise", invalid="raise", divide="raise"):
                    result = decoder._pearson(target, predicted)
                self.assertAlmostEqual(result[0, 0], exact_correlation(target, predicted[:, 0, 0]), places=14)
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            self.assertTrue(np.isnan(decoder._pearson(np.array([large]*3), np.arange(3.)[:, None, None])).all())
            self.assertTrue(np.isnan(decoder._pearson(np.array([1.]), np.ones((1, 2, 3)))).all())

    def test_actual_score_entrypoint_and_panel_pin_keep_all_source_axes(self):
        b = generated_behavior()
        design = decoder.prepare_design(b, b["trial_ids"], participant="generated-person", parcel="generated-parcel",
                                        context="choice", n_components=1, seed=93)
        predictions = generated_perfect_predictions(design, b)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            before = old.score_predictions(design, b, predictions)
        self.assertTrue(any(np.isnan(c["fold_scores"][:, :, 1]).any() for c in before["cells"]))
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scored = decoder.score_predictions(design, b, predictions)
        self.assertEqual(len(scored["cells"]), 18)
        for cell in scored["cells"]:
            self.assertEqual(cell["fold_scores"].shape, (5, 10, 3, 1, 129))
            self.assertEqual(cell["mean_fold_scores"].shape, (5, 3, 1, 129))
            np.testing.assert_allclose(cell["fold_scores"][:, :, :2], 1., atol=1e-14, rtol=0)
        self.assertEqual(panel.DECODER_SHA256, hashlib.sha256((HERE / "decoder.py").read_bytes()).hexdigest())
        paired_inputs = panel._scores(scored, design)
        self.assertEqual(len(paired_inputs), 18)
        for checked, cell in zip(paired_inputs, scored["cells"]):
            np.testing.assert_array_equal(checked["mean"], cell["mean_fold_scores"])
        self.assertEqual(scored["metric_names"], ["corr_S_Shat", "corr_E_Ehat", "corr_E_Shat"])


if __name__ == "__main__":
    unittest.main()
