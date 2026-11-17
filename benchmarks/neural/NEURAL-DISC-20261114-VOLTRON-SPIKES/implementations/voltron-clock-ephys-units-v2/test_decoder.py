"""Generated-only tests for the strict four-entry Voltron NPZ profile."""
import ast
import io
from pathlib import Path
import struct
import types
import unittest
import warnings
import zipfile

_PATH = Path(__file__).with_name('decoder.py')
d = types.ModuleType('voltron_units_decoder')
d.__file__ = str(_PATH)
exec(compile(_PATH.read_bytes(), str(_PATH), 'exec'), d.__dict__)


def npy(payload, header, version=(1, 0)):
    prefix = 10 if version == (1, 0) else 12
    hlen = 128 - prefix
    raw = repr(header).encode('latin1')
    assert len(raw) < hlen
    padded = raw + b' ' * (hlen - len(raw) - 1) + b'\n'
    size = struct.pack('<H' if version == (1, 0) else '<I', hlen)
    return b'\x93NUMPY' + bytes(version) + size + padded + payload


def floats(values, descr='<f8'):
    fmt = descr[0] + ('f' if descr[-1] == '4' else 'd') * len(values)
    return npy(struct.pack(fmt, *values),
               {'descr': descr, 'fortran_order': False, 'shape': (len(values),)})


def units(values=('s', 'mV', 'pA'), *, dtype='<U2', shape=(3,), order=False,
          version=(1, 0), payload=None):
    if payload is None:
        payload = b''.join(x.ljust(2, '\0').encode('utf-32-le') for x in values)
    return npy(payload, {'descr': dtype, 'fortran_order': order, 'shape': shape}, version)


class Unseekable(io.BytesIO):
    def seek(self, *args):
        raise OSError('generated descriptor stream')


def pack(*, metadata=None, names=None, compression=zipfile.ZIP_DEFLATED,
         descriptor=False, local_zip64=False, channels=None):
    values = channels or {
        'time.npy': floats((0.0, .0001, .0002)),
        'voltage.npy': floats((-60.0, -59.0, -58.0)),
        'stimulus.npy': floats((0.0, 0.0, 5.0)),
    }
    values = dict(values)
    values['units.npy'] = units() if metadata is None else metadata
    names = list(values) if names is None else names
    buf = Unseekable() if descriptor else io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(buf, 'w', compression=compression) as archive:
            for name in names:
                body = values.get(name, units())
                with archive.open(name, 'w', force_zip64=local_zip64) as out:
                    out.write(body)
    return buf.getvalue()


