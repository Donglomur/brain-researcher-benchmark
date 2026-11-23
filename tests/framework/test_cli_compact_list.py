"""Generated metadata controls for compact discovery; no data or model access."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('compact_list_cli', ROOT / 'src/neurobench/cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
catalog = cli.public_catalog_module()


def task(identifier, track):
    return {
        'id': identifier, 'title': 'Recorded Δ signal: ' + identifier, 'track': track,
        'source_specification': True, 'registration_stage': 'registered_construction_draft',
        'specification': {'path': 'declared/task.json', 'sha256': '0' * 64, 'bytes': 12},
        'runtime_manifest': None, 'implementation_ids': ['one-source-component'],
        'related_implementation_ids': [], 'scientific_readiness': 'unknown',
        'submission_readiness': 'unknown', 'local_scoring_adapter_verified': None,
        'local_program_runner_verified': None,
        'paper_improvement': ({'disposition': 'design_ready',
                               'contract': {'long_details': 'original scope ' * 1000}}
                              if track == 'paper' else None),
        'paper_outcomes': ({'availability': 'available',
                            'reproduction_eligibility': 'source_unresolved'}
                           if track == 'paper' else None),
        'neural_understanding': ({'disposition': 'delivered_named_scope',
                                  'contract': {'long_details': 'observations ' * 1000}}
                                 if track == 'neural' else None),
        'recorded_evidence': [{'qualification_effect': 'none'}],
    }


class CompactListTests(unittest.TestCase):
    def command(self, arguments, rows):
        builder = SimpleNamespace(load=Mock(return_value={'tasks': rows}),
                                  primary_paper_disposition=catalog.primary_paper_disposition)
        output = io.StringIO()
        before = copy.deepcopy(rows)
        with patch.object(cli, 'public_metadata_mode', return_value=True), \
                patch.object(cli, 'public_catalog_module', return_value=builder), \
                patch.object(cli, 'run_command', side_effect=AssertionError('No programme dispatch')), \
                patch.object(cli, 'score_command', side_effect=AssertionError('No scoring dispatch')), \
                patch.object(cli.subprocess, 'run', side_effect=AssertionError('No process execution')), \
                redirect_stdout(output):
            self.assertEqual(cli.main(arguments, root=ROOT), 0)
        builder.load.assert_called_once_with(ROOT)
        self.assertEqual(rows, before)
        return json.loads(output.getvalue()), output.getvalue()

    def test_compact_is_explicit_and_default_preserves_full_metadata(self):
        rows = [task('PAPER-fixture', 'paper'), task('NEURAL-fixture', 'neural')]
        full, full_text = self.command(['list'], rows)
        self.assertEqual(full, rows)
        compact, compact_text = self.command(['list', '--compact'], rows)
        self.assertEqual([r['id'] for r in compact], [r['id'] for r in full])
        self.assertLess(len(compact_text), len(full_text) // 10)
        for row in compact:
            self.assertEqual(set(row), {'id', 'title', 'track', 'registration_stage',
                                        'scope_disposition', 'scientific_readiness',
                                        'submission_readiness'})
            self.assertNotIn('contract', json.dumps(row))
            self.assertEqual(row['scientific_readiness'], 'unknown')
            self.assertEqual(row['submission_readiness'], 'unknown')
        self.assertIn('Δ', compact_text)

    def test_track_filters_keep_catalog_order_and_full_mode_behavior(self):
        rows = [task('NEURAL-z', 'neural'), task('PAPER-a', 'paper'), task('NEURAL-a', 'neural')]
        neural, _ = self.command(['list', '--track', 'neural', '--compact'], rows)
        self.assertEqual([row['id'] for row in neural], ['NEURAL-z', 'NEURAL-a'])
        paper, _ = self.command(['list', '--compact', '--track', 'paper'], rows)
        self.assertEqual([row['id'] for row in paper], ['PAPER-a'])
        full, _ = self.command(['list', '--track', 'paper'], rows)
        self.assertEqual(full, [rows[1]])

    def test_paper_primary_scope_overrides_retained_improvement_policy(self):
        unavailable = task('PAPER-unavailable', 'paper')
        unavailable['paper_outcomes'] = {'availability': 'unavailable'}
        selected = task('PAPER-selected', 'paper')
        selected['paper_improvement']['disposition'] = 'improvement_ready'
        selected['paper_outcomes'].update(primary_policy_revision={'version': 'fixture'},
                                           improvement_disposition='source_unresolved')
        rows, _ = self.command(['list', '--compact'], [unavailable, selected])
        self.assertEqual(rows[0]['scope_disposition'],
                         {'reproduction': 'unavailable', 'improvement': 'unavailable'})
        self.assertEqual(rows[1]['scope_disposition'],
                         {'reproduction': 'source_unresolved', 'improvement': 'source_unresolved'})
        self.assertEqual(rows[1]['scientific_readiness'], 'unknown')

    def test_neural_delivery_is_reported_without_promoting_readiness(self):
        rows, _ = self.command(['list', '--compact'], [task('NEURAL-delivered', 'neural')])
        self.assertEqual(rows[0]['scope_disposition'], {'source_delivery': 'delivered_named_scope'})
        self.assertEqual(rows[0]['scientific_readiness'], 'unknown')
        self.assertEqual(rows[0]['submission_readiness'], 'unknown')

    def test_absent_neural_contract_is_not_revised_and_empty_selection_is_empty(self):
        row = task('NEURAL-missing', 'neural')
        row['neural_understanding'] = None
        rows, _ = self.command(['list', '--compact'], [row])
        self.assertEqual(rows[0]['scope_disposition'], {'source_delivery': 'not_revised'})
        empty, _ = self.command(['list', '--track', 'paper', '--compact'], [row])
        self.assertEqual(empty, [])

    def test_help_describes_compact_without_loading_catalog(self):
        output = io.StringIO()
        with patch.object(cli, 'public_catalog_module', side_effect=AssertionError('No catalog load')), \
                redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            cli.main(['list', '--help'], root=ROOT)
        self.assertEqual(raised.exception.code, 0)
        self.assertIn('--compact', output.getvalue())
        self.assertIn('readiness remains separate', output.getvalue())

    def test_invalid_track_and_non_list_compact_refuse_before_catalog_load(self):
        for arguments in (['list', '--compact', '--track', 'unknown'],
                          ['show', 'PAPER-fixture', '--compact']):
            with self.subTest(arguments=arguments), \
                    patch.object(cli, 'public_catalog_module', side_effect=AssertionError('No catalog load')), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                cli.main(arguments, root=ROOT)
            self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
