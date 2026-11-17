"""Generated controls only: no author data, inference or scientific result."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("park_decoder_v2", Path(__file__).with_name("decoder.py"))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def behavior(n=40):
    rng = np.random.default_rng(913)
    samples = rng.uniform(1, 9, (n, 12)) * np.tile([1, -1], 6)
    return dict(trial_ids=np.array([f"generated-{i}" for i in range(n)]), sess=np.full(n, 3),
                samples=samples, binary_choices=np.ones(n), interm_cues=np.ones(n),
                estimations=rng.normal(size=n), gen_means=np.linspace(-8, 8, n),
                consistent_samples=np.where(samples > 0, samples, np.nan),
                inconsistent_samples=np.where(samples < 0, samples, np.nan))


def design(b, **kw):
    return decoder.prepare_design(b, b["trial_ids"], participant="generated-participant",
                                  parcel=kw.pop("parcel", "generated-parcel"), context="choice",
                                  n_components=1, seed=kw.pop("seed", 71), **kw)


def perfect_predictions(d, b, *, sign=1, offsets=False):
    """Target-derived synthetic controls, never legitimate scientific predictions."""
    result = []
    for cell in d["cells"]:
        if cell["status"] != "planned":
            continue
        first = 2 * (cell["pair"] - 1)
        stimulus = b["samples"][:, first:first+2].reshape(-1, order="F")
        estimate = np.tile(b["estimations"], 2)
        values = []
        for target in (stimulus, estimate):
            repetitions = []
            for selection in cell["repeats"]:
                x = sign * target[selection["pooled_row_indices"]]
                if offsets:
                    x = x + 1000 * np.asarray(selection["fold_ids"])
                repetitions.append(np.broadcast_to(x[:, None, None], (len(x), 1, 129)).copy())
            values.append(np.stack(repetitions))
        result.append(dict(pair=cell["pair"], consistency=cell["consistency"],
                           repeats=copy.deepcopy(cell["repeats"]), stimulus=values[0], estimate=values[1]))
    return result


class SourceDecoderControls(unittest.TestCase):
    def test_decoder_does_not_import_81_row_information_cutoff(self):
        b = behavior(40)
        d = design(b)
        self.assertEqual(len(d["cells"]), 18)
        self.assertTrue(all(c["matched_rows"] == 40 and len(c["repeats"]) == 5 for c in d["cells"]))
        for cell in d["cells"]:
            for repeat in cell["repeats"]:
                self.assertEqual(len(set(repeat["pooled_row_indices"])), 40)
                self.assertEqual(np.bincount(repeat["fold_ids"]).tolist(), [4]*10)

    def test_missing_sample_excludes_only_affected_row_and_pair(self):
        b = behavior()
        b["samples"][0, 0] = np.nan
        b["consistent_samples"][0, 0] = np.nan
        d = design(b)
        self.assertEqual([x["available_rows"] for x in d["cells"][:3]], [39, 40, 79])
        self.assertEqual([x["matched_rows"] for x in d["cells"][:3]], [39]*3)
        self.assertTrue(all(c["matched_rows"] == 40 for c in d["cells"][3:]))
        self.assertTrue(all(0 not in r["pooled_row_indices"] for c in d["cells"][:3]
                            for r in c["repeats"]))

    def test_source_zero_missing_behavior_and_all_finite_means(self):
        b = behavior()
        b["samples"][0, 0] = 0
        b["consistent_samples"][0, 0] = 0
        b["binary_choices"][1] = 99
        b["estimations"][2] = np.nan
        b["gen_means"][3] = np.nan
        d = design(b)
        self.assertEqual([x["available_rows"] for x in d["cells"][:3]], [36, 37, 74])
        self.assertTrue(all(c["matched_rows"] == 37 for c in d["cells"][3:]))

    def test_neural_alignment_and_invalid_source_mask_rejected(self):
        b = behavior()
        with self.assertRaisesRegex(ValueError, "identity/order"):
            decoder.prepare_design(b, b["trial_ids"][::-1], participant="s", parcel="p",
                                   context="choice", n_components=1, seed=0)
        b["consistent_samples"][0, 7] = b["samples"][0, 7]
        with self.assertRaisesRegex(ValueError, "overlap"):
            design(b)

    def test_contexts_use_correct_intermediate_variable(self):
        b = behavior()
        b["sess"][:] = 1
        b["interm_cues"][:] = -1
        d = decoder.prepare_design(b, b["trial_ids"], participant="s", parcel="p",
                                   context="attn", n_components=1, seed=0)
        for r in d["cells"][0]["repeats"]:
            self.assertTrue(all(i >= 40 for i in r["pooled_row_indices"]))
        # Second interval uses the supplied masks, not the cue sign.
        for r in d["cells"][9]["repeats"]:
            self.assertTrue(all(i < 40 for i in r["pooled_row_indices"]))

    def test_row_folds_and_parcel_streams_are_explicit(self):
        b = behavior()
        d = design(b)
        self.assertEqual(d, design(b))
        self.assertNotEqual(d["cells"][2]["repeats"], design(b, parcel="other")["cells"][2]["repeats"])
        r = d["cells"][2]["repeats"][0]
        trial_folds = {}
        for row, fold in zip(r["pooled_row_indices"], r["fold_ids"]):
            trial_folds.setdefault(row % 40, set()).add(fold)
        self.assertTrue(any(len(f) > 1 for f in trial_folds.values()))

    def test_perfect_and_negative_scores_keep_all_axes_and_signed_primary(self):
        b = behavior()
        d = design(b)
        for sign in (1, -1):
            score = decoder.score_predictions(d, b, perfect_predictions(d, b, sign=sign))
            self.assertEqual(len(score["cells"]), 18)
            for c in score["cells"]:
                self.assertEqual(c["fold_scores"].shape, (5, 10, 3, 1, 129))
                self.assertEqual(c["mean_fold_scores"].shape, (5, 3, 1, 129))
                np.testing.assert_allclose(c["fold_scores"][:, :, :2], sign, atol=1e-12)

    def test_within_fold_metric_differs_from_pooled_prediction_metric(self):
        b = behavior()
        d = design(b)
        p = perfect_predictions(d, b, offsets=True)
        score = decoder.score_predictions(d, b, p)
        np.testing.assert_allclose(score["cells"][0]["mean_fold_scores"][:, 0], 1, atol=1e-12)
        rows = p[0]["repeats"][0]["pooled_row_indices"]
        target = b["samples"][:, :2].reshape(-1, order="F")[rows]
        pooled = np.corrcoef(target, p[0]["stimulus"][0, :, 0, 0])[0, 1]
        self.assertLess(abs(pooled), .9)

    def test_independent_scalar_correlation_oracle_and_companion_distinction(self):
        rng = np.random.default_rng(27)
        target = rng.normal(size=11)
        predicted = rng.normal(size=(11, 2, 3)) * 1e-150
        actual = decoder._pearson(target, predicted)
        for pc in range(2):
            for time in range(3):
                self.assertAlmostEqual(actual[pc, time], np.corrcoef(target, predicted[:, pc, time])[0, 1], places=12)
        b = behavior()
        d = design(b)
        result = decoder.score_predictions(d, b, perfect_predictions(d, b))
        self.assertTrue(any(np.any(np.abs(c["mean_fold_scores"][:, 2]) < .9) for c in result["cells"]))

    def test_constants_and_singletons_stay_undefined_without_dropping_axes(self):
        b = behavior(10)
        d = design(b)
        score = decoder.score_predictions(d, b, perfect_predictions(d, b))
        self.assertTrue(all(c["status"] == "undefined_fold_correlations" for c in score["cells"]))
        self.assertTrue(all(np.isnan(c["mean_fold_scores"]).all() for c in score["cells"]))
        self.assertTrue(np.isnan(decoder._pearson(np.arange(97.), np.full((97, 1, 1), 1.1))).all())
        json.dumps(decoder.json_safe(score), allow_nan=False)
        b = behavior(9)
        d = design(b)
        score = decoder.score_predictions(d, b, [])
        self.assertEqual(len(score["cells"]), 18)
        self.assertTrue(all(c["mean_fold_scores"] is None for c in score["cells"]))

    def test_plan_and_target_mutations_rejected_even_after_rehash(self):
        b = behavior()
        d = design(b)
        mutated = copy.deepcopy(d)
        mutated["cells"][0]["repeats"][0]["fold_ids"][0] = 99
        mutated.pop("design_sha256")
        mutated["design_sha256"] = decoder._digest(mutated)
        with self.assertRaisesRegex(ValueError, "replay"):
            decoder.score_predictions(mutated, b, [])
        b["estimations"][0] += 1
        with self.assertRaisesRegex(ValueError, "replay"):
            decoder.score_predictions(d, b, [])

    def test_prediction_coverage_identity_dimensions_and_nonfinite_rejected(self):
        b = behavior()
        d = design(b)
        p = perfect_predictions(d, b)
        for bad in (p[:-1], p + p[:1]):
            with self.assertRaisesRegex(ValueError, "coverage"):
                decoder.score_predictions(d, b, bad)
        p[0]["repeats"][0]["pooled_row_indices"].reverse()
        with self.assertRaisesRegex(ValueError, "identity"):
            decoder.score_predictions(d, b, p)
        p = perfect_predictions(d, b)
        p[0]["stimulus"][0, 0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            decoder.score_predictions(d, b, p)
        p[0]["stimulus"] = np.zeros((5, 40, 129, 1))
        with self.assertRaisesRegex(ValueError, "shape"):
            decoder.score_predictions(d, b, p)


if __name__ == "__main__":
    unittest.main()
