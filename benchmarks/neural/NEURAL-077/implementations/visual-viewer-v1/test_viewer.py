"""Generated engineering controls only; no labels, model predictions or scoring."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('viewer', HERE / 'viewer.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
r = v.load_module('raster', HERE / 'raster.py', (HERE / 'raster.py').read_bytes())
p = HERE.parent / 'direct-response/portable/response_contract.py'
parser = v.load_module('response_contract', p, p.read_bytes())


def fixture():
    # Invented impulses test preservation of a one-sample transient.
    data = [[0.0] * 1024 for _ in range(2)]
    data[0][257] = 50.0
    data[1][800] = -40.0
    row = {'trial_id': 'development-001-invented-fixture', 'channels': data}
    demos = [dict(row, target=i % 2) for i in range(4)]
    return {'rows': [row], 'demos': demos, 'parser': parser, 'packet': {'invented': '0' * 64}}


def pixels(png):
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    offset, compressed = 8, b''
    chunks = []
    while offset < len(png):
        n = struct.unpack('>I', png[offset:offset + 4])[0]
        name, body = png[offset + 4:offset + 8], png[offset + 8:offset + 8 + n]
        crc = struct.unpack('>I', png[offset + 8 + n:offset + 12 + n])[0]
        assert crc == zlib.crc32(name + body)
        chunks.append(name)
        if name == b'IDAT':
            compressed += body
        offset += 12 + n
    assert chunks == [b'IHDR', b'IDAT', b'IEND']
    scan = zlib.decompress(compressed)
    width = r.WIDTH * 3
    assert len(scan) == r.HEIGHT * (width + 1)
    assert all(scan[y * (width + 1)] == 0 for y in range(r.HEIGHT))
    return b''.join(scan[y * (width + 1) + 1:(y + 1) * (width + 1)] for y in range(r.HEIGHT))


def at(data, x, y):
    i = (y * r.WIDTH + x) * 3
    return tuple(data[i:i + 3])


class RasterTests(unittest.TestCase):
    def test_every_segment_drawn_and_transient_visible_at_full_width(self):
        state, row = v.initial_state(), fixture()['rows'][0]
        calls = []
        original = r.Canvas.line
        def line(canvas, x0, y0, x1, y1, color):
            if color == r.BLUE:
                calls.append((x0, y0, x1, y1))
            return original(canvas, x0, y0, x1, y1, color)
        with patch.object(r.Canvas, 'line', line):
            png = r.render(row, state, 'zero_shot')
        self.assertEqual(len(calls), 2 * 1023)
        data = pixels(png)
        self.assertEqual(at(data, r.sample_x(1, -256, 768), 220), r.BLUE)
        self.assertEqual(at(data, r.sample_x(544, -256, 768), 615), r.BLUE)
        self.assertEqual(png, r.render(row, state, 'zero_shot'))

    def test_zoom_keeps_impulse_and_exact_sample_geometry(self):
        state = dict(v.initial_state(), start_sample=-8, stop_sample=8, channels=['Cz'])
        png = r.render(fixture()['rows'][0], state, 'zero_shot')
        self.assertEqual(at(pixels(png), r.sample_x(1, -8, 8), 220), r.BLUE)
        self.assertEqual(r.sample_x(-256, -256, 768), r.LEFT)
        self.assertEqual(r.sample_x(768, -256, 768), r.RIGHT)
        self.assertLess(r.sample_x(767, -256, 768), r.RIGHT)

    def test_clipping_saturates_extreme_values_without_overflow(self):
        row = fixture()['rows'][0]
        row['channels'][0][257] = 1e300
        png = r.render(row, v.initial_state(), 'zero_shot')
        self.assertEqual(len(pixels(png)), r.WIDTH * r.HEIGHT * 3)
        canvas = r.Canvas()
        with patch.object(canvas, 'line') as draw:
            r.trace_segment(canvas, 0, 1000.0, 70, 0.0, 1, 295)
        draw.assert_called_once_with(70, 205, 70, 295, r.BLUE)


class ActionTests(unittest.TestCase):
    def test_unknown_extra_boolean_and_array_access_rejected(self):
        examples = [
            {'action': 'read_file', 'path': '/anywhere'}, {'action': 'export'},
            {'action': 'inspect', 'code': 'print(1)'}, {'action': 'gain', 'units_per_division': True},
            {'action': 'window', 'start_sample': False, 'stop_sample': 16},
            {'action': 'scroll', 'samples': 0}, {'action': 'zoom', 'factor': 2, 'center_sample': 900},
            {'action': 'channels', 'channels': ['Pz', 'Cz']}, {'action': 'filter', 'hz': 30},
            {'action': 'window', 'start_sample': 0, 'stop_sample': 15},
            {'action': 'window', 'start_sample': -257, 'stop_sample': 0},
        ]
        for request in examples:
            with self.subTest(request=request), self.assertRaises(ValueError):
                v.transition(v.initial_state(), request, 'zero_shot')

    def test_scroll_and_zoom_are_sample_exact(self):
        state = v.transition(v.initial_state(), {'action': 'zoom', 'factor': 2, 'center_sample': 0}, 'zero_shot')
        self.assertEqual((state['start_sample'], state['stop_sample']), (-256, 256))
        state = v.transition(state, {'action': 'scroll', 'samples': 256}, 'zero_shot')
        self.assertEqual((state['start_sample'], state['stop_sample']), (0, 512))
        state = v.transition(state, {'action': 'zoom', 'factor': 0.5, 'center_sample': 256}, 'zero_shot')
        self.assertEqual((state['start_sample'], state['stop_sample']), (-256, 768))

    def test_zero_shot_never_selects_demonstrations(self):
        with self.assertRaises(ValueError):
            v.transition(v.initial_state(), {'action': 'select', 'record': 'demo1'}, 'zero_shot')
        self.assertEqual(v.transition(v.initial_state(), {'action': 'select', 'record': 'demo1'}, 'four_demo')['record'], 'demo1')


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dataset = fixture()

    def tearDown(self):
        self.temp.cleanup()

    def session(self, mode='zero_shot'):
        return v.Session(self.dataset, 0, mode, self.root / 'session')

    def final(self, session, probability=0.25):
        response = json.dumps({'trial_id': self.dataset['rows'][0]['trial_id'], 'target_probability': probability})
        return session.handle(v.encode({'action': 'finalize', 'response': response}))

    def test_projected_response_has_only_raster_axes_and_permitted_label(self):
        session = self.session('four_demo')
        result = session.handle(b'{"action":"inspect"}')
        self.assertNotIn('target', result['display'])
        self.assertNotIn('demonstration_target', result['display'])
        self.assertEqual(result['display']['channels'], ['Cz', 'Pz'])
        self.assertEqual(result['display']['start_ms'], -250)
        self.assertEqual(result['display']['stop_ms_exclusive'], 750)
        self.assertEqual(result['display']['last_sample_ms'], 749.0234375)
        self.assertTrue(base64.b64decode(result['image']['base64']).startswith(b'\x89PNG'))
        self.assertNotIn('trial_id', result['display'])
        result = session.handle(b'{"action":"select","record":"demo1"}')
        self.assertEqual(result['display']['demonstration_target'], 0)
        self.assertEqual(result['display']['record'], 'demo1')
        self.assertNotIn('channels": [[', json.dumps(result))

    def test_invalid_first_final_is_preserved_and_cannot_be_replaced(self):
        session = self.session()
        first = session.handle(b'{"action":"finalize","response":"not JSON"}')
        self.assertEqual(first['status'], 'invalid_response')
        self.assertEqual((session.output / 'response.txt').read_bytes(), b'not JSON')
        before = (session.output / 'FINAL.json').read_bytes()
        self.assertEqual(self.final(session)['status'], 'closed')
        self.assertEqual((session.output / 'FINAL.json').read_bytes(), before)
        self.assertEqual(len(list(session.output.glob('action-*.json'))), 1)

    def test_replay_verifies_all_frames_and_response(self):
        session = self.session()
        session.handle(b'{"action":"inspect"}')
        session.handle(b'{"action":"zoom","factor":2,"center_sample":0}')
        self.final(session)
        self.assertEqual(v.audit_session(session.output, self.dataset, 0, 'zero_shot'), 0.25)
        frame = session.output / 'frames/0000.png'
        raw = bytearray(frame.read_bytes()); raw[-1] ^= 1; frame.write_bytes(raw)
        with self.assertRaises(ValueError):
            v.audit_session(session.output, self.dataset, 0, 'zero_shot')

    def test_rejected_duplicate_and_invalid_utf8_requests_retained(self):
        session = self.session()
        for raw in [b'{"action":"inspect","action":"export"}', b'\xff', b'{"action":"gain","units_per_division":NaN}']:
            self.assertEqual(session.handle(raw)['status'], 'rejected')
        self.final(session)
        self.assertEqual(v.audit_session(session.output, self.dataset, 0, 'zero_shot'), 0.25)

    def test_tampered_history_response_mode_and_packet_refused(self):
        session = self.session()
        self.final(session)
        with self.assertRaises(ValueError):
            v.audit_session(session.output, self.dataset, 0, 'four_demo')
        changed = dict(self.dataset, packet={'invented': '1' * 64})
        with self.assertRaises(ValueError):
            v.audit_session(session.output, changed, 0, 'zero_shot')
        (session.output / 'response.txt').write_text('{"trial_id":"different","target_probability":0.25}')
        with self.assertRaises(ValueError):
            v.audit_session(session.output, self.dataset, 0, 'zero_shot')

    def test_altered_actual_prompt_is_refused(self):
        session = self.session()
        self.final(session)
        (session.output / 'prompt.txt').write_text('Altered exposure')
        with self.assertRaisesRegex(ValueError, 'Stored prompt mismatch'):
            v.audit_session(session.output, self.dataset, 0, 'zero_shot')

    def test_changed_display_metadata_fails_even_with_recomputed_chain(self):
        session = self.session()
        session.handle(b'{"action":"inspect"}')
        self.final(session)
        first_path = session.output / 'action-0000.json'
        first = v.decode(first_path.read_bytes())
        first['detail']['display']['demonstration_target'] = 1
        first_path.write_bytes(v.encode(first))
        last_path = session.output / 'action-0001.json'
        last = v.decode(last_path.read_bytes())
        last['previous_sha256'] = v.digest(first_path.read_bytes())
        last_path.write_bytes(v.encode(last))
        final_path = session.output / 'FINAL.json'
        final = v.decode(final_path.read_bytes())
        final['last_action_sha256'] = v.digest(last_path.read_bytes())
        final_path.write_bytes(v.encode(final))
        with self.assertRaisesRegex(ValueError, 'Rendered metadata mismatch'):
            v.audit_session(session.output, self.dataset, 0, 'zero_shot')

    def test_reused_output_and_oversize_requests_fail_closed(self):
        session = self.session()
        with self.assertRaises(FileExistsError):
            self.session()
        self.assertEqual(session.handle(b'x' * (v.MAX_REQUEST + 1))['status'], 'closed')
        self.assertTrue((session.output / 'FAILED.json').exists())
        self.assertFalse((session.output / 'FINAL.json').exists())

    def test_action_budget_includes_rejections(self):
        session = self.session()
        for _ in range(v.MAX_ACTIONS):
            self.assertEqual(session.handle(b'{}')['status'], 'rejected')
        self.assertEqual(self.final(session)['status'], 'closed')
        self.assertFalse((session.output / 'response.txt').exists())

    def test_collector_requires_all400_even_when_one_valid_session_exists(self):
        session = self.session()
        self.final(session)
        with patch.object(v, 'source', return_value=self.dataset), self.assertRaises(ValueError):
            v.collect('unused', self.root, 'zero_shot', self.root / 'collection')
        self.assertTrue((self.root / 'collection/FAILED.json').exists())


if __name__ == '__main__':
    unittest.main()
