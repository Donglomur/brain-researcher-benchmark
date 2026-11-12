"""Ordinary-checkout source/capability checks only; no scientific execution."""
from pathlib import Path
import hashlib
import importlib.abc
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
REPOSITORY=ROOT.parents[2]
VIRTUAL_SERIALIZED_IO_PRECHARGE=65536
SOURCE_READ_LIMIT=1048576
FORBIDDEN={'numpy','scipy','sklearn','torch','jax'}
class ForbidNumerical(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in FORBIDDEN:raise AssertionError('No numerical import: '+fullname)
sys.meta_path.insert(0,ForbidNumerical())
def forbidden(*args,**kwargs):raise AssertionError('No subprocess, network or scientific execution')
class DeniedToken:
    def require_model_bound(self,spec):raise RuntimeError('Explicit inert TokenAdmission refusal')
class DeniedSupervisor:
    def require_execution(self,context):raise RuntimeError('Explicit inert supervisor refusal')
    def require_grading(self,context):raise RuntimeError('Explicit inert supervisor refusal')
class Portability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory=json.loads((ROOT/'PUBLIC_INVENTORY.json').read_bytes())
        cls.rows=cls.inventory['files']
        cls.pins={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in cls.rows}
        spec=importlib.util.spec_from_file_location('openbmi_portable_trusted_entry',ROOT/'successor/trusted_entry.py')
        cls.entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.entry)
        with patch.object(subprocess,'Popen',forbidden),patch.object(socket,'create_connection',forbidden):
            cls.source=cls.entry.capture(REPOSITORY,ROOT/'SOURCE_MANIFEST.json',cls.pins['SOURCE_MANIFEST.json'],deadline=time.monotonic()+30,read_limit=SOURCE_READ_LIMIT)
        cls.virtual_bytes=len(json.dumps({'incumbent':dict(cls.source.incumbent_pin),'source':dict(cls.source.source_pin)}).encode())
        assert cls.virtual_bytes<VIRTUAL_SERIALIZED_IO_PRECHARGE
    def test_ordinary_checkout_inventory(self):
        self.assertEqual(len(self.rows),46)
        expected={r['path'] for r in self.rows}|{'PUBLIC_INVENTORY.json'}
        self.assertEqual({p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()},expected)
        for p in [ROOT,*ROOT.rglob('*')]:
            self.assertFalse(p.is_symlink())
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o755 if p.is_dir() else 0o644)
        for r in self.rows:
            b=(ROOT/r['path']).read_bytes();self.assertEqual(len(b),r['bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),r['sha256'])
    def test_complete_real_capture(self):
        self.assertEqual((len(self.source.old),len(self.source.new),len(self.source.dependencies),len(self.source.external)),(18,11,4,8))
        self.assertEqual(self.source.incumbent_pin,self.entry.INCUMBENT_PIN)
        expected=sum(len(b)+1 for group in [self.source.old,self.source.new,self.source.dependencies,self.source.external] for b in group.values())
        expected+=self.pins['SOURCE_MANIFEST.json']['bytes']+1+self.pins['incumbent/SOURCE_MANIFEST.json']['bytes']+1
        self.assertEqual(self.source.read_reservations,expected)
    def test_missing_token_capability_refuses(self):
        for bad in [None,False,{}]:
            with self.assertRaisesRegex(ValueError,'External TokenAdmission'):
                self.entry.build(self.source,token_admission=bad)
    def test_actual_definition_build_and_restore(self):
        old_path=sys.path[:];old_modules={n:sys.modules.get(n) for n in ['protocol','broker_factory','morse_protocol','morse_broker','morse_docker']}
        with patch.object(subprocess,'Popen',forbidden),patch.object(socket,'create_connection',forbidden):
            runtime=self.entry.build(self.source,token_admission=DeniedToken())
        self.assertEqual(sys.path,old_path)
        self.assertEqual({n:sys.modules.get(n) for n in old_modules},old_modules)
        self.assertIs(runtime.source,self.source)
        p=runtime.modules['scientific_protocol.py']
        self.assertEqual((len(p.PEOPLE),len(p.SESSIONS),len(p.SETTINGS),len(p.ARMS)),(54,2,4,3))
        self.assertEqual(self.entry.PANELS,('frozen_program','case_adaptive','reference'))
        self.assertIn('original_scorer',runtime.modules)
        with self.assertRaisesRegex(RuntimeError,'inert TokenAdmission'):runtime.token_admission.require_model_bound({})
    def test_missing_and_denying_supervisor_refuse(self):
        for action in ['execution','grading']:
            for bad in [None,False,{}]:
                with self.assertRaisesRegex(ValueError,'External supervisor'):self.entry._supervise(bad,action,{})
            with self.assertRaisesRegex(RuntimeError,'inert supervisor'):self.entry._supervise(DeniedSupervisor(),action,{})
    def test_no_scientific_or_runtime_admission(self):
        self.assertFalse(FORBIDDEN.intersection(sys.modules))
        p=json.loads((ROOT/'PROVENANCE.json').read_bytes())
        self.assertIs(p['external_execution_authority_supplied'],False)
        self.assertIs(p['scientific_qualification'],False)
        self.assertEqual(p['registration_increment'],0)
if __name__=='__main__':unittest.main(verbosity=2)
