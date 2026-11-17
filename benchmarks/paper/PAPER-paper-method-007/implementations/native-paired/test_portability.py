"""Ordinary complete source inspection and inert local configuration; no native/data run."""
from pathlib import Path
import ast
import hashlib
import importlib.abc
import json
import os
import socket
import stat
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
INSTALLED=ROOT/'installed'
MIRROR=ROOT/'source_repository'
RUNNER='authoring/delivery-20261105/unitmatch-program-interface-deadline-v2/'
FORBIDDEN={'numpy','scipy','h5py','sklearn','torch','jax','matlab','docker','pandas'}

def forbidden(*args,**kwargs):
    raise AssertionError('No process, network, native or scientific operation')

class NoScientificImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0]in FORBIDDEN:
            raise AssertionError('No scientific/native import: '+fullname)

def module(name,body,path):
    out=types.ModuleType(name);out.__file__=str(path)
    exec(compile(body,str(path),'exec'),out.__dict__)
    return out

class PortableSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if FORBIDDEN.intersection(sys.modules):raise AssertionError('Use a fresh isolated interpreter')
        cls.finder=NoScientificImports();sys.meta_path.insert(0,cls.finder)
        cls.addClassCleanup(sys.meta_path.remove,cls.finder)
        for target,name in ((subprocess,'Popen'),(subprocess,'run'),(socket,'socket'),(socket,'create_connection')):
            blocked=patch.object(target,name,forbidden);blocked.start();cls.addClassCleanup(blocked.stop)
        p=ROOT/'PUBLIC_INVENTORY.json'
        if p.is_symlink()or not p.is_file()or p.stat().st_size>65536:raise AssertionError('Ordinary finite inventory')
        raw=p.read_bytes();inventory=json.loads(raw);cls.bodies={};cls.source_read_bytes=len(raw)
        if not 1<=len(inventory['files'])<=64:raise AssertionError('Finite selected source')
        for row in inventory['files']:
            relative=Path(row['path']);p=ROOT/relative
            if relative.is_absolute()or '..'in relative.parts or str(relative)!=row['path']or row['path']in cls.bodies:
                raise AssertionError('Unique literal relative source path')
            if any(q.is_symlink()for q in(p,*p.parents))or not p.is_file()or not 0<p.stat().st_size<=1048576:
                raise AssertionError('Bounded ordinary selected source')
            body=p.read_bytes();cls.source_read_bytes+=len(body)
            if (len(body),hashlib.sha256(body).hexdigest())!=(row['bytes'],row['sha256']):raise AssertionError('Exact selected body')
            cls.bodies[row['path']]=body
        if cls.source_read_bytes>1048576:raise AssertionError('One MiB source inventory ceiling')
        cls.caller=module('unitmatch_public_caller',cls.bodies['installed/run_native_paired.py'],INSTALLED/'run_native_paired.py')

    @classmethod
    def tearDownClass(cls):
        if FORBIDDEN.intersection(sys.modules):raise AssertionError('Scientific/native dependency imported')

    def test_complete_inventory_and_ordinary_modes(self):
        expected=set(self.bodies)|{'PUBLIC_INVENTORY.json'}
        actual=set()
        for p in [ROOT,*ROOT.rglob('*')]:
            self.assertFalse(p.is_symlink())
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o755 if p.is_dir()else 0o644)
            if p.is_file():actual.add(p.relative_to(ROOT).as_posix())
        self.assertEqual(actual,expected)

    def test_actual_complete_source_inspection_loads_dependencies(self):
        before={name:sys.modules.get(name)for name in ('support','functional','_unitmatch_installed_study','io_utils','_unitmatch_original_interface','_unitmatch_original_metrics','_unitmatch_independent_bank','_unitmatch_native_component')}
        present=set(sys.modules)
        result=self.caller.source_check(MIRROR)
        self.assertEqual(result['owned_source_files'],7)
        self.assertEqual(result['external_source_files'],24)
        self.assertLess(result['source_read_bytes'],1048576)
        for key in ('scientific_execution','native_execution','runtime_qualified'):self.assertIs(result[key],False)
        for name,value in before.items():
            self.assertEqual(name in sys.modules,name in present)
            if name in present:self.assertIs(sys.modules[name],value)

    def test_wrong_binding_refuses_before_dependency_capture(self):
        wrong=dict(self.caller.BINDING_PIN,sha256='0'*64)
        with patch.object(self.caller,'BINDING_PIN',wrong),patch.object(self.caller,'loaded',forbidden):
            with self.assertRaisesRegex(ValueError,'Stable exact source bytes'):
                self.caller.source_check(MIRROR)

    def test_required_external_packet_refuses_before_cohort_or_targets(self):
        absent=ROOT/'required_external_package_not_bundled'
        self.assertFalse(absent.exists())
        preflight=self.caller.Preflight()
        with self.caller.captured_study(preflight)as(study,binding):
            original=study.capture;attempts=[]
            def guard(path,*args,**kwargs):
                self.assertEqual(Path(path),absent/'private/PACKET_MAP.json')
                self.assertEqual(attempts,[]);attempts.append(str(path))
                return original(path,*args,**kwargs)
            with patch.object(study,'capture',guard):
                with self.assertRaises(FileNotFoundError)as error:study.packet_cohort(absent,preflight)
            self.assertEqual(Path(error.exception.filename),absent/'private/PACKET_MAP.json')
            self.assertEqual(len(attempts),1)

    def test_fixed_local_engine_default_ignores_ambient_remote_context(self):
        keys=('absence','runtime_contract');missing=object();previous={k:sys.modules.get(k,missing)for k in keys}
        try:
            for name in keys:
                path='source_repository/'+RUNNER+'vendor/'+name+'.py'
                sys.modules[name]=module(name,self.bodies[path],ROOT/path)
            hostile={'DOCKER_HOST':'tcp://example.invalid:2376','DOCKER_CONTEXT':'remote-example','DOCKER_TLS_VERIFY':'1','DOCKER_CERT_PATH':'/not-a-real-certificate'}
            path='source_repository/'+RUNNER+'vendor/engine.py'
            with patch.dict(os.environ,hostile):engine=module('unitmatch_public_legacy_engine',self.bodies[path],ROOT/path)
            self.assertEqual(engine.ENV['DOCKER_HOST'],'unix:///var/run/docker.sock')
            for key in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):self.assertNotIn(key,engine.ENV)
            observations=[]
            def inert(argv,**kwargs):
                observations.append((argv,kwargs));return subprocess.CompletedProcess(argv,0,b'',b'')
            with patch.object(engine.subprocess,'run',inert):
                result=engine.Engine(time.monotonic()+10,ROOT/'never-created',object()).run(['version'])
            self.assertEqual(result.returncode,0);self.assertEqual(len(observations),1)
            self.assertEqual(observations[0][1]['env']['DOCKER_HOST'],'unix:///var/run/docker.sock')
            self.assertFalse((ROOT/'never-created').exists())
        finally:
            for name,value in previous.items():
                if value is missing:sys.modules.pop(name,None)
                else:sys.modules[name]=value

    def test_actual_runner_manifest_closure_and_unchanged_trusted_env_route(self):
        path='source_repository/'+RUNNER+'bound_io.py'
        io=module('unitmatch_public_runner_io',self.bodies[path],ROOT/path)
        manifest=self.bodies['source_repository/'+RUNNER+'SOURCE_MANIFEST.json']
        source=io.source_capture(MIRROR/RUNNER,hashlib.sha256(manifest).hexdigest())
        self.assertEqual(len(source),19)
        self.assertEqual(source['vendor/engine.py'],self.bodies['source_repository/'+RUNNER+'vendor/engine.py'])
        # The exact inherited transport overrides Engine.run with the trusted
        # runner's explicit binary/env. No transport function is executed here.
        tree=ast.parse(source['transport.py'])
        bind=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='bind')
        inherited=next(n for n in bind.body if isinstance(n,ast.ClassDef)and n.name=='BoundEngine')
        run=next(n for n in inherited.body if isinstance(n,ast.FunctionDef)and n.name=='run')
        calls=[n for n in ast.walk(run)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='call']
        self.assertEqual(len(calls),1)
        self.assertEqual([n.id for n in calls[0].args[:2]],['binary','env'])

if __name__=='__main__':unittest.main(verbosity=2)
