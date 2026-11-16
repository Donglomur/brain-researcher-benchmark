"""Task-local serial A/B successor of the existing cardiac protected outer.

Inert until exact root-selected admission/runtime/ownership evidence is bound.
There is deliberately no supplied-summary argument or per-arm grade path.
"""
import argparse
import math
import os
from pathlib import Path
import signal
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import execution_support as S

WHOLE_SECONDS=420
WORK_SECONDS=360
ARM_SECONDS=160
START=time.monotonic()
WORK=START+WORK_SECONDS
END=START+WHOLE_SECONDS

def checked(value,cap=131072):
    S.need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Bound exact external metadata descriptor')
    body=S.ordinary(value['path'],cap)
    S.need(S.pin(body)=={k:value[k] for k in ('bytes','sha256')},'Exact selected bytes')
    return body

def authenticate(review,output,pair_root):
    S.need(review.get('schema')=='cardiac_paired_program_execution_request_v1' and review.get('candidate_id')==S.ID,'Current paired execution request')
    S.need(review.get('execution_authority') is True and review.get('automatic_retry') is False,'Explicit once-only external operation selection')
    S.need(review.get('runtime_image')==S.IMAGE,'Exact385454 profile;9aaf is not a replacement')
    S.need(review.get('whole_seconds')==WHOLE_SECONDS and review.get('work_seconds')==WORK_SECONDS and review.get('cleanup_seconds')==60,'Paired whole clock preserves per-arm bounds')
    S.need(review.get('output_path')==str(output) and review.get('pair_root')==str(pair_root),'Selected fresh output and physical pair')
    S.need(review.get('runtime_admission') is not None and review.get('capacity_admission') is not None,'Current runtime and whole-pair capacity evidence remain required')
    runtime=S.decode(checked(review['runtime_admission']))
    capacity=S.decode(checked(review['capacity_admission']))
    # These are root-reviewed task-local admission records. Their identities and
    # exact required statements are checked; source does not invent observations.
    S.need(runtime.get('candidate_id')==S.ID and runtime.get('image')==S.IMAGE and runtime.get('accepted') is True and runtime.get('current_paired_profile_reviewed') is True,'Actual matching runtime evidence, not source qualification')
    S.need(capacity.get('candidate_id')==S.ID and capacity.get('admitted') is True and capacity.get('output_path')==str(output) and capacity.get('whole_seconds')==WHOLE_SECONDS and capacity.get('fresh_for_this_once_operation') is True,'Existing operator fresh admission bound to this pair')
    S.need(review.get('operator_admission_reviewed') is True,'Trusted operator adopts evidence semantics, not arbitrary JSON truth')
    old=S.decode(checked(review['latest_accounting_evidence']))
    prior=review.get('prior_known_seconds')
    S.need(type(prior) in (int,float) and math.isfinite(prior) and prior>=4415 and old.get('candidate_id')==S.ID and old.get('known_after_seconds')==prior,'Carried same-family closed costs')
    S.need(old.get('all_owned_absent') is True and old.get('all_activated_groups_absent') is True,'Previous owned execution closed')
    S.need(S.pin(S.ordinary(pair_root/'receipt.json',100000))==review.get('pair_receipt'),'Physical pair receipt fixed before execution')
    S.need(set(review.get('programs',{}))=={'A','B'},'Both committed programs required')
    S.bind_packet(review['packet_binding'])
    return prior

def commit_programs(review,run,pair_root,budget):
    programs={c:checked(review['programs'][c]) for c in ('A','B')}
    S.need(all(0<len(x)<=131072 for x in programs.values()),'Bounded two-program capture')
    # Commit both programs before either arm's complete public-file release.
    for c in ('A','B'):
        folder=run/c;folder.mkdir(mode=0o700)
        budget.write(folder/'program.py',programs[c],mode=0o444)
        S.save(folder/'source_commit.json',{'condition':c,'program':S.pin(programs[c]),'before_either_arm_input_release':True},budget)
    for c in ('A','B'):
        folder=run/c
        value={'candidate_id':S.ID,'condition':c,'pair_root':str(pair_root),'pair_receipt':review['pair_receipt'],'program_path':str(folder/'program.py'),'program_sha256':S.pin(programs[c])['sha256'],'unit':S.expected_unit(pair_root,c),'packet_binding':S._BINDING,'docker':review['docker']}
        S.save(folder/'runtime_manifest.json',value,budget)
        S.save(folder/'runtime_manifest_commit.json',{'manifest':S.pin(S.ordinary(folder/'runtime_manifest.json',32768)),'before_any_Docker_resource_creation':True},budget)
    return {c:S.pin(programs[c]) for c in ('A','B')}

def recover_arm(run,budget,end):
    lib=S.api();strict=S.recovery();owned,errors=strict.inventory(run);rows=[]
    for folder,item in owned:
        try:rows.append(strict.recover(run,folder,item,lib['BaseEngine'](end,folder,budget),budget))
        except BaseException as error:rows.append({'name':item.get('name'),'absence_verified':False,'error':repr(error)[:1000]})
    return {'resources':rows,'inventory_errors':errors,'absence_verified':not errors and all(x['absence_verified'] for x in rows)}

