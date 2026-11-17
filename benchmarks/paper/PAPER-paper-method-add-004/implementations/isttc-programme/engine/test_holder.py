"""Invented RAM filesystem controls; never start a process/container or open data.

Only this test source and holder source are read from the real filesystem.
All production capture/readiness filesystem calls below are replaced in memory.
"""
import base64
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('holder.py')
spec = importlib.util.spec_from_file_location('isttc_holder_controls_target', SOURCE)
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
OWNER = 'isttc-' + 'a' * 24 + '/holder'


class MemoryFS:
    """Tiny invented inode table; virtual large extents do not allocate data."""
    def __init__(self):
        self.nodes = {}
        self.fds = {}
        self.events = []
        self.next_fd = 10
        self.read_limit = 65536
        self.after_pread = None
        self.add('/capture', directory=True)
        self.add('/ready', directory=True, mode=0o700)

    def add(self, path, data=b'', directory=False, size=None, mode=0o600, **overrides):
        n = SimpleNamespace(st_dev=1, st_ino=len(self.nodes) + 100,
                            st_mode=(stat.S_IFDIR if directory else stat.S_IFREG) | mode,
                            st_size=(0 if directory else len(data)) if size is None else size,
                            st_nlink=2 if directory else 1, st_uid=65534, st_gid=65534,
                            st_mtime_ns=100, st_ctime_ns=100, data=data)
        for name, value in overrides.items():
            setattr(n, name, value)
        self.nodes[str(path)] = n
        return n

    def resolve(self, path, dir_fd=None):
        p = str(path)
        if dir_fd is not None:
            assert not p.startswith('/')
            p = self.fds[dir_fd]['path'] + '/' + p
        return p

    @staticmethod
    def snapshot(n):
        return SimpleNamespace(**vars(n))

    def stat(self, path, *, dir_fd=None, follow_symlinks=False):
        assert follow_symlinks is False
        p = self.resolve(path, dir_fd)
        if p not in self.nodes:
            raise FileNotFoundError(p)
        return self.snapshot(self.nodes[p])

    def open(self, path, flags, mode=0o777, *, dir_fd=None):
        p = self.resolve(path, dir_fd)
        assert flags & os.O_NOFOLLOW
        if flags & os.O_CREAT:
            assert flags & os.O_EXCL
            if p in self.nodes:
                raise FileExistsError(p)
            self.add(p, mode=mode)
        if p not in self.nodes:
            raise FileNotFoundError(p)
        n = self.nodes[p]
        if stat.S_ISLNK(n.st_mode):
            raise OSError('nofollow')
        if flags & os.O_DIRECTORY:
            assert stat.S_ISDIR(n.st_mode)
        fd = self.next_fd
        self.next_fd += 1
        self.fds[fd] = {'path': p, 'node': n, 'offset': 0}
        self.events.append(('open', p, flags))
        return fd

    def close(self, fd):
        self.events.append(('close', self.fds[fd]['path']))
        del self.fds[fd]

    def fstat(self, fd):
        return self.snapshot(self.fds[fd]['node'])

    def scandir(self, path):
        root = self.fds[path]['path'] if type(path) is int else str(path)
        entries = [SimpleNamespace(name=p[len(root) + 1:]) for p in self.nodes
                   if p.startswith(root + '/') and '/' not in p[len(root) + 1:]]
        class Scan:
            def __enter__(self): return iter(entries)
            def __exit__(self, *args): return False
        return Scan()

    def pread(self, fd, count, offset):
        self.events.append(('pread', self.fds[fd]['path'], count, offset))
        n = self.fds[fd]['node']
        body = n.data[offset:offset + min(count, self.read_limit)]
        if self.after_pread is not None:
            callback, self.after_pread = self.after_pread, None
            callback()
        return body

    def read(self, fd, count):
        slot = self.fds[fd]
        b = slot['node'].data[slot['offset']:slot['offset'] + count]
        slot['offset'] += len(b)
        return b

    def write(self, fd, body):
        n = self.fds[fd]['node']
        body = body[:17]  # exercise complete marker writes
        n.data += body
        n.st_size = len(n.data)
        self.events.append(('write', self.fds[fd]['path'], len(body)))
        return len(body)

    def fsync(self, fd):
        self.events.append(('fsync', self.fds[fd]['path']))

    def rename(self, old, new):
        self.events.append(('rename', str(old), str(new)))
        self.nodes[str(new)] = self.nodes.pop(str(old))

    def patched(self, ready=True):
        stack = ExitStack()
        for name in ('open', 'close', 'stat', 'fstat', 'scandir', 'pread', 'read', 'write', 'fsync', 'rename'):
            stack.enter_context(patch.object(H.os, name, getattr(self, name)))
        stack.enter_context(patch.object(H.Path, 'lstat', lambda p: self.stat(p)))
        if ready:
            stack.enter_context(patch.object(H, 'ready', return_value=True))
        return stack


