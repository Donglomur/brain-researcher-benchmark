import importlib.util
import itertools
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("figure5_baseline", Path(__file__).parents[1] / "baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def fixture():
    a, b, c = np.array(list(itertools.product((-1., 1.), repeat=3))).T
    # Orthogonal factorial columns yield exact independent coefficient/R2 oracles.
    columns = {"oef": .4 + .1 * a, "cbf": .75 * (40 + 2 * b),
               "cbv": 4 + .5 * c, "cmro2": 100 + 10 * a + 4 * b + 3 * c + 2 * a * b}
    maps = {name: np.tile(np.tile(values, 2), (40, 1)) for name, values in columns.items()}
    masks = {f"{s}.{block}": np.zeros(16, dtype=bool)
             for s in baseline.STRATA for block in baseline.BLOCKS}
    for task in ("calc", "mem"):
        masks[f"concordant.{task}.positive"][:8] = True
        masks[f"discordant.{task}.negative"][8:] = True
    return np.arange(16), maps, masks


class BaselineTests(unittest.TestCase):
    def test_orthogonal_oracle_and_overlap_preserved(self):
        indices, maps, masks = fixture()
        result = baseline.evaluate_baseline(baseline.SUBJECTS, indices, maps, masks)
        for stratum, fit in result["baseline_cells"].items():
            self.assertEqual(fit["n_fit_rows"], 16)
            self.assertEqual(fit["unique_physical_voxels"], 8)
            self.assertEqual(fit["repeated_task_voxel_rows"], 8)
            self.assertEqual(fit["df_residual"], 12)
            self.assertAlmostEqual(fit["coefficients"]["intercept"], 100)
            self.assertAlmostEqual(fit["coefficients"]["oef"], 100)
            self.assertAlmostEqual(fit["coefficients"]["cbf"], 2)
            self.assertAlmostEqual(fit["coefficients"]["cbv"], 6)
            self.assertAlmostEqual(fit["sse"], 64)
            self.assertAlmostEqual(fit["r_squared_centered_with_intercept"], 125 / 129)
            self.assertAlmostEqual(fit["f_statistic"], 125)
        self.assertFalse(result["full_figure5_reproduction_established"])
        self.assertFalse(result["paper_improvement_established"])

    def test_subject_median_and_cbf_scaling_order(self):
        indices, maps, masks = fixture()
        maps["cbf"] += (np.arange(40) - 19.5)[:, None]
        maps["oef"][0, 0] = np.nan
        panels = baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)
        panel = panels["concordant"]
        self.assertEqual(panel["subject_support"]["oef"][0], 39)
        self.assertAlmostEqual(panel["columns"]["cbf"][0], 38)
        self.assertEqual(panel["row_ids"][0], ("calc.positive", 0))
        self.assertEqual(panel["row_ids"][8], ("mem.positive", 0))

    def test_centering_precedes_joint_missing_exclusion(self):
        a, b, c = np.array(list(itertools.product((-1., 1.), repeat=3))).T
        y = 100 + 10 * a + 4 * b + 3 * c
        y[0] = np.nan
        panel = {"row_ids": [("calc.positive", i) for i in range(8)],
                 "columns": {"cmro2": y, "oef": a, "cbf": b, "cbv": c}}
        fit = baseline.fit_baseline_panel(panel)
        self.assertEqual(fit["n_fit_rows"], 7)
        self.assertEqual(fit["n_excluded_other_joint_missing"], 1)
        self.assertEqual(fit["predictor_means_before_joint_exclusion"], {"oef": 0., "cbf": 0., "cbv": 0.})
        self.assertAlmostEqual(fit["coefficients"]["intercept"], 100)

    def test_all_nan_voxel_retained_until_joint_exclusion(self):
        indices, maps, masks = fixture()
        maps["cmro2"][:, 0] = np.nan
        panel = baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)["concordant"]
        self.assertEqual(panel["subject_support"]["cmro2"][0], 0)
        fit = baseline.fit_baseline_panel(panel)
        self.assertEqual(fit["n_source_rows"], 16)
        self.assertEqual(fit["n_fit_rows"], 14)
        self.assertEqual(fit["n_excluded_other_joint_missing"], 2)

    def test_source_thresholds_are_strict_and_precede_centering(self):
        indices, maps, masks = fixture()
        maps["cmro2"][:, 0] = 351  # excluded twice, once per source task mask
        maps["oef"][:, 1] = 1.01   # excluded twice
        maps["cmro2"][:, 2] = 350  # source > threshold, equality remains
        maps["oef"][:, 3] = 1.0    # source > threshold, equality remains
        panel = baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)["concordant"]
        fit = baseline.fit_baseline_panel(panel)
        self.assertEqual(fit["n_excluded_source_threshold"], 4)
        self.assertEqual(fit["n_excluded_other_joint_missing"], 0)
        self.assertEqual(fit["n_fit_rows"], 12)
        self.assertAlmostEqual(fit["predictor_means_before_joint_exclusion"]["oef"], 3.3 / 6)

    def test_reject_changed_cohort_and_overlapping_same_task_classes(self):
        indices, maps, masks = fixture()
        with self.assertRaisesRegex(ValueError, "primary40"):
            baseline.prepare_baseline(baseline.SUBJECTS[:30], indices, maps, masks)
        masks["discordant.calc.positive"][0] = True
        with self.assertRaisesRegex(ValueError, "overlapping"):
            baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)

    def test_reject_rank_deficiency_and_row_collision(self):
        indices, maps, masks = fixture()
        maps["cbv"][:] = 4
        panel = baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)["concordant"]
        with self.assertRaisesRegex(ValueError, "rank-deficient"):
            baseline.fit_baseline_panel(panel)
        panel["row_ids"][1] = panel["row_ids"][0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            baseline.fit_baseline_panel(panel)

    def test_reject_multi_column_predictor(self):
        indices, maps, masks = fixture()
        panel = baseline.prepare_baseline(baseline.SUBJECTS, indices, maps, masks)["concordant"]
        panel["columns"]["oef"] = np.tile(panel["columns"]["oef"][:, None], (1, 2))
        with self.assertRaisesRegex(ValueError, "one-dimensional"):
            baseline.fit_baseline_panel(panel)

    def test_exact_zero_residual_f_is_explicit_positive_infinity(self):
        a, b, c = np.array(list(itertools.product((-1., 1.), repeat=3))).T
        panel = {"row_ids": [("calc.positive", i) for i in range(8)],
                 "columns": {"cmro2": 100 + 10 * a + 4 * b + 3 * c,
                             "oef": a, "cbf": b, "cbv": c}}
        # The exact mathematical solve isolates zero-residual serialization from
        # incidental SVD roundoff. The ordinary solver is tested above.
        with patch.object(baseline.np.linalg, "lstsq", return_value=(np.array([100., 10., 4., 3.]), [], 4, [])):
            fit = baseline.fit_baseline_panel(panel)
        self.assertEqual(fit["r_squared_centered_with_intercept"], 1.)
        self.assertIsNone(fit["f_statistic"])
        self.assertEqual(fit["f_statistic_nonfinite"], "positive_infinity_perfect_fit")


if __name__ == "__main__":
    unittest.main()
