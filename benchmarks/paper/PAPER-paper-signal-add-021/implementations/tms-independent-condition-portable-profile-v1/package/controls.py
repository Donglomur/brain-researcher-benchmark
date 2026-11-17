"""Unrun invented relocation controls. No Docker, authentic assets or models."""
import copy
import hashlib
import importlib.util
import json
import math
import os
import signal
import stat
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest

SOURCE=Path(__file__).absolute().parent
sys.path.insert(0,str(SOURCE))
import portable_config as pc

def entry(path,n=1,h=None):
    return {'path':str(path),'bytes':n,'sha256':h or '0'*64}

def invented(root):
    roles={n:entry(root/'owner'/n) for n in pc.ASSETS}
    for n,(size,h) in pc.PINS.items():roles[n]=entry(root/'owner'/n,size,h)
    roles['input_manifest']=entry(root/'input/INPUT.json',100)
    roles['input_values']=entry(root/'input/values.f64',11665920)
    return {'schema':'tms_portable_owner_config_v1','profile':pc.PROFILE,
            'private_use_authorized':True,'workspace':str(root/'attempts'),
            'runtime':{'host_python':entry(root/'python',100),'host_version':[3,11,6],
              'host_system':'Linux','docker':entry(root/'docker',100),
              'socket':str(root/'engine.sock'),
              'socket_identity':{'dev':1,'inode':2,'mode':49645,'uid':1000,'gid':1000,'nlink':1},
              'image':pc.IMAGE,'container_user':'1000:1000'},
            'assets':roles,'reference':{'root':str(root/'private-reference'),
              'descriptor':{'bytes':100,'sha256':'1'*64},'source_lock_sha256':'2'*64}}

class RelocationControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tms-portable-invented-')
        self.root=Path(self.tmp.name).resolve(strict=True)
        self.cfg=invented(self.root)
    def tearDown(self):
        self.tmp.cleanup()
    def refused(self,fn,*args):
        with self.assertRaises((ValueError,OSError)):fn(*args)
    def test_two_distinct_roots_preserve_complete_profile(self):
        a=pc.validate(self.cfg);b=pc.validate(invented(self.root/'second'))
        self.assertNotEqual(a['workspace'],b['workspace'])
        self.assertEqual(a['profile'],b['profile'])
        self.assertEqual(set(a['assets']),set(b['assets']))
        self.assertEqual(a['assets']['input_values']['bytes'],11665920)
    def test_missing_role_refuses(self):
        del self.cfg['assets']['input_values'];self.refused(pc.validate,self.cfg)
    def test_extra_role_refuses(self):
        self.cfg['assets']['answers']=entry(self.root/'answers');self.refused(pc.validate,self.cfg)
    def test_changed_source_material_pin_refuses(self):
        self.cfg['assets']['paper']['sha256']='3'*64;self.refused(pc.validate,self.cfg)
    def test_partial_projection_refuses(self):
        self.cfg['assets']['input_values']['bytes']-=8;self.refused(pc.validate,self.cfg)
    def test_boolean_extent_refuses(self):
        self.cfg['assets']['projection_review']['bytes']=True;self.refused(pc.validate,self.cfg)
    def test_undeclared_profile_refuses(self):
        self.cfg['profile']='paired-person';self.refused(pc.validate,self.cfg)
    def test_missing_authority_refuses(self):
        self.cfg['private_use_authorized']=False;self.refused(pc.validate,self.cfg)
    def test_reference_inside_input_refuses(self):
        self.cfg['reference']['root']=str(self.root/'input/private');self.refused(pc.validate,self.cfg)
    def test_input_inside_reference_refuses(self):
        self.cfg['reference']['root']=str(self.root);self.refused(pc.validate,self.cfg)
    def test_reference_inside_attempts_refuses(self):
        self.cfg['reference']['root']=str(self.root/'attempts/private');self.refused(pc.validate,self.cfg)
    def test_auxiliary_file_in_input_refuses(self):
        self.cfg['assets']['reference_review']['path']=str(self.root/'input/secret')
        self.refused(pc.validate,self.cfg)
    def test_changed_image_refuses(self):
        self.cfg['runtime']['image']='sha256:'+'4'*64;self.refused(pc.validate,self.cfg)
    def test_implicit_platform_equivalence_refuses(self):
        self.cfg['runtime']['host_system']='Windows';self.refused(pc.validate,self.cfg)
    def test_wrong_interpreter_version_refuses(self):
        self.cfg['runtime']['host_version']=[3,12,8];self.refused(pc.validate,self.cfg)
    def test_untyped_socket_identity_refuses(self):
        self.cfg['runtime']['socket_identity']['inode']=True;self.refused(pc.validate,self.cfg)
    def test_noninteger_container_user_refuses(self):
        self.cfg['runtime']['container_user']='root';self.refused(pc.validate,self.cfg)
    def test_source_asset_symlink_refuses(self):
        p=self.root/'target';p.write_bytes(b'x');q=self.root/'alias';q.symlink_to(p)
        self.refused(pc.path,str(q))
    def test_path_traversal_refuses(self):
        self.refused(pc.path,str(self.root/'x/../secret'))
    def test_mount_separator_refuses(self):
        self.refused(pc.path,str(self.root/'x,readonly=false'))
    def test_duplicate_json_key_refuses(self):
        self.refused(pc.decode,b'{"a":1,"a":2}')
    def test_nonfinite_json_refuses(self):
        self.refused(pc.decode,b'{"a":NaN}')
    def test_missing_owner_asset_clear_failure(self):
        with self.assertRaisesRegex(ValueError,'missing owner-provided asset'):
            pc.read(entry(self.root/'missing'),10)
    def test_exact_owned_file_and_tampered_file(self):
        p=self.root/'small';p.write_bytes(b'abc');os.chmod(p,0o400)
        e=entry(p,3,hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(pc.read(e,3,0o400),b'abc')
        os.chmod(p,0o600);p.write_bytes(b'abd');os.chmod(p,0o400)
        self.refused(pc.read,e,3,0o400)
    def test_hardlinked_asset_refuses(self):
        p=self.root/'one';p.write_bytes(b'x');os.link(p,self.root/'two')
        self.refused(pc.read,entry(p,1,hashlib.sha256(b'x').hexdigest()),1)
    def test_missing_configuration_clear_failure(self):
        with self.assertRaisesRegex(ValueError,'missing owner configuration'):
            pc.load(str(self.root/'missing.json'),'0'*64)
    def test_stale_configuration_pin_refuses(self):
        p=self.root/'config';raw=(json.dumps(self.cfg)+'\n').encode();p.write_bytes(raw);os.chmod(p,0o400)
        self.refused(pc.load,str(p),'f'*64)
    def test_complete_configuration_load_is_owner_only(self):
        p=self.root/'config';raw=(json.dumps(self.cfg)+'\n').encode();p.write_bytes(raw);os.chmod(p,0o400)
        self.assertEqual(pc.load(str(p),hashlib.sha256(raw).hexdigest())['profile'],pc.PROFILE)
    def test_fixture_arm_exposure_is_exact(self):
        import common,packet
        docs={n:b'invented material\n' for n in packet.DOCS}
        budget=common.Budget(time.monotonic()+10,1<<20,1<<20)
        a=packet.stage_materials(self.root/'A',arm='A',mode='inert',document_bodies=docs,budget=budget)
        b=packet.stage_materials(self.root/'B',arm='B',mode='inert',document_bodies=docs,budget=budget)
        self.assertTrue(packet.paired_materials(a,b))
        self.assertEqual(a['code'],{})
        self.assertEqual(set(b['code']),{'fixture_assistance.py'})
        self.assertNotIn('reference',a['exact_top_level'])
    def test_fresh_attempt_id_and_manifest_binding(self):
        import outer_once
        selected={'comparator_calibration':False}
        raw=json.dumps({'schema':'tms_local_method_reconstruction_run_v1',
                        'attempt_id':'first','selection':selected}).encode()
        h=hashlib.sha256(raw).hexdigest()
        self.assertEqual(outer_once.admit_manifest(raw,h,'first'),selected)
        self.refused(outer_once.admit_manifest,raw,h,'second')
        self.refused(outer_once.checked_attempt,'../reuse')
        p=self.root/'attempt';p.mkdir()
        with self.assertRaises(FileExistsError):p.mkdir()
    def test_source_lock_relocates_without_content_change(self):
        body=b'# invented source, never executed\n'
        lock={'schema':'tms_portable_source_lock_v1','members':
              {'demo.py':{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}}
        raw=json.dumps(lock).encode();h=hashlib.sha256(raw).hexdigest()
        for name in ('source-one','source-two'):
            p=self.root/name;p.mkdir();(p/'demo.py').write_bytes(body)
            (p/'PORTABLE_SOURCE_LOCK.json').write_bytes(raw)
            observed,_=pc.load_source(str(p),h)
            self.assertEqual(observed,{'demo.py':body})
    def test_changed_source_and_missing_source_refuse(self):
        p=self.root/'source';p.mkdir();body=b'original\n'
        lock={'schema':'tms_portable_source_lock_v1','members':
              {'demo.py':{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}}
        raw=json.dumps(lock).encode();h=hashlib.sha256(raw).hexdigest()
        (p/'PORTABLE_SOURCE_LOCK.json').write_bytes(raw)
        self.refused(pc.load_source,str(p),h)
        (p/'demo.py').write_bytes(b'changed!\n')
        self.refused(pc.load_source,str(p),h)
    def test_stale_run_configuration_authority_refuses(self):
        import bridge
        pc._STATE={'config':self.cfg,'sha256':'a'*64,'source_bodies':{}}
        selected={'schema':'tms_portable_selected_reconstruction_v1',
          'config_sha256':'a'*64,'private_local_delivery_selected':True,
          'transient_reference_use_selected':True,'model_calls':0,
          'programs':{'A':entry(self.root/'A.py'),'B':entry(self.root/'B.py')},
          'comparator_calibration':False}
        self.assertEqual(bridge.selection(selected),selected)
        selected['config_sha256']='b'*64;self.refused(bridge.selection,selected)
    def test_changed_arm_authority_refuses(self):
        import bridge
        pc._STATE={'config':self.cfg,'sha256':'a'*64,'source_bodies':{}}
        selected={'schema':'tms_portable_selected_reconstruction_v1',
          'config_sha256':'a'*64,'private_local_delivery_selected':True,
          'transient_reference_use_selected':True,'model_calls':0,
          'programs':{'A':entry(self.root/'A.py'),'C':entry(self.root/'B.py')},
          'comparator_calibration':False}
        self.refused(bridge.selection,selected)

class OwnerBoundaryControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tms-portable-boundary-')
        self.root=Path(self.tmp.name).resolve(strict=True)
        self.cfg=invented(self.root)
        self.cfg['runtime']['container_user']='1607:2609'
        self.cfg['runtime']['socket_identity']={
            'dev':12,'inode':34,'mode':stat.S_IFSOCK|0o600,
            'uid':0,'gid':0,'nlink':1}
        self.stack=ExitStack()
        self.stack.enter_context(mock.patch.object(pc,'_STATE',{
            'config':self.cfg,'sha256':'a'*64,'source_bodies':{}}))
    def tearDown(self):
        self.stack.close()
        self.tmp.cleanup()
    def docker(self):
        import docker_owner as owner
        for name in ('DOCKER','CONTAINER_USER','DAEMON_SOCKET','DAEMON_GUARD',
                     '_CLI_CONFIG','_CLI_ENV'):
            self.stack.enter_context(mock.patch.object(owner,name,None))
        owner.configure_portable(self.cfg)
        return owner
    def test_configured_uid_and_exact_mounts_exclude_private_assets(self):
        owner=self.docker()
        paths=(self.root/'input',self.root/'task',self.root/'candidate.py')
        args=owner.create_argv('invented-owner',*paths)
        mounts=[args[i+1] for i,v in enumerate(args) if v=='--mount']
        self.assertEqual(args[0],self.cfg['runtime']['docker']['path'])
        self.assertIn('--user=1607:2609',args)
        self.assertEqual(mounts,[
            'type=bind,src='+str(path)+',dst='+dest+',readonly'
            for path,dest in zip(paths,('/input','/task','/candidate/solution.py'))])
        joined=' '.join(args)
        self.assertNotIn(self.cfg['reference']['root'],joined)
        for role in ('reference_review','runtime_review','identity'):
            self.assertNotIn(self.cfg['assets'][role]['path'],joined)
        self.assertNotIn('OWNER_CONFIG',joined)
        self.assertEqual(args[-5:],['--entrypoint=python3',owner.IMAGE,'-I','-B','/candidate/solution.py'])
    def socket_stat(self,**changes):
        observed=self.cfg['runtime']['socket_identity'].copy();observed.update(changes)
        return SimpleNamespace(**{'st_'+k:v for k,v in {
            'dev':observed['dev'],'ino':observed['inode'],'mode':observed['mode'],
            'uid':observed['uid'],'gid':observed['gid'],'nlink':observed['nlink']}.items()})
    def test_selected_root_owned_socket_with_invoking_uid(self):
        owner=self.docker();fake=mock.Mock();fake.lstat.return_value=self.socket_stat()
        with mock.patch.object(owner,'plain',return_value=fake) as path_call, \
             mock.patch.object(owner.os,'getuid',return_value=1607), \
             mock.patch.object(owner.os,'getgid',return_value=2609):
            self.assertEqual(owner.daemon_guard(),self.cfg['runtime']['socket_identity'])
        path_call.assert_called_once_with(Path(self.cfg['runtime']['socket']))
    def test_stale_socket_identity_refuses_before_cli_dispatch(self):
        owner=self.docker();fake=mock.Mock();fake.lstat.return_value=self.socket_stat(inode=35)
        with mock.patch.object(owner,'plain',return_value=fake), \
             mock.patch.object(owner.os,'getuid',return_value=1607), \
             mock.patch.object(owner.os,'getgid',return_value=2609), \
             mock.patch.object(owner.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'exact_selected_local_daemon_socket'):
                owner.daemon_guard()
            spawn.assert_not_called()
    def selected(self):
        return {'schema':'tms_p16_authentic_assessment_selection_v1',
                'descriptor':dict(self.cfg['reference']['descriptor']),
                'source_lock_sha256':self.cfg['reference']['source_lock_sha256'],
                'transient_use_selected':True,'input_projection_selected':True,
                'image_content_selected':True,'private_delivery_selected':True}
    def test_reference_capture_before_candidate_closure_refuses_without_read(self):
        import runtime
        custody=mock.Mock();budget=mock.Mock()
        with self.assertRaisesRegex(ValueError,'candidate closure before reference access'):
            runtime.capture_selected_authentic({'custody':custody},
                selection=self.selected(),all_candidates_closed=False,budget=budget)
        self.assertEqual(custody.mock_calls,[]);self.assertEqual(budget.mock_calls,[])
    def test_stale_reference_context_or_descriptor_refuses_without_read(self):
        import runtime
        for key,value in [('source_lock_sha256','f'*64),
                          ('descriptor',{'bytes':100,'sha256':'f'*64})]:
            with self.subTest(key=key):
                selected=self.selected();selected[key]=value
                custody=mock.Mock();budget=mock.Mock()
                with self.assertRaisesRegex(ValueError,'same immutable owner configuration'):
                    runtime.capture_selected_authentic({'custody':custody},
                        selection=selected,all_candidates_closed=True,budget=budget)
                self.assertEqual(custody.mock_calls,[]);self.assertEqual(budget.mock_calls,[])
    def test_closed_reference_capture_uses_exact_owner_pins_and_token_check(self):
        import runtime
        value=object();events=mock.Mock();custody=mock.Mock();budget=mock.Mock()
        events.attach_mock(budget,'budget');events.attach_mock(custody,'custody')
        custody.capture.return_value=value
        observed=runtime.capture_selected_authentic({'custody':custody},
            selection=self.selected(),all_candidates_closed=True,budget=budget)
        self.assertIs(observed,value)
        self.assertEqual(events.mock_calls,[mock.call.budget.charge_read(2100000),
            mock.call.custody.capture(
                selected_source_lock_sha256=self.cfg['reference']['source_lock_sha256'],
                selected_descriptor_pin=self.cfg['reference']['descriptor']),
            mock.call.budget.check(),mock.call.custody.require_operator_reference(value)])

class CompleteOutputControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(SOURCE/'numeric'))
        import scorer
        cls.decode=staticmethod(scorer.decode_candidate)
    def test_all248_values_and_flags(self):
        values=[i/1000 for i in range(248)]
        decoded,flags=self.decode(struct.pack('<248d',*values)+bytes(248))
        self.assertEqual(tuple(decoded),tuple(values));self.assertEqual(sum(flags),0)
    def test_last_coordinate_not_dropped(self):
        values=[0.0]*247+[float('nan')]
        decoded,flags=self.decode(struct.pack('<248d',*values)+bytes(247)+b'\1')
        self.assertTrue(math.isnan(decoded[-1]));self.assertTrue(flags[-1])
    def test_short_complete_submission_refuses(self):
        with self.assertRaises(Exception):self.decode(bytes(2231))
    def test_infinity_and_category_mismatch_refuse(self):
        for values,flags in [([0.0]*247+[float('inf')],bytes(248)),
                             ([0.0]*248,bytes(247)+b'\1')]:
            with self.assertRaises(Exception):self.decode(struct.pack('<248d',*values)+flags)

if __name__=='__main__':
    # Hard timeout is failed partial work, never a temporary-file cleanup claim.
    signal.signal(signal.SIGALRM,lambda *_:os._exit(124))
    signal.setitimer(signal.ITIMER_REAL,90)
    unittest.main(verbosity=2)
