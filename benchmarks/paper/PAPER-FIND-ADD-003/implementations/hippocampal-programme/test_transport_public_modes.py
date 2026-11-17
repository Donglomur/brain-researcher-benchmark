"""Bounded generated controls for the owned hippocampal public publisher.

Generated filesystem fixtures only. No Docker, native, or scientific run.
The provider runs to its intentional absent-socket boundary after publication.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parent / 'transport'
spec = importlib.util.spec_from_file_location('hippocampal_mode_transport', SOURCE / '__init__.py',
                                             submodule_search_locations=[str(SOURCE)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
bounds = sys.modules[spec.name + '.bounds']
provider = sys.modules[spec.name + '.provider']
engine = sys.modules[spec.name + '.engine']
holder_spec = importlib.util.spec_from_file_location('hippocampal_mode_holder', SOURCE / 'holder.py')
holder = importlib.util.module_from_spec(holder_spec)
holder_spec.loader.exec_module(holder)


@contextlib.contextmanager
def umask(value):
    old = os.umask(value)
    try:
        yield
    finally:
        os.umask(old)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class PublicModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hippocampal-public-modes-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def meter(self, write_limit=65536, deadline=None):
        return bounds.Meter(1048576, write_limit,
                            time.monotonic() + 30 if deadline is None else deadline)

    def test_current_source_inventory_chain(self):
        manifest = json.loads((SOURCE / 'SOURCE_MANIFEST.json').read_bytes())
        self.assertEqual(manifest['files']['bounds.py'], engine.pin((SOURCE / 'bounds.py').read_bytes()))
        executable = json.loads((SOURCE.parent / 'EXECUTABLE_SOURCE_MANIFEST.json').read_bytes())
        rows = {row['path']: {'bytes': row['bytes'], 'sha256': row['sha256']} for row in executable['files']}
        self.assertEqual(len(rows), len(executable['files']))
        for name in ('transport/bounds.py', 'transport/SOURCE_MANIFEST.json'):
            self.assertEqual(rows[name], engine.pin((SOURCE.parent / name).read_bytes()))

    def test_provider_real_request_and_policy_under_umask077(self):
        # Use the selected checked-in current transport route and its real pins.
        manifest = (SOURCE / 'SOURCE_MANIFEST.json').read_bytes()
        control, quarantine = self.root / 'control', self.root / 'quarantine'
        control.mkdir(mode=0o700)
        quarantine.mkdir(mode=0o700)
        input_file = self.root / 'input.json'
        input_raw = b'{"generated":true}'
        input_file.write_bytes(input_raw)
        input_file.chmod(0o444)
        mounts = {'/input.json': {'path': str(input_file), 'kind': 'file',
                  'purpose': 'input', 'files': {'input.json': engine.pin(input_raw)}}}
        now = time.monotonic()
        resources = {key: 1 for key in provider.validate_request.__globals__['RESOURCE_KEYS']}
        resources.update(setup_seconds=10, producer_seconds=10, capture_seconds=10,
                         cleanup_seconds=10, memory_bytes=134217728, cpu_nanos=1000000000,
                         pids=64, scratch_bytes=4096, max_files=4, max_directories=2,
                         max_file_bytes=65536, max_output_bytes=65536, manifest_bytes=4096,
                         max_cli_calls=32, max_cli_bytes=262144, inventory_bytes=4096,
                         source_read_bytes=1048576, host_write_bytes=262144)
        request = {'schema': 'h_owned_phase_request_v1', 'phase_id': 'generated-mode-control',
                   'action': 'report', 'role': 'operator', 'image': 'sha256:' + 'a' * 64,
                   'command': ['/generated/no-execution'], 'workdir': '/work',
                   'source': engine.pin(b'generated source'),
                   'clock': {'origin': now, 'phase_deadline': now + 90},
                   'resources': resources, 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        exposure = {'schema': 'h_transport_exposure_v1',
                    **{key: request[key] for key in ('role', 'image', 'source', 'command')},
                    'mounts': bounds.mount_identity(mounts),
                    'approved_image_inventory_sha256': 'b' * 64,
                    'boundary_audit': engine.pin(b'generated audit'), 'role_boundary_verified': True}
        exposure_raw = engine.encoded(exposure)
        exposure_file = self.root / 'exposure.json'
        exposure_file.write_bytes(exposure_raw)
        request['exposure'] = engine.pin(exposure_raw)
        p = provider.Provider(control, quarantine, self.root / 'no-docker',
                              self.root / 'absent.socket', engine.pin(manifest),
                              {request['exposure']['sha256']: str(exposure_file)},
                              1048576, 262144)
        parents = {path: mode(path) for path in (self.root, control, quarantine)}
        events = []
        with umask(0o077), patch.object(engine.Docker, '__call__',
                                      side_effect=AssertionError('Docker is forbidden')) as cli:
            result = p.execute_phase(request, mounts, now + 90,
                                     lambda name, row: events.append(name))
        cli.assert_not_called()
        receipt = result['receipt']
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['error']['type'], 'FileNotFoundError')
        self.assertEqual(receipt['command_metadata'], [])
        self.assertEqual(events, ['OWNERSHIP', 'PHASE-CLOSURE'])
        phase = control / request['phase_id']
        self.assertEqual((phase / 'REQUEST.json').read_bytes(), engine.encoded(request))
        public = ['REQUEST.json', 'POLICY.json']
        self.assertEqual({name: mode(phase / name) for name in public},
                         {name: 0o444 for name in public})
        for name in public:
            bounds.native_readable((phase / name).stat())
        policy_path = phase / 'POLICY.json'
        policy = holder.load_policy(policy_path, hashlib.sha256(policy_path.read_bytes()).hexdigest())
        self.assertEqual(policy, {'schema': 'h_holder_policy_v1', 'phase_id': request['phase_id'],
                                 'role': 'operator', 'file_cap': 65536, 'total_cap': 65536,
                                 'files': 4, 'directories': 2})
        self.assertEqual({path.name: mode(path) for path in phase.iterdir() if path.name not in public},
                         {'OWNERSHIP.json': 0o600, '000000-OWNERSHIP.json': 0o600,
                          '000001-PHASE-CLOSURE.json': 0o600, 'RECEIPT.json': 0o600})
        self.assertEqual(mode(phase), 0o700)
        self.assertEqual(mode(quarantine / request['phase_id']), 0o700)
        self.assertEqual(parents, {path: mode(path) for path in parents})
        self.assertEqual(mode(input_file), 0o444)
        self.assertLess(result['final_transport_counters']['write_reserved_bytes'], 262144)

    def test_public_fd_mode_after_complete_short_writes_before_fsync(self):
        target, raw, meter = self.root / 'public.json', b'complete short-write payload', self.meter()
        real_write, real_fchmod, real_fsync = os.write, os.fchmod, os.fsync
        events = []
        def short_write(fd, data):
            count = real_write(fd, data[:3])
            events.append(('write', count))
            return count
        def chmod(fd, requested):
            self.assertEqual(os.fstat(fd).st_ino, target.stat().st_ino)
            self.assertEqual(os.fstat(fd).st_size, len(raw))
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o400)
            events.append(('fchmod', requested))
            return real_fchmod(fd, requested)
        def fsync(fd):
            events.append(('fsync', stat.S_ISREG(os.fstat(fd).st_mode)))
            return real_fsync(fd)
        with umask(0o077), patch.object(os, 'write', short_write), patch.object(os, 'fchmod', chmod), \
                patch.object(os, 'fsync', fsync), patch.object(os, 'chmod', side_effect=AssertionError('path chmod forbidden')):
            got = bounds.publish(target, raw, meter, mode=0o444)
        self.assertEqual(got, engine.pin(raw))
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(mode(target), 0o444)
        self.assertEqual(events[-3:], [('fchmod', 0o444), ('fsync', True), ('fsync', False)])
        self.assertGreater(sum(event[0] == 'write' for event in events), 1)
        self.assertEqual((meter.write_bytes, meter.write_reserved_bytes), (len(raw), len(raw)))

    def test_private_modes_preserve_umask_and_parent(self):
        for index, (requested, mask, expected) in enumerate(((0o600, 0o077, 0o600),
                                                           (0o640, 0o077, 0o600),
                                                           (0o600, 0o777, 0o000))):
            target = self.root / ('private-' + str(index))
            with umask(mask), patch.object(os, 'fchmod', side_effect=AssertionError('private mode widened')):
                bounds.publish(target, b'private', self.meter(), mode=requested)
            self.assertEqual(mode(target), expected)
        self.assertEqual(mode(self.root), 0o700)

    def test_existing_file_and_symlink_remain_unchanged(self):
        existing, link = self.root / 'existing', self.root / 'link'
        existing.write_bytes(b'keep')
        existing.chmod(0o600)
        link.symlink_to(existing)
        for target, error in ((existing, FileExistsError), (link, ValueError)):
            with patch.object(os, 'fchmod', side_effect=AssertionError('unowned fd')), self.assertRaises(error):
                bounds.publish(target, b'replacement', self.meter(), mode=0o444)
        self.assertEqual(existing.read_bytes(), b'keep')
        self.assertEqual(mode(existing), 0o600)
        self.assertTrue(link.is_symlink())

    def test_budget_and_deadline_reject_before_creation(self):
        for index, meter in enumerate((self.meter(write_limit=1), self.meter(deadline=time.monotonic() - 1))):
            target = self.root / ('rejected-' + str(index))
            with self.assertRaises(ValueError):
                bounds.publish(target, b'too long', meter, mode=0o444)
            self.assertFalse(target.exists())

    def test_incomplete_write_removes_owned_file_without_publication(self):
        target, meter, primary = self.root / 'partial', self.meter(), OSError('generated write failure')
        actual_write = os.write
        calls = []
        def fail_after_prefix(fd, data):
            if calls:
                raise primary
            calls.append(fd)
            return actual_write(fd, data[:3])
        with patch.object(os, 'write', fail_after_prefix), \
                patch.object(os, 'fchmod', side_effect=AssertionError('partial publication')):
            with self.assertRaises(OSError) as caught:
                bounds.publish(target, b'complete payload', meter, mode=0o444)
        self.assertIs(caught.exception, primary)
        self.assertFalse(target.exists())
        self.assertEqual(meter.write_bytes, 3)
        self.assertEqual(meter.write_reserved_bytes, len(b'complete payload'))

    def test_zero_write_removes_owned_file(self):
        target = self.root / 'zero-write'
        with patch.object(os, 'write', return_value=0), \
                patch.object(os, 'fchmod', side_effect=AssertionError('zero-write publication')):
            with self.assertRaisesRegex(ValueError, 'Checked complete write'):
                bounds.publish(target, b'payload', self.meter(), mode=0o444)
        self.assertFalse(target.exists())

    def test_fchmod_failure_preserves_primary_and_cleanup(self):
        target, meter, primary = self.root / 'chmod-failure', self.meter(), OSError('generated fchmod failure')
        with patch.object(os, 'fchmod', side_effect=primary):
            with self.assertRaises(OSError) as caught:
                bounds.publish(target, b'payload', meter, mode=0o444)
        self.assertIs(caught.exception, primary)
        self.assertFalse(target.exists())
        self.assertEqual((meter.write_bytes, meter.write_reserved_bytes), (7, 7))

    def test_fchmod_primary_retains_secondary_cleanup_error(self):
        target, primary = self.root / 'cleanup-failure', OSError('generated fchmod failure')
        original_unlink = Path.unlink
        def refuse_owned_unlink(path, *args, **kwargs):
            if path == target:
                raise PermissionError('generated unlink failure')
            return original_unlink(path, *args, **kwargs)
        with patch.object(os, 'fchmod', side_effect=primary), patch.object(Path, 'unlink', refuse_owned_unlink):
            with self.assertRaises(OSError) as caught:
                bounds.publish(target, b'payload', self.meter(), mode=0o444)
        self.assertIs(caught.exception, primary)
        self.assertEqual(primary.cleanup_errors[0]['action'], 'output.remove_owned')
        self.assertEqual(primary.cleanup_errors[0]['type'], 'PermissionError')
        self.assertTrue(target.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
