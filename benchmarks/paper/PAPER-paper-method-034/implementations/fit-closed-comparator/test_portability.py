"""Source/operand checks only; never a numerical or native benchmark run."""
from pathlib import Path
from contextlib import redirect_stdout
import hashlib
import importlib.abc
import importlib.util
import io
import json
import socket
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
CAPTURE_READ_ALLOWANCE = 1024 * 1024
SERIALIZED_IO_PRECHARGE = 64 * 1024
FORBIDDEN = {'numpy', 'scipy', 'sklearn', 'torch', 'cebra', 'MARBLE',
             'torch_geometric', 'ptu_dijkstra', 'elephant'}


class ForbidNumerical(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN:
            raise AssertionError('No numerical or native import: ' + fullname)


def forbidden(*args, **kwargs):
    raise AssertionError('No subprocess or network operation')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class SourcePortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads((ROOT / 'PUBLIC_INVENTORY.json').read_bytes())
        for row in cls.inventory['files']:
            raw = (ROOT / row['path']).read_bytes()
            assert len(raw) == row['bytes']
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
        cls.finder = ForbidNumerical()
        sys.meta_path.insert(0, cls.finder)
        cls.patches = [patch.object(subprocess, 'Popen', forbidden),
                       patch.object(socket, 'create_connection', forbidden),
                       patch.object(socket, 'socket', forbidden)]
        for item in cls.patches:
            item.start()
        cls.old_aliases = {name: sys.modules.get(name) for name in ('contract', 'campaign')}
        cls.contract = module('contract', ROOT / 'contract.py')
        sys.modules['contract'] = cls.contract
        cls.campaign = module('campaign', ROOT / 'campaign.py')
        sys.modules['campaign'] = cls.campaign
        cls.entry = module('marble_public_entry', ROOT / 'run_comparators.py')
        cls.dependencies = json.loads((ROOT / 'DEPENDENCIES.json').read_bytes())
        cls.provenance = json.loads((ROOT / 'PROVENANCE.json').read_bytes())

    @classmethod
    def tearDownClass(cls):
        assert not FORBIDDEN.intersection(sys.modules)
        for name, old in cls.old_aliases.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        sys.meta_path.remove(cls.finder)
        for item in reversed(cls.patches):
            item.stop()

    def test_ordinary_source_inventory(self):
        expected = {row['path'] for row in self.inventory['files']} | {'PUBLIC_INVENTORY.json'}
        self.assertEqual(len(expected), 22)
        self.assertEqual({p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}, expected)
        for path in [ROOT, *ROOT.rglob('*')]:
            self.assertFalse(path.is_symlink())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755 if path.is_dir() else 0o644)

    def test_complete_descriptors_keep_native_inputs_external(self):
        required = self.provenance['required_dependencies']
        self.assertEqual(len(required), 26)
        self.assertEqual({r['role'] for r in required}, set(self.dependencies['files']))
        self.assertEqual(sum(r['bundled'] for r in required), 10)
        self.assertEqual(sum(not r['bundled'] for r in required), 16)
        for row in required:
            actual = self.dependencies['files'][row['role']]
            for key in ('path', 'bytes', 'sha256'):
                self.assertEqual(actual[key], row[key])
            self.assertEqual((REPOSITORY / row['path']).is_file(), row['bundled'])
        self.assertFalse(self.provenance['native_source_closure_bundled'])
        self.assertFalse(self.provenance['external_execution_authority_supplied'])
        self.assertFalse(self.provenance['scientific_qualification'])

    def test_full_declared_coordinate_scope(self):
        path = REPOSITORY / self.dependencies['files']['protocol']['path']
        protocol = json.loads(path.read_bytes())
        coordinates = self.contract.schedule(protocol)
        self.assertEqual(len(coordinates), 48)
        self.assertEqual(len({self.contract.key(c) for c in coordinates}), 48)
        self.assertEqual({c['rat'] for c in coordinates}, {'achilles', 'buddy', 'cicero', 'gatsby'})
        self.assertEqual({c['method'] for c in coordinates}, {'marble', 'cebra-time', 'cebra-behavior'})
        self.assertEqual({c['condition'] for c in coordinates}, {'clean', 'half'})
        self.assertEqual({c['dimension'] for c in coordinates}, {3, 32})

    def test_actual_inspect_is_declarative_only(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['run_comparators.py', 'inspect']), redirect_stdout(output):
            self.entry.main()
        raw = output.getvalue().encode()
        self.assertLess(len(raw), SERIALIZED_IO_PRECHARGE)
        observed = json.loads(raw)
        self.assertEqual(observed, {'task': 'PAPER-paper-method-034', 'fits': 48,
                         'queries': 48, 'comparator_embeddings': 96,
                         'generic_runner': None, 'scientific_qualification': False})

    def test_actual_missing_protected_operands_refuse(self):
        for action in ('construct', 'grade'):
            with self.subTest(action=action):
                with patch.object(sys, 'argv', ['run_comparators.py', action]):
                    with self.assertRaisesRegex(ValueError, '^explicit protected operand repo$'):
                        self.entry.main()

    def test_actual_bootstrap_refuses_unbundled_native_source(self):
        manifest = (ROOT / 'SOURCE_MANIFEST.json').read_bytes()
        expected = {'bytes': len(manifest), 'sha256': hashlib.sha256(manifest).hexdigest()}
        budget = self.contract.Budget(CAPTURE_READ_ALLOWANCE, 1)
        first = next(r for r in self.provenance['required_dependencies'] if not r['bundled'])
        with patch.object(self.campaign, 'source_module', side_effect=AssertionError('No compiled runtime before complete source')) as compile_guard:
            with self.assertRaises(FileNotFoundError) as refused:
                self.campaign.bootstrap(REPOSITORY, ROOT, expected, budget)
            compile_guard.assert_not_called()
        self.assertEqual(Path(refused.exception.filename), REPOSITORY / first['path'])
        self.assertGreater(budget.reads, 0)
        self.assertLessEqual(budget.reads, CAPTURE_READ_ALLOWANCE)
        self.assertEqual(budget.writes, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
