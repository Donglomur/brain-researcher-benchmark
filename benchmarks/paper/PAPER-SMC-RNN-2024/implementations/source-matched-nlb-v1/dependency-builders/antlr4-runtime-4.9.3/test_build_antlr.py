"""Offline generated integrity controls; no package acquisition or backend run."""
import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('antlr_builder_controls', Path(__file__).with_name('build_antlr.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

DIST_INFO = 'demo-1.0.dist-info'


def fixture(extra=None, corrupt=False):
    files = {
        'demo/__init__.py': b'# inert generated fixture\n',
        DIST_INFO + '/METADATA': b'Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n',
        DIST_INFO + '/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    files.update(extra or {})
    records = io.StringIO(newline='')
    writer = csv.writer(records, lineterminator='\n')
    for name, body in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
        writer.writerow([name, 'sha256=' + digest, str(len(body))])
    writer.writerow([DIST_INFO + '/RECORD', '', ''])
    files[DIST_INFO + '/RECORD'] = records.getvalue().encode()
    if corrupt:
        files['demo/__init__.py'] += b'# changed after RECORD\n'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


class WheelIntegrityControls(unittest.TestCase):
    def test_accepts_outer_metadata_with_vendored_metadata(self):
        raw = fixture({'demo/_vendor/nested-9.0.dist-info/METADATA': b'Name: nested\nVersion: 9.0\n',
                       'demo/_vendor/nested-9.0.dist-info/WHEEL': b'Tag: not-the-outer-wheel\n'})
        observed = builder.zip_inventory(raw, DIST_INFO)
        self.assertEqual(observed['name'], 'demo')
        self.assertEqual(observed['tags'], ['py3-none-any'])
        self.assertTrue(observed['all_record_hashes_verified'])

    def test_rejects_record_content_mismatch(self):
        with self.assertRaises(ValueError):
            builder.zip_inventory(fixture(corrupt=True), DIST_INFO)

    def test_rejects_native_payload_despite_pure_wheel_tag(self):
        with self.assertRaises(ValueError):
            builder.zip_inventory(fixture({'demo/native.bin': b'\x7fELF' + bytes(64)}),
                                  DIST_INFO, output_wheel=True)

    def test_rejects_traversal_before_escaping_owned_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            owned = Path(temporary)
            output = owned / 'output'
            output.mkdir()
            with self.assertRaises(ValueError):
                builder.zip_inventory(fixture({'../escaped.py': b'# never written\n'}),
                                      DIST_INFO, extract_to=output)
            self.assertFalse((owned / 'escaped.py').exists())


if __name__ == '__main__':
    unittest.main()
