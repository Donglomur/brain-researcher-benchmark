"""Complete signal-report producer plus auxiliary admission; numerical grade separate."""
import os,signal,time
from pathlib import Path

def write(p,v,cap,b):return c.save(p,c.encoded(v),cap,b.tick,b.write)

def dependencies(repo,binding,budget):
    source=c.parse(c.capture(repo/binding['source_descriptor']['path'],100000,c.only_pin(binding['source_descriptor']),budget.tick,budget.read))
    export=c.parse(c.capture(repo/binding['export_descriptor']['path'],100000,c.only_pin(binding['export_descriptor']),budget.tick,budget.read))
    rows=binding['files'];c.need(len(rows)==64 and len({r['target'] for r in rows})==64,'complete64 unique members')
    c.need(export['task_ids']==source['task_ids']==['NEURAL-052'] and export['files']==rows and export['source_manifest']==binding['source_descriptor'],'selected source/export binding')
    c.need([{k:r[k] for k in ('target','bytes','sha256','role','visibility')} for r in source['files']]==rows,'unchanged full source rows')
    public=[r for r in rows if r['visibility']=='public']
    c.need(len(public)==14 and sum(r['bytes'] for r in public)==71207593 and len([r for r in public if r['target'].endswith('_responses.npy')])==3,'full public3 response panel')
    for r in rows:
        p=Path(r['target']);c.need(not p.is_absolute() and '..' not in p.parts and p.parts[0] in ('public','private'),'bound package-relative member')
    package=c.path(repo/binding['package']);c.need(package/'DELIVERY_MANIFEST.json'==repo/binding['export_descriptor']['path'],'same installed package')
    verify_package(package,rows,binding,budget)
    return package,public

def verify_package(package,rows,binding,budget):
    files,_,_=c.inventory(package,80000000,512)
    c.need(set(files)=={r['target'] for r in rows}|{'DELIVERY_MANIFEST.json'},'exact complete export inventory')
    c.capture(package/'DELIVERY_MANIFEST.json',100000,c.only_pin(binding['export_descriptor']),budget.tick,budget.read)
    for r in rows:c.capture(package/r['target'],32000000,c.only_pin(r),budget.tick,budget.read)

def prepare(package,public,root,budget):
    current=root/'current';c.need(not os.path.lexists(current),'fresh complete public view')
    budget.capacity(72000000);current.mkdir(mode=0o755);expected={}
    for r in public:
        rel=Path(r['target']).relative_to('public');target=current/rel
        target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        raw=c.capture(package/r['target'],32000000,c.only_pin(r),budget.tick,budget.read)
        expected[rel.as_posix()]=c.save(target,raw,72000000,budget.tick,budget.write);c.readable(target,budget.tick)
    files,dirs,used=c.inventory(current,72000000,70)
    c.need(set(files)==set(expected),'only14 public members')
    for d in sorted(dirs,key=lambda p:len(p.parts),reverse=True):c.sync_dir(d,budget.tick)
    c.sync_dir(root,budget.tick)
    for name,(p,_) in files.items():c.capture(p,72000000,expected[name],budget.tick,budget.read)
    prepared=write(root/'VIEW_PREPARED.json',dict(schema='neural052_full3_public_view_v1',files=expected,member_count=14,primitive_files=3,allocated_bytes=used,decoded=False),32768,budget)
    return current,expected,prepared

def retire(current,expected,root,budget):
    files,dirs,_=c.inventory(current,72000000,70);c.need(set(files)==set(expected),'exact owned view before retirement')
    for name,(p,_) in files.items():c.capture(p,72000000,expected[name],budget.tick,budget.read)
    write(root/'VIEW_RETIRE_INTENT.json',dict(files=expected,after_candidate_native_closure=True),32768,budget)
    for p,identity in files.values():
        budget.tick();c.need(c.stamp(p.lstat())==identity,'same owned retired inode');p.unlink();c.sync_dir(p.parent,budget.tick)
    for d in sorted(dirs,key=lambda p:len(p.parts),reverse=True):d.rmdir();c.sync_dir(d.parent,budget.tick)
    c.need(not os.path.lexists(current),'whole public view absent')
    return write(root/'VIEW_RETIRED.json',dict(schema='neural052_full3_public_retired_v1',member_count=14,primitive_files=3,absent=True,parent_fsynced=True),8192,budget)

