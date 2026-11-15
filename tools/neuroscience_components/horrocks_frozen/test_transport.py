"""Invented byte/arithmetic/wire controls only; no authentic model inputs."""
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import unittest

HERE = Path(__file__).absolute().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


p = load('predict_one'); e = load('convert_model')


def array(dtype, shape, values, order=False, version=1):
    header = repr({'descr': dtype, 'fortran_order': order, 'shape': shape}).encode('ascii') + b'\n'
    prefix = b'\x93NUMPY' + bytes([version, 0]) + len(header).to_bytes(2 if version == 1 else 4, 'little')
    raw = bytes(values) if dtype == '|b1' else struct.pack(('<' if dtype[0] == '<' else '>') + str(len(values)) + 'd', *values)
    return prefix + header + raw


def triples(order=False, endian='<'):
    rows = [[0., 1., 2., 3., 4., 5.], [6., 7., 8., 9., 10., 11.]]
    flat = [rows[i][j] for j in range(6) for i in range(2)] if order else sum(rows, [])
    return (array('|b1', (3,), [1, 0, 1]), array(endian+'f8', (2, 6), flat, order),
            array(endian+'f8', (6,), [0., 0., 0., 0., 0., 0.]))


def model():
    return p.strict_json(e.convert(*triples(), p))


def request(counts=None):
    return {'schema': 'horrocks-current-window-v1', 'token': 'a'*64, 'counts': counts or [2, 0, 1]}


class Transport(unittest.TestCase):
    def test_source_order_and_ignored_units(self):
        m = model(); self.assertEqual(m['selected_indices'], [0, 2]); self.assertEqual(m['feature_count'], 3)
        self.assertEqual(p.predict(m, [2, 2147483647, 1]), 6)

    def test_fortran_and_big_endian(self):
        expected = e.convert(*triples(), p)
        self.assertEqual(e.convert(*triples(True, '>'), p), expected)

    def test_npy_version_two(self):
        self.assertEqual(e.npy(array('>f8', (6,), [0.]*6, version=2), 'intercept'), ((6,), [0.]*6))

    def test_empty_mask_lowest_tie(self):
        raw = e.convert(array('|b1', (3,), [0, 0, 0]), array('<f8', (0, 6), []), array('<f8', (6,), [0.]*6), p)
        self.assertEqual(p.predict(p.strict_json(raw), [0, 0, 0]), 1)
        bad = p.strict_json(raw); bad['intercept'][1] = 1.
        with self.assertRaisesRegex(ValueError, 'uniform'): p.validate_model(bad)

    def test_exact_tie_lowest_class(self):
        m = model(); m['beta'] = [[0.]*6 for _ in m['beta']]; m['intercept'] = [0., 4., 4., 2., 1., 0.]
        self.assertEqual(p.predict(m, [9, 9, 9]), 2)

    def test_documented_fsum_cancellation(self):
        m = model(); m['beta'] = [[1.e16, 0., 0., 0., 0., 0.], [-1.e16, 0., 0., 0., 0., 0.]]
        m['intercept'] = [1., 0.5, 0., 0., 0., 0.]
        self.assertEqual(p.predict(m, [1, 0, 1]), 1)
        self.assertEqual((1. + 1.e16) - 1.e16, 0.)  # distinct arithmetic is intentional

    def test_binary64_roundtrip_signedzero_subnormal(self):
        values = [-0., math.ulp(0.), -math.ulp(0.), 1., 0., 0.]
        raw = e.convert(array('|b1', (1,), [1]), array('<f8', (1, 6), values), array('<f8', (6,), [-0.]*6), p)
        m = p.strict_json(raw)
        self.assertEqual([struct.pack('>d', x) for x in values], [struct.pack('>d', x) for x in m['beta'][0]])

    def test_shape_join_and_width_refusals(self):
        a, b, c = triples()
        with self.assertRaisesRegex(ValueError, 'mask/beta'): e.convert(array('|b1', (3,), [1, 0, 0]), b, c, p)
        with self.assertRaisesRegex(ValueError, 'query axis'): p.predict(model(), [1, 2])

    def test_counts_types_and_ranges(self):
        for values in ([True, 0, 0], [1., 0, 0], [-1, 0, 0], [2147483648, 0, 0]):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'int32'): p.predict(model(), values)

    def test_nonfinite_coefficients_and_product(self):
        a, b, c = triples(); values = [math.inf]*12
        with self.assertRaisesRegex(ValueError, 'finite'): e.convert(a, array('<f8', (2, 6), values), c, p)
        m = model(); m['beta'][0][0] = 1.e308
        with self.assertRaisesRegex(ValueError, 'products'): p.predict(m, [2147483647, 0, 0])

    def test_exact_extent_and_canonical_mask(self):
        a, b, c = triples()
        for bad in (a+b'x', a[:-1], array('|b1', (3,), [1, 2, 0])):
            with self.subTest(bad=bad[-4:]), self.assertRaises(ValueError): e.convert(bad, b, c, p)

    def test_object_dtype_and_duplicate_header_refused(self):
        a, b, c = triples()
        with self.assertRaises(ValueError): e.convert(a.replace(b'|b1', b'|O8'), b, c, p)
        h = b"{'descr':'|b1','descr':'|b1','fortran_order':False,'shape':(3,)}\n"
        bad = b'\x93NUMPY\x01\x00' + len(h).to_bytes(2, 'little') + h + b'\x01\x00\x01'
        with self.assertRaises(ValueError): e.convert(bad, b, c, p)

    def test_mask_indices_are_unique_sorted(self):
        for selected in ([2, 0], [0, 0], [True, 2], [0, 3]):
            m = model(); m['selected_indices'] = selected
            with self.subTest(selected=selected), self.assertRaises(ValueError): p.validate_model(m)

    def test_json_duplicates_extra_fields_and_nonfinite(self):
        with self.assertRaises(ValueError): p.strict_json('{"x":1,"x":2}')
        with self.assertRaises(ValueError): p.strict_json('{"x":NaN}')
        m = model(); m['trial_id'] = 'owner'
        with self.assertRaises(ValueError): p.validate_model(m)

    def test_one_window_wire(self):
        query = request(); out = io.BytesIO()
        incoming = io.BytesIO(json.dumps(query).encode()+b'\n{"schema":"horrocks-window-end-v1"}\n')
        p.serve(model(), incoming, out)
        self.assertEqual(p.strict_json(out.getvalue()), {'token':'a'*64,'prediction':6})

    def test_wire_rejects_private_fields_bad_token_and_second_query(self):
        for query in ({**request(), 'animal':'owner'}, {**request(), 'token':'short'}):
            out = io.BytesIO()
            with self.assertRaises(ValueError): p.serve(model(), io.BytesIO(json.dumps(query).encode()+b'\n'), out)
            self.assertEqual(out.getvalue(), b'')
        raw = json.dumps(request()).encode()+b'\n'
        with self.assertRaisesRegex(ValueError, 'single-window'): p.serve(model(), io.BytesIO(raw+raw), io.BytesIO())


if __name__ == '__main__':
    unittest.main(verbosity=2)
