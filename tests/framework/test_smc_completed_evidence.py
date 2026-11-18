"""Public SMC report projection: metadata only, no source/model/scorer execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location('smc_completed_' + name, ROOT / 'src/neurobench' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evidence = module('evidence')
catalog = module('catalog')


class SMCCompletedEvidenceTests(unittest.TestCase):
    def document(self, relative):
        raw = (ROOT / relative).read_bytes()
        return json.loads(raw), {'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def calibration(self):
        return self.document(evidence.SMC_CALIBRATION)

    def materials(self):
        return self.document(evidence.SMC_MATERIALS)

    def test_calibration_outputs_preserve_two_distinct_lifecycles(self):
        doc, source = self.calibration()
        rows = evidence.smc_calibration_records(doc, source)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]['scoring_execution']['supervisor_success'])
        self.assertFalse(rows[1]['scoring_execution']['supervisor_success'])
        self.assertEqual(rows[1]['scoring_execution']['scorer_child_exit_code'], 0)
        self.assertEqual(rows[1]['scoring_execution']['supervisor_exit_code'], 1)
        self.assertEqual(rows[1]['scoring_execution']['native_ledger_status'], 'failed')
        self.assertTrue(rows[1]['recovered_output_accepted'])
        for row in rows:
            self.assertEqual(len(row['metrics']), 4)
            self.assertEqual(row['scored_phase'], 'test')
            self.assertIn('no validation scoring', row['validation_panel_role'])
            self.assertEqual(row['qualification_effect'], 'none')
            self.assertEqual(row['solver_attempts_recorded'], 0)
            self.assertFalse(row['tolerance_is_success_criterion'])
            self.assertFalse(row['original_report_state']['ready_for_publication'])
            self.assertIsNone(row['original_report_state']['publication_review_accepted'])
            self.assertIn('not 108 nonempty', row['limits'][-1])

    def test_missing_arm_or_metric_refuses(self):
        for kind in ('arm', 'metric'):
            doc, source = self.calibration()
            if kind == 'arm':
                doc['arms'].pop('noncausal')
            else:
                doc['arms']['causal']['observed_metrics'].pop('fp-bps')
            with self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_noncausal_failure_cannot_be_promoted(self):
        for key, value in [('supervisor_success', True), ('supervisor_exit_code', 0),
                           ('native_ledger_status', 'succeeded'), ('existing_aggregate_root_admitted', False),
                           ('failure', None), ('scorer_child_exit_code', True)]:
            doc, source = self.calibration()
            doc['arms']['noncausal']['scoring_execution'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_report_assembly_and_root_disposition_cannot_be_rewritten(self):
        mutations = [lambda d: d.update(ready_for_publication=True),
                     lambda d: d.update(status='complete_success'),
                     lambda d: d['completion'].update(publication_review_accepted=True),
                     lambda d: d['root_disposition'].update(failure_receipt_preserved=False),
                     lambda d: d['root_disposition'].update(retry_authorized=True)]
        for mutate in mutations:
            doc, source = self.calibration()
            mutate(doc)
            with self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_candidate_or_qualification_claims_refuse(self):
        mutations = [lambda d: d['completion'].update(controlled_ai_pass=True),
                     lambda d: d['completion'].update(full_source_qualification=True),
                     lambda d: d['execution_counts'].update(candidate_runs=1),
                     lambda d: d['execution_counts'].update(llm_study_executed=True),
                     lambda d: d['scoring'].update(tolerance_is_success_criterion=True)]
        for mutate in mutations:
            doc, source = self.calibration()
            mutate(doc)
            with self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_metric_delta_nan_and_bool_refuse(self):
        for value in (float('nan'), True, 5):
            doc, source = self.calibration()
            doc['arms']['causal']['signed_delta_observed_minus_published']['co-bps'] = value
            with self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_panel_subset_or_repeat_reduction_refuses(self):
        for mutate in [lambda d: d['data']['phases']['test'].update(n_eval=573),
                       lambda d: d['data']['phases'].pop('val'),
                       lambda d: d['data'].update(full_panel_only=False),
                       lambda d: d['scoring'].update(result_group='mc_maze_val'),
                       lambda d: d['arms']['causal'].update(repeats=1)]:
            doc, source = self.calibration()
            mutate(doc)
            with self.assertRaises(ValueError):
                evidence.smc_calibration_records(doc, source)

    def test_material_pair_has_separate_non_execution_scope(self):
        doc, source = self.materials()
        row, = evidence.smc_material_records(doc, source)
        self.assertEqual(row['coverage'], {'files': 71, 'total_bytes': 31393479, 'official_assets': 10})
        self.assertFalse(row['published_payload'])
        self.assertFalse(row['participant_episode_executed'])
        self.assertEqual(row['reproduction_result'], 'not_attempted')
        self.assertEqual(row['improvement_result'], 'not_attempted')
        self.assertEqual(row['qualification_effect'], 'none')
        self.assertEqual(row['conditions'], ['paper_data', 'paper_data_author_code_and_weights'])

    def test_material_scope_inventory_and_access_mutations_refuse(self):
        for mutate in [lambda d: d['materials'].update(file_count=56),
                       lambda d: d['materials'].update(published_payload=True),
                       lambda d: d['materials'].update(all_assets_assisted_only=False),
                       lambda d: d['materials']['conditions'].pop(),
                       lambda d: d['materials']['original_source_panels']['val'].update(n_train=2295),
                       lambda d: d['interpretation'].update(AI_execution=True),
                       lambda d: d['interpretation'].update(improvement_result='win'),
                       lambda d: d['validation']['stages']['prepare'].update(exit_code=1)]:
            doc, source = self.materials()
            mutate(doc)
            with self.assertRaises(ValueError):
                evidence.smc_material_records(doc, source)

    def test_load_adds_reports_without_new_tasks_or_solver_attempts(self):
        selected = {name: self.document(name) for name in (evidence.SMC_CALIBRATION, evidence.SMC_MATERIALS)}
        with patch.object(evidence, 'read', side_effect=lambda root, relative: selected.get(relative)):
            result = evidence.load(ROOT, {'PAPER-SMC-RNN-2024'})
        self.assertEqual(result['counts']['public_reports'], 2)
        self.assertEqual(result['counts']['tasks_with_recorded_evidence'], 1)
        self.assertEqual(result['counts']['author_reference_calibration_arms'], 2)
        self.assertEqual(result['counts']['author_reference_calibration_reports'], 1)
        self.assertEqual(result['counts']['participant_material_preparation_reports'], 1)
        self.assertEqual(result['counts']['pilot_attempts'], 0)
        self.assertEqual(result['counts']['direct_interpretation_attempts'], 0)

    def test_catalog_distinguishes_old_probes_and_later_completion(self):
        counts = evidence.load(ROOT)['counts']
        rendered = catalog.evidence_text({'recorded_evidence': {'counts': counts}})
        self.assertIn('historical partial', rendered)
        self.assertIn('2 complete author-reference calibration arms', rendered)
        self.assertIn('failed supervisor', rendered)
        self.assertIn('71-file', rendered)
        self.assertNotIn('complete author calibration remains unqualified', rendered)
        old_counts = copy.deepcopy(counts)
        old_counts.pop('author_reference_calibration_arms')
        old_counts.pop('participant_material_preparation_reports')
        old_render = catalog.evidence_text({'recorded_evidence': {'counts': old_counts}})
        self.assertIn('those probes did not produce complete predictions or scores', old_render)
        self.assertNotIn('complete author-reference calibration arms', old_render)

    def test_embedded_paths_are_never_followed(self):
        doc, source = self.calibration()
        doc['private_receipt_path'] = '/private/never-read.json'
        doc['root_disposition']['private_path'] = '/private/never-read.json'
        with patch.object(Path, 'open', side_effect=AssertionError('embedded locator followed')):
            rows = evidence.smc_calibration_records(doc, source)
        self.assertNotIn('/private/', json.dumps(rows))


if __name__ == '__main__':
    unittest.main()
