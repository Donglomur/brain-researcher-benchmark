"""Complete language building blocks pair; private grading remains separate."""
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
import argparse,importlib.util,math,os,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
from common import *
from contract import *
from authoring import global_commit,PROGRAMS,ARMS
import staging,host,journal,artifact_admission
HERE=Path(__file__).absolute().parent
ENTRY_ORIGIN=None


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def selected(v):
    keys={'schema','task_id','operation_selected','operation_id','source_manifest','repo','images','versions','host_python','host_binary','host_environment','docker','pair','archives','other_future_bytes','retained_cap','runtime_qualified','scientific_qualification','full_paper_reproduction','exclusive_operator_custody','native_linux_host','physical_host_capacity_reviewed','generic_image_exposure_reviewed'}
    need(type(v)is dict and set(v)==keys and v['schema']=='language_building_blocks_complete_program_operation_v1' and v['task_id']==TASK and v['operation_selected']is True,'exact external operation selection')
    need(all(v[k]is False for k in('runtime_qualified','scientific_qualification','full_paper_reproduction')),'no inherited scientific/program qualification')
    need(all(v[k]is True for k in('exclusive_operator_custody','native_linux_host','physical_host_capacity_reviewed','generic_image_exposure_reviewed')),'external host/custody/image review authority')
    need(type(v['operation_id'])is str and re.fullmatch('[a-z0-9-]{1,64}',v['operation_id']),'finite unique operation identity')
    need(type(v['other_future_bytes'])is int and v['other_future_bytes']>=0 and type(v['retained_cap'])is int and RETAINED_REQUIRED<=v['retained_cap']<=16*1024**3,'complete declared retention ceiling, never a subset')
    roles={'native','strict','reference_native','reference_strict'}
    need(type(v['images'])is dict and set(v['images'])==roles and all(type(x)is str and re.fullmatch('sha256:[a-f0-9]{64}',x)for x in v['images'].values()) and len(set(v['images'].values()))==1,'same immutable generic image across roles')
    need(type(v['versions'])is dict and set(v['versions'])==roles,'all original dependency profiles')
    need(type(v['host_python'])is str and re.fullmatch(r'3\.11\.[0-9]+',v['host_python']),'explicit trusted Python3.11 version')
    for n in('pair','source_manifest','host_environment'):descriptor(v[n],1048576)
    need(type(v['docker'])is dict and set(v['docker'])=={'binary','socket'},'exact local engine endpoint')
    ordinary(v['repo']);ordinary(v['host_binary']);return v


def closure(r,engine,ctx,source,end):
    need(type(r)is dict and r.get('schema')=='langbuild_owned_phase_v1' and r.get('status')=='captured' and r.get('phase')==ctx['role'] and r.get('phase_id')==ctx['phase_id'] and r.get('mode')==ctx['mode'] and r.get('episode')==ctx['episode'] and r.get('source')==source and r.get('original_deadline')==end,'exact original scientific context/source/clock receipt')
    need(all(r.get(k)is True for k in('producer_closed_before_capture','all_native_resources_closed','cli_reaped')) and r.get('qualification_inherited')is False and r.get('numerical_grading_called')is False,'complete original closure; no grading')
    engine.validate_natural_exit(r['natural_exit']);engine.validate_cli_records(r['command_metadata'])
    prefix=r['attempt_prefix'];need(type(prefix)is str and re.fullmatch('langbuild-[a-f0-9]{24}',prefix),'exact owned attempt identifier')
    rows=r['closures'];need(len(rows)==3 and [(x['kind'],x['name'])for x in rows]==[('container',prefix+'-'+ctx['role']),('container',prefix+'-holder'),('volume',prefix+'-volume')] and all(x['closed']is True and x['absence_observed']is True and x['creation_outcome_unknown']is False for x in rows),'all three original resources absent')
    need(r['source_before']==r['source_after'] and r['source_before']['manifest']==source,'same full immutable source closure')
    expected=engine.expected_outputs(ctx['role'],ctx['episode']);need(r['expected_files']==expected and r['artifacts']['capture_complete']is True and set(r['artifacts']['files'])==set(expected),'complete original output files')
    for n,cap in expected.items():descriptor(r['artifacts']['files'][n],cap)
    need(type(r['elapsed_seconds'])in(int,float) and math.isfinite(r['elapsed_seconds']) and 0<=r['elapsed_seconds']<=sum(engine.TIMES[ctx['role']].values()),'finite full phase interval')
    return r['artifacts']['files']


