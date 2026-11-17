"""Independent Wave14 RAM controls. No processes, timers, arrays, truth or grading.

Source is parsed then only selected definitions are executed. Every filesystem,
engine and lifecycle operation exercised below is an in-memory replacement.
"""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
READ_BYTES = 0
INVENTED_BYTES = 0


def source(name):
    global READ_BYTES
    b = (ROOT / name).read_bytes()
    READ_BYTES += len(b)
    return b.decode()


def defs(name, ns, names=None, constants=()):
    tree = ast.parse(source(name), filename=name)
    nodes = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and (names is None or n.name in names):
            nodes.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets):
            nodes.append(n)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), name, 'exec'), ns)
    return ns


def charge(value):
    global INVENTED_BYTES
    if isinstance(value, bytes):
        INVENTED_BYTES += len(value)
    elif isinstance(value, str):
        INVENTED_BYTES += len(value.encode())
    else:
        INVENTED_BYTES += len(json.dumps(value, sort_keys=True).encode())
    return value


def namespace():
    ns = dict(hashlib=hashlib, json=json, math=math, re=re, Path=Path, stat=stat,
              os=types.SimpleNamespace(), time=types.SimpleNamespace(monotonic=lambda: 10.0))
    defs('common.py', ns, constants=('TASK', 'META_CAP', 'PROGRAM_CAP'))
    defs('controller.py', ns, constants=('WORK', 'PUBLICATION', 'OUTER', 'PROGRAMS', 'ARMS', 'COVERAGE'))
    ns['HERE'] = P('/source')
    return ns


class P:
    FS = {}
    def __init__(self, p): self.p = PurePosixPath(p.p if isinstance(p, P) else p)
    def __truediv__(self, q): return P(self.p / str(q))
    def __str__(self): return str(self.p)
    def mkdir(self, **_): pass
    def relative_to(self, other): return self.p.relative_to(str(other))
    def stat(self): return types.SimpleNamespace(st_size=len(self.FS[str(self)]))
    def exists(self): return str(self) in self.FS
    @property
    def parent(self): return P(self.p.parent)


class Budget:
    read = written = retained_charge = 0
    def __init__(self): self.events = []
    def deadline(self): self.events.append(('deadline',))
    def reading(self, n): self.events.append(('read', n))
    def writing(self, n): self.events.append(('write', n))
    def producer_writes(self, n): self.events.append(('producer', n))


def ram(ns):
    fs, writes, reads = {}, [], []
    P.FS = fs
    def save(p, b, *_, **__):
        key = str(p)
        if key in fs: raise FileExistsError(key)
        fs[key] = charge(b); writes.append(key)
        return ns['pin'](b)
    def capture(p, d, cap, *_, retain=True, **__):
        key = str(p); reads.append(key)
        b = fs[key]
        assert ns['pin'](b) == {k:d[k] for k in ('bytes', 'sha256')}
        assert len(b) <= cap
        return b if retain else ns['pin'](b)
    ns.update(save=save, capture=capture, ordinary=lambda p:P(p),
              os=types.SimpleNamespace(chmod=lambda *_:None))
    return fs, writes, reads


def evidence(ns, ctx, source_pin, deadline):
    prefix = 'isttc-' + 'a' * 24
    return {
        'schema':'isttc_owned_phase_v1', 'status':'captured', 'phase':ctx['role'],
        'phase_id':ctx['phase_id'], 'source':source_pin, 'original_deadline':deadline,
        'producer_closed_before_capture':True, 'all_native_resources_closed':True,
        'cli_reaped':True, 'qualification_inherited':False, 'numerical_grading_called':False,
        'natural_exit':{'invented':'closed-zero'}, 'command_metadata':[{'invented':'closed'}],
        'attempt_prefix':prefix, 'closures':[
            dict(kind=k, name=prefix+s, closed=True, absence_observed=True, creation_outcome_unknown=False)
            for k,s in [('container','-'+ctx['role']),('container','-holder'),('volume','-volume')]],
        'source_before':{'manifest':source_pin}, 'source_after':{'manifest':source_pin},
        'artifacts':{'capture_complete':True, 'files':{
            'estimates.csv':ns['pin'](b'invented-csv'), 'methods.json':ns['pin'](b'invented-meta')}},
        'elapsed_seconds':9.0,
    }


