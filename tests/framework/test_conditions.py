"""Condition routing tests. Synthetic metadata only; never run a candidate."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
fixture_spec = importlib.util.spec_from_file_location(
    'program_admission_fixture', Path(__file__).with_name('test_program_admission.py'))
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)

spec = importlib.util.spec_from_file_location('condition_dispatch', Path(__file__).resolve().parents[2] / 'src/neurobench/conditions.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ProgramMetadataTests(methodName='test_valid_command_is_literal_argv_and_executes_nothing')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.alternate = f.wrapper.with_name('alternate.py')
        self.alternate.write_text('raise AssertionError("must never run")\n')
        variant = copy.deepcopy(f.meta)
        variant['entrypoint']['argv'][1] = f.rel(self.alternate)
        variant['entrypoint']['sha256'] = f.sha(self.alternate)
        freeze = f.wrapper.with_name('ALTERNATE_FREEZE.json')
        f.write(freeze, {'files': {f.rel(self.alternate): f.pin(self.alternate)}})
        variant['source_freeze'] = {'path': f.rel(freeze), 'sha256': f.sha(freeze)}
        for kind, old in [('receipt', f.receipt), ('source_binding', f.binding)]:
            value = json.loads(old.read_text()); value['source_freeze_sha256'] = f.sha(freeze)
            new = old.with_name('alternate_' + old.name); f.write(new, value)
            variant['verification'][kind + '_path'] = f.rel(new)
            variant['verification'][kind + '_sha256'] = f.sha(new)
        f.doc['program_conditions'] = {'features': 'default', 'raw': variant}; f.save()

    def run_condition(self, name, **kw):
        f = self.fixture
        return module.run_command('NEURAL-095', name, f.program, f.output, f.root, **kw)

    def test_information_condition_routes_exactly_without_execution(self):
        with patch.object(module.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            features, _ = self.run_condition('features'); raw, _ = self.run_condition('raw')
        self.assertEqual(features, self.fixture.command()[0])
        self.assertEqual(raw[1], str(self.alternate))
        self.assertIn(str(self.fixture.program), raw)
        self.assertFalse(self.fixture.output.exists())
        path, declaration = module.base.runtime_manifests(self.fixture.root)['NEURAL-095']
        self.assertTrue(module.base.verified_program_runtime(path, declaration, self.fixture.root))
        self.assertTrue(all(not row['additional_task'] for row in module.list_conditions(self.fixture.root)))

    def test_changed_alternative_rejects_and_does_not_fall_back(self):
        self.alternate.write_text('# unqualified new bytes\n')
        with self.assertRaisesRegex(ValueError, 'Missing or changed'):
            self.run_condition('raw')
        self.assertEqual(self.run_condition('features')[0][1], str(self.fixture.wrapper))

    def test_unknown_and_unqualified_reject_without_execution(self):
        for name in ('', '../raw', 'missing'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unknown program condition'):
                self.run_condition(name)
        self.fixture.doc['program_conditions']['raw']['verification']['status'] = 'pending'; self.fixture.save()
        with self.assertRaisesRegex(ValueError, 'no separate passing qualification'):
            self.run_condition('raw')

    def test_reviewed_condition_preserves_existing_execution_review_boundary(self):
        f = self.fixture; review = f.reviewed_entry()
        with self.assertRaisesRegex(ValueError, 'requires --review'):
            self.run_condition('features')
        command, _ = self.run_condition('features', review=review, other_reserve_bytes=102000000)
        self.assertEqual(command, module.base.run_command(
            'NEURAL-095', f.program, f.output, f.root, review=review, other_reserve_bytes=102000000)[0])

    def test_current_neural_target_refuses_before_runtime_and_candidate_reads(self):
        f = self.fixture
        f.registry['tasks'][0]['specification_revision'] = {'version': 'neural-understanding/v1'}
        f.save()
        for fidelity in ('different_target', 'no_target_evaluator', 'unresolved'):
            for condition in ('features', 'raw'):
                contract = {'implementation': {'target_fidelity': fidelity}}
                with self.subTest(fidelity=fidelity, condition=condition):
                    with patch.object(module.base, 'neural_contract', return_value=contract) as current, \
                            patch.object(module.base, 'runtime_manifests', side_effect=AssertionError('runtime read before target guard')) as runtime, \
                            patch.object(module.subprocess, 'run', side_effect=AssertionError('candidate execution')) as execute, \
                            self.assertRaisesRegex(ValueError, '--calibration'):
                        module.run_command('NEURAL-095', condition, f.root / 'missing-program.py', f.output, f.root)
                    current.assert_called_once_with('NEURAL-095', f.root)
                    runtime.assert_not_called()
                    execute.assert_not_called()
        self.assertFalse(f.output.exists())

    def test_accepted_current_neural_targets_preserve_condition_routing(self):
        f = self.fixture
        f.registry['tasks'][0]['specification_revision'] = {'version': 'neural-understanding/v1'}
        f.save()
        for fidelity in ('full_target', 'scoped_target'):
            contract = {'implementation': {'target_fidelity': fidelity}}
            with self.subTest(fidelity=fidelity), \
                    patch.object(module.base, 'neural_contract', return_value=contract) as current, \
                    patch.object(module.subprocess, 'run', side_effect=AssertionError('candidate execution')) as execute:
                for condition, wrapper in (('features', f.wrapper), ('raw', self.alternate)):
                    command, cwd = self.run_condition(condition)
                    self.assertEqual(command, [module.sys.executable, str(wrapper), '--program',
                                               str(f.program), '--out', str(f.output)])
                    self.assertEqual(cwd, f.root)
                self.assertEqual(current.call_count, 2)
                current.assert_called_with('NEURAL-095', f.root)
                execute.assert_not_called()
        self.assertFalse(f.output.exists())


if __name__ == '__main__':
    unittest.main()
