import importlib.util
from pathlib import Path
import unittest

import numpy as np

_path = Path(__file__).resolve().parents[1] / "spatial.py"
_spec = importlib.util.spec_from_file_location("opm_spatial", _path)
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)


def operands():
    c = np.diag([4., 2., 1.])
    active = np.diag([1., 4., 2.])
    control = np.diag([3., 1., 2.])
    first = np.array([[1., 0.], [0., 2.], [0., 0.]])
    second = np.array([[0., 0.], [1., 0.], [0., 2.]])
    return c, active, control, np.stack((first, second), axis=2)


class SpatialTests(unittest.TestCase):
    def test_analytic_map_selects_suppression_not_absolute_peak(self):
        c, a, b, l = operands()
        result = s.pseudo_t_map(c, a, b, l)
        np.testing.assert_allclose(result, [-1., 1.2])
        peak = s.select_peak(result, ["low", "high"], [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(peak["voxel_id"], "low")
        self.assertEqual(peak["position_m"], [1., 2., 3.])

    def test_source_covariance_includes_between_trial_variation(self):
        trials = np.array([[[1, 10], [2, 20]], [[3, 30], [4, 40]]], dtype=float)
        rows = np.array([[1, 3], [2, 4], [10, 30], [20, 40]], dtype=float)
        centered = rows - rows.mean(axis=0)
        np.testing.assert_allclose(s.covariance_from_trials(trials), centered.T @ centered / 3)
        within = np.mean([np.cov(trials[:, :, r], ddof=1) for r in range(2)], axis=0)
        self.assertFalse(np.allclose(s.covariance_from_trials(trials), within))

    def test_channel_permutation_preserves_complete_map(self):
        c, a, b, l = operands()
        order = [2, 0, 1]
        np.testing.assert_allclose(s.pseudo_t_map(c, a, b, l),
            s.pseudo_t_map(c[np.ix_(order, order)], a[np.ix_(order, order)],
                           b[np.ix_(order, order)], l[order]))

    def test_common_covariance_scale_leaves_pseudo_t_unchanged(self):
        c, a, b, l = operands()
        np.testing.assert_allclose(s.pseudo_t_map(c, a, b, l), s.pseudo_t_map(c*17, a*17, b*17, l))

    def test_exact_voxel_ties_keep_first_in_supplied_order(self):
        p = s.select_peak([-1., -1., 0.], ["z", "a", "b"], np.zeros((3, 3)))
        self.assertEqual(p["voxel_id"], "z")
        self.assertEqual(p["exact_minimum_tie_count"], 2)

    def test_virtual_electrode_has_source_noise_norm_and_trial_order(self):
        c, _, _, l = operands()
        trials = np.arange(3*7*2).reshape(3, 7, 2)
        ve = s.virtual_electrode(trials, c, l[:, :, 0])
        np.testing.assert_allclose(abs(ve), trials[0])
        self.assertEqual(ve.shape, (7, 2))

    def test_cross_condition_covariance_is_not_reused(self):
        l = np.array([[1., 0.], [1., 2.], [0., 1.]])
        a = s.source_weight(np.diag([1., 2., 5.]), l)
        b = s.source_weight(np.diag([5., 2., 1.]), l)
        self.assertFalse(np.allclose(np.outer(a/np.linalg.norm(a), a/np.linalg.norm(a)),
                                     np.outer(b/np.linalg.norm(b), b/np.linalg.norm(b))))

    def test_tangential_axes_and_common_translation(self):
        cart = np.eye(3)[:, :, None]
        positions = np.array([[1., 0., 0.]])
        mesh = np.array([[-1., 0., 0.], [1., 0., 0.]])
        result = s.tangential_lead_fields(cart, positions, mesh)
        np.testing.assert_allclose(result[:, :, 0], [[0, 0], [0, 1], [-1, 0]], atol=1e-15)
        np.testing.assert_allclose(result, s.tangential_lead_fields(cart, positions+7, mesh+7))
        with self.assertRaises(s.SourceKernelError):
            s.tangential_lead_fields(cart, [[0, 0, 0]], mesh)

    def test_undefined_orientations_are_not_silently_patched(self):
        for l in (np.array([[1., 1.], [0., 0.], [0., 0.]]), np.eye(3)[:, :2]):
            with self.assertRaises(s.SourceKernelError):
                s.source_weight(np.eye(3), l)

    def test_undefined_voxel_aborts_instead_of_dropping_support(self):
        c, a, b, l = operands()
        l[:, :, 1] = 0
        with self.assertRaises(s.SourceKernelError):
            s.pseudo_t_map(c, a, b, l)
        with self.assertRaises(s.SourceKernelError):
            s.pseudo_t_map(c, np.zeros_like(c), np.zeros_like(c), operands()[3])

    def test_bad_covariance_and_wrong_orientation_count_refused(self):
        c, a, b, l = operands()
        for bad in (np.zeros((3, 3)), np.diag([-1., 2., 3.]),
                    c+np.triu(np.ones((3, 3)), 1), c.astype(complex), np.full((3, 3), np.nan)):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(s.SourceKernelError):
                    s.pseudo_t_map(bad, a, b, l)
        with self.assertRaises(s.SourceKernelError):
            s.pseudo_t_map(c, a, b, np.zeros((3, 3, 2)))

    def test_both_conditions_required_and_no_scientific_score(self):
        c, a, b, l = operands()
        ops = {"index": {"covariance": c, "active_covariance": a, "control_covariance": b},
               "pinky": {"covariance": c, "active_covariance": b, "control_covariance": a}}
        report = s.condition_maps(ops, l, ["v0", "v1"], [[1, 0, 0], [0, 1, 0]])
        self.assertEqual(report["conditions"]["index"]["peak"]["voxel_id"], "v0")
        self.assertEqual(report["conditions"]["pinky"]["peak"]["voxel_id"], "v1")
        self.assertIsNone(report["reproduction_score"])
        self.assertIsNone(report["improvement_score"])
        with self.assertRaises(s.SourceKernelError):
            s.condition_maps({"index": ops["index"]}, l, ["v0", "v1"], [[1, 0, 0], [0, 1, 0]])

    def test_identity_join_must_be_complete_unique_and_ordered(self):
        for ids, points in [(["v", "v"], [[0, 0, 0], [1, 1, 1]]),
                            (["v"], [[0, 0, 0]]), (["a", "b"], [[0, 0, 0]])]:
            with self.assertRaises(s.SourceKernelError):
                s.select_peak([-1., 1.], ids, points)


if __name__ == "__main__":
    unittest.main()
