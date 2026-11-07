"""Full100000-unit iSTTC reproduction/improvement pair. Never grades truth."""
import time
BOOT=time.monotonic()
import signal
INITIAL_HANDLERS={s:signal.getsignal(s) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
CLOCK_OWNED=False

def cleanup_clock(primary=None):
    failures=[]
    for action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda s=s,h=h:signal.signal(s,h) for s,h in INITIAL_HANDLERS.items()]:
        try:action()
        except BaseException as e:failures.append(type(e).__name__)
    if failures:
        if primary is not None:primary.add_note('Independent alarm cleanup uncertainty: '+','.join(failures))
        else:raise RuntimeError('Independent alarm cleanup uncertainty: '+','.join(failures))

def enter_startup():
    global CLOCK_OWNED
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('fresh inactive timer required')
    def expired(*_):raise TimeoutError('original whole-program clock')
    try:
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,120)
    except BaseException as e:
        cleanup_clock(e);raise
    CLOCK_OWNED=True
if __name__=='__main__':enter_startup()
import argparse,importlib.util,os,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
from common import *
import staging,validation
HERE=Path(__file__).absolute().parent
WORK=900000;PUBLICATION=900120;OUTER=900240
PROGRAMS={'reproduction':8*1024**2,'improvement':8*1024**2}
ARMS=('A','B')
COVERAGE={'units':100000,'continuous_records':100000,'continuous_ms':600000,'trial_records':4000000,'trials_per_unit':40,'trial_ms':1000}


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def selected(v):
    keys={'schema','task_id','operation_selected','operation_id','source_manifest','repo','images','versions','docker','pair','other_future_bytes','runtime_qualified','scientific_qualification','full_paper_reproduction','exclusive_operator_custody','native_linux_host','physical_host_capacity_reviewed','generic_image_exposure_reviewed'}
    need(type(v)is dict and set(v)==keys and v['schema']=='isttc_complete_program_operation_v1' and v['task_id']==TASK and v['operation_selected']is True,'exact operation selection before operands')
    need(all(v[k]is False for k in ('runtime_qualified','scientific_qualification','full_paper_reproduction')),'no qualification inheritance')
    need(all(v[k]is True for k in ('exclusive_operator_custody','native_linux_host','physical_host_capacity_reviewed','generic_image_exposure_reviewed')),'external custody/capacity/image-exposure authority')
    need(type(v['operation_id'])is str and re.fullmatch('[a-z0-9-]{1,64}',v['operation_id']),'operation ID')
    need(type(v['other_future_bytes'])is int and v['other_future_bytes']>=0,'standing OTHER')
    need(type(v['images'])is dict and set(v['images'])=={'reproduction','improvement','reference'} and all(type(x)is str and re.fullmatch('sha256:[a-f0-9]{64}',x) for x in v['images'].values()) and len(set(v['images'].values()))==1,'same pinned generic dependency image for all roles')
    need(type(v['versions'])is dict and set(v['versions'])==set(v['images']),'all role versions')
    for k in ('pair','source_manifest'):descriptor(v[k],META_CAP)
    need(type(v['docker'])is dict and set(v['docker'])=={'binary','socket'},'exact Docker selection')
    return v


def contexts():
    rows=[{'role':role,'arm':arm,'fold':None} for role in PROGRAMS for arm in ARMS]+[{'role':'reference','arm':None,'fold':None}]
    for i,r in enumerate(rows):r['index']=i;r['phase_id']=f'{i:02d}-{r["role"]}-{r["arm"] or "fixed"}-full'
    return rows


def bindings(b):
    need(b['schema']=='isttc_complete_program_bindings_v1' and b['task_id']==TASK and b['coverage']==COVERAGE,'entire selected source cohort')
    need([len(b['candidate_assets'][a]) for a in ARMS]==[20,43] and len(b['reference_assets'])==5,'complete unchanged original access views')
    need(b['candidate_assets']['B'][:20]==b['candidate_assets']['A'],'identical common data and paper')
    for rows in [*b['candidate_assets'].values(),b['reference_assets']]:
        need(len({x['target'] for x in rows})==len(rows),'unique complete view inventory')
        data=[r for r in rows if r['target'].endswith('.npy.gz')]
        need(len(data)==4 and sum(r['bytes'] for r in data)==2168730521,'all four exact input arrays')
    need(all(x['target'].startswith('data/') for x in b['reference_assets']),'reference has numeric inputs and descriptor only')
    return b