def support_result(raw,export_sha):
    v=c.parse(raw)
    expected=dict(task_id='NEURAL-052',status='support_consistent_artifact_only',participants=['01','02','03'],total_rows=3600,folds_per_person=15,fixed_models=4,shared_concept_draws=1000,private_reference_calls=0,numerical_values_verified=False,scientific_qualification_added=False,operator_entrypoint='neural052_full3_support_v1',export_manifest_sha256=export_sha,requires_observed_cli_exit_zero=True)
    c.need(c.encoded(v)==c.encoded(expected),'exact auxiliary-only support result')
    return v

def output_pins(outputs):
    c.need(type(outputs)is dict and set(outputs)=={'result.json','METHODS.md'},'exact complete two-artifact output')
    for name,cap in [('result.json',4000000),('METHODS.md',1048576)]:
        c.need(c.exact_pin(outputs[name])['bytes']<=cap,'selected artifact extent')
    return outputs

def recheck_outputs(root,outputs,budget,readable=False):
    output_pins(outputs)
    for name,cap in [('result.json',4000000),('METHODS.md',1048576)]:
        raw=c.capture(root/name,cap,outputs[name],budget.tick,budget.read)
        if name=='METHODS.md':c.need('\0' not in raw.decode('utf-8'),'complete UTF8 METHODS')
        if readable:c.readable(root/name,budget.tick)

