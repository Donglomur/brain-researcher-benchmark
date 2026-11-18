"""Generated protocol controls; no real EEG, credentials, provider or network.

Original Sender executes against an injected finite HTTP object. The two PNGs
are invented constant RGB canvases with the original canvas dimensions, created
only in memory. Temporary custody bytes, including failures, are accumulated.
"""
import base64
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve().parents[1]
FIXTURE_BYTES = 0
FIXTURE_CAP = 524288


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


client = load('generated_visual_client', HERE / 'visual_client.py')
bridge = load('generated_visual_bridge', HERE / 'visual_bridge.py')
codec = load('generated_visual_codec', HERE / 'transfer_png.py')


def png(value):
    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)
    # Invented pixels, never a raster or scientific observation.
    scanlines = (b'\0' + bytes([value]) * (1400 * 3)) * 820
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1400, 820, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scanlines, 9)) + chunk(b'IEND', b'')


class Alarm:
    """Signal enforcement belongs to existing sender controls, not this fixture."""
    def arm(self, deadline):
        self.deadline = deadline


class Response:
    status = 200
    def __init__(self, raw):
        self.raw, self.at, self.length = raw, 0, len(raw)
    def read(self, size):
        value = self.raw[self.at:self.at + size]
        self.at += len(value)
        self.length -= len(value)
        return value
    def getheader(self, key, default=None):
        return 'identity' if key.lower() == 'content-encoding' else default
    def close(self):
        pass


class HTTP:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.requests = []
    def __call__(self, host, port, timeout, context):
        assert host == 'api.openai.com' and port == 443 and timeout > 0
        owner = self
        class Connection:
            sock = None
            def set_debuglevel(self, level):
                assert level == 0
            def request(self, method, path, body, headers, encode_chunked):
                assert method == 'POST' and path == '/v1/responses' and not encode_chunked
                owner.requests.append(body)
            def getresponse(self):
                assert owner.bodies, 'Unplanned additional provider request'
                return Response(owner.bodies.pop(0))
            def close(self):
                pass
        return Connection()


