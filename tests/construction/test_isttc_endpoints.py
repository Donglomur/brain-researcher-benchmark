"""Independent generated controls for iSTTC source endpoints.

The balanced REML expectations follow orthogonal Walsh designs, independently
cross-checked against statsmodels MixedLM before this implementation existed.
These are source controls, not authentic biological or paper-reproduction data.
"""
import importlib.util
import copy
import math
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (ROOT / 'benchmarks/paper/PAPER-paper-method-add-004/implementations'
           / 'sensitivity-glm-v1')
SPEC = importlib.util.spec_from_file_location('isttc_endpoint_models_test', PACKAGE / 'models.py')
MODELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODELS)
METHODS = ('acf_full', 'isttc_full', 'pearsonr_trial_avg', 'sttc_trial_concat')
ENDPOINT_SPEC = importlib.util.spec_from_file_location('isttc_endpoints_test', PACKAGE / 'endpoints.py')
ENDPOINTS = importlib.util.module_from_spec(ENDPOINT_SPEC)
ENDPOINT_SPEC.loader.exec_module(ENDPOINTS)


def balanced_fixture():
    """N8, rank3; all five residual modes orthogonal to the fixed design."""
    x = np.array([-1, -1, -1, -1, 1, 1, 1, 1], dtype=float)
    z = np.array([-1, -1, 1, 1, -1, -1, 1, 1], dtype=float)
    w = np.array([-1, 1, -1, 1, -1, 1, -1, 1], dtype=float)
    raw = np.column_stack((10 + x, 2 + z))
    sd = math.sqrt(32 / 31)  # R scale over four copies of each unit, ddof=1.
    design = np.column_stack((np.ones(8), x / sd, z / sd))
    beta = np.array([[1., 1.2, .7, 1.5], [.1, .2, -.1, .3], [-.2, .1, .2, -.1]])
    modes = [x * z, x * w, z * w, x * z * w]
    residual = np.column_stack([.5 * w + .25 * mode for mode in modes])
    mice = ['a', 'a', 'a', 'b', 'c', 'c', 'd', 'd']
    return design @ beta + residual, raw, mice


