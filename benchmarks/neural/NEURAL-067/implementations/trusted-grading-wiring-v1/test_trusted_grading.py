"""Generated-only new wiring checks; full journals in memory, targets replaced."""
import ast,copy,hashlib,importlib.util,json,struct,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import host,observe,runtime_io
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
W=module(ROOT/'worker/worker.py','generated_worker')
S=module(ROOT/'worker/grading/session-evaluator-v1/scorer.py','generated_scorer')
G=ROOT/'worker/grading'
NAMES=('original-target-callback-v1/target_callback.py','original-target-callback-v1/guarded_npz.py',
       'session-evaluator-v1/scorer.py','journal-session-bridge-v1/bridge.py')
SOURCES={'grading/'+n:(G/n).read_bytes() for n in NAMES}
INPUTS={r:{'bytes':n+1,'sha256':hashlib.sha256(('generated-'+r).encode()).hexdigest()} for r,_,n in S.QUERY}
DESIGN={'query':[{'run':r,'n_rows':n,'input':INPUTS[r]} for r,_,n in S.QUERY],
        'train':[{'run':'generated-train','n_rows':135991}],'arms':list(S.ARMS)}
GENERATED=0
def stable_ast(node):
    # Python3.12 adds empty generic-parameter fields absent in the3.9 metadata writer.
    for child in ast.walk(node):
        if hasattr(child,'type_params') and child.type_params==[]:delattr(child,'type_params')
    return ast.dump(node,include_attributes=False)
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def journal(run,arm,n):
    global GENERATED
    h=enc({'schema':'neural067_action_journal_v1','run':run,'arm':arm,'rows':n,'input':INPUTS[run],
           'encoding':'<Q7d32s32s32s','record_bytes':160,'header_bytes':4096})+b'\n'
    raw=bytearray(h+bytes(4096-len(h)));prior=bytes(32)
    for i in range(n):
        prefix=struct.pack('<Q7d32s32s',i,*([42.0]*7),bytes(32),prior)
        prior=hashlib.sha256(prefix).digest();raw.extend(prefix+prior)
    GENERATED+=len(raw);return bytes(raw),prior.hex()
def descriptors():
    rows=[]
    for r,_,n in S.QUERY:
        for a in S.ARMS:
            raw,c=journal(r,a,n);rows.append({'run':r,'arm':a,'file':r+'__'+a+'.bin',**pin(raw),'final_chain':c})
    return rows
def binding():
    return {'files':{},'grading_sources':{n:pin(SOURCES['grading/'+n]) for n in NAMES},
            'grading_evidence':{n:pin(('generated-'+n).encode()) for n in ('asset_manifest','attempt_receipt','operator_result')},
            'trusted_grading':{'contract_sha256':S.CONTRACT_SHA256}}
class JournalDirectory:
    def __init__(self,rows):self.rows=rows
    def iterdir(self):return [Path(x['file']) for x in self.rows]
class MemoryOutput:
    def __init__(self):self.values={}
    def tick(self):pass
    def put(self,n,b):
        assert n=='score.json' and len(b)<1000000
        self.values[n]=b;return pin(b)
def composition(rows,corrupt=False):
    counts={'journals':0,'private_initializations':0,'targets':0};lookup={r['file']:r for r in rows};real=W.load_source
    def load(raw,name,path):
        cb=real(raw,name,path)
        class SyntheticTargets:
            def __init__(self,root,evidence,scorer,source_inputs=None):
                assert counts['journals']==56 and source_inputs==INPUTS
                assert root==Path('/generated-package/private/data')
                assert evidence=={'design':Path('/generated-package/public/design.json'),
                    'private_bindings':Path('/generated-package/private/PRIVATE_BINDINGS.json'),
                    **{n:Path('/grading-evidence')/(n+'.json') for n in binding()['grading_evidence']}}
                counts['private_initializations']+=1;self.i=0
            def __call__(self,run):
                r,session,n=S.QUERY[self.i];assert run==r;self.i+=1;counts['targets']+=1
                return {'run':r,'session':session,'row_ids':list(range(n)),
                        'velocity':[[0.0 if session=='S6' else float(i%2)]*7 for i in range(n)],
                        'eval_mask':[i%5!=0 for i in range(n)]}
        cb._Targets=SyntheticTargets;return cb
    def capture(path,cap,expected=None):
        row=lookup[path.name];n=next(n for r,_,n in S.QUERY if r==row['run'])
        raw,c=journal(row['run'],row['arm'],n);counts['journals']+=1
        assert expected==row and cap==1000000 and c==row['final_chain']
        if corrupt and counts['journals']==56:raw=raw[:-1]+bytes([raw[-1]^1])
        return raw
    out=MemoryOutput()
    with patch.object(W,'ordinary',lambda p:JournalDirectory(rows)),patch.object(W,'capture',capture),patch.object(W,'load_source',load):
        try:r=W.grade(Path('/generated-package'),DESIGN,binding(),Path('/generated-journals'),rows,out,SOURCES)
        except ValueError:return None,out,counts
    return r,out,counts
