"""Invented operator records only; no models, data, checkpoints or metric runs."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import compare_v2 as c


def observation(run_id='invented-reference', historical=False):
    condition = c.HISTORICAL if historical else c.PROTECTED
    protocol = {key: 'invented-' + key for key in c.PROTOCOL_FIELDS}
    protocol.update(target='speed', task_kind='retrospective_decoding', aggregation='pooled_ordered_rows_pearson')
    declarations = {key: True for key in c.DECLARATION_FIELDS}
    declarations['evaluation_targets_used_for_selection'] = historical
    declarations['evaluation_targets_hidden_until_predictions_committed'] = not historical
    if historical:
        protocol['selection_support'] = protocol['evaluation_support']
    return {'schema': 'neuroformer_operator_observation_v1', 'run_id': run_id,
            'cell_id': 'lateral--speed_regression--neuroformer--100::' + condition,
            'access_arm': 'paper_and_data', 'method_identity': 'invented-method', 'seed': 19,
            'protocol': protocol, 'declarations': declarations,
            'prior_evaluation_access': 'yes' if historical else 'no',
            'metric_profile': 'released_plot_first200_pearson' if historical else 'protected_full_support_pearson',
            'metric': 'pearson_r', 'n_total': 500, 'n_scored': 200 if historical else 500,
            'value': 0.4, 'undefined_reason': None}


class ComparabilityTests(unittest.TestCase):
    def pair(self, historical=False):
        a=observation(historical=historical); b=observation('invented-candidate', historical)
        b['value']=0.3
        return a,b

    def blocked(self,a,b,intent='protected_improvement'):
        result=c.compare(a,b,intent)
        self.assertEqual(result['status'],'blocked')
        self.assertIsNone(result['signed_candidate_minus_reference'])
        self.assertFalse(result['claim_awarded'])
        return result

    def test_negative_effect_is_retained_without_awarding_claim(self):
        a,b=self.pair(); result=c.compare(a,b,'protected_improvement')
        self.assertAlmostEqual(result['signed_candidate_minus_reference'],-.1)
        self.assertEqual(result['status'],'comparable_under_operator_declarations')
        self.assertFalse(result['scientifically_qualified'])
        self.assertTrue(result['unresolved_cell_holds'])

    def test_historical_replay_is_exposed_discrepancy(self):
        a,b=self.pair(True); result=c.compare(a,b,'released_replay')
        self.assertAlmostEqual(result['absolute_difference'],.1)
        self.assertIn('exposed',result['interpretation'])

    def test_historical_cannot_be_clean_improvement(self):
        self.blocked(*self.pair(True))

    def test_cross_profile_first200_vs_full_support_is_blocked(self):
        self.blocked(observation(historical=True),observation('candidate'))

    def test_same_n_but_different_support_is_blocked(self):
        a,b=self.pair(); b['protocol']['evaluation_support']='other-500-rows'; self.blocked(a,b)

    def test_data_resources_features_pretraining_and_budget_mismatches_are_blocked(self):
        for key in ('data_revision','resource_budget','features','pretraining_resources','noncode_resources','context_policy','selection_policy','feedback_policy'):
            with self.subTest(key=key):
                a,b=self.pair(); b['protocol'][key]='other'; self.blocked(a,b)

    def test_only_declared_protected_gates_are_sufficient_for_descriptive_math(self):
        for key in c.DECLARATION_FIELDS:
            with self.subTest(key=key):
                a,b=self.pair(); b['declarations'][key]=not b['declarations'][key]; self.blocked(a,b)

    def test_false_historical_target_hiding_is_refused(self):
        a,b=self.pair(True); b['declarations']['evaluation_targets_hidden_until_predictions_committed']=True
        self.blocked(a,b,'released_replay')

    def test_shared_protected_role_identity_is_refused_even_with_true_gate(self):
        a,b=self.pair()
        for x in (a,b): x['protocol']['selection_support']=x['protocol']['evaluation_support']
        self.blocked(a,b)

    def test_disjoint_historical_selection_is_different_protocol(self):
        a,b=self.pair(True)
        for x in (a,b): x['protocol']['selection_support']='separate-validation'
        self.blocked(a,b,'released_replay')

    def test_unknown_and_known_prior_exposure_remain_blocking(self):
        for value in ('unknown','yes'):
            a,b=self.pair(); b['prior_evaluation_access']=value; self.blocked(a,b)

    def test_forecasting_and_alternative_aggregation_are_not_silently_accepted(self):
        for key,value in (('task_kind','online_forecast'),('aggregation','average_pearson_across_mice')):
            a,b=self.pair()
            for x in (a,b): x['protocol'][key]=value
            self.blocked(a,b)

    def test_undefined_is_not_zero_or_dropped(self):
        a,b=self.pair(); b['value']=None; b['undefined_reason']='constant prediction'
        result=self.blocked(a,b); self.assertTrue(any('constant prediction' in reason for reason in result['reasons']))

    def test_invalid_pearson_nan_infinity_and_bool_refused(self):
        for value in (True,math.nan,math.inf,1.01,-1.01):
            a,b=self.pair(); b['value']=value
            with self.assertRaises(c.ContractError): c.compare(a,b,'protected_improvement')

    def test_profile_support_cannot_be_silently_trimmed(self):
        for historical in (False,True):
            a,b=self.pair(historical); b['n_scored']=199
            with self.assertRaises(c.ContractError): c.compare(a,b,'released_replay' if historical else 'protected_improvement')

    def test_access_pair_changes_only_declared_code_access(self):
        a,b=self.pair(); b['access_arm']='paper_data_official_code'
        result=c.compare(a,b,'code_access_effect')
        self.assertEqual(result['status'],'comparable_under_operator_declarations')
        self.assertFalse(result['claim_awarded']); self.blocked(a,b)
        self.blocked(b,a,'code_access_effect')

    def test_historical_access_pair_cannot_support_clean_code_effect(self):
        a,b=self.pair(True); b['access_arm']='paper_data_official_code'; self.blocked(a,b,'code_access_effect')

    def test_different_seed_same_run_or_different_cell_not_paired(self):
        for key,value in (('seed',20),('run_id','invented-reference'),('cell_id','medial--speed_regression--neuroformer--100::'+c.PROTECTED)):
            a,b=self.pair(); b[key]=value; self.blocked(a,b)

    def test_unknown_extra_fields_and_numeric_gate_refused(self):
        for change in ('extra','gate','cell'):
            a,b=self.pair()
            if change=='extra': b['clean_sota']=True
            if change=='gate': b['declarations']['physical_isolation_enforced']=1
            if change=='cell': b['cell_id']='fake'
            with self.assertRaises(c.ContractError): c.compare(a,b,'protected_improvement')

    def test_paper_target_exact_match_still_not_reproduction(self):
        x=observation(); x['value']=.95
        result=c.published_target_gap(x,'arxiv-v4-table1-lateral-neuroformer')
        self.assertEqual(result['descriptive_gap_only'],0)
        self.assertIsNone(result['reproduction_pass']); self.assertIsNone(result['tolerance'])
        self.assertFalse(result['claim_awarded']); self.assertTrue(result['reasons'])

    def test_wrong_paper_cohort_does_not_get_gap(self):
        self.assertIsNone(c.published_target_gap(observation(),'arxiv-v4-table1-medial-neuroformer')['descriptive_gap_only'])

    def test_gru_alias_is_not_declared_paper_mapping(self):
        x=observation(); x['cell_id']='lateral--speed_regression--bidirectional_gru--100::'+c.PROTECTED; x['method_identity']='released-unidirectional-gru-recipe'
        result=c.published_target_gap(x,'arxiv-v4-table1-lateral-bidirectional_gru')
        self.assertEqual(result['status'],'unmapped_not_reproduced'); self.assertIsNone(result['reproduction_pass'])

    def test_all_85_cells_46_slots_and_seven_families_remain(self):
        scope=c.read_json(c.HERE/'scope.json')
        self.assertEqual(len(scope['cells']),85)
        self.assertEqual(len({x['case']['id'] for x in scope['cells']}),46)
        self.assertEqual(len(scope['wider_families']),7)
        self.assertEqual(sum(x['concrete_historical_factory_source_available'] for x in scope['cells']),2)
        self.assertTrue(all(not x['ready'] and x['holds'] for x in scope['cells']))

    def test_unresolved_metric_profiles_not_replaced_with_pearson(self):
        scope=c.read_json(c.HERE/'scope.json')
        for cell in scope['cells']:
            if cell['metric_profile'] not in c.SCALAR_PROFILES:
                a,b=self.pair()
                for x in (a,b): x['cell_id']=cell['id']; x['metric_profile']=cell['metric_profile']
                self.blocked(a,b)

    def test_json_duplicate_and_nonfinite_fields_refused(self):
        with tempfile.TemporaryDirectory(dir=c.HERE) as directory:
            p=Path(directory)/'tiny.json'
            for raw in ('{"a":1,"a":2}','{"a":NaN}'):
                p.write_text(raw)
                with self.assertRaises(c.ContractError): c.read_json(p)

    def test_joint_speed_and_gaze_reports_retain_distinct_endpoint_identity(self):
        a,b=self.pair()
        for x in (a,b): x['cell_id']='lateral--joint_speed_gaze--neuroformer--100::'+c.PROTECTED
        speed=c.compare(a,b,'protected_improvement')
        for x in (a,b): x['protocol']['target']='phi'
        gaze=c.compare(a,b,'protected_improvement')
        self.assertNotEqual(speed,gaze)
        self.assertEqual(speed['observations'][0]['protocol']['target'],'speed')
        self.assertEqual(gaze['observations'][0]['protocol']['target'],'phi')
        self.assertEqual(gaze['observations'][0]['n_scored'],500)

    def test_native_th_is_supported_without_inventing_theta_alias(self):
        a,b=self.pair()
        for x in (a,b):
            x['cell_id']='lateral--joint_speed_gaze--neuroformer--100::'+c.PROTECTED
            x['protocol']['target']='th'
        self.assertEqual(c.compare(a,b,'protected_improvement')['status'],'comparable_under_operator_declarations')
        b['protocol']['target']='theta'
        with self.assertRaises(c.ContractError): c.compare(a,b,'protected_improvement')

    def test_conflicting_versions_have_distinct_target_ids_and_no_chosen_winner(self):
        x=observation(); x['value']=.95
        arxiv=c.published_target_gap(x,'arxiv-v4-table1-lateral-neuroformer')
        final=c.published_target_gap(x,'iclr-proceedings-table1-lateral-neuroformer')
        self.assertEqual(arxiv['descriptive_gap_only'],0)
        self.assertAlmostEqual(final['descriptive_gap_only'],-.02)
        self.assertIsNone(final['reproduction_pass'])
        self.assertEqual(final['observation']['run_id'],x['run_id'])
        self.assertNotEqual(arxiv['source_version'],final['source_version'])
        with self.assertRaises(c.ContractError): c.published_target_gap(x,'table1-lateral-neuroformer')


if __name__=='__main__': unittest.main(verbosity=2)