class BalancedSourceModelTests(unittest.TestCase):
    def test_exact_interior_reml_and_source_treatment_coefficients(self):
        y, x, mice = balanced_fixture()
        result = MODELS.balanced_reml(y, x, mice, METHODS)
        # R'R/(8-3) = .4*11' + .1*I exactly; no optimizer is the oracle.
        expected = [1., .2, -.3, .5, .1, -.2, .1, -.2, .2, .3, .4, .1]
        np.testing.assert_allclose(result['coefficients'], expected, rtol=0, atol=2e-14)
        self.assertAlmostEqual(result['unit_intercept_variance'], .4, places=13)
        self.assertAlmostEqual(result['residual_variance'], .1, places=13)
        self.assertFalse(result['variance_boundary'])
        self.assertTrue(result['finite_nonsingular_gaussian_fit'])
        self.assertEqual(result['coefficient_names'][0], '(Intercept)')
        self.assertEqual(result['coefficient_names'][1], 'methodisttc_full')
        self.assertEqual(result['coefficient_names'][4:6], ['fr_s', 'alpha_s'])
        self.assertIsNone(result['source_p_values'])
        self.assertIsNone(result['source_profile_confidence_intervals'])
        self.assertFalse(result['scientifically_qualified'])
        self.assertFalse(result['native_lme4_parity_qualified'])

    def test_r_scaling_uses_expanded_long_rows(self):
        y, x, mice = balanced_fixture()
        full = MODELS.balanced_reml(y, x, mice, METHODS)
        trial = MODELS.balanced_reml(y[:, 2:], x, mice, METHODS[2:])
        np.testing.assert_allclose(full['covariate_center'], [10., 2.], rtol=0, atol=0)
        np.testing.assert_allclose(full['covariate_long_table_sample_sd'],
                                   [math.sqrt(32/31)] * 2, rtol=0, atol=1e-15)
        np.testing.assert_allclose(trial['covariate_long_table_sample_sd'],
                                   [math.sqrt(16/15)] * 2, rtol=0, atol=1e-15)
        self.assertNotAlmostEqual(full['covariate_long_table_sample_sd'][0], math.sqrt(8/7))
        self.assertEqual(trial['coefficient_names'][1], 'methodsttc_trial_concat')

    def test_mouse_cr1_matches_independent_fraction_control(self):
        y, x, mice = balanced_fixture()
        result = MODELS.balanced_reml(y, x, mice, METHODS)['mouse_cluster_diagnostic']
        # Fractions were computed by summing raw-coordinate linear influences
        # over mice sized3/1/2/2. An independent GLS+cov_cluster agreed at3.8e-16.
        expected_diagonal = [
            .020182291666666668, .016145833333333335, .03229166666666667,
            .016145833333333335, .020833333333333336, .07083333333333335,
            .016666666666666666, .03333333333333333, .016666666666666666,
            .05, .03333333333333333, .05,
        ]
        covariance = np.array(result['covariance'])
        np.testing.assert_allclose(np.diag(covariance), expected_diagonal, rtol=0, atol=2e-14)
        for i, j, value in [(0, 1, -.016145833333333335),
                            (0, 4, .012303137303143455),
                            (1, 2, .016145833333333335), (4, 5, -.0125),
                            (6, 9, 0.), (9, 10, 1/30), (10, 11, 1/30)]:
            self.assertAlmostEqual(covariance[i, j], value, places=13)
        self.assertAlmostEqual(result['correction'], 31/15)
        self.assertEqual(result['mouse_count'], 4)
        self.assertEqual(result['covariance_rank'], 3)
        self.assertFalse(result['source_lmerTest_inference'])
        self.assertFalse(result['coverage_qualified'])

    def test_neuron_ids_cannot_substitute_for_mouse_cluster_scores(self):
        y, x, mice = balanced_fixture()
        animals = MODELS.balanced_reml(y, x, mice, METHODS)
        neurons = MODELS.balanced_reml(y, x, [f'u{i}' for i in range(8)], METHODS)
        np.testing.assert_allclose(animals['coefficients'], neurons['coefficients'], rtol=0, atol=0)
        self.assertFalse(np.allclose(animals['mouse_cluster_diagnostic']['covariance'],
                                     neurons['mouse_cluster_diagnostic']['covariance']))

    def test_random_intercept_boundary_has_pooled_error_variance(self):
        x = np.array([-1, -1, -1, -1, 1, 1, 1, 1], dtype=float)
        z = np.array([-1, -1, 1, 1, -1, -1, 1, 1], dtype=float)
        w = np.array([-1, 1, -1, 1, -1, 1, -1, 1], dtype=float)
        design = np.column_stack((np.ones(8), x/math.sqrt(16/15), z/math.sqrt(16/15)))
        y = design @ np.array([[1., 1.2], [.1, .2], [-.2, .1]])
        y += np.column_stack((.25*w, -.25*w))
        result = MODELS.balanced_reml(y, np.column_stack((10+x, 2+z)),
                                      [f'm{i//2}' for i in range(8)], METHODS[2:])
        # S=.1[[1,-1],[-1,1]]; constrained REML maximum is unitvar0,errorvar.1.
        np.testing.assert_allclose(result['coefficients'], [1., .2, .1, -.2, .1, .3],
                                   rtol=0, atol=2e-14)
        self.assertEqual(result['unit_intercept_variance'], 0.)
        self.assertAlmostEqual(result['residual_variance'], .1, places=13)
        self.assertTrue(result['variance_boundary'])

    def test_exact_zero_residual_is_explicit_without_epsilon(self):
        _, x, mice = balanced_fixture()
        result = MODELS.balanced_reml(np.zeros((8, 4)), x, mice, METHODS)
        self.assertEqual(result['residual_variance'], 0.)
        self.assertEqual(result['unit_intercept_variance'], 0.)
        self.assertTrue(result['degenerate_zero_residual_variance'])
        self.assertFalse(result['finite_nonsingular_gaussian_fit'])
        self.assertIsNone(result['source_p_values'])

    def test_nonzero_unrepresentable_variance_is_not_exact_degeneracy(self):
        y, x, mice = balanced_fixture()
        with self.assertRaises(ValueError):
            MODELS.balanced_reml(y * 1e-170, x, mice, METHODS)

    def test_covariance_underflow_is_unavailable_not_zero_uncertainty(self):
        y, x, mice = balanced_fixture()
        result = MODELS.balanced_reml(y * 1e-161, x, mice, METHODS)
        self.assertGreater(result['residual_variance'], 0.)
        diagnostic = result['mouse_cluster_diagnostic']
        self.assertEqual(diagnostic['status'], 'unavailable')
        self.assertEqual(diagnostic['reason'], 'positive_covariance_underflow')
        self.assertIsNone(diagnostic['covariance'])
        self.assertIsNone(diagnostic['standard_errors'])

    def test_one_mouse_keeps_fit_but_has_no_cluster_uncertainty(self):
        y, x, _ = balanced_fixture()
        result = MODELS.balanced_reml(y, x, ['same-mouse']*8, METHODS)
        diagnostic = result['mouse_cluster_diagnostic']
        self.assertEqual(diagnostic['status'], 'unavailable')
        self.assertEqual(diagnostic['reason'], 'fewer_than_two_biological_mice')
        self.assertIsNone(diagnostic['covariance'])
        self.assertIsNone(diagnostic['standard_errors'])

    def test_unidentified_and_nonfinite_designs_are_refused(self):
        y, x, mice = balanced_fixture()
        bad_covariates = [np.ones((8, 2)), np.column_stack((x[:, 0], 2*x[:, 0])),
                          np.full((8, 2), np.inf)]
        for bad in bad_covariates:
            with self.subTest(covariates=bad.tolist()):
                with self.assertRaises(ValueError):
                    MODELS.balanced_reml(y, bad, mice, METHODS)
        with self.assertRaises(ValueError):
            MODELS.balanced_reml(y[:3], x[:3], mice[:3], METHODS)
        y[0, 0] = np.nan
        with self.assertRaises(ValueError):
            MODELS.balanced_reml(y, x, mice, METHODS)

    def test_boolean_and_complex_values_refused_before_coercion(self):
        y, x, mice = balanced_fixture()
        for bad_y in [np.ones((8, 4), dtype=bool), y.astype(complex)+1j]:
            with self.assertRaises(ValueError):
                MODELS.balanced_reml(bad_y, x, mice, METHODS)
        for bad_x in [np.ones((8, 2), dtype=bool), x.astype(complex)+1j]:
            with self.assertRaises(ValueError):
                MODELS.balanced_reml(y, bad_x, mice, METHODS)

    def test_support_and_identity_shape_rejections(self):
        y, x, mice = balanced_fixture()
        for bad_y, bad_x, bad_mice, methods in [
            (y[:, :3], x, mice, METHODS),
            (y, x[:-1], mice, METHODS),
            (y, x, mice[:-1], METHODS),
            (y, x, ['']+mice[1:], METHODS),
            (y, x, mice, METHODS[::-1]),
        ]:
            with self.assertRaises(ValueError):
                MODELS.balanced_reml(bad_y, bad_x, bad_mice, methods)


