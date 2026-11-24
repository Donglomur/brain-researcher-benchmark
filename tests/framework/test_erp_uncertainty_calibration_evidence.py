"""Aggregate-only closed-reference controls; no image, label, model or scoring runs."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location('erp_uncertainty_' + name, ROOT / 'src/neurobench' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evidence = module('evidence')
catalog = module('catalog')


class ERPUncertaintyCalibrationEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.document = json.loads((ROOT / evidence.ERP_UNCERTAINTY_CALIBRATION).read_text())
        self.narrative = (ROOT / evidence.ERP_UNCERTAINTY_NARRATIVE).read_bytes()
        self.install(evidence.ERP_UNCERTAINTY_NARRATIVE, self.narrative)
        self.save(self.document)

    def install(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def save(self, document):
        return self.install(evidence.ERP_UNCERTAINTY_CALIBRATION, json.dumps(document).encode())

    def complete_fixture(self):
        """Generated all-support arithmetic fixture, never an empirical result."""
        document = copy.deepcopy(self.document)
        operation = document['operations'][1]
        operation.update(status='complete_scored', counts={
            'engineering_executions': 1, 'reference_fits': 1, 'query_capture_attempts': 6400,
            'complete_query_captures': 6400, 'interrupted_query_captures': 0,
            'failed_query_captures': 0, 'unattempted_queries': 0,
            'score_operations': 1, 'scored_queries': 6400, 'complete_reference_calibrations': 1},
            aggregate_metrics={'participant_macro_balanced_accuracy': .5,
                               'participant_macro_natural_log_loss': math.log(2)},
            analytic_comparators={
                'constant_half': {'probability': .5, 'balanced_accuracy': .5, 'natural_log_loss': math.log(2)},
                'constant_source_prior': {'probability': .2, 'balanced_accuracy': .5,
                    'natural_log_loss': .5004024235381879, 'used_by_classifier': False}},
            support_diagnostics={'queries': 6400, 'features_per_query': 30,
                'feature_order': 'Cz fifteen postmarker50ms bins, then Pz fifteen postmarker50ms bins',
                'no_shared_support_queries': 0, 'positive_shared_support_queries': 6400,
                'feature_defined_queries': [6400] * 30, 'feature_mean_coverage': [.5] * 30,
                'feature_mean_shared_weight': [.5] * 30, 'baseline_mean_coverage': [.5] * 2,
                'mean_shared_support_fraction': .5})
        operation['worker_custody']['scorer_gate'] = 'all_6400_first_captures_admitted_before_private_access'
        return document

    def reject_mutations(self, document, mutations):
        for label, mutate in mutations.items():
            with self.subTest(case=label):
                changed = copy.deepcopy(document)
                mutate(changed)
                self.save(changed)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_closed_execution_fit_capture_and_score_units_do_not_become_ai_attempts(self):
        result = evidence.load(self.root, {'NEURAL-077'})
        counts = result['counts']
        self.assertEqual(counts['public_reports'], 1)
        self.assertEqual(counts['uncertainty_reference_operations'], 2)
        self.assertEqual(counts['uncertainty_reference_root_early_stops'], 1)
        self.assertEqual(counts['uncertainty_reference_engineering_executions'], 2)
        early, = [row for row in result['records']['NEURAL-077'] if row['status'] == 'root_early_stopped_unscored']
        self.assertEqual(early['coverage']['query_capture_attempts'], 2123)
        self.assertEqual(early['coverage']['complete_query_captures'], 2122)
        self.assertEqual(early['coverage']['interrupted_query_captures'], 1)
        self.assertEqual(early['coverage']['unattempted_queries'], 4277)
        self.assertEqual(early['coverage']['scored_queries'], 0)
        self.assertEqual(early['metrics'], [])
        self.assertFalse(early['reference_calibration_complete'])
        for key in ('pilot_attempts', 'paper_calibration_attempts', 'neural_programme_attempts',
                    'direct_interpretation_attempts', 'viewer_interpretation_attempts',
                    'author_reference_calibration_arms', 'image_reference_engineering_execution_attempts'):
            self.assertEqual(counts[key], 0, key)
        for row in result['records']['NEURAL-077']:
            self.assertEqual(row['qualification_effect'], 'none')
            self.assertEqual(row['solver_attempts_recorded'], 0)
            self.assertFalse(row['full_task_completed'])
        self.assertIn('not unique cases', result['count_definitions']['uncertainty_reference_query_capture_attempts'])

    def test_capture_denominators_fit_stages_source_and_scientific_scope_refuse(self):
        self.reject_mutations(self.document, {
            'drop-U': lambda d: d['operations'].pop(0),
            'open-K': lambda d: d['operations'][1].update(closed=False),
            'invalid-closed-aggregate-pin': lambda d: d['operations'][1]['reported_authority'].update(aggregate_or_owner_result_sha256='bad'),
            'lost-interruption': lambda d: d['operations'][0]['counts'].update(interrupted_query_captures=0),
            'unattempted': lambda d: d['operations'][0]['counts'].update(unattempted_queries=0),
            'bool-count': lambda d: d['operations'][0]['counts'].update(reference_fits=True),
            'fit-after-query': lambda d: d['operations'][0]['counts'].update(reference_fits=0),
            'changed-gain': lambda d: d['method']['display'].update(units_per_division=50),
            'pooled-aggregation': lambda d: d['metric_policy'].update(aggregation='pooled_queries'),
            'changed-threshold': lambda d: d['metric_policy'].update(positive_threshold_inclusive=.2),
            'changed-log-base': lambda d: d['metric_policy'].update(log_base='base2'),
            'changed-method': lambda d: d['method'].update(algorithm_sha256='0' * 64),
            'benchmark-promotion': lambda d: d['scientific_limits'].update(completed_benchmarks_added=1),
            'competence-promotion': lambda d: d['scientific_limits'].update(trained_competency_baseline_established=True),
            'lost-history': lambda d: d['scientific_limits'].update(historical_failures_preserved=False),
            'reuse-partial-U': lambda d: d['operations'][1].update(fresh_collection_no_reuse_or_resume=False),
        })

    def test_root_projection_stop_cannot_become_observed_deadline_or_classifier_failure(self):
        self.reject_mutations(self.document, {
            'deadline-failure': lambda d: d['operations'][0]['stop'].update(actual_deadline_failure=True),
            'classifier-failure': lambda d: d['operations'][0]['stop'].update(classifier_failure=True),
            'changed-reason': lambda d: d['operations'][0]['stop'].update(reason='deadline_exceeded'),
            'under-quote': lambda d: d['operations'][0]['stop'].update(projected_collection_seconds=1),
            'zero-rate': lambda d: d['operations'][0]['stop'].update(measured_captures_per_second=0),
            'negative-wall': lambda d: d['operations'][0].update(native_wall_seconds=-1),
            'nonfinite-wall': lambda d: d['operations'][0].update(native_wall_seconds=float('nan')),
            'unknown-owned-process': lambda d: d['operations'][0]['closure'].update(all_known_owned_processes_absent=False),
            'stronger-containment': lambda d: d['operations'][0]['closure'].update(escaped_descendant_containment_claim=True),
        })

    def test_complete_score_requires_all_captures_and_target_last_admission(self):
        document = self.complete_fixture()
        self.save(document)
        result = evidence.load(self.root)
        complete, = [row for row in result['records']['NEURAL-077'] if row['reference_calibration_complete']]
        self.assertEqual(complete['coverage']['scored_queries'], 6400)
        self.assertEqual([item['value'] for item in complete['metrics']], [.5, math.log(2)])
        self.assertEqual(complete['support_diagnostics']['positive_shared_support_queries'], 6400)
        self.assertEqual(result['counts']['uncertainty_reference_complete_reference_calibrations'], 1)
        self.reject_mutations(document, {
            'partial-score': lambda d: d['operations'][1]['counts'].update(scored_queries=6399),
            'partial-capture': lambda d: d['operations'][1]['counts'].update(complete_query_captures=6399, failed_query_captures=1),
            'unfitted-score': lambda d: d['operations'][1]['counts'].update(reference_fits=0),
            'scorer-not-admitted': lambda d: d['operations'][1]['worker_custody'].update(scorer_gate='not_reached'),
            'no-metrics': lambda d: d['operations'][1].update(aggregate_metrics=None),
            'two-scoring-operations': lambda d: d['operations'][1]['counts'].update(score_operations=2),
            'U-partial-metric': lambda d: d['operations'][0].update(aggregate_metrics={'accuracy': 1}),
        })

    def test_metrics_and_analytic_comparators_reject_malformed_or_substituted_results(self):
        self.reject_mutations(self.complete_fixture(), {
            'boolean-metric': lambda d: d['operations'][1]['aggregate_metrics'].update(participant_macro_balanced_accuracy=True),
            'nonfinite-metric': lambda d: d['operations'][1]['aggregate_metrics'].update(participant_macro_natural_log_loss=float('inf')),
            'accuracy-over-one': lambda d: d['operations'][1]['aggregate_metrics'].update(participant_macro_balanced_accuracy=1.1),
            'negative-loss': lambda d: d['operations'][1]['aggregate_metrics'].update(participant_macro_natural_log_loss=-1),
            'prior-in-classifier': lambda d: d['operations'][1]['analytic_comparators']['constant_source_prior'].update(used_by_classifier=True),
            'altered-half-loss': lambda d: d['operations'][1]['analytic_comparators']['constant_half'].update(natural_log_loss=.5),
            'wrong-prior': lambda d: d['operations'][1]['analytic_comparators']['constant_source_prior'].update(probability=.25),
        })

    def test_support_diagnostics_preserve_case_feature_and_fraction_units(self):
        self.reject_mutations(self.complete_fixture(), {
            'case-denominator': lambda d: d['operations'][1]['support_diagnostics'].update(queries=2122),
            'support-denominator': lambda d: d['operations'][1]['support_diagnostics'].update(no_shared_support_queries=1),
            'feature-count': lambda d: d['operations'][1]['support_diagnostics']['feature_defined_queries'].pop(),
            'bool-feature-count': lambda d: d['operations'][1]['support_diagnostics']['feature_defined_queries'].__setitem__(0, True),
            'impossible-defined': lambda d: d['operations'][1]['support_diagnostics']['feature_defined_queries'].__setitem__(0, 6401),
            'mean-without-defined': lambda d: d['operations'][1]['support_diagnostics']['feature_defined_queries'].__setitem__(0, 0),
            'inconsistent-weights': lambda d: d['operations'][1]['support_diagnostics'].update(mean_shared_support_fraction=.2),
            'missing-baseline': lambda d: d['operations'][1]['support_diagnostics']['baseline_mean_coverage'].pop(),
            'weights-without-features': lambda d: d['operations'][1]['support_diagnostics'].update(
                feature_defined_queries=[0] * 30, feature_mean_coverage=[0] * 30),
            'support-count-upper-bound': lambda d: d['operations'][1]['support_diagnostics'].update(
                positive_shared_support_queries=1, no_shared_support_queries=6399),
            'weights-without-baseline': lambda d: d['operations'][1]['support_diagnostics'].update(
                baseline_mean_coverage=[0, .5]),
        })

    def test_worker_target_last_cannot_erase_root_machine_search_disclosure(self):
        self.reject_mutations(self.document, {
            'global-unopened': lambda d: d['root_operator_disclosure'].update(global_targets_unopened=True),
            'scope-equivalence': lambda d: d['root_operator_disclosure'].update(isolated_target_last_is_global_custody=True),
            'erase-machine-reads': lambda d: d['root_operator_disclosure']['metadata_hash_search'].update(protected_json_files_machine_read=0),
            'erase-prior-exposure': lambda d: d['root_operator_disclosure'].update(prior_full_population_exposure=False),
            'worker-global-claim': lambda d: d['operations'][0]['worker_custody'].update(global_target_unopened_claim=True),
            'worker-target-access': lambda d: d['operations'][0]['worker_custody'].update(prediction_worker_query_target_access='permitted'),
            'unsupported-custody-basis': lambda d: d['operations'][0]['worker_custody'].update(basis='inferred_from_stage_only'),
        })
        self.save(self.document)
        result = evidence.load(self.root)
        for row in result['records']['NEURAL-077']:
            self.assertTrue(row['worker_custody']['isolated_target_last'])
            self.assertFalse(row['root_operator_disclosure']['global_targets_unopened'])
            self.assertEqual(row['root_operator_disclosure']['metadata_hash_search']['protected_json_bytes_machine_read'], 756023)
            self.assertEqual(row['root_operator_disclosure']['metadata_hash_search']['read_accounting_basis'],
                             'conservative_file_extent_accounting')
            self.assertFalse(row['root_operator_disclosure']['metadata_hash_search']['kernel_file_read_census'])

    def test_failed_measured_operation_retains_unattempted_denominator_without_partial_score(self):
        document = self.complete_fixture()
        operation = document['operations'][1]
        operation.update(status='failed_unscored', aggregate_metrics=None,
            analytic_comparators=None, support_diagnostics=None, counts={
                'engineering_executions': 1, 'reference_fits': 1, 'query_capture_attempts': 1,
                'complete_query_captures': 0, 'interrupted_query_captures': 0,
                'failed_query_captures': 1, 'unattempted_queries': 6399,
                'score_operations': 0, 'scored_queries': 0, 'complete_reference_calibrations': 0})
        operation['worker_custody']['scorer_gate'] = 'not_reached'
        self.save(document)
        result = evidence.load(self.root)
        self.assertEqual(result['counts']['uncertainty_reference_complete_reference_calibrations'], 0)
        self.assertEqual(result['counts']['uncertainty_reference_scored_queries'], 0)
        self.assertEqual(result['counts']['uncertainty_reference_failed_query_captures'], 1)
        self.assertEqual(result['counts']['uncertainty_reference_unattempted_queries'], 4277 + 6399)
        self.reject_mutations(document, {
            'partial-result': lambda d: d['operations'][1].update(aggregate_metrics={'accuracy': .5}),
            'false-completion': lambda d: d['operations'][1]['counts'].update(complete_reference_calibrations=1),
            'missing-case': lambda d: d['operations'][1]['counts'].update(unattempted_queries=6398),
        })

    def test_missing_changed_or_redirected_narrative_refuses(self):
        narrative = self.root / evidence.ERP_UNCERTAINTY_NARRATIVE
        narrative.unlink()
        with self.assertRaisesRegex(ValueError, 'narrative is missing'):
            evidence.load(self.root)
        narrative.write_bytes(self.narrative + b'changed')
        with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
            evidence.load(self.root)
        narrative.write_bytes(self.narrative)
        self.document['narrative']['path'] = '/private/never-open.md'
        self.save(self.document)
        with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
            evidence.load(self.root)

    def test_only_allowlisted_public_bodies_are_opened_and_private_locators_are_omitted(self):
        self.document['private_receipt'] = '/private/never-open.json'
        self.document['operations'][0]['private_predictions'] = '/private/never-open.json'
        self.save(self.document)
        opened = []
        original = Path.open
        def guarded(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, (evidence.ERP_UNCERTAINTY_CALIBRATION, evidence.ERP_UNCERTAINTY_NARRATIVE))
            opened.append(relative)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(opened, [evidence.ERP_UNCERTAINTY_CALIBRATION, evidence.ERP_UNCERTAINTY_NARRATIVE])
        self.assertNotIn('/private/', json.dumps(result))

    def test_catalog_status_and_registration_preserve_reference_scope(self):
        result = evidence.load(self.root)
        rendered = catalog.evidence_text({'recorded_evidence': result})
        self.assertIn('root timing-based early stop', rendered)
        self.assertIn('2,122 complete captured responses, one interrupted, 4,277 unattempted; zero scores', rendered)
        self.assertIn('no AI attempts or benchmarks are added', rendered)
        self.assertIn('Root machine-search exposure remains distinct', rendered)
        self.assertNotIn('failed engineering executions', rendered)
        old = copy.deepcopy(result)
        for key in list(old['counts']):
            if key.startswith('uncertainty_reference_'):
                del old['counts'][key]
        self.assertNotIn('uncertainty-reference report', catalog.evidence_text({'recorded_evidence': old}))
        with self.assertRaisesRegex(ValueError, 'unregistered task'):
            evidence.load(self.root, {'NEURAL-007'})
        self.assertIn('full32-image-uncertainty-calibration-20261124.md', (ROOT / 'docs/status/README.md').read_text())


if __name__ == '__main__':
    unittest.main()
