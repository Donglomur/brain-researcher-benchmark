"""Invented declaration/aggregation controls, never scientific validation."""
from copy import deepcopy
import json
import math
import unittest
import find025_contract as c
from invented_fixture import fixture, rebind, score_records
from metric_primitives import signed_variance_explained, squared_pearson_correlation


class ContractControls(unittest.TestCase):
    def test_pending_real_plan_is_incomplete(self):
        p = c.pending_plan()
        r = c.report(p, [], [])
        self.assertTrue(r['plan_gaps'])
        self.assertEqual(len([g for g in r['plan_gaps'] if g.startswith('scope:')]), 16)
        self.assertIsNone(r['paper_pass'])
        self.assertFalse(r['execution_ready'])

    def test_all_obligations_and_both_families_retained(self):
        p, s, e = fixture()
        r = c.report(p, s, e)
        self.assertEqual(set(x['obligation'] for x in r['comparisons']), set(c.OBLIGATIONS))
        self.assertEqual({x['family'] for x in r['comparisons']}, {'subspaces', 'decoding_delay'})
        self.assertEqual(sum(v['assigned'] for v in r['denominators'][s[0]['run_id']].values()), 16)
        self.assertIsNone(r['aggregate_score'])

    def test_finite_comparison_is_only_declaration(self):
        p, s, e = fixture()
        r = c.report(p, s, e)
        rows = [x for x in r['comparisons'] if x['status'] == 'declared_comparable']
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(x['left_minus_right'] == 0 for x in rows))
        self.assertFalse(r['scientifically_qualified'])
        self.assertEqual(r['evidence_class'], 'invented')

    def test_missing_family_cannot_disappear(self):
        p, s, e = fixture()
        del p['scope_matrix']['randomized_choice_onset']
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)

    def test_empty_obligation_is_a_gap_not_success(self):
        p, s, e = fixture()
        case = p['scope_matrix']['randomized_motion_onset'].pop()
        p['cases'] = [r for r in p['cases'] if r['case_id'] != case]
        self.assertIn('scope:randomized_motion_onset', c.plan_gaps(p))

    def test_omitted_case_keeps_assigned_denominator(self):
        p, s, e = fixture()
        s[0]['records'].pop()
        r = c.report(p, s, score_records(p, s))
        counts = r['denominators'][s[0]['run_id']]['decoding_delay']
        self.assertEqual(counts['assigned'], 10)
        self.assertEqual(counts['statuses']['missing'], 1)

    def test_missing_run_is_retained(self):
        p, s, e = fixture()
        r = c.report(p, s[:1], score_records(p, s[:1]))
        self.assertEqual(sum(x['status'] == 'missing' for x in r['cells']), 16)
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']))

    def test_failure_and_reason_survive(self):
        p, s, e = fixture()
        s[0]['records'][6].update(status='failed', reason='INVENTED:fit did not converge', artifacts=[])
        r = c.report(p, s, score_records(p, s))
        self.assertIn('INVENTED:fit did not converge', [x['candidate_reason'] for x in r['cells']])
        self.assertEqual(r['denominators'][s[0]['run_id']]['decoding_delay']['statuses']['failed'], 1)

    def test_bare_r2_rejected(self):
        p, s, e = fixture()
        p['cases'][10]['identity']['metric_id'] = 'R2'
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)

    def test_corr_and_signed_never_compare(self):
        p, s, e = fixture()
        s[0]['records'][10]['identity']['metric_id'] = c.SIGNED
        r = c.report(p, s, score_records(p, s))
        row = next(x for x in r['comparisons'] if x['case_id'] == s[0]['records'][10]['case_id'])
        self.assertIsNone(row['left_minus_right'])
        self.assertAlmostEqual(squared_pearson_correlation([0, 1, 2], [10, 11, 12]), 1, places=14)
        self.assertEqual(signed_variance_explained([0, 1, 2], [10, 11, 12]), -149)

    def test_each_material_identity_change_prevents_pair(self):
        # One fixture, no data IO. Every declared scientific operand matters.
        p, original, _ = fixture()
        for field in c.IDENTITY_FIELDS:
            with self.subTest(field=field):
                s = deepcopy(original)
                row = s[0]['records'][10]
                row['identity'][field] = None
                r = c.report(p, s, score_records(p, s) if field != 'metric_id' else [])
                pair = next(x for x in r['comparisons'] if x['case_id'] == row['case_id'])
                self.assertIsNone(pair['left_minus_right'])

    def test_unresolved_join_prevents_all_pairs(self):
        p, s, e = fixture()
        p['joins']['dispatch_arguments_and_explicit_repairs'] = {'status': 'unresolved', 'evidence_id': None}
        r = c.report(p, s, rebind(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']))

    def test_paper_mode_never_numeric_pass_or_pair(self):
        p, s, e = fixture('paper_reproduction')
        r = c.report(p, s, e)
        self.assertIsNone(r['paper_pass'])
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']))
        self.assertTrue(all('final_paper_adjudication_not_implemented' in x['reasons'] for x in r['comparisons']))

    def test_candidate_self_score_is_rejected(self):
        p, s, e = fixture()
        s[0]['records'][0]['value'] = 1
        with self.assertRaises(c.ContractError):
            c.report(p, s, [])

    def test_stale_evaluator_records_rejected(self):
        p, s, e = fixture()
        s[0]['procedure_id'] = 'INVENTED:different'
        with self.assertRaises(c.ContractError):
            c.report(p, s, e)

    def test_evaluator_identity_mismatch(self):
        p, s, e = fixture()
        e[0]['identity']['score_window_id'] = 'INVENTED:different-window'
        r = c.report(p, s, e)
        self.assertIn('evaluator_identity_differs', next(x for x in r['cells'] if
                      x['run_id'] == e[0]['run_id'] and x['case_id'] == e[0]['case_id'])['reasons'])

    def test_score_ranges_and_nonfinite(self):
        p, s, e = fixture()
        for bad in (float('nan'), float('inf'), True):
            x = deepcopy(e)
            x[0]['value'] = bad
            with self.assertRaises(c.ContractError):
                c.report(p, s, x)
        x = deepcopy(e)
        next(r for r in x if r['identity']['metric_id'] == c.ACCURACY)['value'] = 1.1
        with self.assertRaises(c.ContractError):
            c.report(p, s, x)

    def test_negative_signed_ve_is_preserved(self):
        p, s, e = fixture('protected_improvement')
        for x in e:
            if x['identity']['metric_id'] == c.SIGNED:
                x['value'] = -149
        r = c.report(p, s, e)
        self.assertIn(-149, [x['value'] for x in r['cells']])

    def test_normalized_cross_epoch_variance_not_clipped(self):
        p, s, e = fixture()
        e[0]['value'] = 1.2
        self.assertIn(1.2, [x['value'] for x in c.report(p, s, e)['cells']])

    def test_latency_strict_identity_no_directional_superiority(self):
        p, s, e = fixture()
        row = next(x for x in e if x['identity']['metric_id'] == c.LATENCY)
        row['value'] = -0.2
        r = c.report(p, s, e)
        self.assertIn(-0.2, [x['value'] for x in r['cells']])
        self.assertTrue(all(x['meaning'] == 'descriptive_difference_not_reproduction_or_superiority'
                            for x in r['comparisons']))

    def test_undefined_score_not_zero(self):
        p, s, e = fixture()
        e[0].update(status='undefined', value=None)
        r = c.report(p, s, e)
        self.assertTrue(any(x['status'] == 'evaluator_undefined' and x['value'] is None for x in r['cells']))

    def test_protected_both_arms_and_baselines(self):
        p, s, e = fixture('protected_improvement')
        r = c.report(p, s, e)
        self.assertEqual(len(r['denominators']), 4)
        self.assertEqual(len(r['comparisons']), 36)
        gains = [x['left_minus_right'] for x in r['comparisons'] if x['left_minus_right'] is not None]
        self.assertEqual(len(gains), 28)
        self.assertTrue(all(abs(v - .1) < 1e-15 for v in gains))

    def test_historical_parameter_grants_rejected_for_protected(self):
        for field in ('historical_rank_table', 'historical_motion_threshold'):
            p, s, e = fixture('protected_improvement')
            p['access']['paper_data_code'][field] = True
            with self.assertRaises(c.ContractError):
                c.validate_plan(p)

    def test_historical_privilege_cannot_be_called_protected(self):
        p, s, e = fixture('protected_improvement')
        for row in s[0]['records']:
            row['identity']['rank_privilege'] = 'historical_full_session'
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']
                            if x['left'].startswith('paper_data/')))

    def test_protected_split_execution_mismatch(self):
        p, s, e = fixture('protected_improvement')
        s[0]['execution_declaration']['split_realization_id'] = 'INVENTED:other-fold'
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']
                            if x['left'].startswith('paper_data/')))

    def test_protected_each_protocol_operand_required(self):
        p, s, e = fixture('protected_improvement')
        for field in c.PROTECTED_FIELDS:
            q = deepcopy(p)
            q['protected_protocol'][field] = None
            self.assertIn('protected:' + field, c.plan_gaps(q))

    def test_baseline_rerun_and_resources_required(self):
        p, s, e = fixture('protected_improvement')
        s[1]['execution_declaration']['baseline_rerun_id'] = None
        s[2]['execution_declaration']['resource_ceiling_id'] = 'INVENTED:larger-budget'
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']))

    def test_same_baseline_procedure_between_arms(self):
        p, s, e = fixture('protected_improvement')
        s[1]['procedure_id'] = 'INVENTED:unequal-baseline'
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']))

    def test_candidate_cannot_use_official_code_in_paper_data(self):
        p, s, e = fixture()
        s[0]['access_used']['official_code'] = True
        with self.assertRaises(c.ContractError):
            c.report(p, s, [])

    def test_evaluator_baseline_code_is_not_candidate_access(self):
        p, s, e = fixture('protected_improvement')
        s[1]['access_used']['official_code'] = True
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(any(x['left_minus_right'] is not None for x in r['comparisons']))

    def test_saved_outputs_or_targets_never_granted(self):
        for field in ('saved_reference_outputs', 'evaluation_targets'):
            p, s, e = fixture()
            p['access']['paper_data'][field] = True
            with self.assertRaises(c.ContractError):
                c.validate_plan(p)

    def test_unknown_or_duplicate_records_rejected(self):
        p, s, e = fixture()
        s[0]['records'].append(deepcopy(s[0]['records'][0]))
        with self.assertRaises(c.ContractError):
            c.report(p, s, [])
        p, s, e = fixture()
        e.append(deepcopy(e[0]))
        with self.assertRaises(c.ContractError):
            c.report(p, s, e)

    def test_duplicate_endpoint_does_not_pad_denominator(self):
        p, s, e = fixture()
        row = deepcopy(p['cases'][0]);row['case_id'] += ':duplicate'
        p['cases'].append(row)
        p['scope_matrix'][row['obligation']].append(row['case_id'])
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)

    def test_required_artifact_not_optional(self):
        p, s, e = fixture()
        s[0]['records'][0]['artifacts'] = []
        with self.assertRaises(c.ContractError):
            c.report(p, s, [])

    def test_protected_secondary_required_for_each_assigned_panel(self):
        p, s, e = fixture('protected_improvement')
        row = deepcopy(next(x for x in p['cases'] if x['obligation'] == 'movement_choice_prediction'))
        row.update(case_id='INVENTED:second-session', session='INVENTED:SECOND_SESSION')
        p['cases'].append(row)
        p['scope_matrix'][row['obligation']].append(row['case_id'])
        c.validate_plan(p)
        self.assertIn('protected_primary_and_secondary:movement_choice_prediction', c.plan_gaps(p))

    def test_access_privilege_is_visible_in_report(self):
        p, s, e = fixture()
        p['access']['paper_data_code']['historical_rank_table'] = True
        s[1]['access_used']['historical_rank_table'] = True
        r = c.report(p, s, rebind(p, s))
        self.assertTrue(r['access_grants']['paper_data_code']['historical_rank_table'])
        self.assertTrue(r['access_used_by_run']['paper_data_code/candidate']['historical_rank_table'])

    def test_nontext_keys_are_rejected_before_membership(self):
        p, s, e = fixture()
        p['scope_matrix']['context_projections'] = [{}]
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)
        p, s, e = fixture()
        e[0]['case_id'] = []
        with self.assertRaises(c.ContractError):
            c.report(p, s, e)

    def test_protected_intervention_must_be_declared(self):
        p, s, e = fixture('protected_improvement')
        s[0]['predictor_intervention_id'] = None
        r = c.report(p, s, score_records(p, s))
        self.assertTrue(all(x['left_minus_right'] is None for x in r['comparisons']
                            if x['left'].startswith('paper_data/')))

    def test_onset_cannot_change_fixed_randomized_cohort(self):
        for obligation, wrong in [('fixed_choice_onset', 'randomized_delay'),
                                  ('fixed_motion_onset', 'two_context_dr_wc'),
                                  ('randomized_choice_onset', 'fixed_dr'),
                                  ('randomized_motion_onset', 'two_context_dr_wc')]:
            p, s, e = fixture()
            next(r for r in p['cases'] if r['obligation'] == obligation)['cohort'] = wrong
            with self.assertRaises(c.ContractError):
                c.validate_plan(p)

    def test_protected_pair_uses_same_target_and_rows(self):
        for field in ('target_id', 'scoring_rows_id', 'aggregation_id'):
            p, s, e = fixture('protected_improvement')
            row = next(r for r in p['cases'] if r['obligation'] == 'movement_choice_prediction')
            row['identity'][field] = 'INVENTED:different'
            self.assertIn('protected_common_vector:movement_choice_prediction', c.plan_gaps(p))

    def test_metric_specific_dispatch_can_differ_for_common_vector(self):
        p, s, e = fixture('protected_improvement')
        row = next(r for r in p['cases'] if r['obligation'] == 'movement_choice_prediction')
        for field in ('normalization_denominator_id', 'dispatch_id', 'argument_binding_id'):
            row['identity'][field] = 'INVENTED:metric-specific'
        self.assertNotIn('protected_common_vector:movement_choice_prediction', c.plan_gaps(p))

    def test_duplicate_metric_does_not_fill_panel(self):
        p, s, e = fixture('protected_improvement')
        row = deepcopy(next(r for r in p['cases'] if r['obligation'] == 'movement_choice_prediction'))
        row['case_id'] = 'INVENTED:duplicate-metric'
        row['identity']['dispatch_id'] = 'INVENTED:other-scorer'
        p['cases'].append(row);p['scope_matrix'][row['obligation']].append(row['case_id'])
        c.validate_plan(p)
        self.assertIn('protected_primary_and_secondary:movement_choice_prediction', c.plan_gaps(p))

    def test_protected_secondary_has_prospective_metric_identity(self):
        p, s, e = fixture('protected_improvement')
        metrics = {r['identity']['metric_id'] for r in p['cases'] if r['obligation'].startswith('movement_')}
        self.assertEqual(metrics, {c.SIGNED, c.PAIRED_CORR})
        row = next(r for r in p['cases'] if r['identity']['metric_id'] == c.PAIRED_CORR)
        row['identity']['metric_id'] = c.CORR
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)

    def test_prospective_corr_does_not_claim_historical_reconstruction(self):
        p, s, e = fixture()
        row = next(r for r in p['cases'] if r['obligation'].startswith('movement_'))
        self.assertEqual(row['identity']['metric_id'], c.CORR)
        row['identity']['metric_id'] = c.PAIRED_CORR
        with self.assertRaises(c.ContractError):
            c.validate_plan(p)

    def test_protected_metrics_cannot_use_different_predictions(self):
        p, s, e = fixture('protected_improvement')
        row = next(r for r in s[0]['records'] if r['identity']['metric_id'] == c.PAIRED_CORR)
        row['artifacts'][0].update(logical_id='INVENTED:other-predictions', sha256='1'*64)
        r = c.report(p, s, score_records(p, s))
        pairs = [x for x in r['comparisons'] if x['obligation'] == 'movement_choice_prediction'
                 and x['left'] == s[0]['run_id']]
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(x['left_minus_right'] is None for x in pairs))
        self.assertIn('protected_prediction_artifacts_differ',
                      [z for x in r['cells'] for z in x['reasons']])

    def test_protected_primary_prediction_descriptor_is_unique(self):
        p, s, e = fixture('protected_improvement')
        row = next(r for r in s[0]['records'] if r['identity']['metric_id'] == c.PAIRED_CORR)
        row['artifacts'].append(deepcopy(row['artifacts'][0]))
        with self.assertRaises(c.ContractError):
            c.report(p, s, [])

    def test_missing_secondary_prediction_retains_incomplete_pair(self):
        p, s, e = fixture('protected_improvement')
        i = next(i for i, r in enumerate(s[0]['records']) if r['identity']['metric_id'] == c.PAIRED_CORR)
        s[0]['records'].pop(i)
        r = c.report(p, s, score_records(p, s))
        pairs = [x for x in r['comparisons'] if x['obligation'] == 'movement_choice_prediction'
                 and x['left'] == s[0]['run_id']]
        self.assertTrue(all(x['left_minus_right'] is None for x in pairs))
        self.assertEqual(sum(x['status'] == 'missing' for x in r['cells']), 1)

    def test_precomputed_parameters_require_declared_intake(self):
        for field in ('rank_privilege', 'threshold_privilege'):
            p, s, e = fixture()
            s[0]['records'][0]['identity'][field] = 'historical_precomputed'
            with self.assertRaises(c.ContractError):
                c.validate_submission(p, s[0])

    def test_full_session_fit_does_not_imply_imported_table(self):
        p, s, e = fixture()
        for row in s[0]['records']:
            row['identity']['rank_privilege'] = 'historical_full_session'
            row['identity']['threshold_privilege'] = 'historical_full_session'
        self.assertEqual(len(c.validate_submission(p, s[0])), 16)

    def test_report_serializes_without_nonstandard_numbers(self):
        p, s, e = fixture('protected_improvement')
        json.dumps(c.report(p, s, e), allow_nan=False)


if __name__ == '__main__':
    unittest.main()
