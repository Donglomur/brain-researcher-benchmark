"""Source metadata checks only. Never run an experiment or open protected inputs.

Run with: python -B tests/test_source_projection.py
Uses only the standard library, selected package source and tiny temporary copies.
"""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'full-cogitate-meg-v1'

def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

class SourceProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only these three metadata modules are imported. No scientific module,
        # native launcher, entrypoint or protected roster source is imported.
        cls.adapter = module('_public_n097_adapter', ROOT / 'adapter.py')
        package = types.ModuleType('_public_n097_metadata')
        package.__path__ = [str(RUNTIME / 'n097')]
        sys.modules[package.__name__] = package
        cls.io = module(package.__name__ + '.io', RUNTIME / 'n097/io.py')
        cls.contract = module(package.__name__ + '.contract', RUNTIME / 'n097/contract.py')

    def test_complete_adapter_source_guard(self):
        self.assertEqual(self.adapter.verify_runtime(ROOT), RUNTIME / 'entry.py')
        lock = json.loads((ROOT / 'RUNTIME_LOCK.json').read_bytes())
        self.assertEqual(len(lock['files']), 41)
        self.assertFalse(lock['deployment_enabled'])
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            shutil.copyfile(ROOT / 'RUNTIME_LOCK.json', dest / 'RUNTIME_LOCK.json')
            for name in lock['files']:
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            target = dest / 'full-cogitate-meg-v1/contracts/PINS.json'
            target.write_bytes(target.read_bytes() + b' ')
            with self.assertRaises(self.adapter.PackagingRefusal):
                self.adapter.verify_runtime(dest)

    def test_contract_pins_and_closed_metadata(self):
        contracts, binding = self.contract.load()
        self.assertEqual(len(contracts), 10)  # Eleven contracts include DESIGN.md.
        self.assertEqual(contracts['SCIENTIFIC_CONTRACT.json']['outer_split']['folds'], 66)
        self.assertEqual(len(contracts['GATES.json']['gates']), 22)
        pins = json.loads((RUNTIME / 'contracts/PINS.json').read_bytes())
        for name, row in pins.items():
            self.assertEqual(row['original']['path'], row['portable'])
            self.assertEqual(pin((RUNTIME / row['portable']).read_bytes()), {k: row['original'][k] for k in ('bytes', 'sha256')})
            self.assertEqual(set(row['source_identity']), {'bytes', 'sha256'})
        self.assertEqual(binding['scientific'], pins['SCIENTIFIC_CONTRACT.json']['original'])
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / 'contracts').mkdir()
            (dest / 'contracts/PINS.json').write_bytes(b'{}\n')
            old = self.contract.ROOT
            try:
                self.contract.ROOT = dest
                with self.assertRaises(self.io.Refusal):
                    self.contract.load()
            finally:
                self.contract.ROOT = old

    def test_metadata_join_closure(self):
        for name, excluded in [('SOURCE_INTERFACE.json', {'SOURCE_INTERFACE.json', 'SOURCE_FREEZE.json', 'manifest.json'}), ('SOURCE_FREEZE.json', {'SOURCE_FREEZE.json', 'manifest.json'})]:
            rows = json.loads((ROOT / name).read_bytes())['files']
            actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            self.assertEqual({p.removeprefix('benchmarks/neuroscience/neural-097/') for p in rows}, actual - excluded)
            for path, expected in rows.items():
                self.assertEqual(pin((ROOT / path.removeprefix('benchmarks/neuroscience/neural-097/')).read_bytes()), expected)
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        self.assertEqual(manifest['id'], 'NEURAL-097')
        self.assertFalse(manifest['admission']['runnable'])
        def walk(value):
            if isinstance(value, dict):
                if {'path', 'bytes', 'sha256'} <= value.keys():
                    self.assertTrue(value['path'].startswith('benchmarks/neuroscience/neural-097/'))
                    self.assertEqual(pin((ROOT / value['path'].removeprefix('benchmarks/neuroscience/neural-097/')).read_bytes()), {k: value[k] for k in ('bytes', 'sha256')})
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(manifest)

    def test_disabled_protected_boundary(self):
        self.assertFalse(self.contract.DEPLOYMENT_ENABLED)
        self.assertIsNone(self.contract.ROSTER._values)
        with self.assertRaises(self.io.Refusal):
            self.contract.bind_protected_roster({'path': '/never-opened-in-disabled-source'})
        with self.assertRaises(self.io.Refusal):
            len(self.contract.ROSTER)
        self.assertIsNone(self.contract.ROSTER._values)

    def test_routes_and_path_rejections(self):
        argv = ['--program', 'programme.json', '--output', 'fresh', '--review', 'protected.json', '--other-reserve-bytes', '0']
        self.assertEqual(self.adapter.parse('run', argv)[-1], 'candidate')
        self.assertEqual(self.adapter.parse('score', ['--submission', *argv[1:]])[-1], 'assemble')
        with self.assertRaises(self.adapter.PackagingRefusal):
            self.adapter.parse('operator', argv + ['--stage', 'prepare', '--condition', 'A-F'])
        for path in ('../x', '/absolute', 'a//b', 'a/../b', 'a\\b'):
            with self.assertRaises(self.adapter.PackagingRefusal):
                self.adapter.source_body(ROOT, path, 0, '0' * 64)

    def test_python_syntax_only(self):
        for path in ROOT.rglob('*.py'):
            ast.parse(path.read_bytes(), filename=path.name)

if __name__ == '__main__':
    unittest.main()