class HolderControls(unittest.TestCase):
    def test_exact_owner_and_typed_stamp(self):
        self.assertEqual(H.owner_token(OWNER), OWNER)
        for token in ('neural033-' + 'a' * 24 + '/holder', OWNER + '/x', OWNER.upper(), True):
            with self.assertRaises(ValueError): H.owner_token(token)
        for value in ([True] + [1] * 8, [1] * 8, tuple([1] * 9), [-1] + [1] * 8):
            with self.assertRaises(ValueError): H.expected_stamp(value)

    def test_relative_name_bounds(self):
        self.assertEqual(H.names('view/nested/values.npy'), ['view', 'nested', 'values.npy'])
        for name in ('/x', '../x', 'a/../x', 'a//x', 'a/./x', '.hidden', 'x\\y', 'x' * 513,
                     '/'.join(['a'] * 9), 'x\x00y', ''):
            with self.assertRaises(ValueError): H.names(name)

    def test_flat_reference_inventory_sorted_metadata_only(self):
        fs = MemoryFS()
        fs.add('/capture/methods.json', b'{}')
        fs.add('/capture/estimates.csv', b'x\n')
        with fs.patched():
            got = H.inventory(Path('/capture'), OWNER, 'reference')
        self.assertEqual([x['name'] for x in got['files']], ['estimates.csv', 'methods.json'])
        self.assertEqual(got['total_bytes'], 4)
        self.assertEqual(got['directories'], [])
        self.assertTrue(all(set(x) == {'name', 'bytes', 'stamp'} for x in got['files']))
        self.assertFalse(any(x[0] == 'pread' for x in fs.events))
        self.assertEqual(fs.fds, {})

    def test_all_roles_are_flat_and_nonempty(self):
        for role in H.PROFILES:
            for nested in (False, True):
                fs = MemoryFS()
                if nested:
                    fs.add('/capture/view', directory=True)
                    fs.add('/capture/view/a', b'x')
                with fs.patched(), self.assertRaises(ValueError):
                    H.inventory(Path('/capture'), OWNER, role)
                self.assertEqual(fs.fds, {})

    def test_files_refuse_symlink_hardlink_special_and_wrong_owner(self):
        for updates in ({'st_mode': stat.S_IFLNK | 0o777}, {'st_nlink': 2}, {'st_uid': 0},
                        {'st_gid': 0}, {'st_mode': stat.S_IFIFO | 0o600}):
            fs = MemoryFS()
            fs.add('/capture/a', b'x', **updates)
            with fs.patched(), self.assertRaises(ValueError):
                H.inventory(Path('/capture'), OWNER, 'improvement')
            self.assertEqual(fs.fds, {})

    def test_directory_owner_and_symlink_rejected(self):
        for updates in ({'st_uid': 0}, {'st_mode': stat.S_IFLNK | 0o777}):
            fs = MemoryFS()
            fs.add('/capture/view', directory=True, **updates)
            fs.add('/capture/view/a', b'x')
            with fs.patched(), self.assertRaises(ValueError):
                H.inventory(Path('/capture'), OWNER, 'reference')
            self.assertEqual(fs.fds, {})

    def test_count_extent_total_and_directory_bounds(self):
        cases = [(role, count, extent) for role in H.PROFILES
                 for count, extent in ((3, 1), (1, 100_000_001))]
        for role, count, extent in cases:
            fs = MemoryFS()
            for i in range(count): fs.add('/capture/f' + str(i), size=extent)
            with fs.patched(), self.assertRaises(ValueError): H.inventory(Path('/capture'), OWNER, role)
            self.assertEqual(fs.fds, {})
        fs = MemoryFS()
        fs.add('/capture/d', directory=True)
        fs.add('/capture/a', b'x')
        with fs.patched(), self.assertRaises(ValueError): H.inventory(Path('/capture'), OWNER, 'reference')
        # Isolate the aggregate guard with a smaller invented profile, without allocating payload.
        fs = MemoryFS()
        fs.add('/capture/a', size=2)
        fs.add('/capture/b', size=2)
        limits = dict(H.PROFILES['reference'], total_cap=3)
        with fs.patched(), patch.object(H, 'profile', return_value=limits), self.assertRaises(ValueError):
            H.inventory(Path('/capture'), OWNER, 'reference')

    def test_exact_role_profiles_and_accepted_extent_boundaries(self):
        self.assertEqual(set(H.PROFILES), {'reproduction', 'improvement', 'reference'})
        for role, limits in H.PROFILES.items():
            self.assertEqual(limits, {'files': 2, 'directories': 1, 'file_cap': 100000000, 'total_cap': 536870912})
            fs = MemoryFS()
            for i in range(limits['files']): fs.add('/capture/f' + str(i), size=limits['file_cap'])
            with fs.patched(): got = H.inventory(Path('/capture'), OWNER, role)
            self.assertEqual(got['total_bytes'], limits['files'] * limits['file_cap'])

    def test_chunk_short_reads_and_explicit_eof(self):
        fs = MemoryFS()
        fs.read_limit = 2
        node = fs.add('/capture/a.npy', b'abcdef')
        expected = H.stamp(node)
        with fs.patched():
            got = H.chunk(Path('/capture'), OWNER, 'improvement', 'a.npy', 1, 3, expected)
            tail = H.chunk(Path('/capture'), OWNER, 'improvement', 'a.npy', 4, 9, expected)
            eof = H.chunk(Path('/capture'), OWNER, 'improvement', 'a.npy', 6, 0, expected)
        self.assertEqual(base64.b64decode(got['base64']), b'bcd')
        self.assertEqual(got['sha256'], hashlib.sha256(b'bcd').hexdigest())
        self.assertFalse(got['eof'])
        self.assertTrue(tail['eof'])
        self.assertEqual(base64.b64decode(tail['base64']), b'ef')
        self.assertEqual((eof['bytes'], eof['base64'], eof['eof']), (0, '', True))
        self.assertIn(('pread', '/capture/a.npy', 1, 6), fs.events)
        self.assertEqual(fs.fds, {})

    def test_chunk_exact_shape_and_reply_overhead(self):
        fs = MemoryFS()
        node = fs.add('/capture/a', b'x')
        with fs.patched(): got = H.chunk(Path('/capture'), OWNER, 'improvement', 'a', 0, 1, H.stamp(node))
        self.assertEqual(set(got), {'schema', 'owner', 'role', 'name', 'offset', 'bytes', 'stamp', 'eof', 'sha256', 'base64'})
        overhead = len(json.dumps(got, separators=(',', ':')).encode()) - len(got['base64'])
        self.assertLess(overhead + H.NAME_BYTES + 1024, 4096)
        self.assertEqual(4 * ((H.CHUNK_CAP + 2) // 3) + 4096, 5_596_504)

    def test_empty_file_eof_and_bool_stamp_rejection(self):
        fs = MemoryFS()
        node = fs.add('/capture/a')
        with fs.patched():
            got = H.chunk(Path('/capture'), OWNER, 'improvement', 'a', 0, 0, H.stamp(node))
        self.assertEqual((got['bytes'], got['eof'], got['sha256']), (0, True, hashlib.sha256(b'').hexdigest()))
        self.assertIn(('pread', '/capture/a', 1, 0), fs.events)
        bad = H.stamp(node)
        bad[0] = True
        with fs.patched(), self.assertRaises(ValueError):
            H.chunk(Path('/capture'), OWNER, 'improvement', 'a', 0, 0, bad)

    def test_chunk_range_types_and_cap(self):
        fs = MemoryFS()
        node = fs.add('/capture/a', b'abc')
        for offset, length in ((True, 1), (0, True), (-1, 1), (4, 1), (0, H.CHUNK_CAP + 1), (0, 0), (0, -1)):
            with fs.patched(), self.assertRaises(ValueError):
                H.chunk(Path('/capture'), OWNER, 'improvement', 'a', offset, length, H.stamp(node))
            self.assertEqual(fs.fds, {})

    def test_chunk_stale_identity_and_symlink(self):
        for updates in ({'st_ino': 999}, {'st_nlink': 2}, {'st_uid': 0}, {'st_mode': stat.S_IFLNK | 0o777}):
            fs = MemoryFS()
            node = fs.add('/capture/a', b'abc')
            expected = H.stamp(node)
            for k, v in updates.items(): setattr(node, k, v)
            with fs.patched(), self.assertRaises(ValueError):
                H.chunk(Path('/capture'), OWNER, 'improvement', 'a', 0, 3, expected)
            self.assertEqual(fs.fds, {})

    def test_chunk_short_extent_or_extra_eof_byte(self):
        for data, extent in ((b'ab', 3), (b'abcd', 3)):
            fs = MemoryFS()
            node = fs.add('/capture/a', data, size=extent)
            with fs.patched(), self.assertRaises(ValueError):
                H.chunk(Path('/capture'), OWNER, 'improvement', 'a', 0, 3, H.stamp(node))
            self.assertEqual(fs.fds, {})

    def test_chunk_detects_file_or_root_replacement(self):
        for target in ('/capture/a', '/capture'):
            fs = MemoryFS()
            node = fs.add('/capture/a', b'abc')
            fs.after_pread = lambda target=target: setattr(fs.nodes[target], 'st_ctime_ns', 101)
            with fs.patched(), self.assertRaises(ValueError):
                H.chunk(Path('/capture'), OWNER, 'reference', 'a', 0, 3, H.stamp(node))
            self.assertTrue(any(x[0] == 'pread' for x in fs.events))
            self.assertEqual(fs.fds, {})

    def test_chunk_refuses_nested_paths_even_without_inventory(self):
        fs = MemoryFS()
        fs.add('/capture/view', directory=True)
        node = fs.add('/capture/view/a', b'x')
        for role in H.PROFILES:
            with fs.patched(), self.assertRaisesRegex(ValueError, 'flat'):
                H.chunk(Path('/capture'), OWNER, role, 'view/a', 0, 1, H.stamp(node))
        self.assertEqual(fs.events, [])

    def test_inventory_final_comparison_detects_changed_file(self):
        fs = MemoryFS()
        node = fs.add('/capture/a', b'abc')
        with fs.patched():
            initial = H.inventory(Path('/capture'), OWNER, 'improvement')
            node.st_ctime_ns += 1
            final = H.inventory(Path('/capture'), OWNER, 'improvement')
        self.assertNotEqual(initial, final)

    def test_ready_missing_and_exact_owned_marker(self):
        fs = MemoryFS()
        with fs.patched(ready=False): self.assertFalse(H.ready(OWNER))
        fs.add('/ready/READY', H.marker_bytes(OWNER))
        with fs.patched(ready=False): self.assertTrue(H.ready(OWNER))
        with fs.patched(ready=False), self.assertRaises(ValueError): H.ready('isttc-' + 'b' * 24 + '/holder')
        for field, value in (('st_uid', 0), ('st_gid', 0), ('st_nlink', 2),
                             ('st_mode', stat.S_IFREG | 0o644)):
            fs = MemoryFS()
            fs.add('/ready/READY', H.marker_bytes(OWNER), **{field: value})
            with fs.patched(ready=False), self.assertRaises(ValueError): H.ready(OWNER)

    def test_publish_atomic_order_pid1_and_empty_guard(self):
        fs = MemoryFS()
        with fs.patched(ready=False), patch.object(H.os, 'getpid', return_value=1):
            H.publish_ready(Path('/capture'), OWNER)
            self.assertTrue(H.ready(OWNER))
        operations = [x[0] for x in fs.events]
        rename_at = operations.index('rename')
        self.assertEqual(operations[rename_at - 2:rename_at], ['fsync', 'close'])
        self.assertEqual(operations[rename_at + 1:rename_at + 4], ['open', 'fsync', 'close'])
        self.assertEqual(fs.nodes['/ready/READY'].data, H.marker_bytes(OWNER))
        self.assertNotIn('/ready/.pending', fs.nodes)
        for pid, occupied in ((2, None), (1, '/capture/a'), (1, '/ready/a')):
            fs = MemoryFS()
            if occupied: fs.add(occupied, b'x')
            with fs.patched(), patch.object(H.os, 'getpid', return_value=pid), self.assertRaises(ValueError):
                H.publish_ready(Path('/capture'), OWNER)
            self.assertFalse(any(x[0] == 'write' for x in fs.events))

    def test_guard_exact_memory_mounts_and_profile(self):
        fs = MemoryFS()
        values = {'memory.max': '134217728', 'memory.swap.max': '0', 'pids.max': '64', 'cpu.max': '100000 100000'}
        mounts = ('1 0 0:1 / /capture ro,noexec,nosuid,nodev - tmpfs tmpfs ro\n'
                  '2 0 0:2 / /ready rw,noexec,nosuid,nodev - tmpfs tmpfs rw\n')
        def text(path, *args, **kwargs):
            return mounts if str(path) == '/proc/self/mountinfo' else values[path.name]
        with fs.patched(), patch.object(H.os, 'getuid', return_value=65534), patch.object(H.Path, 'read_text', text), \
                patch.object(H.os, 'statvfs', side_effect=lambda p: SimpleNamespace(f_frsize=4096, f_blocks=(4096 if str(p) == '/ready' else 512 * 1024 ** 2) // 4096)):
            self.assertEqual(H.guard('improvement'), Path('/capture'))
            values['memory.max'] = '268435456'
            with self.assertRaises(ValueError): H.guard('improvement')

    def test_cli_ready_and_inventory_route_and_argument_refusal(self):
        for action in ('ready', 'inventory'):
            fs = MemoryFS()
            fs.add('/capture/a', b'x')
            out = io.StringIO()
            with fs.patched(), patch.object(H, 'guard', return_value=Path('/capture')) as guard, \
                    patch.object(sys, 'argv', ['holder.py', action, '--owner-token', OWNER, '--role', 'improvement']), \
                    patch.object(sys, 'stdout', out): H.main()
            self.assertIsInstance(json.loads(out.getvalue()), dict)
            guard.assert_called_once_with('improvement')
        with patch.object(sys, 'argv', ['holder.py', 'ready', '--owner-token', OWNER, '--role', 'improvement', '--name', 'a']), \
                patch.object(H, 'guard') as guard, self.assertRaises(ValueError): H.main()
        guard.assert_not_called()


if __name__ == '__main__':
    unittest.main()
