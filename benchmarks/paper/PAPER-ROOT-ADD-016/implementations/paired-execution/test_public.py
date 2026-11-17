"""Public relocation controls only; generated metadata, no Docker/data/models."""
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 out=importlib.util.module_from_spec(spec);sys.modules[name]=out;spec.loader.exec_module(out);return out

class PublicRelocation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='cardiac-public-source-')
  cls.root=Path(cls.temp.name).resolve()
  cls.checkout=cls.root/'relocated public checkout'
  cls.local=cls.checkout/'benchmarks/paper/PAPER-ROOT-ADD-016/implementations/paired-execution'
  shutil.copytree(HERE,cls.local,ignore=shutil.ignore_patterns('__pycache__'))
  source=HERE.parents[4]
  closure=Path('benchmarks/integrity/current-closures/cardiac-paired-execution/DEPENDENCIES.json')
  target=cls.checkout/closure;target.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(source/closure,target)
  deps=json.loads((source/closure).read_text())['files']
  for rel,row in deps.items():
   target=cls.checkout/rel
   if target.exists():continue
   target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,target)
  cls.forbid_process=patch.object(subprocess,'Popen',side_effect=AssertionError('No process/native execution selected'))
  cls.forbid_socket=patch.object(socket,'socket',side_effect=AssertionError('No network selected'))
  cls.forbid_process.start();cls.forbid_socket.start()
  cls.S=load('execution_support',cls.local/'execution_support.py')
  cls.R=load('cardiac_public_pair_run',cls.local/'pair_run.py')
  cls.api=cls.S.api()
 @classmethod
 def tearDownClass(cls):
  cls.forbid_socket.stop();cls.forbid_process.stop();cls.temp.cleanup()
 def setUp(self):
  self.work=self.root/self._testMethodName;self.work.mkdir()
  self.operands=self.work/'operands';self.operands.mkdir()
  self.reference=self.work/'reference-binding.json'
  self.reference.write_text(json.dumps({'schema':'cardiac_private_reference_binding_v1','benchmark_id':self.S.ID,'input_sha256':'6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11','reference':{'path':'private/generated-reference.json','bytes':17,'sha256':'a'*64}}))
  self.binding={'operands':str(self.operands),'reference_binding':{'path':str(self.reference),**self.S.pin(self.reference.read_bytes())}}
  self.S._PAIR=None;self.S._BINDING=None;self.S._ALLOWED.clear()
  self.packet=self.S.bind_packet(self.binding)
  self.pair=self.work/'pair';self.pair.mkdir()
  receipt=self.packet.receipt('1'*32)
  (self.pair/'receipt.json').write_bytes(self.S.encode(receipt))
  for c in ('A','B'):(self.pair/(c+'.request.json')).write_bytes(self.S.encode(receipt['requests'][c]))
  self.binary=self.work/'generated-never-executed-docker';self.binary.write_text('# never executed\n')
  self.config=self.work/'generated-config';self.config.mkdir()
  self.docker={'executable':str(self.binary),'config':str(self.config),'host':'unix:///generated-unavailable.sock'}
 def test_public_dependency_imports_and_reference_metadata_only(self):
  self.assertEqual(self.S.ROOT,self.checkout)
  self.assertEqual(self.api['contract_profile'].IMAGE,self.S.IMAGE)
  self.assertTrue(str(sys.modules['engine'].__file__).startswith(str(self.checkout/'benchmarks/neural/NEURAL-095/implementations/neural-095-four-cell-runner/source')))
  self.assertEqual((len(self.packet.members('A')),len(self.packet.members('B'))),(41,46))
  self.assertFalse((self.operands/'private/generated-reference.json').exists())
  self.assertFalse(any(x in sys.modules for x in ('numpy','scipy','pymc','pandas')))
  template=json.loads((self.local/'REQUEST.inert.json').read_text())
  self.assertIs(template['execution_authority'],False)
  self.assertIsNone(template['packet_binding']);self.assertIsNone(template['pair_receipt'])
 def test_manifest_relocation_and_child_transport_binding(self):
  run=self.work/'run';run.mkdir();budget=self.api['HostBudget'](run,15000000,3600000)
  programs={}
  for c in ('A','B'):
   p=self.work/(c+'.py');p.write_text('# generated unexecuted '+c+'\n')
   programs[c]={'path':str(p),**self.S.pin(p.read_bytes())}
  review={'programs':programs,'pair_receipt':self.S.pin((self.pair/'receipt.json').read_bytes()),'docker':self.docker}
  self.R.commit_programs(review,run,self.pair,budget)
  self.S._PAIR=None;self.S._BINDING=None
  m=self.S.runtime_manifest(run/'B')
  self.assertEqual(m['packet_binding'],self.binding)
  self.assertEqual(len(m['unit']['public_inputs']),46)
  self.assertEqual(sys.modules['engine'].DOCKER,str(self.binary))
  self.assertEqual(sys.modules['engine'].ENV['DOCKER_HOST'],self.docker['host'])
  self.assertEqual({x['mount_destination'] for x in m['unit']['public_inputs']},set('/input/'+x for x in self.packet.members('B')))
  self.assertFalse(any('private/generated-reference' in x['path'] for x in m['unit']['public_inputs']))
  self.reference.write_text(self.reference.read_text()+'\n')
  with self.assertRaisesRegex(ValueError,'metadata unchanged'):self.S.runtime_manifest(run/'A')
 def test_existing_public_owner_requires_current_route_evidence(self):
  controller={'path':'benchmarks/paper/PAPER-ROOT-ADD-016/implementations/paired-execution/arm_controller.py',**self.S.pin((self.local/'arm_controller.py').read_bytes())}
  evidence={'candidate_id':self.S.ID,'source_closure':self.S.pin((self.S.DEPENDENCIES).read_bytes()),'accepted':False,'entrypoint':self.S.pin((self.local/'pair_run.py').read_bytes()),'controller':controller,'route_interrupt_qualification_current':True}
  ep=self.work/'generated-admission.json';ep.write_bytes(self.S.encode(evidence))
  review={'execution_authority':True,'operator_admission_reviewed':True,'ownership_admission':{'path':str(ep),**self.S.pin(ep.read_bytes())},'controller':controller,'docker':self.docker}
  rp=self.work/'generated-review.json';rp.write_bytes(self.S.encode(review))
  with self.assertRaisesRegex(ValueError,'current route evidence'):self.S.owner(rp,self.local/'pair_run.py')
  evidence['accepted']=True;ep.write_bytes(self.S.encode(evidence));review['ownership_admission'].update(self.S.pin(ep.read_bytes()));rp.write_bytes(self.S.encode(review))
  owner=self.S.owner(rp,self.local/'pair_run.py')
  self.assertEqual(Path(owner.__file__),self.checkout/'benchmarks/shared/program-execution/ownership-v4/process_owner.py')
  target=owner.validate_controller(controller,[sys.executable,str(self.local/'arm_controller.py')])
  self.assertEqual(target,self.local/'arm_controller.py')
  self.assertFalse((self.work/'process_owner.json').exists())
  closure=self.S.DEPENDENCIES;original=closure.read_bytes();closure.write_bytes(original+b'\n')
  try:
   with self.assertRaisesRegex(ValueError,'current route evidence'):self.S.owner(rp,self.local/'pair_run.py')
  finally:closure.write_bytes(original)
 def test_socket_metadata_rejects_actual_controls_and_backslash(self):
  for bad in (chr(0),chr(10),chr(13),chr(9),chr(127),chr(92)):
   value=dict(self.docker,host=self.docker['host']+bad)
   with self.assertRaisesRegex(ValueError,'socket address'):self.S.configure_transport(value)
  self.S.configure_transport(self.docker)
 def test_no_private_publication_bindings_and_exact_source_pins(self):
  for rel,row in json.loads((self.S.DEPENDENCIES).read_text())['files'].items():
   body=(self.checkout/rel).read_bytes();self.assertEqual(self.S.pin(body),row)
  for p in self.local.rglob('*'):
   if p.is_file():
    body=p.read_bytes()
    self.assertIsNone(re.search(b'/Users/'+rb'[A-Za-z0-9_]',body),p.name)
    self.assertNotIn(b'artifacts'+b'-build/',body,p.name)
  self.assertFalse((self.local/'summary_score.py').exists())
  self.assertFalse((self.local/'process_owner.py').exists())

if __name__=='__main__':unittest.main(verbosity=2)
