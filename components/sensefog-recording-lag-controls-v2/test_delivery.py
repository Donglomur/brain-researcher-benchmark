"""Real relocated CLI checks for the complete invented recording-boundary census."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_pairing


def boundary_fixture():
    doc = test_pairing.fixture()
    doc['segments'] = []
    for rec in doc['recordings']:
        rid = rec['recording_id']
        rec['sample_count'] = 10
        rec['window_stride_samples'] = 1
        rec['cases'] = [{'case_id': rid + '_case_%d' % k, 'start_sample': k} for k in range(9)]
        for start in (0, 5):
            doc['segments'].append({'segment_id': rid + '_seg_%d' % start, 'recording_id': rid,
                'acquisition_stratum': 'regime_%d' % start, 'recording_start_sample': start,
                'sample_count': 5, 'channels': ['invented_channel'],
                'masks': {'invented_channel': [[0, 5, False, False]]}})
    return doc


class DeliveryChecks(unittest.TestCase):
    def test_complete_exact_local_members(self):
        manifest = json.loads((HERE / 'COMPONENT_SOURCE.json').read_bytes())
        self.assertEqual({x['path'] for x in manifest['files']} | {'COMPONENT_SOURCE.json'},
                         {p.name for p in HERE.iterdir()})
        for row in manifest['files']:
            raw = (HERE / row['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
        self.assertEqual(Path(test_pairing.mod.__file__).resolve(), HERE / 'sensefog_pairing.py')

    def cli(self, base, cap):
        raw = (json.dumps(boundary_fixture(), separators=(',', ':')) + '\n').encode()
        (base / 'input.json').write_bytes(raw)
        return subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'sensefog_pairing.py'),
            '--input', str(base / 'input.json'), '--expected-input-sha256', hashlib.sha256(raw).hexdigest(),
            '--output', str(base / 'maps.json'), '--max-input-bytes', str(len(raw)),
            '--max-output-bytes', '2000000', '--max-cases', str(cap)],
            cwd=base, capture_output=True, timeout=10, umask=0o077)

    def test_complete_boundary_census_through_real_relocated_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); result = self.cli(base, 108)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, b'')
            report = json.loads((base / 'maps.json').read_bytes())
            self.assertEqual((report['original_case_count'], len(report['maps'])), (108, 2160))
            crossing = [row for row in report['maps'] if row['recipient_core'] == [4, 6]]
            self.assertEqual(len(crossing), 240)
            self.assertTrue(all(row['reason'] == 'recipient_core_crosses_gap_or_acquisition_boundary'
                                for row in crossing))
            self.assertEqual(len(report['participants']), 12)
            self.assertEqual(report['requested_transform_count'], 20)
            self.assertIsNone(report['primary_score'])
            self.assertFalse(report['scientific_qualification'])
            self.assertEqual(stat.S_IMODE((base / 'maps.json').stat().st_mode), 0o600)

    def test_complete_case_cap_cannot_publish_selected_subset(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); result = self.cli(base, 107)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'complete case census exceeds explicit limit', result.stderr)
            self.assertFalse((base / 'maps.json').exists())


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('assertions must remain enabled')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.testsRun == 3 and result.wasSuccessful() and not
                     (result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 1)
