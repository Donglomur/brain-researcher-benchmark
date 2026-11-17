"""Metadata-only production adapter predicates. Invented fixtures stay in RAM."""
import copy,hashlib,importlib.util,json,types,unittest
from pathlib import Path
from unittest import mock
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('isttc_registration_metadata_controls',HERE/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
P={'bytes':1,'sha256':'a'*64}
SOURCE={'bytes':3629,'sha256':'b'*64}

class Poison:
    def __str__(self):raise AssertionError('unqualified operand stringified')
    def __fspath__(self):raise AssertionError('unqualified operand inspected')

class RAM:
    def __init__(self,files):self.files=files;self.reads=[]
    def read(self,path,cap,expected=None,**kw):
        key=str(path);self.reads.append(key);raw=self.files[key]
        assert len(raw)<=cap
        if expected is not None:assert a.pin(raw)==expected
        return raw

def pair():
    d=lambda p:{'path':'/invented/'+p,**P}
    return dict(schema='isttc_independent_program_pair_v1',task_id=a.TASK,programs={arm:{role:d(arm+'-'+role) for role in ('reproduction','improvement')} for arm in ('A','B')},authorship={arm:d(arm+'-authorship') for arm in ('A','B')},authoring_protocol=d('protocol'),root_attests_separate_contexts=True,root_attests_records_are_authentic=True,root_attests_no_cross_arm_feedback=True)

def fixture(mutator=None):
    root=Path('/invented/out');contexts=a.expected_contexts();p=pair();pair_pin=a.pin(a.encode(p));commit={'schema':'isttc_global_four_program_commitment_v1','task_id':a.TASK,'pair':pair_pin,'programs':{arm:{role:dict(P) for role in ('reproduction','improvement')} for arm in ('A','B')},'authorship':{arm:dict(P)for arm in ('A','B')},'data_or_native_phase_started':False,'attestation_is_independent_history_proof':False}
    cb=a.encode(commit);phases=[];artifacts={};support={}
    for ctx in contexts:
        name=ctx['phase_id'];phases.append({'context':ctx,'input_retired_after_exact_closure':True,'request':P,'receipt':{'path':f'phases/{name}/ACCEPTED_PHASE.json',**P}})
        artifacts[name]={n:{'path':f'phases/{name}/closed/artifacts/{n}',**P}for n in ('estimates.csv','methods.json')};support[name]={'invented_metadata_only':True}
    col={'schema':'isttc_complete_paired_collection_v1','task_id':a.TASK,'source_manifest':SOURCE,'contexts':contexts,'coverage':copy.deepcopy(a.SCOPE['coverage']),'original_origin':100.,'work_end':900100.,'phase_receipts':phases,'artifacts':artifacts,'support':support,'commitment':a.pin(cb),'baseline_policy':P,'baseline_evidence':P,'private_grade_join':P}
    for k in ('private_grade_called','runtime_qualified','scientific_qualification','full_paper_reproduction','automatic_retry_authorized'):col[k]=False
    obs={'schema':'isttc_original_whole_command_observed_v1','source':SOURCE,'original_phase_records_checked':5,'forced_stop_independent_host_and_daemon_state':'unknown','child':{'returncode':0,'natural_exit':True,'child_reaped':True,'owned_group_absence_observed':True,'forced_transitive_custody_complete':False,'terminal_bytes':{'stdout':0,'stderr':0},'original_origin':100.,'elapsed_seconds':10.}}
    for k in ('runtime_qualified','scientific_qualification','full_paper_reproduction','private_grade_called','automatic_retry_authorized'):obs[k]=False
    if mutator:mutator(obs,col,commit)
    cb=a.encode(commit);col['commitment']=a.pin(cb);raw=a.encode(col);obs['collection']=a.pin(raw)
    captures=RAM({str(root/'OBSERVED.json'):a.encode(obs),str(root/'run/COLLECTION.json'):raw,str(root/'run/PAIR_COMMITMENT.json'):cb})
    admitted={'output':root,'pair':p,'pair_pin':pair_pin};binding={'controller_manifest':{'path':'invented/SOURCE_MANIFEST.json',**SOURCE}}
    return captures,binding,admitted

class MetadataControls(unittest.TestCase):
    def test_runtime_refusal_before_pair_selection_and_output(self):
        binding={'controller_manifest':{'path':'invented/source.json',**SOURCE}}
        runtime=a.encode({'qualified':False});rp={'path':'invented/runtime.json',**a.pin(runtime)}
        review={'schema':'isttc_full100000_registration_review_v1','task_id':a.TASK,'approved':True,'adapter_source':P,'controller_source':binding['controller_manifest'],'selection':Poison(),'output':Poison(),'adapter_runtime':rp,'source_exposure':{},'typed_result':'isttc_full100000_ungraded_result_v1','private_grading_authorized':False}
        # Poison values cannot be JSON encoded: replace only stored selection/output with inert wrong types;
        # CLI candidate/output stay poison and production bind must refuse on runtime first.
        review['selection']=None;review['output']=None
        captures=RAM({'/invented/review.json':a.encode(review),str(a.ROOT/'invented/runtime.json'):runtime})
        args=types.SimpleNamespace(review='/invented/review.json',program=Poison(),output=Poison(),other_reserve_bytes=0)
        with self.assertRaisesRegex(ValueError,'runtime qualification prerequisite'):
            a.bind(args,captures,P,binding)
        self.assertEqual(captures.reads,['/invented/review.json',str(a.ROOT/'invented/runtime.json')])
    def test_pair_new_program_domain_and_empty_refusal(self):
        p=pair()
        for arm in ('A','B'):
            for role in ('reproduction','improvement'):p['programs'][arm][role]['bytes']=8388608
        a.pair_metadata(p)
        for size in (0,True,8388609):
            q=copy.deepcopy(p);q['programs']['A']['reproduction']['bytes']=size
            with self.assertRaises(ValueError):a.pair_metadata(q)
    def test_complete_metadata_outcome_is_not_scientific_payload_read(self):
        captures,binding,admitted=fixture()
        with mock.patch.object(a,'ORIGIN',100.):out=a.outcome(captures,binding,admitted)
        self.assertEqual(len(out['artifacts']),5);self.assertEqual(len(captures.reads),3)
        self.assertTrue(all(not name.endswith(('.csv','methods.json')) for name in captures.reads))
        self.assertIn('unchanged frozen observer.verify_collection',out['exact_original_record_validation'])
    def test_typed_and_complete_metadata_refusals(self):
        mutations=[lambda o,c,k:o.update(original_phase_records_checked=True),lambda o,c,k:o['child'].update(returncode=False),lambda o,c,k:o['child'].update(original_origin=True),lambda o,c,k:o['child'].update(elapsed_seconds=float('inf')),lambda o,c,k:c['phase_receipts'].pop(),lambda o,c,k:c['contexts'].pop(),lambda o,c,k:c['coverage'].update(units=True),lambda o,c,k:k['programs']['B']['improvement'].update(sha256='c'*64),lambda o,c,k:c.update(private_grade_called=True)]
        for change in mutations:
            # Preserve shared source scope while mutating an invented fixture.
            with mock.patch.object(a,'SCOPE',copy.deepcopy(a.SCOPE)):
                try:captures,binding,admitted=fixture(change)
                except ValueError:continue # strict JSON also rejects nonfinite invented evidence.
                with mock.patch.object(a,'ORIGIN',100.),self.assertRaises(ValueError):a.outcome(captures,binding,admitted)
    def test_actual_source_capture_and_AST_only(self):
        raw=(HERE/'SOURCE_MANIFEST.json').read_bytes();cap=a.Captures(a.time.monotonic()+30)
        binding=a.own_sources(cap,a.pin(raw));compiled,guard,path,bodies=a.target(cap,binding)
        self.assertEqual(len(bodies),24);self.assertEqual(bodies['baseline/source/src/isttc/scripts/__init__.py'],b'')
        self.assertLess(cap.reserved,a.READ_CAP);self.assertIsInstance(compiled,types.CodeType);self.assertIsInstance(guard,types.CodeType)
        # Compile/capture only: no observer execution and no scientific/array body.

if __name__=='__main__':unittest.main(verbosity=2)
