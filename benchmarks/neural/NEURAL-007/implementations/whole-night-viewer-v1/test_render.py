"""Generated-only trace geometry checks using the unchanged raster dependency."""
import copy
import importlib.util
import math
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


r = module('sleep_render', HERE / 'render.py')
RASTER_PATH = HERE.parents[2] / 'NEURAL-077/implementations/visual-viewer-v1/raster.py'
raster = module('existing_eeg_raster', RASTER_PATH)


class RecordingCanvas:
    def __init__(self):
        self.lines = []
        self.texts = []
        self.pixels = []

    def line(self, *args):
        self.lines.append(args)

    def text(self, x, y, text, color=raster.BLACK, scale=2):
        # Exercise the existing font's exact alphabet and actual text extents.
        assert all(c in raster.FONT for c in text.upper()), text
        assert 0 <= x and x + len(text) * 6 * scale <= raster.WIDTH, text
        assert 0 <= y and y + 7 * scale <= raster.HEIGHT, text
        self.texts.append((x, y, text, color, scale))

    def pixel(self, *args):
        self.pixels.append(args)

    def png(self):
        return b'generated-recording-canvas'


def spy_raster():
    canvas = RecordingCanvas()
    calls = []
    def trace(*args):
        calls.append(args[1:])
        return raster.trace_segment(*args)
    supplied = types.SimpleNamespace(**{name: getattr(raster, name) for name in
                                        ('WIDTH', 'HEIGHT', 'LEFT', 'RIGHT', 'BLACK', 'GRID', 'BLUE', 'RED')})
    supplied.Canvas = lambda: canvas
    supplied.trace_segment = trace
    return supplied, canvas, calls


def render_spy(data, supplied):
    # Geometry controls keep their recording canvas; real scanline/codec checks
    # below independently exercise the full unmodified raster and compression.
    with patch.object(r, 'compress_png', side_effect=lambda body: body):
        return r.render(**data, raster=supplied)


def png_scanlines(body):
    assert body[:8] == b'\x89PNG\r\n\x1a\n'
    offset, names, compressed = 8, [], b''
    dimensions = None
    while offset < len(body):
        size = struct.unpack('>I', body[offset:offset + 4])[0]
        name = body[offset + 4:offset + 8]
        data = body[offset + 8:offset + 8 + size]
        checksum = struct.unpack('>I', body[offset + 8 + size:offset + 12 + size])[0]
        assert zlib.crc32(name + data) == checksum
        names.append(name)
        if name == b'IHDR':
            dimensions = struct.unpack('>IIBBBBB', data)
        elif name == b'IDAT':
            compressed += data
        offset += 12 + size
    assert offset == len(body) and names == [b'IHDR', b'IDAT', b'IEND']
    assert dimensions == (1400, 820, 8, 2, 0, 0, 0)
    scan = zlib.decompress(compressed)
    assert len(scan) == (1400 * 3 + 1) * 820
    assert all(scan[y * (1400 * 3 + 1)] == 0 for y in range(820))
    return scan


def decode_png(body):
    scan = png_scanlines(body)
    def pixel(x, y):
        index = y * (1400 * 3 + 1) + 1 + x * 3
        return tuple(scan[index:index + 3])
    return pixel


