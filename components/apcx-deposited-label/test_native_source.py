"""Invented metadata/source-boundary controls; never import Arrow or fit data."""
import copy
import hashlib
import os
from pathlib import Path
import platform
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import task
import native_convert
from apcx_original import census_core as original_core
from apcx_original import native_scan


class OriginalInputControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.budget = task.budget()

    def manifest(self):
        return {'portable_host': {'sys_platform': sys.platform, 'machine': platform.machine(),
                'python': platform.python_version()}, 'site_packages': str(self.root),
                'packages': [{'record': {'path': str(self.root/'pyarrow-24.0.0.dist-info/RECORD')}},
                             {'record': {'path': str(self.root/'numpy-2.4.6.dist-info/RECORD')}}]}

    def save(self, value):
        p = self.root/'runtime.json'; b = task.core.canonical(value); p.write_bytes(b)
        return p, hashlib.sha256(b).hexdigest()

    def test_native_and_task_census_namespaces_do_not_collide(self):
        self.assertIs(native_scan.core, original_core)
        self.assertIsNot(native_scan.core, task.core.census_core)
        self.assertTrue(callable(native_scan.core.audit_row))
        self.assertFalse(hasattr(task.core.census_core, 'audit_row'))
        sample = {'scalar_types': [1, -0.0, True, 'invented']}
        self.assertEqual(original_core.fingerprint(sample), task.core.census_core.fingerprint(sample))

    def test_source_import_does_not_activate_native_libraries(self):
        self.assertNotIn('pyarrow', sys.modules)
        self.assertNotIn('numpy', sys.modules)

    def test_runtime_manifest_hash_precedes_library_access(self):
        p, _ = self.save(self.manifest())
        with self.assertRaisesRegex(ValueError, 'runtime manifest whole hash'):
            native_convert.admitted_runtime(p, '0'*64, self.budget)
        self.assertNotIn('pyarrow', sys.modules)

    def test_wrong_native_host_is_rejected(self):
        value = self.manifest(); value['portable_host']['machine'] = 'INVENTED_WRONG_HOST'
        p, sha = self.save(value)
        with self.assertRaisesRegex(ValueError, 'exact admitted native host'):
            native_convert.admitted_runtime(p, sha, self.budget)

    def test_reference_runtime_cannot_replace_native_runtime(self):
        value = self.manifest()
        value['packages'][1]['record']['path'] = str(self.root/'numpy-2.2.6.dist-info/RECORD')
        p, sha = self.save(value)
        with self.assertRaisesRegex(ValueError, 'fixed native transformation package versions'):
            native_convert.admitted_runtime(p, sha, self.budget)

    def test_complete_manifest_metadata_can_pass_without_native_import(self):
        value = self.manifest(); p, sha = self.save(value)
        self.assertEqual(native_convert.admitted_runtime(p, sha, self.budget), value)
        # Actual RECORD/file verification and activation are separate, uncalled gates.
        self.assertNotIn('pyarrow', sys.modules)

    def test_small_wrong_source_refused_before_runtime_or_output(self):
        p = self.root/'not-the-original.parquet'; p.write_bytes(b'PAR1')
        args = types.SimpleNamespace(parquet=p, runtime_manifest=self.root/'absent.json',
            runtime_manifest_sha256='0'*64, output=self.root/'output')
        env = {n:'1' for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','ARROW_NUM_THREADS')}
        with patch.dict(os.environ, env):
            with self.assertRaisesRegex(ValueError, 'exact file size'):
                native_convert.convert(args)
        self.assertFalse(args.output.exists())
        self.assertNotIn('pyarrow', sys.modules)

    def test_two_whole_bridge_pins_match_existing_complete_converter(self):
        first = native_convert.specification()['expected_bridge']
        second = {v['name']: {'bytes':v['bytes'], 'sha256':v['sha256']}
                  for v in task.config()['prepared_inputs'].values()}
        self.assertEqual(first, second)
        self.assertEqual(sum(x['bytes'] for x in first.values()), 234753785)


    def test_native_receipt_rss_breach_prevents_bridge_write(self):
        writes = []
        store = types.SimpleNamespace(json=lambda name, value: writes.append(name))
        with patch.object(task.resource, 'getrusage',
                          return_value=types.SimpleNamespace(ru_maxrss=5*1024**3)):
            with self.assertRaisesRegex(ValueError, 'RSS'):
                native_convert.write_bridge(store, {'invented': True}, self.budget)
        self.assertEqual(writes, [])

    def test_native_postwrite_rss_breach_prevents_success_return(self):
        writes = []
        store = types.SimpleNamespace(json=lambda name, value: writes.append(name))
        observations = [types.SimpleNamespace(ru_maxrss=1),
                        types.SimpleNamespace(ru_maxrss=5*1024**3)]
        result = None
        with patch.object(task.resource, 'getrusage', side_effect=observations):
            with self.assertRaisesRegex(ValueError, 'RSS'):
                result = native_convert.write_bridge(store, {'invented': True}, self.budget)
        self.assertEqual(writes, ['NATIVE_BRIDGE.json'])
        self.assertIsNone(result)  # A completion-shaped partial output is not success.


if __name__ == '__main__':
    unittest.main()
