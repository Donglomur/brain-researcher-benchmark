"""Tiny invented metadata controls. Never imports the actual scientific basis."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
import types
import unittest

HERE=Path(__file__).absolute().parents[1]
CANONICAL=0
SOURCE_READ=0
EVIDENCE={}

def mod(name):
    global SOURCE_READ
    path=HERE/(name+'.py');raw=path.read_bytes();SOURCE_READ+=len(raw)
    m=types.ModuleType('_it_central_control_'+name);m.__file__=str(path)
    if name!='common_io':m.u=u
    sys.modules[m.__name__]=m;exec(compile(raw,str(path),'exec'),m.__dict__);return m

u=mod('common_io');t=mod('transcript');a=mod('artifacts');d=mod('dispatch');x=mod('external')

def charge(value):
    global CANONICAL
    raw=u.canonical(value);CANONICAL+=len(raw)
    assert CANONICAL<=512*1024
    return value

def sample():
    impl='1'*64;pg='2'*64;model='3'*64;fit='4'*64
    phases=[]
    def add(i,k,deps,**extra):phases.append({'id':i,'kind':k,'dependencies':deps,**extra})
    add('view/A/calibrated/0/observed','fresh_training_context',[])
    view=phases[-1]['id'];fid='fit/A/calibrated/0/observed/case';sid='seal/A/calibrated/0/observed';qid='queries/A/calibrated/0/observed'
    add(fid,'fit',[view],configuration='case');add(sid,'seal_complete_fit',[fid],configurations=['case'])
    add(qid,'query_features_after_seal',[sid]);add('predict/A/calibrated/0/observed/case','predict',[qid,sid],configuration='case')
    add('validate-all','validate_all_candidate_and_reference_outputs',[phases[-1]['id']])
    add('outer-close','independent_full_process_and_resource_closure',['validate-all']);add('protected-grade','load_targets_last_and_grade',['outer-close'])
    seals={k:'5'*64 for k in ('native_bundle_digest','prediction_bundle_digest','expected_bundle_digest','native_schema_digest')}
    fit_art={'model_digest':model,'fit_receipt_digest':fit,'input_digest':'6'*64,'implementation_digest':impl}
    whole={'fit_models':{'case':model},'fit_receipts':{'case':fit}}
    artifacts=[{'context':'invented-context','view_digest':'7'*64},fit_art,whole,{'seal_digest':u.scientific_digest(whole)},
      {'model_digest':model,'fit_receipt_digest':fit,'query_digest':'8'*64,'implementation_digest':impl},seals,
      {**seals,'all_outputs_validated':True,'resources_passed':True,'natural_complete':True,'all_descendants_closed':True},
      {'status':'complete','invented_label':'étendue'}]
    plan={'phases':phases,'programme_digest':pg,'implementation_digest':impl};outputs={};rows=[]
    document={'origin_ns':10,'deadline_ns':100,'profile':{k:1000 for k in t.RESOURCE}}
    for n,(phase,artifact)in enumerate(zip(phases,artifacts)):
        parents={k:outputs[k]for k in phase['dependencies']}
        binding=u.scientific_digest({'phase':phase,'parents':parents,'origin_ns':10,'programme_digest':pg,'implementation_digest':impl})
        obs={'phase_id':phase['id'],'binding_digest':binding,'origin_ns':10,'implementation_digest':impl,'natural_complete':True,
             'exit_code':0,'all_descendants_closed':True,'host_alive':True,'external_host_natural_exit_required':True,
             'observation_scope':'live_host_phase_children','host_observation_digest':'9'*64,'finished_ns':20+n,
             **{k:1 for k in t.RESOURCE}}
        if phase['kind']in('fit','predict'):
            obs.update(view_isolation_verified=True,source_seal_unchanged=True,protected_grading_targets_absent=True)
        if phase['kind']=='fit':obs.update(fit_receipt_digest=fit,model_digest_after_fit=model)
        if phase['kind']=='predict':obs['model_digest_after_inference']=model
        rows.append({'phase':phase,'parents_digest':u.scientific_digest(parents),'binding':binding,'producer_error':None,'observer_error':None,
                     'result':{'phase_id':phase['id'],'binding_digest':binding,'artifact':artifact,
                               'receipt':{'scientific_dispatcher':'paper020_v2','implementation_digest':impl}},'observation':obs})
        outputs[phase['id']]=artifact
    result={'phase_count':8,'result':artifacts[-1],'resources':{k:(1 if k=='live_bytes'else 8)for k in t.RESOURCE},'finished_ns':30}
    return charge((rows,plan,document,result))

class Controls(unittest.TestCase):
    def test_utf8_source_digest(self):
        v=charge({'label':'étendue'})
        self.assertNotEqual(u.scientific_digest(v),u.sha(u.canonical(v)))
        self.assertEqual(u.scientific_digest(v),hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())

    def test_actual_early_legacy_refusal(self):
        """Invoke real entry main in this isolated test process, stopping at gate."""
        entry=mod('entry');raw=(HERE/'SOURCE_MANIFEST.json').read_bytes();pin=u.pin(raw)
        oldargv=sys.argv[:];before=set(sys.modules);failure=None;costs=None
        sys.argv=[str(HERE/'entry.py'),'--program','/nonexistent/it-operand.json','--output','/nonexistent/it-output',
                  '--review','/nonexistent/it-review.json','--source-bytes',str(pin['bytes']),'--source-sha256',pin['sha256'],'--other-reserve-bytes','0']
        try:entry.main()
        except ValueError as error:
            failure=str(error);tb=error.__traceback__
            while tb:
                r=tb.tb_frame.f_locals.get('reader')
                if r is not None and hasattr(r,'report'):costs=r.report()
                tb=tb.tb_next
        finally:sys.argv=oldargv
        self.assertEqual(failure,'current canonical registry does not select this full IT central source')
        self.assertFalse(any(n=='numpy'or n=='scipy'or n.startswith('_it_reviewed_')for n in set(sys.modules)-before))
        self.assertIsNotNone(costs);EVIDENCE['actual_legacy_gate']={'failure':failure,'source_metadata_costs':costs,'scientific_modules_added':False}

    def test_original_clock_boundaries(self):
        for now in (9,100):
            reader=u.Reader(10,100,clock=lambda:now)
            with self.assertRaises(ValueError):reader.tick()
        self.assertEqual(u.Reader(10,100,clock=lambda:99).tick(),99)

    def test_tiny_replay_and_refusals(self):
        rows,plan,document,result=sample();self.assertEqual(t._replay(rows,plan,document,result)['protected-grade'],result['result'])
        cases=[('wrong source',lambda r,p,d,v:r[1]['result']['receipt'].update(implementation_digest='a'*64)),
               ('missing phase',lambda r,p,d,v:r.pop()),
               ('wrong fit model',lambda r,p,d,v:r[1]['observation'].update(model_digest_after_fit='b'*64)),
               ('inference mutation',lambda r,p,d,v:r[4]['observation'].update(model_digest_after_inference='c'*64)),
               ('late phase',lambda r,p,d,v:r[-1]['observation'].update(finished_ns=100)),
               ('final equality',lambda r,p,d,v:v.update(finished_ns=100)),
               ('nonzero phase',lambda r,p,d,v:r[1]['observation'].update(exit_code=1)),
               ('bool exit',lambda r,p,d,v:r[1]['observation'].update(exit_code=False)),
               ('cost refund',lambda r,p,d,v:v['resources'].update(read_bytes=7)),
               ('producer failure',lambda r,p,d,v:r[2].update(producer_error='InventedFailure')),
               ('wrong final grade',lambda r,p,d,v:v.update(result={'status':'partial'}))]
        for name,mutation in cases:
            values=copy.deepcopy((rows,plan,document,result));mutation(*values);charge(values)
            with self.subTest(name=name),self.assertRaises(ValueError):t._replay(*values)
        EVIDENCE['tiny_replay']={'phases':8,'refusals':len(cases),'authentic_graph_generated':False}

    def test_journal_chain_and_strict_budget(self):
        rows,plan,document,result=sample()
        with tempfile.TemporaryDirectory(prefix='it-central-invented-')as tmp:
            r=u.Reader(1,100,read_limit=100000,write_limit=100000,clock=lambda:2)
            journal=t.Journal(Path(tmp)/'tiny.jsonl',r,100000)
            for row in rows:journal.append(row)
            journal.close();raw=r.read(Path(tmp)/'tiny.jsonl',100000);charge(raw.decode())
            observed,head=t.read_records(raw);self.assertEqual(len(observed),8);self.assertEqual(head,journal.head)
            broken=raw.replace(b'fit/A',b'bad/A',1);charge(broken.decode())
            with self.assertRaises(ValueError):t.read_records(broken)
        EVIDENCE['disk_fixture_retained_bytes']=0

    def test_actual_call_composition(self):
        """Inert production seam; no actual programme, science, process or model."""
        phase={'id':'invented-meta','kind':'invented-metadata','dependencies':[]};charge(phase)
        calls=[];records=[]
        class Bound:
            runtime=object();monitor=object()
            def __call__(self,*args):calls.append('execute');return {'invented':'metadata'}
            def observe(self,*args):calls.append('observe');return {'invented_observation':True}
        entry=types.SimpleNamespace()
        def construct(*args,**kwargs):calls.append('construct');return Bound()
        def run(*args,**kwargs):
            calls.append('entry');b=entry.construct(*args,**kwargs);r=b(phase,{},1,10,'a'*64);b.observe(phase,r,1,10,'a'*64)
            return {'invented_provisional':True}
        entry.construct=construct;entry.run_full_study=run;d.transcript=t
        operands={k:None for k in ('runtime_envelope','public_key','contract','admission','mapping')}
        result,bound=d._call_once(entry,operands,types.SimpleNamespace(append=records.append),None)
        self.assertEqual(calls,['entry','construct','execute','observe']);self.assertIs(entry.construct,construct)
        self.assertEqual(len(records),1);self.assertEqual(result,{'invented_provisional':True})
        charge(records);EVIDENCE['inert_composition']={'entry_calls':1,'constructor_calls':1,'actual_scientific_entry_executed':False}

    def test_complete_summary_refusals(self):
        env={'source_pin':{'bytes':1,'sha256':'a'*64},'source_rows':{'invented':{'bytes':1,'sha256':'b'*64}}}
        job={'run_id':'invented','mode':'compiled','origin_ns':1,'deadline_ns':100,'metadata_limits':{'read_bytes':1000,'write_bytes':1000}}
        op={'job':job,'program_pin':{'bytes':1,'sha256':'c'*64}}
        s={k:None for k in x.FIELDS};s.update(schema='paper020_central_provisional_v1',status='provisional_pending_external_natural_exit',
          task_id='PAPER-ROOT-ADD-020',run_id='invented',central_source=env['source_pin'],source_closure_digest=u.sha(u.canonical(env['source_rows'])),
          program_pin=op['program_pin'],mode='compiled',origin_ns=1,deadline_ns=100,phase_count=23786,parent_entry_calls=1,
          parent_controller_executions=1,external_numerical_grader_calls=0,new_canonical_ids=0,scientific_qualification_claim=False,
          physical_qualification_claim=False,files={k:None for k in ('phases.jsonl','artifacts.json','inner.json')},publication_started_ns=50,
          logical_metadata_costs={'physical_accounting':False,'logical_read_reserved':10,'logical_read_observed':8,'logical_write_bytes':5,'hash_input_bytes':8})
        charge(s);x.summary_join(s,env,op)
        for key,value in [('status','complete'),('phase_count',1),('parent_entry_calls',True),('external_numerical_grader_calls',1),
                          ('origin_ns',2),('publication_started_ns',100),('scientific_qualification_claim',True)]:
            bad=copy.deepcopy(s);bad[key]=value;charge(bad)
            with self.subTest(key=key),self.assertRaises(ValueError):x.summary_join(bad,env,op)

    def test_source_ast_no_second_scientific_runner(self):
        global SOURCE_READ
        for name in ('entry.py','observer_entry.py','bootstrap.py','common_io.py','authority.py','dispatch.py','transcript.py','artifacts.py','external.py','credential.py','registration.py'):
            raw=(HERE/name).read_bytes();SOURCE_READ+=len(raw);tree=ast.parse(raw)
            self.assertFalse(any(isinstance(n,ast.Attribute)and n.attr in ('killpg','kill','terminate')for n in ast.walk(tree)))
        raw=(HERE/'dispatch.py').read_bytes();SOURCE_READ+=len(raw);tree=ast.parse(raw)
        self.assertEqual(sum(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='run_full_study'for n in ast.walk(tree)),1)
        self.assertFalse(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr in ('grade_study','execute_plan')for n in ast.walk(tree)))

if __name__=='__main__':
    tracemalloc.start()
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    report={'schema':'paper020_central_source_controls_v1','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'canonical_fixture_bytes':CANONICAL,'scoped_tracemalloc_peak_bytes':peak,'source_read_bytes':SOURCE_READ,
            'evidence':EVIDENCE,'authentic_graphs':0,'scientific_imports':0,'scientific_runs':0,'provider_calls':0,'physical_qualification':False}
    print(json.dumps(report,sort_keys=True));raise SystemExit(0 if result.wasSuccessful()else 1)
