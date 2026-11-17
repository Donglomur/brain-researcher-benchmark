"""Complete85phase collection. Called only from captured-source bootstrap.

Authentic execution remains unqualified/paused. No fitting, grading, daemon calls,
or data capture occurs on import. Every context gets a fresh process and storage.
"""
import importlib.util
import math
import os
from pathlib import Path
import signal
import sys
import time
from common import Budget, canonical, capture, descriptor, mkdirs, need, ordinary, parse, pin, relative, save
import journal
import outputs
import protocol
import staging

READ_CAP=64*1024**3
WRITE_CAP=16*1024**3
RETAINED_CAP=6*1024**3
PROGRAM_CAP=8*1024**2


def selected(v):
    fields={'schema','task_id','condition','repo','source_manifest','image','docker','producer_seconds','programs','authorship','other_future_bytes','retained_cap','scientific_execution_authorized','exclusive_custody','native_linux_host','generic_image_no_data_or_pretraining_assets'}
    need(type(v)is dict and set(v)==fields and v['schema']=='visual_alpha_program_selection_v1' and v['task_id']==protocol.TASK and v['condition']==protocol.CONDITION,'exact explicit operation selection')
    for field in ('scientific_execution_authorized','exclusive_custody','native_linux_host','generic_image_no_data_or_pretraining_assets'):need(v[field]is True,'separate explicit root authority/custody prerequisite')
    descriptor(v['source_manifest'],262144)
    need(type(v['image'])is str and v['image'].startswith('sha256:') and len(v['image'])==71,'immutable existing image')
    need(type(v['docker'])is dict and set(v['docker'])=={'binary','socket'},'exact existing local engine endpoint')
    for val in (v['repo'],v['docker']['binary'],v['docker']['socket']):ordinary(val)
    need(type(v['producer_seconds'])is dict and set(v['producer_seconds'])=={'spectral','spatial','corrected','reference'},'all finite explicit phase budgets required; no defaults')
    need(all(type(n)is int and 1<=n<=2147483647 for n in v['producer_seconds'].values()),'finite positive operator scientific ceilings')
    need(v['producer_seconds']['corrected']==v['producer_seconds']['reference'],'matched corrected candidate/operator ceilings')
    need(type(v['other_future_bytes'])is int and v['other_future_bytes']>=0 and type(v['retained_cap'])is int and v['retained_cap']==RETAINED_CAP,'fixed full-output retention plus OTHER')
    need(type(v['programs'])is dict and set(v['programs'])=={'A','B'} and type(v['authorship'])is dict and set(v['authorship'])=={'A','B'},'all six globally authored programs')
    return v


def authoring_view(b,arm,purpose):
    code=b['spectral_B_code'] if purpose=='spectral_reproduction' else b['spatial_B_code']
    rows=b['common']+(code if arm=='B' else [])
    # This condition supplies schemas and source identity descriptors during authoring,
    # but no numeric input, saved fit, target or other program's state.
    return {'condition':protocol.CONDITION,'purpose':purpose,'arm':arm,'files':[{k:r[k] for k in ('source','bytes','sha256')} for r in rows],'numeric_or_target_exposure':False,'interface':'ABI.md'}


def global_commit(v,b,out,budget):
    commits={};contexts=[];settings={}
    for arm in ('A','B'):
        need(set(v['programs'][arm])==set(protocol.PURPOSES) and set(v['authorship'][arm])==set(protocol.PURPOSES),'exact three independent purposes per arm')
        commits[arm]={}
        for purpose in protocol.PURPOSES:
            r=v['programs'][arm][purpose];need(type(r)is dict and set(r)=={'path','bytes','sha256'},'exact independent program binding')
            raw=capture(ordinary(r['path']),r,PROGRAM_CAP,budget)
            a=v['authorship'][arm][purpose]
            keys={'context_id','model_revision','token_budget','wall_seconds','revision_budget','seed','authoring_view','no_numeric_or_saved_fit_exposure','no_cross_context_state','program_sha256'}
            need(type(a)is dict and set(a)==keys and a['authoring_view']==authoring_view(b,arm,purpose),'exact declared authoring view')
            need(a['no_numeric_or_saved_fit_exposure']is True and a['no_cross_context_state']is True and a['program_sha256']==r['sha256'],'independent no-data source commitment')
            need(type(a['context_id'])is str and a['context_id'] and a['context_id'] not in contexts,'six distinct author contexts');contexts.append(a['context_id'])
            need(type(a['model_revision'])is str and a['model_revision'],'frozen candidate model revision')
            need(all(type(a[k])is int and a[k]>=1 for k in ('token_budget','wall_seconds','revision_budget')) and type(a['seed'])is int,'explicit finite matched authoring protocol')
            match={k:a[k] for k in ('model_revision','token_budget','wall_seconds','revision_budget','seed')}
            if purpose in settings:need(settings[purpose]==match,'A/B authoring resources matched within purpose')
            else:settings[purpose]=match
            commits[arm][purpose]=save(out/'programs'/arm/(purpose+'.py'),raw,budget,cap=PROGRAM_CAP)
            os.chmod(out/'programs'/arm/(purpose+'.py'),0o444)
    document={'schema':'visual_alpha_six_programs_global_commitment_v1','programs':commits,'authorship':v['authorship'],'all6_frozen_before_any_numeric_input':True,'attestation_does_not_prove_historical_blindness':True}
    return document,save(out/'GLOBAL_COMMITMENT.json',canonical(document),budget)


