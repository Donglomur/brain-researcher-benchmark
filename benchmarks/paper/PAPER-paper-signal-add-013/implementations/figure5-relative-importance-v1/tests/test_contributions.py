import importlib.util
import itertools
import json
from pathlib import Path
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bold_contributions", HERE / "contributions.py")
contributions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contributions)
# The maintained test expects its existing neighboring implementation. Private
# construction may supply a minimal exact-hash mirror through the environment.
import os
BASELINE = Path(os.environ.get("BOLD_BASELINE_PATH", str(HERE.parent / "figure5-baseline-v1" / "baseline.py")))
baseline = contributions._baseline(BASELINE)


def fixture(correlated=False):
    a, b, c, d = np.array(list(itertools.product((-1., 1.), repeat=4))).T
    if correlated:
        columns = {"oef": .4 + .1 * a, "cbf": .75 * (40 + 2 * (a + b)),
                   "cbv": 4 + .5 * c, "cmro2": 100 + 10 * a + 5 * d}
    else:
        columns = {"oef": .4 + .1 * a, "cbf": .75 * (40 + 2 * b),
                   "cbv": 4 + .5 * c, "cmro2": 100 + 10 * a + 4 * b + 3 * c + 2 * d}
    maps = {name: np.tile(np.tile(value, 2), (40, 1)) for name, value in columns.items()}
    masks = {f"{s}.{block}": np.zeros(32, dtype=bool)
             for s in baseline.STRATA for block in baseline.BLOCKS}
    for task in ("calc", "mem"):
        masks[f"concordant.{task}.positive"][:16] = True
        masks[f"discordant.{task}.negative"][16:] = True
    return np.arange(32), maps, masks


def evaluate(*args):
    return contributions.evaluate_baseline_contributions(baseline.SUBJECTS, *args, baseline_path=BASELINE)


