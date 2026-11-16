"""Portable source/CLI checks only; accepted numerical suites are not executed."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
RUNTIMES = {
    'dosei_score.py': (15749, '09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77'),
    'dosei_paired.py': (15568, '5f885ffd5052765cedf2fd81bf98f2638c56da3080acc100acd1e13b14bef497'),
}


def verified_members():
    manifest = json.loads((ROOT / 'SOURCE.json').read_bytes())
    members = manifest['files']; names = [row['path'] for row in members]
    if len(names) != len(set(names)) or any(Path(name).name != name for name in names):
        raise ValueError('exact flat source member list required')
    for row in members:
        path = ROOT / row['path']
        if path.is_symlink() or not path.is_file(): raise ValueError('ordinary source member required')
        body = path.read_bytes()
        if len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
            raise ValueError('source member changed: ' + row['path'])
    return names


class PortableChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members = verified_members()
        cls.temp = tempfile.TemporaryDirectory(prefix='dosei-portable-')
        cls.root = Path(cls.temp.name) / 'unrelated project with spaces'
        cls.root.mkdir()
        for name in cls.members + ['SOURCE.json']:
            shutil.copyfile(ROOT / name, cls.root / name)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_child(self, argv):
        result = subprocess.run([sys.executable, '-I', '-S', '-B', *argv], cwd=self.root,
                                capture_output=True, text=True, timeout=15)
        self.assertLessEqual(len(result.stdout.encode()) + len(result.stderr.encode()), 16384)
        return result

    def test_exact_unchanged_scientific_bodies_and_public_members(self):
        for name, (size, digest) in RUNTIMES.items():
            body = (self.root / name).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (size, digest))
        for name in self.members:
            text = (self.root / name).read_text()
            for private in ('/' + 'Users' + '/', '/' + 'home' + '/'):
                self.assertNotIn(private, text)
        self.assertEqual(set(p.name for p in self.root.iterdir()), set(self.members + ['SOURCE.json']))

    def test_clean_imports_retain_all_33_numerical_controls_without_running(self):
        script = '''
import importlib.util,json,pathlib,unittest
expected={'test_dosei.py':14,'test_paired.py':9,'test_primary_independent.py':5,'test_paired_independent.py':5}
counts={}
for name,count in expected.items():
    path=pathlib.Path(name).resolve()
    spec=importlib.util.spec_from_file_location('portable_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    counts[name]=unittest.defaultTestLoader.loadTestsFromModule(module).countTestCases()
    if counts[name]!=count:raise RuntimeError('accepted test inventory changed')
print(json.dumps(counts,sort_keys=True))
'''
        result = self.run_child(['-c', script])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(json.loads(result.stdout).values()), 33)

    def test_both_cli_help_interfaces_are_relocated(self):
        for name in RUNTIMES:
            result = self.run_child([name, '--help'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--expected-policy-sha256', result.stdout)
            self.assertIn('--expected-targets-sha256', result.stdout)
        self.assertIn('--primary-source', self.run_child(['dosei_paired.py', '--help']).stdout)

    def test_required_arguments_and_absent_policy_refuse_without_output(self):
        for name in RUNTIMES:
            result = self.run_child([name, '--output', 'must-not-exist.json'])
            self.assertEqual(result.returncode, 2)
            args = [name, '--output', 'must-not-exist.json']
            kinds = ['policy', 'predictions', 'targets']
            if name == 'dosei_paired.py':
                args += ['--primary-source', 'dosei_score.py']; kinds.insert(1, 'maps')
            for kind in kinds:
                args += ['--' + kind, 'absent-' + kind + '.json', '--expected-' + kind + '-sha256', '0' * 64]
            result = self.run_child(args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('absent-policy.json', result.stderr)
            self.assertFalse((self.root / 'must-not-exist.json').exists())
        self.assertEqual(set(p.name for p in self.root.iterdir()), set(self.members + ['SOURCE.json']))


if __name__ == '__main__':
    if sys.flags.optimize: raise RuntimeError('controls require assertions enabled')
    unittest.main()
