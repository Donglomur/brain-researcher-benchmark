"""Standard-library current source-binding controls; never import NumPy/native code."""
import argparse
import hashlib
import importlib.util
import subprocess
import sys
import json
from pathlib import Path
import shutil
import tempfile
import unittest


_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--composition-fixture', type=Path)
_options, _remaining = _parser.parse_known_args()
sys.argv = [sys.argv[0], *_remaining]
ROOT = (_options.composition_fixture.resolve() if _options.composition_fixture is not None
        else Path(__file__).resolve().parents[2])
PACKAGE = Path('benchmarks/neural/NEURAL-017/implementations/registered-runtime/complete-operator')
BINDING = Path('benchmarks/integrity/current-closures/numeric-nlb/SOURCE_PINS.json')
SPEC = importlib.util.spec_from_file_location('_numeric_nlb_inspector', ROOT / PACKAGE / 'source_inspection.py')
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)


class NlbCurrentSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'repo'
        self.package = self.root / PACKAGE
        shutil.copytree(ROOT / PACKAGE, self.package)
        shutil.copyfile(ROOT / PACKAGE.parent / 'SOURCE_COMPONENTS.json',
                        self.package.parent / 'SOURCE_COMPONENTS.json')
        self.binding = self.root / BINDING
        self.binding.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / BINDING, self.binding)

    def update_binding(self, change):
        value = json.loads(self.binding.read_text())
        change(value)
        self.binding.write_text(json.dumps(value))

    def test_current_source_inspection_preserves_native_and_scientific_holds(self):
        result = INSPECTOR.inspect_source(self.package)
        self.assertEqual(result['status'], 'source_consistency_passed')
        self.assertEqual(result['source_bodies'], 77)
        self.assertEqual(result['payload_bodies'], 75)
        self.assertEqual(result['current_binding']['path'], BINDING.as_posix())
        self.assertTrue(result['historical_native_entry_held'])
        for key in ('self_authentication_claim', 'local_module_execution',
                    'native_qualified', 'scientific_qualified', 'data_or_model_execution'):
            self.assertFalse(result[key])

    def test_current_member_mutation_refuses(self):
        path = self.package / 'nlb/metric_core.py'
        path.write_bytes(path.read_bytes() + b'\n# changed generated copy\n')
        with self.assertRaisesRegex(ValueError, 'payload identity mismatch: nlb/metric_core.py'):
            INSPECTOR.inspect_source(self.package)

    def test_unlisted_member_refuses(self):
        (self.package / 'unlisted.py').write_text('# never executed\n')
        with self.assertRaisesRegex(ValueError, 'unlisted source member'):
            INSPECTOR.inspect_source(self.package)

    def test_overlay_cannot_expand_repair_scope(self):
        self.update_binding(lambda x: x['members'].update({'unlisted.py': {'bytes': 1, 'sha256': '0' * 64}}))
        with self.assertRaisesRegex(ValueError, 'exact current numerical source selection'):
            INSPECTOR.inspect_source(self.package)

    def test_overlay_cannot_rebind_unchanged_dependency(self):
        self.update_binding(lambda x: x['members']['nlb/contracts.py'].update(sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'unchanged numerical dependency identity'):
            INSPECTOR.inspect_source(self.package)

    def test_overlay_cannot_claim_execution_permission(self):
        self.update_binding(lambda x: x.update(execution_selected=True))
        with self.assertRaisesRegex(ValueError, 'current source-only qualification boundary'):
            INSPECTOR.inspect_source(self.package)

    def test_original_manifest_identity_stays_required(self):
        path = self.package / 'SOURCE_MANIFEST.json'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'entry and manifest identity mismatch'):
            INSPECTOR.inspect_source(self.package)


class NlbCompositionSourceTests(unittest.TestCase):
    """Changed composition guards; an explicit fixture is exclusively owned by this run."""
    @classmethod
    def setUpClass(cls):
        if _options.composition_fixture is not None:
            cls.root = ROOT
        else:
            temporary = tempfile.TemporaryDirectory(prefix='nlb-composition-')
            cls.addClassCleanup(temporary.cleanup)
            cls.root = Path(temporary.name).resolve() / 'repo'
            package = cls.root / PACKAGE
            shutil.copytree(ROOT / PACKAGE, package)
            shutil.copyfile(ROOT / PACKAGE.parent / 'SOURCE_COMPONENTS.json',
                            package.parent / 'SOURCE_COMPONENTS.json')
            binding = cls.root / BINDING
            binding.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / BINDING, binding)
        cls.package = cls.root / PACKAGE

    def test_expanded_census_preserves_holds(self):
        result = INSPECTOR.inspect_source(self.package)
        self.assertEqual((result['payload_bodies'], result['source_bodies'], result['python_bodies']),
                         (75, 77, 57))
        self.assertTrue(result['historical_native_entry_held'])
        for name in ('native_qualified', 'scientific_qualified', 'data_or_model_execution',
                     'local_module_execution', 'self_authentication_claim'):
            self.assertFalse(result[name])

    def test_added_helper_mutation_refuses(self):
        path = self.package / 'nlb/opaque_s03.py'
        before = path.read_bytes()
        try:
            path.write_bytes(before + b'\n')
            with self.assertRaisesRegex(ValueError, 'payload identity mismatch: nlb/opaque_s03.py'):
                INSPECTOR.inspect_source(self.package)
        finally:
            path.write_bytes(before)

    def test_added_helper_absence_refuses(self):
        path = self.package / 'nlb/opaque_s03.py'
        held = self.root / 'held-opaque-s03.py'
        self.assertFalse(held.exists())
        path.rename(held)
        try:
            with self.assertRaises(FileNotFoundError):
                INSPECTOR.inspect_source(self.package)
        finally:
            held.rename(path)

    def test_declared_census_cannot_omit_helper(self):
        manifest_path, entry_path = self.package / 'SOURCE_MANIFEST.json', self.package / 'nlb_entry.py'
        before, entry = manifest_path.read_bytes(), entry_path.read_bytes()
        changed = json.loads(before)
        changed['files'] = [row for row in changed['files'] if row['path'] != 'nlb/opaque_s03.py']
        raw = (json.dumps(changed, indent=2) + '\n').encode()
        old_sha, new_sha = hashlib.sha256(before).hexdigest(), hashlib.sha256(raw).hexdigest()
        replacement = entry.replace(('MANIFEST_BYTES = ' + str(len(before))).encode(),
                                    ('MANIFEST_BYTES = ' + str(len(raw))).encode()).replace(old_sha.encode(), new_sha.encode())
        self.assertNotEqual(entry, replacement)
        try:
            manifest_path.write_bytes(raw)
            entry_path.write_bytes(replacement)
            with self.assertRaisesRegex(ValueError, 'complete current 74-payload manifest required'):
                INSPECTOR.inspect_source(self.package)
        finally:
            manifest_path.write_bytes(before)
            entry_path.write_bytes(entry)

    def test_standalone_entry_remains_held(self):
        with tempfile.TemporaryDirectory(prefix='nlb-held-entry-', dir=self.root) as owned:
            prefix = Path(owned) / 'fresh-prefix'
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X',
                                     'pycache_prefix=' + str(prefix), str(self.package / 'nlb_entry.py'),
                                     'prepare', '--help'], capture_output=True, timeout=10, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(result.stdout)
            self.assertLess(len(result.stderr), 8192)
            self.assertIn(b'exact regular single-link source', result.stderr)
            self.assertTrue(prefix.is_dir())
            self.assertEqual(list(prefix.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