def authoring_files(b,bodies,arm):
    files={r['target']:descriptor(r,3*1024**3,allow_empty=True) for r in b['candidate_assets'][arm] if not r['target'].endswith('.npy.gz')}
    files.update({n:pin(bodies[n]) for n in ('CANDIDATE_ABI.md','RESOURCE_PLAN.json')})
    return files

def global_commit(v,b,bodies,out,budget):
    pair_raw=capture(v['pair']['path'],v['pair'],META_CAP,budget);pair=parse(pair_raw)
    keys={'schema','task_id','programs','authorship','authoring_protocol','root_attests_separate_contexts','root_attests_records_are_authentic','root_attests_no_cross_arm_feedback'}
    need(type(pair)is dict and set(pair)==keys and pair['schema']=='isttc_independent_program_pair_v1' and pair['task_id']==TASK and set(pair['programs'])==set(pair['authorship'])==set(ARMS) and all(pair[k]is True for k in keys if k.startswith('root_attests')),'separate complete A/B bundle')
    ap_raw=capture(pair['authoring_protocol']['path'],pair['authoring_protocol'],META_CAP,budget);ap=parse(ap_raw)
    need(type(ap)is dict and set(ap)=={'schema','model','model_revision','system_instructions_sha256','tool_policy_sha256','time_seconds','max_tokens','max_program_revisions','seed_policy'} and ap['schema']=='isttc_matched_authoring_protocol_v1','matched predeclared authoring protocol')
    need(all(type(ap[k])is int and 0<ap[k]<=10**9 for k in ('time_seconds','max_tokens','max_program_revisions')) and all(type(ap[k])is str and 0<len(ap[k])<=512 for k in ('model','model_revision','seed_policy')) and all(type(ap[k])is str and re.fullmatch('[a-f0-9]{64}',ap[k]) for k in ('system_instructions_sha256','tool_policy_sha256')),'bounded authoring controls')
    save(out/'authorship/PROTOCOL.json',ap_raw,budget)
    programs={};records={};identities=set()
    for arm in ARMS:
        need(set(pair['programs'][arm])==set(PROGRAMS),'both original code domains per arm')
        programs[arm]={}
        for role,cap in PROGRAMS.items():
            d=pair['programs'][arm][role];raw=capture(d['path'],d,cap,budget)
            need(len(raw)>0 and '\0'not in raw.decode('utf-8'),'nonempty UTF8 program')
            programs[arm][role]=save(out/'programs'/arm/(role+'.py'),raw,budget,cap);os.chmod(out/'programs'/arm/(role+'.py'),0o444)
        rr=pair['authorship'][arm];raw=capture(rr['path'],rr,META_CAP,budget);r=parse(raw)
        expected={'schema','arm','context_id','programs','interface','resources','authoring_protocol','generation_seed','images','versions','authoring_view','original_or_prepared_numeric_inputs_seen','operator_private_seen','cross_arm_feedback','other_arm_program_seen','interface_supplied_before_finalization','prior_exposure_statement'}
        need(type(r)is dict and set(r)==expected and r['schema']=='isttc_independent_authorship_v1' and r['arm']==arm and r['programs']==programs[arm] and r['interface']==pin(bodies['CANDIDATE_ABI.md']) and r['resources']==pin(bodies['RESOURCE_PLAN.json']) and r['authoring_protocol']==pin(ap_raw) and r['images']=={k:v['images'][k] for k in PROGRAMS} and r['versions']=={k:v['versions'][k] for k in PROGRAMS},'exact program/ABI/resource/environment authorship binding')
        need(type(r['context_id'])is str and 0<len(r['context_id'])<=160 and r['context_id']not in identities and type(r['generation_seed'])is int and 0<=r['generation_seed']<2**64 and all(r[k]is False for k in ('original_or_prepared_numeric_inputs_seen','operator_private_seen','cross_arm_feedback','other_arm_program_seen')) and r['interface_supplied_before_finalization']is True and type(r['prior_exposure_statement'])is str and 0<len(r['prior_exposure_statement'])<=4096,'separate authorship and explicit prior-exposure limits')
        identities.add(r['context_id'])
        vr=capture(r['authoring_view']['path'],r['authoring_view'],META_CAP,budget);view=parse(vr)
        need(view=={'schema':'isttc_authoring_view_v1','task_id':TASK,'arm':arm,'files':authoring_files(b,bodies,arm),'numeric_data_files':0,'private_files':0,'construction_custody_attested_by_root':True},'exact common paper/schema/ABI and B-only author code exposure')
        save(out/'authorship'/(arm+'.json'),raw,budget);save(out/'authorship'/(arm+'-VIEW.json'),vr,budget);records[arm]=pin(raw)
    result={'schema':'isttc_global_four_program_commitment_v1','task_id':TASK,'programs':programs,'authorship':records,'authoring_protocol':pin(ap_raw),'pair':pin(pair_raw),'interface':pin(bodies['CANDIDATE_ABI.md']),'resources':pin(bodies['RESOURCE_PLAN.json']),'data_or_native_phase_started':False,'attestation_is_independent_history_proof':False}
    return result,save(out/'PAIR_COMMITMENT.json',canonical(result),budget)

