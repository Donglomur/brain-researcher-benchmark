"""Generated bundle/control checks; real isolated stdlib children, no neural data."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('n077_bundle_under_test', HERE / 'bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

MAIN = b'''import json, struct, sys
from helper import probability
from neural077_config import CONFIG
import neural077_config

def main():
    size = struct.unpack('!I', sys.stdin.buffer.read(4))[0]
    request = json.loads(sys.stdin.buffer.read(size))
    guards = 0
    try:
        CONFIG['offset'] = 9
    except TypeError:
        guards += 1
    try:
        CONFIG['nested']['values'][0] = 9
    except TypeError:
        guards += 1
    try:
        neural077_config.CONFIG = {}
    except TypeError:
        guards += 1
    answer = {'trial_id': request['trial_id'], 'target_probability': probability(),
              'immutable_guards': guards, 'frozen_file': __file__.startswith('frozen://')}
    body = json.dumps(answer).encode()
    sys.stdout.buffer.write(struct.pack('!I', len(body)) + body)
    sys.stdout.buffer.flush()
'''
HELPER = b'''from neural077_config import CONFIG
def probability():
    return CONFIG['offset'] + CONFIG['nested']['values'][0]
'''
CONFIG = b'{"offset":0.2,"nested":{"values":[0.15]}}\n'
MANIFEST = {'schema': bundle.SCHEMA, 'entry_module': 'main',
            'modules': ['helper.py', 'main.py'], 'config': 'config.json'}


class BundleControls(unittest.TestCase):
    written_bytes = 0
    child_processes = 0

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'generated_bundle_fixture_bytes_written': cls.written_bytes,
                          'logical_fixture_bytes_overwritten_or_reclaimed': cls.written_bytes,
                          'retained_fixture_bytes': 0, 'real_isolated_children': cls.child_processes,
                          'authentic_inputs_or_provider_calls': 0}))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural077-bundle-generated-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.members = self.root / 'source'
        self.members.mkdir()
        for name, body in [('main.py', MAIN), ('helper.py', HELPER), ('config.json', CONFIG)]:
            self.write(self.members / name, body)

    def write(self, path, body):
        path.write_bytes(body)
        type(self).written_bytes += len(body)

    def captured(self):
        return bundle.capture(self.members, copy.deepcopy(MANIFEST))

    def restored(self, frozen, name='restored'):
        result = bundle.restore(frozen, self.root / name)
        type(self).written_bytes += result['pin']['bytes']
        return Path(result['path'])

    def child(self, client, cwd=None):
        directory = cwd or self.root / 'empty-cwd'
        directory.mkdir(exist_ok=True)
        body = b'{"trial_id":"generated-bundle-only"}'
        type(self).child_processes += 1
        return subprocess.run([sys.executable, '-I', '-S', '-B', str(client)],
            cwd=directory, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
            input=struct.pack('!I', len(body)) + body, capture_output=True, timeout=8)

    def test_real_isolated_child_uses_embedded_dependency_and_immutable_config(self):
        frozen = self.captured()
        # The complete captured record is plain JSON, not Python bytes/pickle.
        roundtrip = bundle.decode(bundle.encoded(frozen))
        self.assertEqual(bundle.verify(roundtrip), bundle.verify(frozen))
        client = self.restored(roundtrip)
        self.assertEqual(client.stat().st_mode & 0o777, 0o400)
        self.assertEqual(client.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(set(p.name for p in client.parent.iterdir()), {'CLIENT.py'})
        shutil.rmtree(self.members)
        result = self.child(client)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b'')
        size = struct.unpack('!I', result.stdout[:4])[0]
        self.assertEqual(size, len(result.stdout) - 4)
        answer = json.loads(result.stdout[4:])
        self.assertAlmostEqual(answer['target_probability'], .35)
        self.assertEqual(answer['trial_id'], 'generated-bundle-only')
        self.assertEqual(answer['immutable_guards'], 3)
        self.assertTrue(answer['frozen_file'])

    def test_restored_launcher_ignores_source_and_cwd_replacements(self):
        frozen = self.captured()
        self.write(self.members / 'helper.py', b"raise RuntimeError('changed original must never execute')\n")
        cwd = self.root / 'hostile-cwd'
        cwd.mkdir()
        self.write(cwd / 'helper.py', b"raise RuntimeError('cwd module must never execute')\n")
        result = self.child(self.restored(frozen), cwd)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertAlmostEqual(json.loads(result.stdout[4:])['target_probability'], .35)

    def test_precommit_source_and_config_drift_refused(self):
        frozen = self.captured()
        self.assertEqual(bundle.verify_source(self.members, frozen), frozen['bundle_identity'])
        self.write(self.members / 'helper.py', HELPER + b'# source changed\n')
        with self.assertRaisesRegex(ValueError, 'changed after capture'):
            bundle.verify_source(self.members, frozen)
        self.write(self.members / 'helper.py', HELPER)
        self.write(self.members / 'config.json', b'{"offset":0.9,"nested":{"values":[0.15]}}')
        with self.assertRaisesRegex(ValueError, 'changed after capture'):
            bundle.verify_source(self.members, frozen)

    def test_earlier_member_changed_during_later_read_refused(self):
        original = bundle.read_member
        def changing(directory_fd, name, cap):
            result = original(directory_fd, name, cap)
            if name == 'main.py':
                self.write(self.members / 'helper.py', HELPER + b'# changed after its own read\n')
            return result
        with mock.patch.object(bundle, 'read_member', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'member changed before complete capture'):
                self.captured()

    def test_changed_frozen_member_config_launcher_and_identity_refused(self):
        frozen = self.captured()
        for kind in ('member', 'config', 'launcher', 'identity'):
            bad = copy.deepcopy(frozen)
            if kind == 'member':
                bad['members']['helper.py']['base64'] = base64.b64encode(HELPER + b'# tampered').decode()
            elif kind == 'config':
                bad['config']['offset'] = 9
            elif kind == 'launcher':
                bad['launcher']['sha256'] = '0' * 64
            else:
                bad['bundle_identity']['sha256'] = '0' * 64
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                bundle.verify(bad)

    def test_changed_entrypoint_and_member_roster_refused(self):
        frozen = self.captured()
        bad = copy.deepcopy(frozen)
        bad['manifest']['entry_module'] = 'helper'
        with self.assertRaisesRegex(ValueError, 'launcher source changed'):
            bundle.verify(bad)
        bad = copy.deepcopy(frozen)
        bad['members']['extra.py'] = bad['members']['helper.py']
        with self.assertRaisesRegex(ValueError, 'declared captured members'):
            bundle.verify(bad)

    def test_extra_file_or_directory_refused(self):
        self.write(self.members / 'extra.py', b'pass\n')
        with self.assertRaisesRegex(ValueError, 'exactly declared files'):
            self.captured()
        (self.members / 'extra.py').unlink()
        (self.members / 'cache').mkdir()
        with self.assertRaisesRegex(ValueError, 'exactly declared files'):
            self.captured()

    def test_symbolic_hard_and_root_links_refused(self):
        target = self.root / 'outside.py'
        self.write(target, HELPER)
        (self.members / 'helper.py').unlink()
        (self.members / 'helper.py').symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            self.captured()
        (self.members / 'helper.py').unlink()
        os.link(target, self.members / 'helper.py')
        with self.assertRaisesRegex(ValueError, 'singly linked'):
            self.captured()
        linked_root = self.root / 'root-link'
        linked_root.symlink_to(self.members, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked path'):
            bundle.capture(linked_root, MANIFEST)

    def test_traversal_packages_duplicates_and_stdlib_collisions_refused(self):
        for names in (['../main.py'], ['package/main.py'], ['main.py', 'main.py'], ['json.py'], ['__init__.py']):
            bad = copy.deepcopy(MANIFEST)
            bad['modules'] = names
            bad['entry_module'] = names[0][:-3]
            with self.subTest(names=names), self.assertRaises(ValueError):
                bundle.capture(self.members, bad)

    def test_duplicate_nonfinite_deep_and_nonobject_config_refused(self):
        bodies = [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e309}', b'[]',
                  b'{"x":' + b'[' * 17 + b'0' + b']' * 17 + b'}']
        for body in bodies:
            self.write(self.members / 'config.json', body)
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.captured()

    def test_member_and_config_extent_caps(self):
        self.write(self.members / 'helper.py', b'#' + b'x' * bundle.MODULE_CAP)
        with self.assertRaisesRegex(ValueError, 'Bounded ordinary'):
            self.captured()
        self.write(self.members / 'helper.py', HELPER)
        self.write(self.members / 'config.json', b' ' * (bundle.CONFIG_CAP + 1))
        with self.assertRaisesRegex(ValueError, 'Bounded ordinary'):
            self.captured()

    def test_undeclared_dependency_refused_by_real_isolated_child(self):
        self.write(self.members / 'main.py', b'import undeclared_external\ndef main():\n    pass\n')
        client = self.restored(self.captured())
        cwd = self.root / 'external-cwd'
        cwd.mkdir()
        self.write(cwd / 'undeclared_external.py', b'raise RuntimeError("unfrozen dependency executed")\n')
        result = self.child(client, cwd)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Undeclared participant module: undeclared_external', result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_existing_restore_destination_refused(self):
        frozen = self.captured()
        self.restored(frozen)
        with self.assertRaises(FileExistsError):
            bundle.restore(frozen, self.root / 'restored')


if __name__ == '__main__':
    unittest.main(verbosity=2)
