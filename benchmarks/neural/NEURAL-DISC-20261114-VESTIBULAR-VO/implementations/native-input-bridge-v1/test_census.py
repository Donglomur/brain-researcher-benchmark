"""Generated worker/observer checks; never dispatches the authentic census CLI."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import census as c
import native_mat as n
from test_native_mat import fixture


class WorkerControls(unittest.TestCase):
    def test_complete_generated_worker_output_identity_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'generated.mat';descriptor=fixture(source)
            output=root/'output';output.mkdir()
            receipt=c.census_worker(source,output,{'bytes':1,'sha256':'0'*64},descriptor=descriptor)
            self.assertTrue(receipt['complete_census'])
            self.assertFalse(receipt['biological_binding_verified'])
            self.assertFalse(receipt['historical_Docker_SSL_inventory_verified'])
            body=(output/'PRIVATE_SCHEMA.jsonl').read_bytes()
            self.assertEqual(n.pin(body),receipt['census_artifact'])
            self.assertEqual(len(body),receipt['diagnostics']['census_bytes'])
            self.assertFalse((output/'PRIVATE_SCHEMA.partial.jsonl').exists())
            self.assertEqual((output/'PRIVATE_SCHEMA.jsonl').stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads((output/'WORKER_RECEIPT.json').read_bytes()),receipt)

    def test_failure_preserves_unavailable_diagnostics_without_complete_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'generated.mat';descriptor=fixture(source)
            descriptor['sha256']='0'*64;output=root/'output';output.mkdir()
            receipt=c.census_worker(source,output,{'bytes':1,'sha256':'0'*64},descriptor=descriptor)
            self.assertFalse(receipt['complete_census'])
            self.assertEqual(receipt['failure']['code'],'complete_original_checksum')
            self.assertFalse((output/'PRIVATE_SCHEMA.jsonl').exists())
            self.assertEqual((output/'PRIVATE_SCHEMA.partial.jsonl').read_bytes(),b'')
            self.assertFalse(receipt['diagnostics']['all_variables_loaded'])

    def test_private_writer_refuses_before_exceeding_cap(self):
        body=io.BytesIO();writer=c.CensusWriter(body)
        writer.bytes=n.Limits().census_bytes
        with self.assertRaisesRegex(ValueError,'write_cap'):
            writer.write(b'x')
        self.assertEqual(body.getvalue(),b'')


class ObserverControls(unittest.TestCase):
    def test_generated_natural_zero_child_observation(self):
        receipt,body=c.observe([sys.executable,'-B','-c','print("generated control")'],os.environ.copy(),wall_seconds=5,ram_bytes=128*1024**2)
        self.assertTrue(receipt['natural_exit']);self.assertTrue(receipt['process_reaped'])
        self.assertEqual(receipt['exit_code'],0);self.assertIsNone(receipt['failure'])
        self.assertEqual(body,b'generated control\n')

    def test_deadline_stops_only_owned_generated_child_and_reaps(self):
        receipt,body=c.observe([sys.executable,'-B','-c','import time;time.sleep(5)'],os.environ.copy(),wall_seconds=.2,ram_bytes=128*1024**2)
        self.assertFalse(receipt['natural_exit']);self.assertTrue(receipt['process_reaped'])
        self.assertLess(receipt['exit_code'],0);self.assertEqual(receipt['failure']['code'],'census_wall_deadline')
        self.assertEqual(body,b'');self.assertLess(receipt['elapsed_seconds'],3)

    def test_absent_or_truncated_worker_reads_remain_unknown_and_fully_charged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source={'bytes':1,'sha256':'0'*64}
            for raw in (None,b'{'):
                if raw is not None:(root/'WORKER_RECEIPT.json').write_bytes(raw)
                receipt=c.original_read_accounting(root,source)
                self.assertIsNone(receipt['actual_original_read_bytes'])
                self.assertEqual(receipt['conservative_charged_original_read_bytes'],550565588)

    def test_bound_worker_counter_is_retained_and_wrong_binding_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source={'bytes':1,'sha256':'0'*64}
            receipt={'schema':'vestibular_complete_host_census_worker_v1','source_manifest':source,
                     'original':n.SOURCE,'diagnostics':{'original_bytes_delivered':1234}}
            (root/'WORKER_RECEIPT.json').write_bytes(n.encoded(receipt))
            self.assertEqual(c.original_read_accounting(root,source)['actual_original_read_bytes'],1234)
            self.assertIsNone(c.original_read_accounting(root,{'bytes':2,'sha256':'0'*64})['actual_original_read_bytes'])

    def test_only_authored_allowlisted_failure_codes_are_disclosed(self):
        self.assertEqual(n.failure_record(n.NativeError('census_sampled_RSS_limit'))['code'],'census_sampled_RSS_limit')
        self.assertIsNone(n.failure_record(ValueError('private arbitrary source text'))['code'])
        self.assertNotIn('private arbitrary',json.dumps(n.failure_record(ValueError('private arbitrary source text'))))


if __name__=='__main__':
    unittest.main()
