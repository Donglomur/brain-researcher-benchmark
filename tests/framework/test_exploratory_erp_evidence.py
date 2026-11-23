"""Aggregate-report discovery controls; no images, gold, models or rescoring."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

evidence = module('erp_evidence', 'src/neurobench/evidence.py')


class ExploratoryERPEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.document = json.loads((ROOT / evidence.ERP_PILOT).read_text())
        self.install(evidence.ERP_NARRATIVE, (ROOT / evidence.ERP_NARRATIVE).read_bytes())
        self.save(self.document)

    def install(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def save(self, document):
        return self.install(evidence.ERP_PILOT, json.dumps(document).encode())

    def test_episode_authorship_application_and_historical_counts_are_distinct(self):
        self.install(evidence.PILOT, (ROOT / evidence.PILOT).read_bytes())
        result = evidence.load(self.root)
        counts = result['counts']
        self.assertEqual(counts['pilot_attempts'], 8)
        self.assertEqual(counts['neural_programme_attempts'], 4)
        self.assertEqual(counts['direct_interpretation_attempts'], 32)
        self.assertEqual(counts['exploratory_programme_authoring_attempts'], 1)
        self.assertEqual(counts['exploratory_programme_query_applications'], 32)
        self.assertEqual(counts['exploratory_fixed_image_pilot_reports'], 1)
        self.assertEqual(counts['viewer_interpretation_attempts'], 0)
        self.assertEqual(counts['public_reports'], 2)
        rows = [row for row in result['records']['NEURAL-077']
                if row['category'].startswith('exploratory_')]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(row['coverage']['errors'] for row in rows), [1, 6])
        self.assertTrue(all(row['coverage']['valid_outputs'] + row['coverage']['errors'] == 32 for row in rows))
        self.assertTrue(all(row['qualification_effect'] == 'none' and not row['full_task_completed'] for row in rows))
        self.assertTrue(all(not row['protocol']['enforced_tool_sandbox']
                            and not row['protocol']['matched_compute_budgets'] for row in rows))
        direct = next(row for row in rows if row['category'] == 'exploratory_direct_interpretation')
        self.assertLess(direct['conditional_95_interval_percent'][0], 50)
        self.assertGreater(direct['conditional_95_interval_percent'][1], 50)
        self.assertIn('including delivery failures', result['count_definitions']['direct_interpretation_attempts'])

    def test_missing_stale_or_substituted_narrative_refuses(self):
        narrative = self.root / evidence.ERP_NARRATIVE
        original = narrative.read_bytes()
        narrative.unlink()
        with self.assertRaisesRegex(ValueError, 'narrative is missing'):
            evidence.load(self.root)
        narrative.write_bytes(original + b'\nChanged after projection.\n')
        with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
            evidence.load(self.root)
        narrative.write_bytes(original)
        altered = copy.deepcopy(self.document)
        altered['narrative']['path'] = '/private/other-report.md'
        self.save(altered)
        with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
            evidence.load(self.root)

    def test_failed_cases_and_protocol_limits_cannot_be_removed(self):
        mutations = (
            lambda d: d['arms']['direct'].update(query_applications=31),
            lambda d: d['arms']['programme'].update(authoring_attempts=32),
            lambda d: d['arms']['programme'].update(errors=0, valid_outputs=32),
            lambda d: d['protocol'].update(enforced_tool_sandbox=True),
            lambda d: d['protocol'].update(matched_compute_budgets=True),
            lambda d: d.update(full_task_completed=True),
            lambda d: d['posthoc_diagnostic'].update(new_predictions=6),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                document = copy.deepcopy(self.document)
                mutate(document)
                self.save(document)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_changed_frozen_aggregates_refuse_even_with_unchanged_narrative(self):
        mutations = (
            lambda d: d['arms']['direct'].update(balanced_accuracy_percent=99),
            lambda d: d['arms']['programme'].update(conditional_95_interval_percent=[0, 100]),
            lambda d: d['paired_comparison'].update(difference_percentage_points=50),
            lambda d: d['paired_comparison'].update(conditional_95_interval_percentage_points=[-10, 20]),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                document = copy.deepcopy(self.document)
                mutate(document)
                self.save(document)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_only_fixed_public_reports_open_and_unselected_fields_stay_private(self):
        document = copy.deepcopy(self.document)
        for field in ('protocol', 'paired_comparison', 'posthoc_diagnostic'):
            document[field]['private_receipt'] = '/private/never-open-or-project'
        document['private_input'] = '/private/never-open-or-project'
        self.save(document)
        opened = []
        original = Path.open
        def guarded(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, (evidence.ERP_PILOT, evidence.ERP_NARRATIVE))
            opened.append(relative)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(opened, [evidence.ERP_PILOT, evidence.ERP_NARRATIVE])
        self.assertNotIn('/private/', json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'JSON report is not allowlisted'):
            evidence.read(self.root, evidence.ERP_NARRATIVE)

    def test_new_report_requires_current_registered_task(self):
        with self.assertRaisesRegex(ValueError, 'unregistered task'):
            evidence.load(self.root, {'NEURAL-007'})
        self.assertEqual(evidence.load(self.root, {'NEURAL-077'})['counts']['direct_interpretation_attempts'], 32)

    def test_catalog_text_and_cli_projection_retain_scoped_counts(self):
        catalog = module('erp_catalog', 'src/neurobench/catalog.py')
        cli = module('erp_cli', 'src/neurobench/cli.py')
        loaded = evidence.load(self.root)
        rendered = catalog.evidence_text({'recorded_evidence': loaded})
        self.assertIn('32 direct-image episode attempts', rendered)
        self.assertIn('1 generated programme', rendered)
        self.assertIn('instruction-only', rendered)
        value = {'tasks': [{'id': 'NEURAL-077'}], 'recorded_evidence': loaded}
        with patch.object(cli, 'public_catalog_module', return_value=SimpleNamespace(load=lambda root: value)):
            result = cli.recorded_evidence('NEURAL-077', self.root)
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['records'][0]['narrative']['sha256'], self.document['narrative']['sha256'])
        old_counts = dict(loaded['counts'])
        for key in ('exploratory_fixed_image_pilot_reports', 'exploratory_programme_authoring_attempts',
                    'exploratory_programme_query_applications'):
            old_counts.pop(key)
        old = catalog.evidence_text({'recorded_evidence': {'counts': old_counts}})
        self.assertNotIn('fixed-image ERP pilot', old)


if __name__ == '__main__':
    unittest.main()
