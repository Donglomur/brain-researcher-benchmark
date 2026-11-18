"""One selected ordinary programme or exact fixed control over the existing case."""
import argparse
import os
from pathlib import Path
import sys
import time
from common import Engine,HostBudget,HERE,ROOT,need,regular,pin,lock,save,sync,strict,assets,output_hashes,owner
from protocol import PROTOCOL,ROUNDS,WARMUP,FIRST_BIN
from rtt_profile import IMAGE
from controller import participant,trusted,exact_pins,generated
from prepared_binding import RUN,packet,packet_private,admit
from programme_admission import selected,selected_programme,pin as body_pin,method
MANAGED=110000000
JOURNAL_CAP=101836800


def require_owned_activation(args):
    saved,bootstrap=owner.expected(RUN/'controller')
    need(saved['child_argv']==[sys.executable,str(HERE/'prepared_control.py'),'--run',str(RUN),'--deadline',str(args.deadline)]
         and saved['pid']==os.getppid()==os.getpgrp() and saved['pgid']==saved['pid']
         and 650<=saved['seconds']<=720 and saved['pid_recorded_before_activation']is True,
         'exact owned source-bound fixed-control activation')
    gate=owner.read(RUN/'controller/process_gate.json')
    need(gate=={'token':saved['token'],'activate':True},'durable activation before runtime')


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


