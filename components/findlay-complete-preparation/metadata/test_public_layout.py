"""New public-layout checks. Invented inputs only; no previous science replay."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FILES = {
    'provision_identity_policy.py': (8269, '9432a2b5876774267d0f9e3578facf67346559e543b4aab347c7cf30542b1c03'),
    'provision_family_ledger.py': (8088, '37509a286f9ad3f8b21916aa8fd050c953be8896a657150a48422c6ed991dc95'),
    'CURATED_CROSSWALK.json': (32045, '508f2929ce81e100af354daffa9c28eb567d3d38fd0273180d3c76aa87045194'),
    'test_provisioning.py': (7609, 'ee08fdb7268eccff43c9937aff08050b629de42f85162ece49c399d30529735c'),
}
COPIED_BYTES = 0
MAX_SCRATCH_FILE_BYTES = 0


class PublicLayout(unittest.TestCase):
    def setUp(self):
        global COPIED_BYTES, MAX_SCRATCH_FILE_BYTES
        self.temporary = tempfile.TemporaryDirectory(prefix='findlay metadata layout ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scripts = self.root / 'relocated component with spaces'
        self.scripts.mkdir()
        for name, pin in FILES.items():
            body = (HERE / name).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), pin)
            (self.scripts / name).write_bytes(body)
            COPIED_BYTES += len(body)
        MAX_SCRATCH_FILE_BYTES = max(MAX_SCRATCH_FILE_BYTES, sum(x[0] for x in FILES.values()))
        self.cwd = self.root / 'unrelated working directory'; self.cwd.mkdir()
        self.output = self.root / 'private output.json'

    def cli(self, name, *args):
        env = {key: value for key, value in os.environ.items()
               if key not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run([sys.executable, '-S', '-B', str(self.scripts / name), *map(str, args)],
                                cwd=self.cwd, env=env, capture_output=True, timeout=5)
        self.assertLess(len(result.stdout) + len(result.stderr), 32768)
        self.assertFalse(any(self.root.rglob('__pycache__')))
        return result

    def test_both_documented_entrypoints_resolve_from_unrelated_cwd(self):
        for name in ('provision_identity_policy.py', 'provision_family_ledger.py'):
            result = self.cli(name, '--help')
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertIn(b'--output', result.stdout)
        self.assertFalse(self.output.exists())

    def test_identity_cli_reaches_fixed_admission_without_repo_imports(self):
        original = self.root / 'invented official source'; original.write_bytes(b'invented')
        result = self.cli('provision_identity_policy.py', '--core', original, '--loader', original,
                          '--exporter', original, '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Exact source extent', result.stderr)
        self.assertNotIn(b'ModuleNotFoundError', result.stderr)
        self.assertFalse(self.output.exists())

    def test_family_cli_uses_relocated_companion_crosswalk(self):
        global COPIED_BYTES
        original = self.root / 'invented workbook'; original.write_bytes(b'invented')
        result = self.cli('provision_family_ledger.py', '--workbook', original,
                          '--official-source-root', self.root, '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Exact source extent', result.stderr)
        self.assertNotIn(b'ModuleNotFoundError', result.stderr)
        self.assertFalse(self.output.exists())
        # The crosswalk must be resolved beside the relocated script, not from cwd.
        (self.scripts / 'CURATED_CROSSWALK.json').unlink()
        shutil.copyfile(HERE / 'CURATED_CROSSWALK.json', self.cwd / 'CURATED_CROSSWALK.json')
        COPIED_BYTES += FILES['CURATED_CROSSWALK.json'][0]
        result = self.cli('provision_family_ledger.py', '--workbook', original,
                          '--official-source-root', self.root, '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'FileNotFoundError', result.stderr)
        self.assertFalse(self.output.exists())

    def test_generated_positive_derivation_keeps_exact_schema_after_relocation(self):
        # Import only copied package members. No authentic policy/source is read.
        old_path = list(sys.path)
        prior = {name: sys.modules.pop(name, None) for name in
                 ('provision_identity_policy', 'provision_family_ledger')}
        try:
            sys.path.insert(0, str(self.scripts))
            spec = importlib.util.spec_from_file_location('relocated_fixture', self.scripts / 'test_provisioning.py')
            fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
            value = fixture.p.derive(*fixture.fixture())
            self.assertEqual(value['schema'], 'findlay-private-identity-policy/v1')
            self.assertEqual(len(value['balanced_subjects']), 5)
            self.assertEqual(len(value['ordinary_exclusion']['columns']), 13)
            self.assertEqual(len(fixture.f.headers(fixture.workbook())), 98)
            self.assertFalse(self.output.exists())
        finally:
            sys.path[:] = old_path
            for name, module in prior.items():
                sys.modules.pop(name, None)
                if module is not None: sys.modules[name] = module


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicLayout))
    print(json.dumps({'generated_layout_methods': result.testsRun,
                      'passed': result.wasSuccessful(), 'copied_source_bytes': COPIED_BYTES,
                      'maximum_copied_source_bytes_in_one_scratch': MAX_SCRATCH_FILE_BYTES,
                      'authentic_input_reads': 0, 'native_or_model_runs': 0}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
