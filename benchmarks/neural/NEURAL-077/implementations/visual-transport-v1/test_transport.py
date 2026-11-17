"""Protocol/security controls; invented rows are not neuroscience observations."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('transport', HERE / 'transport.py')
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        parser_path = HERE.parent / 'direct-response/portable/response_contract.py'
        parser = t.v.load_module('test_response', parser_path, parser_path.read_bytes())
        self.dataset = {'rows': [{'trial_id': f'development-001-generated-{i:03d}', 'channels': [[0.0] * 1024] * 2}
                                 for i in range(2)],
                        'demos': [{'trial_id': f'demo-{i}', 'channels': [[1.0] * 1024] * 2, 'target': i % 2}
                                  for i in range(4)], 'parser': parser, 'packet': {'generated': '0' * 64}}
        self.helper = (HERE / 'scripted_client.py').read_text().split("if __name__ == '__main__':")[0]
        self.python = '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3' if sys.platform == 'darwin' else sys.executable

    def tearDown(self):
        self.temp.cleanup()

    def client(self, text):
        path = self.root / f'client-{len(list(self.root.glob("client-*")))}.py'
        path.write_text(self.helper + '\n' + text)
        return path

    def run_client(self, source, mode='zero_shot', limits=None, ordinal=0, sandbox='protocol_only'):
        path = self.root / f'session-{len(list(self.root.glob("session-*")))}'
        receipt = t.run_episode(self.dataset, ordinal, mode, path, self.client(source), self.python, sandbox, limits)
        return path, receipt

    def test_exact_png_framing_fresh_process_and_audit(self):
        script = """
ready, png = receive()
assert png.startswith(b'\\x89PNG\\r\\n\\x1a\\n')
assert ready['initial']['display']['record'] == 'query'
assert ready['initial']['display']['start_sample'] == -256
assert 'demonstration_target' not in ready['initial']['display']
assert 'packet' not in ready and 'ordinal' not in ready
send({'action':'window','start_sample':0,'stop_sample':128})
frame, png = receive()
assert frame['display']['start_sample'] == 0 and png
send({'action':'finalize','response':json.dumps({'trial_id':ready['trial_id'],'target_probability':0.5})})
assert receive()[0]['status'] == 'valid_unscored'
"""
        ids = []
        for i in range(2):
            path, receipt = self.run_client(script, ordinal=i)
            self.assertEqual(receipt['status'], 'valid_unscored')
            t.audit_transport(path, self.dataset, i, 'zero_shot')
            ready, png = t.unpack((path / 'transport/0000-out.bin').read_bytes())
            ids.append(ready['episode_id'])
            self.assertNotIn(self.dataset['rows'][1-i]['trial_id'].encode(), (path / 'transport/0000-out.bin').read_bytes())
        self.assertNotEqual(*ids)

    def test_forbidden_and_malformed_actions_are_exactly_captured(self):
        script = """
ready, _ = receive()
for action in ({'action':'read_file','path':'/etc/passwd'}, {'action':'exec','code':'print(1)'},
               {'action':'export'}, {'action':'target'}, {'action':'select','record':'demo1'},
               {'action':'select','record':'query2'}, {'action':'inspect','path':'secret'},
               {'action':'gain','units_per_division':True}, {'action':'window','start_sample':False,'stop_sample':768}):
    send(action)
    assert receive()[0]['status'] == 'rejected'
for body in (b'\\xff', b'{"action":"inspect","action":"inspect"}', b'{"action":"gain","units_per_division":NaN}', b'['*1000):
    sys.stdout.buffer.write(PREFIX.pack(len(body),0)+body); sys.stdout.buffer.flush()
    assert receive()[0]['status'] == 'rejected'
