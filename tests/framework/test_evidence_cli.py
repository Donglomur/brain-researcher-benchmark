"""Public report navigation and raw operator dispatch, without candidate execution."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('evidence_command_tests_cli', ROOT / 'src/neurobench/cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class EvidenceCommandTests(unittest.TestCase):
    def command(self, arguments):
        output = io.StringIO()
        with redirect_stdout(output), \
                patch.object(cli.subprocess, 'run', side_effect=AssertionError('metadata executed a process')), \
                patch.object(cli, 'run_command', side_effect=AssertionError('metadata prepared a programme')), \
                patch.object(cli, 'score_command', side_effect=AssertionError('metadata prepared a score')):
            code = cli.main(arguments, root=ROOT)
        self.assertEqual(code, 0)
        return json.loads(output.getvalue())

    def test_all_report_counts_remain_distinct_from_qualification(self):
        result = self.command(['evidence'])
        self.assertEqual(result['counts']['pilot_attempts'], 8)
        self.assertEqual(result['counts']['paper_calibration_attempts'], 4)
        self.assertEqual(result['counts']['neural_programme_attempts'], 4)
        self.assertEqual(result['counts']['direct_interpretation_attempts'], 0)
        self.assertEqual(result['counts']['viewer_interpretation_attempts'], 0)
        self.assertEqual(result['counts']['tasks_with_recorded_evidence'], 5)
        self.assertIn('selected public reports only', result['scope'])
        self.assertIn('not current runtime verification', result['scope'])
        for task_records in result['records'].values():
            for record in task_records:
                self.assertEqual(record['qualification_effect'], 'none')
                self.assertNotIn('scientific_readiness', record)
                self.assertNotIn('submission_ready', record)
        status = self.command(['status'])
        self.assertEqual(status['recorded_evidence']['counts'], result['counts'])
        self.assertEqual(status['scientific_readiness'], 'unknown')
        self.assertEqual(status['submission_readiness'], 'unknown')
        self.assertIsNone(status['research_qualified'])
        self.assertIsNone(status['local_program_runners_verified'])
        self.assertIsNone(status['local_score_adapters_verified'])

    def test_task_view_retains_programme_conditions_and_metric_tradeoff(self):
        result = self.command(['evidence', 'NEURAL-077'])
        self.assertEqual(result['task_id'], 'NEURAL-077')
        self.assertTrue(all(record['task_id'] == 'NEURAL-077' for record in result['records']))
        attempts = [record for record in result['records'] if record['category'] == 'neural_programme_attempt']
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(record['condition'] == 'EEG_and_permitted_nuisance_features_program'
                            for record in attempts))
        self.assertTrue(all('not direct or viewer interpretation' in record['scope'] for record in attempts))
        first = next(record for record in attempts if record['attempt_id'] == 'neural077-1')
        primary, secondary = first['metrics']
        self.assertGreater(primary['value'], primary['comparators']['eeg'])
        self.assertEqual(primary['direction'], 'higher')
        self.assertGreater(secondary['value'], secondary['comparators']['prior'])
        self.assertEqual(secondary['direction'], 'lower')
        self.assertEqual(first['coverage'], {'validated_trials': 400})
        self.assertTrue(first['limits'])
        self.assertTrue(any(record['category'] == 'authentic_input_materialization' for record in result['records']))
        self.assertTrue(any(record['category'] == 'authentic_viewer_rendering' for record in result['records']))

    def test_historical_paper_evidence_does_not_become_paper_success(self):
        result = self.command(['evidence', 'PAPER-FIND-REP-013'])
        attempts = [record for record in result['records'] if record['category'] == 'paper_calibration_attempt']
        self.assertEqual(len(attempts), 2)
        self.assertEqual({record['condition'] for record in attempts},
                         {'paper_data_shared_method', 'paper_data_shared_method_official_code'})
        self.assertTrue(all('not whole-paper reproduction or source-paper improvement' in record['scope']
                            for record in attempts))
        self.assertTrue(all(record['qualification_effect'] == 'none' for record in result['records']))
        with self.assertRaisesRegex(ValueError, 'calibration only'):
            cli.require_paper_role({'track': 'paper'}, False)

    def test_absent_task_evidence_is_not_an_unknown_task(self):
        result = self.command(['evidence', 'NEURAL-001'])
        self.assertEqual(result['task_id'], 'NEURAL-001')
        self.assertEqual(result['records'], [])
        self.assertIn('selected public reports only', result['scope'])
        with self.assertRaisesRegex(ValueError, 'registered task ID'):
            self.command(['evidence', 'NOT-REGISTERED'])
        with self.assertRaisesRegex(ValueError, 'registered task ID'):
            self.command(['evidence', '../NEURAL-077'])

    def test_selected_public_fields_do_not_expose_embedded_private_locators(self):
        result = self.command(['evidence'])
        serialized = json.dumps(result)
        self.assertNotIn('operator_evidence_pins', serialized)
        self.assertNotIn('/Users/', serialized)
        self.assertNotIn('/private-ledger-sentinel/', serialized)
        self.assertNotIn('raw_receipt_path', serialized)
        for records in result['records'].values():
            for record in records:
                relative = Path(record['source']['path'])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn('..', relative.parts)
                self.assertEqual(record['source']['bytes'], (ROOT / relative).stat().st_size)

    def test_operator_receives_exact_raw_arguments_and_root(self):
        operator = SimpleNamespace(main=Mock(return_value=9))
        companion = Mock(return_value=operator)
        builder = SimpleNamespace(companion_module=companion)
        arguments = ['operator', 'grade', 'NEURAL-077', '--submission', 'literal ; $(not-a-command).json',
                     '--output', 'directory with spaces', '--purpose', 'development-control', '--unknown-option']
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli, 'public_catalog_module', return_value=builder), \
                patch.object(cli.subprocess, 'run', side_effect=AssertionError('outer CLI executed a process')):
            result = cli.main(arguments, root=directory)
            self.assertEqual(result, 9)
            companion.assert_called_once_with('operator_routes')
            operator.main.assert_called_once_with(arguments[1:], root=Path(directory))
        self.assertEqual(arguments[0], 'operator')

    def test_operator_help_and_default_argv_reach_operator_parser(self):
        operator = SimpleNamespace(main=Mock(return_value=0))
        builder = SimpleNamespace(companion_module=Mock(return_value=operator))
        with patch.object(cli, 'public_catalog_module', return_value=builder), \
                patch.object(sys, 'argv', ['neurobench.py', 'operator', '--help']):
            self.assertEqual(cli.main(root=ROOT), 0)
        operator.main.assert_called_once_with(['--help'], root=ROOT)

    def test_documented_isolated_entrypoint_reports_and_refuses_unknown_id(self):
        command = [sys.executable, '-I', '-S', '-B', str(ROOT / 'scripts/neurobench.py'), 'evidence']
        good = subprocess.run(command + ['NEURAL-007'], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(good.returncode, 0, good.stderr)
        report = json.loads(good.stdout)
        self.assertEqual(report['task_id'], 'NEURAL-007')
        attempts = {record['attempt_id']: record for record in report['records']
                    if record['category'] == 'neural_programme_attempt'}
        self.assertIn('Exploratory:', attempts['neural007-1']['protocol_note'])
        self.assertIn('No sequencing deviation', attempts['neural007-2']['protocol_note'])
        refused = subprocess.run(command + ['NOT-REGISTERED'], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(refused.stdout, '')
        error = json.loads(refused.stderr)
        self.assertEqual(error['status'], 'refused')
        self.assertIn('registered task ID', error['reason'])


if __name__ == '__main__':
    unittest.main()
