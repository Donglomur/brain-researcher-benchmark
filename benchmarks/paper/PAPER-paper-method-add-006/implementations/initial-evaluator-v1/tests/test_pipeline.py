"""Bounded generated engineering controls; no empirical or native runs."""
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("pipeline_evaluator", MODULE_PATH)
ev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ev
spec.loader.exec_module(ev)


def fixture():
    cases = list(itertools.product([-10.0, 10.0], [-5.0, 5.0], [0, 1]))
    z = np.array([[p, -p / 2, 5, v, -v, 1, t] for p, v, t in cases] * 12, dtype=float)
    x = np.column_stack([2 + (z[:, 0] > 0) + z[:, 6], 1 + (z[:, 3] > 0) + (np.arange(len(z)) % 3)])
    return z, x


class PipelineTests(unittest.TestCase):
    def test_movement_and_rate_boundaries_are_distinct(self):
        z, x = fixture()
        z[0, 2], z[0, 3:5] = 4, [8, 0]
        z[1, 2], z[1, 3:5] = 5, [4, 0]
        _, _, source_rows, _ = ev.prepare_glm_session(z, x)
        _, _, geometry_rows, _ = ev.prepare_geometry_session(z, x, ["CA1", "CA1"], "CA1")
        self.assertFalse(source_rows[0])
        self.assertTrue(geometry_rows[0])
        self.assertTrue(source_rows[1])
        self.assertFalse(geometry_rows[1])
        z = np.tile(z[2], (20, 1))
        x = np.column_stack([np.r_[1, np.zeros(19)], np.ones(20)])
        self.assertEqual(ev.prepare_glm_session(z, x)[3].tolist(), [False, True])

    def test_train_only_fit_does_not_read_test_targets_or_fit_transforms(self):
        z, x = fixture()
        train, test = np.arange(64), np.arange(64, 96)
        params = ev.BasisParameters(10, 5, 100, 40, 1)
        first = ev.fit_train_only(z, x, train, test, params, 1)
        changed_x = x.copy()
        changed_x[test] = 900
        second = ev.fit_train_only(z, changed_x, train, test, params, 1)
        np.testing.assert_array_equal(first["predictions"], second["predictions"])
        self.assertFalse(np.array_equal(first["poisson_deviance_per_unit"], second["poisson_deviance_per_unit"]))
        changed_z = z.copy()
        changed_z[test, :2] += 800
        third = ev.fit_train_only(changed_z, x, train, test, params, 1)
        for key in ["position_mean", "design_mean", "design_std", "unit_mask"]:
            np.testing.assert_array_equal(first[key], third[key])
        for key in first["basis"]:
            np.testing.assert_array_equal(first["basis"][key], third["basis"][key])

    def test_source_cv_matches_independent_sklearn_scores(self):
        from sklearn.linear_model import PoissonRegressor
        from sklearn.model_selection import KFold, cross_val_score
        z, x = fixture()
        params = ev.BasisParameters(10, 5, 100, 40, 1)
        centered, eligible, _, _ = ev.prepare_glm_session(z, x)
        result = ev.source_glm_fit(z, x, centered, params, alphas=[0.5, 2.0], folds=3)
        basis = ev.fit_basis(centered, params)
        design = ev.design_matrix(centered, basis, params)
        design = (design - design.mean(0)) / design.std(0)
        for unit in range(2):
            for a, alpha in enumerate([0.5, 2.0]):
                independent = cross_val_score(PoissonRegressor(alpha=alpha), design, eligible[:, unit],
                                              cv=KFold(3, shuffle=False))
                np.testing.assert_allclose(result["cv_scores"][unit, a], independent, atol=2e-13)
        np.testing.assert_array_equal(result["selected_alpha_indices"], result["cv_scores"].mean(2).argmax(1))

    def test_null_mask_zero_score_and_invalid_fold_count(self):
        x = np.array([[0, 1, 1], [1, 2, 4], [2, 3, 2], [3, 4, 3]], dtype=float)
        scores = np.ones((3, 1, 10)) * 0.5
        scores[0, 0] = 0
        scores[1, 0, :2] = np.nan
        original = x.copy()
        result = ev.glm_geometry_summary(x, x, scores, np.zeros(3, dtype=int), [[[0, 1, 2], [0, 1, 2]]])
        self.assertEqual(result["suppressed_units"].tolist(), [0, 1])
        self.assertAlmostEqual(result["fitted_pr"], 1.0)
        np.testing.assert_array_equal(x, original)

    def test_no_subset_replacement_or_population_omission(self):
        with self.assertRaises(ev.ContractError):
            ev.glm_geometry_summary(np.ones((4, 2)), np.ones((4, 2)), np.ones((2, 1, 3)),
                                    np.array([0, 0]), [[[0, 0], [0, 1]]])
        rows = [{"animal": "KL8", "session": "s", "region": "CA1", "x": 1}]
        with self.assertRaises(ev.ContractError):
            ev.paired_region_contrast(rows, [("KL8", "s")], "x")

    def test_animal_macro_average_does_not_pool_unequal_session_counts(self):
        expected = [("a", "1"), ("a", "2"), ("b", "1")]
        rows = []
        for animal, session in expected:
            rows.extend([{"animal": animal, "session": session, "region": "CA1", "x": 2 if animal == "a" else 10},
                         {"animal": animal, "session": session, "region": "PFC", "x": 0}])
        self.assertEqual(ev.paired_region_contrast(rows, expected, "x")["mean_contrast"], 6)

    def test_covariance_validity_is_unit_scale_invariant(self):
        for scale in [1e-12, 1.0, 1e12]:
            with self.assertRaises(ev.ContractError):
                ev.geometry_from_covariance(scale*np.eye(2), 2*scale*np.eye(2), scale*np.eye(2))
            with self.assertRaises(ev.ContractError):
                ev.geometry_from_covariance(scale*np.array([[2, 0.5], [0, 2]]), scale*np.eye(2), scale*np.eye(2))

    def test_undefined_d2_still_checks_predictions(self):
        for y, prediction in [([1, 1], [0, 0]), ([0, 0], [-1, -1])]:
            with self.assertRaises(ev.ContractError):
                ev.poisson_d2(y, prediction)

    def test_manifest_rejects_missing_duplicate_and_unknown_population(self):
        manifest = {"source_revision": ev.SOURCE_REVISION, "dandiset_version": "0.240511.0307",
                    "sessions": [{"animal": a, "session_index": s, "epoch_id": f"epoch{s}",
                                  "path": f"{a}-{s}.npz", "sha256": "a"*64, "bytes": 1}
                                 for a in ev.ANIMALS for s in range(8)]}
        self.assertEqual(len(ev.validate_panel_manifest(manifest)), 64)
        missing = dict(manifest, sessions=manifest["sessions"][:-1])
        with self.assertRaises(ev.ContractError):
            ev.validate_panel_manifest(missing)
        manifest["sessions"][-1] = dict(manifest["sessions"][0])
        with self.assertRaises(ev.ContractError):
            ev.validate_panel_manifest(manifest)

    def test_cli_geometry_emits_no_qualification_and_valid_json(self):
        z = np.array(list(itertools.product([-1, 1], repeat=4)), dtype=float)
        responses, lat = z[:, :2] + z[:, 2:], z[:, :2]
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp)/"control.npz", Path(temp)/"result.json"
            np.savez(source, responses=responses, latents=lat)
            ev.main(["geometry", str(source), str(output)])
            result = json.loads(output.read_text())
            self.assertIs(result["research_qualified"], False)
            self.assertIs(result["full_contract_complete"], False)
            self.assertTrue(result["holds"])
            self.assertAlmostEqual(result["result"]["dimensionality"], 2)


if __name__ == "__main__":
    unittest.main()
