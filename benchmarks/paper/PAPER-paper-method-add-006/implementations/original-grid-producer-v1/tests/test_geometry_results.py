"""Generated mathematical/source-contract controls; no authentic arrays."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
import warnings
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('geometry_results_under_test', HERE / 'geometry_results.py')
G = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G
SPEC.loader.exec_module(G)


def fixture(n=510, units=21):
    rng = np.random.RandomState(734)
    z = rng.normal(size=(n, 7))
    z[:, 2] = 6
    z[:, 3] = 7 + rng.normal(size=n)
    z[:, 4] = 5 + rng.normal(size=n)
    z[:, 5] = np.arange(n) % 2
    z[:, 6] = np.arange(n) % 2
    return {'x': rng.poisson(4, (n, units)), 'z': z,
            'unit_ids': np.array([f'asset:unit-{u * 3 + 5}' for u in range(units)]),
            'row_ids': 10000 + np.arange(n) * 2, 't': np.arange(n) * .5,
            'trial': np.arange(n)}


def fake_repetitions(case_id='KL8-s01-CA1'):
    return [{'case_id': case_id, 'repetition': i, 'condition': 'current_source_code19',
             'geometry_fields': list(G.GEOMETRY_FIELDS),
             'geometry_values': np.array([4, .2, 3, 2, .6, .8, .4, .3]),
             'theory_error': .3 + i * 1e-6,
             'readout': {'hebbian_error': .31, 'svc_error': .2, 'svc_policy': G.SVC_POLICY}}
            for i in range(500)]


def fake_glm(case_id='KL8-s01-CA1'):
    return {'schema': 'source_glm_pr_session_v1', 'condition': 'current_source_code19',
            'case_id': case_id,
            'subset_pr': np.tile([6., 2.], (500, 1)), 'raw_pr': 6., 'fitted_pr': 2.,
            'mean_selected_cv_d2': .25, 'mean_selected_cv_sem': .03}


class GeometryResultControls(unittest.TestCase):
    def test_full_plan_census_and_source_loop_order(self):
        jobs = list(G.geometry_plan())
        self.assertEqual(len(jobs), 64000)
        self.assertEqual(len({(j['case_id'], j['repetition']) for j in jobs}), 64000)
        self.assertEqual(len({j['case_id'] for j in jobs}), 128)
        self.assertEqual(jobs[0], {'case_id': 'KL8-s01-CA1', 'animal': 'KL8', 'session': 1,
                                  'region': 'CA1', 'repetition': 0, 'region_seed': 213423})
        self.assertEqual((jobs[63]['case_id'], jobs[63]['repetition']), ('ZT2-s08-CA1', 0))
        self.assertEqual((jobs[64]['case_id'], jobs[64]['repetition']), ('KL8-s01-CA1', 1))
        self.assertEqual((jobs[32000]['case_id'], jobs[32000]['region_seed']), ('KL8-s01-PFC', 45342))
        self.assertEqual((jobs[-1]['case_id'], jobs[-1]['repetition']), ('ZT2-s08-PFC', 499))

    def test_glm_500_independent_subsets_and_native_ids(self):
        rng = np.random.RandomState(45)
        x = np.random.RandomState(12).poisson(3, (18, 23))
        mu = x * .4 + 1
        scores = np.full((23, 10, 10), .2)
        scores[:, 3] = .4
        selected = np.full(23, 3, dtype=int)
        units = np.array([f'u-{i}' for i in range(23)])
        result = G.glm_pr_result(x, mu, scores, selected, units, rng=rng,
                                 case_id='KL8-s01-CA1', row_ids=np.arange(len(x)))
        oracle = np.random.RandomState(45)
        raw = oracle.choice(23, 19, replace=False)
        fitted = oracle.choice(23, 19, replace=False)
        np.testing.assert_array_equal(result['subset_unit_positions'][0], [raw, fitted])
        np.testing.assert_array_equal(result['subset_unit_ids'][0], [units[raw], units[fitted]])
        self.assertEqual(result['subset_pr'].shape, (500, 2))
        self.assertFalse(np.array_equal(raw, fitted))
        norm = (x[:, raw] - x[:, raw].mean(0)) / (x[:, raw].std(0) + .01)
        cov = norm.T @ norm / len(norm)
        self.assertAlmostEqual(result['subset_pr'][0, 0], np.trace(cov) ** 2 / np.sum(cov ** 2))
        self.assertEqual(result['rng_after'], G.state(rng))
        self.assertFalse(result['historical_realization_authenticated'])

    def test_glm_null_masks_nan_rules_and_sem(self):
        x = np.random.RandomState(20).poisson(4, (20, 19))
        mu = x + 1.
        original_mu = mu.copy()
        scores = np.full((19, 10, 10), .2)
        scores[0] = 0  # equality to null is suppressed
        scores[1, :, :2] = np.nan  # only8 valid folds
        scores[2] = np.nan  # source argmax remains0; population mean remainsNaN
        scores[3, :, 0] = np.nan  # nine is enough, do not suppress
        scores[4] = np.arange(10) / 10
        result = G.glm_pr_result(x, mu, scores, np.zeros(19, dtype=int), np.arange(19),
                                 rng=np.random.RandomState(8), case_id='KL8-s01-CA1', row_ids=np.arange(len(x)))
        np.testing.assert_array_equal(result['suppressed_units'], [0, 1, 2])
        np.testing.assert_array_equal(result['selected_valid_folds'][:4], [10, 8, 0, 9])
        self.assertTrue(np.isnan(result['mean_selected_cv_d2']))
        self.assertTrue(np.isnan(result['mean_selected_cv_sem']))
        self.assertAlmostEqual(result['selected_cv_sem_per_unit'][4], np.std(np.arange(10) / 10) / np.sqrt(10))
        np.testing.assert_array_equal(mu, original_mu)

    def test_glm_all_suppressed_expected_pr_zero(self):
        x = np.tile(np.arange(19), (10, 1)) + np.arange(10)[:, None]
        result = G.glm_pr_result(x, x + 1., np.zeros((19, 10, 10)), np.zeros(19, dtype=int),
                                 np.arange(19), rng=np.random.RandomState(1),
                                 case_id='KL8-s01-CA1', row_ids=np.arange(len(x)))
        self.assertEqual(result['fitted_pr'], 0)
        self.assertAlmostEqual(result['raw_pr'], 1.)
        self.assertTrue(np.all(result['subset_pr'][:, 1] == 0))

    def test_glm_invalid_full_grid_and_identity_refused_before_rng(self):
        x = np.ones((5, 19), dtype=int)
        scores = np.ones((19, 10, 10))
        base = (x, x + .1, scores, np.zeros(19, dtype=int), np.arange(19))
        bad = [(*base[:2], scores[:, :, :9], *base[3:]),
               (*base[:3], np.ones(19, dtype=int), base[4]),
               (*base[:4], np.zeros(19, dtype=int)),
               (x[:, :18], (x + .1)[:, :18], scores[:18], np.zeros(18, dtype=int), np.arange(18))]
        for args in bad:
            with self.subTest(shape=np.shape(args[2])):
                rng = np.random.RandomState(1)
                before = G.state(rng)
                with self.assertRaises(G.ContractError):
                    G.glm_pr_result(*args, rng=rng, case_id='KL8-s01-CA1', row_ids=np.arange(len(x)))
                self.assertEqual(before, G.state(rng))

    def test_geometry_preprocess_distinct_speed_masks_and_native_mapping(self):
        packet = fixture(n=520, units=21)
        packet['z'][:5, 2] = 0  # kept by geometry's derived velocity, unlike GLM
        packet['z'][5:10, 3:5] = 0  # removed despite recorded speed6
        packet['x'][:, 0] = 0
        result = G.prepare_geometry(packet, 'CA1')
        self.assertEqual(result['x'].shape, (515, 20))
        np.testing.assert_array_equal(result['row_ids'][:5], packet['row_ids'][:5])
        self.assertNotIn(packet['row_ids'][5], result['row_ids'])
        np.testing.assert_array_equal(result['unit_ids'], packet['unit_ids'][1:])
        mask = np.linalg.norm(packet['z'][:, 3:5], axis=1) > 4
        raw = packet['x'][mask, 1:]
        wanted = (raw - raw.mean(0)) / (raw.std(0) + .01)
        np.testing.assert_allclose(result['x'], wanted, rtol=1e-13, atol=1e-13)
        np.testing.assert_allclose(result['z'].mean(0), 0, atol=1e-13)
        np.testing.assert_allclose(result['z'].std(0), 1, atol=1e-13)
        self.assertIsNone(result['behavior']['accuracy'])

    def test_behavior_uses_complete_trials_not_bin_weighting(self):
        packet = fixture()
        packet['trial'][:] = 12
        packet['trial'][-1] = 24
        packet['z'][:, 5] = 0
        packet['z'][-1, 5] = 1
        packet['epoch_trials'] = {'trial_ids': [12, 24, 30], 'correct': [0, 1, 1],
                                  'source_binding': 'generated-full-trial-table'}
        result = G.behavior_result(packet)
        self.assertEqual(result['accuracy'], 2 / 3)  # trial30 has no sampled bin
        self.assertEqual(result['trial_count'], 3)
        packet['epoch_trials']['correct'][0] = 1
        with self.assertRaisesRegex(G.ContractError, 'differs'):
            G.behavior_result(packet)

    def test_coverage_bound_behavior_matches_equal_trials_and_refuses_count_drift(self):
        packet = fixture()
        packet['case_id'] = 'KL8-s01-CA1'
        packet['trial'][:] = 18
        packet['trial'][-1] = 24
        packet['z'][:, 5] = 0
        packet['z'][-1, 5] = 1
        packet['complete_trial_support'] = {'coverage_sha256': '1' * 64, 'design_sha256': '2' * 64,
                                            'case_id': 'KL8-s01-CA1', 'source_trial_count': 2}
        self.assertEqual(G.behavior_result(packet)['accuracy'], .5)
        packet['complete_trial_support']['source_trial_count'] = 3
        with self.assertRaisesRegex(G.ContractError, 'count mismatch'):
            G.behavior_result(packet)

    def test_glm_inf_is_valid_and_not_silently_suppressed(self):
        x = np.random.RandomState(34).poisson(2, (12, 19))
        scores = np.full((19, 10, 10), .2)
        scores[0, 0, 0] = np.inf
        result = G.glm_pr_result(x, x + .3, scores, np.zeros(19, dtype=int), np.arange(19),
                                 rng=np.random.RandomState(4), case_id='KL8-s01-CA1', row_ids=np.arange(len(x)))
        self.assertEqual(result['selected_valid_folds'][0], 10)
        self.assertNotIn(0, result['suppressed_units'])
        self.assertEqual(result['mean_selected_cv_d2'], np.inf)
        self.assertTrue(np.isnan(result['selected_cv_fold_population_sd'][0]))

    def test_insufficient_geometry_support_is_not_resized(self):
        for packet in (fixture(n=499), fixture(units=18)):
            with self.assertRaisesRegex(G.ContractError, '500 rows and19'):
                G.prepare_geometry(packet, 'PFC')
        packet = fixture()
        packet['z'][:, 0] = 0
        with self.assertRaises(G.ContractError):
            G.prepare_geometry(packet, 'PFC')

    def test_readout_literal_draws_zero_margin_and_separate_svc_rng(self):
        z = np.random.RandomState(41).normal(size=(500, 4))
        x = np.zeros((500, 19))  # all Hebbian margins zero; source counts no error
        oracle = np.random.RandomState(83)
        teachers = oracle.randn(4, 500)
        labels = np.sign(z @ teachers)
        valid = np.flatnonzero(np.abs(labels.mean(0)) < .25)
        train = oracle.choice(500, 300, replace=False)
        test = np.setdiff1d(np.arange(500), train)
        calls = []
        class FakeSVC:
            def __init__(self, **kwargs):
                calls.append(kwargs)
            def fit(self, xx, yy):
                np.testing.assert_array_equal(xx, x[train])
                np.testing.assert_array_equal(yy, (1 + labels[train, valid[len(calls) - 1]]) / 2)
                return self
            def predict(self, xx):
                np.testing.assert_array_equal(xx, x[test])
                return np.zeros(len(xx))
        rng = np.random.RandomState(83)
        with mock.patch('sklearn.svm.LinearSVC', FakeSVC):
            result = G.readout(x, z, rng=rng, svc_policy=G.SVC_POLICY)
        self.assertEqual(result['hebbian_error'], 0)
        np.testing.assert_array_equal(result['valid_teacher_indices'], valid)
        np.testing.assert_array_equal(result['training_positions'], train)
        np.testing.assert_array_equal(result['test_positions'], test)
        self.assertEqual(result['teacher_identity'], G.array_identity(teachers))
        self.assertEqual(G.state(rng), G.state(oracle))
        self.assertEqual(len(calls), len(valid))
        self.assertEqual(len({r['random_state'] for r in calls}), len(valid))
        self.assertTrue(all(r['dual'] == 'auto' and r['max_iter'] == 10000 for r in calls))

    def test_readout_actual_generated_svc_and_source_formula(self):
        z = np.random.RandomState(75).normal(size=(500, 4))
        x = np.column_stack([z, np.zeros((500, 15))])
        rng = np.random.RandomState(100)
        result = G.readout(x, z, rng=rng, svc_policy=G.SVC_POLICY)
        oracle = np.random.RandomState(100)
        labels = np.sign(z @ oracle.randn(4, 500))
        labels = labels[:, np.abs(labels.mean(0)) < .25]
        train = oracle.choice(500, 300, replace=False)
        test = np.setdiff1d(np.arange(500), train)
        w = np.einsum('ms,mk->sk', labels[train], x[train]) / 300
        pred = np.sign(np.einsum('sk,mk->ms', w, x[test]))
        expected = np.mean((-labels[test] * pred > 0).astype(int), axis=0)
        np.testing.assert_array_equal(result['hebbian_task_errors'], expected)
        self.assertLess(result['svc_error'], .1)
        self.assertGreater(len(result['valid_teacher_indices']), 100)
        self.assertEqual(result['warnings'], [])

    def test_readout_refuses_unbalanced_tasks_policy_and_badshape(self):
        with self.assertRaisesRegex(G.ContractError, 'more than100'):
            G.readout(np.ones((500, 19)), np.ones((500, 4)), rng=np.random.RandomState(1),
                      svc_policy=G.SVC_POLICY)
        with self.assertRaisesRegex(G.ContractError, 'explicit current'):
            G.readout(np.ones((500, 19)), np.ones((500, 4)), rng=np.random.RandomState(1),
                      svc_policy='historical')
        with self.assertRaises(G.ContractError):
            G.readout(np.ones((499, 19)), np.ones((499, 4)), rng=np.random.RandomState(1),
                      svc_policy=G.SVC_POLICY)

    def test_literal_none_route_and_convergence_warning_are_retained(self):
        from sklearn.exceptions import ConvergenceWarning
        z = np.random.RandomState(29).normal(size=(500, 4))
        calls = []
        class WarningSVC:
            def __init__(self, **kwargs):
                calls.append(kwargs)
            def fit(self, xx, yy):
                warnings.warn('generated convergence warning', ConvergenceWarning)
                return self
            def predict(self, xx):
                return np.zeros(len(xx))
        with mock.patch('sklearn.svm.LinearSVC', WarningSVC):
            result = G.readout(np.zeros((500, 19)), z, rng=np.random.RandomState(2),
                               svc_policy=G.SVC_LITERAL_POLICY)
        self.assertTrue(all(r['random_state'] is None for r in calls))
        self.assertEqual(len(result['warnings']), len(calls))
        self.assertIsNone(result['svc_seeds'])
        self.assertTrue(np.isfinite(result['svc_error']))

    def test_primary_seed_recipe_is_reproducible_and_canonical(self):
        import hashlib
        import json
        z = np.random.RandomState(29).normal(size=(500, 4))
        class FakeSVC:
            def __init__(self, **kwargs):
                pass
            def fit(self, xx, yy):
                return self
            def predict(self, xx):
                return np.zeros(len(xx))
        before = G.state(np.random.RandomState(52))
        canonical = json.dumps(before, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        sha = hashlib.sha256(canonical).hexdigest()
        with mock.patch('sklearn.svm.LinearSVC', FakeSVC):
            first = G.readout(np.zeros((500, 19)), z, rng=np.random.RandomState(52), svc_policy=G.SVC_POLICY)
            second = G.readout(np.ones((500, 19)), z, rng=np.random.RandomState(52), svc_policy=G.SVC_POLICY)
        self.assertEqual(first['pre_teacher_state_sha256'], sha)
        index = int(first['valid_teacher_indices'][0])
        expected = int(hashlib.sha256((sha + ':' + str(index)).encode()).hexdigest()[:8], 16)
        self.assertEqual(int(first['svc_seeds'][0]), expected)
        np.testing.assert_array_equal(first['svc_seeds'], second['svc_seeds'])
        self.assertEqual(first['teacher_identity'], second['teacher_identity'])
        self.assertEqual(first['rng_after'], second['rng_after'])

    def test_geometry_repetition_covariance_and_identity_alignment(self):
        packet = G.prepare_geometry(fixture(n=550, units=23), 'CA1')
        def fake_readout(x, z, *, rng, svc_policy):
            return {'training_positions': np.arange(300), 'test_positions': np.arange(300, 500),
                    'hebbian_error': .3, 'svc_error': .2}
        with mock.patch.object(G, 'readout', side_effect=fake_readout):
            result = G.geometry_repetition(packet['x'], packet['z'], packet['row_ids'], packet['unit_ids'],
                                            rng=np.random.RandomState(7), repetition=499, svc_policy=G.SVC_POLICY)
        oracle = np.random.RandomState(7)
        rows = oracle.choice(550, 500, replace=False)
        units = oracle.choice(23, 19, replace=False)
        np.testing.assert_array_equal(result['row_ids'], packet['row_ids'][rows])
        np.testing.assert_array_equal(result['unit_ids'], packet['unit_ids'][units])
        np.testing.assert_array_equal(result['training_row_ids'], packet['row_ids'][rows[:300]])
        joint = np.column_stack([packet['x'][rows][:, units], packet['z'][rows]])
        covariance = np.cov(joint, rowvar=False, bias=True)
        psi, phi, omega = covariance[:19, :19], covariance[:19, 19:], covariance[19:, 19:]
        dimension = np.trace(psi) ** 2 / np.sum(psi ** 2)
        alignment = np.trace(phi @ phi.T) / np.trace(psi) / np.trace(omega)
        t1 = np.pi / 300 * np.trace(psi @ psi.T) * np.trace(omega)
        t2 = 2 * (np.trace(phi.T @ psi @ phi) - np.trace(phi.T @ phi) ** 2 / np.trace(omega))
        expected_theory = np.arctan(np.sqrt(np.trace(omega) * (t1 + t2)) /
                                    (np.sqrt(2) * np.trace(phi @ phi.T))) / np.pi
        self.assertAlmostEqual(result['geometry_values'][0], dimension)
        self.assertAlmostEqual(result['geometry_values'][1], alignment)
        self.assertAlmostEqual(result['theory_error'], expected_theory)

    def test_panel_iterator_all_jobs_loader_arguments_without_repeated_fits(self):
        seen = []
        def loader(rat, session, region):
            seen.append((rat, session, region))
            return {}
        prepared = {'x': None, 'z': None, 'row_ids': None, 'unit_ids': None,
                    'behavior': {'accuracy': None}, 't': np.arange(500), 'trial': np.arange(500)}
        with mock.patch.object(G, 'prepare_geometry', return_value=prepared), \
             mock.patch.object(G, 'geometry_repetition', side_effect=lambda *args, **kwargs:
                               {'repetition': kwargs['repetition'], 'row_positions': np.array([0, 499])}):
            result = list(G.iter_geometry_panel(loader, svc_policy=G.SVC_POLICY))
        self.assertEqual(len(result), 64000)
        self.assertEqual(seen[0], ('KL8', 0, 'CA1'))
        self.assertEqual(seen[-1], ('ZT2', 7, 'PFC'))
        np.testing.assert_array_equal(result[-1]['selected_times'], [0, 499])

    def test_session_reduction_preserves_all_draws_and_missing_behavior(self):
        result = G.session_result(fake_repetitions(), fake_glm(), case_id='KL8-s01-CA1',
                                   behavior={'status': 'unavailable_complete_epoch_trial_table', 'accuracy': None})
        self.assertEqual(result['geometry'].shape, (500, 8))
        self.assertTrue(np.isnan(result['errors'][:, 0]).all())
        self.assertAlmostEqual(result['mean_errors'][2], .3 + 249.5e-6)
        self.assertEqual(result['glm_expected_pr'], 2.)
        with self.assertRaises(G.ContractError):
            G.session_result(fake_repetitions()[:-1], fake_glm(), case_id='KL8-s01-CA1',
                             behavior={'status': 'unavailable_complete_epoch_trial_table', 'accuracy': None})
        bad = fake_repetitions()
        bad[5]['case_id'] = 'ER1-s01-CA1'
        with self.assertRaises(G.ContractError):
            G.session_result(bad, fake_glm(), case_id='KL8-s01-CA1',
                             behavior={'status': 'unavailable_complete_epoch_trial_table', 'accuracy': None})
        bad = fake_repetitions()
        bad[7]['readout']['svc_policy'] = G.SVC_LITERAL_POLICY
        with self.assertRaisesRegex(G.ContractError, 'one explicit SVC recipe'):
            G.session_result(bad, fake_glm(), case_id='KL8-s01-CA1',
                             behavior={'status': 'unavailable_complete_epoch_trial_table', 'accuracy': None})

    def test_full_panel_shapes_order_trajectories_and_descriptive_r2(self):
        sessions = []
        for a, rat in enumerate(G.ANIMALS):
            for session in G.SESSIONS:
                for region in G.REGIONS:
                    cid = f'{rat}-s{session:02d}-{region}'
                    draws = fake_repetitions(cid)
                    value = .1 + (a * 8 + session) / 200
                    for row in draws:
                        row['theory_error'] = value
                    sessions.append(G.session_result(draws, fake_glm(cid), case_id=cid,
                        behavior={'status': 'declared_complete_epoch_trial_mean', 'accuracy': 1 - value}))
        result = G.panel_result(list(reversed(sessions)))
        for region in G.REGIONS:
            r = result['regions'][region]
            self.assertEqual(r['geometry'].shape, (500, 8, 8, 8))
            self.assertEqual(r['errors'].shape, (500, 8, 8, 4))
            self.assertEqual(r['glm_participation_ratios'].shape, (8, 8, 2))
            self.assertAlmostEqual(r['behavior_theory_pearson_r2'], 1)
            self.assertEqual(r['independent_animals'], 8)
            self.assertAlmostEqual(r['learning_mean_errors'][0, 2], np.mean([.1 + (a * 8 + 1) / 200 for a in range(8)]))
        with self.assertRaises(G.ContractError):
            G.panel_result(sessions[:-1])
        with self.assertRaises(G.ContractError):
            G.panel_result(sessions[:-1] + sessions[:1])
        sessions[0]['svc_policy'] = G.SVC_LITERAL_POLICY
        with self.assertRaisesRegex(G.ContractError, 'one explicit SVC recipe'):
            G.panel_result(sessions)

    def test_mixed_trend_formula_grouping_default_options_curve_and_warnings(self):
        import pandas as pd
        observed = []
        class FakeResult:
            params = pd.Series({'Intercept': 1., 'time': 2., 'time_squared': -.1, 'Group Var': .7})
            pvalues = pd.Series({'Intercept': .01, 'time': .02, 'time_squared': .03, 'Group Var': .5})
            converged = False
            reml = True
        class FakeModel:
            def fit(self, *args, **kwargs):
                self_outer.assertEqual((args, kwargs), ((), {}))
                warnings.warn('generated source fit warning', RuntimeWarning)
                return FakeResult()
        def mixedlm(formula, frame, groups):
            observed.append((formula, frame.copy(), groups.copy()))
            return FakeModel()
        self_outer = self
        package, formula, api = (types.ModuleType(n) for n in
                                 ('statsmodels', 'statsmodels.formula', 'statsmodels.formula.api'))
        package.formula, formula.api, api.mixedlm = formula, api, mixedlm
        with mock.patch.dict(sys.modules, {'statsmodels': package, 'statsmodels.formula': formula,
                                          'statsmodels.formula.api': api}), \
             mock.patch.object(G.importlib.metadata, 'version', return_value='generated-mock'):
            quadratic = G.mixed_trend(np.arange(64).reshape(8, 8), quadratic=True)
            linear = G.mixed_trend(np.arange(64).reshape(8, 8), quadratic=False)
        self.assertEqual([r[0] for r in observed], ['Y ~ time + time_squared', 'Y ~ time'])
        np.testing.assert_array_equal(observed[0][1]['Y'], np.arange(64))
        np.testing.assert_array_equal(observed[0][1]['time'], np.tile(np.arange(8), 8))
        np.testing.assert_array_equal(observed[0][2], np.repeat(np.arange(8).astype(str), 8))
        np.testing.assert_array_equal(quadratic['fitted_values'], 1 + 2 * np.arange(8) - .1 * np.arange(8) ** 2)
        np.testing.assert_array_equal(linear['fitted_values'], 1 + 2 * np.arange(8))
        self.assertFalse(quadratic['converged'])
        self.assertEqual(len(quadratic['warnings']), 1)
        self.assertEqual(quadratic['runtime']['statsmodels'], 'generated-mock')

    def test_complete14_source_trends_order_measure_mapping(self):
        geom = np.broadcast_to(np.arange(8), (500, 8, 8, 8)).copy().astype(float)
        dims = np.broadcast_to([80., 81.], (8, 8, 2)).copy()
        panel = {'schema': 'source_population_geometry_panel_v1', 'condition': 'current_source_code19',
                 'animal_order': list(G.ANIMALS), 'session_order': list(G.SESSIONS),
                 'regions': {r: {'geometry': geom, 'glm_participation_ratios': dims} for r in G.REGIONS}}
        calls = []
        def fake_trend(values, *, quadratic):
            calls.append((values.copy(), quadratic))
            return {'generated_control': True, 'fixed_parameters': {'time': .2, 'time_squared': -.1},
                    'fixed_pvalues': {'time': .03, 'time_squared': .04}}
        with mock.patch.object(G, 'mixed_trend', side_effect=fake_trend):
            result = G.source_trends(panel)
        self.assertEqual(len(calls), 14)
        self.assertEqual([r['region'] for r in result['fits']], ['PFC'] * 7 + ['CA1'] * 7)
        self.assertEqual([q for _, q in calls[:7]], [True, True, True, True, False, True, False])
        self.assertEqual([float(a[0, 0]) for a, _ in calls[:7]], [0, 1, 2, 3, 3, 81, 81])
        self.assertEqual(result['excluded_animals'], [])
        self.assertEqual(result['multiple_comparisons']['tests'], 24)

    def test_source_bh24_family_identity_sort_and_small_pvalues(self):
        fits = []
        for region in ('PFC', 'CA1'):
            for j, model in enumerate(['quadratic'] * 4 + ['linear', 'quadratic', 'linear']):
                fits.append({'region': region, 'measure': str(j), 'model': model,
                             'result': {'fixed_parameters': {'time': .2, 'time_squared': float(j)},
                                        'fixed_pvalues': {'time': .5, 'time_squared': .8}}})
        fits[0]['result']['fixed_pvalues']['time'] = .0001
        fits[0]['result']['fixed_pvalues']['time_squared'] = .0002
        result = G.adjust_source_trends(fits)
        self.assertEqual(result['tests'], 24)
        self.assertEqual(result['rejected'].sum(), 2)
        p = result['source_concatenated_pvalues']
        np.testing.assert_allclose(result['adjusted_pvalues'][p < .001], [.0024, .0024])
        self.assertEqual(sum(np.isnan(r['p quad. adj.']) for r in result['table_rows']), 4)
        chosen = [r for r in result['table_rows'] if r['Area'] == 'PFC' and r['meas'] == '0'][0]
        self.assertAlmostEqual(chosen['p lin. adj.'], .0024)
        self.assertAlmostEqual(chosen['p quad. adj.'], .0024)
        fits[1]['result']['fixed_pvalues']['time_squared'] = np.nan
        with self.assertRaisesRegex(G.ContractError, 'ten complete'):
            G.adjust_source_trends(fits)


if __name__ == '__main__':
    unittest.main()