def owned_arm(run,owner,budget,descriptor,end):
    folder=run/'controller';folder.mkdir(mode=0o700);process=None;completion=None;stopped=None
    try:
        S.need(time.monotonic()<end-151,'Full equal candidate allowance plus owned orchestration')
        argv=[sys.executable,str(S.ROOT/descriptor['path']),'--run',str(run),'--work-end',str(end)]
        process=owner.launch(argv,folder,min(170,end-time.monotonic()+1),descriptor)
        while not (folder/'process_completion.json').exists():
            S.need(time.monotonic()<end and process.poll() is None,'Bounded owned arm controller')
            time.sleep(.01)
        completion=owner.read(folder/'process_completion.json');identity=owner.read(folder/'process_owner.json')
        S.need(completion['token']==identity['token'] and completion['group_leader_waits_for_owner_stop'],'Exact process completion')
    finally:
        stopped=owner.stop(folder,min(END-.5,time.monotonic()+1),process)
        S.save(run/'group_absence.json',stopped,budget)
        S.need(stopped['absence_verified'],'Owned host group must close before Docker recovery')
        recovery=recover_arm(run,budget,min(END-.5,time.monotonic()+15))
        S.save(run/'outer_absence.json',recovery,budget)
        S.need(recovery['absence_verified'],'All exact native resources absent')
    S.need(completion is not None and completion['returncode']==0,'Handled candidate result, not infrastructure failure')
    child=S.read(run/'controller_result.json');S.need(child['all_workers_absent'] and child['handled_candidate_outcome'],'Complete arm closure')
    raw=S.ordinary(run/'unit/outcome_commit.json')
    S.need(S.pin(raw)['sha256']==child['outcome_commit_sha256'],'Immutable producer outcome commitment')
    outcome=S.decode(raw)
    S.need(outcome['condition']==run.name and outcome['all_unit_resources_absent'] and outcome['before_any_private_grade'],'Exact arm outcome')
    return {'condition':run.name,'group_absent':True,'native_absent':True,'outcome':outcome,'outcome_pin':S.pin(raw)}