def engine(ns):
    e = types.SimpleNamespace()
    e.OUTPUTS = {r:{'estimates.csv':100000000,'methods.json':20000} for r in ('reproduction','improvement','reference')}
    e.SUPPORT = {r:[] for r in e.OUTPUTS}
    e.TIMES = {r:dict(setup_seconds=120, producer_seconds=172800, capture_seconds=1800, cleanup_seconds=120) for r in e.OUTPUTS}
    e.validate_natural_exit = lambda r:ns['need'](r=={'invented':'closed-zero'}, 'independent natural exit')
    e.validate_cli_records = lambda r:ns['need'](r==[{'invented':'closed'}], 'independent CLI closure')
    return e


class Review(unittest.TestCase):
    def test_01_full_context_and_single_global_order(self):
        n=namespace(); rows=n['contexts']()
        self.assertEqual([(r['role'],r['arm']) for r in rows], [('reproduction','A'),('reproduction','B'),('improvement','A'),('improvement','B'),('reference',None)])
        self.assertEqual(n['COVERAGE'],dict(units=100000,continuous_records=100000,continuous_ms=600000,trial_records=4000000,trials_per_unit=40,trial_ms=1000))
        calls=[]
        o=types.SimpleNamespace(commit_all_four_before_data=lambda:calls.append('freeze'), phase=lambda r:(calls.append(r['phase_id']) or r), complete=lambda rs:(calls.append('complete') or rs))
        self.assertEqual(n['run_sequence'](o), rows)
        self.assertEqual(calls,['freeze']+[r['phase_id'] for r in rows]+['complete'])
        charge(calls)

    def pair_fixture(self,n):
        fs,writes,reads=ram(n); bodies={'CANDIDATE_ABI.md':b'invented interface','RESOURCE_PLAN.json':b'invented resource profile'}
        b={'candidate_assets':{'A':[dict(target='paper.md',bytes=2,sha256='a'*64),dict(target='data/x.npy.gz',bytes=3,sha256='b'*64)],'B':[dict(target='paper.md',bytes=2,sha256='a'*64),dict(target='data/x.npy.gz',bytes=3,sha256='b'*64),dict(target='source/x.py',bytes=4,sha256='c'*64)]}}
        def put(path,obj,raw=False):
            bb=obj if raw else n['canonical'](obj); fs[path]=charge(bb); return {'path':path,**n['pin'](bb)}
        ap=put('/protocol',dict(schema='isttc_matched_authoring_protocol_v1',model='invented',model_revision='r',system_instructions_sha256='a'*64,tool_policy_sha256='b'*64,time_seconds=30,max_tokens=100,max_program_revisions=1,seed_policy='separate'))
        v={'images':{'reproduction':'sha256:'+'a'*64,'improvement':'sha256:'+'a'*64},'versions':{'reproduction':{'x':'1'},'improvement':{'x':'1'}}}
        pair=dict(schema='isttc_independent_program_pair_v1',task_id=n['TASK'],programs={},authorship={},authoring_protocol=ap,root_attests_separate_contexts=True,root_attests_records_are_authentic=True,root_attests_no_cross_arm_feedback=True)
        for arm in ('A','B'):
            programs={r:put('/'+arm+'/'+r,('print('+repr(arm+r)+')').encode(),True) for r in ('reproduction','improvement')}
            pair['programs'][arm]=programs
            allowed={x['target']:{k:x[k] for k in ('bytes','sha256')} for x in b['candidate_assets'][arm] if not x['target'].endswith('.npy.gz')}
            allowed.update({x:n['pin'](bodies[x]) for x in bodies})
            vp=put('/'+arm+'/view',dict(schema='isttc_authoring_view_v1',task_id=n['TASK'],arm=arm,files=allowed,numeric_data_files=0,private_files=0,construction_custody_attested_by_root=True))
            record=dict(schema='isttc_independent_authorship_v1',arm=arm,context_id='distinct-'+arm,programs={r:{k:d[k] for k in ('bytes','sha256')} for r,d in programs.items()},interface=n['pin'](bodies['CANDIDATE_ABI.md']),resources=n['pin'](bodies['RESOURCE_PLAN.json']),authoring_protocol={k:ap[k] for k in ('bytes','sha256')},generation_seed=1,images=v['images'],versions=v['versions'],authoring_view=vp,original_or_prepared_numeric_inputs_seen=False,operator_private_seen=False,cross_arm_feedback=False,other_arm_program_seen=False,interface_supplied_before_finalization=True,prior_exposure_statement='Invented control only')
            pair['authorship'][arm]=put('/'+arm+'/record',record)
        v['pair']=put('/pair',pair)
        return v,b,bodies,fs,writes,reads,put

    def test_02_actual_global_commit_all_four_metadata_only(self):
        n=namespace();v,b,bodies,fs,writes,reads,_=self.pair_fixture(n)
        result,p=n['global_commit'](v,b,bodies,P('/out'),Budget())
        self.assertEqual(sum(len(x) for x in result['programs'].values()),4)
        self.assertFalse(result['data_or_native_phase_started'])
        self.assertFalse(result['attestation_is_independent_history_proof'])
        self.assertFalse(any('.npy.gz' in x for x in reads))
        self.assertEqual(writes[-1],'/out/PAIR_COMMITMENT.json')
        self.assertEqual(p,n['pin'](fs[writes[-1]]))

    def test_03_authorship_contamination_and_duplicate_context_refused(self):
        for changed in ('original_or_prepared_numeric_inputs_seen','operator_private_seen','cross_arm_feedback','other_arm_program_seen','context_id','extra_A_code'):
            n=namespace();v,b,bodies,fs,writes,reads,put=self.pair_fixture(n)
            pair=n['parse'](fs['/pair']);arm='A' if changed=='extra_A_code' else 'B'
            rec=n['parse'](fs['/'+arm+'/record'])
            if changed=='extra_A_code':
                view=n['parse'](fs['/A/view']);view['files']['source/x.py']={'bytes':4,'sha256':'c'*64};rec['authoring_view']=put('/A/view',view)
            else:rec[changed]='distinct-A' if changed=='context_id' else True
            pair['authorship'][arm]=put('/'+arm+'/record',rec);v['pair']=put('/pair',pair)
            with self.assertRaises(ValueError):n['global_commit'](v,b,bodies,P('/out'),Budget())
            self.assertNotIn('/out/PAIR_COMMITMENT.json',writes)

    def operations(self,fail=None):
        n=namespace();fs,writes,reads=ram(n);e=engine(n);events=[]
        bindings={'candidate_assets':{'A':[dict(target='data/x',source='invented/A',bytes=1,sha256='a'*64)],'B':[dict(target='data/x',source='invented/B',bytes=1,sha256='a'*64)]},'reference_assets':[dict(target='data/x',source='invented/ref',bytes=1,sha256='a'*64)],'input_binding':{'bytes':1,'sha256':'b'*64},'source_commit':'e78cfd2b2ea79b7a7e707db7b79e218212497e43','baseline_recipe':{'invented':'exact fixed baseline'}}
        class View:
            def __init__(self,root,rows,metadata,budget):self.root=root;self.meta=metadata;events.append(('stage',metadata['role'],metadata['arm'],rows))
            def handoff(self):return self.root
            def retire_after_closed_execution(self,receipt,check):check(receipt);events.append(('retire',receipt['phase_id']))
        n['staging']=types.SimpleNamespace(View=View)
        def commit(v,b,bodies,out,budget):
            programs={}
            for arm in ('A','B'):
                programs[arm]={}
                for role in ('reproduction','improvement'):
                    raw=charge((arm+role).encode());fs[str(out/'programs'/arm/(role+'.py'))]=raw;programs[arm][role]=n['pin'](raw)
            events.append(('freeze',))
            result={'schema':'isttc_global_four_program_commitment_v1','programs':programs,'data_or_native_phase_started':False}
            return result,n['save'](out/'PAIR_COMMITMENT.json',n['canonical'](result),budget)
        n['global_commit']=commit
        v=dict(repo='/repo',images={r:'sha256:'+'a'*64 for r in e.OUTPUTS},versions={r:{'generic':'1'} for r in e.OUTPUTS},source_manifest=n['pin'](b'source'),docker={'binary':'invented','socket':'invented'})
        def execute(executor,docker,**kw):
            ctx=next(r for r in n['contexts']() if r['phase_id']==kw['request']['phase_id'])
            events.append(('execute',ctx['phase_id'],None if kw['program'] is None else str(kw['program']),kw['original_deadline']))
            if ctx['index']==fail:raise RuntimeError('invented late failure')
            self.assertEqual(set(kw['readonly_mounts']),{'/input','/request.json'})
            for name,body in [('estimates.csv',b'invented-csv'),('methods.json',b'invented-meta')]:fs[str(kw['output_dir']/'artifacts'/name)]=charge(body)
            return evidence(n,ctx,v['source_manifest'],kw['original_deadline'])
        e.execute=execute
        validations=[]
        def validate(csv,meta,role):
            self.assertEqual((csv,meta),(b'invented-csv',b'invented-meta'));validations.append(role)
            return {'units':100000,'condition':'improvement' if role=='improvement' else 'reproduction','numeric_score_computed':False}
        n['validate_artifact']=validate
        o=n['Operations'](v,bindings,{'baseline/baseline.py':b'invented fixed baseline'},P('/out'),Budget(),2.0,e)
        return n,o,fs,writes,events,validations

    def test_04_actual_operations_all_five_and_independent_reference_policy(self):
        n,o,fs,writes,events,validated=self.operations()
        result=n['run_sequence'](o)
        self.assertEqual(events[0],('freeze',))
        runs=[x for x in events if x[0]=='execute']
        self.assertEqual(len(runs),5);self.assertTrue(all(x[3]==900002 for x in runs))
        self.assertEqual(runs[-1][2],None)
        self.assertEqual(validated,['reproduction','reproduction','improvement','improvement','reference'])
        self.assertEqual(len([x for x in events if x[0]=='retire']),5)
        pol=n['parse'](fs['/out/operator-baseline/POLICY.json'])
        expected=o.artifacts['04-reference-fixed-full']
        self.assertEqual(pol['artifacts'],{k:{q:d[q] for q in ('bytes','sha256')} for k,d in expected.items()})
        grade=n['parse'](fs['/out/PRIVATE_GRADE_JOIN.json'])
        self.assertEqual(grade['baseline_artifacts'],expected)
        self.assertEqual(len(grade['candidate_artifacts']),4)
        self.assertTrue(grade['assembly_required_before_existing_comparator'])
        self.assertTrue(grade['requires_external_whole_observer_success'])
        self.assertFalse(grade['automatic_grading']);self.assertFalse(result['scientific_qualification'])

    def test_05_late_reference_failure_cannot_publish_collection_or_policy(self):
        n,o,fs,writes,events,validated=self.operations(fail=4)
        with self.assertRaisesRegex(RuntimeError,'late failure'):n['run_sequence'](o)
        self.assertEqual(len(o.artifacts),4)
        for suffix in ('COLLECTION.json','PRIVATE_GRADE_JOIN.json','operator-baseline/POLICY.json'):
            self.assertNotIn('/out/'+suffix,fs)
        self.assertEqual(len([x for x in events if x[0]=='execute']),5)

    def test_06_exact_phase_closure_and_original_clock(self):
        n=namespace();e=engine(n);ctx=n['contexts']()[0];s=n['pin'](b'source');r=evidence(n,ctx,s,42)
        self.assertEqual(n['closure'](r,e,ctx,s,42),r['artifacts']['files'])
        def mutate(key,val):
            q=copy.deepcopy(r);q[key]=val;return q
        bad=[mutate('original_deadline',43),mutate('phase_id','wrong'),mutate('qualification_inherited',True),mutate('numerical_grading_called',True),mutate('natural_exit',{'invented':'running'}),mutate('command_metadata',[]),mutate('elapsed_seconds',float('nan'))]
        q=copy.deepcopy(r);q['closures'][2]['absence_observed']=False;bad.append(q)
        q=copy.deepcopy(r);q['source_after']={'manifest':n['pin'](b'changed')};bad.append(q)
        q=copy.deepcopy(r);q['artifacts']['files']['extra.csv']=n['pin'](b'x');bad.append(q)
        for q in bad:
            with self.assertRaises(ValueError):n['closure'](q,e,ctx,s,42)
        charge(r)

    def test_07_production_validator_has_fixed100000_and_complete_method_domain(self):
        n=namespace();base=('acf','isttc','pearsonr','isttc_trials');extra=('improved_full','improved_trials')
        class Full:
            def __len__(self):return 100000
            def __iter__(self):return iter([None,1.0]) # mock support, no scientific values
        seen=[]
        def validate(*args,**kw):
            self.assertEqual(len(args),2);self.assertEqual(kw,{})
            seen.append(args);return {k:Full() for k in base+extra},{'condition':'improvement'}
        n['validation']=types.SimpleNamespace(BASE=base,EXTRA=extra,validate=validate)
        r=n['validate_artifact'](b'x',b'{}','improvement');self.assertEqual(r['required_rows'],600000)
        with self.assertRaises(ValueError):n['validate_artifact'](b'x',b'{}','reference')
        n['validation'].validate=lambda *a:({k:Full() for k in base},{'condition':'improvement'})
        with self.assertRaises(ValueError):n['validate_artifact'](b'x',b'{}','improvement')

    def test_08_tiny_literal_validator_preserves_failures_and_positive_unclipped_domain(self):
        import csv,io
        ns=dict(csv=csv,io=io,json=json,math=math)
        defs('validation.py',ns,constants=('N','BASE','EXTRA','REV'))
        meta=dict(schema='isttc_submission_v1',condition='improvement',source_commit=ns['REV'],notes='invented')
        rows=['unit_id,method,status,tau_ms']
        for method in ns['BASE']+ns['EXTRA']:
            rows += [f'0,{method},ok,500',f'1,{method},failed,']
        raw=charge(('\n'.join(rows)+'\n').encode());mb=charge(json.dumps(meta).encode())
        values,_=ns['validate'](raw,mb,n=2)
        self.assertTrue(all(v==[500.0,None] for v in values.values()))
        for bad in [raw.replace(b',ok,500',b',ok,nan',1),raw.replace(b',failed,',b',failed,1',1),raw.replace(b'0,acf',b'00,acf',1),raw+b'0,acf,ok,1\n',b'\n'.join(raw.splitlines()[:-1])+b'\n']:
            charge(bad)
            with self.assertRaises(ValueError):ns['validate'](bad,mb,n=2)

    def test_09_copy_attempts_both_descriptor_closes_even_if_first_fails(self):
        n=namespace();defs('staging.py',n,names={'copy'})
        closes=[];payload=b'abc';stamp=types.SimpleNamespace(st_mode=stat.S_IFREG|0o444,st_nlink=1,st_size=3)
        class Q(P):
            def lstat(self):return stamp
        def close(fd):
            closes.append(fd)
            if fd==10:raise OSError('first close failure')
        n.update(ordinary=lambda p:Q(p),identity=lambda s:('stable',),sync=lambda _:None)
        n['os']=types.SimpleNamespace(O_RDONLY=1,O_NOFOLLOW=2,O_NONBLOCK=4,O_WRONLY=8,O_CREAT=16,O_EXCL=32,open=Mock(side_effect=[10,11]),fstat=lambda _:stamp,read=Mock(side_effect=[payload,b'']),write=lambda fd,v:len(v),fchmod=lambda *_:None,fsync=lambda _:None,close=close)
        with self.assertRaisesRegex(OSError,'close uncertainty'):n['copy']('/in','/out',n['pin'](payload),Budget())
        self.assertEqual(closes,[10,11]);charge(payload)

    def test_10_source_selection_refuses_before_poisoned_candidate_operands(self):
        n=namespace()
        v=dict(schema='isttc_complete_program_operation_v1',task_id=n['TASK'],operation_selected=True,operation_id='invented',source_manifest=n['pin'](b'source'),repo='/repo',images={k:'sha256:'+'a'*64 for k in ('reproduction','improvement','reference')},versions={k:{} for k in ('reproduction','improvement','reference')},docker={'binary':'invented','socket':'invented'},pair=n['pin'](b'pair'),other_future_bytes=0,runtime_qualified=False,scientific_qualification=False,full_paper_reproduction=False,exclusive_operator_custody=True,native_linux_host=True,physical_host_capacity_reviewed=True,generic_image_exposure_reviewed=True)
        self.assertEqual(n['selected'](v),v)
        for key in ('operation_selected','exclusive_operator_custody','generic_image_exposure_reviewed'):
            q=copy.deepcopy(v);q[key]=False
            with self.assertRaises(ValueError):n['selected'](q)
        q=copy.deepcopy(v);q['images']['reference']='sha256:'+'b'*64
        with self.assertRaises(ValueError):n['selected'](q)
        charge(v)

    def test_11_observer_rechecks_all5_collection_artifact_and_clock_joins(self):
        n,o,fs,writes,events,validated=self.operations()
        n['run_sequence'](o)
        ob=dict(json=json,hashlib=hashlib,ORIGIN=2.0)
        defs('observe.py',ob,names={'need','pin','parse','verify_collection'})
        class IO:
            def capture(self,path,d,cap=1048576,owned_metadata_without_external_pin=False,**kw):
                b=fs[str(path)]
                self_assert=len(b)<=cap and len(b)==d['bytes']
                assert self_assert
                if not owned_metadata_without_external_pin:assert n['pin'](b)=={k:d[k] for k in ('bytes','sha256')}
                return b
        o.engine.validate_request=lambda role,r:n['need'](r['schema']=='isttc_owned_phase_request_v1' and r['entry']==role+'_entry.py','invented complete request')
        ctrl=types.SimpleNamespace(**n)
        expected=n['pin'](fs['/out/COLLECTION.json'])
        self.assertEqual(ob['verify_collection'](IO(),P('/out'),o.v,ctrl,o.engine),expected)
        self.assertEqual(validated,['reproduction','reproduction','improvement','improvement','reference']*2)
        original=fs['/out/COLLECTION.json']
        for key,value in [('original_origin',3.0),('coverage',{'units':2}),('scientific_qualification',True),('private_grade_called',True)]:
            bad=n['parse'](original);bad[key]=value;fs['/out/COLLECTION.json']=charge(n['canonical'](bad))
            with self.assertRaises(ValueError):ob['verify_collection'](IO(),P('/out'),o.v,ctrl,o.engine)
        fs['/out/COLLECTION.json']=original
        bad=n['parse'](original);bad['artifacts']['04-reference-fixed-full']['estimates.csv']['path']='phases/02-improvement-A-full/closed/artifacts/estimates.csv'
        fs['/out/COLLECTION.json']=charge(n['canonical'](bad))
        with self.assertRaises(ValueError):ob['verify_collection'](IO(),P('/out'),o.v,ctrl,o.engine)

    def test_12_controller_and_observer_startup_cleanup_without_real_timer(self):
        for filename in ('controller.py','observe.py'):
            events=[];failure=RuntimeError('invented arm failure')
            def timer(kind,seconds):
                events.append(('timer',seconds))
                if seconds:raise failure
            handlers={1:'old-alarm',2:'old-term',3:'old-int'}
            signal=types.SimpleNamespace(SIGALRM=1,SIGTERM=2,SIGINT=3,ITIMER_REAL=7,getitimer=lambda _: (0.0,0.0),setitimer=timer,signal=lambda sig,h:events.append(('handler',sig,h)))
            ns=dict(signal=signal,INITIAL_HANDLERS=handlers,CLOCK_OWNED=False,ORIGIN=1.0,time=types.SimpleNamespace(monotonic=lambda:2.0))
            defs(filename,ns,names={'cleanup_clock','enter_startup'})
            with self.assertRaises(RuntimeError) as got:ns['enter_startup']()
            self.assertIs(got.exception,failure)
            self.assertIn(('timer',0),events)
            self.assertEqual([x[1:] for x in events if x[0]=='handler'][-3:],list(handlers.items()))
            self.assertFalse(ns['CLOCK_OWNED'])
            events.clear();signal.getitimer=lambda _:(10.0,0.0)
            with self.assertRaisesRegex(RuntimeError,'inactive timer'):ns['enter_startup']()
            self.assertEqual(events,[])
        charge({'two_fake_signals':True})

    def test_13_retirement_credit_only_after_full_cleanup_and_durable_parent(self):
        for failure in (None,'closure','verify','unlink','rmdir','sync'):
            n=namespace();defs('staging.py',n,names={'View'});events=[]
            class Q(P):
                def __truediv__(self,q):return Q(self.p/str(q))
                @property
                def parent(self):return Q(self.p.parent)
                def exists(self):return False
                def unlink(self):
                    events.append(('unlink',str(self)))
                    if failure=='unlink' and str(self).endswith('/data/a'):raise OSError('invented unlink failure')
                def rmdir(self):
                    events.append(('rmdir',str(self)))
                    if failure=='rmdir' and str(self).endswith('/data'):raise OSError('invented rmdir failure')
            class B:
                retained_charge=500;read=123;written=456
                def release_retired(self,x):events.append(('credit',x));self.retained_charge-=x
            budget=B()
            def cp(source,target,d,b):b.retained_charge+=100;return d
            def save(path,body,b):b.retained_charge+=50;return n['pin'](body)
            def sync(path):
                events.append(('sync',str(path)))
                if failure=='sync':raise OSError('invented sync failure')
            n.update(ordinary=lambda p:Q(p),copy=cp,save=save,capture=lambda *a,**k:None,sync=sync,
                     tree=lambda root:({x:types.SimpleNamespace(st_mode=stat.S_IFREG|0o444) for x in ('data/a','data/b','VIEW.json')},['data']),
                     os=types.SimpleNamespace(chmod=lambda *a:events.append(('chmod',str(a[0])))))
            rows=[dict(source='invented',target='data/'+x,bytes=1,sha256='a'*64) for x in ('a','b')]
            v=n['View']('/view',rows,{'invented':True},budget)
            self.assertEqual((v.retirement_credit,budget.retained_charge),(250,750))
            events.clear()
            def closure(_):
                events.append(('closure',))
                if failure=='closure':raise ValueError('invented bad closure')
            def verify():
                events.append(('verify',))
                if failure=='verify':raise ValueError('invented bad view')
            v.verify=verify
            if failure:
                with self.assertRaises((ValueError,OSError)):v.retire_after_closed_execution({},closure)
                self.assertEqual(budget.retained_charge,750);self.assertTrue(v.live)
                self.assertFalse(any(e[0]=='credit' for e in events))
                if failure in ('unlink','rmdir'):
                    self.assertEqual(len([e for e in events if e[0]=='unlink']),3)
                    self.assertEqual(len([e for e in events if e[0]=='rmdir']),2)
            else:
                v.retire_after_closed_execution({},closure)
                self.assertEqual(events[-2:],[('sync','/'),('credit',250)])
                self.assertEqual(budget.retained_charge,500);self.assertFalse(v.live)
                with self.assertRaises(ValueError):v.retire_after_closed_execution({},closure)
            self.assertEqual((budget.read,budget.written),(123,456))
            charge(events)

    def test_14_budget_counter_and_resource_reservation_arithmetic(self):
        n=namespace();n['os']=types.SimpleNamespace(statvfs=lambda _:types.SimpleNamespace(f_frsize=4096,f_bavail=10**9))
        budget=n['Budget']('/invented',100.0,read_cap=64*1024**3,write_cap=16*1024**3,retained_cap=3*1024**3,other_future=16*1024**2)
        budget.reading(10);budget.writing(3);prior=(budget.read,budget.written,budget.metadata_written)
        allocated=4096+17*4096;self.assertEqual(budget.retained_charge,allocated)
        budget.release_retired(allocated)
        self.assertEqual(budget.retained_charge,0);self.assertEqual((budget.read,budget.written,budget.metadata_written),prior)
        with self.assertRaises(ValueError):budget.release_retired(1)
        resources=json.loads(source('RESOURCE_PLAN.json'))
        expected=2172976788+5*100020000+64*1024**2+256*1024**2
        self.assertEqual(expected,3008621108)
        self.assertEqual(resources['retained_peak_derivation']['derived_host_peak_upper'],expected)
        self.assertLess(expected,3*1024**3)
        self.assertEqual(resources['whole_retained_reservation'],3*1024**3+16*1024**2)
        self.assertEqual(resources['free_floor'],2*1024**3)
        self.assertEqual(resources['full_phase_sum'],5*(120+172800+1800+120))
        self.assertEqual(resources['timing_basis']['complete_method_unit_rows'],100000*(4+4+6+6+4))
        self.assertLess((5*(3*158+32)+44+128)*(4095+17*4096),256*1024**2)
        charge({'allocation':allocated,'derived':expected})

    def test_15_reference_reserves_both_known_artifact_copies(self):
        n,o,fs,writes,events,validated=self.operations()
        n['run_sequence'](o)
        declared=[e[1] for e in o.budget.events if e[0]=='producer']
        self.assertEqual(declared,[100020000]*4+[200040000])
        self.assertEqual(sum(declared),600120000)
        charge(declared)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Review)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'groups':result.testsRun,'success':result.wasSuccessful(),'source_bytes_read':READ_BYTES,'invented_serialized_bytes':INVENTED_BYTES,'physical_fixtures':0,'actual_process_timer_fit_score_runs':0},sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
