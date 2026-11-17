"""Invented-array checks only. Never reads source neural/image/semantic data."""
import copy
import json
import math
import unittest

import numpy as np

import encoding_core as core


def fixture(nconcepts=10, subjects=("01",), voxels=4):
    rng = np.random.Generator(np.random.PCG64(9821))
    features = {}
    for i in range(nconcepts):
        features[f"c{i:03}"] = {"image": f"photo{i:03}",
            "image_features": [float(np.sin(i * .7)), float(np.cos(i * .31))],
            "animacy": float(1 + i % 7), "size": float((i * 53) % 520)}
    result = []
    for person_i, person in enumerate(subjects):
        rows, responses = [], []
        for session in range(1, 13):
            for i, (concept, f) in enumerate(features.items()):
                rows.append({"concept": concept, "image": f["image"], "session": session,
                             "run": i // 5, "trial_id": (session - 1) * nconcepts + i,
                             "within_run_position": i % 5})
                v = [(.2 + .1 * person_i) * f["image_features"][0] + .3 * f["animacy"],
                     .005 * f["size"] + .2 * f["image_features"][1],
                     .7 * f["animacy"] + .002 * f["size"],
                     .009 * f["size"] + .1 * f["animacy"]]
                responses.append(np.array(v[:voxels]) + .02 * session + rng.normal(0, .03, voxels))
        result.append({"subject_id": person, "responses": np.asarray(responses),
                       "voxel_ids": list(range(voxels)),
                       "roi_masks": {"V1": np.arange(voxels) < voxels // 2,
                                     "IT": np.arange(voxels) >= voxels // 2},
                       "rows": rows})
    return result, features


class GeneratedProtocolChecks(unittest.TestCase):
    def test_grouped_holdout_and_exact_query_coverage(self):
        subjects, features = fixture(100)
        rows = subjects[0]["rows"]
        folds = core.concept_folds(list(features))
        self.assertEqual([list(folds.values()).count(i) for i in range(5)], [20] * 5)
        coverage = np.zeros(len(rows), dtype=int)
        for split in core.split_indices(rows, folds):
            train, query = split["train"], split["query"]
            self.assertEqual((len(train), len(query)), (640, 80))
            self.assertTrue({rows[i]["concept"] for i in train}.isdisjoint({rows[i]["concept"] for i in query}))
            self.assertTrue({rows[i]["session"] for i in train}.isdisjoint({rows[i]["session"] for i in query}))
            coverage[query] += 1
        np.testing.assert_array_equal(coverage, np.ones(1200, dtype=int))
        self.assertEqual(folds, core.concept_folds(list(reversed(features))))

    def test_predictor_scaling_is_train_only_and_constant_safe(self):
        train = np.array([[1., 7.], [3., 7.]])
        tx, qx, mean, scale = core.scale_predictors(train, np.array([[1001., 7.]]))
        np.testing.assert_array_equal(mean, [2., 7.])
        np.testing.assert_array_equal(scale, [1., 1.])
        np.testing.assert_array_equal(tx, [[-1., 0.], [1., 0.]])
        np.testing.assert_array_equal(qx, [[999., 0.]])
        other = core.scale_predictors(train, np.array([[-1e10, 9.]]))
        np.testing.assert_array_equal(other[0], tx)
        np.testing.assert_array_equal(other[2], mean)

    def test_ridge_intercept_is_unpenalized_hand_solution(self):
        x = np.array([[-1., 1.], [0., 1.], [1., 1.]])
        y = np.array([[4.], [5.], [6.]])
        actual = core.ridge_predict(x, np.array([[-2., 1.], [2., 1.]]), y)
        np.testing.assert_allclose(actual[:, 0], [5 - 4/3, 5 + 4/3], atol=1e-14)
        shifted = core.ridge_predict(x, np.array([[-2., 1.], [2., 1.]]), y + 10000)
        np.testing.assert_allclose(shifted, actual + 10000, atol=1e-12)

    def test_negative_heldout_increment_is_valid_and_unclipped(self):
        # Adding a direction helps training but predicts the held-out sign wrong.
        pred = core.ridge_predict(np.array([[-1.], [1.]]), np.array([[1.]]), np.array([[-1.], [1.]]))[0, 0]
        increment = 1.0 - (-1.0 - pred) ** 2
        self.assertAlmostEqual(increment, -16/9)
        nums = np.full((3, 1, 2), increment)
        sst = np.ones((1, 2))
        masks = {"V1": np.array([True, False]), "IT": np.array([False, True])}
        report, _ = core.aggregate_contributions(nums, sst, masks, np.ones((4, 1), dtype=np.uint32))
        self.assertEqual(report["V1"]["metrics"]["joint"]["status"], "defined")
        self.assertAlmostEqual(report["V1"]["metrics"]["joint"]["value"], -16/9)

    def test_macro_ratios_and_pooled_errors_are_distinct_estimands(self):
        # Hand answer: macro=(1/1 + 20/100)/2=.6; pooled=21/101.
        sst = np.array([[.5, 50.], [.5, 50.]])
        num = np.repeat(np.array([[[.5, 10.], [.5, 10.]]]), 3, axis=0)
        masks = {"V1": np.array([True, True]), "IT": np.array([True, True])}
        counts = np.array([[2, 0], [1, 1], [0, 2]], dtype=np.uint32)
        macro, _ = core.aggregate_contributions(num, sst, masks, counts)
        pooled, _ = core._pooled({r: num.sum(axis=2) for r in core.ROIS},
                                 {r: sst.sum(axis=1) for r in core.ROIS}, counts)
        self.assertAlmostEqual(macro["V1"]["metrics"]["joint"]["value"], .6)
        self.assertAlmostEqual(pooled["V1"]["joint"]["value"], 21/101)
        self.assertNotEqual(macro["V1"]["metrics"]["joint"]["value"], pooled["V1"]["joint"]["value"])

    def test_zero_sst_voxel_does_not_disappear_from_primary(self):
        sst = np.array([[1., 0.], [1., 0.]])
        num = np.ones((3, 2, 2))
        masks = {r: np.array([True, True]) for r in core.ROIS}
        report, draws = core.aggregate_contributions(num, sst, masks, np.ones((3, 2), dtype=np.uint32))
        m = report["V1"]["metrics"]["joint"]
        self.assertIsNone(m["value"])
        self.assertEqual(m["status"], "undefined_voxel_sst")
        self.assertEqual(m["defined_voxel_mean_diagnostic"], 1.)
        self.assertEqual(report["V1"]["support"]["all_voxels"], 2)
        self.assertTrue(np.isnan(draws["V1"]["joint"]).all())

    def test_reliability_uses_training_concepts_and_sessions_only(self):
        subjects, features = fixture()
        s = subjects[0]
        split = core.split_indices(s["rows"], core.concept_folds(list(features)))[0]
        train = split["train"]
        concepts = sorted({s["rows"][i]["concept"] for i in train})
        first = core.raw_reliability(s["responses"], s["rows"], train, concepts)
        changed = s["responses"].copy()
        excluded = np.ones(len(changed), dtype=bool)
        excluded[train] = False
        changed[excluded] = 1e8 * np.arange(excluded.sum())[:, None]
        second = core.raw_reliability(changed, s["rows"], train, concepts)
        np.testing.assert_array_equal(first, second)
        zero = np.zeros_like(changed)
        self.assertTrue(np.isnan(core.raw_reliability(zero, s["rows"], train, concepts)).all())

    def test_common_bin_weights_and_undefined_support(self):
        r = np.array([-.5, .1, .1, .8, np.nan, -.3, .2, .9])
        masks = {"V1": np.arange(8) < 5, "IT": np.arange(8) >= 5}
        weights, support = core.shared_bin_weights(r, masks)
        np.testing.assert_allclose(weights["V1"], [1/3, 1/6, 1/6, 1/3, 0, 0, 0, 0])
        np.testing.assert_allclose(weights["IT"], [0, 0, 0, 0, 0, 1/3, 1/3, 1/3])
        self.assertEqual(support["undefined_reliability_voxels"]["V1"], 1)
        self.assertEqual(support["weighted_voxels"]["V1"], 4)
        # Exact boundaries are assigned to the right-hand interval, including 1.
        boundary = np.array([-1., 0., .25, .5, .75, 1.])
        full = {roi: np.ones(6, dtype=bool) for roi in core.ROIS}
        _, b = core.shared_bin_weights(boundary, full)
        self.assertEqual(list(b["bin_counts"]["V1"].values()), [1, 1, 1, 1, 2])
        w, no = core.shared_bin_weights(np.array([-.5, .5]),
                    {"V1": np.array([True, False]), "IT": np.array([False, True])})
        self.assertFalse(no["supported"])
        self.assertTrue(all((a == 0).all() for a in w.values()))

    def test_concept_bootstrap_preserves_repetition_contributions_and_undefined_draws(self):
        c = core.bootstrap_multiplicities(["a", "b", "c", "d", "e"], 17)
        np.testing.assert_array_equal(c.sum(axis=1), np.full(17, 5))
        np.testing.assert_array_equal(c, core.bootstrap_multiplicities(["a", "b", "c", "d", "e"], 17))
        repetitions = np.arange(60.).reshape(5, 12)
        by_concept = repetitions.sum(axis=1)
        for row in c:
            # This direct expansion confirms all 12 rows move with a concept.
            expanded = np.concatenate([np.tile(repetitions[i], int(n)) for i, n in enumerate(row)])
            self.assertEqual(float(row @ by_concept), float(expanded.sum()))
        m = core._interval(1.0, np.array([1., np.nan, 2.]))
        self.assertEqual(m["status"], "undefined_resample_support")
        self.assertEqual(m["undefined_draws"], 1)
        self.assertIsNone(m["lower"])
        self.assertIsNone(m["upper"])

    def test_weighted_pooled_like_estimand_comparator(self):
        # Unequal per-voxel denominators make unweighted pooled=21/101. Equal
        # common-bin weights are .25,.25,.5 in V1, changing only pooled weights.
        masks = {"V1": np.array([1, 1, 1, 0, 0], dtype=bool),
                 "IT": np.array([0, 0, 0, 1, 1], dtype=bool)}
        w, support = core.shared_bin_weights(np.array([.1, .1, .8, .1, .8]), masks)
        self.assertTrue(support["supported"])
        np.testing.assert_array_equal(w["V1"], [.25, .25, .5, 0, 0])
        num = np.array([1., 1., 20., 1., 1.])
        den = np.array([1., 1., 100., 1., 1.])
        weighted = float(num @ w["V1"] / (den @ w["V1"]))
        unweighted = float(num[masks["V1"]].sum() / den[masks["V1"]].sum())
        self.assertAlmostEqual(weighted, 10.5/50.5)
        self.assertAlmostEqual(unweighted, 22/102)
        self.assertNotEqual(weighted, unweighted)

    def test_strict_complete_panel_and_subject_isolation(self):
        subjects, features = fixture(100, ("01", "02", "03"))
        report = core.analyze(subjects, features)
        self.assertTrue(report["strict_benchmark_panel"])
        self.assertEqual(report["cohort"]["subject_ids"], ["01", "02", "03"])
        self.assertEqual(report["bootstrap"]["draws"], 1000)
        self.assertEqual(report["participants"][0]["rows"], 1200)
        self.assertEqual(len(report["participants"][0]["fold_support"]), 15)
        self.assertEqual(report["participants"][0]["voxel_support"]["V1"]["all_voxels"], 2)
        self.assertEqual(report["participants"][0]["reliability_control_support"]["folds_with_common_bins"], 15)
        json.dumps(report, allow_nan=False)
        # The same voxel IDs in different people are legal, but responses from
        # another person cannot change this participant's fits or uncertainty.
        isolated = core.analyze([subjects[0]], features, draws=1000, strict=False)
        self.assertEqual(report["participants"][0], isolated["participants"][0])
        for method in core.METHODS:
            for metric in core.METRICS:
                vals = [p["it_minus_v1"][method][metric]["value"] for p in report["participants"]]
                self.assertAlmostEqual(report["group_descriptive"]["it_minus_v1"][method][metric]["value"], sum(vals)/3)

    def test_row_order_invariance_and_invalid_panel_rejection(self):
        subjects, features = fixture()
        baseline = core.analyze(subjects, features, draws=11, strict=False)
        s = copy.deepcopy(subjects)
        order = np.arange(119, -1, -1)
        s[0]["responses"] = s[0]["responses"][order]
        s[0]["rows"] = [s[0]["rows"][i] for i in order]
        self.assertEqual(baseline, core.analyze(s, dict(reversed(list(features.items()))), draws=11, strict=False))
        missing = copy.deepcopy(subjects)
        missing[0]["rows"] = missing[0]["rows"][:-1]
        missing[0]["responses"] = missing[0]["responses"][:-1]
        with self.assertRaises(core.CoreError):
            core.analyze(missing, features, draws=11, strict=False)
        with self.assertRaises(core.CoreError):
            core.analyze(subjects, features)  # no silent strict cohort relaxation
        duplicate = copy.deepcopy(subjects)
        duplicate[0]["rows"][0]["trial_id"] = duplicate[0]["rows"][1]["trial_id"]
        with self.assertRaises(core.CoreError):
            core.analyze(duplicate, features, draws=11, strict=False)
        wrong = copy.deepcopy(subjects)
        wrong[0]["rows"][0]["image"] = "wrong-photo"
        with self.assertRaises(core.CoreError):
            core.analyze(wrong, features, draws=11, strict=False)

    def test_complete_constant_response_panel_is_explicitly_undefined(self):
        subjects, features = fixture()
        for constant in (7.0, .1, .3, 1.1):
            with self.subTest(constant=constant):
                subjects[0]["responses"][:] = constant
                report = core.analyze(subjects, features, draws=9, strict=False)
                p = report["participants"][0]
                for roi in core.ROIS:
                    self.assertEqual(p["voxel_support"][roi]["zero_sst_voxels"], 2)
                    for metric in core.METRICS:
                        self.assertIsNone(p["roi_metrics"]["macro_primary"][roi][metric]["value"])
                        self.assertEqual(p["roi_metrics"]["unweighted_pooled"][roi][metric]["status"],
                                         "undefined_zero_total_sst")
                        self.assertEqual(p["roi_metrics"]["reliability_weighted_pooled"][roi][metric]["status"],
                                         "undefined_common_reliability_bins")
                    for fold in p["fold_support"]:
                        self.assertEqual(fold["reliability"]["undefined_reliability_voxels"][roi], 2)
                self.assertEqual(p["reliability_control_support"]["folds_with_common_bins"], 0)
                json.dumps(report, allow_nan=False)
        invalid = copy.deepcopy(features)
        invalid["c000"]["animacy"] = True
        with self.assertRaises(core.CoreError):
            core.analyze(subjects, invalid, draws=9, strict=False)

    def test_decimal_constant_training_center_and_nonconstant_query_error(self):
        train_x = np.full((80, 2), .1)
        query_x = np.array([[.1, .1], [.2, .1]])
        tx, qx, mean, scale = core.scale_predictors(train_x, query_x)
        np.testing.assert_array_equal(tx, np.zeros((80, 2)))
        np.testing.assert_array_equal(mean, [.1, .1])
        np.testing.assert_array_equal(scale, [1., 1.])
        # Exact constant training responses retain the original intercept;
        # a different query observation must still contribute a positive SST.
        pred = core.ridge_predict(tx, qx, np.full((80, 1), .3))
        np.testing.assert_array_equal(pred, np.full((2, 1), .3))
        truth = np.array([[.3], [.8]])
        self.assertEqual(float(np.sum((truth - pred) ** 2)), .25)
        # No tolerance-based deletion: a genuinely varying decimal predictor
        # must remain varying even when its variation is very small.
        near = np.array([[.1], [.1 + 1e-12], [.1 - 1e-12]])
        centered, _, _, near_scale = core.scale_predictors(near, near)
        self.assertGreater(float(near_scale[0]), 0)
        self.assertLess(float(near_scale[0]), 1e-10)
        self.assertGreater(float(np.ptp(centered[:, 0])), 1)


if __name__ == "__main__":
    print(f"Generated arrays only; NumPy {np.__version__}")
    unittest.main(verbosity=2)
