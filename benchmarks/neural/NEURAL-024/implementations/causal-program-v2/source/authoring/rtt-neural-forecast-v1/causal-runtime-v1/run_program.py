#!/usr/bin/env python3
"""One explicitly granted persistent causal RTT program; executed BrainWide lifecycle."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
sys.dont_write_bytecode = True
from common import HERE, ROOT, Engine, HostBudget, owner, module, need, regular, pin, lock, strict, save, sync, assets, pinned, seal_opaque
import rtt_recovery as recovery

START=float(os.environ['NEURAL024_ORIGIN']);WHOLE=780;WORK=720;END=START+WHOLE
need(math.isfinite(START) and 0<=time.monotonic()-START<60, 'Original portable launch origin; no refreshed startup budget')
RESERVE=176000000;MANAGED=175000000;RECEIPT_RESERVE=6000000
IMAGE_METADATA=2517190392
ADDITIONAL_IMAGE='sha256:5d20a9fb1ac170089acc608a66fdb041ed811541093f12db7e7a5e5288d9fed7'


def terminal(*unused):os._exit(124)
def cleanup_alarm():
    signal.signal(signal.SIGALRM,terminal);signal.setitimer(signal.ITIMER_REAL,max(.001,END-time.monotonic()))
def work_alarm(*unused):
    cleanup_alarm();raise TimeoutError('Work deadline; exact cleanup only')
def interrupted(*unused):raise InterruptedError('Operator interrupted; preserve partials and exact cleanup')


def exact_int(value,minimum=0):return type(value) is int and value>=minimum

def method(body):
    value=strict(body)
    need(type(value) is dict and set(value)=={'schema_version','method_id','method_description','training_policy','limitations'}
         and type(value['schema_version']) is int and value['schema_version']==1,'Exact method declaration')
    need(all(type(v) is str and 0<len(v)<=4096 for k,v in value.items() if k!='schema_version'),'Bounded method text')
    return value


def source_gate(args):
    raw=regular(HERE/'FREEZE.json',500000);freeze=strict(raw)
    need(regular(HERE/'SOURCE_CLOSURE_PROPOSAL.json',500000)==raw,'Exact reviewed held source proposal')
    review_raw=regular(args.review,65536)
    need(hashlib.sha256(review_raw).hexdigest()==os.environ.get('NEURAL024_REVIEW_SHA256'),
         'Same captured portable operator review')
    review=strict(review_raw);digest=hashlib.sha256(raw).hexdigest();run=args.output.absolute()
    need(type(review.get('operator_docker_host')) is str
         and review['operator_docker_host']==os.environ.get('NEURAL024_DOCKER_HOST')
         and review['operator_docker_host'].startswith('unix:///')
         and not any(ord(c)<=32 for c in review['operator_docker_host'])
         and not os.environ.get('DOCKER_CONTEXT'), 'Explicit selected local socket; no inherited context')
    expected={'decision':'authorize_one_neural024_causal_program_attempt','execution_authority':True,
              'freeze_sha256':digest,'whole_seconds':WHOLE,'work_seconds':WORK,'candidate_seconds':600,
              'cleanup_seconds':60,'artifact_reserve_bytes':RESERVE,'control':args.control,
              'other_reserve_bytes':args.other_reserve_bytes,'output_path':str(run.relative_to(ROOT))}
    need(all(review.get(k)==v for k,v in expected.items()) and review['execution_authority'] is True,
         'Exact prospective single-attempt authority')
    need(all(type(review[k]) is int for k in ('whole_seconds','work_seconds','candidate_seconds','cleanup_seconds',
                                             'artifact_reserve_bytes','other_reserve_bytes')),'Exact integer allowances')
    need(exact_int(args.other_reserve_bytes,352000000),'Current standing102MB and other250MB reservations retained')
    need(run.parent==ROOT/'artifacts-build' and not run.exists() and '..' not in run.parts
         and all(not p.is_symlink() for p in (run,*run.parents)),'Fresh direct output')
    for relative,expected_pin in freeze['files'].items():
        need(not Path(relative).is_absolute() and '..' not in Path(relative).parts,'Relative source closure')
        need(pin(ROOT/relative,3000000)==expected_pin,'Exact source closure: '+relative)
    peer=pinned(review['independent_source_review'],300000)
    need(peer['decision']=='go_for_neural024_causal_program_v1' and peer['source_proposal_sha256']==digest,
         'Independent review of exact causal boundary/source')
    need(assets()['binding_status']=='bound_scientific_source','Held science bindings required')
    # Original binary packets are stat-only here. The trusted preparer hashes and decodes them.
    for item in assets()['original_inputs'].values():
        path=ROOT/item['path'];st=path.lstat()
        need(not Path(item['path']).is_absolute() and '..' not in Path(item['path']).parts
             and all(not p.is_symlink() for p in (path,*path.parents)) and stat.S_ISREG(st.st_mode)
             and st.st_nlink==1 and st.st_size==item['bytes'] and st.st_mode&0o004,'Exact public-source input metadata')
    return review,freeze


def prior_gate(review,freeze_sha):
    previous_receipt=review['prior_receipt'];value=pinned(previous_receipt,300000)
    if previous_receipt==assets()['reference_receipt']:
        need(value['candidate_id']=='NEURAL-024' and value['status']=='rtt_neural_forecast_reference_completed'
             and value['all_owned_absent'] is True and value['attach_cli_reaped'] is True
             and value['known_charged_seconds_after']==2020 and value['charged_reference_allocation_seconds']==600,
             'Exact completed fixed-reference prior; retained RTT history1420+600')
        previous=2020
    else:
        need(value['candidate_id']=='NEURAL-024' and value['task_family']=='rtt_neural_causal_forecast'
             and value['source_freeze_sha256'] in (freeze_sha, '48ef3ea8f5dbfac57a4e0633d8245da59ff061a61cc5830d0b0c3e7e653e2299') and value['historical_lifetime_complete'] is False
             and value['all_owned_absent'] is True and value['all_activated_groups_absent'] is True
             and value['charged_seconds']>=WHOLE,'Latest same-wrapper closed attempt including failure charges')
        previous=value['known_family_allowances_seconds_after']
    need(type(previous) in (int,float) and math.isfinite(previous) and previous>=2800
         and review['prior_known_seconds']==previous and review['prospective_after_seconds']==previous+WHOLE,
         'No cumulative allowance reset')
    allocation=pinned(review['budget_allocation'],65536)
    expected={'candidate_id':'NEURAL-024','authorized':True,'whole_seconds':WHOLE,'work_seconds':WORK,
              'candidate_seconds':600,'cleanup_seconds':60,'own_reserve_bytes':RESERVE,
              'other_reserve_bytes':review['other_reserve_bytes'],'prior_known_seconds':previous,
              'prospective_after_seconds':previous+WHOLE,'historical_lifetime_complete':False,
              'program':review['program'],'method':review['method'],'control':review['control'],
              'output_path':review['output_path'],'freeze_sha256':freeze_sha}
    need(all(allocation.get(k)==v for k,v in expected.items()) and allocation['authorized'] is True
         and allocation['historical_lifetime_complete'] is False,'Separate full prospective attempt allocation')
    need(all(type(allocation[k]) is int for k in ('whole_seconds','work_seconds','candidate_seconds',
              'cleanup_seconds','own_reserve_bytes','other_reserve_bytes')),'Exact allocated integer bounds')
    return previous


def storage(review,deadline):
    policy=pinned(review['capacity_policy'],65536)
    expected={'scope_id':'neural024_causal_program_v1','execution_authority':False,'allocation':False,
              'own_reserve_bytes':RESERVE,'free_after_reserves_floor_bytes':15000000000,
              'other_reserve_bytes_minimum':352000000,'managed_file_bytes_cap':MANAGED,
              'filesystem_rounding_reserve_bytes':1000000,'maximum_managed_entries':200,
              'filesystem_fragment_bytes_cap':4096,'whole_seconds':WHOLE,'work_seconds':WORK,
              'cleanup_seconds':60,'original_image_metadata_baseline_bytes':1339047331,
              'additional_retained_image_id':ADDITIONAL_IMAGE,'additional_retained_image_metadata_bytes':1178143061,
              'fixed_existing_image_metadata_bytes':IMAGE_METADATA,'aggregate_ceiling_bytes':22000000000}
    need(all(policy.get(k)==v for k,v in expected.items()) and policy['execution_authority'] is False
         and policy['allocation'] is False,'Exact prospective capacity policy; never execution authority')
    need(review['additional_image_size_evidence']==assets()['additional_image_size_evidence'],'Exact retained-image inspection source')
    image_evidence=pinned(review['additional_image_size_evidence'],300000)
    inspected=strict(image_evidence['stdout'])
    need(image_evidence['returncode']==0 and image_evidence['all_cli_calls_reaped'] is True and not image_evidence['stderr']
         and type(inspected) is list and len(inspected)==1 and inspected[0]['Id']==ADDITIONAL_IMAGE
         and type(inspected[0]['Size']) is int and inspected[0]['Size']==1178143061,
         'Actual full additional image size retained, regardless of its consumption admission')
    rows=review['other_reservations']
    need(type(rows) is list and 1<=len(rows)<=32 and len(json.dumps(rows).encode())<=16384
         and all(type(row) is dict and set(row)=={'scope','bytes','basis'} and exact_int(row['bytes'],1)
                 and type(row['scope']) is str and 0<len(row['scope'])<=200
                 and type(row['basis']) is str and 0<len(row['basis'])<=2000 for row in rows)
         and sum(row['bytes'] for row in rows)==review['other_reserve_bytes'],'Bounded complete concurrent reservations')
    reply=subprocess.run(['/usr/bin/du','-sk',str(ROOT)],capture_output=True,text=True,
                         timeout=min(5,max(.001,deadline-time.monotonic())),check=True)
    need(len(reply.stdout)<1024 and len(reply.stderr)<1024,'Bounded current capacity metadata')
    project=int(reply.stdout.split()[0])*1024;fs=os.statvfs(ROOT);free=fs.f_bavail*fs.f_frsize
    need(0<fs.f_frsize<=4096,'One-megabyte rounding reserve for at most200 entries')
    reserve=RESERVE+review['other_reserve_bytes']
    need(project+IMAGE_METADATA+reserve<=22000000000 and free-reserve>=15000000000,
         'Fresh measured capacity includes both images in full and every reservation')
    return {'project_allocated_bytes':project,'free_bytes':free,'image_metadata_bytes':IMAGE_METADATA,
            'original_image_metadata_baseline_bytes':1339047331,'additional_retained_image_id':ADDITIONAL_IMAGE,
            'additional_retained_image_metadata_bytes':1178143061,
            'additional_image_size_evidence':review['additional_image_size_evidence'],
            'image_metadata_is_not_physical_Docker_disk_measurement':True,'layer_deduplication_discount':False,
            'own_reserve_bytes':RESERVE,'other_reserve_bytes':review['other_reserve_bytes'],
            'other_reservations':rows,'aggregate_ceiling_bytes':22000000000,'fragment_bytes':fs.f_frsize,
            'capacity_policy':review['capacity_policy']}


def control_check(label,child,run):
    if label=='ordinary':return None
    need(label=='calibration_rate' and child['status']=='scored' and child['committed_prediction_count']==22100
         and child['protocol_complete'] is True and child['candidate_chronology_verified'] is True,
         'Complete full-support disclosed calibration-rate control')
    score=strict(regular(run/'grade/output/score.json',131072))
    check=score['calibration_rate_control']
    need(check['exact_parity'] is True and check['zero_primary_gain'] is True,
         'Exact full saved calibration-rate metrics and zero signed gain; no tolerance substitution')
    return {'label':label,'passed':True,'calibration_rate_control':check,'candidate_optimizer_fits':0,
            'source_disclosed_and_independently_written':True,'ordinary_accuracy_floor':False,
            'empirical_calls':22100,'warmup_calls':10,'scored_rows':22090,'scored_channels':96}


def execute(args,review,freeze):
    run=args.output.absolute();budget=HostBudget(run,MANAGED,RECEIPT_RESERVE)
    folder=run/'controller';process=None;work_end=START+WORK
    freeze_sha=pin(HERE/'FREEZE.json',500000)['sha256'];previous=prior_gate(review,freeze_sha)
    result={'candidate_id':'NEURAL-024','task_family':'rtt_neural_causal_forecast','status':'started',
            'source_freeze_sha256':freeze_sha,'control':args.control,'prior_known_seconds':previous,
            'candidate_source':review['program'],'candidate_method':review['method'],
            'all_owned_absent':False,'all_activated_groups_absent':False,'candidate_fit_count':None,
            'new_reference_fits':0,'model_API_calls':0,'host_neural_array_decodes':0,
            'trusted_count_decode_extent_unknown':False,'private_grader_dispatched':False,
            'private_read_accounting':None,'historical_lifetime_complete':False,'historical_total_seconds':None,
            'automatic_retry':False,'new_benchmark_IDs':0,'research_qualified':False,
            'lawful_prefix_online_learning_allowed':True,'fixed_weights_for_arbitrary_code_enforced':False}
    try:
        result['storage']=storage(review,work_end)
        for name,path,cap in (('program.py',args.program,65536),('method.json',args.method,16384)):
            body=regular(path,cap);need(lock(body)==review[name.split('.')[0]],'Exact precommitted source/method')
            if name=='method.json':method(body)
            else:body.decode('utf-8')
            budget.write(run/name,body,mode=0o444)
            fd=os.open(run/name,os.O_RDONLY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        sync(run)
        save(run/'source_commit.json',{'program':review['program'],'method':review['method'],
                                     'before_trusted_projection':True},budget)
        if args.control!='ordinary':
            expected=assets()['controls'][args.control]
            need(review['program']=={k:expected['program'][k] for k in ('bytes','sha256')}
                 and review['method']=={k:expected['method'][k] for k in ('bytes','sha256')},'Exact disclosed first control')
        folder.mkdir(mode=0o700);relative=str((HERE/'controller.py').relative_to(ROOT))
        source={'path':relative,**freeze['files'][relative]}
        need(work_end-time.monotonic()>=690,'Full680phase windows plus controller setup')
        result.update(trusted_count_decode_extent_unknown=True,private_read_accounting=None)
        process=owner.launch([sys.executable,str(HERE/'controller.py'),'--run',str(run),'--deadline',str(work_end)],
                             folder,min(760,work_end-time.monotonic()+1),source)
        helper=module(ROOT/'authoring/paper-language-project/phase1-numerical-v1/run_outer.py','_rtt_causal_wait')
        done=helper.completed(folder,work_end,owner)
        stopped=owner.stop(folder,min(END-5,time.monotonic()+3),process);process=None
        need(stopped['absence_verified'],'Controller absent before independent resource recovery')
        child=strict(regular(run/'result.json',131072))
        result.update(status=child['status'],controller_result=pin(run/'result.json',131072),score=child.get('score'),
                      trusted_count_decode_extent_unknown=child['trusted_count_decode_extent_unknown'],
                      private_grader_dispatched=child['private_grader_dispatched'],
                      private_read_accounting=child.get('grade_accounting'),
                      committed_prediction_count=child.get('committed_prediction_count'),
                      candidate_chronology_verified=child.get('candidate_chronology_verified',False),
                      protocol_complete=child.get('protocol_complete',False),protocol_checks=child.get('protocol_checks'))
        need(done['returncode']==0,'Complete controller disposition; failures preserved')
        checked=control_check(args.control,child,run)
        if checked is not None:result.update(control_checks=checked,candidate_fit_count=0)
    except BaseException as error:result.update(status='failed_preserved',error=repr(error)[:1500])
    finally:
        cleanup_alarm()
        try:stopped=owner.stop(folder,min(END-4,time.monotonic()+5),process) if folder.exists() else {'absence_verified':True,'never_activated':True}
        except BaseException as error:stopped={'absence_verified':False,'error':repr(error)[:1000]}
        result['all_activated_groups_absent']=stopped['absence_verified']
        try:result['group_cleanup']=save(run/'group_cleanup.json',stopped,budget,150000)
        except BaseException as error:result.update(group_cleanup_retention_error=repr(error)[:1000],status='failed_preserved')
        try:
            need(stopped['absence_verified'],'Controller absence before exact independent resource recovery')
            rows=recovery.recover_all(run,Engine(END-.5,run,budget),budget)
            result['cleanup']=rows;result['all_owned_absent']=all(row['absence_verified'] for row in rows)
            result['cleanup_evidence_retention_failed']=any(row.get('evidence_retention_failed',False) for row in rows)
            if result['cleanup_evidence_retention_failed']:result['status']='failed_preserved'
            if result['status'] in ('scored','invalid_submission','numerical_failure'):
                need(len(rows)==3,'Exactly preparation/candidate/grade resource identities')
        except BaseException as error:result.update(all_owned_absent=False,cleanup_error=repr(error)[:1000])
        journal=run/'candidate/commits.jsonl'
        if result['all_owned_absent'] and result['all_activated_groups_absent']:
            try:
                result['retained_commit_journal']=({'present':True,'sealed_after_all_owned_absence':True,
                     **seal_opaque(journal,101836800)} if journal.exists() else
                     {'present':False,'sealed_after_all_owned_absence':False,'extent_unknown':False})
            except BaseException as error:
                result.update(status='failed_preserved',retained_commit_journal={'sealed':False,
                              'extent_unknown':True,'error':repr(error)[:1000]})
        else:result['retained_commit_journal']={'sealed':False,'extent_unknown':True,
                                               'reason':'Group or container absence unresolved; no seal attempted'}
        elapsed=time.monotonic()-START;charge=max(WHOLE,elapsed)
        result.update(wall_seconds_before_receipt=elapsed,charged_seconds=charge,
                      known_family_allowances_seconds_after=previous+charge,retained_bytes_before_receipt=budget.used())
        entries=list(run.rglob('*'))
        need(len(entries)+2<=200 and all(not p.is_symlink() for p in entries),'Bounded200entry scope including fallback')
        if not result['all_owned_absent'] or not result['all_activated_groups_absent']:result['status']='cleanup_unverified'
        if elapsed>=WHOLE:result['status']='deadline_exceeded'
        save(run/'outer_receipt.json',result,budget,131072)
    print(json.dumps({'status':result['status'],'charged_seconds':result['charged_seconds']}),flush=True)
    if time.monotonic()>=END:return 1
    return int(result['status'] not in ('scored','invalid_submission','numerical_failure'))


def main():
    parser=argparse.ArgumentParser()
    for name in ('program','method','review','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--other-reserve-bytes',type=int,required=True)
    parser.add_argument('--control',choices=('ordinary','calibration_rate'),default='ordinary')
    args=parser.parse_args();need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'No inherited timer')
    signal.signal(signal.SIGALRM,work_alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,START+WORK-time.monotonic()))
    started=False;finalized=False
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
    try:
        review,freeze=source_gate(args)
        run=args.output.absolute();run.mkdir(mode=0o700);started=True
        budget=HostBudget(run,MANAGED,RECEIPT_RESERVE)
        save(run/'charge_intent.json',{'candidate_id':'NEURAL-024','whole_seconds':WHOLE,
             'prior_known_seconds':review['prior_known_seconds'],'automatic_retry':False},budget,16384)
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','NUMBA_NUM_THREADS'):
            os.environ[key]='1'
        os.environ['PYTHONDONTWRITEBYTECODE']='1'
        code=execute(args,review,freeze);finalized=True
        return code
    finally:
        cleanup_alarm()
        if started and not finalized:
            elapsed=time.monotonic()-START
            save(args.output/'outer_failure.json',{'status':'failed_preserved','charged_seconds':max(WHOLE,elapsed),
                 'prior_known_seconds':review['prior_known_seconds'],
                 'known_family_allowances_seconds_after':review['prior_known_seconds']+max(WHOLE,elapsed),
                 'cleanup_claim':'unknown; inspect owned journals',
                 'original_outer_path_present':(args.output/'outer_receipt.json').exists(),
                 'original_outer_completion_or_durability_not_assumed':True,
                 'historical_lifetime_complete':False,'automatic_retry':False},HostBudget(args.output,MANAGED,RECEIPT_RESERVE),16384)


if __name__=='__main__':raise SystemExit(main())
