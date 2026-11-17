"""Complete generated eight-person/195-field controls; no authentic/native execution."""
import copy,hashlib,importlib.util,json,math,os,resource,sys,tempfile,time,types,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
READ_BYTES=0;MAX_FIXTURE_BYTES=0;PRIVATE_OPENS=[]
_original_fdopen=os.fdopen;_original_read=os.read;_original_open=os.open
class Metered:
    def __init__(self,f):self.f=f
    def __getattr__(self,n):return getattr(self.f,n)
    def __enter__(self):self.f.__enter__();return self
    def __exit__(self,*args):return self.f.__exit__(*args)
    def read(self,*args):
        global READ_BYTES
        b=self.f.read(*args);READ_BYTES+=len(b);return b
def metered_fdopen(*a,**k):return Metered(_original_fdopen(*a,**k))
def metered_read(*a,**k):
    global READ_BYTES
    b=_original_read(*a,**k);READ_BYTES+=len(b);return b
def monitored_open(path,flags,*a,**kw):
    if '/private/reference/' in str(path) and not flags & (os.O_WRONLY|os.O_RDWR):PRIVATE_OPENS.append(str(path))
    return _original_open(path,flags,*a,**kw)
os.fdopen=metered_fdopen;os.read=metered_read;os.open=monitored_open
def read(p):
    global READ_BYTES
    b=Path(p).read_bytes();READ_BYTES+=len(b);return b
def load(name,path):
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(read(path),str(path),'exec'),m.__dict__);return m
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return pin(b)
def check_peak(root):
    global MAX_FIXTURE_BYTES
    n=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());MAX_FIXTURE_BYTES=max(MAX_FIXTURE_BYTES,n);assert n<2000000
CURRENT=HERE.parents[4]/'benchmarks/integrity/current-closures/input-neural078/SOURCE_MANIFEST.json'
api=load('_test078_api',HERE/'score_artifact.py');SOURCE=pin(read(CURRENT));CONTEXT=api.bootstrap(SOURCE,manifest_path=CURRENT);SOURCES,MODS,_=CONTEXT;IO=MODS['bound_io'];ADM=MODS['admission'];GRADE=MODS['grading'];WORKER=load('_test078_worker',HERE/'trusted_entry.py')
# Only scalar finiteness and an unused OFFSETS declaration are exercised in these
# stdlib generated report tests; actual NumPy/runtime dependency is unqualified.
np=types.ModuleType('numpy');np.isfinite=math.isfinite;np.arange=lambda *a,**k:None;np.int16='int16';sys.modules['numpy']=np

class FakeBudget:
    def __init__(self,root,other=0):self.root=root;self.written=0
    def mkdir(self,p,parents=False,exist_ok=False):p.mkdir(parents=parents,exist_ok=exist_ok)
    def admit_created_directory(self,p):p.mkdir(parents=True,exist_ok=True)
    def write(self,p,b,**kw):self.written+=len(b);write(p,b);check_peak(self.root.parent)
    def save(self,p,v,cap=200000,replace=False,publication=None):
        b=enc(v);assert len(b)<=cap
        if not replace:assert not p.exists()
        self.write(p,b);s=p.stat()
        if publication is not None:publication.update(st_dev=s.st_dev,st_ino=s.st_ino,**pin(b))
        return pin(b)
    def check(self,*a,**k):pass

