"""Invented, bounded source controls. No actual arrays, Docker, fitting or scoring."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).absolute().parent))
import common
import controller
import npy_transport
import outputs
import protocol
import staging

ROOT=Path(__file__).absolute().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
engine=load('_visual_alpha_test_engine',ROOT/'engine/native.py')
registration=load('_visual_alpha_test_registration',ROOT/'registration/adapter.py')
observer=load('_visual_alpha_test_observer',ROOT/'run.py')

class Controls(unittest.TestCase):
    def test_complete_plan_and_no_state_channel(self):
        p=protocol.phases();self.assertEqual(len(p),85)
        self.assertEqual(sum(x['mode']=='reference' for x in p),27)
        self.assertEqual(sum(x['mode']=='corrected' for x in p),54)
        self.assertEqual([x['fit_role'] for x in p[4:7]],list(protocol.ROLES))
        self.assertEqual(sum(protocol.COUNTS.values()),433)
        self.assertEqual(len({x['phase_id'] for x in p}),85)
    def test_global_commit_precedes_all_inputs_and85phases(self):
        calls=[]
        class Fake:
            def commit_all_six_before_data(self):calls.append('commit')
            def admit_complete_inputs(self):calls.append('admit')
            def phase(self,ctx):calls.append(ctx['phase_id']);return ctx
            def complete(self,rows):self.rows=rows;calls.append('complete');return rows
        ops=Fake();self.assertEqual(controller.run_sequence(ops),protocol.phases())
        self.assertEqual(calls[:2],['commit','admit']);self.assertEqual(len(calls),88)
    def test_half_selection_preserves_every_bit_both_orders(self):
        shape=(2,4,75)
        values=[struct.pack('<Q',0x7ff8000000000123) if i==0 else struct.pack('<Q',0x8000000000000000) if i==1 else struct.pack('<d',i+0.25) for i in range(600)]
        for f in (False,True):
            ordered=[values[(a*4+s)*75+t] for t in range(75) for s in range(4) for a in range(2)] if f else values
            raw=npy_transport.header(shape,f)+b''.join(ordered)
            for si in range(4):
                for role in protocol.ROLES:
                    ix=protocol.indices(role);out=npy_transport.select_response(raw,shape,si,ix)
                    order,payload=npy_transport.inspect(out,(2,len(ix)))
                    self.assertFalse(order);self.assertEqual(bytes(payload),b''.join(values[(a*4+si)*75+t] for a in range(2) for t in ix))
    def test_held_half_change_cannot_change_training_bytes(self):
        shape=(1,4,75);raw=npy_transport.header(shape)+b''.join(struct.pack('<d',float(i)) for i in range(300))
        changed=bytearray(raw);offset=len(npy_transport.header(shape))
        for s in range(4):
            for t in range(38,75):changed[offset+(s*75+t)*8:offset+(s*75+t+1)*8]=struct.pack('<d',-12345.)
        for s in range(4):self.assertEqual(npy_transport.select_response(raw,shape,s,protocol.indices('train_first')),npy_transport.select_response(bytes(changed),shape,s,protocol.indices('train_first')))
    def test_transport_rejects_other_splits_pickle_and_trailing(self):
        raw=npy_transport.header((1,4,75))+b'\0'*2400
        for bad in ([],list(range(37)),list(range(37,75))):
            with self.assertRaises(ValueError):npy_transport.select_response(raw,(1,4,75),0,bad)
        with self.assertRaises(ValueError):npy_transport.inspect(raw+b'x',(1,4,75))
        with self.assertRaises(ValueError):npy_transport.inspect(raw.replace(b'<f8',b'|O8'),(1,4,75))
    def test_original_parameter_boundaries_and_sign(self):
        r={'allow_negative_gain':False,'model':'GS'}
        self.assertEqual(outputs.parameters([-49,150,0,0,1],r),[-49,150,0,0,1])
        for v in ([50,50,-1,1,0],[50,50,1,-1,0],[50,50,1,True,0],[50,50,1,1,float('inf')]):
            with self.assertRaises(ValueError):outputs.parameters(v,r)
        with self.assertRaises(ValueError):outputs.parameters([50,50,1,1,.1],{**r,'model':'OG'})
    def test_metadata_scope_exact9_and_allconditions(self):
        persons=[{'participant':p,'electrode_ids':[p+'-e'+str(i) for i in range(protocol.COUNTS[p])],'response_signal_order':list(protocol.SIGNALS),'apertures':{s:'apertures/x.npy' for s in protocol.SIGNALS}} for p in protocol.PEOPLE]
        rows=staging.roster(persons);self.assertEqual(len(rows),3464)
        for p in protocol.PEOPLE:self.assertEqual(sum(r['participant']==p for r in rows),protocol.COUNTS[p]*8)
        bad=copy.deepcopy(persons);bad[-1]['electrode_ids'].pop()
        with self.assertRaises(ValueError):staging.roster(bad)
    def test_exact_engine_request_and_no_duration_default(self):
        for ctx in protocol.phases():
            mode=ctx['mode'];r={'schema':'visualalpha_owned_phase_request_v1','phase_id':ctx['phase_id'],'mode':mode,'participant':ctx['participant'],'fit_role':ctx['fit_role'],'image':'sha256:'+'1'*64,'source':{'bytes':1,'sha256':'2'*64},'expected_files':engine.expected_outputs(mode,ctx['participant']),'entry':engine.ENTRIES[mode],'entry_support':engine.SUPPORT[mode],**engine.TIMES[mode],'producer_seconds':999}
            self.assertEqual(engine.validate_request(mode,r),r)
            bad=dict(r);bad.pop('producer_seconds')
            with self.assertRaises(ValueError):engine.validate_request(mode,bad)
            bad=dict(r,producer_seconds=True)
            with self.assertRaises(ValueError):engine.validate_request(mode,bad)
        self.assertEqual(engine.expected_outputs('reference','p01')['baseline_audit.json'],4194304)
    def test_strict_natural_exit_rejects_bool_zero(self):
        r={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}
        engine.validate_natural_exit(r)
        for k,v in [('Pid',False),('ExitCode',False),('Running',0),('OOMKilled',True)]:
            with self.assertRaises(ValueError):engine.validate_natural_exit({**r,k:v})
    def test_registration_refuses_before_any_candidate_open(self):
        value=json.loads((ROOT/'registration/REGISTRATION.json').read_bytes())
        with patch('builtins.open',side_effect=AssertionError('no candidate IO')):
            r=registration.admit_registration(value)
        self.assertEqual(r['status'],'refused_unqualified_complete_program');self.assertFalse(r['candidate_operand_opened'])
        for k in ('runtime_qualified','scientific_qualified','submission_ready'):
            with self.assertRaises(ValueError):registration.admit_registration({**value,k:True})
    def test_grade_all_candidates_before_any_private_callback(self):
        import grading
        with patch.object(outputs,'spectral',side_effect=ValueError('last malformed original matrix')):
            with self.assertRaises(ValueError):grading.grade_complete(dict.fromkeys(('spectral_A','spectral_B','reproduction_A','reproduction_B','corrected_A','corrected_B'),b'{}'),{'spectral_rows':[],'spectral_sha':'x'},capture_sealed_baseline=lambda: self.fail('private baseline called'),expected_baseline_pin={},load_person=lambda _:self.fail('private person called'),load_spectral_targets=lambda:self.fail('private target called'),modules=None)
    def test_candidate_views_do_not_contain_sealed_operator_mount(self):
        for mode in ('spectral','spatial','corrected'):
            self.assertEqual(set(engine.SUPPORT[mode]),{'/trusted/entry_common.py'})
            self.assertEqual(engine.ENTRIES[mode],'candidate_entry.py')
        self.assertEqual(engine.ENTRIES['reference'],'baseline_entry.py')
    def test_source_bindings_only_original_inputs_not_saved_fits(self):
        b=json.loads((ROOT/'BINDINGS.json').read_bytes())
        self.assertEqual(len(b['spectral_inputs']),37)
        self.assertEqual(len(b['spectral_B_code']),40);self.assertEqual(len(b['spatial_B_code']),78)
        self.assertEqual(len(b['spatial_inputs']),11)
        self.assertTrue(all('responses.npy' in k or k.startswith('apertures/') for k in b['spatial_inputs']))
        self.assertEqual({x['target'].split('/')[1] for x in b['spectral_inputs'][:-1]},set(protocol.PEOPLE))

if __name__=='__main__':unittest.main()

class CustodyControls(unittest.TestCase):
    def test_reused_lifecycle_core_is_ast_unchanged(self):
        import ast
        donor=ROOT.parents[1]/'remaining-builds-wave15/next-paper-complete-program/engine/native.py'
        # Explicit donor scope; only source bodies are read, never runtime operands.
        body=donor.read_text().replace('popgeom','visualalpha').replace('population geometry','visual alpha').replace('population-geometry','visual-alpha').replace('PAPER-paper-method-add-006','PAPER-ROOT-ADD-014')
        previous={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(body).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        current={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((ROOT/'engine/native.py').read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        names=('Docker','validate_natural_exit','validate_cli_records','retire','create_args','admission','capture_artifacts','artifact_inventory','chunk_reply','wait_ready')
        for name in names:self.assertEqual(current[name],previous[name],name)
    def test_85phase_observer_join_and_tamper_refusals(self):
        source={'bytes':1,'sha256':'a'*64};end=1e9;files={};read=[]
        def put(path,value):
            raw=common.canonical(value);files[str(path)]=raw;return common.pin(raw)
        root=Path('/invented-owned-collection');records=[];artifacts={};panel=common.pin(b'{}');program=common.pin(b'x')
        settings={'image':'sha256:'+'b'*64,'producer_seconds':dict.fromkeys(('spectral','spatial','corrected','reference'),100),'authorship':{},'programs':{a:{p:dict(path='/invented',**program) for p in protocol.PURPOSES} for a in ('A','B')}}
        cli={'phase':'image','returncode':0,'error_type':None,'observed_retained_bytes':0,'seconds':0.,'client_reaped':True,'cleanup_complete':True,'cleanup_before_original_cutoff':True,'owned_group_absence_observed':True,'leader_exited_with_group_alive':False,'group_probe_or_cleanup_error':None}
        for ctx in protocol.phases():
            mode=ctx['mode'];pr=root/'phases'/ctx['phase_id'];expected=engine.expected_outputs(mode,ctx['participant'])
            request={'schema':'visualalpha_owned_phase_request_v1','phase_id':ctx['phase_id'],'mode':mode,'participant':ctx['participant'],'fit_role':ctx['fit_role'],'image':settings['image'],'source':source,'expected_files':expected,'entry':engine.ENTRIES[mode],'entry_support':engine.SUPPORT[mode],**engine.TIMES[mode],'producer_seconds':100}
            pins={n:common.pin(b'{}') for n in expected}
            for n in expected:files[str(pr/'closed/artifacts'/n)]=b'{}'
            files[str(pr/'ADMITTED.json')]=b'{}';files[str(pr/'JOURNAL.jsonl')]=b'{}'
            receipt={'phase_id':ctx['phase_id'],'phase':mode,'participant':ctx['participant'],'fit_role':ctx['fit_role'],'status':'captured','source':source,'source_before':{'manifest':source},'source_after':{'manifest':source},'natural_exit':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'command_metadata':[cli],'producer_closed_before_capture':True,'all_native_resources_closed':True,'cli_reaped':True,'closures':[{'closed':True}]*3,'original_deadline':end,'started':0.,'elapsed_seconds':1.,'phase_end':2.,'artifacts':{'files':pins,'capture_complete':True}}
            records.append({'context':ctx,'request':put(pr/'REQUEST.json',request),'receipt':put(pr/'ACCEPTED_PHASE.json',receipt),'journal':common.pin(b'{}'),'input_retired_only_after_exact_closure':True})
            artifacts[ctx['phase_id']]={'raw':pins,'admitted':common.pin(b'{}')}
        panels=dict.fromkeys(('reproduction_A','reproduction_B','corrected_A','corrected_B','portable_operator'),panel)
        for name in ('corrected_A','corrected_B','portable_operator'):files[str(root/'panels'/(name+'.json'))]=b'{}'
        commit={'schema':'visual_alpha_six_programs_global_commitment_v1','programs':{a:{p:program for p in protocol.PURPOSES} for a in ('A','B')},'authorship':{},'all6_frozen_before_any_numeric_input':True}
        for a in ('A','B'):
            for p in protocol.PURPOSES:files[str(root/'programs'/a/(p+'.py'))]=b'x'
        join={'panels':panels,'source_manifest':source,'portable_operator_phases':[x['phase_id'] for x in protocol.phases() if x['mode']=='reference'],'automatic_scoring':False}
        collection={'schema':'visual_alpha_complete_paired_collection_v1','source_manifest':source,'coverage':protocol.COVERAGE,'phases':records,'artifacts':artifacts,'panels':panels,'sealed_grade_join':put(root/'SEALED_GRADE_JOIN.json',join),'commitment':put(root/'GLOBAL_COMMITMENT.json',commit),'private_scoring_called':False,'runtime_qualified':False,'scientific_qualified':False}
        class MemoryIO:
            def capture(self,path,d,cap=1048576,retain=True):
                raw=files[str(path)];read.append(str(path));common.need(common.pin(raw)=={k:d[k] for k in ('bytes','sha256')} and len(raw)<=cap,'exact invented source body');return raw if retain else d
        raw=common.canonical(collection)
        with patch.object(Path,'exists',return_value=False):
            observer.admit_collection(root,raw,engine,protocol,MemoryIO(),source,end,settings)
            self.assertEqual(sum(x.endswith('/REQUEST.json') for x in read),85)
            self.assertEqual(sum('/programs/' in x for x in read),6)
            # Corrupt the independently pinned last program without changing its commitment.
            target=str(root/'programs/B/spatial_improvement.py');old=files[target];files[target]=b'y'
            with self.assertRaises(ValueError):observer.admit_collection(root,raw,engine,protocol,MemoryIO(),source,end,settings)
            files[target]=old
            bad=copy.deepcopy(collection);bad['panels'].pop('portable_operator')
            with self.assertRaises(ValueError):observer.admit_collection(root,common.canonical(bad),engine,protocol,MemoryIO(),source,end,settings)
            request_path=str(root/'phases/operator_p11_train_second/REQUEST.json');old=files[request_path];files[request_path]=old+b' '
            with self.assertRaises(ValueError):observer.admit_collection(root,raw,engine,protocol,MemoryIO(),source,end,settings)
            files[request_path]=old
            # An otherwise valid other-person/role request with its updated pin
            # still cannot join the original context's execution receipt.
            for field,value in [('participant','p10'),('fit_role','train_first')]:
                request=json.loads(old);request[field]=value
                altered=copy.deepcopy(collection)
                altered['phases'][-1]['request']=put(Path(request_path),request)
                with self.assertRaises(ValueError):observer.admit_collection(root,common.canonical(altered),engine,protocol,MemoryIO(),source,end,settings)
            files[request_path]=old


class CandidateParserControl(unittest.TestCase):
    def test_exact_original_lexical_parser(self):
        import ast
        import candidate_json
        original=ast.parse((ROOT/'spatial/vendor/interface.py').read_bytes())
        copied=ast.parse((ROOT/'candidate_json.py').read_bytes())
        function=lambda tree:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_parse')
        self.assertEqual(ast.dump(function(original),include_attributes=False),ast.dump(function(copied),include_attributes=False))
        for token in (b'999999999999999999',b'-99999999999999999',b'1e300'):
            self.assertEqual(candidate_json.parse(token,1024),json.loads(token))
        for token in (b'9999999999999999999',b'-999999999999999999',b'{"x":1,"x":2}',b'['*13+b'0'+b']'*13):
            with self.assertRaises(ValueError):candidate_json.parse(token,1024)
        self.assertIs(outputs.parse,candidate_json.parse)