class ExecutionBudget:
    def __init__(self,b):self.b=b
    def read(self,n):self.b.reading(n)
    def write(self,n):self.b.writing(n)
    def tick(self):self.b.deadline()


def closure(r,engine,ctx,source,end):
    need(type(r)is dict and r['schema']=='visualalpha_owned_phase_v1' and r['phase_id']==ctx['phase_id'] and r['phase']==ctx['mode'] and r['participant']==ctx['participant'] and r['fit_role']==ctx['fit_role'],'exact context receipt')
    need(r['status']=='captured' and r['source']==source and r['source_before']==r['source_after'] and r['source_before']['manifest']==source,'full source custody before/after')
    engine.validate_natural_exit(r['natural_exit']);engine.validate_cli_records(r['command_metadata'])
    need(r['producer_closed_before_capture']is True and r['all_native_resources_closed']is True and r['cli_reaped']is True and len(r['closures'])==3 and all(x['closed']is True for x in r['closures']),'all owned native resources and CLI groups closed')
    need(type(r['original_deadline'])in (int,float) and r['original_deadline']==end and r['phase_end']<=end and r['started']+r['elapsed_seconds']<r['phase_end'],'original phase and whole clocks')
    a=r['artifacts'];need(a['capture_complete']is True and set(a['files'])==set(engine.expected_outputs(ctx['mode'],ctx['participant'])),'complete stopped artifact capture')
    return a['files']


def run_sequence(ops):
    ops.commit_all_six_before_data()
    ops.admit_complete_inputs()
    records=[ops.phase(ctx) for ctx in protocol.phases()]
    return ops.complete(records)


