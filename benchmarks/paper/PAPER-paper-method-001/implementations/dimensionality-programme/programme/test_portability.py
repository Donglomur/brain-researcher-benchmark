"""Standard-library source relocation controls; no scientific kernels or data."""
from pathlib import Path
import ast
import hashlib
import importlib.abc
import json
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
FORBIDDEN={'numpy','scipy','jax','opt_einsum','cryptography'}
class NoScientificImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in FORBIDDEN:
            raise AssertionError('Numerical or cryptographic import forbidden: '+fullname)
sys.meta_path.insert(0,NoScientificImports())
sys.path.insert(0,str(ROOT))
from finite_runtime import entry
from finite_runtime.common import Refusal
from finite_runtime.planner import Contracts,NORMATIVE_JSON

class PortableSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_bytes())
        cls.rows=cls.manifest['files']
        cls.bodies={r['path']:(ROOT/r['path']).read_bytes() for r in cls.rows}
        cls.documents={n:json.loads(cls.bodies['accepted-design/'+n+'.json']) for n in NORMATIVE_JSON}
    def test_full_inventory(self):
        expected={r['path'] for r in self.rows}|{'SOURCE_MANIFEST.json'}
        actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
        self.assertEqual(actual,expected)
        self.assertEqual(len(expected),82)
        for r in self.rows:
            body=self.bodies[r['path']]
            self.assertEqual(len(body),r['bytes'])
            self.assertEqual(hashlib.sha256(body).hexdigest(),r['sha256'])
    def test_exact_runtime_and_contract_counts(self):
        self.assertEqual(sum(r['kind']=='runtime' for r in self.rows),59)
        self.assertEqual(sum(r['kind']=='normative_contract' for r in self.rows),13)
        for r in self.rows:
            if r['kind']=='runtime':ast.parse(self.bodies[r['path']],filename=r['path'])
    def test_actual_contract_metadata(self):
        c=Contracts(self.documents)
        self.assertEqual(len(c.obligations),42)
        self.assertEqual(len(c.operators),32)
        self.assertEqual(len(c.keys),24)
        self.assertEqual(len(c.bank),17)
        census=c.preflight_census()
        self.assertEqual(census['point_variants'],187)
        self.assertEqual(census['uncertainty_variants'],1963)
        self.assertEqual(census['required_R_obligations'],37)
        self.assertEqual(census['required_I_obligations'],5)
    def test_fixed_policy_and_all_gates(self):
        p=json.loads(self.bodies['TRUSTED_POLICY.json'])
        self.assertEqual(p['status'],'BUILD_ONLY')
        self.assertIsNone(p['issuer'])
        self.assertIsNone(p['issuer_public_key_hex'])
        self.assertIs(p['scientific_execution_selected'],False)
        self.assertEqual(set(p['open_gates']),{f'G{i:02d}' for i in range(1,25)})
        gates=self.documents['FUTURE_QUALIFICATION']['gates']
        self.assertEqual(len(gates),24)
        self.assertTrue(all(g['status']=='OPEN' for g in gates))
    def test_actual_entry_refuses_before_invocation(self):
        original=entry.bounded_control
        seen=[]
        def only_policy(path,*args,**kwargs):
            self.assertEqual(Path(path),ROOT/'TRUSTED_POLICY.json')
            seen.append(Path(path));return original(path,*args,**kwargs)
        with patch.object(entry,'bounded_control',only_policy):
            for condition in [None,*entry.CONDITIONS]:
                with self.assertRaises(Refusal) as failure:
                    entry.run('invented-invocation-must-not-open.json','invented-output-must-not-create',condition)
                self.assertEqual(failure.exception.code,'BUILD_ONLY_SCIENTIFIC_EXECUTION_DISABLED')
        self.assertEqual(len(seen),len(entry.CONDITIONS)+1)
        self.assertFalse((Path.cwd()/'invented-output-must-not-create').exists())
    def test_relative_import_closure(self):
        runtime={r['path'] for r in self.rows if r['kind']=='runtime'}
        for name in runtime:
            a=ast.parse(self.bodies[name]);parts=Path(name).parent.parts
            for node in ast.walk(a):
                if isinstance(node,ast.ImportFrom) and node.level:
                    base=parts[:len(parts)-node.level+1]
                    if node.module:
                        root='/'.join((*base,*node.module.split('.')))
                        self.assertTrue(root+'.py' in runtime or root+'/__init__.py' in runtime,(name,root))
                    else:
                        for alias in node.names:
                            root='/'.join((*base,alias.name))
                            self.assertTrue(root+'.py' in runtime or root+'/__init__.py' in runtime,(name,root))
    def test_full_majaj_source_is_inside_programme(self):
        roles={r['path'] for r in self.rows if r['kind']=='runtime'}
        self.assertIn('finite_runtime/majaj_route.py',roles)
        self.assertIn('finite_runtime/science.py',roles)
        self.assertIn('scientific-runtime/finite_science/majaj.py',roles)
        self.assertIn('scientific-runtime/finite_science/majaj_core.py',roles)
        self.assertIn('scientific-runtime/finite_science/literal.py',roles)
        self.assertEqual(len(self.documents['INPUTS']['roles']),26)
        self.assertEqual(len(self.documents['COHORTS']['records']),13)
    def test_no_scientific_import_or_execution_authority(self):
        self.assertFalse(FORBIDDEN.intersection(sys.modules))
        p=json.loads(self.bodies['PROVENANCE.json'])
        self.assertIs(p['scientific_execution_enabled'],False)
        self.assertEqual(p['registration_increment'],0)
        self.assertEqual(p['qualification_increment'],0)

if __name__=='__main__':unittest.main(verbosity=2)
