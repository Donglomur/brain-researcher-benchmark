"""Ordinary source loading and authority refusals; no score matrix or native run."""
from pathlib import Path
import hashlib
import importlib.abc
import importlib.util
import json
import socket
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
GRADER = ROOT / 'paired_grading'
SOURCE_REPOSITORY = ROOT / 'source_repository'
FORBIDDEN = {'numpy', 'h5py', 'scipy', 'sklearn', 'torch', 'jax', 'jaxley'}
SOURCE_PIN = {'bytes': 1589, 'sha256': '2f7efbaa03fd83449038d83700efd7e187a4ce440073735ea90f7b3efd8c1dd9'}


class ForbidNumerical(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN:
            raise AssertionError('No numerical/native import: ' + fullname)


def forbidden(*args, **kwargs):
    raise AssertionError('No subprocess, socket or protected operation')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourcePortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.finder = ForbidNumerical()
        sys.meta_path.insert(0, cls.finder)
        cls.patches = [patch.object(subprocess, 'Popen', forbidden),
                       patch.object(socket, 'socket', forbidden),
                       patch.object(socket, 'create_connection', forbidden)]
        for item in cls.patches:
            item.start()
        cls.operator = load('neural075_public_operator', GRADER / 'operator.py')

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()
        sys.meta_path.remove(cls.finder)
        if FORBIDDEN.intersection(sys.modules):
            raise AssertionError('A numerical/native dependency was imported')

    def budget(self):
        # A source-test allowance only, never a grading authority or runtime profile.
        return self.operator._InspectBudget(512 * 1024, 64 * 1024, 10)

    def test_ordinary_inventory_and_exact_body_pins(self):
        inventory = json.loads((ROOT / 'PUBLIC_INVENTORY.json').read_bytes())
        expected = {row['path'] for row in inventory['files']} | {'PUBLIC_INVENTORY.json'}
        actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
        self.assertEqual(actual, expected)
        for row in inventory['files']:
            raw = (ROOT / row['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
        for path in [ROOT, *ROOT.rglob('*')]:
            self.assertFalse(path.is_symlink())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755 if path.is_dir() else 0o644)

    def test_actual_inspection_keeps_complete_scope_and_false_qualification(self):
        budget = self.budget()
        result = self.operator.inspect(SOURCE_PIN, budget)
        self.assertEqual(result['source_files'], 9)
        self.assertEqual(result['source_bytes'], 84481)
        self.assertEqual(result['declared_scope'], {'people': 5, 'arms': 3, 'phases': 2, 'accesses': 2, 'cases': 60})
        for key in ('runtime_qualified', 'scientific_qualified', 'execution_authorized',
                    'module_code_executed', 'authentic_inputs_read'):
            self.assertIs(result[key], False)
        self.assertEqual(result['external_dependencies']['files'], 18)
        self.assertEqual(budget.read_bytes, result['minimum_loader_read_bytes'])

    def test_bad_manifest_pin_refuses_before_module_execution(self):
        wrong = dict(SOURCE_PIN, sha256='0' * 64)
        with patch.object(self.operator, '_execute_module', forbidden):
            with self.assertRaisesRegex(ValueError, 'Stable exact captured source'):
                self.operator.inspect(wrong, self.budget())

    def test_actual_fixed_ordinary_dependency_chain_loads_without_data(self):
        budget = self.budget()
        root, _, bodies = self.operator._capture(SOURCE_PIN, budget)
        before = {name: sys.modules.get(name) for name in self.operator._ALIASES}
        present = {name for name in self.operator._ALIASES if name in sys.modules}
        with self.operator._modules(root, bodies, budget):
            closure = sys.modules['closed_pair']
            bindings = closure.load_fixed_bindings(str(SOURCE_REPOSITORY), budget)
            self.assertEqual(tuple(bindings.binding['cases']), closure.CASES)
            self.assertEqual(len(closure.CASES), 30)
            self.assertEqual(bindings.lock['design'], closure.DESIGN_PIN)
            provenance = closure.parse(bindings.provenance_raw)
            self.assertIs(provenance['design_body_read'], False)
            self.assertIs(provenance['native_imported'], False)
            self.assertEqual(len(provenance['captured_sources']), 13)
        for name in self.operator._ALIASES:
            self.assertEqual(name in sys.modules, name in present)
            if name in present:
                self.assertIs(sys.modules[name], before[name])

    def test_exact_scorer_declarations_authenticate_without_numerics(self):
        budget = self.budget()
        root, _, bodies = self.operator._capture(SOURCE_PIN, budget)
        with self.operator._modules(root, bodies, budget):
            scorer = sys.modules['pinned_scorer']
            source = {name: (SOURCE_REPOSITORY / scorer.EXPORT / name).read_bytes()
                      for name in scorer.PINS}
            # Selected function declarations only. No metric/admit/evaluate call.
            result = scorer.scorer_from_sources(source, object())
            self.assertTrue(callable(result.admit) and callable(result.evaluate))
            self.assertEqual(len(result.case_ids()), 30)
            self.assertEqual(result.ROWS, {'imagery': 500, 'perception': 1750})
            altered = dict(source)
            name = next(iter(altered))
            altered[name] = b'X' + altered[name][1:]
            with self.assertRaisesRegex(ValueError, 'Changed original scorer source'):
                scorer.scorer_from_sources(altered, object())

    def test_actual_grading_rejects_boolean_authority_before_protected_capture(self):
        class Denied:
            def require_neural075_paired_grading(self, selection):
                return True
        original = self.operator._execute_module
        captures = []
        def guarded(alias, body, filename):
            module = original(alias, body, filename)
            if alias == '_neural075_installed_paired_grade':
                def no_capture(*args, **kwargs):
                    captures.append(True)
                    raise AssertionError('No producer/design/target capture after denied authority')
                module.capture_closed_pair = no_capture
            return module
        with patch.object(self.operator, '_execute_module', guarded):
            with self.assertRaisesRegex(ValueError, 'Explicit trusted grading authority'):
                self.operator.grade_pair(SOURCE_PIN, SOURCE_REPOSITORY,
                    ROOT / 'absent_producer', {}, {}, ROOT / 'absent_prepared', {}, Denied(), self.budget())
        self.assertEqual(captures, [])
        self.assertFalse((ROOT / 'absent_producer').exists())
        self.assertFalse((ROOT / 'absent_prepared').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
