"""Metadata summaries retain the existing unit definitions beside evidence counts."""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('status_evidence_units_cli', ROOT / 'src/neurobench/cli.py')
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


class StatusEvidenceUnitTests(unittest.TestCase):
    def test_status_and_check_keep_evidence_units_without_promoting_qualification(self):
        # Generated public metadata: operation counts are not unique populations.
        evidence = {
            'counts': {'uncertainty_reference_query_capture_attempts': 8523,
                       'uncertainty_reference_operations': 2,
                       'trusted_operator_reference_estimator_fits': 5685},
            'reports': [{'path': 'docs/example.json', 'bytes': 23, 'sha256': 'a' * 64}],
            'scope': 'Selected public reports only, not current runtime verification.',
            'count_definitions': {
                'uncertainty_reference_query_capture_attempts': 'Summed across operations; not unique cases.',
                'trusted_operator_reference_estimator_fits': 'Estimator fits, not people or AI attempts.'},
            'records': {'EXAMPLE': [{'category': 'trusted_operator_reference'}]},
            'unselected_private_locator': '/not-a-public-summary-field'}
        catalog = {
            'counts': {'total': 3, 'paper': 1, 'neural': 2, 'canonical_specifications': 1,
                       'expansion_drafts': 2, 'runtime_manifests': 1, 'source_components': 7},
            'tasks': [], 'paper_improvement_counts': {}, 'paper_outcome_counts': {},
            'neural_understanding_counts': {}, 'recorded_evidence': evidence,
            'counting_note': 'Registrations and components are separate from scientific results.'}
        before = copy.deepcopy(catalog)
        builder = SimpleNamespace(load=Mock(return_value=catalog), generate=Mock(return_value=catalog))
        with patch.object(cli, 'public_catalog_module', return_value=builder), \
                patch.object(cli, 'public_metadata_mode', return_value=True), \
                patch.object(cli.subprocess, 'run', side_effect=AssertionError('metadata executed a process')), \
                patch.object(cli, 'run_command', side_effect=AssertionError('metadata dispatched a programme')), \
                patch.object(cli, 'score_command', side_effect=AssertionError('metadata dispatched scoring')):
            complete_evidence = cli.recorded_evidence(root=ROOT)
            for action in ('status', 'check'):
                with self.subTest(action=action):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(cli.main([action], root=ROOT), 0)
                    summary = json.loads(output.getvalue())
                    projected = summary['recorded_evidence']
                    self.assertEqual(projected.get('count_definitions'), complete_evidence['count_definitions'])
                    self.assertEqual(projected['counts'], complete_evidence['counts'])
                    self.assertEqual(set(projected), {'counts', 'reports', 'scope', 'count_definitions'})
                    self.assertEqual(summary['target_assignments'], 3)
                    self.assertEqual(summary['supporting_source_components'], 7)
                    self.assertEqual(summary['scientific_readiness'], 'unknown')
                    self.assertEqual(summary['submission_readiness'], 'unknown')
                    for field in ('research_qualified', 'submission_ready', 'local_program_runners_verified',
                                  'local_score_adapters_verified', 'bounded_reference_runs_recorded'):
                        self.assertIsNone(summary[field])
        self.assertEqual(catalog, before)


if __name__ == '__main__':
    unittest.main()