def run(s,source,bodies,manifest,origin,worker_end):
    here=Path(__file__).parent;repo=c.path(s['repository']);root=c.path(s['output'])
    budget=c.Budget(root,s['other_future_bytes'],min(worker_end,origin+180))
    signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
    c.need(not os.path.lexists(root) and root.parent.is_dir(),'fresh output')
    c.need(not root.is_relative_to(repo) and root.parent.stat().st_dev==repo.stat().st_dev,'separate same-volume custody')
    budget.capacity();budget.read(sum(len(x)+1 for x in bodies.values())+65536)
    binding=c.parse(bodies['BINDINGS.json']);policy.reviews(s,budget)
    package,public=dependencies(repo,binding,budget)
    program=c.capture(s['program']['path'],1048576,c.only_pin(s['program']),budget.tick,budget.read)
    c.need('\0' not in program.decode('utf-8'),'UTF8 self-contained source')
    root.mkdir(mode=0o700)
    for name in ('commitment','candidate','admission'):(root/name).mkdir(mode=0o700)
    c.sync_dir(root,budget.tick);c.sync_dir(root.parent,budget.tick)
    frozen=c.save(root/'commitment/program.py',program,1048576,budget.tick,budget.write);c.readable(root/'commitment/program.py',budget.tick)
    for name in ('holder.py','candidate_entry.py','trusted_entry.py'):
        c.save(root/'commitment'/name,bodies[name],16384,budget.tick,budget.write);c.readable(root/'commitment'/name,budget.tick)
    commit=write(root/'commitment/COMMITMENT.json',dict(schema='neural052_full3_commitment_v1',source=source,program=frozen,scope=s['scope'],method_review=c.only_pin(s['method_review']),before_any_public_signal_view=True),8192,budget)
    stage='committed'
    write(root/'INTENT.json',dict(source=source,program=frozen,scope=s['scope'],commitment=commit,stages=['candidate','admission'],feedback_withheld=True,grade_authorized=False),8192,budget)
    try:
        current,expected,prepared=prepare(package,public,root,budget);stage='prepared'
        candidate_end=min(worker_end-600,time.monotonic()+s['candidate_seconds']+180)
        c.need(candidate_end-time.monotonic()>s['candidate_seconds']+175,'full candidate phase allocation')
        budget.end=candidate_end;signal.setitimer(signal.ITIMER_REAL,max(.001,candidate_end-time.monotonic()))
        for name in ('holder.py','candidate_entry.py','trusted_entry.py'):c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)
        c.capture(root/'commitment/program.py',1048576,frozen,budget.tick,budget.read)
        budget.native('candidate');stage='candidate'
        candidate=native.phase(s,root/'commitment',current,root/'commitment/program.py',root/'candidate','candidate',source,budget,candidate_end-30,binding['export_descriptor']['sha256'])
        c.need(candidate['status']=='captured','complete closed candidate output')
        c.capture(root/'commitment/program.py',1048576,frozen,budget.tick,budget.read)
        retirement=retire(current,expected,root,budget);stage='candidate_closed_and_view_retired'
        outputs=output_pins(candidate['outputs']);recheck_outputs(root/'candidate',outputs,budget,readable=True)
        candidate_pin=c.pin(c.capture(root/'candidate/NATIVE.json',262144,tick=budget.tick,charge=budget.read))
        sealed=write(root/'REPORT_COMMITTED.json',dict(source=source,program=frozen,outputs=outputs,candidate_native=candidate_pin,retirement=retirement,whole_two_artifact_output_captured=True,full3_support_not_yet_validated=True,numerically_validated=False),8192,budget)
        admission_end=min(worker_end-100,time.monotonic()+480)
        c.need(admission_end-time.monotonic()>475,'full trusted admission allocation')
        budget.end=admission_end;signal.setitimer(signal.ITIMER_REAL,max(.001,admission_end-time.monotonic()))
        verify_package(package,binding['files'],binding,budget)
        for name in ('holder.py','trusted_entry.py'):c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)
        budget.native('admission');stage='admission'
        admitted=native.phase(s,root/'commitment',package,root/'candidate',root/'admission','admission',source,budget,admission_end-30,binding['export_descriptor']['sha256'])
        c.need(set(admitted['outputs'])=={'support.json'},'only trusted support result')
        raw=c.capture(root/'admission/support.json',262144,admitted['outputs']['support.json'],budget.tick,budget.read)
        support_result(raw,binding['export_descriptor']['sha256'])
        recheck_outputs(root/'candidate',outputs,budget)
        admission_pin=c.pin(c.capture(root/'admission/NATIVE.json',262144,tick=budget.tick,charge=budget.read));stage='support_admitted_not_numerically_graded'
        budget.end=min(worker_end,time.monotonic()+100);signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
        handoff=write(root/'GRADE_HANDOFF.json',dict(schema='neural052_separate_grade_handoff_v1',task_id='NEURAL-052',outputs={name:{'path':str(root/'candidate'/name),**pin} for name,pin in outputs.items()},package=str(package),export_descriptor=binding['export_descriptor'],scope=s['scope'],argv=['python','-B',str(package/'private/grade.py'),'--submission',str(root/'candidate/result.json'),'--output','ROOT_MUST_SELECT_FRESH_OUTPUT'],execution_authorized=False,new_budget_and_external_observer_required=True,reference_calls_per_future_grade=1,primary18_support_and_defined_requirements_preserved=True,prose_quality_not_numerically_graded=True,scientific_reasoning_or_causality_or_SOTA_established=False),8192,budget)
        result=dict(schema='neural052_full3_complete_v1',status='complete_unqualified',source=source,program=frozen,commitment=commit,scope=s['scope'],outputs=outputs,outputs_commitment=sealed,view_prepared=prepared,view_retirement=retirement,candidate_native=candidate_pin,admission_native=admission_pin,admission_output=admitted['outputs']['support.json'],grade_handoff=handoff,complete_report_support_validated=True,all_public_views_retired=True,numerical_grading_performed=False,scientific_qualified=False,runtime_qualified=False,external_natural_zero_required=True,costs=budget.record())
        result['costs']['write_reservations']+=32768;budget.write(32768)
        terminal=c.save(root/'COMPLETE.json',c.encoded(result),32768,budget.tick)
        budget.tick();return dict(schema='neural052_full3_worker_v1',source=source,complete=terminal,scope=s['scope'],status='complete_unqualified')
    except BaseException as exc:
        budget.end=min(origin+policy.whole(s['candidate_seconds'])+40,time.monotonic()+10)
        try:
            signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
            write(root/'FAILURE.json',dict(schema='neural052_full3_failure_v1',source=source,error_type=type(exc).__name__,stage=stage,costs=budget.record(),partial_outputs_preserved=True,nested_cli_and_native_recovery_may_be_required=True,resource_intents_in=['candidate','admission'],automatic_continuation=False,scientific_qualified=False),16384,budget)
        except BaseException:pass
        raise
