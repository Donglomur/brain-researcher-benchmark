"""Portable packaging regression controls; generated source bytes only."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
import n061_public_verifier as verifier


class PackageTests(unittest.TestCase):
    def clone(self, root):
        bodies = __verified_package__['bodies']
        for name, body in bodies.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        raw = bodies['SOURCE_MANIFEST.json']
        return len(raw), hashlib.sha256(raw).hexdigest()

    def test_relocated_closed_dependency_population(self):
        root = __verified_package__['root']; bodies = __verified_package__['bodies']
        self.assertNotEqual(Path.cwd(), root)
        self.assertTrue(root.is_relative_to(Path.cwd()))
        raw = bodies['SOURCE_MANIFEST.json']; verified = verifier.authenticate(root, len(raw), hashlib.sha256(raw).hexdigest())
        self.assertEqual(verified, bodies)
        self.assertEqual(len(verifier.parse(bodies['producer/INHERITED.json'])['runtime']), 22)

    def test_tampered_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); size, sha = self.clone(root)
            path = root / 'producer/adapter.py'; path.write_bytes(path.read_bytes() + b'\n# changed\n')
            with self.assertRaises(ValueError): verifier.authenticate(root, size, sha)

    def test_unlisted_cached_bytecode_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); size, sha = self.clone(root)
            cache = root / 'producer/__pycache__'; cache.mkdir()
            (cache / 'adapter.cpython-311.pyc').write_bytes(b'not executed')
            with self.assertRaisesRegex(ValueError, 'exact source population'):
                verifier.authenticate(root, size, sha)

    def test_manifest_and_inner_binding_refusals(self):
        with self.assertRaises(ValueError): verifier.parse(b'{"a":1,"a":2}')
        for path in ('../outside.py', '/absolute.py', 'producer/../outside.py', 'a//b.py'):
            with self.subTest(path=path), self.assertRaises(ValueError): verifier.relative(path)
        bodies = dict(__verified_package__['bodies'])
        inherited = verifier.parse(bodies['producer/INHERITED.json'])
        inherited['installed_manifest']['sha256'] = '0' * 64
        bodies['producer/INHERITED.json'] = json.dumps(inherited).encode()
        # Even an outer-selected body cannot silently contradict its inner pins.
        with self.assertRaises(ValueError): verifier.inner_joins(bodies)

    def test_no_skip_or_expected_failure_can_be_called_success(self):
        fields = dict(testsRun=26, failures=[], errors=[], skipped=[], expectedFailures=[], unexpectedSuccesses=[])
        good = types.SimpleNamespace(**fields, wasSuccessful=lambda: True)
        self.assertTrue(verifier.completed(good, 26))
        for name in ('failures', 'errors', 'skipped', 'expectedFailures', 'unexpectedSuccesses'):
            altered = dict(fields); altered[name] = [('generated', 'not a full pass')]
            self.assertFalse(verifier.completed(types.SimpleNamespace(**altered, wasSuccessful=lambda: True), 26))
        good.testsRun = 25; self.assertFalse(verifier.completed(good, 26))
