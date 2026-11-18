"""Generated cgroup records and public140-row toy scoring, never authentic data.

No kernel file, container, model or subprocess is queried. The original worker
source is authenticated and run with an in-memory file descriptor/path fixture;
its public validation, integrity checks and numerical calculations are unchanged.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import stat
import sys
import types
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generated_telemetry', HERE / 'telemetry.py')
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
ORIGINAL = HERE.parent/'neural034-portable/benchmarks/neuroscience/neural-034/grader.py'


def encode(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def v2():
    return {'/proc/self/cgroup': b'0::/\n',
        '/proc/self/mountinfo': b'28 23 0:26 / /sys/fs/cgroup ro,nosuid,nodev,noexec - cgroup2 cgroup rw\n',
        '/sys/fs/cgroup/memory.max': b'536870912\n', '/sys/fs/cgroup/memory.swap.max': b'0\n',
        '/sys/fs/cgroup/memory.events': b'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n',
        '/sys/fs/cgroup/memory.peak': b'12345678\n'}


def reader(files):
    def read(path, cap):
        if path not in files: raise FileNotFoundError('GENERATED missing file: ' + path)
        body = files[path]
        if len(body) > cap: raise ValueError('GENERATED extent over cap')
        return body
    return read


class VirtualFiles:
    def __init__(self, data):
        self.data = data; self.opened = []; self.fds = {}; self.serial = 100
    def open(self, path, flags):
        self.opened.append(path); body = self.data[path]; self.serial += 1
        self.fds[self.serial] = [body, 0]
        return self.serial
    def read(self, fd, count):
        body, offset = self.fds[fd]; result = body[offset:offset + count]
        self.fds[fd][1] += len(result)
        return result
    def fstat(self, fd):
        return types.SimpleNamespace(st_mode=stat.S_IFREG | 0o444, st_nlink=1,
            st_size=len(self.fds[fd][0]), st_dev=1, st_ino=fd, st_mtime_ns=0, st_ctime_ns=0)
    def close(self, fd): del self.fds[fd]


def generated_worker(source, outcome='scored'):
    cases = [{'fold': fold, 'query_id': format(fold * 20 + i, '024x')} for fold in range(7) for i in range(20)]
    probabilities = [{**row, 'probability': .5} for row in cases]
    if outcome == 'invalid_submission': probabilities.pop()
    bodies = {'/public/cases.json': encode({'cases': cases}),
        '/submission/probabilities.json': encode({'schema_version': 1, 'probabilities': probabilities}),
        '/private/targets.json': encode({'folds': [{'fold': fold,
            'query_ids': [r['query_id'] for r in cases if r['fold'] == fold],
            'query_labels': [0] * 10 + [1] * 10} for fold in range(7)]}),
        '/private/reference_grade.json': encode({'summary': {name: {'balanced_accuracy': .5, 'log_loss': .7}
            for name in ('constant', 'amplitude', 'glial', 'behavior', 'combined', 'time_scrambled')}})}
    assets = {key: pin(bodies[path]) for key, path in (
        ('public_panel', '/public/cases.json'), ('private_targets', '/private/targets.json'),
        ('private_references', '/private/reference_grade.json'))}
    if outcome == 'operator_error': assets['public_panel']['sha256'] = '0' * 64
    metadata = {'/source/operator_assets.json': encode(assets),
        '/source/invocation.json': encode({'submission': pin(bodies['/submission/probabilities.json'])})}
    class VirtualPath:
        def __init__(self, path): self.path = path
        def read_bytes(self): return metadata[self.path]
    worker = T.worker_from_bytes(source)
    fs = VirtualFiles(bodies)
    worker.__globals__['Path'] = VirtualPath
    worker.__globals__['os'] = types.SimpleNamespace(open=fs.open, read=fs.read, close=fs.close,
        fstat=fs.fstat, O_RDONLY=0, O_NOFOLLOW=1, O_NONBLOCK=2)
    return worker, fs


class TelemetryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()
        if pin(cls.original) != T.WORKER_PIN: raise ValueError('Original worker source pin')

    def test_v2_kernel_peak_and_explicit_observation_scope(self):
        value = T.snapshot(reader(v2()), lambda: 123)
        self.assertEqual(value['peak_status'], 'available')
        self.assertEqual(value['peak_bytes'], 12345678)
        self.assertEqual(value['peak_observed_monotonic_ns'], 123)
        self.assertEqual(value['oom_counters'], {'oom': 0, 'oom_kill': 0, 'oom_group_kill': 0})
        self.assertTrue(value['memory_limit_match']); self.assertTrue(value['swap_limit_match'])
        self.assertFalse(value['entire_container_lifetime_measured'])

    def test_v1_exact_files_and_failcnt_not_oom_counter(self):
        root = '/sys/fs/cgroup/memory'
        files = {'/proc/self/cgroup': b'4:memory:/\n',
            '/proc/self/mountinfo': b'29 23 0:27 / /sys/fs/cgroup/memory ro - cgroup cgroup rw,memory\n',
            root + '/memory.limit_in_bytes': b'536870912\n', root + '/memory.memsw.limit_in_bytes': b'536870912\n',
            root + '/memory.max_usage_in_bytes': b'555\n', root + '/memory.failcnt': b'17\n',
            root + '/memory.oom_control': b'oom_kill_disable 0\nunder_oom 0\noom_kill 2\n'}
        value = T.snapshot(reader(files), lambda: 1)
        self.assertEqual(value['peak_bytes'], 555)
        self.assertEqual(value['oom_counters'], {'oom_kill': 2})
        self.assertEqual(value['allocation_failure_count'], 17)
        files[root + '/memory.oom_control'] = b'oom_kill_disable 0\nunder_oom 0\n'
        value = T.snapshot(reader(files), lambda: 2)
        self.assertEqual(value['oom_status'], 'unsupported'); self.assertIsNone(value['oom_counters'])

    def test_unknown_is_not_zero_or_sampled_fallback(self):
        mutations = [lambda f: f.pop('/sys/fs/cgroup/memory.peak'),
            lambda f: f.update({'/proc/self/cgroup': b'0::/some-subgroup\n'}),
            lambda f: f.update({'/sys/fs/cgroup/memory.max': b'4294967296\n'}),
            lambda f: f.update({'/sys/fs/cgroup/memory.peak': b'-1\n'}),
            lambda f: f.update({'/proc/self/mountinfo': f['/proc/self/mountinfo'] * 2})]
        for index, mutate in enumerate(mutations):
            files = v2(); mutate(files); value = T.snapshot(reader(files), lambda: 2)
            with self.subTest(index=index):
                self.assertEqual(value['peak_status'], 'unsupported'); self.assertIsNone(value['peak_bytes'])
        files = v2(); files['/sys/fs/cgroup/memory.events'] = b'oom 0\noom 1\n'
        value = T.snapshot(reader(files), lambda: 3)
        self.assertEqual(value['peak_status'], 'available'); self.assertEqual(value['oom_status'], 'unsupported')

    def test_two_frames_original_worker_stdout_status_and_public_first(self):
        for outcome, code in (('scored', 0), ('invalid_submission', 2), ('operator_error', 1)):
            direct, _ = generated_worker(self.original, outcome)
            plain = io.StringIO()
            with contextlib.redirect_stdout(plain): self.assertEqual(direct(), code)
            wrapped, fs = generated_worker(self.original, outcome); output = io.StringIO(); frames = []
            with contextlib.redirect_stdout(output):
                self.assertEqual(T.run_worker(wrapped, reader=reader(v2()), emit=frames.append, clock=lambda: 10), code)
            self.assertEqual(output.getvalue(), plain.getvalue())
            self.assertEqual([r['phase'] for r in frames], ['before', 'after'])
            self.assertEqual(frames[1]['worker_returncode'], code)
            self.assertTrue(frames[1]['same_cgroup_as_before'])
            for frame in frames: self.assertLessEqual(len(T.frame_bytes(frame)), 8192)
            result = json.loads(output.getvalue())
            if code == 0:
                self.assertEqual(result['score']['balanced_accuracy'], .5)
                self.assertEqual(result['score']['log_loss'], math.log(2))
                self.assertEqual(len(result['per_mouse']), 7)
                self.assertEqual(len(result['reference_metrics']), 6)
            else:
                self.assertFalse(any(path.startswith('/private/') for path in fs.opened))

    def test_telemetry_and_emit_errors_preserve_completed_worker_result(self):
        for emit_fails in (False, True):
            frames = []; worker, _ = generated_worker(self.original)
            def missing(*unused): raise PermissionError('GENERATED telemetry denied')
            def emit(record):
                if emit_fails: raise OSError('GENERATED stderr failure')
                frames.append(record)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = T.run_worker(worker, reader=missing, emit=emit, clock=lambda: 1)
            self.assertEqual(code, 0); self.assertEqual(json.loads(output.getvalue())['status'], 'scored')
            if not emit_fails:
                self.assertEqual(frames[-1]['measurement']['peak_status'], 'unsupported')
                self.assertIsNone(frames[-1]['measurement']['peak_bytes'])

    def test_oom_delta_and_counter_regression_are_explicit(self):
        for final in (3, 0):
            files = v2(); count = [0]; frames = []
            def read(path, cap):
                if path.endswith('/memory.events'):
                    count[0] += 1; number = 1 if count[0] == 1 else final
                    return ('oom %d\noom_kill %d\n' % (number, number)).encode()
                return reader(files)(path, cap)
            self.assertEqual(T.run_worker(lambda: 0, reader=read, emit=frames.append, clock=lambda: 1), 0)
            self.assertEqual(frames[-1]['oom_counter_delta'], {'oom': 2, 'oom_kill': 2} if final == 3 else None)

    def test_worker_source_change_is_refused_before_execution(self):
        with self.assertRaises(ValueError): T.worker_from_bytes(self.original + b'\n')


if __name__ == '__main__':
    unittest.main()