def finalize_pair(pair_root,run,closed,budget):
    S.need(set(closed)=={'A','B'} and all(closed[c]['condition']==c and closed[c]['group_absent'] is True and closed[c]['native_absent'] is True for c in ('A','B')),'Both owned arms closed before any private reference')
    pair=S.packet();paired=sys.modules['_cardiac_current_pair']
    candidates={};invalid={}
    for c in ('A','B'):
        arm=run/c;outcome=closed[c]['outcome']
        S.need(S.pin(S.ordinary(arm/'unit/outcome_commit.json'))==closed[c]['outcome_pin'],'Closed outcome drift')
        if outcome['unit_status']!='unit_committed':
            invalid[c]=outcome['unit_status'];continue
        manifest=S.runtime_manifest(arm)
        S.need(manifest['program_sha256']==outcome['program_sha256'],'Executed committed program identity')
        commit_raw=S.ordinary(arm/'unit/commit.json')
        S.need(S.pin(commit_raw)['sha256']==outcome['producer_output_commit_sha256'],'Protected collector commitment')
        commit=S.decode(commit_raw)
        S.need(commit['program_sha256']==outcome['program_sha256'] and commit['output']==outcome['output'] and commit['producer_removed_before_capture'] is True and commit['all_candidate_holder_volume_absent'] is True,'Actual producer-to-output lineage and closure')
        raw=S.ordinary(arm/'unit/summary.json',200000)
        S.need(S.pin(raw)==outcome['output'],'Only protected captured output may be graded')
        try:
            candidate=paired.S.validate(paired.decode(raw))
            S.need(candidate['input_sha256']==pair.spec['scope']['input_sha256'],'Exact scientific input identity')
            candidates[c]=candidate
        except ValueError as error:invalid[c]={'status':'invalid_submission','error':str(error)[:1000]}
    S.save(run/'PAIR_CLOSED.json',{'arms':closed,'before_any_private_grade':True},budget)
    if invalid:
        result={'status':'pair_has_unscored_candidate_outcome','arms':invalid,'private_reference_reads':0,'scientific_success':None}
        S.save(run/'pair_result.json',result,budget,private=True);return result
    captures={}
    for c in ('A','B'):
        dest=run/(c+'.capture');budget.check(400000,receipt=True)
        captures[c]=pair.capture(pair_root,c,pair_root/(c+'.request.json'),run/c/'program.py',run/c/'unit/summary.json',dest)
    budget.check(1000000,receipt=True)
    # Unchanged paired scorer revalidates BOTH captured artifacts before target
    # access and uses its repaired0600 writer. It never executes either program.
    result=pair.score_pair(pair_root,run/'A.capture',run/'B.capture',run/'private_score.json')
    S.need((run/'private_score.json').stat().st_mode&0o777==0o600,'Private report access mode')
    S.need((run/'private_score.json').stat().st_size<=1000000,'Bounded complete paired report')
    return {'status':'paired_outputs_scored','private_reference_reads':1,'scientific_success':None,'score':S.pin(S.ordinary(run/'private_score.json',1000000)),'limits':'Executed output lineage only; no data-dependence, convergence, authoring-isolation or measured code-benefit guarantee.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',required=True,type=Path);p.add_argument('--root-selected-once',action='store_true');a=p.parse_args()
    S.need(a.root_selected_once,'Explicit external once selection')
    S.need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'No conflicting inherited alarm')
    def hard_stop(*unused):os._exit(124)
    def cleanup_clock():signal.signal(signal.SIGALRM,hard_stop);signal.setitimer(signal.ITIMER_REAL,max(.001,END-time.monotonic()))
    def work_stop(*unused):cleanup_clock();raise TimeoutError('Whole pair work deadline; cleanup only')
    old=signal.getsignal(signal.SIGALRM);signal.signal(signal.SIGALRM,work_stop);signal.setitimer(signal.ITIMER_REAL,max(.001,WORK-time.monotonic()))
    run=None;budget=None;owner=None;closed={};handlers={};prior=None;started=False
    result={'candidate_id':S.ID,'status':'operator_error','private_reference_reads':0,'automatic_retry':False,'historical_environment_reproduced':False,'all_owned_absent':False,'all_activated_groups_absent':False}
    try:
        review=S.read(a.review);run=S.unlinked(review['output_path']);pair_root=S.unlinked(review['pair_root'])
        S.need(not run.exists() and run.parent.is_dir() and run!=pair_root and run not in pair_root.parents and pair_root not in run.parents and not run.is_relative_to(S.ROOT),'Fresh external output separate from source/pair')
        run.mkdir(mode=0o700);started=True
        prior=authenticate(review,run,pair_root)
        lib=S.api();budget=lib['HostBudget'](run,15000000,3600000)
        owner=S.owner(a.review,Path(__file__).resolve())
        controller=review['controller'];S.need(controller['path']==(S.LOCAL/'arm_controller.py').relative_to(S.ROOT).as_posix(),'Exact task-local controller')
        S.need(S.pin(S.source(controller['path']))=={k:controller[k] for k in ('bytes','sha256')},'Frozen controller')
        S.need(time.monotonic()<WORK-340,'Whole pair orchestration room before input release')
        result['programs']=commit_programs(review,run,pair_root,budget)
        for sig in (signal.SIGINT,signal.SIGTERM):
            handlers[sig]=signal.getsignal(sig);signal.signal(sig,lambda *_:(_ for _ in ()).throw(InterruptedError('Paired outer interrupted')))
        for c in ('A','B'):
            closed[c]=owned_arm(run/c,owner,budget,controller,min(WORK-10,time.monotonic()+ARM_SECONDS))
        result['private_reference_reads']=None # unknown until complete private stage returns
        result.update(finalize_pair(pair_root,run,closed,budget))
    except BaseException as error:result['error']=repr(error)[:2000]
    finally:
        cleanup_clock();groups=[];native=[]
        for c in ('A','B') if started else ():
            arm=run/c
            if not arm.exists():continue
            group=None
            try:
                if owner is None:group={'absence_verified':not (arm/'controller/process_gate.json').exists()}
                else:group=owner.stop(arm/'controller',min(END-.5,time.monotonic()+1))
                groups.append(group);S.need(group['absence_verified'],'Group closure before exact resource cleanup')
                native.append(recover_arm(arm,budget,END-.5))
            except BaseException as error:
                if group is None:
                    groups.append({'condition':c,'absence_verified':False,'error':repr(error)[:1000],'closure_state':'unknown; stop did not return'})
                native.append({'absence_verified':False,'error':repr(error)[:1000]})
        result['all_activated_groups_absent']=all(x['absence_verified'] for x in groups)
        result['all_owned_absent']=all(x['absence_verified'] for x in native)
        result['closure']={'groups':groups,'native':native}
        result.update(charged_seconds=max(WHOLE_SECONDS,time.monotonic()-START),prior_known_seconds=prior)
        result['known_after_seconds']=None if prior is None else prior+result['charged_seconds']
        if not result['all_owned_absent'] or not result['all_activated_groups_absent']:result['status']='cleanup_unverified'
        if started:
            if budget is not None:S.save(run/'outer_receipt.json',result,budget,250000,private=True)
            else:
                body=S.encode(result);S.need(len(body)<=16384,'Bounded pre-admission failure receipt')
                fd=os.open(run/'preflight_failure.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        for sig,handler in handlers.items():signal.signal(sig,handler)
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
    print(S.encode({'status':result['status'],'all_owned_absent':result['all_owned_absent'],'all_activated_groups_absent':result['all_activated_groups_absent']}).decode(),end='')
    return 0 if result['status'] in ('paired_outputs_scored','pair_has_unscored_candidate_outcome') and result['all_owned_absent'] and result['all_activated_groups_absent'] else 2

if __name__=='__main__':raise SystemExit(main())
