"""One frozen candidate and independent reference; no target or scorer invocation."""
import os,signal,time
from pathlib import Path

def write(path,value,cap,budget):return c.save(path,c.encoded(value),cap,budget.tick,budget.write)
def directory(path,budget,mode=0o700):
    budget.tick();path.mkdir(mode=mode);c.sync_dir(path,budget.tick);c.sync_dir(path.parent,budget.tick)

def dependencies(repo,binding,budget):
    for row in binding['metadata_dependencies']:
        c.capture(repo/row['path'],1000000,c.only_pin(row),budget.tick,budget.read)
    rows=binding['public_files']
    c.need(len(rows)==21 and len({r['target'] for r in rows})==21 and sum(r['bytes'] for r in rows)==11648181,'entire exact public package')
    for row in rows:
        p=Path(row['target']);c.need(len(p.parts)==2 and p.parts[0]=='public' and p.name not in ('PROTOCOL.json','SOURCE_BINDING.json'),'only flat public export assets')
    return c.path(repo/binding['package'])

def prepare(package,binding,root,budget):
    current=root/'current';c.need(not os.path.lexists(current),'fresh full public view');budget.capacity(12000000)
    directory(current,budget,0o755);expected={}
    for row in binding['public_files']:
        name=Path(row['target']).name;raw=c.capture(package/row['target'],20000000,c.only_pin(row),budget.tick,budget.read)
        expected[name]=c.save(current/name,raw,20000000,budget.tick,budget.write);c.readable(current/name,budget.tick)
    files,dirs,_=c.inventory(current,12582912,32)
    c.need(set(files)==set(expected) and dirs==[current],'exact21 public-only view')
    for name,(p,_) in files.items():c.capture(p,20000000,expected[name],budget.tick,budget.read)
    public=output.public_contract(c.parse(c.capture(current/'MANIFEST.json',2000000,expected['MANIFEST.json'],budget.tick,budget.read)))
    for row in public['sessions']:c.need(c.only_pin(row)==expected[row['file']],'public manifest/asset pin join')
    write(root/'journal/PREPARED.json',dict(files=expected,public_bytes=11648181,numeric_arrays_decoded_by_host=False),16384,budget)
    return current,expected,public

def retire(current,expected,root,budget):
    files,dirs,_=c.inventory(current,12582912,32);c.need(set(files)==set(expected) and dirs==[current],'same owned flat view')
    for name,(p,_) in files.items():c.capture(p,20000000,expected[name],budget.tick,budget.read)
    write(root/'journal/RETIRE_INTENT.json',dict(files=expected),16384,budget)
    for p,identity in files.values():
        budget.tick();c.need(c.stamp(p.lstat())==identity,'same owned inode');p.unlink();c.sync_dir(current,budget.tick)
    current.rmdir();c.sync_dir(root,budget.tick);c.need(not os.path.lexists(current),'view absent')
    return write(root/'journal/RETIRED.json',dict(absent=True,parent_fsynced=True,files=expected),16384,budget)

