"""Generated engineering controls only; no source dataset or native scientific execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neural028_evaluator', HERE / 'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def packet():
    """Four paired animals, two regimes; area V1, all declared sessions retained."""
    out = {'task_id': 'NEURAL-028', 'schema_version': 1,
           'protocol': {'source_revision': e.SOURCE_REVISION, 'data_scope': 'public_development_only',
                        'phase_mapping_evidence': 'generated_control_mapping_not_native',
                        'calibration_evidence': 'generated_equal_units_not_native',
                        'selection_frozen_before_outcomes': True,
                        'fit_phases': ['before'], 'activity_kind': 'calcium_derived_activity',
                        'position_edges': [0, 20, 40], 'movement_edges': [0, 2, 4],
                        'bootstrap_replicates': 100, 'shuffle_replicates': 10, 'seed': 11},
           'session_manifest': [], 'sessions': []}
    for a, regime in enumerate(('unsup', 'unsup', 'sup', 'sup')):
        for phase in ('before', 'after'):
            key = f'm{a}-{phase}'
            out['session_manifest'].append({'session_id': key, 'mname': f'm{a}', 'datexp': phase,
                                            'blk': '1', 'regime': regime, 'phase': phase,
                                            'source_asset_sha256': '0' * 64,
                                            'mapping_evidence': 'generated_control_not_source'})
            trial_stimulus = [2, 0, 2, 0, 2, 0, 2, 0]
            signal, second, trial_ids, stim_ids, pos, move, corridor, gray = [], [], [], [], [], [], [], []
            for t, stim in enumerate(trial_stimulus):
                for k in range(5):
                    p = (5, 15, 25, 35, 45)[k]
                    m = (1, 1, 3, 3, 1)[k]
                    activity = a + 0.1 * p + 0.2 * m + (stim == 2) * (1 + (phase == 'after')) + (t % 4) * 0.1
                    signal.append(activity)
                    second.append(0.5 * activity + 0.3 * (k % 2))
                    trial_ids.append(t); stim_ids.append(stim); pos.append(p); move.append(m)
                    corridor.append(k < 4); gray.append(k == 4)
            interp = np.empty((2, 8, 60))
            for n in range(2):
                for t in range(8):
                    interp[n, t] = (1 + 0.2 * n) * (t + np.arange(60) * 0.01)
            out['sessions'].append({'session_id': key, 'activity': [signal, second], 'area_ids': [8, 8],
                                     'trial_id': trial_ids, 'stimulus_id': stim_ids,
                                     'position': pos, 'movement': move, 'corridor': corridor, 'gray': gray,
                                     'trial_stimulus_id': trial_stimulus,
                                     'sound_del_pos': [5, 0, 10, 0, 30, 0, 35, 0],
                                     'position_activity': interp.tolist(),
                                     'interpolation_evidence': 'generated_60_bin_tensor_not_native'})
    return out


class TestSourceStatistics(unittest.TestCase):
    def test_arithmetic_sd_not_pooled_variance(self):
        # Means 2 and 2, then means 4 and 1, population SD 2 and 1: d'=2.
        np.testing.assert_allclose(e.dprime([[2, 6]], [[0, 2]]), [2.0])
        self.assertNotAlmostEqual(float(e.dprime([[2, 6]], [[0, 2]])[0]), 3 / np.sqrt(2.5))

    def test_population_not_sample_sd_and_sign(self):
        np.testing.assert_allclose(e.dprime([[2, 4]], [[0, 2]]), [2.0])
        np.testing.assert_allclose(e.dprime([[0, 2]], [[2, 4]]), [-2.0])

    def test_undefined_neurons_not_dropped(self):
        dp = e.dprime([[1, 1], [2, 4]], [[1, 1], [0, 2]])
        result = e.fractions(dp, np.array([8, 8]), 0.3)['V1']
        self.assertEqual(result['n_neurons'], 2)
        self.assertEqual(result['undefined_neurons'], 1)
        self.assertIsNone(result['fraction'])

    def test_constant_nonbinary_unequal_lengths_are_undefined(self):
        for w1, w2 in ((None, None), ([0.3, 0.7], list(range(1, 11)))):
            result = e.dprime(np.full((1, 2), 0.1), np.full((1, 10), 0.1), w1, w2)
            self.assertTrue(np.isnan(result[0]))

    def test_independent_reference_fixture_and_invariance(self):
        x, y = np.array([[0., 4.]]), np.array([[0., 2.]])
        for scale, offset in ((1, 0), (3, 15), (0.01, 0.2)):
            self.assertAlmostEqual(float(e.dprime(scale*x+offset, scale*y+offset)[0]), 2/3)

    def test_independent_global_cue_split_and_reward_window(self):
        p = packet()
        for s in p['sessions']:
            labels = [2, 2, 2, 2, 2, 2, 0, 0]
            s['trial_stimulus_id'] = labels
            s['stimulus_id'] = [labels[t] for t in s['trial_id']]
            s['sound_del_pos'] = [5, 10, 15, 25, 35, 40, 55, 55]
            tensor = np.full((2, 8, 60), 1000.)
            for t, response in enumerate([0, 2, 0, 2, 3, 5, 0, 0]): tensor[:, t, 5:40] = response
            s['position_activity'] = tensor.tolist()
        sessions, policy = e.validate_packet(p)
        _, weights = e.matching_weights(sessions)
        result = e.session_metrics(sessions[0], weights[sessions[0]['session_id']], 0.3)
        self.assertEqual(result['reward_split']['all_trial_cue_mean_mod60'], 30)
        self.assertEqual(result['reward_split']['late_stimulus2_trials'], 2)
        np.testing.assert_allclose(result['source_reward_dprime'], [3., 3.])

    def test_reward_gate_and_all_area_denominator(self):
        result = e.fractions(np.array([0.3, 2, 4]), np.array([8, 8, 8]), 0.3,
                             np.array([0, -0.1, 1]))['V1']
        self.assertAlmostEqual(result['fraction'], 2 / 3)

    def test_reward_uses_all_trial_cue_mean(self):
        p = packet()
        sessions, policy = e.validate_packet(p)
        common, weights = e.matching_weights(sessions)
        r = e.session_metrics(sessions[0], weights[sessions[0]['session_id']], 0.3)
        self.assertEqual(r['reward_split']['all_trial_cue_mean_mod60'], 10)
        self.assertEqual(r['reward_split']['late_stimulus2_trials'], 2)
        self.assertEqual(r['reward_split']['early_stimulus2_trials'], 2)
        # Mean [5:40] adds a common constant; late means 4,6 vs early 0,2 -> d'=4.
        np.testing.assert_allclose(r['source_reward_dprime'], [4, 4])

    def test_weighted_moments_remove_occupancy_effect(self):
        # No stimulus effect within a position bin; different occupancies produce raw effect.
        x = np.array([[0, 0, 0, 2]])
        y = np.array([[0, 2, 2, 2]])
        raw = e.dprime(x, y)[0]
        balanced = e.dprime(x, y, [1/6, 1/6, 1/6, 1/2], [1/2, 1/6, 1/6, 1/6])[0]
        self.assertLess(raw, -1)
        self.assertAlmostEqual(balanced, 0)


class TestContractAndPopulation(unittest.TestCase):
    def test_end_to_end_population_and_strict_json(self):
        result = e.evaluate(packet())
        self.assertEqual(result['population']['n_sessions'], 8)
        self.assertEqual(result['population']['animals'], ['m0', 'm1', 'm2', 'm3'])
        self.assertEqual(result['scientific_qualification'], 'unknown')
        json.dumps(result, allow_nan=False)
        for fold in result['held_animal_explanation']['V1']['folds']:
            self.assertNotIn(fold['held_out_mname'], fold['fitting_mnames'])
            self.assertTrue(all(key.endswith('before') for key in fold['fitting_session_ids']))
            self.assertEqual(len(fold['models']['behavior_only']['sessions']), 2)

    def test_drop_session_rejected(self):
        p = packet(); p['sessions'].pop()
        with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_duplicate_biological_tuple_rejected(self):
        p = packet(); p['session_manifest'][1]['datexp'] = 'before'
        with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_animal_regime_leakage_rejected(self):
        p = packet(); p['session_manifest'][1]['regime'] = 'sup'
        with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_phase_leakage_rejected(self):
        p = packet(); p['protocol']['fit_phases'] = ['before', 'after']
        with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_malformed_structure_and_policy_rejected(self):
        for field, bad in (('protocol', []), ('sessions', [None] * 8)):
            p = packet(); p[field] = bad
            with self.assertRaises(e.ContractError): e.evaluate(p)
        for field, bad in (('phase_mapping_evidence', True), ('calibration_evidence', []),
                           ('ridge_lambda', '0.1'), ('selectivity_threshold', True)):
            p = packet(); p['protocol'][field] = bad
            with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_trial_null_is_reproducible_and_accounts_whole_trials(self):
        p = packet(); sessions, policy = e.validate_packet(p)
        first, second = e.trial_shuffle_control(sessions, policy), e.trial_shuffle_control(sessions, policy)
        self.assertEqual(first, second)
        self.assertTrue(all(r['exchangeable_trials'] == 8 for r in first))
        self.assertTrue(all(r['n_profile_groups'] == 1 for r in first))
        self.assertTrue(all(r['total_stimulus0_2_trials'] == 8 and r['fixed_stimulus0_2_trials'] == 0 for r in first))
        self.assertTrue(all(r['status'] == 'computed_diagnostic' for r in first))

    def test_no_exchangeable_trial_null_is_held(self):
        p = packet(); sessions, policy = e.validate_packet(p)
        # Create condition-specific movement-position profiles without breaking trial identity.
        for s in sessions: s['stratum'] = s['stimulus_id'].copy()
        self.assertTrue(all(r['status'] == 'held_no_exchangeable_trials' for r in e.trial_shuffle_control(sessions, policy)))

    def test_alignment_and_nonfinite_rejected(self):
        for mutate in (lambda s: s['movement'].pop(), lambda s: s['activity'][0].__setitem__(0, float('nan')),
                       lambda s: s['stimulus_id'].__setitem__(0, 0)):
            p = packet(); mutate(p['sessions'][0])
            with self.assertRaises(e.ContractError): e.evaluate(p)

    def test_no_common_support_rejected(self):
        p = packet()
        for i in range(len(p['sessions'][0]['position'])):
            if p['sessions'][0]['corridor'][i]: p['sessions'][0]['position'][i] = 5
        for i in range(len(p['sessions'][1]['position'])):
            if p['sessions'][1]['corridor'][i]: p['sessions'][1]['position'][i] = 25
        with self.assertRaisesRegex(e.ContractError, 'no common'): e.evaluate(p)

    def test_constant_activity_yields_held_not_false_success(self):
        p = packet(); p['sessions'][0]['activity'] = [[1] * 40, [1] * 40]
        r = e.evaluate(p)
        self.assertIsNone(next(s for s in r['sessions'] if s['session_id'] == 'm0-before')['source_selectivity']['V1']['fraction'])
        self.assertIsNone(r['contrasts']['source_selectivity']['V1']['regimes']['unsup']['mean_delta'])

    def test_constant_nonbinary_training_target_has_undefined_scaled_loss(self):
        p = packet()
        for s in p['sessions']:
            if s['session_id'].endswith('before'): s['activity'] = [[0.1] * 40, [0.1] * 40]
            s['movement'] = [0.1] * 40
        r = e.evaluate(p)
        for fold in r['held_animal_explanation']['V1']['folds']:
            self.assertEqual(fold['training_target_variance'], 0)
            self.assertEqual(fold['feature_scale'][1], 1)
            for model in fold['models'].values():
                self.assertTrue(all(row['train_variance_scaled_mse'] is None for row in model['sessions']))

    def test_missing_area_holds_complete_area_endpoint(self):
        p = packet(); p['sessions'][0]['area_ids'] = [0, 0]
        r = e.evaluate(p)
        self.assertEqual(r['held_animal_explanation']['V1']['status'], 'held_missing_area')

    def test_test_neural_changes_do_not_change_own_fit(self):
        original = e.evaluate(packet())
        p = packet()
        for s in p['sessions']:
            if s['session_id'].startswith('m0-'):
                s['activity'] = (np.asarray(s['activity']) + 50).tolist()
        changed = e.evaluate(p)
        old = original['held_animal_explanation']['V1']['folds'][0]
        new = changed['held_animal_explanation']['V1']['folds'][0]
        self.assertEqual(old['feature_center'], new['feature_center'])
        for name in old['models']:
            self.assertEqual(old['models'][name]['coefficients'], new['models'][name]['coefficients'])
            self.assertNotEqual(old['models'][name]['animal_mse'], new['models'][name]['animal_mse'])

    def test_after_targets_never_change_any_fit(self):
        original = e.evaluate(packet())
        p = packet()
        for s in p['sessions']:
            if s['session_id'].endswith('after'):
                s['activity'] = (np.asarray(s['activity']) + 20).tolist()
        changed = e.evaluate(p)
        for old, new in zip(original['held_animal_explanation']['V1']['folds'], changed['held_animal_explanation']['V1']['folds']):
            self.assertEqual(old['models']['behavior_plus_stimulus']['coefficients'], new['models']['behavior_plus_stimulus']['coefficients'])

    def test_session_aggregation_does_not_pseudoreplicate_animals(self):
        base = e.evaluate(packet())['sessions']
        # Additional identical session affects session count, never animal count.
        copied = copy.deepcopy(base[0]); copied['session_id'] += '-extra'
        r = e.paired_contrasts(base + [copied], packet()['protocol'])
        regime = r['source_selectivity']['V1']['regimes']['unsup']
        self.assertEqual(regime['n_animals'], 2)

    def test_cli(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td)/'packet.json', Path(td)/'result.json'
            src.write_text(json.dumps(packet()))
            subprocess.run([sys.executable, str(HERE/'evaluator.py'), str(src), '--output', str(dst)], check=True)
            self.assertEqual(json.loads(dst.read_text())['task_id'], 'NEURAL-028')


if __name__ == '__main__':
    unittest.main()