def closure(r,engine,ctx,source,end):
    need(type(r)is dict and r.get('schema')=='isttc_owned_phase_v1' and r.get('status')=='captured' and r.get('phase')==ctx['role'] and r.get('phase_id')==ctx['phase_id'] and r.get('source')==source and type(r.get('original_deadline'))in (int,float) and r['original_deadline']==end,'same source/phase/original-clock captured receipt')
    need(all(r.get(k)is True for k in ('producer_closed_before_capture','all_native_resources_closed','cli_reaped')) and r.get('qualification_inherited')is False and r.get('numerical_grading_called')is False,'complete native closure and no qualification/grade')
    engine.validate_natural_exit(r['natural_exit']);engine.validate_cli_records(r['command_metadata'])
    prefix=r.get('attempt_prefix');need(type(prefix)is str and re.fullmatch('isttc-[a-f0-9]{24}',prefix),'exact owned attempt prefix')
    rows=r.get('closures');need(type(rows)is list and len(rows)==3 and [(x.get('kind'),x.get('name')) for x in rows]==[('container',prefix+'-'+ctx['role']),('container',prefix+'-holder'),('volume',prefix+'-volume')] and all(x.get('closed')is True and x.get('absence_observed')is True and x.get('creation_outcome_unknown')is False for x in rows),'all three exact owned resources absent')
    need(r.get('source_before')==r.get('source_after') and type(r['source_before'])is dict and r['source_before'].get('manifest')==source,'complete immutable source reauthentication')
    a=r.get('artifacts');need(type(a)is dict and a.get('capture_complete')is True and set(a['files'])==set(engine.OUTPUTS[ctx['role']]),'exact complete stopped artifact inventory')
    for name,cap in engine.OUTPUTS[ctx['role']].items():descriptor(a['files'][name],cap)
    need(type(r.get('elapsed_seconds'))in (int,float) and math.isfinite(r['elapsed_seconds']) and 0<=r['elapsed_seconds']<= (174840),'bounded complete native phase interval')
    return a['files']

class ExecutionBudget:
    def __init__(self,b):self.b=b
    def tick(self):self.b.deadline()
    def read(self,n):self.b.reading(n)
    def write(self,n):self.b.writing(n)


def route_rows(b,ctx,repo):
    rows=b['reference_assets'] if ctx['role']=='reference' else b['candidate_assets'][ctx['arm']]
    return [{**r,'source':str(repo/relative(r['source']))} for r in rows]


def run_sequence(operations):
    operations.commit_all_four_before_data()
    records=[]
    for ctx in contexts():records.append(operations.phase(ctx))
    return operations.complete(records)


def validate_artifact(csv_body,meta_body,role):
    need(len(csv_body)<=100000000 and len(meta_body)<=20000,'original two-file caps')
    values,meta=validation.validate(csv_body,meta_body)
    expected='improvement' if role=='improvement' else 'reproduction'
    need(meta['condition']==expected,'original exact selected endpoint')
    need(set(values)==set(validation.BASE+(validation.EXTRA if role=='improvement' else ())) and all(len(x)==100000 for x in values.values()),'full100000 original method/unit support')
    return {'condition':expected,'units':100000,'required_rows':100000*len(values),'methods':list(values),'failed_fit_counts':{k:sum(x is None for x in v) for k,v in values.items()},'numeric_score_computed':False}


