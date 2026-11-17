"""Generated portable-source boundary checks. No data, Docker or model calls."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
    raise RuntimeError('Invoke with Python -I -B')
HERE = Path(__file__).absolute().parent
verifier = types.ModuleType('neural030_package_verifier')
verifier.__file__ = str(HERE/'package.py')
exec(compile((HERE/'package.py').read_bytes(), verifier.__file__, 'exec'), verifier.__dict__)


class PackageControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural030-portable-control-')
        self.base = Path(self.temp.name).resolve()
        self.root = self.base/'unrelated-location'
        self.raw, self.pin = verifier.manifest_pin()
        self.manifest, self.bodies = verifier.verify(self.pin['bytes'], self.pin['sha256'])
        self.root.mkdir()
        for name, body in self.bodies.items():
            (self.root/name).write_bytes(body)
        (self.root/'SOURCE_MANIFEST.json').write_bytes(self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        return verifier.verify(self.pin['bytes'], self.pin['sha256'], self.root)

    def repin_manifest(self, manifest=None, raw=None):
        raw = raw if raw is not None else (json.dumps(manifest, sort_keys=True)+'\n').encode()
        (self.root/'SOURCE_MANIFEST.json').write_bytes(raw)
        self.pin = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}

    def test_relocated_real_cli_check_and_inspect(self):
        unrelated = self.base/'cwd'; unrelated.mkdir()
        for operation in ('check','inspect'):
            result = subprocess.run([sys.executable,'-I','-B',str(self.root/'package.py'),operation,
                '--source-bytes',str(self.pin['bytes']),'--source-sha256',self.pin['sha256']],
                cwd=unrelated, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value['task_id'],'NEURAL-030')
            if operation == 'check':
                self.assertTrue(value['closed_source_verified'])
            else:
                self.assertEqual((value['sessions'],value['dispatches']),(16,128))
            self.assertFalse(value['scientific_qualification'])
            self.assertFalse(value['native_qualification'])

    def test_missing_extra_cache_and_nested_members_refused(self):
        extra = self.root/'unexpected.txt'; extra.write_text('generated extra')
        with self.assertRaises(ValueError):self.check()
        extra.unlink()
        extra = self.root/'__pycache__'; extra.mkdir(); (extra/'run.pyc').write_bytes(b'generated cached bytecode')
        with self.assertRaises(ValueError):self.check()
        shutil.rmtree(extra)
        (self.root/'baseline.py').unlink()
        with self.assertRaises(ValueError):self.check()

    def test_changed_source_refused_before_execution(self):
        marker = self.base/'must-not-exist'
        attack = '\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("bad")\n'
        (self.root/'run.py').write_bytes(self.bodies['run.py']+attack.encode())
        result = subprocess.run([sys.executable,'-I','-B',str(self.root/'package.py'),'inspect',
            '--source-bytes',str(self.pin['bytes']),'--source-sha256',self.pin['sha256']],
            capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(marker.exists())

    def test_member_and_root_links_refused(self):
        member = self.root/'baseline.py'; member.unlink()
        donor = self.base/'generated-donor.py'; donor.write_bytes(self.bodies['baseline.py'])
        member.symlink_to(donor)
        with self.assertRaises(ValueError):self.check()
        member.unlink(); os.link(donor,member)
        with self.assertRaises(ValueError):self.check()
        member.unlink(); member.write_bytes(self.bodies['baseline.py'])
        alias = self.base/'linked-root'; alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):verifier.verify(self.pin['bytes'],self.pin['sha256'],alias)
        with self.assertRaises(ValueError):
            verifier.verify(self.pin['bytes'],self.pin['sha256'],Path('//'+str(self.root).lstrip('/')))

    def test_self_consistent_omission_is_not_complete_source(self):
        (self.root/'baseline.py').unlink(); del self.manifest['files']['baseline.py']
        self.repin_manifest(self.manifest)
        with self.assertRaisesRegex(ValueError,'Complete required'):self.check()

    def test_duplicate_extra_and_invalid_manifest_fields(self):
        duplicate = ('{"task_id":"NEURAL-030",'+self.raw.decode().lstrip()[1:]).encode()
        self.repin_manifest(raw=duplicate)
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.check()
        value = json.loads(self.raw); value['unexpected']=True; self.repin_manifest(value)
        with self.assertRaises(ValueError):self.check()
        value = json.loads(self.raw); value['files']['baseline.py']['bytes']=True; self.repin_manifest(value)
        with self.assertRaises(ValueError):self.check()
        value = json.loads(self.raw); value['files']['baseline.py']['bytes']=1048577; self.repin_manifest(value)
        with self.assertRaises(ValueError):self.check()

    def test_wrong_manifest_pin_refused(self):
        with self.assertRaisesRegex(ValueError,'Selected manifest'):
            verifier.verify(self.pin['bytes'],'0'*64,self.root)

    def test_authored_import_closure_and_scientific_inheritance(self):
        local = {Path(name).stem for name in self.bodies if name.endswith('.py')}
        allowed = set(sys.stdlib_module_names) | local | {'numpy'}
        for name, body in self.bodies.items():
            if not name.endswith('.py'):continue
            for node in ast.walk(ast.parse(body,filename=name)):
                if isinstance(node,ast.Import):
                    roots = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node,ast.ImportFrom):
                    self.assertEqual(node.level,0,(name,node.lineno))
                    roots = [(node.module or '').split('.')[0]]
                else:continue
                self.assertTrue(set(roots) <= allowed,(name,roots))
        provenance = json.loads(self.bodies['PROVENANCE.json'])
        self.assertEqual(len(provenance['scientific_modules']),7)
        inherited = provenance['unchanged_authored_members']
        self.assertEqual(sum(x['file'].endswith('.py') for x in inherited),18)
        for row in inherited:
            body = self.bodies[row['file']]
            self.assertEqual((len(body),hashlib.sha256(body).hexdigest()),(row['bytes'],row['sha256']))
        self.assertFalse(provenance['primary_code_vendored'])
        self.assertEqual(self.bodies['requirements.txt'],b'numpy==2.2.6\n')

    def test_complete_population_and_no_private_checkout_reference(self):
        def literal(source,name):
            for node in ast.parse(source).body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
                    return ast.literal_eval(node.value)
            self.fail(name)
        groups = literal(self.bodies['source_binding.py'],'GROUPS')
        self.assertEqual([v[2] for v in groups.values()],[5,5,6])
        self.assertEqual([v[1] for v in groups.values()],[1.,2.,2.])
        self.assertEqual(literal(self.bodies['views.py'],'ARMS'),('context_handle','grc','cf','joint'))
        self.assertEqual(literal(self.bodies['views.py'],'MODES'),('frozen_program','case_adaptive_equal_inputs_tools_compute'))
        self.assertEqual(sum(x[2] for x in groups.values())*4*2,128)
        for name,body in self.bodies.items():
            self.assertNotIn(b'neuroscience-' + b'benchmark-planning',body,name)
            self.assertNotIn(b'authoring/' + b'delivery-',body,name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
