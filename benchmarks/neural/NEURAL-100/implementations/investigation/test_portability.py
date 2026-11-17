"""Ordinary-source inspection and missing-export refusal; no scientific execution."""
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
PACKAGE = ROOT / 'investigation/package'
MIRROR = ROOT / 'source_repository'
SOURCE_PIN = {
    'bytes': 2374,
    'sha256': '5ef0b78934bfc72977b032b3a1cdd43d197f59c90a772411f02f69517b5da9eb',
}
EXPORT_SHA = '69b11de087b77dd3214ceb1d240182cc26908fb1eff16b5ca4eca7bcaea8efb8'
GUARD_PIN = {
    'bytes': 12383,
    'sha256': 'b2468187d47405e94aed1223fb99261e71846d14ccd8bec2c1d1e9dd8f284562',
}
FORBIDDEN_IMPORTS = {
    'numpy', 'h5py', 'scipy', 'sklearn', 'torch', 'jax', 'jaxley', 'cebra',
    'MARBLE', 'pandas',
}


class SourceOnlyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN_IMPORTS:
            raise AssertionError('No numerical or native import: ' + fullname)


def forbidden(*args, **kwargs):
    raise AssertionError('No subprocess or network operation in source checks')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


class SourcePortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if FORBIDDEN_IMPORTS.intersection(sys.modules):
            raise AssertionError('Run the isolated source-only command in a fresh interpreter')
        cls.finder = SourceOnlyImports()
        sys.meta_path.insert(0, cls.finder)
        cls.addClassCleanup(sys.meta_path.remove, cls.finder)
        for target, attribute in (
                (subprocess, 'Popen'), (socket, 'socket'),
                (socket, 'create_connection')):
            blocking = patch.object(target, attribute, forbidden)
            blocking.start()
            cls.addClassCleanup(blocking.stop)

        inventory_path = ROOT / 'PUBLIC_INVENTORY.json'
        if (ROOT.is_symlink() or inventory_path.is_symlink() or
                not inventory_path.is_file() or
                not 0 < inventory_path.stat().st_size <= 65536):
            raise AssertionError('Bounded ordinary inventory')
        inventory = json.loads(inventory_path.read_bytes())
        cls.rows = inventory['files']
        if not isinstance(cls.rows, list) or not 1 <= len(cls.rows) <= 128:
            raise AssertionError('Finite public source inventory required')
        cls.bodies = {}
        for row in cls.rows:
            relative = Path(row['path'])
            if (relative.is_absolute() or '..' in relative.parts or
                    row['path'] == 'PUBLIC_INVENTORY.json' or
                    row['path'] in cls.bodies):
                raise AssertionError('Unique ordinary relative inventory paths')
            path = ROOT / relative
            if (any(parent.is_symlink() for parent in (path, *path.parents)) or
                    not path.is_file() or type(row['bytes']) is not int or
                    not 0 < row['bytes'] <= 1048576 or
                    path.stat().st_size != row['bytes']):
                raise AssertionError('Ordinary selected source file')
            body = path.read_bytes()
            if not 0 < len(body) <= 1048576 or identity(body) != {
                    'bytes': row['bytes'], 'sha256': row['sha256']}:
                raise AssertionError('Complete selected source identity')
            cls.bodies[row['path']] = body
        if sum(map(len, cls.bodies.values())) > 1048576:
            raise AssertionError('One MiB source-only inventory bound')
        cls.api = load_module('neural100_portable_inspection', PACKAGE / 'api.py')
        cls.support = load_module('neural100_portable_support', MIRROR / 'private/grade_support.py')

    @classmethod
    def tearDownClass(cls):
        if FORBIDDEN_IMPORTS.intersection(sys.modules):
            raise AssertionError('No numerical or native module was imported')

    def test_complete_ordinary_checkout_inventory(self):
        expected = set(self.bodies) | {'PUBLIC_INVENTORY.json'}
        actual = set()
        for path in [ROOT, *ROOT.rglob('*')]:
            self.assertFalse(path.is_symlink())
            if path.is_dir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
            else:
                self.assertTrue(path.is_file())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                actual.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(actual, expected)

    def test_actual_inspection_preserves_full_scope_and_gates(self):
        observed = self.api.inspect(dict(SOURCE_PIN))
        self.assertEqual(observed, {
            'schema': 'neural100_investigation_source_inspection_v1',
            'task_id': 'NEURAL-100', 'source': SOURCE_PIN,
            'source_members': 17, 'status': 'inactive_source_only',
            'recordings': 47, 'participants': 41,
            'area_recordings': {'A1': 39, 'A2': 8}, 'conditions': 8,
            'candidate_artifacts': ['report.json', 'claims.json'],
            'reference_calls_per_future_grade': 1,
            'scientific_qualified': False, 'runtime_qualified': False,
            'central_run_or_score_admission_changed': False,
            'authentic_inputs_opened': False,
        })

    def test_actual_loader_rejects_wrong_source_identity(self):
        wrong = {'bytes': SOURCE_PIN['bytes'], 'sha256': '0' * 64}
        with self.assertRaisesRegex(ValueError, '^Selected source identity$'):
            self.api.inspect(wrong)

    def test_exact_operator_code_copies_preserve_source_bindings(self):
        for name in ('artifact_io', 'report_contract', 'grade', 'analysis_core', 'guard'):
            source = 'investigation/package/upstream/' + name + '.py'
            mirrored = ('source_repository/private/support_consistency/guard.py'
                        if name == 'guard' else 'source_repository/private/' + name + '.py')
            with self.subTest(module=name):
                self.assertEqual(self.bodies[source], self.bodies[mirrored])
        self.assertEqual(identity(self.bodies[
            'source_repository/private/support_consistency/guard.py']), GUARD_PIN)

    def test_actual_bootstrap_refuses_missing_complete_export(self):
        # The mirror intentionally has code, not a fabricated authenticated export.
        missing = MIRROR / 'DELIVERY_MANIFEST.json'
        self.assertFalse(missing.exists())
        attempts = []
        original_capture = self.support.capture
        allowed = [MIRROR / 'private/support_consistency/guard.py', missing]

        def observed_capture(path, cap):
            path = Path(path)
            if len(attempts) >= len(allowed) or path != allowed[len(attempts)]:
                raise AssertionError('No roster, binding, header or neural-input access')
            attempts.append(path)
            return original_capture(path, cap)

        with patch.object(self.support, 'capture', observed_capture):
            with self.assertRaises(FileNotFoundError) as refused:
                self.support.start(MIRROR, EXPORT_SHA)
        self.assertEqual(Path(refused.exception.filename), missing)
        self.assertEqual(attempts, allowed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