class FourEntryProfile(unittest.TestCase):
    def refuse(self, body, message=None):
        if message:
            with self.assertRaisesRegex(d.Refusal, message):
                d.describe_sweep(body)
        else:
            with self.assertRaises(d.Refusal):
                d.describe_sweep(body)

    def test_valid_storage_descriptors_and_local_zip64(self):
        for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            for descriptor in (False, True):
                for local_zip64 in (False, True):
                    with self.subTest(compression=compression, descriptor=descriptor,
                                      local_zip64=local_zip64):
                        blob = pack(compression=compression, descriptor=descriptor,
                                    local_zip64=local_zip64)
                        got = d.describe_sweep(blob)
                        self.assertEqual(set(got['channels']), {'time', 'voltage', 'stimulus'})
                        self.assertEqual(got['units_metadata']['values'], ['s', 'mV', 'pA'])
                        self.assertEqual(got['units_metadata']['file_bytes'], 152)
                        self.assertEqual(got['inner_file_bytes'], 3 * 152 + 152)
                        self.assertFalse(got['events_generated'])
                        self.assertFalse(got['physical_support_qualified'])
                        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                            self.assertEqual(archive.testzip(), None)
                            self.assertEqual(archive.read('units.npy'), units())

    def test_units_first_and_mixed_signal_endian(self):
        channels = {'time.npy': floats((0.0, .1, .2), '>f4'),
                    'voltage.npy': floats((-60.0, -59.0, -58.0), '<f4'),
                    'stimulus.npy': floats((0.0, 1.0, 2.0), '>f8')}
        got = d.describe_sweep(pack(channels=channels,
                                   names=['units.npy', 'stimulus.npy', 'time.npy', 'voltage.npy']))
        self.assertEqual(got['channels']['time']['dtype'], '>f4')
        self.assertEqual(got['units_metadata']['channel_order'], ['time', 'voltage', 'stimulus'])

    def test_legacy_three_entry_is_preserved_as_incompatible(self):
        self.refuse(pack(names=['time.npy', 'voltage.npy', 'stimulus.npy']),
                    'four-entry single-disk profile')

    def test_arbitrary_extra_and_missing_and_duplicate(self):
        cases = [
            ['time.npy', 'voltage.npy', 'stimulus.npy', 'units.npy', 'other.npy'],
            ['time.npy', 'voltage.npy', 'stimulus.npy', 'other.npy'],
            ['time.npy', 'voltage.npy', 'units.npy', 'units.npy'],
            ['time.npy', 'voltage.npy', 'units.npy'],
        ]
        for names in cases:
            with self.subTest(names=names):
                self.refuse(pack(names=names))

    def test_wrong_unit_values_and_order(self):
        for values in [('ms', 'mV', 'pA'), ('s', 'V', 'pA'), ('s', 'mV', 'nA'),
                       ('mV', 's', 'pA'), ('s ', 'mV', 'pA')]:
            with self.subTest(values=values):
                self.refuse(pack(metadata=units(values)), 'units exact time-voltage-stimulus')

    def test_metadata_schema_is_exact(self):
        variants = [
            units(dtype='<f8', payload=struct.pack('<3d', 0, 1, 2)),
            units(dtype='|O', payload=b'\0' * 24),
            units(dtype='>U2'),
            units(shape=(1, 3)),
            units(shape=(True,)),
            units(order=True),
            units(version=(2, 0)),
        ]
        for i, metadata in enumerate(variants):
            with self.subTest(index=i):
                self.refuse(pack(metadata=metadata))

    def test_duplicate_or_executable_header_is_not_evaluated(self):
        for header in [
            "{'descr':'<U2','descr':'<U2','shape':(3,)}",
            "{'descr':'<U2','fortran_order':False,'shape':__import__('os')}",
            "{'descr':'<U2','fortran_order':False,'shape':(3,),'extra':0}",
        ]:
            raw = header.encode()
            self.assertLess(len(raw), 118)
            forged = b'\x93NUMPY\x01\x00' + struct.pack('<H', 118) + raw
            forged += b' ' * (127 - len(forged)) + b'\n' + units()[128:]
            self.assertEqual(len(forged), 152)
            self.refuse(pack(metadata=forged), 'units')

    def test_invalid_unicode_and_header_length(self):
        bad = bytearray(units())
        bad[128:132] = b'\xff' * 4
        self.refuse(pack(metadata=bytes(bad)), 'UTF-32')
        bad = bytearray(units())
        bad[8:10] = struct.pack('<H', 117)
        self.refuse(pack(metadata=bytes(bad)), 'header extent')

    def test_metadata_extent_is_not_expanded(self):
        self.refuse(pack(metadata=units() + b'X'), 'units metadata size')
        self.refuse(pack(metadata=units()[:-1]), 'units metadata size')

    def test_units_crc_still_required(self):
        blob = bytearray(pack(compression=zipfile.ZIP_STORED))
        row = next(r for r in d.inner_directory(bytes(blob)) if r['name'] == b'units.npy')
        start = row['offset'] + 30 + len(row['name'])
        blob[start + 128] ^= 1
        self.refuse(bytes(blob), 'inner length/CRC')

    def test_local_units_name_must_match_central(self):
        blob = bytearray(pack())
        row = next(r for r in d.inner_directory(bytes(blob)) if r['name'] == b'units.npy')
        blob[row['offset'] + 30] = ord('x')
        self.refuse(bytes(blob), 'local raw name')

    def test_terminal_and_central_extent_are_not_relaxed(self):
        blob = pack()
        self.refuse(blob + b'X', 'terminal EOCD')
        self.refuse(blob[:-22] + b'X' + blob[-22:], 'central extent')
        bad = bytearray(blob)
        bad[-22 + 4:-22 + 6] = struct.pack('<H', 1)
        self.refuse(bytes(bad), 'single-disk')

    def test_channel_length_and_axis_and_finite_checks_remain(self):
        base = {'time.npy': floats((0.0, .1, .2)),
                'voltage.npy': floats((-60.0, -59.0, -58.0)),
                'stimulus.npy': floats((0.0, 0.0, 1.0))}
        for name, value in [
            ('voltage.npy', floats((-60.0, -59.0))),
            ('time.npy', floats((0.0, .1, .1))),
            ('voltage.npy', floats((-60.0, float('nan'), -58.0))),
        ]:
            channels = dict(base)
            channels[name] = value
            with self.subTest(name=name):
                self.refuse(pack(channels=channels))

    def test_frame_decoder_is_unchanged(self):
        got = d.describe_frame_times(floats((0.0, .002, .004)), 3)
        self.assertTrue(got['axis_strictly_increasing'])
        with self.assertRaises(d.Refusal):
            d.describe_frame_times(floats((0.0, .002, .004)), 4)


if __name__ == '__main__':
    unittest.main()
