"""Actual publisher/snapshot controls using invented bytes, never native execution."""
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time
import types
import unittest

HERE = Path(__file__).resolve().parent
WRITES = {'requested_bytes': 0, 'completed_bytes': 0, 'calls': 0, 'failed_calls': 0}


class Proxy:
    def __init__(self, original, **changes):
        self.original, self.changes = original, changes

    def __getattr__(self, name):
        return self.changes.get(name, getattr(self.original, name))


def counted_write(fd, body):
    WRITES['requested_bytes'] += len(body)
    WRITES['calls'] += 1
    try:
        count = os.write(fd, body)
    except BaseException:
        WRITES['failed_calls'] += 1
        raise
    WRITES['completed_bytes'] += count
    return count


def fixture(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(body):
            count = counted_write(fd, body[offset:])
            if count <= 0:
                raise OSError('fixture short write')
            offset += count
    finally:
        os.close(fd)


def load():
    body = (HERE / 'support.py').read_bytes()
    support = types.ModuleType('_mode_control_support')
    support.__file__ = str(HERE / 'support.py')
    exec(compile(body, support.__file__, 'exec'), support.__dict__)
    return support.runtime()


class ReachedNativeBoundary(Exception):
    """The real snapshot path completed; scientific/native execution is forbidden."""


class PublicModeControls(unittest.TestCase):
    def setUp(self):
        self.loader, self.bodies, self.manifest, self.source = load()
        self.common = self.loader('common')
        self.original_os = self.common.os
        self.common.os = Proxy(os, write=counted_write)
        self.old_umask = os.umask(0o077)
        self.temporary = tempfile.TemporaryDirectory(prefix='neural076-public-mode-')
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.common.os = self.original_os
        os.umask(self.old_umask)
        self.temporary.cleanup()
        self.assertFalse(self.root.exists())

    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_actual_publisher_finalizes_complete_bytes_and_keeps_parent_private(self):
        body = b'invented public script\n'
        path = self.root / 'public.py'
        result = self.common.write(path, body, len(body))
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(result, self.common.short(body))
        self.assertEqual(self.mode(path), 0o444)
        self.assertEqual(self.mode(self.root), 0o700)
        self.assertEqual(os.umask(0o077), 0o077)

    def test_short_writes_finish_before_owned_descriptor_finalization(self):
        body = b'complete short-write source\n'
        path = self.root / 'short.py'
        events = []

        def partial(fd, data):
            count = counted_write(fd, data[:3])
            events.append(('write', count))
            return count

        def finalize(fd, mode):
            self.assertEqual(os.fstat(fd).st_size, len(body))
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o400)
            events.append(('fchmod', mode))
            os.fchmod(fd, mode)

        self.common.os = Proxy(os, write=partial, fchmod=finalize)
        self.common.write(path, body, len(body))
        self.assertGreater(len(events), 2)
        self.assertEqual(events[-1], ('fchmod', 0o444))
        self.assertEqual(path.read_bytes(), body)
        self.assertEqual(self.mode(path), 0o444)

    def test_failed_partial_write_never_finalizes_public_mode(self):
        path = self.root / 'partial.py'
        calls = []
        finalizations = []

        def fail_after_prefix(fd, data):
            calls.append(len(data))
            if len(calls) == 1:
                return counted_write(fd, data[:2])
            raise OSError('scripted write failure before complete publication')

        def finalize(fd, mode):
            finalizations.append(mode)
            os.fchmod(fd, mode)

        self.common.os = Proxy(os, write=fail_after_prefix, fchmod=finalize)
        with self.assertRaisesRegex(OSError, 'scripted write failure'):
            self.common.write(path, b'incomplete script\n', 100)
        self.assertEqual(path.read_bytes(), b'in')
        self.assertEqual(finalizations, [])
        self.assertEqual(self.mode(path), 0o400)
        self.assertEqual(self.mode(self.root), 0o700)

    def test_existing_file_and_size_guards_remain_active(self):
        path = self.root / 'owned.py'
        self.common.write(path, b'first', 5)
        with self.assertRaises(FileExistsError):
            self.common.write(path, b'second', 6)
        with self.assertRaises(ValueError):
            self.common.write(self.root / 'oversized.py', b'body', 3)
        self.assertEqual(path.read_bytes(), b'first')
        self.assertFalse((self.root / 'oversized.py').exists())

    def test_actual_candidate_phase_snapshots_under_restrictive_umask(self):
        c = self.common
        coordinator = self.loader('coordinator')
        phase = self.loader('phases')
        runtime = self.loader('runtime')
        lifecycle = self.loader('lifecycle')
        self.assertEqual(len(c.KEYS), 650)
        self.assertEqual(c.PRED, 24 * 2**20)
        root = self.root / 'output'
        root.mkdir(mode=0o700)
        for name in ('program', 'phases', 'current'):
            (root / name).mkdir(mode=0o700)
        key = c.KEYS[0]
        view = root / 'current' / key.replace('/', '__')
        view.mkdir(mode=0o700)
        folder = root / 'phases' / '0001-candidate'
        program = b'# invented source; not executed\n'
        fixture(root / 'program' / 'program.py', program)
        image = 'sha256:' + 'b' * 64
        binary = str(self.root / 'never-called-docker')
        socket = str(self.root / 'never-used-socket')
        review = {'schema': 'neural076_program_procedural_review_v1',
                  'program': c.short(program), 'source': self.source,
                  'training_only_transforms': True, 'pointwise_query_prediction': True,
                  'no_cross_context_state': True, 'max_voxels_per_unit': 316,
                  'reviewed': True, 'input_dependence_empirically_proven': False}
        # This is invented admission metadata for a scripted boundary, never host qualification.
        qualification = {'schema': 'neural076_full650_runtime_qualification_v1',
                         'source': self.source, 'image': image, 'python': '3.11.13',
                         'dependencies': c.decode(self.bodies['LOCK.json'])['expected_dependencies'],
                         'host_python': str(Path(sys.executable).resolve()),
                         'docker_binary': binary, 'docker_socket': socket,
                         'source_directory': str(HERE / 'runtime'),
                         'candidate_seconds': 10, 'candidate_memory_bytes': 512 * 2**20,
                         'staging_candidate_collection_capabilities_qualified': True,
                         'scientific_performance_qualified': False,
                         'exclusive_operator_owned_source_collection_output': True,
                         'same_filesystem_no_concurrent_writers': True,
                         'candidate_has_no_host_or_socket_access': True}
        operands = {}
        for name, document in (('review', review), ('qualification', qualification)):
            path = self.root / (name + '.json')
            raw = c.encode(document)
            fixture(path, raw)
            operands[name] = {'path': str(path), **c.short(raw)}
        selection = {'schema': 'neural076_full650_selection_v1', 'execution_selected': True,
                     'task_id': 'NEURAL-076', 'source': self.source,
                     'collection': str(self.root / 'no-authentic-collection'), 'output': str(root),
                     'program': {'path': str(root / 'program' / 'program.py'), **c.short(program)},
                     'program_review': operands['review'],
                     'runtime_qualification': operands['qualification'],
                     'image': image, 'docker_binary': binary, 'docker_socket': socket,
                     'candidate_seconds': 10, 'memory_bytes': 512 * 2**20,
                     'other_future_bytes': 0, 'whole_seconds': coordinator.whole_seconds(10),
                     'retained_bytes': c.RETAIN + c.MIB, 'managed_reads': c.READS,
                     'managed_writes': c.WRITES}
        commitment = {'schema': 'neural076_frozen_program_v1', 'source': self.source,
                      'program': c.short(program), 'keys': list(c.KEYS), 'image': image,
                      'candidate_seconds': 10, 'memory_bytes': 512 * 2**20,
                      'procedural_review': operands['review'],
                      'runtime_qualification': operands['qualification'],
                      'condition': 'full650_feature_recovery', 'feedback_before_commitment': False}
        commit_raw = c.encode(commitment)
        fixture(root / 'program' / 'COMMIT.json', commit_raw)
        context = {'schema': 'neural076_matched_hierarchy_v1', 'key': key,
                   'source_design_sha256': '56ff1e67bb824b9ad6ab9005db82a11349581bb634a0725f4a1cca81019a6026',
                   'max_selected_voxels': 316}
        pins = {}
        for name, raw in [('training.npz', b'invented training bytes'),
                          ('queries.npz', b'invented query bytes'),
                          ('bank.npz', b'invented bank bytes'), ('context.json', c.encode(context))]:
            fixture(view / name, raw)
            pins[name] = c.short(raw)
        fixture(view / 'COMPLETE.json', c.encode({'schema': 'neural076_prepared_v1', 'files': pins}))
        binding = phase.stage_binding(view, key, lambda: None)
        phase.seal_view(view, binding, lambda: None)
        request = {'schema': 'neural076_owned_phase_request_v1', 'source': self.source,
                   'selection': selection, 'mode': 'candidate', 'key': key,
                   'folder': str(folder), 'view': str(view), 'end': time.monotonic() + 90,
                   'other': 0, 'commit': c.short(commit_raw)}
        request_path = self.root / 'request.json'
        raw = c.encode(request)
        fixture(request_path, raw)
        old_os, old_docker, old_lifecycle = phase.os, runtime.Docker, lifecycle.case_lifecycle
        old_handler = signal.getsignal(signal.SIGALRM)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        # Fixture-only physical free-space observation; actual inventory/caps/deadlines remain active.
        phase.os = Proxy(os, statvfs=lambda _p: types.SimpleNamespace(f_bavail=2**40, f_frsize=4096))
        runtime.Docker = lambda *_a: 'scripted non-native boundary'
        reached = []

        def stop_before_native(_engine, docker, snapshot, _cfg, actual_view, *_args):
            reached.append(True)
            self.assertEqual(docker, 'scripted non-native boundary')
            self.assertEqual(actual_view, view)
            self.assertEqual({p.name for p in snapshot.iterdir()}, {'program.py', 'entry.py', 'holder.py'})
            for name, expected in [('program.py', program), ('entry.py', self.bodies['entry.py']),
                                   ('holder.py', self.bodies['holder.py'])]:
                self.assertEqual((snapshot / name).read_bytes(), expected)
                self.assertEqual(self.mode(snapshot / name), 0o444)
            self.assertEqual(self.mode(snapshot), 0o555)
            for private in (self.root, root, root / 'phases', folder):
                self.assertEqual(self.mode(private), 0o700)
            raise ReachedNativeBoundary()

        lifecycle.case_lifecycle = stop_before_native
        try:
            with self.assertRaises(ReachedNativeBoundary):
                phase.main(['--source-sha256', self.source['sha256'], '--request', str(request_path),
                            '--request-sha256', c.short(raw)['sha256']],
                           self.loader, self.bodies, self.manifest, self.source)
            self.assertEqual(reached, [True])
            self.assertFalse((folder / 'COMPLETE.json').exists())
            self.assertFalse((folder / 'EXECUTION.json').exists())
            self.assertFalse((folder / 'predictions.npz').exists())
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
            phase.os, runtime.Docker, lifecycle.case_lifecycle = old_os, old_docker, old_lifecycle
            view.chmod(0o700)
            if (folder / 'snapshot').exists():
                (folder / 'snapshot').chmod(0o700)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicModeControls))
    print(json.dumps({'schema': 'neural076_public_modes_generated_controls_v1',
                      'python': sys.version, 'numpy': 'not imported; standard-library controls only',
                      'methods': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                      'generated_os_write_calls': WRITES,
                      'accounting': 'actual fixture/publisher os.write arguments and returns only; excludes source/admin writes, filesystem allocation and metadata',
                      'scripted_write_failure_count': 1, 'fixtures_removed': True,
                      'native_execution': False, 'scientific_qualification': False}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
