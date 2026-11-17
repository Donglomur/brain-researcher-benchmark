"""Generated namespace-reader and lifecycle composition controls, without Docker.

The simulated daemon deliberately returns an empty cp archive even when the
real generated output directory contains a file. The actual pinned reader runs
in memory against that directory; no source body is copied into a fixture.
"""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('n031_capture_backend', HERE / 'docker_backend.py')
db = importlib.util.module_from_spec(spec); spec.loader.exec_module(db)
GENERATED_WRITES = 0


def put(path, body):
    global GENERATED_WRITES
    GENERATED_WRITES += len(body)
    Path(path).write_bytes(body)


def reader_namespace():
    namespace = {'__name__': 'generated_capture_fixture'}
    exec(compile(db.CAPTURE_SOURCE, '<pinned-capture-source>', 'exec'), namespace)
    return namespace


class Transport:
    """Real generated output bytes, simulated Engine state; never subprocess."""
    def __init__(self, directory, fault=None):
        self.directory, self.fault = directory, fault
        self.exists = self.running = self.paused = False
        self.steps = []
        self.spec = {'name': 'n031-' + 'a' * 24 + '-00-b', 'batch': 'a' * 24,
                     'image': db.SELECTED_IMAGE,
                     'mounts': [('/generated/data.npz', '/input/data.npz'),
                                ('/generated/manifest.json', '/input/manifest.json'),
                                ('/generated/submission.py', '/program/submission.py')]}
        self.payload = b'{"generated_prediction":[1.0,1.0]}\n'

    def inspection(self):
        fixed = dict(value.split('=', 1) for value in db.ENV)
        config = {'Env': [k + '=' + v for k, v in {**db.SELECTED_IMAGE_ENV, **fixed}.items()],
                  'User': '65534:65534', 'WorkingDir': '/tmp', 'Entrypoint': [db.KEEPER[0]],
                  'Cmd': db.KEEPER[1:], 'Labels': {'neural031.batch': self.spec['batch']}, 'Volumes': None}
        host = {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Memory': db.MEMORY,
                'MemorySwap': db.MEMORY, 'NanoCpus': db.NANO_CPUS, 'PidsLimit': db.PIDS,
                'IpcMode': 'none', 'PidMode': '', 'Privileged': False, 'Devices': [],
                'DeviceRequests': [], 'CapAdd': None, 'CapDrop': ['ALL'], 'Tmpfs': db.TMPFS,
                'LogConfig': {'Type': 'none'}, 'RestartPolicy': {'Name': 'no'},
                'SecurityOpt': ['no-new-privileges:true']}
        mounts = [{'Type': 'bind', 'Source': source, 'Destination': dest, 'RW': False}
                  for source, dest in self.spec['mounts']]
        mounts += [{'Type': 'tmpfs', 'Destination': dest} for dest in db.TMPFS]
        return {'Name': '/' + self.spec['name'], 'Image': self.spec['image'], 'HostConfig': host,
                'Config': config, 'State': {'Running': self.running, 'Paused': self.paused}, 'Mounts': mounts}

    def __call__(self, argv, deadline, cap):
        args = argv[3:]
        self.steps.append(args)
        if args[:2] == ['image', 'inspect']:
            return db.encoded([{'Id': db.SELECTED_IMAGE, 'Os': 'linux', 'Architecture': 'arm64',
                 'Config': {'Env': [k + '=' + v for k, v in db.SELECTED_IMAGE_ENV.items()], 'Volumes': None}}])
        if args[0] == 'ps': return b'generated-id\n' if self.exists else b''
        if args[0] == 'create': self.exists = True; return b'generated-id\n'
        if args[0] == 'start': self.running = True; return b'generated-id\n'
        if args[:2] == ['container', 'inspect']: return db.encoded([self.inspection()])
        if args[0] == 'exec':
            if self.paused: raise RuntimeError('Engine cannot exec a paused container')
            if args[4:] == db.CANDIDATE:
                put(self.directory / 'predictions.json', self.payload)
                return b'{"generated_candidate":true}\n'
            if args[4:] == db.CAPTURE:
                if self.fault == 'reader': raise RuntimeError('generated reader failure')
                frame = reader_namespace()['capture'](self.directory)
                if self.fault == 'frame': frame['payload']['sha256'] = '0' * 64
                return db.encoded(frame)
            raise AssertionError('Only exact candidate or capture argv')
        if args[0] == 'pause':
            self.paused = self.fault != 'pause'
            return b'paused\n'
        if args[0] == 'cp': return b'\0' * 1536  # Faithful unsupported-tmpfs corner-case model.
        if args[0] == 'rm':
            if self.fault == 'remove': raise RuntimeError('generated removal failure')
            self.exists = self.running = self.paused = False
            return b'removed\n'
        raise AssertionError(args)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='n031-capture-generated-')
        self.root = Path(self.tmp.name)
        self.output = self.root / 'output'; self.output.mkdir()
        self.reader = reader_namespace()

    def tearDown(self): self.tmp.cleanup()

    def frame(self, body=b'{"prediction":1}\n'):
        put(self.output / 'predictions.json', body)
        return self.reader['capture'](self.output)

    def test_real_generated_file_reader_and_strict_frame_agree(self):
        body = b'{"prediction":1}\n'
        frame = self.frame(body)
        self.assertFalse(frame['capture_while_paused'])
        self.assertEqual(frame['file_before'], frame['file_after'])
        self.assertEqual(frame['file_before'], frame['name_after'])
        self.assertEqual(db.prediction_from_frame(db.encoded(frame)), body)

    def test_exact_maximum_and_oversized_file_boundary(self):
        frame = self.frame(b'x' * 131072)
        self.assertEqual(len(db.prediction_from_frame(db.encoded(frame))), 131072)
        self.assertEqual(len(frame['payload']['base64']), 174764)
        put(self.output / 'predictions.json', b'x' * 131073)
        with self.assertRaises(ValueError): self.reader['capture'](self.output)

    def test_missing_and_extra_entries_refused(self):
        with self.assertRaises(ValueError): self.reader['capture'](self.output)
        self.frame()
        put(self.output / 'extra', b'x')
        with self.assertRaises(ValueError): self.reader['capture'](self.output)

    def test_file_symlink_hardlink_and_fifo_refused_without_blocking(self):
        target = self.root / 'target'; put(target, b'generated')
        path = self.output / 'predictions.json'
        path.symlink_to(target)
        with self.assertRaises((OSError, ValueError)): self.reader['capture'](self.output)
        path.unlink(); os.link(target, path)
        self.assertEqual(set(os.listdir(self.output)), {'predictions.json'})
        with self.assertRaises(ValueError): self.reader['capture'](self.output)
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): self.reader['capture'](self.output)

    def test_output_directory_symlink_refused(self):
        self.frame()
        link = self.root / 'link'; link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(OSError): self.reader['capture'](link)

    def test_observed_same_extent_content_mutation_refused(self):
        self.frame(b'initial')
        path = self.output / 'predictions.json'; initial = path.stat()
        class Proxy:
            changed = False
            def __getattr__(self, key): return getattr(os, key)
            def read(proxy, fd, count):
                data = os.read(fd, count)
                if not proxy.changed:
                    proxy.changed = True
                    put(path, b'changed')
                    os.utime(path, ns=(initial.st_atime_ns, initial.st_mtime_ns + 1000000000))
                return data
        self.reader['os'] = Proxy()
        with self.assertRaises(ValueError): self.reader['capture'](self.output)

    def test_equal_contents_name_replacement_refused(self):
        self.frame(b'unchanged-bytes')
        path = self.output / 'predictions.json'
        class Proxy:
            changed = False
            def __getattr__(self, key): return getattr(os, key)
            def read(proxy, fd, count):
                data = os.read(fd, count)
                if not proxy.changed:
                    proxy.changed = True
                    path.rename(self.root / 'old-inode')
                    put(path, b'unchanged-bytes')
                return data
        self.reader['os'] = Proxy()
        with self.assertRaises(ValueError): self.reader['capture'](self.output)

    def test_malformed_frame_identity_and_noncanonical_encoding_refused(self):
        frame = self.frame(b'f')
        variants = []
        for key in ('file_after', 'name_after', 'directory_after'):
            value = copy.deepcopy(frame); value[key][1] += 1; variants.append(value)
        for key, changed in [('sha256', '0' * 64), ('bytes', True), ('base64', '!!!!'), ('base64', 'Zh==')]:
            value = copy.deepcopy(frame); value['payload'][key] = changed; variants.append(value)
        value = copy.deepcopy(frame); value['capture_while_paused'] = True; variants.append(value)
        value = copy.deepcopy(frame); value['extra'] = 1; variants.append(value)
        value = copy.deepcopy(frame); value['file_before'][3] = 2; variants.append(value)
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): db.prediction_from_frame(db.encoded(value))
        duplicate = db.encoded(frame).replace(b'{', b'{"schema":"duplicate",', 1)
        with self.assertRaises(ValueError): db.prediction_from_frame(duplicate)
        with self.assertRaises(ValueError): db.prediction_from_frame(b'x' * 262145)

    def test_inline_reader_and_selected_intent_fit_existing_bounds(self):
        self.assertLessEqual(len(db.CAPTURE_SOURCE.encode()), 2048)
        argv = ['/usr/local/bin/docker', '--host', 'unix:///Users/nicholas/.docker/run/docker.sock',
                '--config', '/Users/nicholas/Documents/Codex/neuroscience-benchmark-data/neural031-paired-native-successor/docker-config',
                'exec', '--user', '65534:65534', 'n031-' + 'a' * 24 + '-19-n', *db.CAPTURE]
        intent = {'schema': 'neural031_cli_intent_v1', 'sequence': 441, 'argv': argv,
                  'started_monotonic': 1234567.123456789, 'deadline_monotonic': 1235047.123456789,
                  'stdout_cap': 262144, 'stderr_cap': 4096, 'journal_grant_bytes': 274432}
        self.assertLessEqual(len(db.encoded(intent)), db.INTENT_CAP)
        self.assertEqual(db.CAPTURE[:5], ['/usr/local/bin/python', '-I', '-S', '-B', '-c'])

    def backend(self, fault=None):
        transport = Transport(self.output, fault)
        backend = db.DockerBackend(command=transport)
        deadline = db.Deadline()
        backend.verify_image(db.SELECTED_IMAGE, deadline)
        return backend, transport, deadline

    def test_original_empty_cp_defect_and_repaired_actual_namespace_composition(self):
        backend, transport, deadline = self.backend()
        put(self.output / 'predictions.json', transport.payload)
        empty = transport(backend.prefix + ['cp', transport.spec['name'] + ':/output/.', '-'], deadline, 262144)
        self.assertEqual(len(empty), 1536)
        self.assertTrue((self.output / 'predictions.json').is_file())
        with self.assertRaises(ValueError): db.prediction_from_tar(empty)
        transport.steps.pop()  # Exclude the deliberately invoked historical defect model.
        body = backend.run_context(transport.spec, deadline)
        self.assertEqual(body, transport.payload)
        self.assertFalse(transport.exists)
        self.assertEqual([x[0] for x in transport.steps],
                         ['image', 'ps', 'create', 'start', 'container', 'exec', 'exec', 'pause', 'container', 'rm', 'ps'])
        execs = [x[4:] for x in transport.steps if x[0] == 'exec']
        self.assertEqual(execs, [db.CANDIDATE, db.CAPTURE])
        self.assertEqual(backend.command_count, 11)
        self.assertEqual(backend.events[-1]['event'], 'context_absence_observed')
        backend.absent_all(deadline)
        self.assertEqual(backend.command_count, 12)  # One context of the1+40*10+40 complete roster.

    def test_capture_reader_or_bad_frame_failure_preserves_owned_cleanup(self):
        for fault in ('reader', 'frame'):
            with self.subTest(fault=fault):
                backend, transport, deadline = self.backend(fault)
                with self.assertRaises((RuntimeError, ValueError)):
                    backend.run_context(transport.spec, deadline)
                self.assertFalse(transport.exists)
                self.assertEqual(backend.events[-1]['event'], 'failure_cleanup')
                self.assertTrue(backend.events[-1]['absence_verified'])
                self.assertNotIn('pause', [x[0] for x in transport.steps])

    def test_pause_or_removal_failure_never_returns_captured_submission(self):
        for fault in ('pause', 'remove'):
            with self.subTest(fault=fault):
                backend, transport, deadline = self.backend(fault)
                with self.assertRaises((RuntimeError, ValueError)):
                    backend.run_context(transport.spec, deadline)
                self.assertEqual(backend.events[-1]['event'], 'failure_cleanup')
                self.assertEqual(backend.events[-1]['absence_verified'], fault != 'remove')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CaptureTests))
    print(json.dumps({'generated_fixture_cumulative_write_charge_bytes': GENERATED_WRITES,
                      'fixtures_removed': True, 'Docker_calls': 0, 'actual_tmpfs_qualification': False,
                      'authentic_data_reads': 0, 'generated_reader_executes_in_memory': True}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
