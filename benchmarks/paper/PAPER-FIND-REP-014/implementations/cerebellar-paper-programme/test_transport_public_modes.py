"""Generated publication controls; no Docker, native execution or scientific data."""
from contextlib import contextmanager
from pathlib import Path
import os
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from transport import bounds, holder, provider
from transport.engine import encoded, parse, pin


@contextmanager
def restrictive_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


class PublicPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='public-mode-control-', dir=HERE)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)

    def meter(self, write_limit=1048576):
        return bounds.Meter(1048576, write_limit, time.monotonic() + 30)

    def mode(self, file):
        return stat.S_IMODE(file.stat().st_mode)

    def test_actual_provider_publications_under_umask_077(self):
        # Match the current controller/supervisor selection: the executable
        # inventory supplies the transport pin, then real engine_auth reads
        # the current SOURCE_MANIFEST and authenticates every engine member.
        executable = parse((HERE / 'EXECUTABLE_SOURCE_MANIFEST.json').read_bytes())
        engine_row = next(row for row in executable['files']
                          if row['path'] == 'transport/SOURCE_MANIFEST.json')
        engine_pin = {key: engine_row[key] for key in ('bytes', 'sha256')}
        control, quarantine = self.root / 'control', self.root / 'quarantine'
        control.mkdir(mode=0o700)
        quarantine.mkdir(mode=0o700)
        input_file = self.root / 'generated-input.json'
        input_raw = encoded({'generated': True})
        input_file.write_bytes(input_raw)
        input_file.chmod(0o444)
        mounts = {'/input.json': {'path': str(input_file), 'kind': 'file',
                  'purpose': 'input', 'files': {input_file.name: pin(input_raw)}}}
        now = time.monotonic()
        resources = dict(setup_seconds=5, producer_seconds=5, capture_seconds=5,
                         cleanup_seconds=5, memory_bytes=134217728, cpu_nanos=1000000000,
                         pids=64, scratch_bytes=4096, max_files=2, max_directories=1,
                         max_file_bytes=4096, max_output_bytes=8192, manifest_bytes=4096,
                         max_cli_calls=1, max_cli_bytes=131072, inventory_bytes=4096,
                         source_read_bytes=1048576, host_write_bytes=1048576)
        request = {'schema': 'paper_i_owned_phase_request_v1', 'phase_id': 'generated-mode',
                   'action': 'fit', 'role': 'A', 'image': 'sha256:' + '1' * 64,
                   'command': ['/generated-never-executed'], 'workdir': '/work',
                   'source': pin(b'generated-source'),
                   'clock': {'origin': now, 'phase_deadline': now + 60},
                   'resources': resources, 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        exposure = {'schema': 'osl_transport_exposure_v1',
                    **{key: request[key] for key in ('role', 'image', 'source', 'command')},
                    'mounts': bounds.mount_identity(mounts),
                    'approved_image_inventory_sha256': '2' * 64,
                    'boundary_audit': pin(b'generated-control-only'), 'role_boundary_verified': True}
        exposure_raw = encoded(exposure)
        exposure_file = self.root / 'generated-exposure.json'
        exposure_file.write_bytes(exposure_raw)
        request['exposure'] = pin(exposure_raw)
        # A regular file intentionally fails the socket gate after publication.
        # The additional call trap prevents any external command if that changes.
        fake_socket = self.root / 'not-a-socket'
        fake_socket.write_bytes(b'generated')
        transport = provider.Provider(control, quarantine, self.root / 'no-docker', fake_socket,
                                      engine_pin, {pin(exposure_raw)['sha256']: exposure_file},
                                      1048576, 1048576)
        journal = []
        with restrictive_umask(), patch.object(provider.Docker, '__call__',
                side_effect=AssertionError('External execution forbidden')) as docker_call:
            result = transport.execute_phase(request, mounts, now + 60,
                                             lambda name, value: journal.append((name, value)))
        docker_call.assert_not_called()
        receipt = result['receipt']
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['error']['message'], 'Existing local Unix daemon socket')
        self.assertEqual(receipt['command_metadata'], [])
        self.assertFalse(receipt['scientific_qualification'])
        phase = control / request['phase_id']
        expected_policy = {'schema': 'osl_holder_policy_v1', 'phase_id': request['phase_id'],
                           'role': 'A', 'file_cap': 4096, 'total_cap': 8192,
                           'files': 2, 'directories': 1}
        for name, raw in (('REQUEST.json', encoded(request)), ('POLICY.json', encoded(expected_policy))):
            file = phase / name
            self.assertEqual(file.read_bytes(), raw)
            self.assertEqual(self.mode(file), 0o444)
            bounds.native_readable(file.stat())
        self.assertEqual(holder.load_policy(phase / 'POLICY.json',
                         pin(encoded(expected_policy))['sha256']), expected_policy)
        self.assertEqual(pin((phase / 'RECEIPT.json').read_bytes()), result['receipt_pin'])
        private = [file for file in phase.iterdir() if file.name not in ('REQUEST.json', 'POLICY.json')]
        self.assertEqual(len(private), 4)  # ownership, two journals, receipt
        self.assertTrue(all(self.mode(file) == 0o600 for file in private))
        for directory in (self.root, control, quarantine, phase, quarantine / request['phase_id']):
            self.assertEqual(self.mode(directory), 0o700)
        total = sum(file.stat().st_size for file in phase.iterdir())
        counters = result['final_transport_counters']
        self.assertEqual(counters['write_bytes'], total)
        self.assertEqual(counters['write_reserved_bytes'], total)
        self.assertEqual(transport.write_used, total)
        self.assertEqual([name for name, _ in journal], ['OWNERSHIP', 'PHASE-CLOSURE'])

    def test_public_mode_is_set_on_owned_fd_after_all_short_writes(self):
        file, raw, meter = self.root / 'public.json', b'generated-public-body' * 4, self.meter()
        original_write, original_fchmod, original_fsync = os.write, os.fchmod, os.fsync
        writes, promotions, sync_modes = [], [], []

        def short_write(fd, chunk):
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o400)
            count = original_write(fd, chunk[:7])
            writes.append(count)
            return count

        def promote(fd, mode):
            self.assertEqual(sum(writes), len(raw))
            self.assertEqual((os.fstat(fd).st_dev, os.fstat(fd).st_ino),
                             (file.stat().st_dev, file.stat().st_ino))
            promotions.append(mode)
            original_fchmod(fd, mode)

        def sync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                sync_modes.append(stat.S_IMODE(os.fstat(fd).st_mode))
            original_fsync(fd)

        with restrictive_umask(), patch.object(bounds.os, 'write', short_write), \
                patch.object(bounds.os, 'fchmod', promote), patch.object(bounds.os, 'fsync', sync):
            result = bounds.publish(file, raw, meter, mode=0o444)
        self.assertEqual(result, pin(raw))
        self.assertEqual(file.read_bytes(), raw)
        self.assertEqual(promotions, [0o444])
        self.assertEqual(sync_modes, [0o444])
        self.assertGreater(len(writes), 1)
        self.assertEqual(meter.write_bytes, meter.write_reserved_bytes)
        self.assertEqual(meter.write_bytes, len(raw))

    def test_private_and_other_modes_remain_umask_limited(self):
        with restrictive_umask(), patch.object(bounds.os, 'fchmod') as chmod:
            for requested in (0o600, 0o640):
                file = self.root / ('private-' + str(requested))
                bounds.publish(file, b'private', self.meter(), mode=requested)
                self.assertEqual(self.mode(file), 0o600)
            bounds.publish(self.root / 'default-private', b'private', self.meter())
        chmod.assert_not_called()
        self.assertEqual(self.mode(self.root / 'default-private'), 0o600)
        self.assertEqual(self.mode(self.root), 0o700)

    def test_existing_file_and_symlink_are_preserved(self):
        file = self.root / 'existing'
        file.write_bytes(b'original')
        file.chmod(0o600)
        link = self.root / 'link'
        link.symlink_to(file)
        with patch.object(bounds.os, 'fchmod') as chmod:
            with self.assertRaises(FileExistsError):
                bounds.publish(file, b'replacement', self.meter(), mode=0o444)
            with self.assertRaisesRegex(ValueError, 'unlinked canonical path'):
                bounds.publish(link, b'replacement', self.meter(), mode=0o444)
        chmod.assert_not_called()
        self.assertEqual(file.read_bytes(), b'original')
        self.assertEqual(self.mode(file), 0o600)
        self.assertTrue(link.is_symlink())

    def test_write_ceiling_refuses_before_publication(self):
        file, meter = self.root / 'over-budget', self.meter(write_limit=1)
        with patch.object(bounds.os, 'fchmod') as chmod:
            with self.assertRaisesRegex(ValueError, 'Transport write ceiling'):
                bounds.publish(file, b'too large', meter, mode=0o444)
        chmod.assert_not_called()
        self.assertFalse(file.exists())
        self.assertEqual(meter.write_bytes, 0)
        self.assertEqual(meter.write_reserved_bytes, 0)

    def test_incomplete_write_never_promotes_and_removes_owned_file(self):
        file, meter = self.root / 'incomplete', self.meter()
        with patch.object(bounds.os, 'write', return_value=0), \
                patch.object(bounds.os, 'fchmod') as chmod:
            with self.assertRaisesRegex(ValueError, 'Checked complete write'):
                bounds.publish(file, b'body', meter, mode=0o444)
        chmod.assert_not_called()
        self.assertFalse(file.exists())
        self.assertEqual(meter.write_bytes, 0)
        self.assertEqual(meter.write_reserved_bytes, 4)

    def test_mode_failure_preserves_primary_and_closes_and_removes_owned_file(self):
        file, meter, failed_fd = self.root / 'mode-failure', self.meter(), []
        failure = OSError('generated fchmod failure')

        def fail(fd, mode):
            self.assertEqual(meter.write_bytes, 4)
            failed_fd.append(fd)
            raise failure

        with patch.object(bounds.os, 'fchmod', fail):
            with self.assertRaises(OSError) as caught:
                bounds.publish(file, b'body', meter, mode=0o444)
        self.assertIs(caught.exception, failure)
        self.assertFalse(file.exists())
        with self.assertRaises(OSError):
            os.fstat(failed_fd[0])
        self.assertEqual(meter.write_bytes, meter.write_reserved_bytes)


if __name__ == '__main__':
    unittest.main()
