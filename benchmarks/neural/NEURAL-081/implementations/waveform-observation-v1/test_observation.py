"""Generated engineering controls only; no authentic neural inputs or targets."""
import base64
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural081_observation', HERE/'observation.py')
obs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = obs
spec.loader.exec_module(obs)


def npy(values=None, *, header=None, version=1):
    if header is None:
        header = {'descr':'<f4','fortran_order':False,'shape':(64,512)}
    text = repr(header).encode('ascii') + b'\n'
    size = struct.pack('<H' if version == 1 else '<I', len(text))
    body = b'\0'*131072 if values is None else struct.pack('<32768f', *values)
    return b'\x93NUMPY' + bytes((version,0)) + size + text + body


def decode_png(encoded):
    data = base64.b64decode(encoded)
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, chunks, compressed = 8, [], b''
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        body = data[offset+8:offset+8+length]
        crc = struct.unpack('>I', data[offset+8+length:offset+12+length])[0]
        assert crc == zlib.crc32(kind+body)
        chunks.append(kind)
        if kind == b'IHDR':
            assert struct.unpack('>IIBBBBB', body) == (1168,1080,8,2,0,0,0)
        if kind == b'IDAT':
            compressed += body
        offset += 12+length
    assert chunks == [b'IHDR', b'IDAT', b'IEND']  # No numerical/text payload chunks.
    raw = zlib.decompress(compressed)
    assert len(raw) == 1080*(1+1168*3)
    assert all(raw[y*(1+1168*3)] == 0 for y in range(1080))
    return raw


def pixel(raw, x, y):
    start = y*(1+1168*3)+1+x*3
    return tuple(raw[start:start+3])


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flat = obs.prepare_observation(npy(), context_alias='a'*32, view='EEG')
        cls.zero = obs.prepare_observation(npy(), context_alias='b'*32, view='ZERO')
        values = [0.0]*32768
        values[17] = 50e-6       # An off-grid transient must survive rendering.
        values[511] = -50e-6    # Last sample must be present, not truncated.
        values[16*512+41] = 1e-3
        values[63*512+42] = -1e-3
        cls.impulses = obs.prepare_observation(npy(values), context_alias='c'*32, view='EEG')

    def test_nonconsecutive_labels_and_source_channel_order(self):
        # Independent source correspondence, not duplicated expected constants.
        root = HERE.parents[1]
        protocol = root/'implementations/programme-source/implementation-v1/installation-v1/acyclic-parent-v1/program/protocol.py'
        import ast
        assignments = {}
        for node in ast.parse(protocol.read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == 'CHANNELS':
                    assignments['CHANNELS'] = ast.literal_eval(node.value)
        self.assertEqual(obs.CHANNELS, assignments['CHANNELS'])
        self.assertEqual(self.flat.metadata()['class_ids'], [1,2,3,4,11,12,13,14,21,22,23,24])

    def test_direct_and_viewer_have_identical_complete_images(self):
        bundle = self.impulses.direct()
        channels = []
        for page in range(4):
            response = self.impulses.page({'action':'view_page','page':page})
            self.assertEqual(bundle['images'][page], response)
            channels.extend(response['channels'])
            decode_png(response['image_base64'])
        self.assertEqual(channels, list(obs.CHANNELS))

    def test_voltage_gain_time_geometry_and_every_sample(self):
        raw = decode_png(self.impulses.page({'action':'view_page','page':0})['image_base64'])
        self.assertEqual(pixel(raw,120+2*17,100-11), obs.TRACE)
        self.assertEqual(pixel(raw,120+2*511,100+11), obs.TRACE)
        self.assertEqual(pixel(raw,120+2*17,100-22), obs.BACKGROUND)
        # Adjacent untouched channel remains at the same fixed baseline.
        self.assertEqual(pixel(raw,120+2*17,156), obs.TRACE)

    def test_page_mapping_and_visible_positive_negative_clipping(self):
        page1 = decode_png(self.impulses.page({'action':'view_page','page':1})['image_base64'])
        page3 = decode_png(self.impulses.page({'action':'view_page','page':3})['image_base64'])
        self.assertEqual(pixel(page1,120+2*41,100-22), obs.CLIPPED)
        self.assertEqual(pixel(page3,120+2*42,100+15*56+22), obs.CLIPPED)

    def test_fixed_scale_and_zero_waveform_geometry_match(self):
        a = decode_png(self.flat.page({'action':'view_page','page':0})['image_base64'])
        b = decode_png(self.zero.page({'action':'view_page','page':0})['image_base64'])
        # Headers distinguish the disclosed view; all trace and axis rows match.
        self.assertEqual(a[75*(1+1168*3):], b[75*(1+1168*3):])

    def test_projection_has_no_arrays_labels_or_source_identity(self):
        result = self.impulses.direct()
        self.assertEqual(set(vars(self.impulses)), {'context_alias','view','_frames'})
        self.assertTrue(all(type(frame) is bytes for frame in self.impulses._frames))
        self.assertEqual(set(result), {'metadata','images'})
        for image in result['images']:
            self.assertEqual(set(image), {'context_alias','view','page','channels','mime_type','width','height','sha256','image_base64'})
        for forbidden in ('private_label','source_event_index','participant','filename','raw_array'):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_rejects_unsupported_viewer_actions_and_boolean_pages(self):
        for action in ({'action':'view_page','page':True}, {'action':'view_page','page':-1},
                       {'action':'view_page','page':4}, {'action':'view_page','page':0,'scale':1},
                       {'action':'raw'}, {'action':'view_page','page':0.0}):
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.flat.page(action)

    def test_rejects_wrong_dtype_shape_layout_and_extent(self):
        for patch in ({'descr':'<f8'}, {'descr':'|O'}, {'shape':(512,64)},
                      {'fortran_order':True}, {'shape':[64,512]}, {'unexpected':0}):
            header = {'descr':'<f4','fortran_order':False,'shape':(64,512),**patch}
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                obs.prepare_observation(npy(header=header), context_alias='d'*32, view='EEG')
        for payload in (npy()[:-1], npy()+b'x', b'not npy', npy().replace(b'NUMPY',b'PICKL',1)):
            with self.assertRaises(ValueError):
                obs.prepare_observation(payload, context_alias='d'*32, view='EEG')

    def test_rejects_nonfinite_and_nonpositive_zero_view(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            values = [0.0]*32768
            values[53] = value
            with self.assertRaises(ValueError):
                obs.prepare_observation(npy(values), context_alias='d'*32, view='EEG')
        for value in (-0.0, 1e-40, 0.1):
            values = [0.0]*32768
            values[51] = value
            with self.assertRaises(ValueError):
                obs.prepare_observation(npy(values), context_alias='d'*32, view='ZERO')

    def test_header_v2_same_values_and_opaque_alias_validation(self):
        self.assertEqual(obs._window(npy(version=2),'EEG'), obs._window(npy(),'EEG'))
        for alias in ('person-P01', 'A'*32, '../private/target', 'a'*31, 123):
            with self.assertRaises(ValueError):
                obs.prepare_observation(npy(), context_alias=alias, view='EEG')


if __name__ == '__main__':
    unittest.main()