class Operations:
    def __init__(self,v,b,bodies,out,budget,origin,engine):
        self.v,self.b,self.bodies,self.out,self.budget,self.origin,self.engine=v,b,bodies,out,budget,origin,engine
        self.commit=None;self.commit_pin=None;self.artifacts={};self.support={}
    def commit_all_four_before_data(self):
        need(self.commit is None,'single global commitment')
        self.commit,self.commit_pin=global_commit(self.v,self.b,self.bodies,self.out,self.budget)
    def phase(self,ctx):
        need(self.commit is not None and ctx==contexts()[len(self.artifacts)],'global freeze and exact complete phase order')
        v,b,budget,engine=self.v,self.b,self.budget,self.engine;role=ctx['role'];arm=ctx['arm'];root=self.out/'phases'/ctx['phase_id'];root.mkdir(mode=0o700,parents=True)
        view=staging.View(root/'input',route_rows(b,ctx,ordinary(v['repo'])),{'schema':'isttc_complete_view_v1','task_id':TASK,'role':role,'arm':arm,'versions':v['versions'][role],'coverage':COVERAGE,'original_work_deadline':self.origin+WORK},budget)
        req={'schema':'isttc_owned_phase_request_v1','phase_id':ctx['phase_id'],'image':v['images'][role],'source':v['source_manifest'],'expected_files':sorted(engine.OUTPUTS[role]),'entry':role+'_entry.py','entry_support':engine.SUPPORT[role],**engine.TIMES[role]}
        reqpin=save(root/'REQUEST.json',canonical(req),budget);os.chmod(root/'REQUEST.json',0o444);data=view.handoff();program=None
        if arm is not None:
            program=self.out/'programs'/arm/(role+'.py');capture(program,self.commit['programs'][arm][role],PROGRAMS[role],budget,retain=False)
        output=root/'closed';output.mkdir(mode=0o700);budget.producer_writes(sum(engine.OUTPUTS[role].values())*(2 if role=='reference' else 1))
        def publish(name,value):save(root/'journal'/(str(relative(name))+'.json'),canonical(value),budget)
        receipt=engine.execute(ExecutionBudget(budget),v['docker'],phase=role,request=req,program=program,readonly_mounts={'/input':data,'/request.json':root/'REQUEST.json'},output_dir=output,source_dir=HERE,original_deadline=self.origin+WORK,publish=publish)
        check=lambda r:closure(r,engine,ctx,v['source_manifest'],self.origin+WORK)
        artifacts=check(receipt)
        if program is not None:capture(program,self.commit['programs'][arm][role],PROGRAMS[role],budget,retain=False)
        csv_body=capture(output/'artifacts/estimates.csv',artifacts['estimates.csv'],100000000,budget)
        meta_body=capture(output/'artifacts/methods.json',artifacts['methods.json'],20000,budget)
        support=validate_artifact(csv_body,meta_body,role)
        # Store the exact two-file native capture itself; no second CSV copy.
        self.artifacts[ctx['phase_id']]={name:{'path':f'phases/{ctx["phase_id"]}/closed/artifacts/{name}',**d} for name,d in artifacts.items()}
        self.support[ctx['phase_id']]=support
        view.retire_after_closed_execution(receipt,check)
        desc=save(root/'ACCEPTED_PHASE.json',canonical(receipt),budget)
        return {'context':ctx,'request':reqpin,'receipt':{'path':str((root/'ACCEPTED_PHASE.json').relative_to(self.out)),**desc},'input_retired_after_exact_closure':True}
    def complete(self,records):
        need([r['context'] for r in records]==contexts() and list(self.artifacts)==[r['phase_id'] for r in contexts()],'all5 complete original phases')
        baseline_ctx=contexts()[-1];art=self.artifacts[baseline_ctx['phase_id']]
        evidence={'schema':'isttc_fixed_native_execution_evidence_v1','source':self.v['source_manifest'],'context':baseline_ctx,'original_receipt':records[-1]['receipt'],'request':records[-1]['request'],'baseline_implementation':pin(self.bodies['baseline/baseline.py']),'full_inputs':self.b['input_binding'],'image':self.v['images']['reference'],'versions':self.v['versions']['reference'],'support':self.support[baseline_ctx['phase_id']],'runtime_qualified':False,'private_grade_called':False}
        ep=save(self.out/'operator-baseline/execution_evidence.json',canonical(evidence),self.budget)
        policy={'schema':'isttc_operator_baseline_artifacts_v1','task_id':TASK,'unit_count':100000,'source_commit':self.b['source_commit'],'recipe':self.b['baseline_recipe'],'artifacts':{n:{k:d[k] for k in ('bytes','sha256')} for n,d in art.items()},'execution_evidence':ep}
        pp=save(self.out/'operator-baseline/POLICY.json',canonical(policy),self.budget)
        # Existing comparator expects a separate three-file baseline directory.
        # Explicit deferred assembly recipe keeps originals immutable and no grade occurs here.
        grade={'schema':'isttc_deferred_private_grade_join_v1','operator_policy':{'path':'operator-baseline/POLICY.json',**pp},'baseline_artifacts':art,'execution_evidence':{'path':'operator-baseline/execution_evidence.json',**ep},'candidate_artifacts':{r['phase_id']:self.artifacts[r['phase_id']] for r in contexts()[:-1]},'requires_external_whole_observer_success':True,'requires_independent_operator_policy_selection':True,'assembly_required_before_existing_comparator':True,'automatic_grading':False}
        gp=save(self.out/'PRIVATE_GRADE_JOIN.json',canonical(grade),self.budget)
        result={'schema':'isttc_complete_paired_collection_v1','task_id':TASK,'source_manifest':self.v['source_manifest'],'coverage':COVERAGE,'contexts':contexts(),'phase_receipts':records,'commitment':self.commit_pin,'artifacts':self.artifacts,'support':self.support,'baseline_policy':pp,'baseline_evidence':ep,'private_grade_join':gp,'original_origin':self.origin,'work_end':self.origin+WORK,'private_grade_called':False,'runtime_qualified':False,'scientific_qualification':False,'full_paper_reproduction':False,'automatic_retry_authorized':False,'forced_stop_independent_host_and_daemon_state':'unknown','managed_read_bytes':self.budget.read,'managed_write_bytes_before_collection':self.budget.written,'retained_charge_before_collection':self.budget.retained_charge}
        save(self.out/'COLLECTION.json',canonical(result),self.budget);return result


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--origin',required=True,type=float);a=p.parse_args(argv);primary=None
    try:
        need(math.isfinite(a.origin) and 0<=BOOT-a.origin<120,'same original origin including startup')
        remaining=a.origin+PUBLICATION-time.monotonic();need(remaining>0,'original remaining publication clock');signal.setitimer(signal.ITIMER_REAL,remaining)
        q=ordinary(a.selection);raw=capture(q,{'bytes':q.stat().st_size,'sha256':a.selection_sha256},META_CAP);v=selected(parse(raw))
        out=ordinary(a.output);need(not out.exists(),'fresh controller root');out.mkdir(mode=0o700)
        budget=Budget(out,a.origin+WORK,read_cap=64*1024**3,write_cap=16*1024**3,retained_cap=3*1024**3,other_future=v['other_future_bytes']+16*1024**2)
        mraw=capture(HERE/'SOURCE_MANIFEST.json',v['source_manifest'],262144,budget);m=parse(mraw)
        need(m['task_id']==TASK and m['source_only']is True and type(m['files'])is dict and 1<=len(m['files'])<=128 and sum(d['bytes'] for d in m['files'].values())<=4*1024**2,'bounded complete source identity')
        bodies={n:capture(HERE/relative(n),d,META_CAP,budget,allow_empty=True) for n,d in m['files'].items()}
        b=bindings(parse(bodies['BINDINGS.json']));need(all(x==b['versions'] for x in v['versions'].values()),'exact unchanged dependency versions')
        engine=load('isttc_engine',HERE/'engine/native.py');run_sequence(Operations(v,b,bodies,out,budget,a.origin,engine))
        need(time.monotonic()<a.origin+PUBLICATION,'original publication cutoff');return 0
    except BaseException as error:primary=error;raise
    finally:
        if CLOCK_OWNED:cleanup_clock(primary)
if __name__=='__main__':raise SystemExit(main())
