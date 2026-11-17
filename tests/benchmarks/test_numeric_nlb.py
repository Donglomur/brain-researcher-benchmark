"""Standard-library current source-binding controls; never import NumPy/native code."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
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
        self.assertEqual(result['source_bodies'], 76)
        self.assertEqual(result['payload_bodies'], 74)
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


if __name__ == '__main__':
    unittest.main()
