"""Independent authentication refusals; never load valid benchmark modules."""
import builtins
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


_RUNNER_PATH = Path(__file__).resolve().with_name('run_generated_controls.py')
_SPEC = importlib.util.spec_from_file_location('dosei_public_bootstrap_under_test', _RUNNER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError('local bootstrap entry required')
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


class PublicBootstrapAuthentication(unittest.TestCase):
    def test_all_source_mutations_refuse_before_execution_or_module_injection(self):
        originals = runner.read_sources()
        self.assertEqual(len(runner.PINS), 4)
        self.assertEqual(set(originals), set(runner.PINS))
        self.assertEqual(runner.MODULE_NAMES, (
            'input_adapter_reviewed', 'frozen_input_reader_source',
            'input_test_bundle', 'input_independent_bundle'))
        mutations_checked = 0
        before = dict(sys.modules)
        assignment_attempts = []

        class GuardedModules(dict):
            def __setitem__(self, name, value):
                if name in runner.MODULE_NAMES:
                    assignment_attempts.append(name)
                    raise AssertionError('benchmark module injection forbidden')
                super().__setitem__(name, value)

        guarded = GuardedModules(before)
        with patch.object(runner, '_exec_module', side_effect=AssertionError('source execution forbidden')) as execute, \
             patch.object(builtins, 'compile', side_effect=AssertionError('source compilation forbidden')) as compile_source, \
             patch.object(runner, 'sys', types.SimpleNamespace(modules=guarded)):
            # Acceptance authenticates bytes only; valid load_modules is never called.
            runner.authenticate_sources(originals)
            self.assertFalse(assignment_attempts)
            self.assertEqual(set(sys.modules), set(before))
            self.assertTrue(all(sys.modules[name] is value for name, value in before.items()))
            execute.assert_not_called()
            compile_source.assert_not_called()
            for relative, original in originals.items():
                self.assertIs(type(original), bytes)
                self.assertGreater(len(original), 0)
                alternatives = (
                    ('same_length_tamper', bytes((original[0] ^ 1,)) + original[1:]),
                    ('truncate', original[:-1]),
                    ('extend', original + b'\0'),
                )
                for kind, changed in alternatives:
                    with self.subTest(source=relative, mutation=kind):
                        supplied = dict(originals)
                        supplied[relative] = changed
                        snapshot = dict(sys.modules)
                        with self.assertRaises(ValueError):
                            runner.load_modules(supplied)
                        execute.assert_not_called()
                        compile_source.assert_not_called()
                        self.assertFalse(assignment_attempts)
                        self.assertEqual(set(sys.modules), set(snapshot))
                        self.assertTrue(all(sys.modules[name] is value for name, value in snapshot.items()))
                        for name in runner.MODULE_NAMES:
                            if name in snapshot:
                                self.assertIs(sys.modules[name], snapshot[name])
                            else:
                                self.assertNotIn(name, sys.modules)
                        mutations_checked += 1
        self.assertEqual(mutations_checked, 12)


def main():
    suite = unittest.TestSuite([PublicBootstrapAuthentication(
        'test_all_source_mutations_refuse_before_execution_or_module_injection')])
    return runner.run_suite(suite, expected_count=1, scope='bootstrap_authentication', mutation_cases=12)


if __name__ == '__main__':
    raise SystemExit(main())
