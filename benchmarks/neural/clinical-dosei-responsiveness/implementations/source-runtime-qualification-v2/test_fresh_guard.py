"""Generated successor authority and supervisor controls; no real ledger or Docker."""
import contextlib
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location('fresh_guard_test_'+name,HERE/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod
    spec.loader.exec_module(mod);return mod
guard=load('qualification_guard_v4')
entry=load('qualification_entry_v4')

def protocol():
    modules={k:{'path':str(guard.ADAPTERS/n),'sha256':h} for k,(n,h) in guard.FROZEN.items()}
    modules.update({k:{'path':str(guard.LEGACY/n),'sha256':h} for k,(n,h) in guard.LEGACY_MODULES.items()})
    modules.update({k:{'path':str(HERE/n),'sha256':'a'*64} for k,n in guard.NEW_MODULES.items()})
    names=['runtime','readonly_scratch','fresh_scratch','nonzero','flood','deadline']
    p={'schema':'dosei_fresh_six_control_protocol_v1','owner':guard.OWNER,
       'native_run_id':guard.RUN,'approval_id':guard.APPROVAL,'limits':dict(guard.LIMITS),
       'output_directory':str(guard.OUTPUT),'parent_reservation_id':guard.PARENT_RESERVATION,
       'docker_executable':guard.DOCKER,'docker_socket':guard.SOCKET,'python_executable':guard.PYTHON,
       'binaries':copy.deepcopy(guard.BINARY_PINS),'capture_file_caps':dict(guard.CAPTURE_FILES),
       'source_cutoff':'1a947dd3163f8dd556146a9721d50feefde21b54',
       'context_count':3,'container_count':6,'context_ids':[c*64 for c in '123'],
       'criterion_selection_sha256':guard.SELECTION_SHA256,'historical_qualified_controls':0,
       'historical_failed_attempts':3,'case_order':names,
       'generated_programs':{k:{'bytes':100,'sha256':'b'*64} for k in names},
       'runtime_attach_cap_bytes':524288,'modules':modules,
       'profile':{'path':str(guard.ADAPTERS/'runtime_profile.json'),'sha256':guard.PROFILE_PIN}}
    for k in ('authentic_input_reads','model_calls','api_calls','scoring','image_pull','image_build','install'):p[k]=False
    for k,n in (('entry','qualification_entry_v4.py'),('guard','qualification_guard_v4.py'),('cli_shim','cpu_cli_exec.py')):
        p[k]={'path':str((guard.LEGACY if k=='cli_shim' else HERE)/n),'sha256':'c'*64}
    return p

def ledger(p):
    binding={'path':str(guard.PROTOCOL),'sha256':'d'*64}
    return {'approved_native_protocols':[{'id':guard.APPROVAL,'owner':guard.OWNER,
              'approved_by':'/root','protocol':binding}],
      'reservations':[{'id':guard.PARENT_RESERVATION,'owner':guard.OWNER,'status':'active','kind':'artifact',
          'destination':str(guard.OUTPUT),'reserved_bytes':guard.LIMITS['artifact_envelope_bytes']}],
      'native_runs':[{'id':guard.RUN,'owner':guard.OWNER,'status':'running','protocol':binding,
          'approval_id':guard.APPROVAL,'command':guard.expected_command(p,'d'*64),'cwd':str(HERE),
          'child_pid':123,'coordinator_pid':122,'declared_max_working_ram_bytes':1073741824,'requested_threads':1}]}

class FreshGuardControls(unittest.TestCase):
    def test_exact_new_artifact_grant_and_registered_child_required(self):
        p=protocol();good=ledger(p)
        check=lambda v:guard.validate_authority(v,p,'d'*64,pid=123,parent_pid=122)
        check(good)
        mutations=[('reservations','id','dosei-attempt03-prospective-evidence-20261117'),
          ('reservations','owner','root'),('reservations','status','closed'),
          ('reservations','destination',str(guard.Q)),('reservations','reserved_bytes',4390911),
          ('native_runs','child_pid',True),('native_runs','coordinator_pid',999),
          ('native_runs','requested_threads',True),('native_runs','status','succeeded'),
          ('approved_native_protocols','approved_by','another-agent')]
        for group,key,value in mutations:
            with self.subTest(group=group,key=key):
                bad=copy.deepcopy(good);bad[group][0][key]=value
                with self.assertRaises(ValueError):check(bad)
    def test_exact_frozen_policy_scope_and_six_program_roster(self):
        good=protocol();guard.validate_protocol(good)
        for key,value in [('criterion_selection_sha256','f'*64),('historical_qualified_controls',1),
          ('historical_failed_attempts',False),('runtime_attach_cap_bytes',2097152),
          ('case_order',good['case_order'][:5]),('image_pull',True),('authentic_input_reads',True)]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):guard.validate_protocol(bad)
        for name in ('probe','network_policy','store','owned'):
            bad=copy.deepcopy(good);bad['modules'][name]['sha256']='f'*64
            with self.subTest(name=name),self.assertRaises(ValueError):guard.validate_protocol(bad)
        bad=copy.deepcopy(good);del bad['generated_programs']['deadline']
        with self.assertRaises(ValueError):guard.validate_protocol(bad)
        self.assertEqual(sum(guard.CAPTURE_FILES.values()),49153)
        self.assertEqual(4194304+65536+49153+65536,4374529)
    def test_supervisor_cancellation_cannot_be_reported_success(self):
        handlers={};ctx=types.SimpleNamespace(cancelled=False,modules={},operational_receipt=lambda:{'generated':True})
        def produce(_):
            try:handlers[entry.signal.SIGALRM](entry.signal.SIGALRM,None)
            except TimeoutError:pass
            return {'status':'succeeded','failure':None,'report':{'bytes':42,'sha256':'a'*64}}
        ctx.modules['driver']=types.SimpleNamespace(run_qualification=produce)
        argv=['entry','--protocol','/generated','--protocol-sha256','a'*64,
              '--approval-id','generated','--native-run-id','generated']
        with patch.object(sys,'argv',argv),patch.object(entry,'bootstrap',return_value=types.SimpleNamespace(Context=lambda _:ctx)), \
             patch.object(entry.signal,'signal',side_effect=lambda sig,fn:handlers.__setitem__(sig,fn)), \
             patch.object(entry.signal,'setitimer'),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(entry.main(),1)
        self.assertTrue(ctx.cancelled);self.assertIn('"complete": false',out.getvalue())
        self.assertEqual(entry.GUARD_SHA256,hashlib.sha256((HERE/'qualification_guard_v4.py').read_bytes()).hexdigest())

if __name__=='__main__':unittest.main(verbosity=2)
