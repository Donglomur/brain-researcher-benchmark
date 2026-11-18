"""Generated source/collection controls; no authentic arrays or models.

The full65-person membership is retained. Build orchestration substitutes only
the already separately tested capture/publication I/O, never a scientific fit.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import primary_ctf_inputs as target


def npy(value):
    out = io.BytesIO()
    np.lib.format.write_array(out, np.asarray(value), version=(1, 0), allow_pickle=False)
    return out.getvalue()


def fixture(*, age_order=None, corrupt_person=None, extra=None, omit=None):
    people = [f'subject{i:02d}' for i in range(65)]
    ages = age_order if age_order is not None else people
    members = {'bursts/': b'', 'networks/': b'',
               'demographics.csv': ('name,age,gender,handedness\n' +
                                    ''.join(f'{p},30,F,R\n' for p in ages)).encode()}
    for i, person in enumerate(people):
        # Deliberately not an NPY: this separate branch's body must not decode.
        members[f'bursts/{person}.npy'] = b'UNREAD_SEPARATE_BURST_BRANCH'
        values = np.arange(114, dtype='<f4').reshape(3, 38) + i
        if person == corrupt_person:
            values[0, 0] = np.nan
        members[f'networks/{person}.npy'] = npy(values)
    if omit is not None:
        del members[omit]
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)
        if extra is not None:
            archive.writestr(extra, b'extra')
    body = out.getvalue()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = [{'member': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                 'local_header_offset': i.header_offset, 'compression': i.compress_type,
                 'flags': i.flag_bits, 'crc32': f'{i.CRC:08x}'} for i in archive.infolist()]
    return body, rows, members


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


class ProjectionTests(unittest.TestCase):
    def project(self, body, rows, array_cap=10**6):
        self.saved, self.arrays, self.reads = {}, {}, []
        def save(name, raw):
            self.saved[name] = raw
            return pin(raw)
        def array(name, value):
            self.arrays[name] = np.asarray(value).copy()
            raw = npy(value)
            return {'path': name, **pin(raw), 'shape': list(value.shape), 'dtype': value.dtype.str}
        return target._project(body, rows, save, array, array_cap, self.reads.append)

    def test_all65_complete_original_networks_and_unread_bursts(self):
        body, rows, originals = fixture()
        native, regional, ages = self.project(body, rows)
        self.assertEqual([r['person'] for r in regional], [f'subject{i:02d}' for i in range(65)])
        self.assertEqual(len(native), 66)
        self.assertEqual(len(ages), 65)
        self.assertEqual(len(self.arrays), 130)
        self.assertEqual(len(self.reads), 66)
        self.assertTrue(all('/bursts/' not in name for name in self.saved))
        for i, row in enumerate(regional):
            name = f'networks/subject{i:02d}.npy'
            self.assertEqual(self.saved['ctf/' + name], originals[name])
            x = self.arrays[row['observations']['path']]
            self.assertEqual(x.shape, (3, 38))
            self.assertEqual(x.dtype.str, '<f8')
            np.testing.assert_array_equal(self.arrays[row['physical_rows']['path']], [0, 1, 2])
        self.assertEqual(sum(self.reads), sum(len(v) for k, v in originals.items()
                                            if k == 'demographics.csv' or k.startswith('networks/') and not k.endswith('/')))

    def test_duplicate_directory_member_is_rejected_not_collapsed(self):
        body, rows, _ = fixture()
        rows[-1] = copy.deepcopy(rows[-2])
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.project(body, rows)

    def test_missing_original_person_or_extra_member_rejected(self):
        for kwargs in ({'omit': 'networks/subject64.npy'}, {'extra': 'networks/unrelated.npy'}):
            with self.subTest(kwargs=kwargs):
                body, rows, _ = fixture(**kwargs)
                with self.assertRaisesRegex(ValueError, '133'):
                    self.project(body, rows)

    def test_directory_order_or_metadata_disagreement_rejected(self):
        body, rows, _ = fixture()
        altered = copy.deepcopy(rows)
        altered[-1]['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'metadata parity'):
            self.project(body, altered)
        altered = copy.deepcopy(rows)
        altered[-1], altered[-2] = altered[-2], altered[-1]
        with self.assertRaisesRegex(ValueError, 'directory order'):
            self.project(body, altered)

    def test_boolean_zip_metadata_is_not_integer_identity(self):
        body, rows, _ = fixture()
        rows[0]['flags'] = False
        with self.assertRaisesRegex(ValueError, 'integer ZIP metadata'):
            self.project(body, rows)

    def test_demographic_reordering_rejected_before_signal_decode(self):
        order = [f'subject{i:02d}' for i in range(65)]
        order[0], order[1] = order[1], order[0]
        body, rows, _ = fixture(age_order=order)
        with patch.object(target, 'numeric_original', side_effect=AssertionError('signal decoded')):
            with self.assertRaisesRegex(ValueError, 'Literal ordered CTF'):
                self.project(body, rows)
        self.assertEqual(self.saved, {})

    def test_array_cap_precedes_numeric_materialization(self):
        body, rows, _ = fixture()
        with patch.object(target, 'numeric_original', side_effect=AssertionError('materialized')):
            with self.assertRaisesRegex(ValueError, 'allocation before materialization'):
                self.project(body, rows, array_cap=32)

    def test_nonfinite_member_is_not_filtered_or_zeroed(self):
        body, rows, _ = fixture(corrupt_person='subject00')
        with self.assertRaisesRegex(ValueError, 'finite original'):
            self.project(body, rows)
        self.assertEqual(list(self.saved), ['ctf/demographics.csv'])

    def test_crc_corruption_is_not_accepted_as_original_member(self):
        body, rows, _ = fixture()
        row = next(r for r in rows if r['member'] == 'networks/subject00.npy')
        raw = bytearray(body)
        start = row['local_header_offset'] + 30 + len(row['member'])
        raw[start + row['bytes'] - 1] ^= 1
        with self.assertRaises(zipfile.BadZipFile):
            self.project(bytes(raw), rows)


class BuildGateTests(unittest.TestCase):
    def spec(self):
        return {'ctf_archive': {'path': '/unopened/original.zip', 'bytes': target.CTF_BYTES,
                                'sha256': target.CTF_SHA},
                'ctf_directory': {'path': '/unopened/directory.json', 'bytes': target.DIRECTORY_BYTES,
                                  'sha256': target.DIRECTORY_SHA}}

    def test_wrong_source_identity_rejected_before_io(self):
        for field in ('ctf_archive', 'ctf_directory'):
            spec = self.spec()
            spec[field]['sha256'] = '0' * 64
            with patch.object(target, 'capture', side_effect=AssertionError('unexpected I/O')):
                with self.assertRaisesRegex(ValueError, 'fixed original CTF identity'):
                    target.build(spec, '/uncreated/output', {'read_bytes': 10**9, 'write_bytes': 10**9, 'array_bytes': 10**6})

    def test_no_elekta_or_other_extra_operand_accepted(self):
        spec = self.spec()
        spec['elekta_binding'] = {'path': '/unopened'}
        with self.assertRaisesRegex(ValueError, 'Only the two exact CTF'):
            target.build(spec, '/uncreated/output', {'read_bytes': 10**9, 'write_bytes': 10**9, 'array_bytes': 10**6})

    def test_primary_completion_and_write_cap_through_real_orchestration(self):
        archive, directory, _ = fixture()
        directory_body = json.dumps({'members': directory}).encode()
        saved = {}
        # These stubs replace source authentication and physical publication;
        # no generated archive is described as an authentic released source.
        def capture(path, cap, expected):
            return directory_body if path.endswith('.json') else archive
        def publish(path, raw):
            key = str(path)
            if key in saved:
                raise AssertionError('overwritten')
            saved[key] = raw
            return pin(raw)
        def array(path, value, cap):
            raw = npy(value)
            if len(raw) > cap:
                raise ValueError('array write cap')
            return {'path': Path(path).name, **publish(path, raw),
                    'shape': list(value.shape), 'dtype': value.dtype.str}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(target, 'capture', capture), patch.object(target, 'durable_new', publish), patch.object(target, 'write_array', array):
                output = Path(temporary) / 'primary'
                answer = target.build(self.spec(), output, {'read_bytes': 10**9, 'write_bytes': 10**6, 'array_bytes': 10**6})
                manifest = answer['inputs']
                self.assertEqual(manifest['primary_branches'], ['ctf_tde', 'ctf_dynemo'])
                self.assertFalse(manifest['six_branch_completion'])
                self.assertFalse(manifest['model_preprocessing_or_fit_executed'])
                self.assertEqual(set(manifest['packets']), {'ctf_tde'})
                self.assertEqual(answer['logical_IO']['write'], sum(map(len, saved.values())))
                self.assertEqual(manifest['ctf_people'], 65)
                self.assertIn(str(output / 'PRIMARY_CTF_INPUTS.json'), saved)
                saved.clear()
                with self.assertRaises(ValueError):
                    target.build(self.spec(), Path(temporary) / 'too-small',
                                 {'read_bytes': 10**9, 'write_bytes': 1, 'array_bytes': 10**6})
                self.assertFalse(any(p.endswith('PRIMARY_CTF_INPUTS.json') for p in saved))

    def test_read_cap_prevents_any_capture(self):
        with patch.object(target, 'capture', side_effect=AssertionError('unexpected capture')):
            with self.assertRaisesRegex(ValueError, 'read allocation'):
                target.build(self.spec(), '/uncreated/output', {'read_bytes': 1, 'write_bytes': 1, 'array_bytes': 1})


if __name__ == '__main__':
    unittest.main()