send({'action':'finalize','response':json.dumps({'trial_id':ready['trial_id'],'target_probability':0.5})})
assert receive()[0]['status'] == 'valid_unscored'
"""
        path, receipt = self.run_client(script)
        self.assertEqual(receipt['status'], 'valid_unscored')
        t.audit_transport(path, self.dataset, 0, 'zero_shot')
        for p in (path / 'transport').glob('*-out.bin'):
            header, _ = t.unpack(p.read_bytes())
            self.assertNotIn(str(self.root), json.dumps(header))
            self.assertNotIn('target_probability', json.dumps(header)) if header['status'] != 'ready' else None

    def test_first_invalid_final_is_terminal_without_replacement(self):
        path, receipt = self.run_client("""
ready, _ = receive()
first = json.dumps({'action':'finalize','response':'first invalid response'}).encode()
replacement = json.dumps({'action':'finalize','response':json.dumps({'trial_id':ready['trial_id'],'target_probability':1})}).encode()
sys.stdout.buffer.write(PREFIX.pack(len(first),0)+first+PREFIX.pack(len(replacement),0)+replacement)
sys.stdout.buffer.flush()
assert receive()[0]['status'] == 'invalid_response'
""")
        self.assertEqual(receipt['status'], 'invalid_response')
        self.assertEqual((path / 'response.txt').read_bytes(), b'first invalid response')
        self.assertEqual(t.v.decode((path / 'FINAL.json').read_bytes())['actions'], 2)
        with self.assertRaises(ValueError):
            t.audit_transport(path, self.dataset, 0, 'zero_shot')

    def test_four_demo_is_explicit_and_query_has_no_label(self):
        path, receipt = self.run_client("""
ready, _ = receive()
for i in range(1,5):
    send({'action':'select','record':'demo'+str(i)})
    frame, png = receive()
    assert frame['display']['demonstration_target'] == (i-1)%2 and png
send({'action':'select','record':'query'})
assert 'demonstration_target' not in receive()[0]['display']
send({'action':'finalize','response':json.dumps({'trial_id':ready['trial_id'],'target_probability':0.5})})
receive()
""", mode='four_demo')
        self.assertEqual(receipt['status'], 'valid_unscored')
        t.audit_transport(path, self.dataset, 0, 'four_demo')
        with self.assertRaises(ValueError):
            t.audit_transport(path, self.dataset, 0, 'zero_shot')

    def test_limits_eof_deadline_and_partial_input_fail_closed(self):
        cases = [
            ('ready,_=receive()\nsend({"action":"inspect"})\nreceive()', t.Limits(max_images=1), 'image_limit'),
            ('ready,_=receive()\nsend({"action":"bad"})\nreceive()\nsend({"action":"finalize","response":"{}"})\nreceive()',
             t.Limits(max_actions=2, max_images=1), 'action_limit'),
            ('ready,_=receive()\nsend({"action":"inspect"})\nreceive()',
             t.Limits(max_output_bytes=t.PNG_MAX+t.HEADER_MAX+t.RESERVE), 'output_byte_limit'),
            ('receive()', None, 'transport_eof'),
            ('receive()\nimport time\ntime.sleep(2)', t.Limits(wall_seconds=0.4), 'deadline'),
            ('receive()\nsys.stdout.buffer.write(b"abc");sys.stdout.buffer.flush()', None, 'transport_eof'),
            ('receive()\nsys.stdout.buffer.write(PREFIX.pack(2**32-1,0));sys.stdout.buffer.flush()', None, 'invalid_frame_length'),
            ('receive()\nsys.stdout.buffer.write(PREFIX.pack(1,1));sys.stdout.buffer.flush()', None, 'invalid_frame_length'),
        ]
        for script, limits, reason in cases:
            with self.subTest(reason=reason):
                path, receipt = self.run_client(script, limits=limits)
                self.assertEqual(receipt['status'], 'failed')
                self.assertEqual(receipt['reason'], reason)
                self.assertTrue((path / 'FAILED.json').exists())
                with self.assertRaises(ValueError):
                    t.audit_transport(path, self.dataset, 0, 'zero_shot')

    def test_changed_wire_image_or_missing_capture_refused(self):
        path, receipt = self.run_client('control()')
        self.assertEqual(receipt['status'], 'valid_unscored')
        target = path / 'transport/0000-out.bin'
        original = target.read_bytes()
        target.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(ValueError):
            t.audit_transport(path, self.dataset, 0, 'zero_shot')
        target.write_bytes(original)
        (path / 'transport/0001-in.bin').unlink()
        with self.assertRaises(OSError):
            t.audit_transport(path, self.dataset, 0, 'zero_shot')

    def test_client_stderr_and_post_final_failure_are_not_success(self):
        path, receipt = self.run_client("print('operator-like secret/path',file=sys.stderr)\ncontrol()\nraise RuntimeError('after final')")
        self.assertEqual(receipt['reason'], 'client_failed_after_final')
        self.assertNotEqual(receipt['client_exit_code'], 0)
        for p in (path / 'transport').glob('*-out.bin'):
            self.assertNotIn(b'operator-like secret/path', p.read_bytes())
        with self.assertRaises(ValueError):
            t.audit_transport(path, self.dataset, 0, 'zero_shot')

    def test_invalid_final_cli_exit_is_nonzero(self):
        client = self.client("receive()\nsend({'action':'finalize','response':'invalid'})\nreceive()")
        with patch.object(t.v, 'source', return_value=self.dataset), contextlib.redirect_stdout(io.StringIO()):
            code = t.main(['episode', '--packet', 'unused', '--ordinal', '0', '--mode', 'zero_shot',
                           '--output', str(self.root / 'cli-invalid'), '--client', str(client),
                           '--python', self.python, '--sandbox', 'protocol_only'])
        self.assertEqual(code, 2)
        self.assertEqual((self.root / 'cli-invalid/response.txt').read_bytes(), b'invalid')

    @unittest.skipUnless(sys.platform == 'darwin', 'Actual macOS sandbox proof runs on macOS only')
    def test_actual_client_sandbox_denies_operator_file_network_fork_and_environment(self):
        sentinel = self.root / 'operator-only.txt'; sentinel.write_text('not participant input')
        os.environ['NEURAL077_OPERATOR_SECRET'] = 'must not cross boundary'
        try:
            script = f"""
