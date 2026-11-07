"""Condition routing tests. Synthetic metadata only; never run a candidate."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.tests.test_neurobench_programs import ProgramMetadataTests

spec = importlib.util.spec_from_file_location('condition_dispatch', Path(__file__).resolve().parents[1] / 'neurobench_condition.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ProgramMetadataTests(methodName='test_valid_command_is_literal_argv_and_executes_nothing')
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
        self.assertEqual(module.base.summary(self.fixture.root)['local_program_runners_verified'], 1)
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


if __name__ == '__main__':
    unittest.main()
