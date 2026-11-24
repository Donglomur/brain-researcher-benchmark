"""Metadata-only discovery controls for incomplete image-reference calibration."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location('erp_failure_' + name, ROOT / 'src/neurobench' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evidence = module('evidence')
catalog = module('catalog')


class ERPReferenceFailureEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.document = json.loads((ROOT / evidence.ERP_REFERENCE_FAILURE).read_text())
        self.narrative = (ROOT / evidence.ERP_REFERENCE_NARRATIVE).read_bytes()
        self.install(evidence.ERP_REFERENCE_NARRATIVE, self.narrative)
        self.save(self.document)

    def install(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def save(self, document):
        return self.install(evidence.ERP_REFERENCE_FAILURE, json.dumps(document).encode())

    def test_failed_executions_fits_capture_counts_and_ai_counts_stay_distinct(self):
        result = evidence.load(self.root, {'NEURAL-077'})
        counts = result['counts']
        self.assertEqual(counts['public_reports'], 1)
        self.assertEqual(counts['image_reference_failed_calibration_reports'], 1)
        self.assertEqual(counts['image_reference_engineering_execution_attempts'], 2)
        self.assertEqual(counts['image_reference_preflight_only_failures'], 1)
        self.assertEqual(counts['image_reference_fits'], 1)
        self.assertEqual(counts['image_reference_query_capture_attempts'], 62)
        self.assertEqual(counts['image_reference_complete_query_captures'], 61)
        self.assertEqual(counts['image_reference_scored_queries'], 0)
        for key in ('pilot_attempts', 'paper_calibration_attempts', 'neural_programme_attempts',
                    'direct_interpretation_attempts', 'viewer_interpretation_attempts',
                    'author_reference_calibration_arms', 'author_reference_calibration_reports',
                    'historical_reference_rescore_models'):
            self.assertEqual(counts[key], 0, key)
        row, = result['records']['NEURAL-077']
        self.assertEqual(row['qualification_effect'], 'none')
        self.assertFalse(row['full_task_completed'])
        self.assertEqual(row['solver_attempts_recorded'], 0)
        self.assertEqual(row['metrics'], [])
        self.assertEqual(row['coverage']['unattempted_queries'], 6338)
        self.assertEqual([x['status'] for x in row['attempts']],
                         ['failed_runtime_preflight', 'failed_no_partial_qualification'])

    def test_failed_attempt_or_unattempted_cases_cannot_be_removed(self):
        mutations = (
            lambda d: d['attempts'].pop(0),
            lambda d: d['attempts'][0].update(fitted_models=1),
            lambda d: d['attempts'][1].update(failed_query_attempts=0),
            lambda d: d['attempts'][1].update(unattempted_queries=0),
            lambda d: d['attempts'][1].update(complete_query_captures=62),
            lambda d: d['attempts'][1].update(automatic_retry=True),
            lambda d: d['attempts'][1].update(full_arm_admitted=True),
            lambda d: d['cohort'].update(selected_queries=400),
        )
        for mutate in mutations:
            document = copy.deepcopy(self.document)
            mutate(document)
            self.save(document)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evidence.load(self.root)

    def test_diagnostic_cannot_become_score_or_full_population_claim(self):
        mutations = (
            lambda d: d['scientific_limits'].update(performance_metrics={'accuracy': 1}),
            lambda d: d['scientific_limits'].update(completed_benchmarks_added=1),
            lambda d: d['scientific_limits'].update(full_population_run_completed=True),
            lambda d: d['scientific_limits'].update(native_ai_understanding_assessed=True),
            lambda d: d['scientific_limits'].update(independent_generalization=True),
            lambda d: d['attempts'][1].update(scored_queries=61),
            lambda d: d['label_free_diagnostic'].update(prediction_calls=1),
            lambda d: d['label_free_diagnostic'].update(query_missing_features=0),
            lambda d: d['label_free_diagnostic'].update(visible_query_baselines_present=False),
            lambda d: d['label_free_diagnostic'].update(demo_defined_features_total=30),
            lambda d: d['followup_status'].update(historical_failures_preserved=False),
        )
        for mutate in mutations:
            document = copy.deepcopy(self.document)
            mutate(document)
            self.save(document)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evidence.load(self.root)

    def test_boolean_counts_nonfinite_time_and_changed_fixed_view_refuse(self):
        mutations = (
            lambda d: d['attempts'][0].update(fitted_models=False),
            lambda d: d['attempts'][1].update(native_wall_seconds=float('nan')),
            lambda d: d['method']['display'].update(units_per_division=50),
            lambda d: d['method']['display'].update(start_sample=-128),
            lambda d: d['method'].update(sha256='0' * 64),
            lambda d: d['attempts'][1].update(status='complete_scored'),
        )
        for mutate in mutations:
            document = copy.deepcopy(self.document)
            mutate(document)
            self.save(document)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evidence.load(self.root)

    def test_missing_changed_or_redirected_narrative_refuses(self):
        narrative = self.root / evidence.ERP_REFERENCE_NARRATIVE
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

    def test_only_allowlisted_public_bodies_are_read_and_projected(self):
        self.document['private_receipt'] = '/private/never-open.json'
        self.document['label_free_diagnostic']['private_image'] = '/private/never-open.png'
        self.document['attempts'][1]['private_predictions'] = '/private/never-open.json'
        self.save(self.document)
        opened = []
        original = Path.open
        def guarded(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, (evidence.ERP_REFERENCE_FAILURE, evidence.ERP_REFERENCE_NARRATIVE))
            opened.append(relative)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(opened, [evidence.ERP_REFERENCE_FAILURE, evidence.ERP_REFERENCE_NARRATIVE])
        self.assertNotIn('/private/', json.dumps(result))

    def test_current_status_and_task_registration_keep_failure_scope(self):
        result = evidence.load(self.root)
        rendered = catalog.evidence_text({'recorded_evidence': result})
        self.assertIn('2 failed engineering executions', rendered)
        self.assertIn('1 preflight-only', rendered)
        self.assertIn('1 reference fit', rendered)
        self.assertIn('62 query capture attempts (61 complete)', rendered)
        self.assertIn('zero scoring and no AI attempt or successful calibration', rendered)
        self.assertNotIn('2 complete author-reference calibration arms', rendered)
        with self.assertRaisesRegex(ValueError, 'unregistered task'):
            evidence.load(self.root, {'NEURAL-007'})
        old = copy.deepcopy(result)
        for key in list(old['counts']):
            if key.startswith('image_reference_'):
                del old['counts'][key]
        self.assertNotIn('full32 image-reference report', catalog.evidence_text({'recorded_evidence': old}))
        status = (ROOT / 'docs/status/README.md').read_text()
        self.assertIn('full32-image-reference-calibration-20261124.md', status)


if __name__ == '__main__':
    unittest.main()
