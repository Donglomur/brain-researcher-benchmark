"""Independent generated metadata; no source-paper values or artifact execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from neurobench import paper_panel_comparison as panel


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def fixture():
    ref = ['primary']
    def baseline(value):
        return {'status': 'verified', 'value': value, 'description': 'Generated fixed reference', 'evidence_ids': ref[:]}
    def threshold(value, status='justified'):
        return {'status': status, 'value': value, 'rationale': 'Generated predeclared threshold', 'evidence_ids': ref[:] if status == 'justified' else []}
    def row(name, direction, value, unit, tolerance, gain, control=False):
        return {'id': name, 'group_id': name, 'role': 'control' if control else 'score', 'support_key': 'complete-generated-support',
            'metric': 'fixture-' + name, 'unit': unit, 'direction': direction,
            'published_baseline': baseline(value), 'reproduced_author_baseline': baseline(value),
            'reproduction_tolerance': threshold(tolerance), 'minimum_gain': threshold(None, 'not_applicable') if control else threshold(gain),
            'gain_eligible': not control, 'gain_operator': '>=',
            'control_rule': {'status': 'specified' if control else 'not_applicable', 'minimum': .45 if control else None, 'maximum': .55 if control else None, 'rationale': 'Generated control policy', 'evidence_ids': ref[:] if control else []},
            'metric_domain': {'minimum': 0, 'maximum': 1 if unit == 'fraction' else None, 'rationale': 'Generated metric domain', 'evidence_ids': ref[:]}, 'evidence_ids': ref[:]}
    coordinates = [row('higher', 'higher', .7, 'fraction', .1, .01), row('lower', 'lower', 10, 'units', 2, .1), row('negative-control', 'not_applicable', .5, 'fraction', .1, None, True)]
    anchors = {name: {'status': 'verified', 'description': 'Generated ' + name, 'evidence_ids': ref[:]} for name in ('target', 'dataset', 'cohort', 'split', 'inputs', 'preprocessing', 'metric', 'aggregation')}
    contract = {'schema_version': panel.VERSION, 'task_id': 'GENERATED-PANEL', 'objective': 'reproduce_and_surpass_source_paper_same_panel',
        'disposition': 'metadata_ready', 'disposition_reason': 'Generated consistency controls only',
        'source_paper': {'title': 'GENERATED FICTIONAL REFERENCE', 'url': 'https://example.org/generated-fixture'},
        'evidence': [{'id': 'primary', 'kind': 'paper', 'url': 'https://example.org/generated-fixture', 'locator': 'invented fixture', 'supports': 'Generated consistency assertions only'}],
        'same_task': anchors,
        'episode': {'improvement_loop': 'Generated fixed result', 'candidate_freeze': 'Before evaluation', 'final_evaluation': 'One generated evaluation', 'access_budget': '5 generated calls cumulative', 'resource_budget': '2 generated units cumulative', 'baseline_policy': 'Both frozen and replayed author references'},
        'lineage': {'scalar_contract': {'path': 'generated-scalar.json', 'bytes': 1, 'sha256': '0' * 64}, 'selected_endpoint_contract': None, 'notes': 'Generated lineage only'},
        'panel': {'source_manifest': {'path': 'generated-roster.json', 'bytes': 1, 'sha256': '0' * 64}, 'support_scope': 'All three generated coordinates',
            'groups': [{'id': c['group_id'], 'role': c['role'], 'description': 'Generated group', 'independent_unit': 'generated independent unit', 'support_description': 'Complete generated support', 'evidence_ids': ref[:]} for c in coordinates],
            'coordinates': coordinates, 'reference_selection': {'status': 'verified', 'description': 'Generated original references', 'evidence_ids': ref[:]},
            'comparison_target': 'stronger_of_published_and_reproduced_author_per_score_coordinate',
            'score_rule': 'no_regression_on_every_score_coordinate_and_meaningful_gain_on_at_least_one_eligible_score_coordinate',
            'control_rule': 'all_required_controls_pass_their_frozen_constraints_without_contributing_improvement', 'scalar_aggregation': 'none'},
        'scientific_inference': {'status': 'unresolved', 'method': 'Not evaluated', 'independent_unit': 'Generated only', 'multiplicity_policy': 'No scientific test performed', 'evidence_ids': []}, 'blocking_issues': [],
        'binding_policy': {'evaluator': {'id': 'generated-evaluator', 'sha256': 'e' * 64, 'status': 'verified', 'evidence_ids': ref[:]},
            'budgets': {name: {'unit': 'generated-' + name, 'limit': limit, 'scope': 'cumulative_episode'} for name, limit in [('access', 5), ('resource', 2)]},
            'conditions': {name: {'paper_sha256': 'a' * 64, 'data_sha256': 'b' * 64, 'official_code_sha256': None if name == 'paper_data' else 'c' * 64, 'tool_policy_sha256': 'd' * 64} for name in ('paper_data', 'paper_data_official_code')}}}
    condition = deepcopy(contract['binding_policy']['conditions']['paper_data'])
    result = {'schema_version': panel.RESULT_VERSION, 'task_id': contract['task_id'], 'claim': 'same_task_finite_panel_numerical_comparison', 'phase': 'final', 'contract_digest': digest(contract), 'candidate_sha256': 'f' * 64,
        'same_task': deepcopy(anchors), 'source_evidence_ids': ref[:], 'access_condition': 'paper_data', 'condition_binding': condition,
        'freeze': {'contract_digest': digest(contract), 'candidate_sha256': 'f' * 64, 'frozen_at': '2026-01-01T00:00:00Z', 'evidence_ids': ['freeze'], 'access_condition': 'paper_data', 'condition_binding_digest': digest({'access_condition': 'paper_data', 'condition_binding': condition})},
        'evaluation': {'evaluator_id': 'generated-evaluator', 'evaluator_sha256': 'e' * 64, 'contract_digest': digest(contract), 'candidate_sha256': 'f' * 64, 'started_at': '2026-01-01T00:00:01Z', 'evidence_ids': ['evaluation'], 'access_condition': 'paper_data', 'condition_binding_digest': digest({'access_condition': 'paper_data', 'condition_binding': condition})},
        'reproduced_author_baseline': {'role': 'evaluator_owned_reference_shared_between_assistance_arms', 'same_task': deepcopy(anchors), 'evidence_ids': ['baseline']},
        'measurements': [{**{key: c[key] for key in ('id', 'group_id', 'role', 'support_key', 'metric', 'unit', 'direction')}, 'candidate_value': .75 if c['id'] == 'higher' else c['published_baseline']['value'], 'published_value': c['published_baseline']['value'], 'reproduced_value': c['published_baseline']['value']} for c in coordinates],
        'budget_usage': {name: {'unit': 'generated-' + name, 'used': 1, 'scope': 'cumulative_episode', 'evidence_ids': ['budget']} for name in ('access', 'resource')},
        'evidence': [{'id': name, 'kind': kind, 'sha256': sha * 64, 'locator': 'Generated metadata, no actual artifact'} for name, kind, sha in [('candidate', 'candidate', 'f'), ('freeze', 'freeze', '1'), ('evaluation', 'evaluation', '2'), ('baseline', 'reproduced_baseline', '3'), ('budget', 'budget', '4')]]}
    return contract, result


def refreeze(contract, result):
    for record in (result, result['freeze'], result['evaluation']):
        record['contract_digest'] = digest(contract)


class IndependentPanelControls(unittest.TestCase):
    def assert_base_valid(self, contract, result):
        self.assertEqual(panel.contract_validate(contract), [])
        report = panel.compare(contract, result)
        self.assertTrue(report['metadata_admitted'], report)
        return report

    def test_positive_fixture_never_qualifies_scientific_superiority(self):
        c, r = fixture(); report = self.assert_base_valid(c, r)
        self.assertTrue(report['finite_numerical_dominance'])
        self.assertIsNone(report['scientific_superiority'])
        self.assertIsNone(report['paper_win'])
        self.assertEqual(report['current_sota'], 'not_assessed')
        r['scientific_superiority'] = True
        self.assertFalse(panel.compare(c, r)['metadata_admitted'])

    def test_frozen_stronger_reference_blocks_both_directions(self):
        for index, pinned, candidate in [(0, .8, .75), (1, 8, 9)]:
            with self.subTest(index=index):
                c, r = fixture(); c['panel']['coordinates'][index]['reproduced_author_baseline']['value'] = pinned
                r['measurements'][index]['candidate_value'] = candidate; refreeze(c, r)
                report = self.assert_base_valid(c, r)
                self.assertFalse(report['score_nonregression'])
                self.assertFalse(report['finite_numerical_dominance'])

    def test_declared_decimal_stronger_selection_not_binary_mixed_order(self):
        c, r = fixture(); x = c['panel']['coordinates'][0]; m = r['measurements'][0]
        x['published_baseline']['value'] = 10**23 - 1
        x['reproduced_author_baseline']['value'] = 1e23
        x['metric_domain'].update(minimum=None, maximum=None)
        x['reproduction_tolerance']['value'] = 1; x['minimum_gain']['value'] = 1
        m.update(published_value=10**23-1, reproduced_value=1e23, candidate_value=10**23)
        refreeze(c, r); report = self.assert_base_valid(c, r)
        self.assertEqual(report['coordinate_results'][0]['gain'], '0')
        self.assertFalse(report['finite_numerical_dominance'])

    def test_declared_decimal_empty_metric_domain_is_rejected(self):
        c, _ = fixture(); x = c['panel']['coordinates'][0]
        x['published_baseline']['value'] = x['reproduced_author_baseline']['value'] = 1e23
        x['metric_domain'].update(minimum=1e23, maximum=10**23)
        self.assertTrue(panel.contract_validate(c))

    def test_access_arm_and_phase_condition_digests_cannot_be_retagged(self):
        for mutate in ('arm', 'freeze', 'evaluation'):
            with self.subTest(mutate=mutate):
                c, r = fixture()
                if mutate == 'arm':
                    r['access_condition'] = 'paper_data_official_code'
                    r['condition_binding'] = deepcopy(c['binding_policy']['conditions'][r['access_condition']])
                else:
                    r[mutate]['condition_binding_digest'] = '9' * 64
                report = panel.compare(c, r)
                self.assertFalse(report['metadata_admitted'])
                self.assertIsNone(report['finite_numerical_dominance'])

    def test_held_dispositions_cannot_numerically_admit(self):
        for disposition in ('source_unresolved', 'design_ready'):
            with self.subTest(disposition=disposition):
                c, r = fixture(); c['disposition'] = disposition; refreeze(c, r)
                self.assertEqual(panel.contract_validate(c), [])
                self.assertFalse(panel.compare(c, r)['metadata_admitted'])

    def test_mandatory_controls_do_not_supply_gains_and_fail_closed(self):
        c, r = fixture(); r['measurements'][0]['candidate_value'] = .7
        r['measurements'][2]['candidate_value'] = .55
        report = self.assert_base_valid(c, r)
        self.assertTrue(report['required_controls_pass'])
        self.assertFalse(report['finite_numerical_dominance'])
        c, r = fixture(); r['measurements'][2]['candidate_value'] = .9
        report = self.assert_base_valid(c, r)
        self.assertFalse(report['required_controls_pass'])
        self.assertFalse(report['finite_numerical_dominance'])
        c, r = fixture(); r['measurements'].pop()
        self.assertFalse(panel.compare(c, r)['metadata_admitted'])

    def test_surrogates_reject_without_uncaught_encoding_errors(self):
        c, r = fixture(); c['disposition_reason'] = '\ud800'
        self.assertTrue(panel.contract_validate(c))
        self.assertFalse(panel.compare(c, r)['metadata_admitted'])
        with self.assertRaises(ValueError):
            panel.loads_contract('{"x":"\\ud800"}')
        with self.assertRaises(ValueError):
            panel.loads_contract('{"\\ud800":"x"}')
        c, r = fixture(); r['evidence'][0]['locator'] = '\udfff'
        self.assertFalse(panel.compare(c, r)['metadata_admitted'])

    def test_reference_source_and_budget_evidence_cannot_be_substituted(self):
        for mutate in ('source', 'budget', 'reference'):
            with self.subTest(mutate=mutate):
                c, r = fixture()
                if mutate == 'source': r['source_evidence_ids'].append('invented')
                elif mutate == 'budget': r['budget_usage']['resource']['used'] = 3
                else: r['reproduced_author_baseline']['role'] = 'candidate_owned'
                self.assertFalse(panel.compare(c, r)['metadata_admitted'])


    def test_same_tool_policy_required_across_assistance_arms(self):
        contract, result = fixture()
        self.assertEqual(panel.contract_validate(contract), [])
        self.assertTrue(panel.compare(contract, result)['finite_numerical_dominance'])
        conditions = contract['binding_policy']['conditions']
        conditions['paper_data_official_code']['tool_policy_sha256'] = '9' * 64
        self.assertTrue(any('tool policy' in error for error in panel.contract_validate(contract)))
        self.assertFalse(panel.compare(contract, result)['metadata_admitted'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