class ContributionTests(unittest.TestCase):
    def test_factorial_absolute_and_percentage_units(self):
        result = evaluate(*fixture())
        for panel in result["baseline_cells"].values():
            values = panel["contributions"]
            for name, numerator, percent in (("oef", 100, 80), ("cbf", 16, 12.8), ("cbv", 9, 7.2)):
                self.assertAlmostEqual(values["relimp"][name], numerator / 129)
                self.assertAlmostEqual(values["relimp_perc"][name], percent)
            self.assertAlmostEqual(sum(values["relimp"].values()), 125 / 129)
            self.assertEqual(len(panel["subset_fits"]), 8)
            self.assertEqual(len(values["ordered_increments"]), 6)
            self.assertEqual(panel["fit_support"]["n_fit_rows"], 32)
            self.assertEqual(len(set(row[1] for row in panel["fit_support"]["fitted_row_ids"])), 16)
        self.assertFalse(result["paper_improvement_established"])
        self.assertFalse(result["full_figure5_reproduction_established"])
        json.dumps(result, allow_nan=False)

    def test_correlated_predictor_share_is_not_squared_coefficient(self):
        result = evaluate(*fixture(correlated=True))
        for panel in result["baseline_cells"].values():
            values = panel["contributions"]
            self.assertAlmostEqual(values["relimp"]["oef"], .6)
            self.assertAlmostEqual(values["relimp"]["cbf"], .2)
            self.assertAlmostEqual(values["relimp"]["cbv"], 0)
            self.assertAlmostEqual(values["relimp_perc"]["oef"], 75)
            self.assertAlmostEqual(values["relimp_perc"]["cbf"], 25)
            # CBF's conditional full-model coefficient is zero, yet it has a
            # positive order-averaged share through information shared with OEF.
            self.assertAlmostEqual(panel["reference_full_fit"]["coefficients"]["cbf"], 0)

    def test_source_target_only_missing_preserves_pre_drop_centering(self):
        indices, maps, masks = fixture()
        maps["cmro2"][:, 0] = np.nan
        result = evaluate(indices, maps, masks)
        panel = result["baseline_cells"]["concordant"]
        self.assertEqual(panel["fit_support"]["n_fit_rows"], 30)
        self.assertAlmostEqual(panel["predictor_means_before_joint_exclusion"]["oef"], .4)
        self.assertNotEqual(np.mean(np.array(panel["centered_predictor_rows"]), axis=0)[0], 0)
        self.assertEqual(panel["fit_support"]["fitted_row_ids_sha256"],
                         panel["reference_full_fit"]["retained_row_ids_sha256"])

    def test_predictor_only_missing_refuses_silent_joint_drop(self):
        indices, maps, masks = fixture()
        maps["oef"][:, 0] = np.nan
        # The earlier statsmodels baseline is still defined on joint complete
        # rows; source Pingouin x/y are not the same length in this case.
        baseline.evaluate_baseline(baseline.SUBJECTS, indices, maps, masks)
        with self.assertRaisesRegex(ValueError, "separate-dropna"):
            evaluate(indices, maps, masks)

    def test_joint_missing_and_whole_row_threshold_are_explicit(self):
        indices, maps, masks = fixture()
        maps["oef"][:, 0] = np.nan
        maps["cmro2"][:, 0] = np.nan
        maps["cmro2"][:, 1] = 351
        result = evaluate(indices, maps, masks)
        panel = result["baseline_cells"]["concordant"]
        self.assertEqual(panel["fit_support"]["n_fit_rows"], 28)
        self.assertEqual(panel["reference_full_fit"]["n_excluded_source_threshold"], 2)
        self.assertEqual(panel["reference_full_fit"]["n_excluded_other_joint_missing"], 2)

    def test_strata_remain_separate(self):
        indices, maps, masks = fixture()
        a, b, c, d = np.array(list(itertools.product((-1., 1.), repeat=4))).T
        maps["cmro2"][:, 16:] = 100 + 10 * a + 4 * b + 3 * c + 10 * d
        result = evaluate(indices, maps, masks)
        self.assertAlmostEqual(result["baseline_cells"]["concordant"]["contributions"]["full_model_centered_r_squared"], 125 / 129)
        self.assertAlmostEqual(result["baseline_cells"]["discordant"]["contributions"]["full_model_centered_r_squared"], 125 / 225)
        self.assertNotIn("combined_score", result)

    def test_complete_subset_family_and_nested_support_consistency(self):
        subsets = {tuple(c): 0.1 * len(c) for n in range(4)
                   for c in itertools.combinations(contributions.PREDICTORS, n)}
        result = contributions.decompose_baseline_r_squared(subsets)
        self.assertTrue(all(abs(v - .1) < 1e-12 for v in result["relimp"].values()))
        changed = dict(subsets)
        del changed[("oef", "cbv")]
        with self.assertRaisesRegex(ValueError, "all eight"):
            contributions.decompose_baseline_r_squared(changed)
        changed = dict(subsets)
        changed[("oef",)] = .4
        with self.assertRaisesRegex(ValueError, "decreased"):
            contributions.decompose_baseline_r_squared(changed)

    def test_zero_explained_variance_has_no_percentages(self):
        subsets = {tuple(c): 0.0 for n in range(4)
                   for c in itertools.combinations(contributions.PREDICTORS, n)}
        result = contributions.decompose_baseline_r_squared(subsets)
        self.assertEqual(result["relimp_perc"], dict.fromkeys(contributions.PREDICTORS))
        self.assertEqual(result["percentage_undefined_reason"], "nonpositive_full_r_squared")
        json.dumps(result, allow_nan=False)

    def test_baseline_dependency_and_changed_cohort_refused(self):
        with self.assertRaisesRegex(ValueError, "identity changed"):
            contributions._baseline(HERE / "contributions.py")
        with self.assertRaisesRegex(ValueError, "primary40"):
            contributions.evaluate_baseline_contributions(baseline.SUBJECTS[:30], *fixture(), baseline_path=BASELINE)


if __name__ == "__main__":
    unittest.main()
