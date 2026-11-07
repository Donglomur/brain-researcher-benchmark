"""Invented RAM-only arithmetic/admission/controller controls; no scientific run."""
import ast,copy,hashlib,json,math,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent/'program'
def module(name,**bindings):
    m=types.ModuleType(name);m.__file__=str(HERE/name);m.__dict__.update(bindings)
    exec(compile((HERE/name).read_bytes(),str(HERE/name),'exec'),m.__dict__);return m
c=module('common.py');core=module('order_core.py');contract=module('output_contract.py',c=c)
def ident(i):return hashlib.sha256(str(i).encode()).hexdigest()
def public():
    out=[]
    for i in range(14):
        sid=ident(i);n=76 if i==13 else 72
        out.append(dict(session_id=sid,cell_ids=[ident(10000+i*100+k) for k in range(n)],file=sid+'.npz',bytes=10,sha256=ident('file'+str(i)),calibration_starts_seconds=[0,30,60,90],validation_starts_seconds=[150],queries=[dict(query_id=ident(100+i*2+j),start_seconds=start) for j,start in enumerate([210,270])]))
    return dict(schema='neural035-public-v1',sessions=out)
def predictions(p):
    return dict(schema='neural035-order-predictions-v1',predictions=[dict(query_id=q['query_id'],ordering_scores=[.5]*len(s['cell_ids'])) for s in p['sessions'] for q in s['queries']])