class Operations:
    def __init__(self,v,b,out,budget,origin,end,source_dir,engine):
        self.v,self.b,self.out,self.budget=v,b,out,budget
        self.origin,self.end,self.source_dir,self.engine=origin,end,source_dir,engine
        self.commit=self.design=None;self.artifacts={};self.documents={}
    def commit_all_six_before_data(self):
        need(self.commit is None,'single source commitment');self.commit,self.commit_pin=global_commit(self.v,self.b,self.out,self.budget)
    def admit_complete_inputs(self):
        need(self.commit is not None and self.design is None,'data only after six-program freeze')
        self.design=staging.admit(ordinary(self.v['repo']),self.b,self.budget)
    def phase(self,ctx):
        need(self.design is not None and ctx==protocol.phases()[len(self.artifacts)],'exact complete85phase sequence')
        mode=ctx['mode'];root=self.out/'phases'/ctx['phase_id'];mkdirs(root,self.budget)
        view=staging.materialize(root/'input',ordinary(self.v['repo']),self.b,self.design,{**ctx,'original_work_deadline':self.end},self.budget)
        req={'schema':'visualalpha_owned_phase_request_v1','phase_id':ctx['phase_id'],'mode':mode,'participant':ctx['participant'],'fit_role':ctx['fit_role'],'image':self.v['image'],'source':self.v['source_manifest'],'expected_files':self.engine.expected_outputs(mode,ctx['participant']),'entry':self.engine.ENTRIES[mode],'entry_support':self.engine.SUPPORT[mode],**self.engine.TIMES[mode],'producer_seconds':self.v['producer_seconds'][mode]}
        reqpin=save(root/'REQUEST.json',canonical(req),self.budget);os.chmod(root/'REQUEST.json',0o444)
        program=None
        if ctx['arm']:
            program=self.out/'programs'/ctx['arm']/(ctx['purpose']+'.py');capture(program,self.commit['programs'][ctx['arm']][ctx['purpose']],PROGRAM_CAP,self.budget,retain=False)
        log=journal.Journal(root/'JOURNAL.jsonl',self.budget);closed=root/'closed';mkdirs(closed,self.budget)
        self.budget.producer_writes(sum(req['expected_files'].values()))
        receipt=self.engine.execute(ExecutionBudget(self.budget),self.v['docker'],phase=mode,request=req,program=program,readonly_mounts={'/input':view.handoff(),'/request.json':root/'REQUEST.json'},output_dir=closed,source_dir=self.source_dir,original_deadline=self.end,publish=log.append)
        check=lambda r:closure(r,self.engine,ctx,self.v['source_manifest'],self.end)
        pins=check(receipt);logpin=log.finish()
        if program is not None:capture(program,self.commit['programs'][ctx['arm']][ctx['purpose']],PROGRAM_CAP,self.budget,retain=False)
        raw=capture(closed/'artifacts/submission.json',pins['submission.json'],outputs.CAP,self.budget)
        if mode=='spectral':doc=outputs.spectral(raw,self.design['spectral_rows'],self.design['spectral_sha'])
        else:doc=outputs.spatial(raw,self.design['parameter_rows'],self.design['parameter_sha'],ctx['participant'],ctx['fit_role'])
        # Canonical admission is only validation; raw outputs stay independently pinned.
        canonical_pin=save(root/'ADMITTED.json',canonical(doc),self.budget,cap=outputs.CAP,metadata=False)
        self.documents[ctx['phase_id']]=canonical_pin
        view.retire_after_closed_execution(receipt,check)
        rp=save(root/'ACCEPTED_PHASE.json',canonical(receipt),self.budget)
        self.artifacts[ctx['phase_id']]={'raw':pins,'admitted':canonical_pin}
        return {'context':ctx,'request':reqpin,'receipt':rp,'journal':logpin,'input_retired_only_after_exact_closure':True}
    def complete(self,records):
        need([r['context'] for r in records]==protocol.phases() and len(self.artifacts)==85,'all85 full original phases required')
        panels={}
        for arm,label in [('A','corrected_A'),('B','corrected_B'),(None,'portable_operator')]:
            raw={}
            for person in protocol.PEOPLE:
                for role in protocol.ROLES:
                    key=(arm or 'operator')+'_'+person+'_'+role
                    raw[person,role]=capture(self.out/'phases'/key/'ADMITTED.json',self.documents[key],outputs.CAP,self.budget)
            doc=outputs.assemble(raw,self.design['parameter_rows'],self.design['parameter_sha'])
            panels[label]=save(self.out/'panels'/(label+'.json'),canonical(doc),self.budget,cap=outputs.CAP,metadata=False)
        for arm in ('A','B'):
            panels['reproduction_'+arm]=self.documents['spatial_'+arm]
        join={'schema':'visual_alpha_sealed_comparison_join_v1','source_manifest':self.v['source_manifest'],'panels':panels,'portable_operator_source':'spatial/ALGORITHM_PROPOSAL.json','portable_operator_phases':[r['context']['phase_id'] for r in records if r['context']['mode']=='reference'],'portable_baseline_candidate_controlled':False,'all4_candidate_panels_admit_before_private_callbacks':True,'native_gain_provenance_missing_must_stay_unavailable':True,'requires_whole_observer_admission':True,'requires_separate_private_scoring_authority':True,'automatic_scoring':False}
        jp=save(self.out/'SEALED_GRADE_JOIN.json',canonical(join),self.budget)
        result={'schema':'visual_alpha_complete_paired_collection_v1','task_id':protocol.TASK,'condition':protocol.CONDITION,'coverage':protocol.COVERAGE,'source_manifest':self.v['source_manifest'],'commitment':self.commit_pin,'phases':records,'artifacts':self.artifacts,'panels':panels,'sealed_grade_join':jp,'original_origin':self.origin,'original_work_end':self.end,'managed_read_bytes':self.budget.read,'managed_write_bytes_before_collection':self.budget.written,'retained_charge_before_collection':self.budget.retained_charge,'runtime_qualified':False,'scientific_qualified':False,'whole_paper_reproduced':False,'native_MATLAB_parity':False,'automatic_retry':False,'private_scoring_called':False}
        save(self.out/'COLLECTION.json',canonical(result),self.budget);return result


def execute(selection,b,output,origin,source_dir):
    v=selected(selection);need(sys.version.split()[0]==protocol.VERSIONS['python'],'exact selected host interpreter')
    seconds=sum(v['producer_seconds'][c['mode']]+360 for c in protocol.phases())
    end=origin+120+seconds+600
    need(math.isfinite(end) and time.monotonic()<origin+120,'unrenewed original startup clock')
    out=ordinary(output);need(not out.exists() and out.parent.is_dir(),'fresh explicit owned output directory')
    mkdirs(out)
    budget=Budget(out,end,read_cap=READ_CAP,write_cap=WRITE_CAP,retained_cap=RETAINED_CAP,other_future=v['other_future_bytes'])
    name='_visual_alpha_owned_engine';spec=importlib.util.spec_from_file_location(name,source_dir/'engine/native.py');engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    return run_sequence(Operations(v,b,out,budget,origin,end,source_dir,engine))
