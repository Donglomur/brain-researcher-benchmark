"""Full public fit/preparation, sealed state, batch inference and public admission."""
import os,signal,time
from pathlib import Path

def write(path,value,cap,budget):return c.save(path,c.encoded(value),cap,budget.tick,budget.write)

def dependencies(repo,binding,budget):
    source=c.parse(c.capture(repo/binding['source_descriptor']['path'],65536,c.only_pin(binding['source_descriptor']),budget.tick,budget.read))
    export=c.parse(c.capture(repo/binding['export_descriptor']['path'],65536,c.only_pin(binding['export_descriptor']),budget.tick,budget.read))
    rows=binding['files'];c.need(len(rows)==25 and len({r['target'] for r in rows})==25,'complete original source inventory')
    c.need(source['task_ids']==export['task_ids']==['NEURAL-021'] and export['files']==rows and export['source_manifest']==binding['source_descriptor'],'selected source/export identity')
    c.need([{k:r[k] for k in ('target','bytes','sha256','role','visibility')} for r in source['files']]==rows,'complete original source rows')
    public=[r for r in rows if r['visibility']=='public']
    c.need(len(public)==12 and sum(r['bytes'] for r in public)==653046,'all twelve public members')
    expected={r['target'] for r in public}
    c.need(set(binding['phase_public_members']['fit'])==expected-{'public/cases.json','public/queries.npz'} and set(binding['phase_public_members']['infer'])==expected-{'public/training.npz'},'exact phase visibility')
    for row in rows:
        p=Path(row['target']);c.need(not p.is_absolute() and '..' not in p.parts and p.parts[0] in ('public','private'),'confined source member')
    package=c.path(repo/binding['package']);c.need(package/'DELIVERY_MANIFEST.json'==repo/binding['export_descriptor']['path'],'same selected package')
    files,_,_=c.inventory(package,2000000,128)
    c.need(set(files)=={r['target'] for r in rows}|{'DELIVERY_MANIFEST.json'},'exact export inventory; no private body reads')
    return package,public

def phase_rows(public,binding,phase):
    expected=set(binding['phase_public_members'][phase])
    rows=[r for r in public if r['target'] in expected]
    c.need(len(rows)==(10 if phase=='fit' else 11) and {r['target'] for r in rows}==expected,'full phase allowlist')
    return rows

def prepare(package,rows,root,budget,label,current_name='current'):
    current=root/current_name;c.need(not os.path.lexists(current),'fresh owned public view')
    budget.capacity(1000000);current.mkdir(mode=0o755);expected={}
    for row in rows:
        rel=Path(row['target']).relative_to('public');target=current/rel
        target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        raw=c.capture(package/row['target'],1000000,c.only_pin(row),budget.tick,budget.read)
        expected[rel.as_posix()]=c.save(target,raw,1000000,budget.tick,budget.write);c.readable(target,budget.tick)
    files,dirs,used=c.inventory(current,1000000,32);c.need(set(files)==set(expected),'exact public view inventory')
    for name,(path,_) in files.items():c.capture(path,1000000,expected[name],budget.tick,budget.read)
    for directory in sorted(dirs,key=lambda p:len(p.parts),reverse=True):c.public_directory(directory,budget.tick)
    c.sync_dir(root,budget.tick)
    receipt=write(root/('VIEW_'+label+'_PREPARED.json'),dict(schema='neural021_phase_view_v1',phase=label,files=expected,member_count=len(expected),allocated_bytes=used,decoded=False),32768,budget)
    return current,expected,receipt

def retire(current,expected,root,budget,label):
    files,dirs,_=c.inventory(current,1000000,32);c.need(set(files)==set(expected),'exact owned view before retirement')
    for name,(path,_) in files.items():c.capture(path,1000000,expected[name],budget.tick,budget.read)
    write(root/('VIEW_'+label+'_RETIRE_INTENT.json'),dict(phase=label,files=expected,after_phase_native_closure=True),32768,budget)
    for path,identity in files.values():
        budget.tick();c.need(c.stamp(path.lstat())==identity,'same retired inode');path.unlink();c.sync_dir(path.parent,budget.tick)
    for directory in sorted(dirs,key=lambda p:len(p.parts),reverse=True):directory.rmdir();c.sync_dir(directory.parent,budget.tick)
    c.need(not os.path.lexists(current),'whole view absent')
    return write(root/('VIEW_'+label+'_RETIRED.json'),dict(schema='neural021_phase_retired_v1',phase=label,member_count=len(expected),absent=True,parent_fsynced=True),8192,budget)

def support_result(raw,cases_sha):
    expected=dict(task_id='NEURAL-021',status='public_format_admitted_ungraded',query_trials=92,active_queries=52,perturbation_queries=40,time_bins=30,velocity_axes=2,cases_sha256=cases_sha,private_target_calls=0,numerical_values_verified=False,scientific_qualification_added=False,operator_entrypoint='neural021_full92_public_support_v1',requires_observed_cli_exit_zero=True)
    value=c.parse(raw);c.need(c.encoded(value)==c.encoded(expected),'exact public format-only result');return value

