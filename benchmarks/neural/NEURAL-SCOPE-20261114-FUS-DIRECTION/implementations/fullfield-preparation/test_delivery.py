"""Portable source admission only; retained scientific methods are never run."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
UNCHANGED = {
    'fullfield.py': (12927, '20fe65ee870ae6a7a18c8534e3b935cdd30b75b49993adb9a644ff0f9b1422d6'),
    'scorer.py': (14394, '6956a375c850a21abab2febc99cb3579900e74606cf3dd199ac2661ab0270dc7'),
    'roster.py': (2755, '0f1ac943d56edc5305be4ba74f5d27c8cfa626e555092b7a51a1f6f2641dd4c9'),
    'test_fullfield.py': (10939, '2c3d0d20a321dc1f4f15bb15c769eb7a3f7f008ad7c1899c1bcb6ea7703a265e'),
}


def verified_members(root):
    manifest = root / 'SOURCE.json'
    if root.is_symlink() or not root.is_dir() or manifest.is_symlink() or not manifest.is_file():
        raise ValueError('ordinary component directory and manifest required')
    obj = json.loads(manifest.read_bytes())
    rows = obj['files']
    names = [row['path'] for row in rows]
    if len(names) != len(set(names)) or any(Path(name).name != name or name == 'SOURCE.json' for name in names):
        raise ValueError('exact flat source members required')
    entries = list(root.iterdir())
    if {p.name for p in entries} != set(names) | {'SOURCE.json'}:
        raise ValueError('complete exact component directory required')
    for row in rows:
        path = root / row['path']
        if path.is_symlink() or not path.is_file():
            raise ValueError('ordinary source member required: ' + row['path'])
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('source member changed: ' + row['path'])
    return names


class PortableChecks(unittest.TestCase):
    def setUp(self):
        self.members = verified_members(ROOT)
        self.temp = tempfile.TemporaryDirectory(prefix='fus-portable-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'unrelated directory with spaces'
        self.root.mkdir()
        for name in self.members + ['SOURCE.json']:
            shutil.copyfile(ROOT / name, self.root / name)

    def child(self, tail):
        script = ('import hashlib,json,pathlib,sys\nfrom pathlib import Path\n' +
                  inspect.getsource(verified_members) + '\nverified_members(Path.cwd())\n' +
                  'sys.path.insert(0,str(Path.cwd()))\n' + tail)
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', script],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertLessEqual(len(result.stdout.encode()) + len(result.stderr.encode()), 16384)
        return result

    def test_unchanged_science_and_preserved_independent_function_bodies(self):
        for name, expected in UNCHANGED.items():
            raw = (self.root / name).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), expected)
        provenance = json.loads((self.root / 'PROVENANCE.json').read_bytes())
        source = ast.parse((self.root / 'test_independent.py').read_text())
        functions = {n.name: n for n in source.body if isinstance(n, ast.FunctionDef)}
        expected = provenance['retained_independent_function_AST_SHA256']
        self.assertEqual(set(functions), set(expected))
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256(ast.dump(functions[name], include_attributes=False).encode()).hexdigest(), digest)
        for name in self.members:
            text = (self.root / name).read_text()
            for private in ('/' + 'Users' + '/', '/' + 'home' + '/'):
                self.assertNotIn(private, text)

    def test_clean_relocated_imports_and_sixteen_discovered_tests_without_run(self):
        result = self.child('''
import fullfield, scorer, roster, test_fullfield, test_independent, unittest
assert fullfield.validate_intake is scorer.validate_intake
assert scorer.ROSTER is roster.ROSTER
counts={m.__name__:unittest.defaultTestLoader.loadTestsFromModule(m).countTestCases()
        for m in (test_fullfield,test_independent)}
assert counts=={'test_fullfield':11,'test_independent':5}
assert all(Path(m.__file__).parent==Path.cwd() for m in (fullfield,scorer,roster,test_fullfield,test_independent))
print(json.dumps(counts,sort_keys=True))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(json.loads(result.stdout).values()), 16)

    def test_tampered_dependency_refuses_before_any_runtime_import(self):
        path = self.root / 'roster.py'
        path.write_bytes(path.read_bytes() + b"\nopen('unexpected-import.txt','w').write('not admitted')\n")
        result = self.child('import fullfield\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source member changed: roster.py', result.stderr)
        self.assertFalse((self.root / 'unexpected-import.txt').exists())

    def test_missing_or_linked_dependency_refuses_before_runtime_import(self):
        path = self.root / 'scorer.py'
        raw = path.read_bytes()
        path.unlink()
        result = self.child('import fullfield\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('complete exact component directory required', result.stderr)
        path.symlink_to(ROOT / 'scorer.py')
        result = self.child('import fullfield\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ordinary source member required: scorer.py', result.stderr)
        path.unlink()
        path.write_bytes(raw)


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('controls require assertions enabled')
    unittest.main()
