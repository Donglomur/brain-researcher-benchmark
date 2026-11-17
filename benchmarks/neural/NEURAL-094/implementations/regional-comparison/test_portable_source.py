"""Stdlib-only portability controls. All candidate documents are invented.

Run: python3 -I -B test_portable_source.py
Never imports the numerical/native/transport modules or starts a worker.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parent
COMPONENT = BASE / 'complete_regional'
SOURCES = COMPONENT / 'source'
MISSING = object()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PortableSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ('neural094_source_operator', 'regional_custody', 'regional_sources', 'regional_runtime')
        cls.previous = {name: sys.modules.get(name, MISSING) for name in names}
        cls.before_imports = set(sys.modules)
        cls.inspector = capture(names[0], COMPONENT / 'operator.py')
        cls.custody = capture(names[1], SOURCES / 'regional_custody.py')
        cls.loader = capture(names[2], SOURCES / 'regional_sources.py')
        cls.runtime = capture(names[3], SOURCES / 'regional_runtime.py')
        cls.temp = Path(tempfile.mkdtemp(prefix='neural094-source-only-')).resolve()
        cls.inventory_raw = (COMPONENT / 'RUNTIME_INVENTORY.json').read_bytes()
        cls.manifest_raw = (COMPONENT / 'SOURCE_MANIFEST.json').read_bytes()
        cls.manifest = json.loads(cls.manifest_raw)
        cls.mounted = cls.temp / 'mounted'
        cls.mounted.mkdir()
        # Invented engineering allowances only; not production resource defaults.
        cls.source_budget = cls.custody.Budget(524288, 524288, 30)
        cls.layout = cls.runtime.materialize(SOURCES, cls.inventory_raw, pin(cls.inventory_raw),
                                             cls.mounted, cls.source_budget)
        cls.readback = 0
        cls.extra_budget_reads = cls.extra_budget_writes = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)
        for name, prior in cls.previous.items():
            if prior is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior

    def test_01_complete_inspector(self):
        expected = sum(row['bytes'] + 1 for row in self.manifest['files'].values()) + len(self.manifest_raw) + 1
        budget = self.inspector.Budget(expected, 4096, 30)
        raw = self.inspector.inspect(COMPONENT, pin(self.manifest_raw), budget=budget)
        value = json.loads(raw)
        self.assertEqual(budget.read_bytes, expected)
        self.assertEqual(value['package_members'], 35)
        self.assertEqual(value['source_members'], 29)
        self.assertEqual(value['mounted_members_if_materialized'], 33)
        self.assertFalse(value['benchmark_modules_imported'])
        self.assertFalse(value['execution_authority'])
        self.assertFalse(value['scientific_qualification'])
        type(self).inspection_read, type(self).inspection_write = budget.read_bytes, budget.write_bytes

    def test_02_wrong_manifest_pin_refuses_early(self):
        budget = self.inspector.Budget(65536, 4096, 30)
        bad = {**pin(self.manifest_raw), 'sha256': '0' * 64}
        with self.assertRaises(self.inspector.Refusal):
            self.inspector.inspect(COMPONENT, bad, budget=budget)
        self.assertEqual(budget.read_bytes, len(self.manifest_raw) + 1)
        self.assertEqual(budget.write_bytes, 0)
        type(self).extra_budget_reads += budget.read_bytes

    def test_03_exact_full_materialized_layout(self):
        self.assertEqual(len(self.layout['files']), 33)
        self.assertEqual(len(set(self.layout['mounted_to_source'].values())), 29)
        actual = {str(p.relative_to(self.mounted)) for p in self.mounted.rglob('*') if p.is_file()}
        self.assertEqual(actual, set(self.layout['files']))
        for name, descriptor in self.layout['files'].items():
            body = (self.mounted / name).read_bytes()
            type(self).readback += len(body)
            self.assertEqual(pin(body), descriptor)
        for name in self.loader.TRANSPORT:
            self.assertEqual(self.layout['files'][name + '.py'],
                             self.layout['files']['host_transport/' + name + '.py'])

    def test_04_three_fixed_capsules(self):
        roots = {role: self.temp / ('capsule-' + role) for role in ('F', 'I', 'reference')}
        for root in roots.values():
            root.mkdir()
        program = b'# Invented source fixture, deliberately never executed.\n'
        budget = self.custody.Budget(65536, 65536, 30)
        output = self.runtime.materialize_capsules(self.layout, roots, program=program,
            training_recipe=b'{"invented":true}', instructions=b'{"invented":true}', budget=budget)
        expected = {'F': {'frozen_program_entry.py', 'program.py', 'TRAINING_RECIPE.json'},
                    'I': {'investigator_policy.py', 'INSTRUCTIONS.json'},
                    'reference': {'reference_entry.py'}}
        for role, record in output.items():
            self.assertEqual(set(record['files']), expected[role])
            for name, descriptor in record['files'].items():
                body = (roots[role] / name).read_bytes()
                type(self).readback += len(body)
                self.assertEqual(pin(body), descriptor)
        type(self).extra_budget_reads += budget.read_bytes
        type(self).extra_budget_writes += budget.write_bytes

    def test_05_inventory_authentication_precedes_writes(self):
        empty = self.temp / 'rejected'
        empty.mkdir()
        budget = self.custody.Budget(65536, 65536, 30)
        with self.assertRaises(ValueError):
            self.runtime.materialize(SOURCES, self.inventory_raw,
                {**pin(self.inventory_raw), 'sha256': '0' * 64}, empty, budget)
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual((budget.read_bytes, budget.write_bytes), (0, 0))

    def test_06_transport_copy_mismatch_refused(self):
        altered = dict(self.layout['files'])
        altered['morse_protocol.py'] = {**altered['morse_protocol.py'], 'sha256': '0' * 64}
        with self.assertRaises(ValueError):
            self.runtime.validate_mounted(altered, altered['host_transport/SOURCE_MANIFEST.json'])

    def test_07_loader_restores_namespace_on_failure(self):
        # Only tiny invented fixed-name modules enter this actual loader control.
        folder = self.temp / 'invented-load-group'
        folder.mkdir()
        names = self.loader.NUMERICAL
        before = {name: sys.modules.get(name, MISSING) for name in names}
        manifest = {}
        for index, name in enumerate(names):
            body = b'raise ValueError("invented last-module refusal")\n' if index == len(names) - 1 else b'invented = True\n'
            (folder / (name + '.py')).write_bytes(body)
            manifest[name] = {'path': name + '.py', **pin(body)}
        raw = json.dumps(manifest, sort_keys=True).encode()
        (folder / 'SOURCE_MANIFEST.json').write_bytes(raw)
        budget = self.custody.Budget(16384, 16384, 30)
        with self.assertRaisesRegex(ValueError, 'invented last-module refusal'):
            self.loader.load_group(folder, pin(raw), budget, names)
        for name, prior in before.items():
            self.assertIs(sys.modules.get(name, MISSING), prior)
        type(self).extra_budget_reads += budget.read_bytes
        type(self).extra_budget_writes += len(raw) + sum(p.stat().st_size for p in folder.glob('*.py'))

    def test_08_no_numerical_native_or_provider_import(self):
        added = set(sys.modules) - self.before_imports
        forbidden = ('numpy', 'scipy', 'sklearn', 'regional_native', 'regional_controller', 'morse_broker', 'morse_docker')
        self.assertFalse(any(name == item or name.startswith(item + '.') for name in added for item in forbidden))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PortableSource))
    if result.wasSuccessful():
        # Operational source-byte accounting; fixed parser/control overhead is
        # reserved separately by the construction owner, not a production grant.
        print(json.dumps({'source_read': PortableSource.source_budget.read_bytes,
                          'source_write': PortableSource.source_budget.write_bytes,
                          'inspection_read': PortableSource.inspection_read,
                          'inspection_write': PortableSource.inspection_write,
                          'extra_budget_reads': PortableSource.extra_budget_reads,
                          'extra_budget_writes': PortableSource.extra_budget_writes,
                          'readback': PortableSource.readback,
                          'scientific_execution': False}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
