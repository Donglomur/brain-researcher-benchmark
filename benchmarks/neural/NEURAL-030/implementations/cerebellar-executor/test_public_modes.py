"""Generated publisher controls; no Docker, model, array or scientific execution."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HISTORICAL_PIN = {'bytes': 2295, 'sha256': 'b0cb8ef53c946ea9f4d0bddab5f6f1d7c4153a79d870a98bbb62021e7f665011'}
WRITTEN = 0


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def save(path, raw, mode=0o600):
    global WRITTEN
    WRITTEN += len(raw)
    if WRITTEN > 1024**2:
        raise AssertionError('Generated fixture write ceiling')
    path.write_bytes(raw)
    path.chmod(mode)
    return pin(raw)


class PublicModeControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural030-public-modes-')
        self.root = Path(self.temp.name).resolve()
        spec = importlib.util.spec_from_file_location('_neural030_mode_loader', HERE / 'captured_loader.py')
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        historical_raw = (HERE / 'SOURCE_MANIFEST.json').read_bytes()
        self.assertEqual(pin(historical_raw), HISTORICAL_PIN)
        historical = json.loads(historical_raw)
        files = {name: pin((HERE / name).read_bytes()) for name in loader.MEMBERS}
        self.current = {'schema': 'neural030_current_executor_source_v1', 'files': files,
                        'predecessor': {'path': 'SOURCE_MANIFEST.json', **HISTORICAL_PIN},
                        'scientific_qualification': False, 'native_qualification': False,
                        'changed_files': sorted(name for name in files if files[name] != historical['files'][name])}
        current_path = self.root / 'CURRENT.json'
        current_pin = save(current_path, encoded(self.current))
        # This generated descriptor is only a source-test operand. The production
        # entry/current pins are separately adopted by the integration owner.
        self.context = loader.load(HERE, current_pin, current_path, HISTORICAL_PIN)
        self.bounds = self.context.module('vendor_transport.bounds')
        self.provider = self.context.module('vendor_transport.provider')
        self.holder = self.context.module('vendor_transport.holder')

    def tearDown(self):
        self.context.close()
        self.temp.cleanup()

    def test_public_finalization_follows_complete_partial_writes(self):
        global WRITTEN
        body = b'generated public metadata with several partial writes\n'
        destination = self.root / 'PUBLIC.json'
        meter = self.bounds.Meter(1024, 1024, time.monotonic() + 10)
        real_write, real_fchmod = os.write, os.fchmod
        observed = []

        def partial(fd, data):
            return real_write(fd, data[:7])

        def finalize(fd, mode):
            before = os.fstat(fd)
            self.assertTrue(stat.S_ISREG(before.st_mode))
            self.assertEqual(before.st_size, len(body))
            self.assertEqual(stat.S_IMODE(before.st_mode), 0o400)
            self.assertEqual(destination.read_bytes(), body)
            self.assertEqual(mode, 0o444)
            observed.append(before.st_size)
            real_fchmod(fd, mode)

        old = os.umask(0o077)
        try:
            with patch.object(self.bounds.os, 'write', side_effect=partial), \
                 patch.object(self.bounds.os, 'fchmod', side_effect=finalize):
                self.assertEqual(self.bounds.publish(destination, body, meter, mode=0o444), pin(body))
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(old)
            WRITTEN += meter.write_bytes
        self.assertEqual(observed, [len(body)])
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o444)
        self.assertEqual(meter.write_bytes, len(body))

    def test_private_modes_unchanged_and_no_public_finalization(self):
        global WRITTEN
        meter = self.bounds.Meter(1024, 1024, time.monotonic() + 10)
        old = os.umask(0o077)
        try:
            with patch.object(self.bounds.os, 'fchmod', side_effect=AssertionError('Private mode widened')):
                self.bounds.publish(self.root / 'PRIVATE.json', b'private', meter)
                self.bounds.publish(self.root / 'PRIVATE_READONLY.json', b'readonly', meter, mode=0o400)
        finally:
            os.umask(old)
            WRITTEN += meter.write_bytes
        self.assertEqual(stat.S_IMODE((self.root / 'PRIVATE.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / 'PRIVATE_READONLY.json').stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    def test_failed_public_finalization_removes_owned_output(self):
        global WRITTEN
        meter = self.bounds.Meter(1024, 1024, time.monotonic() + 10)
        output = self.root / 'FAILED.json'
        old = os.umask(0o077)
        try:
            with patch.object(self.bounds.os, 'fchmod', side_effect=OSError('generated chmod refusal')):
                with self.assertRaisesRegex(OSError, 'generated chmod refusal'):
                    self.bounds.publish(output, b'complete before refusal', meter, mode=0o444)
        finally:
            os.umask(old)
            WRITTEN += meter.write_bytes
        self.assertFalse(output.exists())
        self.assertEqual(meter.write_bytes, len(b'complete before refusal'))

    def test_actual_provider_request_policy_before_native_refusal(self):
        global WRITTEN
        control, quarantine = self.root / 'control', self.root / 'capture'
        control.mkdir(mode=0o700)
        quarantine.mkdir(mode=0o700)
        source_pin = pin(b'generated source identity')
        input_path = self.root / 'input.txt'
        input_pin = save(input_path, b'generated public input', 0o444)
        mounts = {'/input.txt': {'path': str(input_path), 'kind': 'file', 'purpose': 'input',
                                 'files': {input_path.name: input_pin}}}
        now = time.monotonic()
        limits = dict(setup_seconds=10, producer_seconds=3, capture_seconds=2, cleanup_seconds=2,
            memory_bytes=134217728, cpu_nanos=1000000000, pids=32, scratch_bytes=4096,
            max_files=4, max_directories=4, max_file_bytes=4096, max_output_bytes=8192,
            manifest_bytes=2048, max_cli_calls=16, max_cli_bytes=32768, inventory_bytes=4096,
            source_read_bytes=1048576, host_write_bytes=131072)
        request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': 'generated-publication',
            'action': 'held_attempt', 'role': 'A', 'image': 'sha256:' + 'a' * 64,
            'command': ['/generated/never-executed'], 'workdir': '/work', 'source': source_pin,
            'clock': {'origin': now - 1, 'phase_deadline': now + 60}, 'resources': limits,
            'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'A', 'image': request['image'],
            'source': source_pin, 'command': request['command'], 'mounts': self.bounds.mount_identity(mounts),
            'approved_image_inventory_sha256': 'b' * 64, 'boundary_audit': pin(b'generated audit'),
            'role_boundary_verified': True}
        exposure_path = self.root / 'EXPOSURE.json'
        request['exposure'] = save(exposure_path, encoded(exposure))
        binary, not_socket = self.root / 'never-docker', self.root / 'not-a-socket'
        save(binary, b'never executed')
        save(not_socket, b'ordinary file intentionally refuses native boundary')

        class InertDocker:
            constructed = 0
            def __init__(self, *args, **kwargs):
                type(self).constructed += 1
                self.records, self.reaped = [], True
            def __call__(self, *args, **kwargs):
                raise AssertionError('No native dispatch permitted')

        manifest_pin = pin((HERE / 'vendor_transport/SOURCE_MANIFEST.json').read_bytes())
        actual = self.provider.Provider(control, quarantine, binary, not_socket, manifest_pin,
            {request['exposure']['sha256']: str(exposure_path)}, 1048576, 131072)
        old = os.umask(0o077)
        try:
            with patch.object(self.provider, 'Docker', InertDocker):
                result = actual.execute_phase(request, mounts, now + 60, lambda *_: None)
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(old)
            WRITTEN += actual.write_used
        self.assertEqual(InertDocker.constructed, 1)
        receipt = result['receipt']
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['error']['message'], 'Existing local Unix daemon socket')
        self.assertEqual(receipt['command_metadata'], [])
        self.assertEqual(receipt['retired_resources'], [])
        phase = control / request['phase_id']
        self.assertEqual((phase / 'REQUEST.json').read_bytes(), self.provider.encoded(request))
        policy_raw = (phase / 'POLICY.json').read_bytes()
        policy = self.holder.load_policy(str(phase / 'POLICY.json'), pin(policy_raw)['sha256'])
        self.assertEqual(policy['phase_id'], request['phase_id'])
        self.assertEqual(policy['file_cap'], limits['max_file_bytes'])
        for path in phase.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),
                             0o444 if path.name in ('REQUEST.json', 'POLICY.json') else 0o600)
        for path in (control, quarantine, phase, quarantine / request['phase_id']):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'scope': 'generated_source_and_publication_controls_only'}), flush=True)
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'generated_fixture_bytes_written': WRITTEN, 'native_runs': 0,
                          'model_runs': 0, 'authentic_array_reads': 0}), flush=True)