def provider(action, identity='resp_generated_1', **changes):
    value = {'object': 'response', 'status': 'completed', 'error': None, 'incomplete_details': None,
             'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False, 'store': False,
             'truncation': 'disabled', 'previous_response_id': None, 'conversation': None,
             'model': 'generated-model', 'max_output_tokens': 100, 'id': identity,
             'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                         'content': [{'type': 'output_text', 'text': action.decode('utf-8')}]}],
             'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}
    value.update(changes)
    return bridge.encode(value)


def frame(header, image=b''):
    raw = bridge.encode(header)
    return bridge.PREFIX.pack(len(raw), len(image)) + raw + image


def rendered(image, record='query', remaining=126):
    display = {'record': record, 'channels': ['Cz', 'Pz'], 'start_sample': -256, 'stop_sample': 768}
    if record != 'query':
        display['demonstration_target'] = 1
    return {'status': 'rendered', 'display': display, 'remaining_actions': remaining,
            'image': {'mime_type': 'image/png', 'bytes': len(image)}}


def initial(trial_id, image):
    return {'status': 'ready', 'episode_id': 'a' * 32, 'trial_id': trial_id,
            'prompt': 'Generated scientific-interface fixture for ' + trial_id,
            'actions': {'description': 'Invented test interface; production loads original actions'},
            'limits': {'max_actions': 128, 'max_images': 32, 'max_request_bytes': 8192, 'max_image_bytes': 4194304},
            'instructions': 'Generated action control', 'initial': rendered(image, remaining=127)}


class VisualClientControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get('N077_IMPLEMENTATIONS_ROOT', str(HERE.parent))).resolve()
        cls.original = client.source(cls.root / 'waveform-provider-v1/client.py', client.ORIGINAL_SENDER)
        cls.images = [png(0), png(255)]
        cls.trial = 'development-001-' + '0' * 24

    def configuration(self, trial=None, **overrides):
        value = {'schema': 'neural077_visual_provider_client_v1', 'model': 'generated-model',
                 'max_output_tokens': 100, 'deadline': time.monotonic() + 30,
                 'trial_id': trial or self.trial, 'implementations_root': str(self.root),
                 'source_bindings': {'waveform-provider-v1/client.py': client.ORIGINAL_SENDER},
                 'sender_path': str(self.root / 'waveform-provider-v1/client.py'), 'sender_pin': client.ORIGINAL_SENDER,
                 'bridge_path': str(HERE / 'visual_bridge.py'), 'bridge_pin': client.pin((HERE / 'visual_bridge.py').read_bytes()),
                 'codec_path': str(HERE / 'transfer_png.py'), 'codec_pin': client.pin((HERE / 'transfer_png.py').read_bytes()),
                 'max_request_bytes': 8388608, 'max_requests': 127,
                 'max_query_request_bytes': 512 * 1024 * 1024, 'max_query_response_bytes': 128 * 1024 * 1024}
        value.update(overrides)
        return client.configuration(client.encoded(value))

    def exercise(self, bodies, incoming, cfg=None, credential='SYNTHETIC_CREDENTIAL_7', hook=None):
        global FIXTURE_BYTES
        cfg = cfg or self.configuration()
        http, outgoing = HTTP(bodies), io.BytesIO()
        with tempfile.TemporaryDirectory(prefix='generated-n077-visual-') as tmp:
            root = Path(tmp).resolve()
            root.chmod(0o700)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                if hook is None:
                    success = client.serve(cfg, client.pin(client.encoded(cfg)), credential, fd, self.original,
                                           bridge, codec, Alarm(), io.BytesIO(incoming), outgoing, http_factory=http)
                else:
                    with hook:
                        success = client.serve(cfg, client.pin(client.encoded(cfg)), credential, fd, self.original,
                                               bridge, codec, Alarm(), io.BytesIO(incoming), outgoing, http_factory=http)
                saved = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            finally:
                os.close(fd)
                created = sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
                FIXTURE_BYTES += created
                self.assertLessEqual(FIXTURE_BYTES, FIXTURE_CAP, 'All temporary writes, including failures, exceed declared bound')
        return success, http.requests, outgoing.getvalue(), saved

    def final(self, response=None, status='valid_unscored'):
        response = response or bridge.encode({'trial_id': self.trial, 'target_probability': 0.5})
        action = bridge.encode({'action': 'finalize', 'response': response.decode()})
        terminal = {'status': status, 'response_sha256': bridge.pin(response)['sha256'], 'terminal': True}
        return action, terminal

    def test_full_history_images_and_first_final(self):
        select = bridge.encode({'action': 'select', 'record': 'demo1'})
        final, terminal = self.final()
        incoming = frame(initial(self.trial, self.images[0]), self.images[0]) + frame(rendered(self.images[1], 'demo1'), self.images[1]) + frame(terminal)
        ok, requests, output, saved = self.exercise([provider(select), provider(final, 'resp_generated_2')], incoming)
        self.assertTrue(ok)
        self.assertEqual(len(requests), 2)
        values = [bridge.decode(raw) for raw in requests]
        self.assertEqual(values[1]['input'][:1], values[0]['input'])
        self.assertEqual(values[1]['input'][1]['content'][0]['text'], select.decode())
        image_urls = [part['image_url'] for row in values[1]['input'] for part in row['content'] if part['type'] == 'input_image']
        self.assertEqual(len(image_urls), 2)
        for url, image in zip(image_urls, self.images):
            delivered = base64.b64decode(url.split(',', 1)[1], validate=True)
            self.assertEqual(delivered, codec.encode_transport_image(image)[0])
        self.assertNotIn('previous_response_id', values[1])
        self.assertEqual(output, frame(bridge.decode(select)) + frame(bridge.decode(final)))
        end = client.decode(saved['CLIENT_END.json'])
        self.assertEqual(end['status'], 'closed_first_final')
        self.assertEqual(end['request_bytes'], sum(map(len, requests)))
        self.assertFalse(end['response_charge_contains_upper_bound'])

    def test_invalid_first_final_stays_terminal(self):
        final, terminal = self.final(b'not a valid scalar', 'invalid_response')
        incoming = frame(initial(self.trial, self.images[0]), self.images[0]) + frame(terminal)
        ok, requests, output, saved = self.exercise([provider(final), provider(final, 'resp_forbidden_second')], incoming)
        self.assertFalse(ok)
        self.assertEqual(len(requests), 1)
        self.assertTrue(output)
        self.assertTrue(client.decode(saved['CLIENT_END.json'])['first_finalize_terminal'])

    def test_bounded_rejected_action_is_preserved_in_next_history(self):
        invalid = b'{ "action" : "window", "start_sample" : 700, "stop_sample" : 500 }\n'
        rejection = {'status': 'rejected', 'error': 'Invalid action or parameters', 'remaining_actions': 126}
        final, terminal = self.final()
        incoming = frame(initial(self.trial, self.images[0]), self.images[0]) + frame(rejection) + frame(terminal)
        ok, requests, output, saved = self.exercise([provider(invalid), provider(final, 'resp_after_rejection')], incoming)
        self.assertTrue(ok)
        self.assertEqual(len(requests), 2)
        second = bridge.decode(requests[1])['input']
        self.assertEqual(second[1]['content'][0]['text'].encode(), invalid)
        self.assertEqual(bridge.decode(second[2]['content'][0]['text'].encode()), rejection)
        self.assertEqual(output, bridge.PREFIX.pack(len(invalid), 0) + invalid + bridge.PREFIX.pack(len(final), 0) + final)

    def test_tools_refusals_incomplete_and_duplicate_ids_fail(self):
        final, terminal = self.final()
        first = frame(initial(self.trial, self.images[0]), self.images[0])
        for extra in ({'output': [{'type': 'function_call'}]}, {'status': 'incomplete'},
                      {'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'refusal', 'refusal': 'no'}]}]}):
            with self.subTest(extra=extra):
                ok, requests, output, saved = self.exercise([provider(final, **extra)], first)
                self.assertFalse(ok)
                self.assertEqual(len(requests), 1)
                self.assertEqual(output, b'')
        inspect = bridge.encode({'action': 'inspect'})
        incoming = first + frame(rendered(self.images[0]), self.images[0])
        ok, requests, output, saved = self.exercise([provider(inspect), provider(final)], incoming)
        self.assertFalse(ok)
        self.assertEqual(len(requests), 2)
        self.assertEqual(output, frame(bridge.decode(inspect)))

    def test_cumulative_full_history_cap_fails_without_truncating(self):
        inspect = bridge.encode({'action': 'inspect'})
        start = initial(self.trial, self.images[0])
        history, _ = bridge.first_frame(start, self.images[0], self.trial, codec.encode_transport_image)
        first_bytes = len(bridge.request_body(history, 'generated-model', 100))
        second_history, _ = bridge.append_frame(history, inspect, rendered(self.images[1]), self.images[1], codec.encode_transport_image)
        second_bytes = len(bridge.request_body(second_history, 'generated-model', 100))
        self.assertGreater(second_bytes, first_bytes)
        # Each request fits individually; only their cumulative sum fails.
        cfg = self.configuration(max_request_bytes=second_bytes, max_query_request_bytes=second_bytes)
        incoming = frame(start, self.images[0]) + frame(rendered(self.images[1]), self.images[1])
        ok, requests, output, saved = self.exercise([provider(inspect)], incoming, cfg)
        self.assertFalse(ok)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0], bridge.request_body(history, 'generated-model', 100))

    def test_escaped_final_credential_never_reaches_viewer(self):
        secret = 'SYNTHETIC_CREDENTIAL_7'
        escaped = ''.join('\\u%04x' % ord(char) for char in secret)
        action = ('{"action":"finalize","response":"' + escaped + '"}').encode()
        raw = provider(action)
        self.assertNotIn(secret.encode(), raw)
        ok, requests, output, saved = self.exercise([raw], frame(initial(self.trial, self.images[0]), self.images[0]), credential=secret)
        self.assertFalse(ok)
        self.assertEqual(output, b'')
        receipt = client.decode(saved['000/BRIDGE.json'])
        self.assertEqual(receipt['status'], 'failed_no_action')
        self.assertIsNone(receipt['action'])
        self.assertNotIn(secret.encode(), saved['CLIENT_END.json'])

    def test_fresh_queries_have_no_cross_query_history(self):
        for index in (0, 1):
            trial = 'development-001-' + str(index) * 24
            response = bridge.encode({'trial_id': trial, 'target_probability': 0.5})
            final, terminal = self.final(response)
            ok, requests, output, saved = self.exercise([provider(final, 'resp_fresh_' + str(index))],
                frame(initial(trial, self.images[index]), self.images[index]) + frame(terminal), self.configuration(trial))
            self.assertTrue(ok)
            request = bridge.decode(requests[0])
            self.assertEqual(len(request['input']), 1)
            self.assertIn(trial, request['input'][0]['content'][0]['text'])
            self.assertEqual(client.decode(saved['CLIENT_END.json'])['turns'], 1)

    def test_failed_sender_charged_finite_upper_bound(self):
        raw = b'SYNTHETIC_CREDENTIAL_7'
        cfg = self.configuration(max_query_response_bytes=128)
        ok, requests, output, saved = self.exercise([raw], frame(initial(self.trial, self.images[0]), self.images[0]), cfg)
        self.assertFalse(ok)
        end = client.decode(saved['CLIENT_END.json'])
        self.assertEqual(end['response_bytes'], 128)
        self.assertTrue(end['response_charge_contains_upper_bound'])
        self.assertEqual(output, b'')

    def test_turn_setup_refusal_closes_owned_descriptor(self):
        opened = []
        def refused(fd, *args):
            opened.append(fd)
            raise ValueError('Generated custody setup refusal')
        final, terminal = self.final()
        ok, requests, output, saved = self.exercise([provider(final)],
            frame(initial(self.trial, self.images[0]), self.images[0]), hook=patch.object(self.original, 'Custody', refused))
        self.assertFalse(ok)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])
        self.assertEqual(requests, [])


def tearDownModule():
    print(json.dumps({'schema': 'neural077_visual_client_generated_fixture_accounting_v1',
                      'cumulative_temporary_file_bytes': FIXTURE_BYTES, 'finite_upper_bound': FIXTURE_CAP,
                      'original_payloads_read': False, 'real_provider_requests': 0}, sort_keys=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