def run(s,source,bodies,manifest,origin,worker_end):
    repo=c.path(s['repository']);root=c.path(s['output']);budget=c.Budget(root,s['other_future_bytes'],worker_end)
    c.need(not os.path.lexists(root) and root.parent.is_dir() and not root.is_relative_to(repo),'fresh external output')
    c.need(root.parent.stat().st_dev==repo.stat().st_dev,'same volume custody');budget.capacity()
    budget.read(sum(len(x)+1 for x in bodies.values())+65536)
    binding=c.parse(bodies['BINDINGS.json']);policy.reviews(s,binding,budget);package=dependencies(repo,binding,budget)
    program=c.capture(s['program']['path'],131072,c.only_pin(s['program']),budget.tick,budget.read)
    c.need('\0' not in program.decode('utf-8'),'UTF8 standalone program')
    directory(root,budget)
    for name in ('cases','journal','commitment'):directory(root/name,budget)
    programs={}
    for role,body in [('candidate',program),('operator',bodies['baseline_program.py'])]:
        programs[role]=c.save(root/'commitment'/(role+'.py'),body,131072,budget.tick,budget.write);c.readable(root/'commitment'/(role+'.py'),budget.tick)
    for name in ('holder.py','candidate_entry.py'):
        c.save(root/'commitment'/name,bodies[name],16384,budget.tick,budget.write);c.readable(root/'commitment'/name,budget.tick)
    commitment=write(root/'commitment/COMMITMENT.json',dict(schema='neural035_program_commitment_v1',source=source,programs=programs,before_any_public_view=True,method_review=c.only_pin(s['method_review'])),8192,budget)
    completed=[];slots=['not_attempted']*2
    write(root/'INTENT.json',dict(source=source,programs=programs,commitment=commitment,feedback_withheld=True,slots=slots),8192,budget)
    try:
        current,expected,public=prepare(package,binding,root,budget)
        for case,role in enumerate(('candidate','operator')):
            seconds=s['candidate_seconds'] if case==0 else 300;phase_end=min(time.monotonic()+seconds+150,worker_end-100)
            c.need(time.monotonic()+seconds+145<phase_end,'complete phase allowance remains')
            budget.end=phase_end;signal.setitimer(signal.ITIMER_REAL,phase_end-time.monotonic())
            for rr,pin in programs.items():c.capture(root/'commitment'/(rr+'.py'),131072,pin,budget.tick,budget.read)
            for name in ('holder.py','candidate_entry.py'):c.capture(root/'commitment'/name,16384,manifest['files'][name],budget.tick,budget.read)
            attempt=root/'cases'/f'{case:02d}';directory(attempt,budget);budget.native(case);slots[case]='running'
            selected=dict(s,candidate_seconds=seconds)
            receipt=native.case(selected,root/'commitment',current,expected,root/'commitment'/(role+'.py'),attempt,case,source,budget,phase_end-30)
            c.need(receipt['status']=='captured' and receipt['role']==role,'closed complete role')
            raw=c.capture(attempt/'predictions.json',2000000,receipt['prediction'],budget.tick,budget.read)
            core.validate_submission(c.parse(raw),public)
            native_pin=c.pin(c.capture(attempt/'NATIVE.json',262144,tick=budget.tick,charge=budget.read))
            completed.append(dict(case=case,role=role,prediction=receipt['prediction'],native_receipt=native_pin,native_closed=True));slots[case]='closed'
            budget.end=worker_end;c.before(worker_end);signal.setitimer(signal.ITIMER_REAL,worker_end-time.monotonic())
        c.need(len(completed)==2 and slots==['closed','closed'],'all28 in both complete roles before collection')
        retirement=retire(current,expected,root,budget)
        docs=[c.parse(c.capture(root/'cases'/f'{i:02d}'/'predictions.json',2000000,r['prediction'],budget.tick,budget.read)) for i,r in enumerate(completed)]
        output.admit_pair(*docs,public,core)
        public_pin=c.save(root/'PUBLIC_MANIFEST.json',c.encoded(public),2000000,budget.tick,budget.write)
        result=dict(schema='neural035_full14_complete_v1',status='complete_unqualified',source=source,programs=programs,commitment=commitment,contexts=completed,public_manifest=public_pin,retirement=retirement,outputs=2,query_blocks_per_output=28,sessions=14,biological_mice=7,cells=1012,all_views_retired=True,private_grading_performed=False,target_bodies_opened=False,runtime_qualified=False,scientific_qualified=False,external_natural_zero_required=True,costs=budget.record())
        terminal=write(root/'COMPLETE.json',result,32768,budget);budget.tick()
        return dict(schema='neural035_full14_worker_v1',source=source,complete=terminal,outputs=2,status='complete_unqualified')
    except BaseException as exc:
        # The original worker deadline is never extended. Partial output is not success.
        try:write(root/'FAILURE.json',dict(error_type=type(exc).__name__,slots=slots,completed=len(completed),costs=budget.record(),recovery_may_be_required=True),16384,budget)
        except BaseException:pass
        raise
