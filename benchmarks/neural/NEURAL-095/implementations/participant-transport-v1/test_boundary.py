"""Actual generated local boundary controls; no original packets or targets."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import test_transport as support

t = support.t

class BoundaryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='.generated-participant-boundary-', dir=support.HERE)
        cls.root = Path(cls.temp.name)
        cls.f = support.Fixture(cls.root / 'inputs')
    @classmethod
    def tearDownClass(cls):
        print('GENERATED_BOUNDARY_RETAINED_BYTES_BEFORE_CLEANUP=' + str(sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())))
        cls.temp.cleanup()

    def test_actual_macos_client_denies_raw_opposite_targets_writes_network_and_fork(self):
        if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
            self.skipTest('Actual macOS sandbox is unavailable on this host; no containment claim')
        markers = [self.f.files['cue_only']['train.npz'], self.f.files['neural']['query.npz'],
                   support.put(self.root / 'private-query-targets.json', b'{"private":"generated marker"}'),
                   support.put(self.root / 'reference-grade.json', b'{"grade":"generated marker"}')]
        prelude = '''import errno, os, socket
from pathlib import Path
assert 'HOME' not in os.environ and 'PATH' not in os.environ
assert Path(__file__).read_bytes().startswith(b'import')
def denied(call):
 try: call()
 except OSError as error:
  assert error.errno in (errno.EPERM,errno.EACCES), str(error)
  return
 raise AssertionError('operation unexpectedly permitted')
for target in MARKERS: denied(lambda: Path(target).read_bytes())
denied(lambda: Path(WRITE_TARGET).write_text('forbidden'))
denied(lambda: Path('local-write').write_text('forbidden'))
def network():
 with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
  connection.settimeout(.5);connection.connect(('127.0.0.1',9))
denied(network)
def fork():
 pid=os.fork()
 if pid==0: os._exit(0)
 os.waitpid(pid,0)
denied(fork)
'''.replace('MARKERS', repr(list(map(str, markers)))).replace('WRITE_TARGET', repr(str(self.root / 'forbidden-created-file')))
        client = support.put(self.root / 'restricted-client.py', (prelude + support.CLIENT_WIRE + support.QUERY_LOOP).encode())
        result = t.run_view(self.f.packets['cue_only'], self.root / 'restricted-session', client,
                            support.PYTHON, 'macos', support.LIMITS)
        self.assertEqual(result['status'], 'complete_unscored', result)
        self.assertEqual((result['images'], result['actions']), (258, 517))
        self.assertFalse((self.root / 'forbidden-created-file').exists())
        self.assertEqual(result['process_group_cleanup'], 'absent')
        t.audit_view(self.root / 'restricted-session', self.f.packets['cue_only'])
        boundary = support.json_at(self.root / 'restricted-session/BOUNDARY.json')
        self.assertEqual(boundary['sandbox'], 'macos')
        self.assertFalse(boundary['provider_context_qualified'])
        self.assertFalse(boundary['scientific_qualification'])

    def test_client_symlink_and_existing_output_refused_before_launch(self):
        client = support.put(self.root / 'ordinary.py', b'pass\n')
        linked = self.root / 'linked.py'; linked.symlink_to(client)
        with self.assertRaises(ValueError):
            t.run_view(self.f.packets['cue_only'], self.root / 'symlink-must-not-launch', linked,
                       support.PYTHON, 'protocol_only', support.LIMITS)
        self.assertFalse((self.root / 'symlink-must-not-launch').exists())
        output = self.root / 'already-there'; output.mkdir()
        marker = support.put(output / 'untouched', b'original')
        with self.assertRaises(FileExistsError):
            t.run_view(self.f.packets['cue_only'], output, client, support.PYTHON, 'protocol_only', support.LIMITS)
        self.assertEqual(marker.read_bytes(), b'original')

    def test_sandbox_capture_and_child_lifecycle_cannot_be_relabelled(self):
        # Early exit is sufficient: original lifecycle fields must record failure,
        # and removing the top-level marker cannot turn this into completion.
        client = support.put(self.root / 'early-client.py', support.CLIENT_WIRE.encode())
        output = self.root / 'early-session'
        result = t.run_view(self.f.packets['cue_only'], output, client, support.PYTHON, 'protocol_only', support.LIMITS)
        self.assertEqual(result['status'], 'failed')
        marker = output / 'FAILED.json'; saved = marker.read_bytes(); marker.unlink()
        try:
            with self.assertRaises(ValueError): t.audit_view(output, self.f.packets['cue_only'])
        finally: support.put(marker, saved)

if __name__ == '__main__':
    unittest.main(verbosity=2)