class MouseBootstrapTests(unittest.TestCase):
    def test_whole_mouse_draws_preserve_original_scaling(self):
        y, x, mice = balanced_fixture()
        result = MODELS.mouse_bootstrap(y, x, mice, METHODS, seed=7, repetitions=4)
        self.assertEqual(result['sampled_mouse_indices'],
                         [[2, 1, 3, 0], [0, 0, 2, 0], [1, 0, 0, 3], [3, 0, 1, 0]])
        # The second draw has11 units because the three-unit mouse is sampled
        # three times. These coefficients were computed on explicitly expanded
        # original-scale rows, independently of the production QR-block route.
        second = [.5, .575, -.175, .875, -.1540002540003805, -.7080005080007621,
                  .3540002540003808, .054000254000380554, .4540002540003808,
                  .6810003810005717, .5270001270001906, .48100038100057174]
        np.testing.assert_allclose(result['coefficient_samples'][1], second, rtol=0, atol=3e-14)
        np.testing.assert_allclose(result['fixed_covariate_center'], [10., 2.], rtol=0, atol=0)
        np.testing.assert_allclose(result['fixed_covariate_long_table_sample_sd'],
                                   [math.sqrt(32/31)]*2, rtol=0, atol=1e-15)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['failed_replicates'], [])
        self.assertFalse(result['coverage_qualified'])
        self.assertFalse(result['source_lmerTest_inference'])

    def test_rank_failed_draws_are_retained_and_suppress_intervals(self):
        y, x, _ = balanced_fixture()
        mice = ['left']*4 + ['right']*4
        result = MODELS.mouse_bootstrap(y, x, mice, METHODS, seed=0, repetitions=8)
        # Sampling only one side makes firing rate constant. Such draws must
        # remain failures, not be repaired by drawing until an interval exists.
        expected_failed = [i for i, draw in enumerate(result['sampled_mouse_indices'])
                           if len(set(draw)) == 1]
        self.assertTrue(expected_failed)
        self.assertEqual([r['replicate'] for r in result['failed_replicates']], expected_failed)
        self.assertEqual(len(result['coefficient_samples']), 8)
        self.assertEqual(len(result['sampled_mouse_indices']), 8)
        for i in expected_failed:
            self.assertIsNone(result['coefficient_samples'][i])
        self.assertEqual(result['status'], 'incomplete_support')
        self.assertIsNone(result['intervals'])

    def test_invalid_resampling_configuration_refused(self):
        y, x, mice = balanced_fixture()
        for seed, repetitions in [(True, 2), (-1, 2), (2**64, 2), (0, True), (0, 1), (0, 10001)]:
            with self.assertRaises(ValueError):
                MODELS.mouse_bootstrap(y, x, mice, METHODS, seed=seed, repetitions=repetitions)

    def test_one_mouse_bootstrap_is_unavailable(self):
        y, x, _ = balanced_fixture()
        result = MODELS.mouse_bootstrap(y, x, ['same']*8, METHODS, seed=0, repetitions=2)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['intervals'])