def main(args):
    need(args.run==RUN and args.run.is_dir() and not args.run.is_symlink(),'fixed fresh runtime root')
    require_owned_activation(args)
    chosen=selected();run=args.run;budget=HostBudget(run,MANAGED,6000000)
    result={'status':'started','private_grader_dispatched':False,'private_read_accounting':None,
            'candidate_fit_count':0 if chosen['mode']=='calibration_rate' else None,
            'candidate_authorship':'disclosed_fixed_control' if chosen['mode']=='calibration_rate' else 'unknown',
            'candidate_training_policy_verified':chosen['mode']=='calibration_rate','new_reference_fits':0,'model_api_calls_by_controller':0,
            'host_neural_array_decodes':0,'trusted_count_decode_extent_unknown':False,
            'prepared_inputs_recomputed':False,'whole_benchmark_ready':False}
    try:
        need({x.name for x in run.iterdir()}=={'program.py','method.json','source_commit.json','controller'},'one fresh fixed-control attempt')
        for name,key,cap in(('program.py','programme',65536),('method.json','method',16384)):
            need(pin(run/name,cap)=={k:chosen[key][k]for k in('bytes','sha256')},'exact precommitted submitted bytes')
        declaration=method(regular(run/'method.json',16384));result['candidate_method_declaration']=declaration
        commitment=strict(regular(run/'source_commit.json',32768))
        need(commitment=={'mode':chosen['mode'],'programme':{k:chosen['programme'][k]for k in('bytes','sha256')},
             'method':{k:chosen['method'][k]for k in('bytes','sha256')},'before_candidate_activation':True,
             'before_first_request':True,'historical_preparation_preceded_commitment':True},'durable commitment precedes this activation, not historical preparation')
        if chosen['mode']=='calibration_rate':
            fixed=assets()['controls']['calibration_rate']
            need(commitment['programme']=={k:fixed['program'][k]for k in('bytes','sha256')}
                 and commitment['method']=={k:fixed['method'][k]for k in('bytes','sha256')},'fixed control branch remains exact')
        files,admission=admit(min(args.deadline-650,time.monotonic()+30))
        result['existing_case_admission']=save(run/'existing_case_admission.json',admission,budget,32768)
        schedule=strict(regular(packet_private('schedule.json'),2000000))
        need(set(schedule)=={'candidate_id','first_target_bin','warmup_rounds','scored_rounds','intervals'}
             and schedule['candidate_id']=='NEURAL-024' and schedule['first_target_bin']==FIRST_BIN
             and schedule['warmup_rounds']==WARMUP and schedule['scored_rounds']==22090,'original full native schedule')
        engine=Engine(args.deadline,run,budget);reply=engine.run(['image','inspect',IMAGE],cap=65536)
        need(reply.returncode==0,'existing exact image; no pull')
        image=strict(reply.stdout)[0];need(image['Id']==IMAGE,'fixed candidate and grader image')
        environment=dict(row.split('=',1)for row in image['Config']['Env'])
        save(run/'image.json',{'image':IMAGE,'environment':environment},budget)
        need(args.deadline-time.monotonic()>=650,'complete original600second candidate and grade windows')
        outcome=participant(run,schedule,files,budget,time.monotonic()+610,environment);result['candidate']=outcome
        need(outcome['all_owned_absent'] and outcome['attach_cli_reaped'] and not outcome['infrastructure_failure'],
             'candidate and attach absent before private grade')
        commits=run/'candidate/commits.jsonl'
        if not commits.exists():budget.write(commits,b'',receipt=True,mode=0o444)
        commits.chmod(0o444);sync(commits.parent)
        complete=outcome['status']=='complete' and outcome['committed']==ROUNDS
        grade=run/'grade';grade.mkdir(mode=0o700);(grade/'output').mkdir(mode=0o777);(grade/'output').chmod(0o777)
        private={name:files[name]for name in('prepare_receipt.json','observations.jsonl','schedule.json','references.json')}
        save(grade/'invocation.json',{'submission':pin(commits,JOURNAL_CAP,empty=True),
             'producer_stopped_attested':True,'protocol_complete':complete,'committed_rounds':outcome['committed'],
             'private_inputs':private},budget,32768)
        result.update(protocol_complete=complete,committed_prediction_count=outcome['committed'])
        need(args.deadline-time.monotonic()>=40,'full private grade and cleanup window')
        result['private_grader_dispatched']=True
        report=trusted(run,'grade',budget,time.monotonic()+40,environment)
        grade_files,grade_bytes=output_hashes(grade/'output',assets()['grade_output_caps'])
        exact_pins(report['files'])
        need(report['files']==grade_files and grade_bytes<=196608,'Exact complete score outputs')
        receipt=strict(regular(grade/'output/grade_receipt.json',65536))
        exact_pins(receipt['files'])
        counters=receipt['counters'];config=strict(regular(ROOT/assets()['scientific_inputs']['path'],64000))
        need(type(counters) is dict and set(counters)==set(assets()['grade_counter_names'])
             and all(type(v) is int and v>=0 for v in counters.values())
             and type(report['counters']) is dict and all(type(v) is int for v in report['counters'].values())
             and counters==report['counters'] and receipt['status']==report['status']
             and receipt['candidate_id']=='NEURAL-024' and receipt['protocol']==PROTOCOL
             and receipt['inputs_sha256']==assets()['scientific_inputs']['sha256']
             and receipt['invocation_sha256']==pin(grade/'invocation.json',32768)['sha256']
             and receipt['files']=={'score.json':grade_files['score.json']}
             and type(receipt['complete_scored_panel']) is bool
             and type(receipt['incomplete_operation_extent_unknown']) is bool
             and counters['scientific_fits']==counters['candidate_invocations']==0,
             'Exact sealed grading disposition, invocation and read counters')
        if report['status']=='scored':
            expected={'submission_reads_attempted':1,'submission_reads_completed':1,
                      'committed_rows_admitted':22100,'prediction_cells_admitted':2121600,
                      'private_reads_attempted':4,'private_reads_completed':4,
                      'private_observation_rows_decoded':22100,'prefix_request_hashes_verified':22100,
                      'generated_score_controls':8,'scored_rows':22090,'unscored_warmup_rows':10}
            need(complete and receipt['complete_scored_panel'] is True and receipt['error'] is None
                 and receipt['incomplete_operation_extent_unknown'] is False
                 and all(counters[k]==v for k,v in expected.items()),'Complete full scored support and private-read extent')
            generated(receipt['generated_checks'],'synthetic_private_poisson_score_checks_passed',8,
                      config['generated_controls']['grade_score'])
        elif report['status']=='invalid_submission':
            need(receipt['complete_scored_panel'] is False and receipt['invalid_submission_private_reads_zero'] is True
                 and counters['private_reads_attempted']==counters['private_reads_completed']==0
                 and counters['private_bytes_read']==0,'Public rejection precedes every private read')
        else:need(receipt['complete_scored_panel'] is False,'Numerical failure never becomes a score')
        result.update(status=report['status'],score=grade_files['score.json'],grade_receipt=grade_files['grade_receipt.json'],
                      grade_report=report,grade_accounting=receipt,candidate_chronology_verified=complete,
                      lawful_prefix_adaptation_allowed=True,fixed_model_only_enforced=False)

        checked=control_check(chosen['mode'],result,run)
        result['control_checks']=checked
        result['operation_mode']=chosen['mode']
        result['ordinary_scored_without_accuracy_floor']=chosen['mode']=='ordinary' and result['status']=='scored'
        if chosen['mode']=='calibration_rate':need(checked['passed'] is True,'exact fixed-control parity and zero gain')
    except BaseException as error:result.update(status='failed_preserved',error=repr(error)[:1500])
    finally:save(run/'result.json',result,budget,131072)
    return 0 if result['status']=='scored' and (chosen['mode']=='ordinary' or(result.get('control_checks')or{}).get('passed')is True)else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);parser.add_argument('--deadline',type=float,required=True)
    raise SystemExit(main(parser.parse_args()))