def artifact(result,phase):
    expected={'fit':('state.bin',16777216),'infer':('submission.json',4194304),'admission':('support.json',262144)}
    name,cap=expected[phase];c.need(result['status']=='captured' and set(result['outputs'])=={name},'complete role artifact')
    value=c.exact_pin(result['outputs'][name]);c.need(value['bytes']<=cap,'role output bound');return value

def check_copied_sources(root,manifest,budget):
    for name in ('holder.py','candidate_entry.py','trusted_entry.py'):
        c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)

def set_end(budget,end):
    budget.end=end;budget.tick();remaining=end-time.monotonic()
    c.need(remaining>0,'positive original phase interval');signal.setitimer(signal.ITIMER_REAL,remaining)

def run(s,source,bodies,manifest,origin,worker_end):
    here=Path(__file__).parent;repo=c.path(s['repository']);root=c.path(s['output'])
    budget=c.Budget(root,s['other_future_bytes'],min(worker_end,origin+180));set_end(budget,budget.end)
    c.need(not os.path.lexists(root) and root.parent.is_dir(),'fresh output')
    c.need(not root.is_relative_to(repo) and root.parent.stat().st_dev==repo.stat().st_dev,'separate same-volume custody')
    budget.capacity();budget.read(sum(len(x)+1 for x in bodies.values())+65536)
    binding=c.parse(bodies['BINDINGS.json']);policy.reviews(s,budget)
    package,public=dependencies(repo,binding,budget)
    program=c.capture(s['program']['path'],1048576,c.only_pin(s['program']),budget.tick,budget.read)
    c.need('\0' not in program.decode('utf-8'),'UTF8 self-contained source')
    root.mkdir(mode=0o700)
    for name in ('commitment','fit','infer','admission'):(root/name).mkdir(mode=0o700)
    c.sync_dir(root,budget.tick);c.sync_dir(root.parent,budget.tick)
    frozen=c.save(root/'commitment/program.py',program,1048576,budget.tick,budget.write);c.readable(root/'commitment/program.py',budget.tick)
    for name in ('holder.py','candidate_entry.py','trusted_entry.py'):
        c.save(root/'commitment'/name,bodies[name],16384,budget.tick,budget.write);c.readable(root/'commitment'/name,budget.tick)
    commitment=write(root/'commitment/COMMITMENT.json',dict(schema='neural021_full92_commitment_v1',source=source,program=frozen,scope=s['scope'],method_review=c.only_pin(s['method_review']),before_any_public_signal_view=True),8192,budget)
    stage='committed';views={};native_pins={}
    write(root/'INTENT.json',dict(source=source,program=frozen,scope=s['scope'],commitment=commitment,stages=['fit','infer','admission'],feedback_withheld=True,grade_authorized=False),8192,budget)
    try:
        current,expected,prepared=prepare(package,phase_rows(public,binding,'fit'),root,budget,'fit')
        end=min(worker_end-s['infer_seconds']-900,time.monotonic()+s['fit_seconds']+240)
        c.need(end-time.monotonic()>s['fit_seconds']+235,'full fit preparation allocation');set_end(budget,end)
        check_copied_sources(root,manifest,budget);c.capture(root/'commitment/program.py',1048576,frozen,budget.tick,budget.read)
        budget.native('fit');stage='fit'
        fitted=native.phase(s,root/'commitment',current,root/'commitment/program.py',root/'fit','fit',source,budget,end-30,binding['cases']['sha256'])
        state=artifact(fitted,'fit')
        c.capture(root/'fit/state.bin',16777216,state,budget.tick,budget.read);c.readable(root/'fit/state.bin',budget.tick)
        retired=retire(current,expected,root,budget,'fit');views['fit']=dict(prepared=prepared,retired=retired)
        native_pins['fit']=c.pin(c.capture(root/'fit/NATIVE.json',262144,tick=budget.tick,charge=budget.read))
        sealed=write(root/'STATE_COMMITTED.json',dict(schema='neural021_state_seal_v1',source=source,program=frozen,state=state,fit_native=native_pins['fit'],fit_retirement=retired,before_any_query_view=True,readonly_owned_state=True,semantic_training_only_compliance_proven=False,training_only_lazy_computation_permitted=True),8192,budget)
        stage='state_sealed_before_query'
        # Whole92 batch is released only after fit native closure, state capture and durable seal.
        end=min(worker_end-650,time.monotonic()+s['infer_seconds']+240)
        c.need(end-time.monotonic()>s['infer_seconds']+235,'full inference allocation');set_end(budget,end)
        c.capture(root/'STATE_COMMITTED.json',8192,sealed,budget.tick,budget.read)
        c.capture(root/'fit/state.bin',16777216,state,budget.tick,budget.read)
        current,expected,prepared=prepare(package,phase_rows(public,binding,'infer'),root,budget,'infer')
        check_copied_sources(root,manifest,budget);c.capture(root/'commitment/program.py',1048576,frozen,budget.tick,budget.read)
        budget.native('infer');stage='infer'
        inferred=native.phase(s,root/'commitment',current,root/'commitment/program.py',root/'infer','infer',source,budget,end-30,binding['cases']['sha256'],state_file=root/'fit/state.bin')
        submission=artifact(inferred,'infer')
        c.capture(root/'fit/state.bin',16777216,state,budget.tick,budget.read)
        c.capture(root/'infer/submission.json',4194304,submission,budget.tick,budget.read);c.readable(root/'infer/submission.json',budget.tick)
        retired=retire(current,expected,root,budget,'infer');views['infer']=dict(prepared=prepared,retired=retired)
        native_pins['infer']=c.pin(c.capture(root/'infer/NATIVE.json',262144,tick=budget.tick,charge=budget.read))
        output_commitment=write(root/'SUBMISSION_COMMITTED.json',dict(source=source,program=frozen,state_commitment=sealed,outputs={'submission.json':submission},infer_native=native_pins['infer'],infer_retirement=retired,public_format_not_yet_validated=True,numerically_validated=False),8192,budget)
        stage='complete_predictions_closed'
        end=min(worker_end-100,time.monotonic()+480);c.need(end-time.monotonic()>475,'full public admission allocation');set_end(budget,end)
        check_copied_sources(root,manifest,budget)
        support_rows=[row for row in public if row['target'] in ('public/interface.py','public/cases.json')]
        support,expected,prepared=prepare(package,support_rows,root,budget,'support','support')
        budget.native('admission');stage='admission'
        admitted=native.phase(s,root/'commitment',support,root/'infer/submission.json',root/'admission','admission',source,budget,end-30,binding['cases']['sha256'])
        support_pin=artifact(admitted,'admission')
        support_result(c.capture(root/'admission/support.json',262144,support_pin,budget.tick,budget.read),binding['cases']['sha256'])
        c.capture(root/'infer/submission.json',4194304,submission,budget.tick,budget.read)
        retired=retire(support,expected,root,budget,'support');views['support']=dict(prepared=prepared,retired=retired)
        native_pins['admission']=c.pin(c.capture(root/'admission/NATIVE.json',262144,tick=budget.tick,charge=budget.read))
        stage='public_format_admitted_ungraded';set_end(budget,min(worker_end,time.monotonic()+100))
        c.capture(root/'commitment/program.py',1048576,frozen,budget.tick,budget.read)
        handoff=write(root/'GRADE_HANDOFF.json',dict(schema='neural021_separate_grade_handoff_v1',task_id='NEURAL-021',submission={'path':str(root/'infer/submission.json'),**submission},package=str(package),export_descriptor=binding['export_descriptor'],scope=s['scope'],argv=['python','-I','-B',str(package/'private/grade.py'),'--submission',str(root/'infer/submission.json'),'--output','ROOT_MUST_SELECT_FRESH_OUTPUT'],execution_authorized=False,new_budget_and_external_observer_required=True,private_target_calls_this_run=0,condition_R2_negative_null_and_loss_preserved=True,baselines_executed=False,time_template_comparison_required_for_interpretation=True,semantic_training_compliance_proven=False,scientific_reasoning_or_causality_or_SOTA_established=False),8192,budget)
        result=dict(schema='neural021_full92_complete_v1',status='complete_unqualified',source=source,program=frozen,commitment=commitment,scope=s['scope'],state=state,state_commitment=sealed,outputs={'submission.json':submission},outputs_commitment=output_commitment,views=views,native=native_pins,admission_output=support_pin,grade_handoff=handoff,complete_public_format_validated=True,all_public_views_retired=True,numerical_grading_performed=False,semantic_training_compliance_proven=False,scientific_qualified=False,runtime_qualified=False,external_natural_zero_required=True,costs=budget.record())
        result['costs']['write_reservations']+=32768;budget.write(32768)
        terminal=c.save(root/'COMPLETE.json',c.encoded(result),32768,budget.tick)
        budget.tick();return dict(schema='neural021_full92_worker_v1',source=source,complete=terminal,scope=s['scope'],status='complete_unqualified')
    except BaseException as exc:
        budget.end=min(origin+policy.whole(s['fit_seconds'],s['infer_seconds'])+40,time.monotonic()+10)
        try:
            remaining=budget.end-time.monotonic();c.need(remaining>0,'positive original failure-publication interval')
            signal.setitimer(signal.ITIMER_REAL,remaining)
            write(root/'FAILURE.json',dict(schema='neural021_full92_failure_v1',source=source,error_type=type(exc).__name__,stage=stage,costs=budget.record(),partial_outputs_preserved=True,nested_cli_and_native_recovery_may_be_required=True,resource_intents_in=['fit','infer','admission'],automatic_continuation=False,scientific_qualified=False),16384,budget)
        except BaseException:pass
        raise