class FakeDocker:
    def __init__(self):self.items={};self.target_reads=0;self.starts=0
    def absent(self,args,target,volume=False):
        text=('Error response from daemon: get '+target+': no such volume\n') if volume else ('Error: No such object: '+target+'\n')
        return types.SimpleNamespace(returncode=1,stdout=b'',stderr=text.encode())
    def __call__(self,binary,env,args,deadline,cap):
        if args[0]=='create':
            name=args[args.index('--name')+1];image=args[args.index('--entrypoint')+2]
            mounts={}
            for i,x in enumerate(args):
                if x=='--mount':
                    fields=dict(y.split('=',1) for y in args[i+1].split(',') if '=' in y);mounts[fields['dst']]=Path(fields['src'])
            h={'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':None,'SecurityOpt':['no-new-privileges:true'],'Devices':[],'DeviceRequests':None,'PortBindings':{},'PidMode':'','IpcMode':'private','AutoRemove':False,'Init':False,'RestartPolicy':{'Name':'no'},'Memory':512*1024**2,'MemorySwap':512*1024**2,'NanoCpus':1000000000,'PidsLimit':32,'ShmSize':1048576,'OomKillDisable':False,'Tmpfs':GRADE.TMPFS,'LogConfig':{'Type':'local','Config':{'max-size':'64k','max-file':'1','compress':'false'}},'Ulimits':[{'Name':k,'Soft':a,'Hard':b} for k,(a,b) in GRADE.ULIMITS.items()],'Mounts':[{'Type':'bind','Source':str(p),'Target':d,'ReadOnly':True} for d,p in mounts.items()]}
            obj={'Id':'f'*64,'Name':'/'+name,'Image':image,'Config':{'Image':image,'Entrypoint':['python'],'Cmd':GRADE.COMMAND,'User':GRADE.grade_user(mounts),'WorkingDir':'/','Env':[k+'=1' for k in GRADE.THREADS]+['PYTHONDONTWRITEBYTECODE=1']},'State':{'Status':'created','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'HostConfig':h,'NetworkSettings':{'Networks':{'none':{}}},'Mounts':[{'Type':'bind','Source':str(p),'Destination':d,'RW':False} for d,p in mounts.items()]}
            obj['Config']['Healthcheck']={'Test':['NONE']}
            self.items[name]=(obj,mounts);return types.SimpleNamespace(returncode=0,stdout=b'f'*64+b'\n',stderr=b'')
        if args[0]=='inspect' or args[:2]==['volume','inspect']:
            target=args[-1];found=next((obj for obj,_ in self.items.values() if target in (obj['Name'][1:],obj['Id'])),None)
            if found is None:return self.absent(args,target,args[0]=='volume')
            return types.SimpleNamespace(returncode=0,stdout=enc([found]),stderr=b'')
        if args[0]=='start':
            obj,mounts=self.items[args[-1]];self.starts+=1
            source={n:read(mounts['/source/'+n]) for n in ('public_report.py','report_contract.py','bound_io.py','admission.py','gold_binding.py','analysis_core.py','score.py')}
            metadata={n:read(mounts['/private/'+n]) for n in ('TARGET_BINDING.json','WORKER_COMPLETION.json','RECOVERY_ATTEMPT.json','RECOVERY_COMPLETION.json')}
            rows=json.loads(read(mounts['/inputs/ROWS.json']))
            def target(pin):
                self.target_reads+=1;return read(mounts['/private/GOLD.json'])
            r=WORKER.evaluate(read(mounts['/inputs/report.json']),metadata,rows,source,target)
            obj['State'].update(Status='exited')
            return types.SimpleNamespace(returncode=0,stdout=enc(r),stderr=b'')
        if args[0]=='rm':
            target=args[-1];name=next(k for k,(obj,_) in self.items.items() if target in (k,obj['Id']));del self.items[name]
            return types.SimpleNamespace(returncode=0,stdout=b'removed\n',stderr=b'')
        raise AssertionError(args)

def report(unsupported=False):
    v=MODS['public_report'].load(SOURCES['producer/program/report_contract.py']);people=[]
    for i,p in enumerate(v.PEOPLE):
        count=1 if unsupported and i==0 else 3
        row=dict(participant_id=p,eligible_error_n=count*4,eligible_correct_n=count*4,matched_pairs_n=count*4,pair_digest=hashlib.sha256(p.encode()).hexdigest(),stratum_support={s:dict(error_n=count,correct_n=count,pairs_n=count) for s in v.STRATA},status='insufficient_matched_pairs' if count==1 else 'supported')
        row.update({n:None if count==1 else -(i+1)*.25 for n in v.NUMBERS});people.append(row)
    return dict(schema='neural078_contrast_submission_v1',protocol_sha256=v.PROTOCOL_SHA256,participants=people,aggregate=dict(status='not_all_participants_supported' if unsupported else 'all_participants_supported',matched_FCz_equal_person_mean=None if unsupported else -1.125,matched_FCz_between_person_descriptive_SE=None if unsupported else .21))

def fixture(root,unsupported=False,bind_current_sources=True):
    root=root.resolve();repo=root/'repo';old=repo/'authoring/delivery-20261105/common/neural078-holder-readiness-successor-v1';attempt=root/'producer';package=repo/'authoring/delivery-20261105/common/exports/neural078-reference-v3';sources=dict(SOURCES)
    binding=json.loads(sources['producer/program/BINDINGS.json']);rows={r['target']:r for r in binding['files']};people=MODS['policy'].SCOPE['people'];gold=enc(report(unsupported))
    # This entirely generated producer/reference fixture binds its own numerical
    # source. The unchanged published original producer is not silently rebound.
    if bind_current_sources:
        for name in ('score.py','analysis_core.py'):rows['private/source/'+name].update(pin(sources['scorer/'+name]))
    gold_pin=write(package/'private/reference/GOLD.json',gold);rows['private/reference/GOLD.json'].update(gold_pin)
    bp=dict(schema='neural078_private_target_binding_v1',gold=dict(name='GOLD.json',**gold_pin),packets=[dict(person=p,name=p+'.npz',**ADM.only(rows['public/data/'+p+'.npz'])) for p in people],protocol_sha256=rows['public/PROTOCOL.json']['sha256'],frozen_sources={n:pin(sources['scorer/'+n]) for n in ('score.py','analysis_core.py')},empirical_EEG_contrasts_computed=True,new_scientific_choices=False,unsupported_nulls_preserved=True,host_admission_required=True,model_fits=0,candidate_or_method_evaluations=0,answer_source_sha256='a'*64)
    braw=enc(bp);bpin=write(package/'private/reference/TARGET_BINDING.json',braw);rows['private/reference/TARGET_BINDING.json'].update(bpin)
    worker=dict(schema='neural078_answer_worker_completion_v1',source_sha256='a'*64,host_admission_required=True,not_a_candidate_evaluation=True,files=[dict(name='GOLD.json',**gold_pin),dict(name='TARGET_BINDING.json',**bpin)])
    wraw=enc(worker);wpin=write(package/'private/reference/WORKER_COMPLETION.json',wraw);rows['private/reference/WORKER_COMPLETION.json'].update(wpin)
    limits=dict(original_host_admission_success=False,original_cleanup_within180seconds_proven=False,new_answer_computation=False,new_empirical_calculation=False)
    recovery=dict(schema='neural078_answer_recovery_attempt_v2',success=True,status='private_answer_recovered_from_existing_bytes',original_failure_preserved=True,model_or_candidate_evaluation=False,source_sha256='b'*64,outputs=dict(gold=dict(name='GOLD.json',**gold_pin),binding=dict(name='TARGET_BINDING.json',**bpin),worker_completion=wpin),**limits)
    araw=enc(recovery);apin=write(package/'private/reference/RECOVERY_ATTEMPT.json',araw);rows['private/reference/RECOVERY_ATTEMPT.json'].update(apin)
    rc=dict(schema='neural078_answer_recovery_completion_v2',subsequent_metadata_recovery=True,recovery_source_sha256='b'*64,recovery_record=apin,gold=dict(name='GOLD.json',**gold_pin),**limits)
    rpin=write(package/'private/reference/RECOVERY_COMPLETION.json',enc(rc));rows['private/reference/RECOVERY_COMPLETION.json'].update(rpin)
    source_desc=dict(task_ids=['NEURAL-078'],files=list(rows.values()));sd=write(repo/binding['source_descriptor']['path'],enc(source_desc));binding['source_descriptor'].update(sd)
    export=dict(task_ids=['NEURAL-078'],files=list(rows.values()),source_manifest=binding['source_descriptor']);ed=write(repo/binding['export_descriptor']['path'],enc(export));binding['export_descriptor'].update(ed)
    sources['producer/program/BINDINGS.json']=enc(binding)
    pm=json.loads(sources['producer/program/SOURCE_MANIFEST.json']);pm['files']['BINDINGS.json']=pin(sources['producer/program/BINDINGS.json']);sources['producer/program/SOURCE_MANIFEST.json']=enc(pm);ps=pin(sources['producer/program/SOURCE_MANIFEST.json']);adapter=pin(sources['producer/SOURCE_MANIFEST.json'])
    for n,b in sources.items():
        if n.startswith('producer/'):write(old/n[len('producer/'):],b)
    program=root/'candidate.py';pr=write(program,b"print('generated-only')\n");scope=MODS['policy'].SCOPE
    method=dict(schema='neural078_full8_method_review_v1',task_id='NEURAL-078',approved=True,source=ps,program=pr,other_future_bytes=0,scope=scope)
    for k in ('all8_and195_fields','one_program_before_public_input_access','grouping_covariates_intentionally_public','fixed_matching_windows_and_equal_person_aggregate','all_null_and_support_dispositions_preserved','complete_report_before_feedback','no_private_source_exposure'):method[k]=True
    for k in ('numeric_agreement_proves_neural_understanding','heldout_generalization_or_paper_parity','hashes_alone_prove_chronology'):method[k]=False
    mp=root/'method.json';mpin=write(mp,enc(method));image='sha256:'+'c'*64
    rt=dict(schema='neural078_runtime_profile_review_v1',task_id='NEURAL-078',approved=True,source=ps,program=pr,other_future_bytes=0,scope=scope,image=image,candidate_seconds=900,memory_bytes=1073741824,docker_binary=str(root/'docker'),docker_socket=str(root/'docker.sock'),runtime_versions=dict(python='3.12',numpy='2.2.6',scipy='1.15.3'),native_full_panel_qualification_required_before_campaign=True,qualification_inherited=False,independent_cli_groups_and_native_failure_recovery_acknowledged=True)
    rp=root/'runtime.json';rpin=write(rp,enc(rt))
    s=dict(schema='neural078_full8_program_selection_v1',execution_selected=True,task_id='NEURAL-078',repository=str(repo),output=str(attempt),program=dict(path=str(program),**pr),source=ps,docker_binary=rt['docker_binary'],docker_socket=rt['docker_socket'],image=image,candidate_seconds=900,memory_bytes=1073741824,other_future_bytes=0,scope=scope,retained_bytes=128000000,managed_reads=604000000,managed_writes=90016384,whole_seconds=2100,method_review=dict(path=str(mp),**mpin),runtime_review=dict(path=str(rp),**rpin),support_admission_authorized=True,numeric_grading_authorized=False)
    sp=root/'selection.json';spin=write(sp,enc(s));external=root/'EXTERNAL.json';reviewpath=root/'review.json'
    review=dict(schema='neural078_full8_central_review_v1',task_id='NEURAL-078',approved=True,numeric_grade_authorized=False,adapter_source=adapter,selection=dict(path=str(sp),**spin),source_exposure=dict(condition='full8_investigation',agent_mode='frozen_program',public_files=15,primitive_files=8,private_source_visible=False,source_history_attested_by_root=True),authoring_context_id='generated-only',adapter_additional_read_cap=500000,adapter_additional_retained_bytes=0,external_output=str(external));reviewpin=write(reviewpath,enc(review))
    write(attempt/'commitment/program.py',read(program));commit=write(attempt/'commitment/COMMITMENT.json',enc(dict(schema='neural078_full8_commitment_v1',source=ps,program=pr,scope=scope,method_review=mpin,before_any_public_signal_view=True)))
    prepared=write(attempt/'VIEW_PREPARED.json',enc(dict(files={str(Path(r['target']).relative_to('public')):ADM.only(r) for r in rows.values() if r['visibility']=='public'},member_count=15,primitive_files=8,decoded=False)))
    retired=write(attempt/'VIEW_RETIRED.json',enc(dict(schema='neural078_full8_public_retired_v1',member_count=15,primitive_files=8,absent=True,parent_fsynced=True)))
    reportpin=write(attempt/'candidate/report.json',gold)
    support=dict(task_id='NEURAL-078',status='schema_support_consistent_artifact_only',participants=8,required_fields=195,private_reference_calls=0,numeric_comparison_performed=False,scientific_qualification_added=False,operator_entrypoint='neural078_public_report_admission_v1',export_manifest_sha256=ed['sha256'],requires_observed_cli_exit_zero=True)
    supportpin=write(attempt/'admission/report.json',enc(support));natives={}
    command=dict(phase='generated',returncode=0,error_type=None,observed_retained_bytes=0,seconds=.1,client_reaped=True,cleanup_complete=True,cleanup_before_original_cutoff=True,owned_group_absence_observed=True,leader_exited_with_group_alive=False,group_probe_or_cleanup_error=None)
    for i,phase in enumerate(('candidate','admission')):
        prefix='neural078-'+str(i+1)*24;closures=[dict(kind=kind,name=prefix+'-'+name,removed=True,absence_observed=True,creation_outcome_unknown=False,closed=True) for name,kind in [(phase,'container'),('holder','container'),('volume','volume')]]
        nr=dict(phase=phase,source=ps,status='captured',output=reportpin if phase=='candidate' else supportpin,all_native_resources_closed=True,cli_reaped=True,producer_closed_before_capture=True,recovery_may_be_required=False,closures=closures,attempt_prefix=prefix,natural_exit=dict(Status='exited',Running=False,Dead=False,Pid=0,ExitCode=0,OOMKilled=False),command_metadata=[command],error_type=None,numerical_grading_called=False,elapsed_seconds=1.)
        natives[phase]=write(attempt/phase/'NATIVE.json',enc(nr))
    handoff=write(attempt/'GRADE_HANDOFF.json',enc(dict(report=dict(path=str(attempt/'candidate/report.json'),**reportpin),export_descriptor=binding['export_descriptor'],scope=scope,execution_authorized=False,scientific_reasoning_or_causality_or_SOTA_established=False)))
    complete=dict(source=ps,status='complete_unqualified',scope=scope,all_public_views_retired=True,complete_report_schema_support_validated=True,numerical_grading_performed=False,runtime_qualified=False,scientific_qualified=False,view_prepared=prepared,view_retirement=retired,commitment=commit,program=pr,report=reportpin,admission_output=supportpin,candidate_native=natives['candidate'],admission_native=natives['admission'],grade_handoff=handoff)
    cp=write(attempt/'COMPLETE.json',enc(complete));child=dict(natural_exit=True,process_reaped=True,process_group_absent=True,streams_closed=True,timed_out=False,kill_sent=False,error_type=None,timer_disable_error=None,timer_restore_error=None,exit_code=0,pid=999991,elapsed_seconds=1.,combined_stream_bytes=100,stdout_bytes=100)
    workerargv=['/generated/python','-I','-S','-B','-X','pycache_prefix='+str(external)+'.UNUSED-PYCACHE',str(old/'program/worker.py'),'--source-pin',json.dumps(ps),'--selection',str(sp),'--selection-pin',json.dumps(spin),'--origin',repr(1000.),'--worker-end',repr(3080.)]
    e=dict(schema='neural078_full8_external_v1',status='complete_unqualified',source=ps,selection=spin,attempt=str(attempt),argv=workerargv,child=child,error_type=None,report=reportpin,complete=cp,origin_monotonic=1000.,whole_deadline=3100.,outer_deadline=3160.,elapsed_before_publication=2.,full8_source_scope=True,scientific_qualified=False,runtime_qualified=False,numerical_grading_performed=False,nested_cli_and_native_recovery_may_be_required=False,automatic_retry=False)
    eraw=enc(e);epin=write(external,eraw+b' '*(8192-len(eraw)))
    argv=['/generated/python','-I','-S','-B','-X','pycache_prefix='+str(root/'unused-cache'),str(old/'adapter.py'),'--source-bytes',str(adapter['bytes']),'--source-sha256',adapter['sha256'],'--program',str(program),'--output',str(attempt),'--review',str(reviewpath),'--other-reserve-bytes','0']
    observation=dict(schema='neural078_trusted_outer_exit_v1',authority_id='generated-independent-observer',adapter_source=adapter,program_source=ps,selection=spin,review=reviewpin,external_receipt=epin,argv=argv,process=dict(pid=999992,pgid=999992,returncode=0,natural_exit=True,reaped=True,group_absent=True,elapsed_seconds=3.),signals_sent=[],completion_observed_after_process_exit=True,candidate_access_closed=True,scope=scope)
    op=root/'OUTER.json';opin=write(op,enc(observation));request=dict(schema='neural078_trusted_grade_selection_v1',task_id='NEURAL-078',operator_authority_id='generated-only-not-real-authority',source=SOURCE,numeric_grading_authorized=True,candidate_access_closed=True,producer=dict(repository=str(repo),source_directory=str(old),attempt=str(attempt),package=str(package),selection=dict(path=str(sp),**spin),review=dict(path=str(reviewpath),**reviewpin),external_receipt=dict(path=str(external),**epin)),observation=dict(path=str(op),**opin),output=str(root/'grade-output'),runtime=dict(docker_binary=str(root/'docker'),docker_socket=str(root/'docker.sock'),docker_config=str(root/'docker-config'),image=image),other_future_bytes=0)
    PRIVATE_OPENS.clear();IO.READ_BYTES=0;check_peak(root)
    return request,(sources,MODS,0),observation

def run(request,context,docker=None,**kw):
    api.ORIGIN=time.monotonic();return api.execute(request,SOURCE,context=context,check=lambda *a:True,call=docker or FakeDocker(),budget_class=FakeBudget,**kw)

class Tests(unittest.TestCase):
    def test_original_numerical_binding_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp),bind_current_sources=False);d=FakeDocker();result=run(req,ctx,d)
            self.assertFalse(result['success'],result)
            self.assertEqual(result['error_type'],'ValueError')
            self.assertFalse(result['private_grade_dispatched'])
            self.assertEqual((d.starts,d.target_reads,PRIVATE_OPENS),(0,0,[]))

    def test_complete195_protected_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));d=FakeDocker();result=run(req,ctx,d)
            self.assertTrue(result['success'],result);self.assertEqual((d.starts,d.target_reads,len(d.items)),(1,1,0));self.assertEqual(result['required_fields'],195)
            score=json.loads(read(Path(req['output'])/'grade/score.json'));self.assertEqual(score['matching_fields'],195);self.assertEqual(len(score['field_checks']),195)
            self.assertFalse(any(p.endswith('/GOLD.json') for p in PRIVATE_OPENS))
    def test_complete_null_dispositions(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp),True);d=FakeDocker();result=run(req,ctx,d);self.assertTrue(result['success'],result);self.assertEqual(d.target_reads,1)
    def test_outer_false_integer_zero_refuses_before_private(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,o=fixture(Path(temp));o['process']['returncode']=False;req['observation'].update(write(Path(req['observation']['path']),enc(o)));d=FakeDocker()
            with self.assertRaisesRegex(ValueError,'Actual natural outer zero'):run(req,ctx,d)
            self.assertEqual((d.target_reads,PRIVATE_OPENS),(0,[]))
    def test_signaled_outer_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,o=fixture(Path(temp));o['signals_sent']=['SIGTERM'];req['observation'].update(write(Path(req['observation']['path']),enc(o)))
            with self.assertRaisesRegex(ValueError,'Natural outer closure'):run(req,ctx)
            self.assertEqual(PRIVATE_OPENS,[])
    def test_changed_frozen_program_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));write(Path(req['producer']['attempt'])/'commitment/program.py',b'changed')
            with self.assertRaises(ValueError):run(req,ctx)
            self.assertEqual(PRIVATE_OPENS,[])
    def test_private_recovery_mismatch_refuses_before_gold(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));p=Path(req['producer']['package'])/'private/reference/TARGET_BINDING.json';p.write_bytes(b'{}');d=FakeDocker();r=run(req,ctx,d)
            self.assertFalse(r['success']);self.assertEqual(d.target_reads,0);self.assertFalse((Path(req['output'])/'COMPLETION.json').exists())
    def test_full_report_missing_person_refuses_before_private(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));args,o=api.selected(req,SOURCE,MODS);admitted=ADM.admit(args,ctx[0],MODS,o,lambda *a:True);bad=report();bad['participants'].pop();admitted['report']=enc(bad);original=ADM.admit
            ADM.admit=lambda *a,**k:admitted
            try:
                with self.assertRaisesRegex(ValueError,'All eight'):run(req,ctx)
            finally:ADM.admit=original
            self.assertEqual(PRIVATE_OPENS,[])
    def test_nonzero_native_field_mismatch_is_valid_score(self):
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));d=FakeDocker();old=WORKER.evaluate
            def modified(raw,*a,**k):
                report_value=json.loads(raw);report_value['participants'][0]['matched_FCz_contrast']+=1.;return old(enc(report_value),*a,**k)
            WORKER.evaluate=modified
            try:r=run(req,ctx,d)
            finally:WORKER.evaluate=old
            self.assertTrue(r['success'],r);score=json.loads(read(Path(req['output'])/'grade/score.json'));self.assertEqual(score['matching_fields'],194);self.assertEqual(score['score'],194/195)
    def test_writable_native_mount_refuses(self):
        class Writable(FakeDocker):
            def __call__(self,*a,**k):
                p=super().__call__(*a,**k)
                if a[2][0]=='create':
                    for obj,_ in self.items.values():obj['Mounts'][0]['RW']=True
                return p
        with tempfile.TemporaryDirectory() as temp:
            req,ctx,_=fixture(Path(temp));d=Writable();r=run(req,ctx,d);self.assertFalse(r['success']);self.assertEqual((d.starts,d.target_reads),(0,0))
    def test_live_outer_refuses(self):
        with self.assertRaisesRegex(ValueError,'still exists'):ADM.absent(os.getpid(),os.getpgrp())
    def test_native_malformed_report_never_requests_gold(self):
        source={n:SOURCES['scorer/'+n] if n in ('score.py','analysis_core.py') else SOURCES['producer/program/report_contract.py'] if n=='report_contract.py' else SOURCES[n] for n in ('public_report.py','report_contract.py','bound_io.py','admission.py','gold_binding.py','analysis_core.py','score.py')}
        bad=report();bad['participants'].pop();calls=[]
        with self.assertRaisesRegex(ValueError,'All eight'):WORKER.evaluate(enc(bad),{}, {},source,lambda *a:calls.append(a))
        self.assertEqual(calls,[])

if __name__=='__main__':
    started=time.monotonic();suite=unittest.TestSuite(Tests(n) for n in sys.argv[1:]) if sys.argv[1:] else unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),explicit_read_bytes=READ_BYTES,peak_fixture_bytes=MAX_FIXTURE_BYTES,peak_rss_darwin_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,elapsed_seconds=time.monotonic()-started,children=0)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
