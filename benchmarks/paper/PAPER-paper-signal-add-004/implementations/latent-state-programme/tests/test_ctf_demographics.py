"""Invented metadata controls; no neural arrays, private targets or model runs."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_inputs import ctf_demographics
import source_inputs
from diagnostics import age_group


def fixture(rows=None, header=('name', 'age', 'gender', 'handedness')):
    if rows is None:
        rows = [[f'subject{i:02d}', str(20 + i), 'fixture', 'fixture'] for i in range(65)]
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def rows_from(body):
    return list(csv.reader(io.StringIO(body.decode('utf-8'))))[1:]


class CtfDemographicsTests(unittest.TestCase):
    def test_original_person_age_relationship_and_distinct_source_policies(self):
        result = ctf_demographics(fixture())
        self.assertEqual(len(result), 65)
        self.assertEqual(result[0], {'person': 'subject00', 'age': 20.0})
        self.assertEqual(result[-1], {'person': 'subject64', 'age': 84.0})
        # Age34 is a real policy boundary, not a reason to harmonize the source.
        self.assertEqual(result[14]['age'], 34.0)
        self.assertEqual(age_group(result[14]['age'], 'native_dynamic_numeric'), 1)
        self.assertEqual(age_group(result[14]['age'], 'native_static_numeric'), 1)
        self.assertEqual(age_group(result[13]['age'], 'native_dynamic_numeric'), 1)
        self.assertEqual(age_group(result[13]['age'], 'native_static_numeric'), 2)

    def test_row_permutation_is_rejected_instead_of_relabeling_people(self):
        rows = rows_from(fixture())
        rows[0], rows[64] = rows[64], rows[0]
        with self.assertRaisesRegex(ValueError, 'person identity'):
            ctf_demographics(fixture(rows))

    def test_duplicate_missing_and_unknown_people(self):
        for name in ('subject00', 'subject65', 'sub01', 'subject01.npy', ' subject01'):
            with self.subTest(name=name):
                rows = rows_from(fixture())
                rows[1][0] = name
                with self.assertRaisesRegex(ValueError, 'person identity'):
                    ctf_demographics(fixture(rows))

    def test_no_truncation_or_extra_participants(self):
        rows = rows_from(fixture())
        for changed in (rows[:-1], rows + [['subject65', '40', '', '']]):
            with self.subTest(count=len(changed)):
                with self.assertRaises(ValueError):
                    ctf_demographics(fixture(changed))

    def test_nonfinite_invalid_and_out_of_range_ages(self):
        for age in ('nan', 'NaN', 'inf', '-inf', '1e500', '', 'unknown', '0', '-1', '130'):
            with self.subTest(age=age):
                rows = rows_from(fixture())
                rows[14][1] = age
                with self.assertRaisesRegex(ValueError, 'age'):
                    ctf_demographics(fixture(rows))

    def test_duplicate_missing_and_added_columns(self):
        for header in (('age', 'age', 'gender', 'handedness'),
                       ('name', 'age', 'gender'),
                       ('name', 'age', 'gender', 'handedness', 'age'),
                       ('name', 'age', 'gender', 'other')):
            with self.subTest(header=header):
                with self.assertRaisesRegex(ValueError, 'columns'):
                    ctf_demographics(fixture(header=header))

    def test_missing_and_extra_fields_in_a_row(self):
        for width in (3, 5):
            rows = rows_from(fixture())
            rows[3] = rows[3][:width] if width == 3 else rows[3] + ['extra']
            with self.subTest(width=width):
                with self.assertRaisesRegex(ValueError, 'complete demographics rows'):
                    ctf_demographics(fixture(rows))

    def test_header_order_uses_column_identity(self):
        rows = rows_from(fixture())
        reordered = [[r[2], r[0], r[3], r[1]] for r in rows]
        self.assertEqual(ctf_demographics(fixture(reordered, ('gender', 'name', 'handedness', 'age'))),
                         ctf_demographics(fixture()))

    def test_well_formed_csv_and_source_encoding_required(self):
        for body in (b'', b'\xff', fixture().replace(b'subject10,', b'"subject10,')):
            with self.subTest(body=body[:20]):
                with self.assertRaises(ValueError):
                    ctf_demographics(body)

    def test_preparation_rejects_identity_mismatch_before_signal_read_or_write(self):
        rows = rows_from(fixture())
        rows[0], rows[64] = rows[64], rows[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'generated.zip'
            # Complete original membership, but deliberately no real signal body.
            with zipfile.ZipFile(archive, 'w') as handle:
                for family in ('bursts', 'networks'):
                    handle.writestr(family + '/', b'')
                    for index in range(65):
                        handle.writestr(f'{family}/subject{index:02d}.npy', b'not-a-signal')
                handle.writestr('demographics.csv', fixture(rows))
            with zipfile.ZipFile(archive) as handle:
                directory = {'members': [
                    {'member': row.filename, 'bytes': row.file_size,
                     'compressed_bytes': row.compress_size, 'crc32': f'{row.CRC:08x}'}
                    for row in handle.infolist()]}
            directory_path = root / 'generated-directory.json'
            directory_path.write_text(json.dumps(directory), encoding='utf-8')
            def descriptor(path):
                body = path.read_bytes()
                return {'path': str(path), 'bytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest()}
            spec = {'ctf_archive': descriptor(archive), 'ctf_directory': descriptor(directory_path)}
            output = root / 'output'
            # The constants change only for this generated-fixture test, never
            # the production selected archive. All real capture/ZIP checks run.
            with mock.patch.multiple(source_inputs,
                                     CTF_BYTES=spec['ctf_archive']['bytes'],
                                     CTF_SHA=spec['ctf_archive']['sha256']), \
                    mock.patch.object(source_inputs, 'numeric_original',
                                      side_effect=AssertionError('Signal decoder reached')):
                with self.assertRaisesRegex(ValueError, 'person identity'):
                    source_inputs.build(spec, output,
                                        {'read_bytes': 131072, 'write_bytes': 131072,
                                         'array_bytes': 131072})
            self.assertEqual(list(output.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
