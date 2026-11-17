"""Keep a verified legacy adapter separate from a revised neural target.

These use real current/history/registry pins and a compact scientific-validator
stub. No candidate, target, Docker process, model or scientific metric executes.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'neural_dispatch_bound_fixture', ROOT / 'tests/framework/test_neural_catalog_binding.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
cli = fixture.cli
TASK = 'NEURAL-096'


class NeuralDispatchBoundaryTests(unittest.TestCase):
    def setUp(self):
        # Reuse the pinned 234-row fixture without inheriting and rerunning its
        # independent catalog test suite.
        self.bound = fixture.NeuralCatalogBindingTests()
        self.addCleanup(self.bound.doCleanups)
        self.bound.setUp()
        self.root = self.bound.root
        package = self.root / 'benchmarks/neural' / TASK / 'implementations/legacy-counts'
        package.mkdir(parents=True)
        self.wrapper = package / 'score.py'
        self.wrapper.write_text('raise AssertionError("fixture must never execute")\n')
        relative = self.wrapper.relative_to(self.root).as_posix()
        entry = {'argv': ['python3', relative, '--submission', '{submission}', '--output', '{output}'],
                 'working_directory': '.', 'sha256': cli.digest(self.wrapper)}
        self.runtime_doc = {
            'id': TASK, 'status': 'historical_passed', 'admission': {'runnable': True},
            'verification': {'status': 'passed', 'receipt_path': '/never-open/private-targets.json'},
            'entrypoints': {'score': entry},
            'program_execution': {
                'verification': {'status': 'passed'},
                'entrypoint': {'argv': ['python3', relative, '--program', '{program}', '--output', '{output}'],
                               'working_directory': '.', 'sha256': cli.digest(self.wrapper)},
            },
        }
        self.manifest = package / 'manifest.json'
        registry = self.bound.registry()
        row = self.bound.row(registry, TASK)
        row.update(runtime_manifest=fixture.put(self.root, self.manifest.relative_to(self.root).as_posix(),
                                               self.runtime_doc),
                   runtime_package=package.relative_to(self.root).as_posix(),
                   runtime_manifest_status='historical_passed')
        for key in ('runtime_manifests', 'linked_runtime_manifests'):
            registry['source_counts'][key] += 1
        self.bound.save_registry(registry)
        self.submission = self.root / 'submission.json'
        self.submission.write_text('{}\n')
        self.program = self.root / 'candidate.py'
        self.program.write_text('raise AssertionError("candidate must never execute")\n')
        self.output = self.root / 'fresh-output'
        self.set_fidelity('different_target')

    def set_fidelity(self, value):
        registry = self.bound.registry()
        row = self.bound.row(registry, TASK)
        relative = row['specification_revision']['understanding_contract']['path']
        contract = json.loads((self.root / relative).read_bytes())
        contract['implementation'] = {'target_fidelity': value}
        replacement = fixture.put(self.root, relative, contract)
        row['specification_revision']['understanding_contract'] = replacement
        # A forged convenience summary must not override the pinned contract.
        row['neural_understanding'] = {'target_fidelity': 'full_target',
                                     'disposition': 'delivered_named_scope'}
        self.bound.edit_task(registry, lambda doc: doc['evaluation']['neural_understanding'].update(
            contract_sha256=replacement['sha256']), identifier=TASK)

    def invoke(self, action, *, calibration=False, missing=False):
        supplied = self.root / 'missing-input' if missing else (
            self.program if action == 'run' else self.submission)
        return getattr(cli, action + '_command')(
            TASK, supplied, self.output, root=self.root, calibration=calibration)

    def test_all_mismatched_or_unresolved_targets_refuse_before_runtime_and_inputs(self):
        for fidelity in ('different_target', 'no_target_evaluator', 'unresolved'):
            self.set_fidelity(fidelity)
            for action in ('score', 'run'):
                with self.subTest(fidelity=fidelity, action=action), \
                        patch.object(cli, 'runtime_manifests', side_effect=AssertionError('runtime read')) as runtime, \
                        patch.object(cli, 'verified_runtime', return_value=True) as score_verified, \
                        patch.object(cli, 'verified_program_runtime', return_value=True) as program_verified, \
                        patch.object(cli.subprocess, 'run', side_effect=AssertionError('candidate execution')), \
                        self.assertRaisesRegex(ValueError, '--calibration'):
                    self.invoke(action, missing=True)
                runtime.assert_not_called()
                score_verified.assert_not_called()
                program_verified.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_full_and_scoped_targets_keep_the_normal_scoring_and_programme_paths(self):
        for fidelity in ('full_target', 'scoped_target'):
            self.set_fidelity(fidelity)
            for action in ('score', 'run'):
                with self.subTest(fidelity=fidelity, action=action), \
                        patch.object(cli, 'verified_runtime', return_value=True), \
                        patch.object(cli, 'verified_program_runtime', return_value=True), \
                        patch.object(cli.subprocess, 'run', side_effect=AssertionError('candidate execution')):
                    argv, cwd = self.invoke(action)
                self.assertEqual(argv[1], str(self.wrapper))
                self.assertEqual(cwd, self.root)
        self.assertFalse(self.output.exists())

    def test_explicit_calibration_does_not_bypass_runtime_qualification(self):
        for action, verifier in (('score', 'verified_runtime'), ('run', 'verified_program_runtime')):
            with self.subTest(action=action), patch.object(cli, verifier, return_value=False) as check, \
                    self.assertRaisesRegex(ValueError, 'reference/negative checks|separate passing qualification'):
                self.invoke(action, calibration=True, missing=True)
            check.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_explicit_calibration_allows_only_the_normally_verified_legacy_command(self):
        for action in ('score', 'run'):
            with self.subTest(action=action), patch.object(cli, 'verified_runtime', return_value=True), \
                    patch.object(cli, 'verified_program_runtime', return_value=True), \
                    patch.object(cli.subprocess, 'run', side_effect=AssertionError('candidate execution')):
                argv, cwd = self.invoke(action, calibration=True)
            self.assertEqual(argv[1], str(self.wrapper))
            self.assertEqual(cwd, self.root)
        self.assertFalse(self.output.exists())

    def test_stale_contract_still_refuses_when_calibration_was_requested(self):
        registry = self.bound.registry()
        row = self.bound.row(registry, TASK)
        path = self.root / row['specification_revision']['understanding_contract']['path']
        path.write_bytes(path.read_bytes() + b' ')
        for action in ('score', 'run'):
            with self.subTest(action=action), \
                    patch.object(cli, 'runtime_manifests', side_effect=AssertionError('runtime read')), \
                    self.assertRaisesRegex(ValueError, 'pin mismatch'):
                self.invoke(action, calibration=True)

    def test_dry_run_cannot_hide_the_mismatch_and_calibration_is_labeled(self):
        for action, option, supplied in (('score', '--submission', self.submission),
                                         ('run', '--program', self.program)):
            args = [action, TASK, option, str(supplied), '--output', str(self.output), '--dry-run']
            with self.subTest(action=action), patch.object(cli.subprocess, 'run', side_effect=AssertionError('execution')):
                with self.assertRaisesRegex(ValueError, '--calibration'):
                    cli.main(args, root=self.root)
                captured = io.StringIO()
                with patch.object(cli, 'verified_runtime', return_value=True), \
                        patch.object(cli, 'verified_program_runtime', return_value=True), redirect_stdout(captured):
                    self.assertEqual(cli.main(args + ['--calibration'], root=self.root), 0)
                result = json.loads(captured.getvalue())
                self.assertEqual(result['evaluation_role'], 'calibration_only')
                self.assertFalse(result['current_task_success'])
                self.assertFalse(result['executed'])
        self.assertFalse(self.output.exists())

    def test_mismatch_is_still_inspectable_as_metadata(self):
        with patch.object(cli, 'runtime_manifests', side_effect=AssertionError('runtime read')), \
                patch.object(cli.subprocess, 'run', side_effect=AssertionError('execution')):
            contract = cli.neural_contract(TASK, self.root)
            captured = io.StringIO()
            with redirect_stdout(captured):
                self.assertEqual(cli.main(['neural-contract', TASK], root=self.root), 0)
        self.assertEqual(contract['implementation']['target_fidelity'], 'different_target')
        self.assertEqual(json.loads(captured.getvalue()), contract)

    def test_unbound_legacy_neural_fixture_keeps_existing_admission_behavior(self):
        row = {'id': TASK, 'track': 'neural'}
        for action in ('score', 'run'):
            with self.subTest(action=action), \
                    patch.object(cli, 'specifications', return_value=({}, {TASK: row})), \
                    patch.object(cli, 'neural_contract', side_effect=AssertionError('unbound contract read')), \
                    patch.object(cli, 'runtime_manifests', return_value={}), \
                    self.assertRaisesRegex(ValueError, 'No local scoring adapter|No local program runner'):
                self.invoke(action)


if __name__ == '__main__':
    unittest.main()
