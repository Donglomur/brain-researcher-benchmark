"""Complete eight-person public-input producer; schema admission and private grade separated."""
import os,signal,time
from pathlib import Path

def write(p,v,cap,b):return c.save(p,c.encoded(v),cap,b.tick,b.write)

def dependencies(repo,binding,budget):
    source=c.parse(c.capture(repo/binding['source_descriptor']['path'],100000,c.only_pin(binding['source_descriptor']),budget.tick,budget.read))
    export=c.parse(c.capture(repo/binding['export_descriptor']['path'],100000,c.only_pin(binding['export_descriptor']),budget.tick,budget.read))
    rows=binding['files'];c.need(len(rows)==76 and len({r['target'] for r in rows})==76,'complete76 unique members')
    c.need(export['task_ids']==source['task_ids']==['NEURAL-078'] and export['files']==rows and export['source_manifest']==binding['source_descriptor'],'selected source/export binding')
    c.need([{k:r[k] for k in ('target','bytes','sha256','role','visibility')} for r in source['files']]==rows,'unchanged full source rows')
    public=[r for r in rows if r['visibility']=='public']
    c.need(len(public)==15 and sum(r['bytes'] for r in public)==76460895 and len([r for r in public if r['target'].endswith('.npz')])==8,'full public8 primitive panel')
    for r in rows:
        p=Path(r['target']);c.need(not p.is_absolute() and '..' not in p.parts and p.parts[0] in ('public','private'),'bound package-relative member')
    package=c.path(repo/binding['package']);c.need(package/'DELIVERY_MANIFEST.json'==repo/binding['export_descriptor']['path'],'same installed package')
    verify_package(package,rows,binding,budget)
    return package,public

def verify_package(package,rows,binding,budget):
    # Authenticate only the full public subtree. Private rows are metadata bindings.
    public=[r for r in rows if r['visibility']=='public']
    files,_,_=c.inventory(package/'public',80000000,32)
    expected={str(Path(r['target']).relative_to('public')):r for r in public}
    c.need(set(files)==set(expected),'exact complete15 public inventory')
    c.capture(package/'DELIVERY_MANIFEST.json',100000,c.only_pin(binding['export_descriptor']),budget.tick,budget.read)
    for name,r in expected.items():c.capture(package/'public'/name,15000000,c.only_pin(r),budget.tick,budget.read)

def prepare(package,public,root,budget):
    current=root/'current';c.need(not os.path.lexists(current),'fresh complete public view')
    budget.capacity(80000000);current.mkdir(mode=0o755);expected={}
    for r in public:
        rel=Path(r['target']).relative_to('public');target=current/rel
        target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        raw=c.capture(package/r['target'],80000000,c.only_pin(r),budget.tick,budget.read)
        expected[rel.as_posix()]=c.save(target,raw,80000000,budget.tick,budget.write);c.readable(target,budget.tick)
    files,dirs,used=c.inventory(current,80000000,70)
    c.need(set(files)==set(expected),'only15 public members')
    for d in sorted(dirs,key=lambda p:len(p.parts),reverse=True):c.sync_dir(d,budget.tick)
    c.sync_dir(root,budget.tick)
    for name,(p,_) in files.items():c.capture(p,80000000,expected[name],budget.tick,budget.read)
    prepared=write(root/'VIEW_PREPARED.json',dict(schema='neural078_full8_public_view_v1',files=expected,member_count=15,primitive_files=8,allocated_bytes=used,decoded=False),32768,budget)
    return current,expected,prepared

def retire(current,expected,root,budget):
    files,dirs,_=c.inventory(current,80000000,70);c.need(set(files)==set(expected),'exact owned view before retirement')
    for name,(p,_) in files.items():c.capture(p,80000000,expected[name],budget.tick,budget.read)
    write(root/'VIEW_RETIRE_INTENT.json',dict(files=expected,after_candidate_native_closure=True),32768,budget)
    for p,identity in files.values():
        budget.tick();c.need(c.stamp(p.lstat())==identity,'same owned retired inode');p.unlink();c.sync_dir(p.parent,budget.tick)
    for d in sorted(dirs,key=lambda p:len(p.parts),reverse=True):d.rmdir();c.sync_dir(d.parent,budget.tick)
    c.need(not os.path.lexists(current),'whole public view absent')
    return write(root/'VIEW_RETIRED.json',dict(schema='neural078_full8_public_retired_v1',member_count=15,primitive_files=8,absent=True,parent_fsynced=True),8192,budget)

