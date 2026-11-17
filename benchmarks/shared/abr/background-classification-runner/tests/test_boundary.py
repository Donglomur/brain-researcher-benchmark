"""Invented export and authenticated-preparation boundary regressions only."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import os
import shutil
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('abr_public_author_fixture',ROOT/'tests/test_runner.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
import verify_export
import prepared_manifest as pm

class Boundary(unittest.TestCase):
    def setUp(self):self.x=a.Controls();self.x.setUp()
    def tearDown(self):self.x.tearDown()

    def rewrite(self,entry,body):
        p=Path(entry['path']);os.chmod(p,0o600);p.write_bytes(body);os.chmod(p,0o400)
        return {'path':str(p),**a.c.pin(body)}

    def test_missing_receipt_never_dispatches(self):
        del self.x.selection['preparation']
        with self.assertRaises(KeyError):self.x.execute()
        self.assertEqual(self.x.calls,[]);self.x.assert_no_score()

    def test_changed_receipt_cannot_reuse_root_pin(self):
        item=self.x.selection['preparation'];raw=Path(item['path']).read_bytes()
        self.rewrite(item,raw+b' ')
        with self.assertRaisesRegex(ValueError,'ordinary_input|input_pin'):self.x.execute()
        self.assertEqual(self.x.calls,[]);self.x.assert_no_score()

    def test_structurally_valid_alternative_manifest_fails_preparation_join(self):
        m=copy.deepcopy(self.x.manifest)
        renamed={r['animal_id']:'animal_'+hashlib.sha256(('alternate-invented/'+r['animal_id']).encode()).hexdigest()for r in m['animals']}
        for row in m['animals']:row['animal_id']=renamed[row['animal_id']]
        m['animals'].sort(key=lambda row:row['animal_id'])
        for f in m['folds']:
            for key in ('train_animal_ids','test_animal_ids'):f[key]=sorted(renamed[x]for x in f[key])
            for inner in f['inner_folds']:
                for key in ('train_animal_ids','validation_animal_ids'):inner[key]=sorted(renamed[x]for x in inner[key])
        a.split.validate_manifest(m)  # Structure alone is intentionally insufficient.
        comp=a.c.decode(Path(self.x.selection['completion']['path']).read_bytes())
        comp['private_manifest_sha256']=a.split.digest(m)
        for row in comp['animal_files']:row['name']=renamed[row['name'][:-5]]+'.json'
        self.x.selection['manifest']=self.rewrite(self.x.selection['manifest'],a.c.encode(m))
        self.x.selection['completion']=self.rewrite(self.x.selection['completion'],a.c.encode(comp))
        with self.assertRaisesRegex(ValueError,'preparation exact opaque operands'):self.x.execute()
        self.assertEqual(self.x.calls,[]);self.x.assert_no_score()

    def test_receipt_assertions_and_pins_are_closed(self):
        value=a.c.decode(Path(self.x.selection['preparation']['path']).read_bytes())
        mp={k:self.x.selection['manifest'][k]for k in ('bytes','sha256')}
        cp={k:self.x.selection['completion'][k]for k in ('bytes','sha256')}
        for mode in ('flag','count','hash','extra','bool','float_count','bool_count'):
            bad=copy.deepcopy(value)
            if mode=='flag':bad['full_private_validation']=False
            if mode=='count':bad['counts']['inner_partitions']=19
            if mode=='hash':bad['opaque_manifest']['sha256']='0'*64
            if mode=='extra':bad['candidate_approved']=True
            if mode=='bool':bad['private_validator']['bytes']=True
            if mode=='float_count':bad['counts']['animals']=104.0
            if mode=='bool_count':bad['counts']['animals']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):pm.validate_receipt(bad,mp,cp)

    def test_rendered_configuration_rejects_rebound_preparation(self):
        request,result,bodies,wrapper,metadata=self.x.configured()
        item=wrapper['selection']['preparation']
        wrapper['selection']['preparation']=dict(item,sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'exact predeclared packet'):self.x.admission(request,bodies,wrapper)
        self.assertEqual(self.x.calls,[])

    def test_opaque_schema_partitions_and_policy_fail_closed(self):
        for mode in ('private_identity','bool_label','duplicate','outer','inner','state','order','class_float','class_bool','class_extra'):
            m=copy.deepcopy(self.x.manifest)
            if mode=='private_identity':m['animals'][0]['released_mouse_id']='invented-only'
            if mode=='bool_label':m['animals'][0]['label']=True
            if mode=='duplicate':m['animals'][1]=dict(m['animals'][0])
            if mode=='outer':m['folds'][0]['test_animal_ids'].pop()
            if mode=='inner':m['folds'][0]['inner_folds'][0]['validation_animal_ids'][0]=m['folds'][0]['test_animal_ids'][0]
            if mode=='state':m['state_policy']['cohort_derived_state_shared_between_outer_folds']=True
            if mode=='order':m['animals'].reverse()
            if mode=='class_float':m['class_counts']['0']=54.0
            if mode=='class_bool':m['class_counts']['0']=True
            if mode=='class_extra':m['class_counts']['extra']=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):a.split.validate_manifest(m)

    def test_exact_tree_and_relocated_render(self):
        moved=self.x.root/'relocated-source';shutil.copytree(ROOT,moved)
        result=verify_export.verify(moved);self.assertTrue(result['public_source_only'])
        request=self.x.render_request()
        rendered=a.provision.render(request,source_root=moved)
        self.assertFalse(rendered['dispatch_performed'])
        self.assertFalse(Path(rendered['required_selection_path']).exists())
        generated=Path(request['package_root'])
        lock=a.c.decode((generated/'EXECUTION_LOCK.json').read_bytes())
        self.assertEqual(len(lock['members']),16)
        self.assertIn('runtime/prepared_manifest.py',lock['members'])

    def test_source_census_digest_and_symlink_tampering(self):
        for mode in ('extra','digest','missing','symlink'):
            root=self.x.root/('copy-'+mode);shutil.copytree(ROOT,root)
            if mode=='extra':(root/'unexpected.json').write_bytes(b'{}')
            if mode=='digest':
                p=root/'runtime/score.py';p.write_bytes(p.read_bytes()+b'\n')
            if mode=='missing':(root/'TASK.md').unlink()
            if mode=='symlink':(root/'unexpected-link').symlink_to(root/'TASK.md')
            with self.subTest(mode=mode),self.assertRaises(ValueError):verify_export.verify(root)

    def test_private_body_and_label_builder_exclusions(self):
        bodies=[p+b'invented-only'for p in verify_export.FORBIDDEN]
        bodies += [('animal_'+'a'*64).encode(),b'def '+b'build_'+b'manifest(x):\n    return x\n']
        for body in bodies:
            with self.subTest(body_length=len(body)),self.assertRaises(ValueError):verify_export.content('invented.py',body)
        for name in ('../bad','/bad','a/../b','a\\b','.hidden'):
            with self.subTest(name=name),self.assertRaises(ValueError):verify_export.relative(name)

if __name__=='__main__':unittest.main(verbosity=2)
