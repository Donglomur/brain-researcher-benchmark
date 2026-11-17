"""Generated source/capture controls. No Docker, scientific inputs or model calls."""
import base64
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

PACKAGE = Path(__file__).absolute().parents[1]
C = types.ModuleType('_rep012_namespace_capture')
C.__file__ = str(PACKAGE / 'controller.py')
exec(compile((PACKAGE / 'controller.py').read_bytes(), C.__file__, 'exec'), C.__dict__)
FIXTURE_WRITES = 0


def write(path, body):
    global FIXTURE_WRITES
    path.write_bytes(body)
    FIXTURE_WRITES += len(body)


def run_reader(path):
    # Only substitute the fixed generated operand; all reader operations are real.
    old = "p='/output/result.json'"
    assert C.OUTPUT_CAPTURE.count(old) == 1
    source = C.OUTPUT_CAPTURE.replace(old, 'p=' + repr(str(path)))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            exec(compile(source, '<generated-namespace-reader>', 'exec'), {})
        except SystemExit as error:
            if error.code != 0:
                raise
    return output.getvalue().encode()


def frame(body=b'{"opaque":true}\n'):
    return {'schema': 'rep012_live_namespace_output_v1', 'status': 'ordinary',
            'signature': [1, 2, stat.S_IFREG | 0o600, 1, len(body), 3, 4],
            'body_b64': base64.b64encode(body).decode(),
            'sha256': hashlib.sha256(body).hexdigest()}


def condition(reply, *, stderr=b'', close_error=False):
    calls, saved = [], {}
    c = C.Condition.__new__(C.Condition)
    c.closed = False
    c.frozen = None
    c.failed = None
    c.tokens = 0
    c.calls = 0
    c.arm = 'A'
    c.cid = 'a' * 64
    c.tool_end = time.monotonic() + 100
    c.folder = Path('/generated-owner/A')
    c.lock = threading.RLock()
    c.pair = types.SimpleNamespace(budget=types.SimpleNamespace(
        write=lambda path, body: saved.setdefault(path.name, body)))
    c.inspect = lambda: calls.append('inspect')
    def execute(args, **kwargs):
        calls.append((args, kwargs))
        return types.SimpleNamespace(stdout=reply, stderr=stderr, returncode=0)
    def close():
        calls.append('close')
        if close_error:
            raise ValueError('generated unknown closure')
        c.closed = True
    c.execute = execute
    c.close = close
    return c, calls, saved