class ExecutionBudget:
    def __init__(self,b):self.b=b
    def tick(self):self.b.deadline()
    def read(self,n):self.b.reading(n)
    def write(self,n):self.b.writing(n)


def run_sequence(ops):
    ops.commit_all_four_before_data();ops.admit_complete_inputs()
    rows=[]
    for ctx in contexts():rows.append(ops.phase(ctx))
    return ops.complete(rows)


class Operations:
    def __init__(self,v,b,bodies,out,budget,origin,engine,score_loader=artifact_admission.original):
        self.v,self.b,self.bodies,self.out,self.budget,self.origin,self.engine=v,b,bodies,out,budget,origin,engine
        self.score_loader=score_loader;self.commit=self.commit_pin=self.design=self.design_pin=None
        self.prepared_files={};self.host_records=[];self.artifacts={};self.case=None;self.case_report=None;self.case_binding=None;self.case_root=None
        self.bindings={};self.native={};self.prediction={'A':{},'B':{}};self.seen_rows={s:set()for s in SESSIONS}
    def commit_all_four_before_data(self):
        need(self.commit is None,'single complete global commitment')
        self.commit,self.commit_pin=global_commit(self.v,self.b,self.bodies,self.out,self.budget)
    def host_request(self,action,root,extra,seconds):
        mkdirs(root,self.budget);request={'schema':'language_trusted_host_request_v1','action':action,'source_manifest':self.v['source_manifest'],'environment':self.v['host_environment'],**extra}
        log=journal.Journal(root/'HOST.jsonl',self.budget,host_only=True)
        r,proof=host.run(self.engine,self.v['host_binary'],HERE,request,root/'HOST_REQUEST.json',root/'HOST_RESULT.json',self.budget,log,seconds)
        proof['journal']={'path':str((root/'HOST.jsonl').relative_to(self.out)),**log.finish()}
        proof['report']['path']=str((root/'HOST_RESULT.json').relative_to(self.out));proof['request_path']=str((root/'HOST_REQUEST.json').relative_to(self.out))
        self.host_records.append(proof);return r
    def admit_complete_inputs(self):
        need(self.commit is not None and self.design is None,'all four programs before original data')
        archive_root=staging.originals(self.v['archives'],self.b,self.budget)
        root=self.out/'preparation';mkdirs(root,self.budget)
        # Source-defined finite producer writes/allocation, before trusted child.
        selected_credit=self.budget.generated_tree(SELECTED_CAP,183)
        self.budget.generated_tree(PREPARED_CAP,197);self.budget.reading(8*1024**3)
        report=self.host_request('prepare',root,{'archives':str(archive_root),'output':str(root),'acquisition_pin':pin(self.bodies['vendor/operator/ACQUISITION.json'])},86400)
        self.prepared_root=root/'prepared';self.prepared_files=report['prepared']
        self.design,self.design_pin=staging.prepared(self.prepared_root,report,self.b,self.budget)
        selected=report['selected'];names={r['member']for r in self.b['acquisition']['selected_members']}|{'transcription/cleaned/'+s+'.csv'for s in SESSIONS}|{'SELECTION.json'}
        need(set(selected)==names,'complete168Npy+14timings source selection')
        need(self.design['source_selection']==selected['SELECTION.json'],'same original complete source selection')
        save(root/'SOURCE_SELECTION_IDENTITY.json',capture(root/'selected/SELECTION.json',selected['SELECTION.json'],1048576,self.budget),self.budget)
        staging.retire_owned(root/'selected',selected,self.budget,selected_credit,True)
        save(self.out/'PREPARATION_BINDING.json',canonical({'prepared_files':self.prepared_files,'design':self.design_pin,'complete_originals':self.v['archives'],'selected_retired_after_natural_close':True}),self.budget)
    def begin_episode(self,eid):
        need(self.case is None and eid==EPISODES[len(self.bindings)],'complete original episode order')
        root=self.out/'episodes'/eid;mkdirs(root,self.budget)
        self.case_public_credit=self.budget.generated_tree(EPISODE_PUBLIC_CAP,3)
        self.case_private_credit=self.budget.generated_tree(EPISODE_PRIVATE_CAP,2)
        self.budget.reading(4*1024**3)
        report=self.host_request('episode',root,{'prepared':str(self.prepared_root),'design':str(self.prepared_root/'DESIGN.json'),'episode':eid,'output':str(root/'staged'),'nonce':self.v['operation_id']+':'+self.design_pin['sha256']},1200)
        self.case_root=root/'staged';self.case_report=report
        self.case,self.case_binding=staging.episode(self.case_root,report,eid,self.design_pin,self.b,self.budget)
        target_bytes=sum(x['target']['bytes']for x in self.bindings.values())+report['files']['operator/target.npz']['bytes']
        need(target_bytes<=PRIVATE_TARGET_TOTAL_CAP,'full source-derived private target payload ceiling')
        s=eid.rsplit('_f',1)[0];rows=self.case_binding['source_rows'];need(not self.seen_rows[s].intersection(rows),'source-staged pooled query rows appear once');self.seen_rows[s].update(rows)
    def phase(self,ctx):
        need(self.design is not None and ctx==contexts()[len(self.artifacts)],'full original preparation and213 context order')
        if ctx['episode'] is not None:
            if self.case is None:self.begin_episode(ctx['episode'])
            need(self.case['id']==ctx['episode'],'same staged case for independent A/B/operator')
        root=self.out/'phases'/ctx['phase_id'];mkdirs(root,self.budget);v=self.v;engine=self.engine
        program=None;program_pin=None
        if ctx['arm'] is not None:
            program=self.out/'programs'/ctx['arm']/(ctx['purpose']+'.py');program_pin=self.commit['programs'][ctx['arm']][ctx['purpose']]
            capture(program,program_pin,PROGRAMS[ctx['purpose']],self.budget,retain=False)
        metadata={'schema':'language_program_view_v1','task_id':TASK,'phase_id':ctx['phase_id'],'mode':ctx['mode'],'episode':ctx['episode'],'role':ctx['role'],'arm':ctx['arm'],'versions':v['versions'][ctx['role']],'program':program_pin,'source_manifest':v['source_manifest'],'original_work_deadline':self.origin+WORK}
        view=staging.materialize(root/'input',v['repo'],self.b,self.bodies,ctx,self.prepared_root,self.prepared_files,self.case_root,self.case_report,metadata,self.budget)
        expected=engine.expected_outputs(ctx['role'],ctx['episode']);req={'schema':'langbuild_owned_phase_request_v1','phase_id':ctx['phase_id'],'mode':ctx['mode'],'episode':ctx['episode'],'image':v['images'][ctx['role']],'source':v['source_manifest'],'expected_files':expected,'entry':engine.ENTRIES[ctx['role']],'entry_support':engine.SUPPORT[ctx['role']],**engine.TIMES[ctx['role']]}
        request=save(root/'REQUEST.json',canonical(req),self.budget);os.chmod(root/'REQUEST.json',0o444)
        closed=root/'closed';mkdirs(closed,self.budget);self.budget.producer_writes(sum(expected.values()))
        log=journal.Journal(root/'JOURNAL.jsonl',self.budget)
        receipt=engine.execute(ExecutionBudget(self.budget),v['docker'],phase=ctx['role'],request=req,program=program,readonly_mounts={'/input':view.handoff(),'/request.json':root/'REQUEST.json'},output_dir=closed,source_dir=HERE,original_deadline=self.origin+WORK,publish=log.append)
        check=lambda r:closure(r,engine,ctx,v['source_manifest'],self.origin+WORK)
        files=check(receipt);logpin=log.finish()
        if program is not None:capture(program,program_pin,PROGRAMS[ctx['purpose']],self.budget,retain=False)
        view.retire_after_closed_execution(receipt,check)
        rp=save(root/'ACCEPTED_PHASE.json',canonical(receipt),self.budget);self.artifacts[ctx['phase_id']]={name:{'path':f'phases/{ctx["phase_id"]}/closed/artifacts/{name}',**d}for name,d in files.items()}
        if ctx['mode']=='native':self.native[ctx['arm']or'operator']={'root':f'phases/{ctx["phase_id"]}/closed/artifacts','files':files}
        elif ctx['arm'] is not None:
            d=self.artifacts[ctx['phase_id']]['prediction.npz'];self.prediction[ctx['arm']][ctx['episode']]={**d,'case_sha256':pin(canonical(self.case))['sha256']}
            need(sum(x['bytes']for x in self.prediction[ctx['arm']].values())<=536870912,'original complete candidate panel cap, no excluded cases')
        else:self.finish_episode(ctx)
        return {'context':ctx,'request':request,'journal':{'path':f'phases/{ctx["phase_id"]}/JOURNAL.jsonl',**logpin},'receipt':{'path':f'phases/{ctx["phase_id"]}/ACCEPTED_PHASE.json',**rp},'input_retired_after_exact_closure':True,'original_output_bytes_retained':True}
    def finish_episode(self,ctx):
        eid=ctx['episode'];files=self.artifacts[ctx['phase_id']]
        meta=parse(capture(self.out/files['baselines.npz.metadata.json']['path'],files['baselines.npz.metadata.json'],100000,self.budget))
        need(meta['case_sha256']==pin(canonical(self.case))['sha256'] and descriptor(meta['baselines'],33554432)==descriptor(files['baselines.npz'],33554432) and set(meta['selected'])=={'context','lexical','random_token','clock'},'all four independent source-produced baseline identities')
        target=self.case_report['files']['operator/target.npz'];descriptor(target,33554432)
        self.bindings[eid]={'case':self.case,'source_rows':self.case_binding['source_rows'],'target':{'path':f'episodes/{eid}/staged/operator/target.npz',**target},'baselines':files['baselines.npz']}
        # Only the public ephemeral packet retires. Target/binding stay private.
        candidate_files={n.split('/',1)[1]:d for n,d in self.case_report['files'].items()if n.startswith('candidate/')}
        staging.retire_owned(self.case_root/'candidate',candidate_files,self.budget,self.case_public_credit,True)
        # The private reservation stays charged; after full generated-tree proof,
        # reduce its upper bound to its exact two retained files plus block margin.
        retained=sum(d['bytes']for n,d in self.case_report['files'].items()if n.startswith('operator/'))+2*18*4096
        need(retained<=self.case_private_credit,'exact retained private allocation fits prior reservation')
        self.budget.settle_closed_generated_reservation(self.case_private_credit,retained)
        self.case=self.case_report=self.case_binding=self.case_root=None
    def complete(self,rows):
        need([x['context']for x in rows]==contexts() and len(self.artifacts)==213 and list(self.bindings)==list(EPISODES) and self.case is None,'all213 original phases and70complete episode joins')
        b={'schema':'language_episodes_v1','design_sha256':self.design_pin['sha256'],'episodes':self.bindings}
        bp=save(self.out/'OPERATOR_BINDINGS.json',canonical(b),self.budget,33554432)
        panels={a:artifact_admission.prediction_panel(self.prediction[a],self.design_pin['sha256'],self.b['protocol_sha256'])for a in ARMS}
        panel_pins={a:save(self.out/'panels'/(a+'.json'),canonical(panels[a]),self.budget)for a in ARMS}
        self.enable_qualified_numeric_admission()
        score=self.score_loader(HERE)
        admission=artifact_admission.admit_all(self.out,self.native,panels,b,self.design_pin['sha256'],self.b['protocol_sha256'],self.budget,score)
        result={'schema':'language_building_blocks_complete_paired_collection_v1','task_id':TASK,'source_manifest':self.v['source_manifest'],'coverage':COVERAGE,'contexts':contexts(),'phase_count':213,'phase_receipts':rows,'host_receipts':self.host_records,'commitment':self.commit_pin,'design':self.design_pin,'protocol_sha256':self.b['protocol_sha256'],'preparation':pin(canonical({'prepared_files':self.prepared_files,'design':self.design_pin,'complete_originals':self.v['archives'],'selected_retired_after_natural_close':True})),'artifacts':self.artifacts,'native_panels':self.native,'prediction_panels':panel_pins,'operator_bindings':bp,'full_admission':admission,'original_origin':self.origin,'work_end':self.origin+WORK,'private_grade_called':False,'runtime_qualified':False,'scientific_qualification':False,'full_paper_reproduction':False,'automatic_retry_authorized':False,'forced_stop_independent_host_and_daemon_state':'unknown','managed_read_bytes':self.budget.read,'managed_write_bytes_before_collection':self.budget.written,'retained_charge_before_collection':self.budget.retained_charge}
        save(self.out/'COLLECTION.json',canonical(result),self.budget);return result
    def enable_qualified_numeric_admission(self):
        e=parse(capture(self.v['host_environment']['path'],self.v['host_environment'],1048576,self.budget))
        need(e['schema']=='language_qualified_host_environment_v1' and e['qualified']is True and e['covers_interpreter_native_libraries_and_site_packages']is True and e['source_manifest']==self.v['source_manifest'] and e['python']==sys.version.split()[0] and e['versions']==self.b['versions'],'independent source-bound environment authority before numerical imports')
        capture(e['qualification_receipt']['path'],e['qualification_receipt'],1048576,self.budget,retain=False)
        site=ordinary(e['site_packages']);need(site.is_dir(),'one exact qualified dependency directory');self.budget.deadline();sys.path.append(str(site))
        from importlib.metadata import version
        for k,v in self.b['versions'].items():need(version(k)==v,'same exact numerical environment')


