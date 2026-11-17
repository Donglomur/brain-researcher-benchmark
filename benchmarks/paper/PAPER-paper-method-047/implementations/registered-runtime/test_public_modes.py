"""Generated controller staging controls; no scientific or container execution."""
import base64
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / 'transitive-recovery/controller'
sys.path.insert(0, str(CONTROLLER))
import control as C
import coordinator as Q
import runtime as R


@contextmanager
def masked(mask):
    previous = os.umask(mask)
    try:
        yield
    finally:
        os.umask(previous)


class StopBeforeCase(Exception):
    pass


class PublicModeTests(unittest.TestCase):
    def test_active_local_manifest_chain_matches_current_controller(self):
        controller_manifest = C.parse((CONTROLLER / 'SOURCE_MANIFEST.json').read_bytes())
        package = HERE / 'transitive-recovery'
        manifest = C.parse((package / 'SOURCE_MANIFEST.json').read_bytes())
        components = C.parse((HERE / 'SOURCE_COMPONENTS.json').read_bytes())
        control_pin = C.pin((CONTROLLER / 'control.py').read_bytes())
        self.assertEqual(controller_manifest['runtime_files']['control.py'], control_pin)
        self.assertEqual(manifest['files']['controller/control.py'], control_pin)
        self.assertEqual(manifest['files']['controller/SOURCE_MANIFEST.json'],
                         C.pin((CONTROLLER / 'SOURCE_MANIFEST.json').read_bytes()))
        component, = components['components']
        self.assertEqual(C.only_pin(component['source_manifest']),
                         C.pin((package / 'SOURCE_MANIFEST.json').read_bytes()))
        self.assertEqual(component['source_files'], len(manifest['files']) + 1)
        self.assertEqual(component['source_bytes'], sum(row['bytes'] for row in manifest['files'].values())
                         + component['source_manifest']['bytes'])
        self.assertFalse(component['execution_selected'])
        self.assertFalse(component['native_qualification'])
        self.assertFalse(component['scientific_qualification'])

    def test_actual_controller_stages_public_sources_under_private_umask(self):
        with tempfile.TemporaryDirectory(prefix='.public-mode-', dir=HERE) as temporary:
            root = Path(temporary).resolve()
            export = root / 'export'
            (export / 'private/prepared').mkdir(parents=True)
            source_names = ('stage_view.py', 'interface.py', 'ASSETS.json',
                            'VIEW_FILES.json', 'prepared/PREPARED.json')
            lock = {'files': {}}
            for name in source_names:
                raw = b'{}\n' if name.endswith('.json') else b'# generated inert fixture\n'
                (export / 'private' / name).write_bytes(raw)
                lock['files']['private/' + name] = C.pin(raw)
            lock_raw = C.encoded(lock)
            (root / 'LOCK.json').write_bytes(lock_raw)
            bindings = {'transport_lock': {'path': 'LOCK.json', **C.pin(lock_raw)}}
            identities = [[f'generated-{n:03}', track, arm] for n in range(117)
                          for track in ('pooled', 'variant') for arm in ('A', 'B')]

            class Catalog:
                ids = range(117)

                def __init__(self, actual_export, actual_lock):
                    self.lock = actual_lock
                    self_test.assertEqual(actual_export, export)
                    self_test.assertEqual(actual_lock, lock)

                def identities(self):
                    return identities

            self_test = self
            seen = []
            ownership = SimpleNamespace(programme=lambda rows: seen.extend(rows))

            def begin(index, identity):
                self.assertEqual((index, identity), (0, identities[0]))
                raise StopBeforeCase('generated control stops before empirical staging')

            ownership.begin = begin
            programs = {}
            for arm in ('A', 'B'):
                raw = ('# generated inert program ' + arm + '\n').encode()
                p = root / (arm + '.py')
                p.write_bytes(raw)
                programs[arm] = {'path': str(p), **C.pin(raw)}
            (root / 'fixture.sock').write_bytes(b'generated inert socket stand-in\n')
            with mock.patch.object(Q.stat, 'S_ISSOCK', return_value=True):
                cfg = {
                    'schema': 'gcamp8_full117_selection_v1', 'enabled': True,
                    'task_id': C.TASK, 'source': C.pin(b'generated source selection'),
                    'programs': programs, 'authoring_receipt': {}, 'runtime_receipt': {},
                    'image': 'sha256:' + '0' * 64, 'memory_bytes': 1073741824,
                    'train_seconds': 1, 'predict_seconds': 1, 'stage_seconds': 1,
                    'grade_seconds': 1, 'other_reserved_bytes': 0,
                    'private_grading_authorized': True,
                    'exclusive_immutable_operator_storage': True,
                    'python': str(Path(sys.executable).resolve()),
                    'docker': str(Path(sys.executable).resolve()),
                    'socket': str(root / 'fixture.sock'),
                }
                selection = root / 'selection.json'
                selection.write_bytes(C.encoded(cfg))
                executor = SimpleNamespace(opaque_pin=lambda *args: None)
                transport = SimpleNamespace(strict=C.parse, Catalog=Catalog)
                prerequisites = {'executable_pins': {'python': {}, 'docker': {}}}
                output = root / 'output'
                outer = {}
                with masked(0o077), \
                     mock.patch.object(C, 'capacity'), \
                     mock.patch.object(Q, 'bootstrap', return_value=(bindings, executor, transport, None)), \
                     mock.patch.object(Q, 'attest', return_value=prerequisites), \
                     mock.patch.object(Q.signal, 'setitimer'), \
                     self.assertRaises(StopBeforeCase):
                    Q._run(root, export, selection, C.pin(selection.read_bytes()),
                           output, time.monotonic(), outer, ownership)
            self.assertEqual(seen, identities)
            self.assertEqual(outer['owned_output'], output)
            expected = {'programs/' + arm + '.py': (root / (arm + '.py')).read_bytes()
                        for arm in ('A', 'B')}
            expected.update({'source/' + name: (CONTROLLER / name).read_bytes()
                             for name in ('entry.py', 'holder.py', 'trusted_worker.py', 'CANDIDATE_ABI.md')})
            expected.update({'source/' + name: (export / 'private' / name).read_bytes()
                             for name in source_names})
            for name, raw in expected.items():
                with self.subTest(staged=name):
                    self.assertEqual((output / name).read_bytes(), raw)
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o444)
            for name in ('COMMITMENT.json', 'FAILURE.json'):
                self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o444)
            self.assertEqual(C.parse((output / 'FAILURE.json').read_bytes())['error_type'], 'StopBeforeCase')
            self.assertEqual(len(list(output.rglob('*.*'))), 13)
            for name in ('', 'programs', 'source', 'source/prepared', 'transient', 'cases', 'grades'):
                self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o700)
            self.assertFalse(any((output / 'cases').iterdir()))

    def test_complete_partial_writes_restore_mode_on_owned_fd_before_sync(self):
        for mask in (0o077, 0o022):
            with self.subTest(umask=oct(mask)), \
                 tempfile.TemporaryDirectory(prefix='.public-mode-', dir=HERE) as temporary:
                root = Path(temporary).resolve()
                p, raw = root / 'public', b'generated multi-write bytes\n'
                before = stat.S_IMODE(root.stat().st_mode)
                events = []
                real_write, real_chmod, real_sync = os.write, os.fchmod, os.fsync

                def partial(fd, view):
                    events.append(('write', os.fstat(fd).st_size))
                    return real_write(fd, view[:3])

                def chmod(fd, mode):
                    events.append(('chmod', os.fstat(fd).st_size))
                    self.assertEqual(mode, 0o444)
                    self.assertEqual(os.fstat(fd).st_ino, p.stat().st_ino)
                    self.assertEqual(os.fstat(fd).st_size, len(raw))
                    return real_chmod(fd, mode)

                def sync(fd):
                    events.append(('sync', os.fstat(fd).st_size))
                    return real_sync(fd)

                with masked(mask), mock.patch.object(C.os, 'write', side_effect=partial), \
                     mock.patch.object(C.os, 'fchmod', side_effect=chmod), \
                     mock.patch.object(C.os, 'fsync', side_effect=sync):
                    pin = C.write(p, raw)
                self.assertEqual(pin, C.pin(raw))
                self.assertEqual(p.read_bytes(), raw)
                self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o444)
                self.assertEqual(stat.S_IMODE(root.stat().st_mode), before)
                chmod_at = [i for i, event in enumerate(events) if event[0] == 'chmod']
                self.assertEqual(len(chmod_at), 1)
                self.assertTrue(all(event[0] == 'write' for event in events[:chmod_at[0]]))
                self.assertEqual([event[0] for event in events[chmod_at[0] + 1:]], ['sync', 'sync'])

    def test_failed_write_does_not_publish_permissions_or_replace_existing(self):
        with tempfile.TemporaryDirectory(prefix='.public-mode-', dir=HERE) as temporary:
            root = Path(temporary).resolve()
            p = root / 'partial'
            real_write = os.write
            calls = 0

            def partial_then_zero(fd, view):
                nonlocal calls
                calls += 1
                return real_write(fd, view[:2]) if calls == 1 else 0

            with masked(0o077), mock.patch.object(C.os, 'write', side_effect=partial_then_zero), \
                 mock.patch.object(C.os, 'fchmod') as chmod, \
                 self.assertRaisesRegex(ValueError, 'complete write'):
                C.write(p, b'generated partial bytes')
            chmod.assert_not_called()
            self.assertEqual(p.read_bytes(), b'ge')
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o400)
            with self.assertRaises(FileExistsError):
                C.write(p, b'replacement')
            self.assertEqual(p.read_bytes(), b'ge')
            link = root / 'linked'
            link.symlink_to(p)
            with self.assertRaisesRegex(ValueError, 'canonical unlinked path'):
                C.write(link, b'not allowed')
            for raw, cap in ((b'', 1), (b'12', 1)):
                with self.assertRaisesRegex(ValueError, 'bounded fresh publication'):
                    C.write(root / 'bounded', raw, cap)
            self.assertFalse((root / 'bounded').exists())

    def test_private_prediction_capture_keeps_owner_only_mode(self):
        with tempfile.TemporaryDirectory(prefix='.public-mode-', dir=HERE) as temporary:
            p = Path(temporary).resolve() / 'prediction.json'
            raw = b'{"generated":true}\n'
            response = C.encoded({'name': 'prediction.json', 'offset': 0,
                                  'bytes': len(raw), 'base64': base64.b64encode(raw).decode()})
            executor = SimpleNamespace(call=lambda *args: response, parse=C.parse)
            with masked(0o077), mock.patch.object(R.os, 'fchmod') as chmod:
                result = R.capture_prediction(executor, None, {'id': 'generated'},
                                              C.pin(raw), p, time.monotonic() + 10)
            chmod.assert_not_called()
            self.assertEqual(result, C.pin(raw))
            self.assertEqual(p.read_bytes(), raw)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o400)

    def test_unprivileged_launcher_and_entry_keep_program_route(self):
        executor = SimpleNamespace(LABEL='generated', mounts_argv=lambda mounts: [])
        item = {'name': 'generated', 'owner': 'generated'}
        for role, script in (('holder', '/trusted/holder.py'), ('candidate', '/entry.py')):
            args = R.create_args(executor, item, role, {}, 1073741824, 'generated', 'train')
            self.assertEqual(args[args.index('--user') + 1], '65534:65534')
            self.assertIn(script, args)
        spec = importlib.util.spec_from_file_location('generated_entry_control', CONTROLLER / 'entry.py')
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        for phase in ('train', 'predict'):
            with mock.patch.object(entry, 'observed'), \
                 mock.patch.object(entry.sys, 'argv', ['entry.py', '1073741824', phase]), \
                 mock.patch.object(entry.os, 'execv') as execute:
                entry.main()
            args = execute.call_args.args[1]
            self.assertEqual(args[:4], [sys.executable, '-I', '-B', '/program/program.py'])
            self.assertEqual(args[args.index('--phase') + 1], phase)
            self.assertEqual('--model' in args, phase == 'predict')


if __name__ == '__main__':
    unittest.main(verbosity=2)
