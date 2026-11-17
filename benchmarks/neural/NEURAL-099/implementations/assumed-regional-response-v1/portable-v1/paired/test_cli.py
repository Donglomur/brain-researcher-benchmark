"""Generated operator protocol checks; authentic serve is never called."""
import io
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cli import manifest, operator_loop, strict_json, PACKET_SHA
from session import ARMS


class FakeStudy:
    def __init__(self): self.actions=[]
    def current(self):
        self.actions.append('current')
        return {'generated':True}
    def submit(self,p):
        self.actions.append(('submit',p))
        return {'locked':True}
    def finish(self):
        self.actions.append('finish')
        return {'all_locked':True,'scores_computed':0}


class CliTests(unittest.TestCase):
    def test_dispatch_current_submit_finish(self):
        s=FakeStudy(); out=io.BytesIO()
        commands=[{'operation':'current'}, {'operation':'submit','submission':{'generated':True}}, {'operation':'finish'}]
        source=io.BytesIO(b''.join(json.dumps(v).encode()+b'\n' for v in commands))
        operator_loop(s,source,out,max_message_bytes=4096,max_commands=3)
        records=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([r['operation'] for r in records],['begin','current','submit','finish'])
        self.assertEqual(records[-1]['completion']['scores_computed'],0)

    def test_strict_json_no_duplicate_or_nan(self):
        for data in (b'{"operation":"current","operation":"finish"}',b'{"x":NaN}'):
            with self.assertRaises(ValueError): strict_json(data)
        self.assertIs(type(strict_json(b'{"x":100000000000000000001}')['x']),int)

    def test_command_bounds_and_private_extra_fields(self):
        for raw in (b'{"operation":"current","case_id":"future"}\n',b'{}',b'x'*100+b'\n'):
            with self.assertRaises(ValueError):
                operator_loop(FakeStudy(),io.BytesIO(raw),io.BytesIO(),max_message_bytes=96,max_commands=1)

    def test_frozen_procedure_and_study_id_refuse_before_any_input(self):
        value={'schema':'neural099-paired-operator-manifest/v1',
               'phase':'separately_admitted_authentic_observation_collection',
               'study_id':'synthetic-study','cases_path':'/synthetic/cases',
               'packet_path':'/synthetic/packet','output_path':'/synthetic/output',
               'packet_binding':{'sha256':PACKET_SHA,'bytes':15787200,'case_count':9867},
               'procedure_hashes':{arm:'1'*64 for arm in ARMS},
               'max_message_bytes':262144,'max_record_bytes':262144,
               'max_journal_bytes':1048576,
               'runtime_supervisor_and_isolation_admission_reference':'synthetic-reference'}
        self.assertEqual(manifest(value),value)
        for change in ('hash','study'):
            bad=copy.deepcopy(value)
            if change=='hash': bad['procedure_hashes'][ARMS[0]]='unfrozen'
            else: bad['study_id']='bad study'
            with self.assertRaises(ValueError): manifest(bad)

    def test_no_partial_or_arbitrary_manifest(self):
        for value in ({}, {'phase':'synthetic'}, {'schema':'neural099-paired-operator-manifest/v1'}):
            with self.assertRaises(ValueError): manifest(value)


if __name__=='__main__': unittest.main()