def main(argv=None):
    global ENTRY_ORIGIN
    p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args(argv);primary=None
    try:
        need(math.isfinite(a.origin) and 0<=BOOT-a.origin<120,'one original startup origin');ENTRY_ORIGIN=a.origin;left=a.origin+PUBLICATION-time.monotonic();need(left>0,'remaining original publication clock');signal.setitimer(signal.ITIMER_REAL,left)
        raw,observed=observed_capture(a.selection,1048576);need(observed['sha256']==a.selection_sha256,'exact selected operation');v=selected(parse(raw))
        need(sys.version.split()[0]==v['host_python'],'exact trusted host interpreter')
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(17179869184,17179869184)) # full admission controller, independently unqualified
        out=ordinary(a.output);need(not out.exists() and out.parent.is_dir(),'fresh owned controller root');mkdirs(out)
        budget=Budget(out,a.origin+WORK,read_cap=READ_CAP,write_cap=WRITE_CAP,retained_cap=v['retained_cap'],other_future=v['other_future_bytes']+OBSERVER_RETAINED)
        m=parse(capture(HERE/'SOURCE_MANIFEST.json',v['source_manifest'],262144,budget));need(m['task_id']==TASK and m['source_only']is True and 1<=len(m['files'])<=128 and sum(d['bytes']for d in m['files'].values())<=4194304,'full finite runtime source closure')
        bodies={n:capture(HERE/relative(n),d,1048576,budget,allow_empty=True)for n,d in m['files'].items()};b=parse(bodies['BINDINGS.json'])
        need(b['task_id']==TASK and b['coverage']==COVERAGE and tuple(x['id']for x in b['protocol']['sessions'])==SESSIONS and sum(x['units']for x in b['protocol']['sessions'])==567,'exact full scientific source scope')
        need(all(x=={'python':v['host_python'],**b['versions']}for x in v['versions'].values()),'same source dependency profile across roles')
        engine=load('language_building_blocks_engine',HERE/'engine/native.py');run_sequence(Operations(v,b,bodies,out,budget,a.origin,engine));need(time.monotonic()<a.origin+PUBLICATION,'original publication cutoff');return 0
    except BaseException as e:primary=e;raise
    finally:
        if CLOCK_OWNED:cleanup_clock(primary)
if __name__=='__main__':
    result=main()
    need(ENTRY_ORIGIN is not None and time.monotonic()<ENTRY_ORIGIN+PUBLICATION,'post-cleanup exit before original publication cutoff')
    raise SystemExit(result)
