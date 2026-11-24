"""Later successful scoring remains distinct from inference and prior failures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location('smc_rescore_' + name,
                                                 ROOT / 'src/neurobench' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evidence = module('evidence')
catalog = module('catalog')


class SMCRescoreEvidenceTests(unittest.TestCase):
    def document(self, name):
        body = (ROOT / name).read_bytes()
        return json.loads(body), {'path': name, 'bytes': len(body),
                                 'sha256': hashlib.sha256(body).hexdigest()}

    def operands(self):
        doc, source = self.document(evidence.SMC_RESCORE)
        return doc, source, self.document(evidence.SMC_CALIBRATION)

    def test_successful_rescore_keeps_original_failure_and_exact_vectors(self):
        doc, source, prior = self.operands()
        rows = evidence.smc_rescore_records(doc, source, prior)
        self.assertEqual(len(rows), 2)
        for row, arm in zip(rows, ('causal', 'noncausal')):
            self.assertEqual(row['source_pointer'], '/metrics/' + arm)
            self.assertEqual({m['name']: m['value'] for m in row['metrics']}, doc['metrics'][arm]['current'])
            self.assertTrue(row['reported_known_owned_closure'])
            self.assertTrue(row['historical_failure_preserved'])
            self.assertFalse(row['historical_noncausal_supervisor_success'])
            self.assertTrue(row['canonical_train_decoder_fitting'])
            self.assertFalse(row['new_author_model_inference_or_training'])
            self.assertEqual(row['qualification_effect'], 'none')
            self.assertEqual(row['model_attempts_recorded'], 0)
            self.assertEqual(row['solver_attempts_recorded'], 0)
            self.assertIsNone(row['observed_resources']['current_child_peak_RSS_bytes'])
        original = evidence.smc_calibration_records(*prior)
        self.assertFalse(original[1]['scoring_execution']['supervisor_success'])

    def test_incomplete_vectors_nonfinite_values_and_inconsistent_deltas_refuse(self):
        mutations = [lambda d: d.update(original_task='MC_Maze, 10 ms bins; one-trial subset'),
            lambda d: d['metrics'].pop('noncausal'),
            lambda d: d['metrics']['causal']['current'].pop('fp-bps'),
            lambda d: d['metrics']['causal']['current'].update({'co-bps': float('nan')}),
            lambda d: d['metrics']['causal']['current'].update({'co-bps': True}),
            lambda d: d['metrics']['causal']['current_minus_historical'].update({'co-bps': .1}),
            lambda d: d['metrics']['causal']['current_minus_paper_printed'].update({'co-bps': 0}),
            lambda d: d['metrics']['noncausal']['historical'].update({'vel R2': .2})]
        for mutation in mutations:
            doc, source, prior = self.operands()
            mutation(doc)
            with self.assertRaises(ValueError):
                evidence.smc_rescore_records(doc, source, prior)

    def test_inflated_claims_unclosed_work_and_invented_resource_measurements_refuse(self):
        mutations = [lambda d: d['interpretation'].update(AI_or_candidate_trial=True),
            lambda d: d['interpretation'].update(exact_paper_reproduction_claim=True),
            lambda d: d['interpretation'].update(new_author_model_inference_or_training=True),
            lambda d: d['historical_noncausal_supervision'].update(supervisor_success=True),
            lambda d: d['historical_noncausal_supervision'].update(preserved_as_failed=False),
            lambda d: d['closure'].update(Docker_CLI_calls_closed=11),
            lambda d: d['closure'].update(grader_container_removed_and_absence_observed=False),
            lambda d: d['whole_two_score_limits'].update(one_budget_no_per_model_reset=False),
            lambda d: d['whole_two_score_limits'].update(child_numerical_CPU_quota=True),
            lambda d: d['observed_resources'].update(current_child_CPU_seconds=22.07),
            lambda d: d['observed_resources'].update(current_child_peak_RSS_bytes=2147483648),
            lambda d: d['observed_resources'].update(child_OOMKilled=True)]
        for mutation in mutations:
            doc, source, prior = self.operands()
            mutation(doc)
            with self.assertRaises(ValueError):
                evidence.smc_rescore_records(doc, source, prior)

    def test_rescore_requires_valid_predecessor_and_keeps_runtime_variant(self):
        doc, source, prior = self.operands()
        with self.assertRaisesRegex(ValueError, 'historical calibration report'):
            evidence.smc_rescore_records(doc, source, None)
        changed = copy.deepcopy(prior)
        changed[0]['arms']['noncausal']['scoring_execution']['supervisor_success'] = True
        with self.assertRaises(ValueError):
            evidence.smc_rescore_records(doc, source, changed)
        doc['numerical_versions']['h5py'] = '3.11.0'
        with self.assertRaises(ValueError):
            evidence.smc_rescore_records(doc, source, prior)

    def test_load_counts_one_operation_two_models_and_no_new_attempts_or_tasks(self):
        selected = {name: self.document(name) for name in (evidence.SMC_CALIBRATION, evidence.SMC_RESCORE)}
        with patch.object(evidence, 'read', side_effect=lambda root, relative: selected.get(relative)):
            result = evidence.load(ROOT, {'PAPER-SMC-RNN-2024'})
        counts = result['counts']
        self.assertEqual(counts['public_reports'], 2)
        self.assertEqual(counts['tasks_with_recorded_evidence'], 1)
        self.assertEqual(counts['historical_reference_rescore_models'], 2)
        self.assertEqual(counts['historical_reference_rescore_operations'], 1)
        self.assertEqual(counts['author_reference_calibration_arms'], 2)
        self.assertEqual(counts['pilot_attempts'], 0)
        self.assertEqual(counts['author_model_inference_probes'], 0)
        self.assertEqual(counts['direct_interpretation_attempts'], 0)
        self.assertIn('not new model or AI attempts', result['count_definitions']['historical_reference_rescore_models'])

    def test_embedded_locators_are_ignored_without_any_body_access(self):
        doc, source, prior = self.operands()
        doc['private_receipt_path'] = '/private/never-open'
        doc['closure']['raw_path'] = '/private/never-open'
        with patch.object(Path, 'open', side_effect=AssertionError('embedded locator followed')):
            rows = evidence.smc_rescore_records(doc, source, prior)
        self.assertNotIn('/private/never-open', json.dumps(rows))

    def test_catalog_reports_later_success_without_rewriting_prior_supervision(self):
        counts = evidence.load(ROOT)['counts']
        rendered = catalog.evidence_text({'recorded_evidence': {'counts': counts}})
        self.assertIn('2 frozen references successfully rescored', rendered)
        self.assertIn('failed supervisor', rendered)
        self.assertIn('no author-model inference or AI attempts', rendered)
        counts = {**counts, 'historical_reference_rescore_models': 0}
        self.assertNotIn('frozen references successfully rescored',
                         catalog.evidence_text({'recorded_evidence': {'counts': counts}}))


if __name__ == '__main__':
    unittest.main()
