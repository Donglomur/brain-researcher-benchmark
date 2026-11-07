"""Independent adapter integration controls; source metadata and tiny RAM only."""
import ast
import builtins
import copy
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isttc_independent_adapter',BASE/'adapter.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
B=json.loads((BASE/'BINDING.json').read_bytes())
SOURCE=(BASE/'SOURCE_MANIFEST.json').read_bytes()
RAM_BYTES=0
D={'bytes':10,'sha256':'a'*64}


def enc(v):
    global RAM_BYTES
    b=json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode();RAM_BYTES+=len(b);return b


def fixture():
    contexts=A.expected_contexts();root=Path('/invented/observation')
    pair={'programs':{a:{r:{'path':'/invented/'+a+'/'+r,**D} for r in ('reproduction','improvement')} for a in ('A','B')},'authorship':{a:{'path':'/invented/'+a,**D} for a in ('A','B')}}
    commitment={'schema':'isttc_global_four_program_commitment_v1','task_id':A.TASK,'pair':D,'programs':{a:{r:D for r in ('reproduction','improvement')} for a in ('A','B')},'authorship':{a:D for a in ('A','B')},'data_or_native_phase_started':False,'attestation_is_independent_history_proof':False}
    source={k:B['controller_manifest'][k] for k in ('bytes','sha256')}
    false={k:False for k in ('private_grade_called','runtime_qualified','scientific_qualification','full_paper_reproduction','automatic_retry_authorized')}
    collection={'schema':'isttc_complete_paired_collection_v1','task_id':A.TASK,'source_manifest':source,'contexts':contexts,'coverage':A.SCOPE['coverage'],'original_origin':100.0,'work_end':900100.0,**false,
        'phase_receipts':[{'context':c,'request':D,'receipt':{'path':'phases/'+c['phase_id']+'/ACCEPTED_PHASE.json',**D},'input_retired_after_exact_closure':True} for c in contexts],
        'artifacts':{c['phase_id']:{name:{'path':'phases/'+c['phase_id']+'/closed/artifacts/'+name,**D} for name in ('estimates.csv','methods.json')} for c in contexts},
        'support':{c['phase_id']:{'invented':'not scientific payload validation'} for c in contexts},'baseline_policy':D,'baseline_evidence':D,'private_grade_join':D}
    observed={'schema':'isttc_original_whole_command_observed_v1','source':source,'original_phase_records_checked':5,**false,'forced_stop_independent_host_and_daemon_state':'unknown',
        'child':{'returncode':0,'natural_exit':True,'child_reaped':True,'owned_group_absence_observed':True,'forced_transitive_custody_complete':False,'terminal_bytes':{'stdout':0,'stderr':0},'original_origin':100.0,'elapsed_seconds':800.0}}
    return root,pair,commitment,collection,observed


class Signals:
    SIGALRM=signal.SIGALRM;SIGTERM=signal.SIGTERM;SIGINT=signal.SIGINT;ITIMER_REAL=signal.ITIMER_REAL
    def __init__(self,clock,fail=None,late=False):
        self.clock=clock;self.fail=fail;self.late=late;self.calls=[]
    def setitimer(self,kind,value):
        self.calls.append(('timer',value))
        if self.late:self.clock[0]=900340.0
        if self.fail=='cancel':raise OSError('invented cancellation failure')
    def signal(self,number,handler):
        self.calls.append(('handler',number,handler))
        if self.fail==number:raise OSError('invented restore failure')