import ctypes, os, socket, subprocess
ready, _ = receive()
assert 'NEURAL077_OPERATOR_SECRET' not in os.environ
libc = ctypes.CDLL(None, use_errno=True)
mib = (ctypes.c_int * 3)(1, 49, os.getppid())
size = ctypes.c_size_t(65536)
memory = ctypes.create_string_buffer(size.value)
assert libc.sysctl(mib, 3, memory, ctypes.byref(size), None, 0) == -1
assert ctypes.get_errno() == 1
try:
    open({str(sentinel)!r}, 'rb').read()
except PermissionError:
    pass
else:
    raise AssertionError('Operator file accessible')
try:
    open({str(self.root / 'client-write.txt')!r}, 'w').write('leak')
except PermissionError:
    pass
else:
    raise AssertionError('File write permitted')
try:
    socket.socket().connect(('127.0.0.1', 9))
except PermissionError:
    pass
else:
    raise AssertionError('Network permitted')
try:
    subprocess.run(['/bin/echo','forbidden'],check=True)
except PermissionError:
    pass
else:
    raise AssertionError('Child process permitted')
send({{'action':'finalize','response':json.dumps({{'trial_id':ready['trial_id'],'target_probability':0.5}})}})
receive()
"""
            path, receipt = self.run_client(script, sandbox='macos')
            self.assertEqual(receipt['status'], 'valid_unscored', receipt)
            t.audit_transport(path, self.dataset, 0, 'zero_shot')
            self.assertFalse((self.root / 'client-write.txt').exists())
            (path / 'transport/sandbox.sb').write_text('(version 1) (allow default)')
            with self.assertRaisesRegex(ValueError, 'Sandbox policy mismatch'):
                t.audit_transport(path, self.dataset, 0, 'zero_shot')
        finally:
            del os.environ['NEURAL077_OPERATOR_SECRET']


if __name__ == '__main__':
    unittest.main()
