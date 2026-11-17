"""Generated packaging controls. These never use official code or real data."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('checked_source_import', HERE / 'source_import.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class PackageControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cbramod-package-controls-')
        self.base = Path(self.tmp.name).resolve()
        self.external = self.base / 'external'; self.external.mkdir()
        self.package = self.base / 'package'; self.package.mkdir()
        self.dest = self.base / 'runtime'
        self.bodies = {'science/central_operator.py': b'# generated operator; not executed\n'}
        rows = []
        for i in range(103):
            name = ('runtime/source/official/' if i < 65 else 'runtime/source/benchmark/') + str(i) + '.py'
            raw = ('# generated source role ' + str(i) + '\n').encode()
            rows.append(dict(path=name, **pin(raw)))
            if i < 65:
                (self.external / (str(i) + '.py')).write_bytes(raw)
            else:
                self.bodies['science/' + name] = raw
        self.freeze = dict(task_id='PAPER-paper-method-024', role_count=103, roles=rows,
                           bytes=sum(r['bytes'] for r in rows))
        self.sync()

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self):
        self.bodies['science/SOURCE_FREEZE.json'] = json.dumps(self.freeze).encode()

    def run_prepare(self, dest=None):
        return source.prepare(self.bodies, str(self.external), str(dest or self.dest), str(self.package))

    def test_complete103_and_exact105_runtime_members(self):
        result = self.run_prepare()
        self.assertEqual((result['scientific_roles'], result['external_roles'], result['bundled_roles']), (103, 65, 38))
        files = [p for p in self.dest.rglob('*') if p.is_file()]
        self.assertEqual(len(files), 105)
        for row in self.freeze['roles']:
            self.assertEqual(pin((self.dest / row['path']).read_bytes()), {k: row[k] for k in ('bytes', 'sha256')})

    def test_last_external_mismatch_creates_nothing(self):
        (self.external / '64.py').write_bytes(b'wrong')
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.dest.exists())

    def test_missing_final_external_creates_nothing(self):
        (self.external / '64.py').unlink()
        with self.assertRaises(FileNotFoundError): self.run_prepare()
        self.assertFalse(self.dest.exists())

    def test_linked_external_members_refused(self):
        path = self.external / '0.py'; raw = path.read_bytes(); path.unlink()
        target = self.base / 'outside.py'; target.write_bytes(raw); path.symlink_to(target)
        with self.assertRaises(ValueError): self.run_prepare()
        path.unlink(); os.link(target, path)
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.dest.exists())

    def test_existing_destination_preserved(self):
        self.dest.mkdir(); (self.dest / 'keep').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'fresh destination'): self.run_prepare()
        self.assertEqual((self.dest / 'keep').read_bytes(), b'keep')

    def test_source_overlap_and_double_root_refused(self):
        for dest in (self.external, self.external / 'inside', self.package, self.base):
            with self.subTest(dest=dest), self.assertRaisesRegex(ValueError, 'disjoint'):
                self.run_prepare(dest)
        with self.assertRaisesRegex(ValueError, 'single-root'):
            source.prepare(self.bodies, '/' + str(self.external), str(self.dest), str(self.package))

    def test_missing_or_duplicate_authored_role_refused(self):
        original = copy.deepcopy(self.freeze)
        self.freeze['roles'].pop(); self.sync()
        with self.assertRaises(ValueError): self.run_prepare()
        self.freeze = original; self.freeze['roles'][-1] = self.freeze['roles'][-2]; self.sync()
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.dest.exists())

    def test_traversal_and_empty_file_pin_rules(self):
        for name in ('../outside', '/absolute', 'a/../b', 'a//b', 'a/./b'):
            with self.subTest(name=name), self.assertRaises(ValueError): source.relative(name)
        (self.external / 'empty').write_bytes(b'')
        self.assertEqual(source.capture(self.external, 'empty', pin(b'')), b'')
        with self.assertRaises(ValueError): source.capture(self.external, 'empty', dict(bytes=False, sha256=pin(b'')['sha256']))
