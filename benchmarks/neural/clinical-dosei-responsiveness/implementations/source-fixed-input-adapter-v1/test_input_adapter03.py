"""Fictional filesystem behind the unchanged reader; no authentic inputs."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'input_adapter.py'
module = sys.modules['input_adapter_reviewed']
IO_SOURCE = sys.modules['frozen_input_reader_source'].raw
if hashlib.sha256(IO_SOURCE).hexdigest() != module.IO_SHA256:
    raise RuntimeError('existing reader changed')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')+b'\n'


class MemoryFS:
    """Only OS file operations are fake; actual Meter/Reader code is exercised."""
    def __init__(self):
        self.root = Path('/generated/dosei-inputs')
        self.files = {}
        self.fds = {}
        self.opens = []
        self.closes = []
        self.next_fd = 100000
        self.fail_read = None
        self.fail_close = None
        self.read_error = OSError('generated interrupted read')
        self.version = 1
    def put(self, path, raw):
        path = str(path)
        self.version += 1
        self.files[path] = (bytes(raw), self.version)
    def lstat(self, path, *args, **kwargs):
        key = os.fsdecode(path)
        if key in self.files:
            raw, version = self.files[key]
            return types.SimpleNamespace(st_mode=stat.S_IFREG|0o600, st_nlink=1, st_uid=os.getuid(),
                st_size=len(raw), st_dev=17, st_ino=version, st_mtime_ns=version, st_ctime_ns=version)
        if key == '/generated' or key.startswith(str(self.root)):
            return types.SimpleNamespace(st_mode=stat.S_IFDIR|0o700, st_nlink=1, st_uid=os.getuid(),
                st_size=0, st_dev=17, st_ino=1, st_mtime_ns=1, st_ctime_ns=1)
        return self.original_lstat(path, *args, **kwargs)
    def stat(self, path, *args, **kwargs):
        key = os.fsdecode(path)
        if key in self.files or key == '/generated' or key.startswith(str(self.root)):
            return self.lstat(path)
        return self.original_stat(path, *args, **kwargs)
    def open(self, path, flags, *args, **kwargs):
        key = os.fsdecode(path)
        if key not in self.files:
            raise AssertionError('unlisted generated file open: '+key)
        if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT):
            raise AssertionError('generated input write requested')
        self.next_fd += 1
        self.fds[self.next_fd] = [key, 0]
        self.opens.append(key)
        return self.next_fd
    def read(self, fd, count):
        path, offset = self.fds[fd]
        if path == self.fail_read:
            raise self.read_error
        raw = self.files[path][0][offset:offset+count]
        self.fds[fd][1] += len(raw)
        return raw
    def fstat(self, fd):
        return self.lstat(self.fds[fd][0])
    def close(self, fd):
        path = self.fds[fd][0]
        self.closes.append(path)
        if path == self.fail_close:
            raise OSError('generated uncertain close')
        del self.fds[fd]
    @contextmanager
    def active(self):
        self.original_lstat = os.lstat
        self.original_stat = os.stat
        with patch.object(os, 'stat', self.stat), patch.object(os, 'lstat', self.lstat), \
             patch.object(os, 'open', self.open), \
             patch.object(os, 'read', self.read), patch.object(os, 'fstat', self.fstat), \
             patch.object(os, 'close', self.close):
            yield self
    def bound(self, path, *, closed=False):
        raw = self.files[str(path)][0]
        value = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        if closed:
            # lstat on these known memory members does not need an active patch.
            value['closed_file_signature'] = {key: getattr(self.lstat(path), key) for key in
                ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
        return value


class Fixture:
    def __init__(self):
        self.fs = MemoryFS()
        root = self.fs.root
        self.signal_root = root/'signals'
        self.indices = root/'indices'
        self.observations = root/'observations'
        self.paths = {
            'cohort': self.observations/'COHORT.json', 'success': self.observations/'SUCCESS.json',
            'observations': self.observations/'OBSERVATIONS.provisional.jsonl',
            'index_manifest': self.indices/'MANIFEST.json', 'index_cases': self.indices/'CASES.provisional.jsonl',
            'key': self.indices/'case-key.bin', 'numeric_cohort': self.signal_root/'COHORT_SUCCESS.json',
            'numeric_proof': root/'proof'/'verification.json', 'accepted_observation_evidence': root/'public'/'evidence.json'}
        self.member_bodies = {}
        for number in range(1, 172):
            rid = str(number)
            raw = canonical({'schema': 'dosei_full_eeg_member_success_v1', 'status': 'succeeded', 'recording_id': rid})
            path = self.signal_root/f'recording-{rid}.success.json'
            self.fs.put(path, raw)
            self.member_bodies[rid] = raw
        for role in ('observations', 'index_cases', 'numeric_proof', 'accepted_observation_evidence'):
            self.fs.put(self.paths[role], canonical({'fictional_role': role}))
        self.fs.put(self.paths['key'], b'Q'*32)
        self.numeric = {'complete_member_receipts': []}
        self.index = {'recordings': [], 'key': self.fs.bound(self.paths['key'])}
        self.cohort = {'schema': 'dosei_complete_paired_observations_v1', 'status': 'complete',
            'cases': 7345, 'recordings': 171, 'native_member_bindings': []}
        for rid in self.member_bodies:
            path = self.signal_root/f'recording-{rid}.success.json'
            self.cohort['native_member_bindings'].append({'recording_id': rid, 'receipt': self.fs.bound(path)})
            self.numeric['complete_member_receipts'].append({'recording_id': rid, 'receipt': self.fs.bound(path, closed=True)})
            self.index['recordings'].append({'recording_id': rid, 'native_receipt': self.fs.bound(path)})
        self.rebuild()
    def rebuild(self):
        """Rebind only outer authentication; preserve deliberate semantic mutations."""
        self.fs.put(self.paths['index_manifest'], canonical(self.index))
        self.fs.put(self.paths['numeric_cohort'], canonical(self.numeric))
        for field, role in (('observations', 'observations'), ('source_index_manifest', 'index_manifest'),
                            ('source_case_stream', 'index_cases'), ('numeric_cohort', 'numeric_cohort'),
                            ('numeric_verification', 'numeric_proof')):
            self.cohort[field] = self.fs.bound(self.paths[role], closed=role == 'observations')
        self.fs.put(self.paths['cohort'], canonical(self.cohort))
        success = {'schema': 'dosei_complete_paired_success_v1', 'status': 'succeeded',
            'cohort': self.fs.bound(self.paths['cohort'], closed=True), 'observations': self.cohort['observations']}
        self.fs.put(self.paths['success'], canonical(success))
        self.roles = {key: (path, self.fs.bound(path)['sha256'], module.ROLES[key][2]) for key, path in self.paths.items()}
    def loader(self):
        return module.generated_loader(IO_SOURCE, roles=self.roles, signal_root=self.signal_root,
            private_roots=(self.signal_root, self.indices, self.observations))


class InputAdapterTests(unittest.TestCase):
    def test_complete180_roles_use_real_reader_finish_and_one_shared_meter(self):
        f = Fixture()
        loader = f.loader()
        with f.fs.active(), patch.object(loader.io, 'Context', side_effect=AssertionError('native context forbidden')):
            result = loader.load()
        self.assertEqual(set(result), {'blobs', 'member_blobs'})
        self.assertEqual(set(result['blobs']), set(module.ROLES))
        self.assertEqual(result['member_blobs'], f.member_bodies)
        self.assertEqual(len(f.fs.opens), 180)
        self.assertEqual(len(set(f.fs.opens)), 180)
        self.assertEqual(len(f.fs.closes), 180)
        self.assertFalse(f.fs.fds)
        report = loader.report()
        self.assertTrue(report['completed'] and report['closed'] and report['reader_cleanup_confirmed'])
        self.assertFalse(report['failed'] or report['array_payloads_opened'] or report['participant_or_provider_invoked'])
        self.assertEqual(report['metadata_reads']['charged'], sum(len(x) for x in result['blobs'].values())+
                         sum(len(x) for x in result['member_blobs'].values()))
        self.assertEqual(report['metadata_reads']['unknown_grant_upper_bound'], 0)
        with self.assertRaises(module.InputRefusal):
            loader.load()
        with self.assertRaises(module.InputRefusal):
            module.FixedInputLoader(IO_SOURCE+b'changed')
    def test_read_failure_preserves_unknown_grant_and_prevents_retry(self):
        f = Fixture()
        loader = f.loader()
        f.fs.fail_read = str(f.paths['key'])
        with f.fs.active():
            with self.assertRaisesRegex(OSError, 'generated interrupted read'):
                loader.load()
            opened = list(f.fs.opens)
            with self.assertRaises(module.InputRefusal):
                loader.load()
            self.assertEqual(f.fs.opens, opened)
        self.assertTrue(loader.report()['failed'])
        self.assertEqual(loader.report()['metadata_reads']['unknown_grant_upper_bound'], 32)
        self.assertFalse(f.fs.fds)
    def test_small_real_generated_file_hash_identity_and_EOF_headroom(self):
        # At most4 bytes of generated file payload are written; no actual source
        # roles are used. Failed reads are not refunded or retried in a session.
        with tempfile.TemporaryDirectory(prefix='generated-input-', dir=str(HERE.parent/'evidence')) as folder:
            path = Path(folder)/'tiny.json'
            path.write_bytes(b'{}\n')
            path.chmod(0o600)
            for delta, wanted in ((0, hashlib.sha256(b'{}\n').hexdigest()),
                                  (1, hashlib.sha256(b'{}\n').hexdigest()), (1, 'f'*64)):
                loader = module.FixedInputLoader(IO_SOURCE)
                loader.scope = 'generated_only'
                loader.private_roots = ()
                loader.roles = {'cohort': (path, wanted, 3)}
                loader.meter = loader.io.Meter(3+delta)
                loader.started = True
                if delta == 0:
                    with self.assertRaisesRegex(module.InputRefusal, 'EOF headroom'):
                        loader._read('cohort')
                    self.assertEqual(loader.report()['metadata_reads']['known'], 0)
                elif wanted == 'f'*64:
                    with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                        loader._read('cohort')
                    self.assertTrue(loader.report()['failed'])
                else:
                    self.assertEqual(loader._read('cohort'), b'{}\n')
                    self.assertEqual(loader.report()['metadata_reads']['charged'], 3)


if __name__ == '__main__':
    unittest.main()
