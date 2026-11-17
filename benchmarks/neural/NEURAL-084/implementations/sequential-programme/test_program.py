"""Invented stdlib controls only; no native/model/actual EEG execution."""
import ast,hashlib,importlib.util,json,os,shutil,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).absolute().parent;P=HERE/'program'
CANONICAL=0;PHYSICAL=0

def module(name,**kw):
    m=types.ModuleType(name);m.__file__=str(P/name);m.__dict__.update(kw);exec(compile((P/name).read_bytes(),str(P/name),'exec'),m.__dict__);return m
c=module('common.py');original_encode=c.encoded

def encoded(v):
    global CANONICAL
    raw=original_encode(v);CANONICAL+=len(raw)
    if CANONICAL>8*1024**2:raise ValueError('author cumulative canonical fixture cap')
    return raw
c.encoded=encoded
policy=module('policy.py',c=c)

def pin(raw):return c.pin(raw)

def baseplan():return dict(contexts=54,query_count=21600,training_per_context=21200,files=216,public_bytes=18663400000,max_fold_bytes=345620000)
class Tests(unittest.TestCase):
    def test_scope_and_resource_floor(self):
        p=baseplan();v=policy.limits(p,900,120)
        self.assertGreater(v['reads'],11*p['public_bytes']+216*16000000)
        self.assertEqual(v['whole_seconds'],54*(900+360+520+180)+1800)
        for key,value in [('contexts',53),('query_count',21200),('training_per_context',20800),('files',212)]:
            q=dict(p);q[key]=value
            with self.assertRaises(ValueError):policy.limits(q,900,120)
        with self.assertRaises(ValueError):policy.limits(p,True,120)
    def test_exact_baseline_sources_and_entry_modes(self):
        tree=ast.parse((P/'reference_program.py').read_text());values=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCES' for t in n.targets));sources=ast.literal_eval(values)
        original=HERE.parents[2]/'neural084/public'
        # Resolve delivery directory without source/data discovery.
        original=next(p for p in HERE.parents if p.name=='delivery-20261105')/'neural084/public'
        self.assertEqual(set(sources),{'protocol.py','io_utils.py','reference_cca.py'})
        for name,text in sources.items():self.assertEqual(text,(original/name).read_text())
        n=module('native.py',c=c);h=module('holder.py')
        self.assertEqual(set(n.PROFILE),set(policy.MODES));self.assertEqual(set(h.KINDS),set(policy.MODES))
        for mode in policy.MODES:
            self.assertEqual(n.PROFILE[mode]['cap'],262144);self.assertEqual(h.KINDS[mode][-1],'predictions.json')
        entry=module('candidate_entry.py');calls=[]
        for mode in policy.MODES:
            with patch.object(entry.sys,'argv',['entry','1073741824',mode]),patch.object(entry,'observed',lambda n:None),patch.object(entry.os,'execv',lambda exe,args:calls.append(args)):entry.main()
        self.assertEqual(calls[0][-4:],['--input','/input','--out','/output/predictions.json'])
        self.assertEqual([a[-1] for a in calls[1:]],list(policy.MODES[1:]))
    def test_native_output_and_closure_controls(self):
        n=module('native.py',c=c);import base64
        raw=b'{}';v=dict(schema='neural084-capture-v1',kind='cca',**pin(raw),base64=base64.b64encode(raw).decode())
        self.assertEqual(n.output_reply(encoded(v),'cca'),raw)
        v['kind']='constant'
        with self.assertRaises(ValueError):n.output_reply(encoded(v),'cca')
        good=dict(Status='exited',Running=False,Dead=False,Pid=0,ExitCode=0,OOMKilled=False)
        c.validate_natural_exit(good)
        for k,v in [('ExitCode',False),('Pid',True),('OOMKilled',True),('Running',0)]:
            bad=dict(good);bad[k]=v
            with self.assertRaises(ValueError):c.validate_natural_exit(bad)
    def test_full54_controller_and_late_failure(self):
        global PHYSICAL
        # Real tiny owned paths, but source/input/native boundaries are explicitly invented stubs.
        # This discriminates orchestration, mode closure, retirement and failure publication only.
        def run(fail=None):
            global PHYSICAL
            with tempfile.TemporaryDirectory() as td:
                base=Path(td).resolve();out=base/'attempt';program=base/'candidate.py';program.write_bytes(b'pass\n');PHYSICAL+=5
                rows=[dict(person=p,root=base/f'source{p}',fold=dict(fold=f'fold{p:03d}')) for p in range(1,55)]
                plan=baseplan();s=dict(output=str(out),repository=str(base),program=dict(path=str(program),**pin(b'pass\n')),public_manifest=dict(path=str(base/'INPUT_INDEX.json'),**pin(b'{}')),preparation={'test':'preparation'},input_review={'test':'input'},plan=plan,other_future_bytes=0,limits=policy.limits(plan,60,60))
                packets=types.SimpleNamespace(PRED_CAP=262144,NATIVE_CAP=262144,JSON_CAP=262144)
                calls=[];verifies=[];retired=[]
                packets.inspect_index=lambda raw,b:(dict(preparation=s['preparation'],input_review=s['input_review']),rows,plan)
                packets.unchanged=lambda row,b:None
                def view(path,row,docs,b):path.mkdir();(path/'tiny').write_bytes(b'x');return {'tiny':pin(b'x')}
                packets.view=view
                def verify(path,expected,b):verifies.append(path);return {'tiny':c.stamp((path/'tiny').stat())}
                packets.verify_view=verify
                def retire(path,expected,stamps,b):retired.append(path);(path/'tiny').unlink();path.rmdir()
                packets.retire=retire;packets.prediction=lambda raw,fold:None
                class Budget:
                    def __init__(self,*args):self.reads=self.writes=0
                    def capacity(self,*a):return 0
                    def read(self,n):self.reads+=n
                    def write(self,n):self.writes+=n
                    def tick(self):pass
                    def native(self,*a):pass
                    def record(self):return dict(reads=self.reads,writes=self.writes)
                original_capture=c.capture
                def capture(path,cap,expected=None,tick=lambda:None,charge=lambda n:None):
                    if Path(path)==base/'INPUT_INDEX.json':return b'{}'
                    return original_capture(path,cap,expected,tick,charge)
                def native(s,here,current,program,model,attempt,kind,ordinal,source,b,end):
                    calls.append((ordinal,kind,program.name))
                    if (ordinal,kind)==fail:raise ValueError('invented late native failure')
                    pp=c.save(attempt/'predictions.json',b'{}',262144,b.tick,b.write)
                    c.save(attempt/'NATIVE.json',b'{}',262144,b.tick,b.write)
                    return dict(status='captured',all_native_resources_closed=True,output=pp)
                control=module('controller.py',c=c,policy=types.SimpleNamespace(MODES=policy.MODES,reviews=lambda *a:None),packet=packets,native=types.SimpleNamespace(phase=native))
                bodies={n:b'pass\n' for n in ('holder.py','candidate_entry.py','reference_program.py')};bodies['BINDING.json']=encoded(dict(sources={'score.py':dict(path='source-only-scorer',bytes=1,sha256='0'*64)}))
                # No actual dependency body; exact capture boundary substituted only for fake binding.
                def capture2(path,*a,**kw):
                    if Path(path)==base/'source-only-scorer':return b'x'
                    return capture(path,*a,**kw)
                with patch.object(c,'Budget',Budget),patch.object(c,'capture',capture2):
                    if fail:
                        with self.assertRaises(ValueError):control.run(s,{},bodies,0,s['limits']['whole_seconds']-s['limits']['observer_seconds'])
                        self.assertFalse((out/'COMPLETE.json').exists());self.assertFalse((out/'submission.json').exists());self.assertTrue((out/'FAILURE.json').exists())
                    else:
                        result=control.run(s,{},bodies,0,s['limits']['whole_seconds']-s['limits']['observer_seconds']);self.assertEqual(result['query_count'],21600)
                        self.assertEqual(calls,[(i,k,'program.py' if k=='candidate' else 'reference_program.py') for i in range(54) for k in policy.MODES]);self.assertEqual(len(verifies),270);self.assertEqual(len(retired),54)
                        self.assertFalse((out/'current').exists());self.assertEqual(len(c.parse((out/'submission.json').read_bytes())['folds']),54)
                PHYSICAL+=sum(p.stat().st_size for p in base.rglob('*') if p.is_file())+54 # tiny current writes conservative
                self.assertLess(PHYSICAL,1000000)
        run();run((53,'frequency-permuted'))
if __name__=='__main__':
    result=unittest.main(exit=False)
    print(json.dumps(dict(canonical_serialization_bytes=CANONICAL,physical_fixture_bytes_conservative=PHYSICAL,actual_native_runs=0,authentic_input_reads=0),sort_keys=True))
    raise SystemExit(not result.result.wasSuccessful())
