"""Generated provider metadata only; no daemon, native runtime or scientific data."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transport import bounds, provider
from transport.engine import encoded, parse, pin


class TransportPublicModesTests(unittest.TestCase):
    def test_provider_public_metadata_under_private_umask(self):
        with tempfile.TemporaryDirectory(prefix='osl-public-modes-') as temporary:
            root = Path(temporary).resolve()
            control_root, quarantine_root = root / 'control', root / 'quarantine'
            for directory in (control_root, quarantine_root):
                directory.mkdir(mode=0o700)
            # Current pins authenticate the exact generated seven-file source copy.
            # Retained historical manifests are deliberately not rewritten.
            source = root / 'engine-source'
            source.mkdir(mode=0o700)
            source_files = {}
            for name in sorted(provider.ENGINE_FILES):
                raw = (Path(provider.__file__).parent / name).read_bytes()
                (source / name).write_bytes(raw)
                source_files[name] = pin(raw)
            source_raw = (Path(provider.__file__).parent / 'SOURCE_MANIFEST.json').read_bytes()
            self.assertEqual(parse(source_raw),
                             {'schema': 'osl_transport_source_manifest_v1',
                              'files': source_files})
            (source / 'SOURCE_MANIFEST.json').write_bytes(source_raw)
            program = root / 'generated-program.py'
            program_raw = b'# Generated inert metadata fixture.\n'
            program.write_bytes(program_raw)
            program.chmod(0o444)
            mounts = {'/program.py': {'path': str(program), 'kind': 'file',
                                      'purpose': 'program',
                                      'files': {program.name: pin(program_raw)}}}
            now = time.monotonic()
            request = {
                'schema': 'osl_owned_phase_request_v1', 'phase_id': 'mode-control',
                'action': 'report', 'role': 'operator', 'image': 'sha256:' + '1' * 64,
                'command': ['/usr/local/bin/python', '-I', '-B', '/program.py'],
                'workdir': '/work', 'source': pin(program_raw),
                'clock': {'origin': now, 'phase_deadline': now + 60},
                'resources': {
                    'setup_seconds': 5, 'producer_seconds': 5,
                    'capture_seconds': 5, 'cleanup_seconds': 5,
                    'memory_bytes': 134217728, 'cpu_nanos': 1000000000,
                    'pids': 16, 'scratch_bytes': 4096, 'max_files': 2,
                    'max_directories': 1, 'max_file_bytes': 4096,
                    'max_output_bytes': 8192, 'manifest_bytes': 4096,
                    'max_cli_calls': 32, 'max_cli_bytes': 262144,
                    'inventory_bytes': 4096, 'source_read_bytes': 1048576,
                    'host_write_bytes': 1048576},
                'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
            exposure = {
                'schema': 'osl_transport_exposure_v1',
                **{key: request[key] for key in ('role', 'image', 'source', 'command')},
                'mounts': bounds.mount_identity(mounts),
                'approved_image_inventory_sha256': '2' * 64,
                'boundary_audit': pin(b'generated-boundary'),
                'role_boundary_verified': True}
            exposure_raw = encoded(exposure)
            exposure_path = root / 'generated-exposure.json'
            exposure_path.write_bytes(exposure_raw)
            request['exposure'] = pin(exposure_raw)
            # The actual provider must stop at its existing socket-kind guard,
            # after both public publications and before its first CLI call.
            socket_path = root / 'not-a-socket'
            socket_path.write_bytes(b'generated non-socket fixture\n')
            instance = provider.Provider(
                control_root, quarantine_root, root / 'unused-docker', socket_path,
                pin(source_raw), {pin(exposure_raw)['sha256']: exposure_path},
                1048576, 1048576)
            instance.source_root = source
            control = control_root / request['phase_id']
            expected = {
                'REQUEST.json': encoded(request),
                'POLICY.json': encoded({
                    'schema': 'osl_holder_policy_v1', 'phase_id': request['phase_id'],
                    'role': request['role'], 'file_cap': 4096, 'total_cap': 8192,
                    'files': 2, 'directories': 1})}
            real_write, real_fchmod = os.write, os.fchmod
            promotions = []

            def short_write(fd, raw):
                return real_write(fd, raw[:7])

            def complete_public_fd(fd, mode):
                identity = os.fstat(fd)
                matches = [name for name in expected
                           if (control / name).exists()
                           and (control / name).stat().st_ino == identity.st_ino
                           and (control / name).stat().st_dev == identity.st_dev]
                self.assertEqual(len(matches), 1)
                name = matches[0]
                self.assertEqual(mode, 0o444)
                self.assertEqual(identity.st_size, len(expected[name]))
                self.assertEqual((control / name).read_bytes(), expected[name])
                promotions.append(name)
                real_fchmod(fd, mode)

            prior_umask = os.umask(0o077)
            try:
                with mock.patch.object(bounds.os, 'write', side_effect=short_write), \
                        mock.patch.object(bounds.os, 'fchmod', side_effect=complete_public_fd), \
                        mock.patch.object(provider.Docker, '__call__',
                                          side_effect=AssertionError('Daemon call reached')) as daemon:
                    result = instance.execute_phase(request, mounts, now + 60,
                                                    lambda name, value: None)
                daemon.assert_not_called()
            finally:
                os.umask(prior_umask)
            for name, raw in expected.items():
                file = control / name
                self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o444, name)
                self.assertEqual(file.read_bytes(), raw)
                bounds.native_readable(file.stat())
            self.assertEqual(promotions, ['REQUEST.json', 'POLICY.json'])
            self.assertEqual(result['receipt']['status'], 'failed')
            self.assertEqual(result['receipt']['error']['message'],
                             'Existing local Unix daemon socket')
            self.assertEqual(result['receipt']['retired_resources'], [])
            self.assertEqual(result['receipt']['command_metadata'], [])
            published = list(control.iterdir())
            self.assertEqual(len(published), 6)
            for file in published:
                if file.name not in expected:
                    self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600, file.name)
            for directory in (root, control_root, quarantine_root, control,
                              quarantine_root / request['phase_id']):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(program.read_bytes(), program_raw)
            self.assertEqual(stat.S_IMODE(program.stat().st_mode), 0o444)
            self.assertEqual(result['receipt_pin'], pin((control / 'RECEIPT.json').read_bytes()))
            written = sum(file.stat().st_size for file in published)
            self.assertEqual(result['final_transport_counters']['write_bytes'], written)
            self.assertEqual(result['final_transport_counters']['write_reserved_bytes'], written)
            self.assertEqual(instance.write_used, written)


if __name__ == '__main__':
    unittest.main(verbosity=2)