class Budget:
    def __init__(self):self.reads=self.debits=0
    def mkdir(self,p,mode=0o700):p.mkdir(mode=mode)
    def save(self,p,v,**kw):b=enc(v);p.write_bytes(b);return pin(b)
    def read(self,n):self.reads+=n
    def debit(self,n,**kw):self.debits+=n
def observer_fixture(rows):
    records={};wb=(ROOT/'worker/worker.py').read_bytes();b=binding()
    lock={'design':DESIGN,'design_pin':pin(b'generated design'),'grading_evidence':b['grading_evidence'],'trusted_grading':b['trusted_grading']}
    v={'queries':[{'journal':x} for x in rows],'program_commit':pin(b'program'),'states_sealed':pin(b'states')}
    def put(n,x):raw=enc(x);records[n]=raw;return pin(raw)
    v['grading_input']=put('GRADING_INPUT.json',{'schema':'neural067_closed_journal_grading_input_v1','journals':rows,
        'all_query_producers_absent':True,'program_commit':v['program_commit'],'states_sealed':v['states_sealed'],'contract_sha256':S.CONTRACT_SHA256})
    inv={'schema':'neural067_worker_invocation_v1','mode':'grade','journals':rows,'grading_evidence':b['grading_evidence'],
         'worker_source':pin(wb),'design':lock['design_pin'],'files':{'generated':pin(b'operand')}}
    ip=put('grade/INVOCATION.json',inv)
    score={'schema':'neural067_session_grade_v1','contract_sha256':S.CONTRACT_SHA256,'query_runs':14,'query_sessions':7,
           'full_rows_per_arm':34490,'arms':{a:{'negative':-9.0,'undefined':None} for a in S.ARMS},'causal_program_execution_verified':False}
    sp=put('grade/output/data/score.json',score)
    result={'status':'scored_current_session_contract','scientific_score_computed':True,'scientific_qualification':False,
            'causal_program_execution_verified':False,'contract_sha256':S.CONTRACT_SHA256,'journal_blocks':56}
    wp=put('grade/output/WORKER.json',{'mode':'grade','invocation':ip,'worker_source':pin(wb),'package_files':inv['files'],
        'requires_external_natural_exit':True,'runtime_qualified':False,'scientific_qualification':False,'result':result,'files':{'data/score.json':sp}})
    hp=pin(b'generated closed trusted host');ap=put('grade/ADMISSION.json',{'host':hp,'worker':wp,'invocation':ip,
        'files':{'data/score.json':sp,'WORKER.json':wp}});v['grade']={'host':hp,'worker':wp,'admission':ap,'score':sp};seen=[]
    def capture(p,cap,expected=None):
        n=str(p.relative_to('/generated-attempt'));seen.append(n);raw=records[n]
        assert len(raw)<=cap and pin(raw)==expected
        return raw
    io=types.SimpleNamespace(need=runtime_io.need,parse=runtime_io.parse,identity=pin,capture=capture)
    return io,v,lock,{'worker/worker.py':wb},records,seen
class Wiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=descriptors()
    def test_full_current_composition_negative_undefined_and_order(self):
        r,out,c=composition(self.rows)
        self.assertEqual(c,{'journals':56,'private_initializations':1,'targets':14});self.assertEqual(r['journal_blocks'],56)
        score=json.loads(out.values['score.json']);self.assertEqual(score['full_rows_per_arm'],34490)
        self.assertEqual(score['schema'],'neural067_session_grade_v1')
        for a in S.ARMS:
            self.assertIsNone(score['arms'][a]['by_session']['S6']['variance_weighted_r2'])
            self.assertLess(score['arms'][a]['by_session']['S7']['variance_weighted_r2'],0)
    def test_late_corruption_never_opens_private_targets(self):
        r,out,c=composition(self.rows,True)
        self.assertIsNone(r);self.assertEqual(c,{'journals':56,'private_initializations':0,'targets':0});self.assertEqual(out.values,{})
    def test_missing_reordered_refuse_before_callback(self):
        for rows in (self.rows[:-1],[self.rows[1],self.rows[0],*self.rows[2:]]):
            with patch.object(W,'load_source',side_effect=AssertionError('callback reached')):
                with self.assertRaises(ValueError):W.grade(Path('/generated-package'),DESIGN,binding(),Path('/generated-journals'),rows,MemoryOutput(),SOURCES)
    def test_public_source_capture_and_private_role_boundaries(self):
        b=binding();b['files']={n:pin(b'generated source') for n in W.SOURCE_NAMES};read=[]
        with patch.object(W,'capture',lambda p,cap,expected:read.append(str(p)) or b'x'):
            bodies=W.source_bundle(Path('/generated-package'),b,'grade')
        self.assertEqual(len(bodies),6);self.assertTrue(all(p.endswith('.py') for p in read))
        self.assertFalse(any('PREPARATION' in p or 'PRIVATE_BINDINGS' in p or p.endswith('.npz') for p in read))
        for mode in ('train','query'):
            names=W.required_files(DESIGN,mode);self.assertNotIn('private/data/PREPARATION.json',names);self.assertNotIn('private/PRIVATE_BINDINGS.json',names)
        self.assertIn('private/data/PREPARATION.json',W.required_files(DESIGN,'grade'));self.assertNotIn('private/scorer.py',W.required_files(DESIGN,'grade'))
    def test_host_mounts_invocation_and_read_reserve(self):
        b=binding();lock={'design':DESIGN,'design_pin':pin(b'generated design'),'grading_evidence':b['grading_evidence']}
        lock['files']={n:pin(('generated-'+n).encode()) for n in W.required_files(DESIGN,'grade')}
        wb=(ROOT/'worker/worker.py').read_bytes();seen=[]
        def run(command,mounts,phase,budget,config):
            seen.append((command,mounts));raw=(phase/'INVOCATION.json').read_bytes();inv=json.loads(raw);out=phase/'output';(out/'data').mkdir()
            score=enc({'generated':True});(out/'data/score.json').write_bytes(score)
            worker={'schema':'neural067_worker_completion_v1','mode':'grade','invocation':pin(raw),'worker_source':pin(wb),'package_files':inv['files'],
                    'files':{'data/score.json':pin(score)},'requires_external_natural_exit':True,'runtime_qualified':False,'scientific_qualification':False}
            (out/'WORKER.json').write_bytes(enc(worker));return pin(b'generated host')
        with tempfile.TemporaryDirectory(dir=ROOT.parent.parent,prefix='generated-mounts-') as tmp:
            attempt=Path(tmp);budget=Budget()
            with patch.object(host.trusted,'run',run):host.invoke(ROOT,{'worker/worker.py':wb},lock,Path('/generated-package'),attempt,'grade','grade',budget,{}, {'journals':self.rows},[(attempt/'journals','/journals',True)])
            inv=json.loads((attempt/'grade/INVOCATION.json').read_bytes());self.assertEqual(inv['journals'],self.rows)
            self.assertEqual(inv['grading_evidence'],b['grading_evidence']);command,mounts=seen[0]
            self.assertEqual(command[-2:],['--journals','/journals']);self.assertNotIn('--submission',command)
            mapped={dst:(src,ro) for src,dst,ro in mounts}
            self.assertEqual(mapped['/package/private/data/PREPARATION.json'],(ROOT/'operator-evidence/PREPARATION.json',True))
            self.assertEqual(mapped['/grading-evidence/operator_result.json'],(ROOT/'operator-evidence/operator_result.json',True))
            self.assertTrue(all(ro for _,dst,ro in mounts if dst!='/out'));self.assertNotIn('/submission',mapped)
            self.assertGreaterEqual(budget.reads,sum(x['bytes'] for x in self.rows))
    def test_observer_current_contract_and_support_refusals(self):
        for change in ('none','missing','reordered','partial','contract'):
            io,v,lock,bodies,records,seen=observer_fixture(self.rows)
            if change=='missing':v['queries'].pop()
            if change=='reordered':v['queries'][0],v['queries'][1]=v['queries'][1],v['queries'][0]
            if change=='partial':v['queries'][0]=copy.deepcopy(v['queries'][0]);v['queries'][0]['journal']['bytes']-=160
            if change=='contract':lock['trusted_grading']={'contract_sha256':'0'*64}
            with patch.object(observe,'role',return_value={}) as role:
                args=(io,Path('/generated-attempt'),v,lock,bodies,{'mount_source_policy':'identity'})
                if change=='none':
                    observe.admit_grade(*args);role.assert_called_once();self.assertNotIn('assemble/CLOSED.json',seen)
                else:
                    with self.assertRaises(ValueError):observe.admit_grade(*args)
                    role.assert_not_called()
    def test_preserved_source_and_direct_grade_dispatch(self):
        expected=json.loads((ROOT/'SOURCE_CONSERVATION.json').read_bytes())
        for row in expected['unchanged_functions']:
            tree=ast.parse((ROOT/row['file']).read_bytes());n=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==row['name'])
            self.assertEqual(hashlib.sha256(stable_ast(n).encode()).hexdigest(),row['ast_sha256'],row)
        for row in expected['unchanged_files']:self.assertEqual(pin((ROOT/row['file']).read_bytes()),row['pin'])
        tree=ast.parse((ROOT/'host.py').read_bytes());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        modes=[n.args[5].value for n in ast.walk(f) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='invoke' and len(n.args)>6]
        self.assertEqual(sorted(modes),['grade','query','train'])
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Wiring))
    print(json.dumps({'tests_run':r.testsRun,'successful':r.wasSuccessful(),'generated_journal_bytes_in_memory':GENERATED,
                      'authentic_payload_reads':0,'docker_calls':0,'private_loader':'synthetic substitution after complete admission'}))
    raise SystemExit(0 if r.wasSuccessful() else 1)
