"""Generated filesystem/control cases; no Docker, Linux procfs or neural data."""
import importlib.util
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'package/programme/n054/frozen_capture.py'
spec = importlib.util.spec_from_file_location('frozen_capture', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'namespace'
        self.source.mkdir()
        self.work = self.source / 'work'
        self.work.mkdir()
        self.dest = self.root / 'destination'
        self.dest.mkdir()
        self.proc = self.root / 'invented-proc'
        self.proc.mkdir()
        (self.proc / 'stat').write_text('123 (generated ) comm) ' + ' '.join(['S'] + ['0'] * 18 + ['19']) + '\n')
        (self.proc / 'cgroup').write_text('0::/generated-owned-group\n')
        (self.proc / 'root').symlink_to(self.source, target_is_directory=True)
        proc = m._open_dir(self.proc)
        root = os.open('root', os.O_RDONLY | os.O_DIRECTORY, dir_fd=proc)
        try:
            self.identity = m._identity(proc, root, 123)
        finally:
            os.close(root)
            os.close(proc)

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, *, cap=64, files=8, boundary=None, expected=None):
        original = m._open_dir
        def generated_dir(name, parent=None):
            return original(self.proc if name == '/proc/123' else name, parent)
        with patch.object(m.sys, 'platform', 'linux'), patch.object(m, '_open_dir', generated_dir):
            return m.capture(123, expected or self.identity, '/work', self.dest, files, cap, 5,
                             boundary or (lambda remaining: {'generated_frozen': True, 'remaining': remaining}))

    def test_complete_nested_roster_preserves_bytes_and_empty_directories(self):
        (self.work / 'sub').mkdir()
        (self.work / 'empty').mkdir()
        (self.work / 'sub/a.bin').write_bytes(b'\x00abc\xff')
        (self.work / 'zero').write_bytes(b'')
        result = self.capture()
        self.assertTrue(result['complete'] and result['fd_closure_complete'])
        self.assertEqual((result['bytes_read'], result['bytes_written'], result['files']), (5, 5, 2))
        self.assertEqual((self.dest / 'sub/a.bin').read_bytes(), b'\x00abc\xff')
        self.assertTrue((self.dest / 'empty').is_dir())
        self.assertEqual([x['path'] for x in result['roster']], ['empty', 'sub', 'sub/a.bin', 'zero'])

    def test_links_fifo_and_destination_collision_are_rejected(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'not public')
        for kind in ('symlink', 'hardlink', 'fifo', 'collision'):
            with self.subTest(kind=kind):
                item = self.work / 'item'
                if kind == 'symlink': item.symlink_to(outside)
                elif kind == 'hardlink': os.link(outside, item)
                elif kind == 'fifo': os.mkfifo(item)
                else:
                    item.write_bytes(b'new')
                    (self.dest / 'item').write_bytes(b'old')
                with self.assertRaises(m.CaptureError) as caught: self.capture()
                self.assertFalse(caught.exception.capture_observation['complete'])
                self.assertTrue(caught.exception.capture_observation['fd_closure_complete'])
                item.unlink()
                if kind == 'collision':
                    self.assertEqual((self.dest / 'item').read_bytes(), b'old')
                    (self.dest / 'item').unlink()
        self.assertEqual(outside.read_bytes(), b'not public')

    def test_byte_file_and_entry_quotas(self):
        (self.work / 'a').write_bytes(b'abc')
        with self.assertRaisesRegex(m.CaptureError, 'File byte cap'): self.capture(cap=2)
        (self.work / 'b').write_bytes(b'')
        with self.assertRaisesRegex(m.CaptureError, 'File count cap'): self.capture(files=1)
        for item in self.work.iterdir(): item.unlink()
        for item in self.dest.iterdir(): item.unlink()
        for i in range(7): (self.work / str(i)).mkdir()
        with self.assertRaisesRegex(m.CaptureError, 'Directory entry cap'): self.capture(files=1)

    def test_original_starttime_change_refuses_before_copy(self):
        (self.work / 'a').write_bytes(b'abc')
        expected = dict(self.identity, starttime=self.identity['starttime'] + 1)
        with self.assertRaisesRegex(m.CaptureError, 'Original process identity changed') as caught:
            self.capture(expected=expected)
        self.assertEqual(caught.exception.capture_observation['bytes_read'], 0)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_same_length_file_mutation_during_read_is_rejected(self):
        source = self.work / 'a'
        source.write_bytes(b'abc')
        original = os.read
        mutated = False
        def changed(fd, amount):
            nonlocal mutated
            block = original(fd, amount)
            if not mutated and block == b'abc':
                mutated = True
                source.write_bytes(b'xyz')
            return block
        with patch.object(m.os, 'read', changed):
            with self.assertRaisesRegex(m.CaptureError, 'Source file changed') as caught: self.capture()
        self.assertEqual(caught.exception.capture_observation['bytes_read'], 3)
        self.assertEqual(caught.exception.capture_observation['bytes_written'], 3)

    def test_top_level_directory_replacement_is_rejected(self):
        (self.work / 'a').write_bytes(b'abc')
        original = m._copy_tree
        def replaced(*args, **kwargs):
            result = original(*args, **kwargs)
            self.work.rename(self.source / 'old-work')
            self.work.mkdir()
            return result
        with patch.object(m, '_copy_tree', replaced):
            with self.assertRaisesRegex(m.CaptureError, 'Top-level source name changed'): self.capture()

    def test_postcopy_freeze_failure_retains_partial_cost_and_closes_all_fds(self):
        (self.work / 'a').write_bytes(b'abc')
        checks = []
        tracked = set()
        original_open, original_close = os.open, os.close
        def opened(*args, **kwargs):
            fd = original_open(*args, **kwargs); tracked.add(fd); return fd
        def closed(fd):
            original_close(fd); tracked.discard(fd)
        def boundary(remaining):
            checks.append(remaining)
            if len(checks) == 2: raise ValueError('generated unfreeze')
            return {'generated': True}
        with patch.object(m.os, 'open', opened), patch.object(m.os, 'close', closed):
            with self.assertRaisesRegex(m.CaptureError, 'generated unfreeze') as caught:
                self.capture(boundary=boundary)
        result = caught.exception.capture_observation
        self.assertFalse(result['complete'])
        self.assertTrue(result['fd_closure_complete'])
        self.assertEqual((result['bytes_read'], result['bytes_written']), (3, 3))
        self.assertEqual(tracked, set())
        self.assertLess(checks[1], checks[0])

    def test_deadline_expiry_does_not_start_boundary_callback(self):
        called = []
        with self.assertRaisesRegex(m.CaptureError, 'deadline'):
            m._boundary({'deadline': time.monotonic() - 1}, lambda remaining: called.append(remaining))
        self.assertEqual(called, [])

    def test_process_stat_uses_last_parenthesis_and_rejects_wrong_pid(self):
        raw = (self.proc / 'stat').read_bytes()
        self.assertEqual(m.parse_process_stat(raw, 123), 19)
        with self.assertRaises(m.CaptureError): m.parse_process_stat(raw, 124)
        with self.assertRaises(m.CaptureError): m.parse_process_stat(b'123 (x) S 0', 123)

    def test_failed_capture_writes_remain_in_launcher_aggregate(self):
        sys.path.insert(0, str(SOURCE.parents[1]))
        from n054.launcher import Launcher
        names = ('cpu_s', 'logical_request_bytes', 'logical_output_bytes',
                 'physical_read_bytes', 'physical_write_bytes', 'model_calls', 'tokens',
                 'unknown_model_counter_count', 'unknown_cpu_jobs')
        launcher = SimpleNamespace(totals={**dict.fromkeys(names, 0), 'unknown_model_counter_jobs': []})
        record = {'job': 'generated', 'outputs': [], 'control_namespace_written_bytes': 11,
                  'control_stream_bytes': 3, 'control_namespace_read_bytes': 13}
        Launcher._charge(launcher, record)
        self.assertEqual(launcher.totals['logical_output_bytes'], 14)
        self.assertEqual(launcher.totals['logical_request_bytes'], 13)
        record.update(outputs=[{'bytes': 7}], stdout={'bytes': 2}, stderr={'bytes': 1})
        Launcher._charge(launcher, record)
        self.assertEqual(launcher.totals['logical_output_bytes'], 28)

    def test_source_path_is_fixed(self):
        with self.assertRaisesRegex(m.CaptureError, 'Fixed tmpfs'):
            m.capture(123, self.identity, '/work/../private', self.dest, 8, 64, 5, lambda x: {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
