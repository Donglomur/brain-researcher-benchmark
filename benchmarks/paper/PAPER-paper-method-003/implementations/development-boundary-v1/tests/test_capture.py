"""Tiny inert physical receipt/promotion controls; no arrays, Docker or models."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reve_boundary_capture',HERE/'boundary.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
a=b.a
CREATED=0

def write(path,raw):
    global CREATED
    CREATED+=len(raw)
    if CREATED>131072:raise AssertionError('bounded tiny generated fixture allocation')
    path.write_bytes(raw);os.chmod(path,0o600)
    return a.pin(raw)

def document(path,value):return write(path,a.canonical(value)+b'\n')

class CaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='reve-boundary-inert-');cls.root=Path(cls.temp.name).resolve()
        cls.p,cls.contract,cls.bounds=a.transport_package()
        cls.provider=object.__new__(cls.p.Provider)
        cls.provider.control_root=cls.root/'control';cls.provider.control_root.mkdir(mode=0o700)
        cls.provider.quarantine_root=cls.root/'capture';cls.provider.quarantine_root.mkdir(mode=0o700)
        cls.provider.read_limit=1048576;cls.provider.read_used=0
        cls.provider.write_limit=1048576;cls.provider.write_used=0
        cls.phase_id='generated_development';cls.deadline=time.monotonic()+120;cls.origin=cls.deadline-120
        resources={'setup_seconds':2,'producer_seconds':3,'capture_seconds':2,'cleanup_seconds':2,
          'memory_bytes':134217728,'cpu_nanos':1000000000,'pids':16,'scratch_bytes':4096,
          'max_files':4,'max_directories':1,'max_file_bytes':1048576,'max_output_bytes':2097152,
          'manifest_bytes':65536,'max_cli_calls':64,'max_cli_bytes':1048576,'inventory_bytes':65536,
          'source_read_bytes':1048576,'host_write_bytes':1048576}
        mounts={'/candidate/develop.py':b.file_mount(cls.root/'never-run.py','program',a.pin(b'pass\n'))}
        cls.bundle=b.phase_request(phase_id=cls.phase_id,role='A',image='sha256:'+'d'*64,exposure=a.pin(b'inert'),
             mounts=mounts,kind='development',origin=cls.origin,deadline=cls.deadline,resources=resources)
        phase=cls.bundle['request'];cls.phase_dir=cls.provider.quarantine_root/cls.phase_id;cls.phase_dir.mkdir()
        cls.pins={'selected.py':write(cls.phase_dir/'selected.py',b'pass\n'),
                  'model.bin':write(cls.phase_dir/'model.bin',b'inert-no-model')}
        cls.result={'schema':'reve-development-selection-v2','episode_id':'a'*64,
                    'development_identity':'b'*64,'selected_files':deepcopy(cls.pins)}
        cls.pins['RESULT.json']=document(cls.phase_dir/'RESULT.json',cls.result)
        request_sha=a.pin(cls.p.encoded(phase))['sha256']
        envelope={'schema':'osl_transport_output_manifest_v1','phase_id':cls.phase_id,
                  'request_sha256':request_sha,'files':deepcopy(cls.pins)}
        cls.envelope_pin=document(cls.phase_dir/'OUTPUTS.json',envelope)
        cli={'phase':'image','returncode':0,'error_type':None,'observed_retained_bytes':0,'seconds':0,
             'client_reaped':True,'cleanup_complete':True,'cleanup_before_original_cutoff':True,
             'owned_group_absence_observed':True,'leader_exited_with_group_alive':False,'group_probe_or_cleanup_error':None}
        cls.receipt={'schema':'osl_owned_phase_receipt_v1','phase_id':cls.phase_id,'request_sha256':request_sha,
          **{k:phase[k] for k in ('action','role','image','source','exposure')},'status':'captured',
          'all_native_resources_closed':True,'cli_reaped':True,'producer_closed_before_capture':True,
          'error':None,'oom':False,'deadline_exceeded':False,
          'retired_resources':[{'kind':kind,'name':name,'closed':True,'absence_observed':True,'creation_outcome_unknown':False}
              for kind,name in [('container','producer'),('container','holder'),('volume','output')]],
          'natural_exit':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},
          'command_metadata':[cli],'enforced_resource_limits':resources,
          'input_before':cls.bounds.mount_identity(mounts),'input_after':cls.bounds.mount_identity(mounts),
          'timing':{'original_deadline':cls.deadline,'started':cls.origin,'finished':cls.origin+.001},
          'qualification_inherited':False,'scientific_qualification':False,
          'output_inventory':{'complete':True,'files':{**cls.pins,'OUTPUTS.json':cls.envelope_pin}},
          'quarantine_root':str(cls.phase_dir)}
        control=cls.provider.control_root/cls.phase_id;control.mkdir()
        cls.receipt_pin=document(control/'RECEIPT.json',cls.receipt)
        cls.returned={'receipt':cls.receipt,'receipt_pin':cls.receipt_pin}
        cls.capture={'files':deepcopy(cls.pins),'root':str(cls.phase_dir)}
    @classmethod
    def tearDownClass(cls):
        # Only these generated trees are owned; readonly files are deliberately
        # retained until this explicit cleanup so permissions can be inspected.
        for root,dirs,files in os.walk(cls.root):
            os.chmod(root,0o700)
        cls.temp.cleanup()
    def observe(self,returned=None):
        return b.observe_capture(self.provider,self.bundle,returned or self.returned,self.deadline,
                                 output_names=b.ARTIFACT_FILES|{'RESULT.json'})
    def test_real_independent_provider_observer(self):
        before=self.provider.read_used;result=self.observe()
        self.assertEqual(result['result'],self.result)
        self.assertEqual(self.provider.read_used-before,self.receipt_pin['bytes']+self.pins['RESULT.json']['bytes']+self.envelope_pin['bytes'])
    def test_returned_receipt_cannot_override_saved_proof(self):
        changed=deepcopy(self.returned);changed['receipt']['role']='B'
        with self.assertRaises(ValueError):self.observe(changed)
    def test_receipt_digest_mismatch_is_refused(self):
        changed=deepcopy(self.returned);changed['receipt_pin']['sha256']='0'*64
        with self.assertRaises(ValueError):self.observe(changed)
    def bad_receipt(self,mutate):
        receipt=deepcopy(self.receipt);mutate(receipt)
        with patch.object(self.p.Provider,'observe',return_value={'receipt':receipt}):
            with self.assertRaises(ValueError):self.observe({'receipt':receipt,'receipt_pin':self.receipt_pin})
    def test_incomplete_cleanup_is_refused(self):self.bad_receipt(lambda x:x.update(all_native_resources_closed=False))
    def test_unobserved_absence_is_refused(self):self.bad_receipt(lambda x:x['retired_resources'][0].update(absence_observed=False))
    def test_duplicate_native_resource_is_refused(self):self.bad_receipt(lambda x:x['retired_resources'].__setitem__(1,x['retired_resources'][0]))
    def test_reversed_chronology_is_refused(self):self.bad_receipt(lambda x:x['timing'].update(started=self.deadline))
    def test_nonfinite_chronology_is_refused(self):self.bad_receipt(lambda x:x['timing'].update(finished=float('nan')))
    def test_changed_readonly_inputs_are_refused(self):self.bad_receipt(lambda x:x.update(input_after={}))
    def test_extra_captured_file_is_refused(self):self.bad_receipt(lambda x:x['output_inventory']['files'].update({'private.json':a.pin(b'x')}))
    def test_partial_read_failure_is_charged(self):
        before=self.provider.read_used
        with patch.object(self.provider,'read_limit',before+self.receipt_pin['bytes']+self.envelope_pin['bytes']+5):
            with self.assertRaises(ValueError):self.observe()
        self.assertGreater(self.provider.read_used,before+self.receipt_pin['bytes'])
    def promote(self,name='frozen',capture=None):
        return b.promote_selected(self.provider,capture or self.capture,self.root/name,
                                  {'episode_id':'a'*64,'profile':b.PROFILES[0]},self.deadline)
    def account(self,artifact):
        global CREATED
        CREATED+=artifact['conservative_copy_write_charge_bytes']
        self.assertLessEqual(CREATED,131072)
    def test_promotion_exact_bytes_modes_and_budget(self):
        before=(self.provider.read_used,self.provider.write_used);old=os.umask(0o077)
        try:artifact=self.promote()
        finally:os.umask(old)
        self.account(artifact);root=Path(artifact['root'])
        self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o555)
        for name in ('selected.py','model.bin','FROZEN.json'):
            self.assertEqual(stat.S_IMODE((root/name).stat().st_mode),0o444)
        for name in b.ARTIFACT_FILES:self.assertEqual((root/name).read_bytes(),(self.phase_dir/name).read_bytes())
        self.assertEqual(a.pin((root/'FROZEN.json').read_bytes()),artifact['manifest_pin'])
        self.assertEqual(self.provider.read_used-before[0],artifact['conservative_copy_read_charge_bytes'])
        self.assertEqual(self.provider.write_used-before[1],artifact['conservative_copy_write_charge_bytes'])
    def test_promotion_budget_failure_before_any_write(self):
        before=self.provider.write_used
        with patch.object(self.provider,'write_limit',before+1):
            with self.assertRaises(ValueError):self.promote('not-created')
        self.assertFalse((self.root/'not-created.staging').exists());self.assertEqual(before,self.provider.write_used)
    def test_promotion_read_budget_failure_before_any_write(self):
        before=self.provider.write_used
        with patch.object(self.provider,'read_limit',self.provider.read_used):
            with self.assertRaises(ValueError):self.promote('no-read')
        self.assertFalse((self.root/'no-read.staging').exists());self.assertEqual(before,self.provider.write_used)
    def test_promotion_failure_keeps_conservative_debits_and_removes_only_owned_tree(self):
        global CREATED
        capture=deepcopy(self.capture);capture['files']['selected.py']['sha256']='0'*64
        before=(self.provider.read_used,self.provider.write_used)
        with self.assertRaises(ValueError)as cm:self.promote('failed',capture)
        # A deterministic name iteration is not required: charge all prospective
        # extents conservatively; source files remain present and unchanged.
        charge=cm.exception.conservative_copy_write_charge_bytes;CREATED+=charge
        self.assertEqual(self.provider.write_used-before[1],charge);self.assertGreater(self.provider.read_used,before[0])
        self.assertFalse((self.root/'failed').exists());self.assertFalse((self.root/'failed.staging').exists())
        self.assertEqual((self.phase_dir/'selected.py').read_bytes(),b'pass\n')
        self.assertLessEqual(CREATED,131072)
    def test_existing_output_preserved(self):
        existing=self.root/'existing';existing.mkdir()
        before=self.provider.write_used
        with self.assertRaises(ValueError):self.promote('existing')
        self.assertTrue(existing.is_dir());self.assertEqual(self.provider.write_used,before)
    def test_promotion_expired_clock_before_write(self):
        before=self.provider.write_used
        with self.assertRaises(ValueError):b.promote_selected(self.provider,self.capture,self.root/'expired',{},0)
        self.assertEqual(self.provider.write_used,before);self.assertFalse((self.root/'expired.staging').exists())

if __name__=='__main__':
    program=unittest.main(exit=False,verbosity=2)
    print(json.dumps({'generated_write_charge_created_and_reclaimed_bytes':CREATED,'authentic_arrays':0,'Docker_calls':0,'models':0}))
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