class Tests(unittest.TestCase):
    def test_scalar_baseline_not_rank_of_mean_peak(self):
        baseline=module('baseline_program.py')
        got=baseline.baseline([[1,2,3]]*4+[[299,0,1]],[[True]*3]*5)
        self.assertEqual(got,[.2,.4,.9]);self.assertNotEqual(got,baseline.ranks([60.6,1.6,2.6]))
        self.assertEqual(baseline.baseline([[0,1,2]]*5,[[False,False,True]]*5),[.5,.5,.5])
    def test_literal_baseline_math(self):
        original=ast.parse((HERE/'order_core.py').read_bytes());fixed=ast.parse((HERE/'baseline_program.py').read_bytes())
        def chosen(tree):return [ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'need','ranks','baseline'}]
        self.assertEqual(chosen(original),chosen(fixed))
    def test_full28_admission(self):
        p=public();d=predictions(p);contract.admit_pair(d,d,p,core)
        for mutant in ('missing','boolean','extra','infinite','duplicate'):
            v=copy.deepcopy(d)
            if mutant=='missing':v['predictions'].pop()
            elif mutant=='boolean':v['predictions'][0]['ordering_scores'][0]=False
            elif mutant=='extra':v['predictions'][0]['extra']=1
            elif mutant=='infinite':v['predictions'][0]['ordering_scores'][0]=float('inf')
            else:v['predictions'][1]['query_id']=v['predictions'][0]['query_id']
            with self.assertRaises(ValueError):contract.admit_pair(d,v,p,core)
    def test_public_geometry(self):
        p=public();contract.public_contract(p)
        for change in ('mapping','cell','querytime','session'):
            v=copy.deepcopy(p)
            if change=='mapping':v['sessions'][0]['mouse']='secret'
            elif change=='cell':v['sessions'][0]['cell_ids'].pop()
            elif change=='querytime':v['sessions'][0]['queries'][0]['start_seconds']=180
            else:v['sessions'].pop()
            with self.assertRaises(ValueError):contract.public_contract(v)
    def test_target_callback_after_both_outputs_only(self):
        g=module('deferred_grade.py');p=public();d=predictions(p);bad=copy.deepcopy(d);bad['predictions'].pop();calls=[]
        with self.assertRaises(ValueError):g.score(d,bad,p,lambda:calls.append('private'),core,contract)
        self.assertEqual(calls,[])
    def test_native_caps_and_holder_profile(self):
        n=module('native.py',c=c);h=module('holder.py')
        args=n.create_args({'name':'x','owner':'x'},'holder',{},134217728)
        self.assertIn('--init=false',args);self.assertIn('/ready:'+n.READY_TMPFS,args)
        self.assertEqual(n.PRED_CAP,h.CAP);self.assertEqual(h.CAP,2000000)
        b=b'{"a":1}';reply=c.encoded(dict(schema='slicetca_capture_v1',**c.pin(b),base64=__import__('base64').b64encode(b).decode()))
        self.assertEqual(n.output_reply(reply),b)
        with self.assertRaises(ValueError):c.validate_natural_exit(dict(Status='exited',Running=False,Dead=False,Pid=False,ExitCode=0,OOMKilled=False))
    def test_two_phase_actual_controller_mock_sequence_and_late_failure(self):
        for fail in (False,True):
            events=[];store={};p=public();d=predictions(p)
            class Budget:
                def __init__(self,*a):self.end=10000
                def tick(self):pass
                def capacity(self,*a):pass
                def read(self,*a):pass
                def write(self,*a):pass
                def native(self,i):events.append(('native',i))
                def record(self):return {}
            def save(path,raw,cap,*args):
                if len(raw)>cap:raise ValueError('cap')
                store[str(path)]=raw;events.append(('save',str(path)));return c.pin(raw)
            def capture(path,cap,expected=None,*args,**kwargs):
                raw=b'pass\n' if str(path)=='/candidate' else store[str(path)]
                if expected is not None:self.assertEqual(c.pin(raw),expected)
                return raw
            cc=types.SimpleNamespace(**{k:getattr(c,k) for k in ['need','parse','encoded','pin','only_pin','before']},path=Path,Budget=Budget,save=save,capture=capture,readable=lambda *a:None)
            ctl=module('controller.py',c=cc,core=core,output=contract,policy=types.SimpleNamespace(reviews=lambda *a:None))
            def prepare(*a):
                events.append(('view',));self.assertTrue(any(x[0]=='save' and x[1].endswith('COMMITMENT.json') for x in events));return Path('/owned/current'),{},p
            def native_case(s,here,current,expected,program,attempt,i,source,budget,end):
                events.append(('phase',i,s['candidate_seconds']))
                if fail and i==1:raise RuntimeError('late reference failure')
                out=c.encoded(d);store[str(attempt/'predictions.json')]=out
                row=dict(status='captured',role=('candidate','operator')[i],prediction=c.pin(out));store[str(attempt/'NATIVE.json')]=c.encoded(row);return row
            ctl.native=types.SimpleNamespace(case=native_case)
            ctl.directory=lambda *a:None;ctl.dependencies=lambda *a:Path('/package');ctl.prepare=prepare;ctl.retire=lambda *a:c.pin(b'retired')
            bodies={'BINDINGS.json':b'{}','baseline_program.py':b'baseline\n','holder.py':b'holder\n','candidate_entry.py':b'entry\n'}
            manifest={'files':{k:c.pin(v) for k,v in bodies.items()}}
            s=dict(repository='/repo',output='/owned',program={'path':'/candidate',**c.pin(b'pass\n')},other_future_bytes=0,candidate_seconds=60,method_review=c.pin(b'method'))
            with patch.object(ctl.os.path,'lexists',return_value=False),patch.object(Path,'is_dir',return_value=True),patch.object(Path,'stat',return_value=types.SimpleNamespace(st_dev=1)),patch.object(ctl.signal,'setitimer'),patch.object(ctl.time,'monotonic',return_value=1),patch.object(c.time,'monotonic',return_value=1):
                if fail:
                    with self.assertRaises(RuntimeError):ctl.run(s,c.pin(b'source'),bodies,manifest,0,10000)
                    self.assertNotIn('/owned/COMPLETE.json',store)
                else:
                    result=ctl.run(s,c.pin(b'source'),bodies,manifest,0,10000);self.assertEqual(result['outputs'],2)
                    self.assertEqual([e for e in events if e[0]=='phase'],[('phase',0,60),('phase',1,300)])
    def test_observer_setup_independent_cleanup(self):
        o=module('observe.py');calls=[];o.ORIGIN=0
        def arm(which,t):
            calls.append(('timer',t))
            if t>0:raise RuntimeError('arm')
        with patch.object(o.signal,'getitimer',return_value=(0.,0.)),patch.object(o.signal,'getsignal',return_value='old'),patch.object(o.signal,'signal',side_effect=lambda s,h:calls.append(('handler',s,h))),patch.object(o.signal,'setitimer',side_effect=arm),patch.object(o.time,'monotonic',return_value=1):
            with self.assertRaises(RuntimeError):o.enter_startup()
        self.assertEqual(sum(x[0]=='handler' and x[2]=='old' for x in calls),3);self.assertIn(('timer',0),calls)
    def test_baseline_first_max_source_semantics(self):
        tree=ast.parse((HERE/'baseline_program.py').read_bytes())
        call=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='argmax']
        self.assertEqual(len(call),1);self.assertEqual(ast.literal_eval(call[0].keywords[0].value),1)
        self.assertIn("np.__version__!='2.2.6'",(HERE/'baseline_program.py').read_text())
if __name__=='__main__':unittest.main()