class RenderChecks(unittest.TestCase):
    def inputs(self, width=100, start=0, target=0, channels=None):
        channels = list(r.CHANNELS) if channels is None else channels
        return dict(epoch_id='person-001/night-1/epoch-000000', start_sample=start,
                    channel_names=channels, channel_values_volts=[[0.] * width for _ in channels],
                    gain_uv=50, clock_features={'elapsed_hours': target / 360000,
                                               'wall_clock_sin': 0., 'wall_clock_cos': 1.},
                    target_start_sample=target)

    def test_png_is_repeatable_raster_only_with_positive_up_and_volt_conversion(self):
        data = self.inputs(channels=['EEG Fpz-Cz'])
        data['channel_values_volts'][0] = [25e-6] * 100
        image = r.render(**data, raster=raster)
        self.assertEqual(image, r.render(**data, raster=raster))
        pixel = decode_png(image)
        self.assertEqual(pixel(740, 285 - 15), raster.BLUE)
        self.assertNotEqual(pixel(740, 285 + 15), raster.BLUE)

    def test_every_sample_and_adjacent_segment_retained_at_full_60_second_width(self):
        data = self.inputs(width=6000, channels=['EEG Fpz-Cz'])
        data['channel_values_volts'][0][4173] = 100e-6
        spy, canvas, calls = spy_raster()
        self.assertEqual(render_spy(data, spy), b'generated-recording-canvas')
        self.assertEqual(len(calls), 5999)
        self.assertEqual(sum(call[1] == 100e-6 or call[3] == 100e-6 for call in calls), 2)
        self.assertEqual(calls[0][0], raster.LEFT)
        self.assertEqual(calls[-1][2], r.sample_x(5999, 0, 6000, raster))
        self.assertEqual(calls[4172][3], 100e-6)
        self.assertTrue(any(min(line[1], line[3]) < 285 for line in canvas.lines if line[-1] == raster.BLUE))

    def test_all_three_channels_fit_original_canvas_and_long_safe_identity(self):
        data = self.inputs(width=3000)
        data['epoch_id'] = 'x' * 96
        data['gain_uv'] = 1000
        spy, canvas, calls = spy_raster()
        render_spy(data, spy)
        self.assertEqual(len(calls), 3 * 2999)
        self.assertEqual({call[-1] for call in calls}, {285, 485, 685})
        self.assertTrue(all(0 <= line[1] < 820 and 0 <= line[3] < 820 for line in canvas.lines))

    def test_half_open_target_highlight_clips_span_without_inventing_edge_boundary(self):
        data = self.inputs(width=4000, start=1000, target=3000, channels=['EOG horizontal'])
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        red = [line for line in canvas.lines if line[-1] == raster.RED]
        self.assertEqual(red, [(740, 198, 1300, 198, raster.RED), (740, 195, 740, 375, raster.RED)])
        data = self.inputs(width=1000, start=6000, target=3000, channels=['EOG horizontal'])
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        self.assertFalse([line for line in canvas.lines if line[-1] == raster.RED])

    def test_absolute_sample_time_does_not_wrap_after_midnight(self):
        data = self.inputs(width=3000, start=8640000, target=8640000, channels=['EEG Pz-Oz'])
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        labels = [entry[2] for entry in canvas.texts]
        self.assertIn('86400.00', labels)
        self.assertIn('86430.00', labels)
        self.assertTrue(any('LAST SAMPLE 86429.99 S' in s for s in labels))
        self.assertTrue(any('ROUNDED TO 6 SIGNIFICANT DIGITS: H=24 ' in s for s in labels))

    def test_extreme_finite_volts_never_overflow_and_crossing_uses_fraction_clip(self):
        data = self.inputs(channels=['EEG Fpz-Cz'])
        data['channel_values_volts'][0] = [sys.float_info.max, -sys.float_info.max] + [0.] * 98
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        trace = [line for line in canvas.lines if line[-1] == raster.BLUE]
        self.assertTrue(trace)
        self.assertTrue(all(195 <= line[1] <= 375 and 195 <= line[3] <= 375 for line in trace))
        self.assertTrue(any('CLIPPED' in row[2] for row in canvas.texts))
        probe = RecordingCanvas()
        raster.trace_segment(probe, 180, 1e308, 1300, -1e308, 50 / 1e6, 285)
        self.assertEqual(probe.lines, [(740, 195, 740, 375, raster.BLUE)])

    def test_clipped_same_side_segment_is_not_false_flat_boundary(self):
        data = self.inputs(channels=['EEG Fpz-Cz'])
        data['channel_values_volts'][0] = [1e308] * 100
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        self.assertFalse([line for line in canvas.lines if line[-1] == raster.BLUE])
        self.assertFalse(canvas.pixels)
        self.assertTrue(any('CLIPPED' in row[2] for row in canvas.texts))

    def test_scientific_data_and_clock_rejections_precede_canvas_creation(self):
        changes = [
            {'epoch_id': 'unsafe\nidentity'}, {'epoch_id': 'x' * 97}, {'epoch_id': 'nonASCII\u03b2'},
            {'start_sample': True}, {'start_sample': -1}, {'target_start_sample': True},
            {'target_start_sample': 1}, {'target_start_sample': -3000},
            {'channel_names': []}, {'channel_names': ['EOG horizontal', 'EEG Fpz-Cz']},
            {'channel_names': ['EEG Fpz-Cz', 'EEG Fpz-Cz']}, {'channel_names': ['EEG arbitrary']},
            {'channel_values_volts': [[0.] * 99] * 3}, {'channel_values_volts': [[0.] * 6001] * 3},
            {'channel_values_volts': [[0.] * 100, [0.] * 101, [0.] * 100]},
            {'gain_uv': True}, {'gain_uv': 0}, {'gain_uv': 50.}, {'gain_uv': 5},
            {'clock_features': {'elapsed_hours': math.inf, 'wall_clock_sin': 0., 'wall_clock_cos': 1.}},
            {'clock_features': {'elapsed_hours': 0., 'wall_clock_sin': True, 'wall_clock_cos': 1.}},
            {'clock_features': {'elapsed_hours': 0., 'wall_clock_sin': 0., 'wall_clock_cos': 1., 'stage': 'W'}},
        ]
        for value in (True, math.nan, math.inf, -math.inf, 10 ** 400, '0'):
            rows = [[0.] * 100 for _ in r.CHANNELS]
            rows[-1][-1] = value
            changes.append({'channel_values_volts': rows})
        for change in changes:
            with self.subTest(change=tuple(change)):
                data = self.inputs()
                data.update(change)
                sentinel = types.SimpleNamespace(Canvas=lambda: self.fail('Canvas created before rejection'))
                with self.assertRaises(ValueError):
                    r.render(**data, raster=sentinel)

    def test_image_rounding_never_changes_clock_arguments(self):
        data = self.inputs(start=3000, target=3000)
        data['clock_features'].update(wall_clock_sin=math.sin(.123456789), wall_clock_cos=math.cos(.123456789))
        original = copy.deepcopy(data)
        spy, canvas, _ = spy_raster()
        render_spy(data, spy)
        self.assertEqual(data, original)
        self.assertTrue(any('ROUNDED TO 6 SIGNIFICANT DIGITS' in row[2] for row in canvas.texts))

    def test_stored_clock_precision_is_not_rejected_by_new_trigonometric_rules(self):
        data = self.inputs(start=3000, target=3000)
        data['clock_features'] = {'elapsed_hours': 0.008333333767950535,
                                  'wall_clock_sin': 0.12314341217279434,
                                  'wall_clock_cos': 0.992388904094696}
        before = copy.deepcopy(data['clock_features'])
        spy, _, _ = spy_raster()
        render_spy(data, spy)
        self.assertEqual(data['clock_features'], before)

    def test_lossless_codec_matches_every_original_pixel_for_generated_traces(self):
        cases = [self.inputs(), self.inputs(width=3000), self.inputs(width=777, start=3123, target=3000)]
        cases[1]['channel_values_volts'] = [
            [75e-6 * math.sin(i * .17) for i in range(3000)],
            [25e-6 if i % 7 == 0 else -25e-6 for i in range(3000)],
            [sys.float_info.max if i == 1500 else -sys.float_info.max if i == 1501 else 0. for i in range(3000)],
        ]
        for case in cases:
            with self.subTest(width=len(case['channel_values_volts'][0])):
                with patch.object(r, 'compress_png', side_effect=lambda body: body):
                    original = r.render(**case, raster=raster)
                compressed = r.render(**case, raster=raster)
                self.assertEqual(png_scanlines(original), png_scanlines(compressed))
                self.assertLess(len(compressed), len(original))
                self.assertEqual(r.compress_png(original), compressed)

    def test_codec_rejects_corruption_unknown_chunks_or_changed_pixel_mode(self):
        with patch.object(r, 'compress_png', side_effect=lambda body: body):
            original = r.render(**self.inputs(), raster=raster)
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
        bad_crc = bytearray(original)
        bad_crc[32] ^= 1
        changed_mode = original[:8] + chunk(b'IHDR', struct.pack('>IIBBBBB', 1400, 820, 8, 6, 0, 0, 0)) + original[33:]
        extra_text = original[:-12] + chunk(b'tEXt', b'unexpected metadata') + original[-12:]
        for body in (bytes(bad_crc), original[:-1], changed_mode, extra_text, original + b'trailing'):
            with self.subTest(size=len(body)):
                with self.assertRaises(ValueError):
                    r.compress_png(body)

    def test_codec_rejects_changed_filters_extra_stream_or_decompression_overrun(self):
        with patch.object(r, 'compress_png', side_effect=lambda body: body):
            original = r.render(**self.inputs(), raster=raster)
        scan = png_scanlines(original)
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
        def replacement(data):
            return original[:33] + chunk(b'IDAT', data) + original[-12:]
        changed_filter = b'\x01' + scan[1:]
        cases = (zlib.compress(changed_filter), zlib.compress(scan) + zlib.compress(b'extra'),
                 zlib.compress(scan + b'overrun'), zlib.compress(scan[:-1]))
        for compressed in cases:
            with self.subTest(size=len(compressed)):
                with self.assertRaises(ValueError):
                    r.compress_png(replacement(compressed))


if __name__ == '__main__':
    unittest.main(verbosity=2)