class NamespaceCapture(unittest.TestCase):
    def test_actual_reader_handles_binary_empty_and_complete_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            for body in (b'', b'\x00\xff\nopaque json is not interpreted', bytes(range(256)) * 128):
                with self.subTest(size=len(body)):
                    write(path, body)
                    path.chmod(0o600)
                    result = run_reader(path)
                    self.assertLessEqual(len(result), 65536)
                    self.assertEqual(C.namespace_output(result), body)

    def test_actual_missing_reader_is_explicit_not_empty_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = run_reader(Path(tmp) / 'missing')
        self.assertIsNone(C.namespace_output(raw))
        self.assertEqual(json.loads(raw), {'schema': 'rep012_live_namespace_output_v1', 'status': 'missing'})

    def test_actual_links_directory_fifo_and_oversize_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regular = root / 'regular'
            write(regular, b'ok')
            linked = root / 'linked'
            linked.symlink_to(regular)
            directory = root / 'directory'
            directory.mkdir()
            fifo = root / 'fifo'
            os.mkfifo(fifo)
            large = root / 'large'
            write(large, b'x' * 32769)
            for path in (linked, directory, fifo, large):
                with self.subTest(path=path.name), self.assertRaises(ValueError):
                    run_reader(path)
            hardlink = root / 'hardlink'
            os.link(regular, hardlink)
            with self.assertRaises(ValueError):
                run_reader(regular)

    def test_metadata_change_after_open_refuses_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            write(path, b'unchanged bytes')
            original = os.fstat
            count = 0
            def changed(fd):
                nonlocal count
                count += 1
                value = original(fd)
                if count == 2:
                    fields = {k: getattr(value, k) for k in (
                        'st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
                    fields['st_ctime_ns'] += 1
                    return types.SimpleNamespace(**fields)
                return value
            with mock.patch.object(os, 'fstat', changed), self.assertRaisesRegex(ValueError, 'stable complete'):
                run_reader(path)

    def test_frame_rejects_truncation_identity_type_and_shape_changes(self):
        good = frame()
        bad = []
        for key, value in [('sha256', '0' * 64), ('body_b64', good['body_b64'][:-1]),
                           ('schema', 'other'), ('status', 'missing'), ('signature', [1] * 7)]:
            row = copy.deepcopy(good)
            row[key] = value
            bad.append(json.dumps(row).encode())
        row = copy.deepcopy(good)
        row['signature'][3] = True
        bad.append(json.dumps(row).encode())
        row = copy.deepcopy(good)
        row['extra'] = 'ignored'
        bad.append(json.dumps(row).encode())
        bad += [json.dumps(good).encode()[:-1], b'{}', b'x' * 65537,
                b'{"schema":"x","schema":"y"}', json.dumps({'status': 'missing'}).encode()]
        for value in bad:
            with self.subTest(value=value[:48]), self.assertRaises((ValueError, TypeError)):
                C.namespace_output(value)

    def test_freeze_uses_one_unprivileged_reader_then_original_closure(self):
        body = b'{"opaque":"candidate text"}'
        c, calls, saved = condition(json.dumps(frame(body)).encode())
        result = c.freeze()
        commands = [value for value in calls if isinstance(value, tuple)]
        self.assertEqual(len(commands), 1)
        argv, options = commands[0]
        self.assertEqual(argv, ['exec', '--user', '65534:65534', c.cid, C.PYTHON,
                                '-I', '-S', '-B', '-c', C.OUTPUT_CAPTURE])
        self.assertLessEqual(options['timeout'], 5)
        self.assertEqual(calls[-1], 'close')
        self.assertEqual(saved['submission.json'], body)
        self.assertTrue(json.loads(saved['FROZEN.json'])['closed'])
        self.assertEqual(result['output']['sha256'], hashlib.sha256(body).hexdigest())
        self.assertFalse(any(argv[0] == 'cp' for argv, _ in commands))

    def test_missing_output_closes_without_synthesizing_submission(self):
        c, _, saved = condition(b'{"schema":"rep012_live_namespace_output_v1","status":"missing"}')
        self.assertEqual(c.freeze()['output'], {'status': 'missing'})
        self.assertTrue(c.closed)
        self.assertNotIn('submission.json', saved)

    def test_bad_frame_or_stderr_closes_without_success_receipt(self):
        for reply, stderr in [(b'not a complete frame', b''), (json.dumps(frame()).encode(), b'warning')]:
            c, _, saved = condition(reply, stderr=stderr)
            with self.assertRaises(ValueError):
                c.freeze()
            self.assertTrue(c.closed)
            self.assertNotIn('submission.json', saved)
            self.assertNotIn('FROZEN.json', saved)
            self.assertIn('FAILURE.json', saved)

    def test_unknown_closure_preserves_capture_but_never_freezes(self):
        c, _, saved = condition(json.dumps(frame()).encode(), close_error=True)
        with self.assertRaises(ValueError):
            c.freeze()
        self.assertIn('submission.json', saved)
        self.assertNotIn('FROZEN.json', saved)
        self.assertFalse(c.closed)
        self.assertIn('FAILURE.json', saved)

    def test_capture_consumes_original_deadline(self):
        c, calls, saved = condition(json.dumps(frame()).encode())
        original = c.execute
        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            c.tool_end = time.monotonic() - 1
            return result
        c.execute = delayed
        with self.assertRaisesRegex(ValueError, 'original tool deadline'):
            c.freeze()
        self.assertTrue(c.closed)
        self.assertNotIn('FROZEN.json', saved)
        self.assertNotIn('submission.json', saved)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        print('generated_fixture_body_bytes_written=' + str(FIXTURE_WRITES))