def support_result(raw,export_sha):
    v=c.parse(raw)
    expected=dict(task_id='NEURAL-078',status='schema_support_consistent_artifact_only',participants=8,required_fields=195,private_reference_calls=0,numeric_comparison_performed=False,scientific_qualification_added=False,operator_entrypoint='neural078_public_report_admission_v1',export_manifest_sha256=export_sha,requires_observed_cli_exit_zero=True)
    c.need(c.encoded(v)==c.encoded(expected),'exact auxiliary-only support result')
    return v

def run(s,source,bodies,manifest,origin,worker_end):
    here=Path(__file__).parent;repo=c.path(s['repository']);root=c.path(s['output'])
    budget=c.Budget(root,s['other_future_bytes'],min(worker_end,origin+180))
    signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
    c.need(not os.path.lexists(root) and root.parent.is_dir(),'fresh output')
    c.need(not root.is_relative_to(repo) and root.parent.stat().st_dev==repo.stat().st_dev,'separate same-volume custody')
    budget.capacity();budget.read(sum(len(x)+1 for x in bodies.values())+65536)
    binding=c.parse(bodies['BINDINGS.json']);policy.reviews(s,budget)
    package,public=dependencies(repo,binding,budget)
    program=c.capture(s['program']['path'],131072,c.only_pin(s['program']),budget.tick,budget.read)
    c.need('\0' not in program.decode('utf-8'),'UTF8 self-contained source')
    root.mkdir(mode=0o700)
    for name in ('commitment','candidate','admission'):(root/name).mkdir(mode=0o700)
    c.sync_dir(root,budget.tick);c.sync_dir(root.parent,budget.tick)
    frozen=c.save(root/'commitment/program.py',program,131072,budget.tick,budget.write);c.readable(root/'commitment/program.py',budget.tick)
    for name in ('holder.py','candidate_entry.py','trusted_entry.py','report_contract.py'):
        c.save(root/'commitment'/name,bodies[name],16384,budget.tick,budget.write);c.readable(root/'commitment'/name,budget.tick)
    commit=write(root/'commitment/COMMITMENT.json',dict(schema='neural078_full8_commitment_v1',source=source,program=frozen,scope=s['scope'],method_review=c.only_pin(s['method_review']),before_any_public_signal_view=True),8192,budget)
    stage='committed'
    write(root/'INTENT.json',dict(source=source,program=frozen,scope=s['scope'],commitment=commit,stages=['candidate','admission'],feedback_withheld=True,grade_authorized=False),8192,budget)
    try:
        current,expected,prepared=prepare(package,public,root,budget);stage='prepared'
        candidate_end=min(worker_end-600,time.monotonic()+s['candidate_seconds']+180)
        c.need(candidate_end-time.monotonic()>s['candidate_seconds']+175,'full candidate phase allocation')
        budget.end=candidate_end;signal.setitimer(signal.ITIMER_REAL,max(.001,candidate_end-time.monotonic()))
        for name in ('holder.py','candidate_entry.py','trusted_entry.py','report_contract.py'):c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)
        c.capture(root/'commitment/program.py',131072,frozen,budget.tick,budget.read)
        budget.native('candidate');stage='candidate'
        candidate=native.phase(s,root/'commitment',current,root/'commitment/program.py',root/'candidate','candidate',source,budget,candidate_end-30,binding['export_descriptor']['sha256'])
        c.need(candidate['status']=='captured','complete closed candidate output')
        c.capture(root/'commitment/program.py',131072,frozen,budget.tick,budget.read)
        retirement=retire(current,expected,root,budget);stage='candidate_closed_and_view_retired'
        report=candidate['output'];c.capture(root/'candidate/report.json',65536,report,budget.tick,budget.read);c.readable(root/'candidate/report.json',budget.tick)
        candidate_pin=c.pin(c.capture(root/'candidate/NATIVE.json',262144,tick=budget.tick,charge=budget.read))
        write(root/'REPORT_COMMITTED.json',dict(source=source,program=frozen,report=report,candidate_native=candidate_pin,retirement=retirement,whole_report_captured=True,full8_schema_support_not_yet_validated=True,numerically_validated=False),8192,budget)
        admission_end=min(worker_end-100,time.monotonic()+480)
        c.need(admission_end-time.monotonic()>475,'full trusted admission allocation')
        budget.end=admission_end;signal.setitimer(signal.ITIMER_REAL,max(.001,admission_end-time.monotonic()))
        c.capture(package/'DELIVERY_MANIFEST.json',100000,c.only_pin(binding['export_descriptor']),budget.tick,budget.read)
        for name in ('holder.py','trusted_entry.py','report_contract.py'):c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)
        budget.native('admission');stage='admission'
        admitted=native.phase(s,root/'commitment',package,root/'candidate/report.json',root/'admission','admission',source,budget,admission_end-30,binding['export_descriptor']['sha256'])
        raw=c.capture(root/'admission/report.json',65536,admitted['output'],budget.tick,budget.read)
        support_result(raw,binding['export_descriptor']['sha256'])
        c.capture(root/'candidate/report.json',65536,report,budget.tick,budget.read)
        admission_pin=c.pin(c.capture(root/'admission/NATIVE.json',262144,tick=budget.tick,charge=budget.read));stage='support_admitted_not_numerically_graded'
        budget.end=min(worker_end,time.monotonic()+100);signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
        gold=next(r for r in binding['files'] if r['target']=='private/reference/GOLD.json')
        handoff=write(root/'GRADE_HANDOFF.json',dict(schema='neural078_separate_grade_handoff_v1',task_id='NEURAL-078',report={'path':str(root/'candidate/report.json'),**report},package=str(package),export_descriptor=binding['export_descriptor'],scope=s['scope'],argv=['python',str(package/'private/source/score.py'),'--submission',str(root/'candidate/report.json'),'--gold',str(package/gold['target']),'--gold-sha256',gold['sha256'],'--output','ROOT_MUST_SELECT_FRESH_OUTPUT'],execution_authorized=False,new_budget_and_external_observer_required=True,private_reference_calls_in_this_producer=0,required_fields=195,scientific_reasoning_or_causality_or_SOTA_established=False),8192,budget)
        result=dict(schema='neural078_full8_complete_v1',status='complete_unqualified',source=source,program=frozen,commitment=commit,scope=s['scope'],report=report,view_prepared=prepared,view_retirement=retirement,candidate_native=candidate_pin,admission_native=admission_pin,admission_output=admitted['output'],grade_handoff=handoff,complete_report_schema_support_validated=True,all_public_views_retired=True,numerical_grading_performed=False,scientific_qualified=False,runtime_qualified=False,external_natural_zero_required=True,costs=budget.record())
        result['costs']['write_reservations']+=32768;budget.write(32768)
        terminal=c.save(root/'COMPLETE.json',c.encoded(result),32768,budget.tick)
        budget.tick();return dict(schema='neural078_full8_worker_v1',source=source,complete=terminal,scope=s['scope'],status='complete_unqualified')
    except BaseException as exc:
        budget.end=min(origin+policy.whole(s['candidate_seconds'])+40,time.monotonic()+10)
        try:
            signal.setitimer(signal.ITIMER_REAL,max(.001,budget.end-time.monotonic()))
            write(root/'FAILURE.json',dict(schema='neural078_full8_failure_v1',source=source,error_type=type(exc).__name__,stage=stage,costs=budget.record(),partial_outputs_preserved=True,nested_cli_and_native_recovery_may_be_required=True,resource_intents_in=['candidate','admission'],automatic_continuation=False,scientific_qualified=False),16384,budget)
        except BaseException:pass
        raise
