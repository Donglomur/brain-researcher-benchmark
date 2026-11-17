"""Standard-library integrity controls; numerical controls are package-local."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('benchmarks/shared/four-programmes/_four_programmes_source_v1')
DESCRIPTOR = ROOT / 'benchmarks/integrity/current-closures/numeric-dmd/SOURCE_BINDINGS.json'
NUMERICS = 'current/source/extensions/critical_init/numerics.py'


class NumericDmdBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = json.loads(DESCRIPTOR.read_text())

    def test_current_source_and_unchanged_evidence_match_exact_pins(self):
        self.assertEqual(self.binding['schema'], 'four_programme_current_dmd_bindings_v1')
        for group in ('source_files', 'unchanged_dependencies', 'historical_files', 'integration_files'):
            rows = self.binding[group]
            self.assertTrue(rows, group)
            self.assertEqual(len({row['path'] for row in rows}), len(rows))
            for row in rows:
                with self.subTest(group=group, path=row['path']):
                    path = ROOT / row['path']
                    self.assertTrue(path.resolve().is_relative_to(ROOT))
                    raw = path.read_bytes()
                    self.assertEqual(len(raw), row['bytes'])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])

    def test_historical_lock_and_original_numerics_remain_predecessor_evidence(self):
        lock = json.loads((ROOT / SHARED / 'SOURCE_LOCK.json').read_text())
        rows = {row['path']: row for row in lock['files']}
        predecessor = self.binding['historical_current_identity']
        self.assertEqual(predecessor, {key: rows[NUMERICS][key] for key in ('path', 'bytes', 'sha256')})
        current = next(row for row in self.binding['source_files']
                       if row['path'] == (SHARED / NUMERICS).as_posix())
        self.assertNotEqual(current['sha256'], predecessor['sha256'])
        for relative in self.binding['historical_numerics_paths']:
            with self.subTest(path=relative):
                raw = (ROOT / SHARED / relative).read_bytes()
                self.assertEqual(len(raw), predecessor['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), predecessor['sha256'])
        self.assertEqual(lock['qualification_holds'], 65)

    def test_repair_preserves_inactive_scope_and_original_native_route(self):
        qualification = self.binding['qualification']
        self.assertTrue(qualification['source_only'])
        self.assertEqual(qualification['qualification_holds_open'], 65)
        for field in ('runnable', 'scientific_qualified', 'submission_ready',
                      'execution_authority', 'original_native_route_repaired'):
            self.assertIs(qualification[field], False, field)
        self.assertEqual(self.binding['new_benchmark_ids'], 0)
        self.assertEqual(self.binding['consumers']['current_kernel'], 'critical_init.kernels.KERNELS[dmd]')
        self.assertEqual(self.binding['consumers']['original_source_session_numerics'],
                         self.binding['historical_numerics_paths'][1])
        for row in self.binding['historical_files']:
            if row['path'].endswith('/registered-runtime/manifest.json'):
                manifest = json.loads((ROOT / row['path']).read_text())
                self.assertEqual(manifest['status'], 'source_only_inactive')
                self.assertIsNone(manifest['run'])
                self.assertIsNone(manifest['score'])
                self.assertTrue(all(value is False for value in manifest['admission'].values()))


if __name__ == '__main__':
    unittest.main()