class Checks(unittest.TestCase):
    def test_01_exact_source_target_authentication_no_operand_or_payload(self):
        captures=A.Captures(time.monotonic()+60)
        binding=A.own_sources(captures,A.pin(SOURCE))
        code,guard,path,bodies=A.target(captures,binding)
        self.assertEqual(len(bodies),24)
        self.assertEqual(bodies['baseline/source/src/isttc/scripts/__init__.py'],b'')
        self.assertEqual(A.pin(bodies['observe.py']),{'bytes':16393,'sha256':'73ef5bb40538c31eebe9747778ef5e057c6a389ecebdc913fc2eb0fa0fb3b00e'})
        self.assertEqual(code.co_filename,str(path));self.assertEqual(guard.co_filename,str(path))
        self.assertLess(captures.reserved,8*1024**2)
        print('ACTUAL_SOURCE_METADATA_CAPTURE_RESERVATION='+str(captures.reserved))

    def test_02_full_scope_matches_literal_controller_contexts(self):
        source=(A.ROOT/B['controller_directory']/'controller.py').read_bytes()
        tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='contexts')
        ns={'ARMS':('A','B'),'PROGRAMS':{'reproduction':8388608,'improvement':8388608}}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<contexts-only>','exec'),ns)
        self.assertEqual(A.expected_contexts(),ns['contexts']());self.assertEqual(len(A.expected_contexts()),5)
        self.assertEqual(A.SCOPE,B['scope']);self.assertEqual(A.SCOPE['global_programs'],4)
        self.assertEqual(A.SCOPE['coverage']['units'],100000);self.assertEqual(A.SCOPE['coverage']['trial_records'],4000000)
        self.assertEqual(2*A.SCOPE['reproduction_rows_per_arm']+2*A.SCOPE['improvement_rows_per_arm']+A.SCOPE['fixed_baseline_rows'],2400000)
        resource=B['resources']
        self.assertEqual(resource['combined_retained_cap_bytes'],3*1024**3+16*1024**2)
        self.assertEqual(resource['combined_managed_read_cap_bytes'],64*1024**3+1024**3+8*1024**2)
        self.assertEqual(resource['combined_managed_write_cap_bytes'],16*1024**3+16*1024**2)

    def test_03_full_typed_outcome_refuses_scope_clock_path_program_and_false_success(self):
        root,pair,cm,co,ob=fixture()
        def evaluate(commitment,collection,observed):
            cbody=enc(commitment);collection=copy.deepcopy(collection);collection['commitment']=A.pin(cbody)
            body=enc(collection);observed=copy.deepcopy(observed);observed['collection']=A.pin(body)
            store={str(root/'run/PAIR_COMMITMENT.json'):cbody,str(root/'run/COLLECTION.json'):body,str(root/'OBSERVED.json'):enc(observed)}
            calls=[]
            def read(p,cap,expected=None):
                calls.append(str(p));b=store[str(p)];assert len(b)<=cap
                if expected:assert A.pin(b)==expected
                return b
            with patch.object(A,'ORIGIN',100.0):result=A.outcome(SimpleNamespace(read=read),B,{'output':root,'pair':pair,'pair_pin':D})
            self.assertEqual(len(calls),3);self.assertFalse(any(p.endswith('.csv') for p in calls))
            return result
        self.assertEqual(evaluate(cm,co,ob)['scope']['total_phases'],5)
        mutations=[lambda x,y,z:z['child'].update(returncode=True),lambda x,y,z:z['child'].update(original_origin=200.0),lambda x,y,z:y['phase_receipts'].pop(),lambda x,y,z:y['coverage'].update(units=1),lambda x,y,z:y['artifacts']['04-reference-fixed-full']['estimates.csv'].update(path='phases/02-improvement-A-full/closed/artifacts/estimates.csv'),lambda x,y,z:x['programs']['B'].update(improvement={'bytes':10,'sha256':'b'*64}),lambda x,y,z:y.update(scientific_qualification=True)]
        for mutate in mutations:
            a,b,c=copy.deepcopy(cm),copy.deepcopy(co),copy.deepcopy(ob);mutate(a,b,c)
            with self.assertRaises(ValueError):evaluate(a,b,c)

    def test_04_missing_qualification_before_poisoned_candidate_output_and_selection(self):
        class Poison:
            def __str__(self):raise AssertionError('poisoned operand converted')
            def __fspath__(self):raise AssertionError('poisoned operand read')
        source=A.pin(SOURCE)
        review={'schema':'isttc_full100000_registration_review_v1','task_id':A.TASK,'approved':True,'adapter_source':source,'controller_source':B['controller_manifest'],'selection':{'must':'not be touched'},'output':'must-not-be-touched','adapter_runtime':{},'source_exposure':{},'typed_result':'isttc_full100000_ungraded_result_v1','private_grading_authorized':False}
        args=SimpleNamespace(review='/invented/review',program=Poison(),output=Poison(),other_reserve_bytes=Poison())
        with patch.object(A,'literal',side_effect=lambda x:Path(str(x))),patch.object(A,'metadata',return_value=({'qualified':False},None)):
            with self.assertRaisesRegex(ValueError,'runtime qualification prerequisite'):A.bind(args,SimpleNamespace(read=lambda *a:enc(review)),source,B)

    def main_run(self,fail=None,late=False):
        clock=[110.0];fake=Signals(clock,fail,late);initial={s:'old'+str(s) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
        captures=SimpleNamespace(reserved=0,end=0,read=lambda *a:b'',tick=lambda:None)
        fake_sys=SimpleNamespace(flags=SimpleNamespace(isolated=True,no_site=True),dont_write_bytecode=True,pycache_prefix='/invented/no-cache')
        printed=[]
        with patch.object(A,'signal',fake),patch.object(A,'sys',fake_sys),patch.object(A,'INITIAL_HANDLERS',initial),patch.object(A,'INITIAL_HANDLER','old'),patch.object(A,'ORIGIN',100.0),patch.object(A.time,'monotonic',side_effect=lambda:clock[0]),patch.object(A,'startup_owned'),patch.object(A,'literal',side_effect=Path),patch.object(A.os.path,'lexists',return_value=False),patch.object(A,'Captures',return_value=captures),patch.object(A,'own_sources',return_value=B),patch.object(A,'target',return_value=(None,None,None,{})),patch.object(A,'bind',return_value={'metadata_pins':[]}),patch.object(A,'invoke'),patch.object(A,'outcome',return_value={'invented':True}),patch.object(builtins,'print',side_effect=lambda *a,**k:printed.append(a)):
            code=A.main(['--program','/invented/pair','--output','/invented/out','--review','/invented/review','--source-sha256','a'*64,'--source-bytes','514','--other-reserve-bytes','0'])
        for call in printed:enc(call)
        return code,fake.calls,initial,printed

    def test_05_final_main_cleanup_cannot_turn_late_exit_into_success(self):
        self.assertEqual(self.main_run()[0],0)
        code,calls,initial,printed=self.main_run(late=True)
        self.assertEqual(code,2);self.assertEqual(len(printed),1)
        self.assertIn(('timer',0),calls)
        for s,h in initial.items():self.assertIn(('handler',s,h),calls)

    def test_06_final_main_cleanup_failures_attempt_all_handlers(self):
        for fail in ('cancel',signal.SIGALRM,signal.SIGTERM):
            code,calls,initial,printed=self.main_run(fail=fail)
            self.assertEqual(code,2);self.assertEqual(len(printed),1)
            self.assertIn(('timer',0),calls)
            for s,h in initial.items():self.assertIn(('handler',s,h),calls)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    print(json.dumps({'groups':result.testsRun,'success':result.wasSuccessful(),'invented_serialized_bytes':RAM_BYTES,'physical_fixtures':0,'actual_timers_processes_fits_scoring':0}))
    raise SystemExit(not result.wasSuccessful())