def complete_cohort():
    """Complete generated dimensions; never claims original biological identity."""
    _, x, mice = balanced_fixture()
    units = []
    for i in range(5775):
        mouse = ('m' + str({'a': 0, 'b': 1, 'c': 2, 'd': 3}[mice[i]])) if i < 8 else f'm{i%26}'
        fr, lv = x[i].tolist() if i < 8 else (10., 2.)
        units.append({'unit_id': f'u{i}', 'mouse_id': mouse, 'session_id': 's-' + mouse,
                      'area': f'area{i%8}', 'fr_hz': fr, 'lv': lv})
    return {'schema': 'isttc_empirical_cohort_v1', 'source_sha256': 'a'*64, 'units': units}


def complete_four_method_estimates():
    y, _, _ = balanced_fixture()
    rows = []
    for i in range(5775):
        for j, method in enumerate(METHODS):
            present = i < 8
            rows.append({'unit_id': f'u{i}', 'method': method,
                         'tau_bins': float(10**y[i, j] / 50) if present else None,
                         'r_squared': .5 if present else None,
                         'failure_reason': None if present else 'generated missing fit'})
    return {'schema': 'isttc_empirical_estimates_v1', 'rows': rows}


class CompleteFigureEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = complete_cohort()
        cls.estimates = complete_four_method_estimates()

    def report(self, cohort=None, estimates=None, **config):
        return ENDPOINTS.figure7c(self.cohort if cohort is None else cohort,
                                 self.estimates if estimates is None else estimates,
                                 bootstrap_seed=config.get('bootstrap_seed', 20261117005),
                                 bootstrap_repetitions=config.get('bootstrap_repetitions', 1000))

    def test_complete_population_retained_while_source_mask_is_explicit(self):
        result = self.report()
        self.assertEqual(len(result['source_reduction']['records']), 5775)
        self.assertEqual(result['source_reduction']['counts']['missing_fit_or_covariate'], 5767)
        self.assertEqual(result['source_reduction']['counts']['complete_cases'], 8)
        self.assertEqual(result['model_unit_ids'], [f'u{i}' for i in range(8)])
        panel = result['models']['log10_tau_ms']
        self.assertEqual(panel['status'], 'available')
        np.testing.assert_allclose(panel['fixed_effects']['coefficients'],
                                   [1., .2, -.3, .5, .1, -.2, .1, -.2, .2, .3, .4, .1],
                                   rtol=0, atol=2e-12)
        self.assertFalse(result['scientifically_qualified'])
        self.assertFalse(result['historical_lmerTest_p_values_reproduced'])
        self.assertIsNone(result['scientific_pass'])

    def test_zero_residual_retains_points_without_finite_gaussian_fit_claim(self):
        estimates = copy.deepcopy(self.estimates)
        for row in estimates['rows'][:32]:
            row['tau_bins'] = .02  # Exactly1ms: log10(tau_ms)=0 for all methods.
        result = self.report(estimates=estimates)
        self.assertEqual(len(result['source_reduction']['records']), 5775)
        self.assertEqual(result['source_reduction']['counts']['missing_fit_or_covariate'], 5767)
        self.assertEqual(result['model_unit_ids'], [f'u{i}' for i in range(8)])
        panel = result['models']['log10_tau_ms']
        self.assertEqual(panel['status'], 'point_estimates_only')
        fitted = panel['fixed_effects']
        self.assertFalse(fitted['finite_nonsingular_gaussian_fit'])
        self.assertTrue(fitted['degenerate_zero_residual_variance'])
        self.assertEqual(fitted['residual_variance'], 0.)
        self.assertEqual(fitted['unit_intercept_variance'], 0.)
        self.assertEqual(fitted['coefficients'], [0.]*12)
        self.assertIsNone(fitted['source_p_values'])
        self.assertIsNone(fitted['source_profile_confidence_intervals'])
        self.assertIsNotNone(panel['mouse_bootstrap'])
        self.assertFalse(panel['mouse_bootstrap']['coverage_qualified'])
        self.assertFalse(panel['mouse_bootstrap']['source_lmerTest_inference'])
        self.assertEqual(result['models']['log10_pseudo_ree_percent']['status'], 'unavailable')
        self.assertFalse(result['scientifically_qualified'])

    def test_zero_relative_error_does_not_receive_epsilon_or_drop_unit(self):
        estimates = copy.deepcopy(self.estimates)
        estimates['rows'][2]['tau_bins'] = estimates['rows'][0]['tau_bins']
        result = self.report(estimates=estimates)
        self.assertEqual(result['model_unit_ids'], [f'u{i}' for i in range(8)])
        self.assertEqual(result['models']['log10_tau_ms']['status'], 'available')
        error = result['models']['log10_pseudo_ree_percent']
        self.assertEqual(error['status'], 'unavailable')
        self.assertEqual(error['reason'], 'source_log_domain_unresolved')
        self.assertIn({'unit_id': 'u0', 'method': 'pearsonr_trial_avg',
                       'reason': 'undefined_or_nonpositive_log_argument'}, error['invalid_coordinates'])
        self.assertIsNone(error['fixed_effects'])

    def test_nonpositive_reference_suppresses_model_without_mask_shrinkage(self):
        estimates = copy.deepcopy(self.estimates)
        estimates['rows'][0]['tau_bins'] = 0.
        result = self.report(estimates=estimates)
        self.assertEqual(result['source_reduction']['counts']['complete_cases'], 8)
        self.assertEqual(result['source_reduction']['counts']['undefined_reference'], 1)
        self.assertEqual(len(result['model_unit_ids']), 8)
        for panel in result['models'].values():
            self.assertEqual(panel['status'], 'unavailable')
            self.assertIsNone(panel['fixed_effects'])

    def test_negative_r_squared_union_differs_from_zero_boundary(self):
        estimates = copy.deepcopy(self.estimates)
        estimates['rows'][0]['r_squared'] = -.1
        estimates['rows'][4]['r_squared'] = 0.
        result = self.report(estimates=estimates)
        self.assertEqual(result['source_reduction']['counts']['negative_r2_after_missing'], 1)
        self.assertEqual(result['model_unit_ids'], [f'u{i}' for i in range(1, 8)])

    def test_missing_or_duplicate_method_coordinate_refused(self):
        missing = {'schema': self.estimates['schema'], 'rows': self.estimates['rows'][:-1]}
        with self.assertRaises(ValueError):
            self.report(estimates=missing)
        duplicate = {'schema': self.estimates['schema'], 'rows': list(self.estimates['rows'])}
        duplicate['rows'][0] = duplicate['rows'][1]
        with self.assertRaises(ValueError):
            self.report(estimates=duplicate)

    def test_whole_cohort_and_biological_session_consistency_required(self):
        for operation in ('missing-unit', 'one-area', 'session-alias'):
            cohort = copy.deepcopy(self.cohort)
            if operation == 'missing-unit':
                cohort['units'].pop()
            elif operation == 'one-area':
                for row in cohort['units']:
                    row['area'] = 'single'
            else:
                cohort['units'][3]['session_id'] = cohort['units'][0]['session_id']
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    self.report(cohort=cohort)

    def test_bad_bootstrap_config_refused_even_if_log_model_unavailable(self):
        estimates = copy.deepcopy(self.estimates)
        estimates['rows'][0]['tau_bins'] = 0.
        for seed, repetitions in [(-1, 1000), (20261117005, 0),
                                  (True, 1000), (20261117005, True),
                                  (7, 1000), (20261117005, 999)]:
            with self.subTest(seed=seed, repetitions=repetitions):
                with self.assertRaises(ValueError):
                    self.report(estimates=estimates, bootstrap_seed=seed,
                                bootstrap_repetitions=repetitions)

    def test_even_median_does_not_overflow_on_finite_equal_values(self):
        result = ENDPOINTS._summary([1e308, 1e308], 2)
        self.assertEqual(result['median_pseudo_ree_percent'], 1e308)
        self.assertEqual(result['defined_count'], 2)


if __name__ == '__main__':
    unittest.main()
