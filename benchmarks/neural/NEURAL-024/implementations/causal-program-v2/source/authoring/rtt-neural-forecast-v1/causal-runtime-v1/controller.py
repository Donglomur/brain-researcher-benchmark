"""One persistent causal RTT candidate; all count feedback follows durable commit."""
import argparse
import hashlib
import os
import re
from pathlib import Path
import time
import uuid
from common import Engine,HostBudget,HERE,ROOT,need,regular,pin,lock,save,sync,strict,assets,output_hashes,stamp,seal_opaque
from rtt_profile import IMAGE,StreamEngine,mapping
from protocol import PROTOCOL,ROUNDS,WARMUP,FIRST_BIN,COMMIT_CAP,Gate,answer,decode,wire,wrapped
from stream import Stream
import rtt_recovery as recovery

MANAGED=175000000
JOURNAL_CAP=101836800


def remove(run,folder,engine,budget):
    return [recovery.recover(run,f,row,engine,budget) for f,row in recovery.inventory(run) if f==folder]


def trusted(run,label,budget,end,environment):
    folder=run/label
    if label=='grade':
        need(folder.is_dir() and {p.name for p in folder.iterdir()}=={'invocation.json','output'},'Exact grader precommit')
    else:folder.mkdir(mode=0o700)
    engine=StreamEngine(end,folder,budget);name='neural024-causal-'+label+'-'+uuid.uuid4().hex
    record={'label':label,'status':'started','trusted_work_extent_unknown':True}
    try:
        need(end-time.monotonic()>=35,'Full30second trusted worker plus immediate removal')
        _,record['boundary']=engine.create_task(name,label,mapping(run,label),environment)
        need(end-time.monotonic()>=33,'Unshortened30second trusted attachment')
        reply=engine.run(['start','--attach',name],timeout=30,cap=150000)
        budget.write(folder/'stdout.json',reply.stdout,receipt=True,mode=0o444)
        save(folder/'streams.json',{'returncode':reply.returncode,'stderr':reply.stderr.decode(errors='replace')},budget)
        report=strict(reply.stdout)
        record.update(status=report['status'],trusted_work_extent_unknown=False,retained_report=pin(folder/'stdout.json',150000))
        state=engine.inspect('container',name)['State']
        need(state['Status']=='exited' and state['Running'] is False and state['Pid']==0
             and state['OOMKilled'] is False and state['ExitCode']==reply.returncode and not reply.stderr,
             'Exact stopped trusted worker identity')
        expected=((reply.returncode,report['status'])==(0,'rtt_neural_causal_packet_prepared') if label=='prepare'
                  else reply.returncode==0 and report['status'] in ('scored','invalid_submission','numerical_failure'))
        need(expected,'Recognized complete trusted disposition')
        return report
    finally:
        try:record['cleanup']=remove(run,folder,engine,budget)
        except BaseException as error:record['cleanup']=[{'absence_verified':False,'error':repr(error)[:1000]}]
        save(folder/'execution.json',record,budget)
        need(record['cleanup'] and all(r['absence_verified'] for r in record['cleanup']),
             'Trusted producer absent before the next phase')


def exact_pins(value):
    need(type(value) is dict and all(type(name) is str and type(item) is dict
         and set(item)=={'bytes','sha256'} and type(item['bytes']) is int and item['bytes']>=0
         and type(item['sha256']) is str and re.fullmatch('[a-f0-9]{64}',item['sha256'])
         for name,item in value.items()),'Exact integer-byte SHA256 pin dictionary')


def generated(value,status,count,names,number_key='checks',names_key='names'):
    need(type(value) is dict and value['status']==status and type(value[number_key]) is int
         and value[number_key]==count and value[names_key]==names and len(names)==len(set(names))==count,
         'Exact generated guard roster and count')


def preparation(run,report,budget):
    held=assets();caps=held['preparation_output_caps'];files,total=output_hashes(run/'prepared',caps)
    exact_pins(report['files'])
    need(total<=57000000 and report['files']==files,'Exact bounded complete preparation outputs')
    receipt=strict(regular(run/'prepared/prepare_receipt.json',128000))
    need(receipt['status']=='rtt_neural_causal_packet_prepared' and receipt['candidate_id']=='NEURAL-024'
         and receipt['protocol']==PROTOCOL and receipt['complete'] is True and receipt['error'] is None
         and receipt['files']=={k:v for k,v in files.items() if k!='prepare_receipt.json'},'Complete prepared lineage')
    exact_pins(receipt['files'])
    expected=held['expected_preparation_counters']
    need(set(receipt['counters'])==set(expected) and all(type(report['counters'].get(k)) is int for k in expected)
         and all(type(receipt['counters'].get(k)) is int and receipt['counters'][k]==v for k,v in expected.items())
         and receipt['counters']==report['counters'] and receipt['native_clock_edges_modified'] is False
         and receipt['public_projection_members']==['counts','bin_edges_seconds']
         and receipt['private_future_rows']==ROUNDS and receipt['warmup_rows']==WARMUP and receipt['scored_rows']==22090
         and receipt['incomplete_operation_extent_unknown'] is False,'Exact complete projection extent; zero fits/behavior')
    config=strict(regular(ROOT/held['scientific_inputs']['path'],64000))
    guards=receipt['generated_checks']
    generated(guards['packet'],'packet_controls_passed',8,config['generated_controls']['prepare_packet'])
    generated(guards['calibration_candidate'],'passed',12,config['generated_controls']['prepare_fixed_candidate'],
              'guard_count','guards')
    need(guards['packet']['invented_only'] is True and guards['packet']['empirical_inputs_opened']==0
         and guards['packet']['model_fits']==0 and guards['calibration_candidate']['invented_only'] is True
         and guards['calibration_candidate']['empirical_data_files_opened']==0,'Generated-only preparation guards')
    need(receipt['inputs_sha256']==held['scientific_inputs']['sha256']
         and receipt['input_identity_pins']=={k:{f:v[f] for f in ('bytes','sha256')} for k,v in config['data'].items()}
         and receipt['reference_scores_pin']=={k:config['reference_scores'][k] for k in ('bytes','sha256')},
         'Exact scientific input and fixed-reference identities')
    save(run/'prepare/OUTPUT_HASHES.json',{'files':files,'bytes':total,'host_neural_array_decodes':0},budget)
    return files


def participant(run,schedule,files,budget,end,environment):
    folder=run/'candidate';folder.mkdir(mode=0o700)
    engine=StreamEngine(end,folder,budget);name='neural024-causal-candidate-'+uuid.uuid4().hex
    gate=Gate(schedule['intervals']);stream=None;journal=None;observations=None
    result={'status':'started','rounds_expected':ROUNDS,'scored_rounds_expected':22090,'committed':0,
            'feedback_rows_sent':0,'attach_cli_reaped':False,'stream_start_attempted':False,
            'attach_dispatch_or_reaping_extent_unknown':False,'create_verified':False,
            'infrastructure_failure':False,'candidate_fit_count':None,'host_neural_vector_decodes':0,
            'private_grading_reads':0,'errors':[]}
    path=folder/'commits.jsonl';obs_path=run/'prepared/observations.jsonl'
    try:
        need(end-time.monotonic()>=605,'Full600second candidate plus immediate removal')
        _,result['boundary']=engine.create_task(name,'candidate',mapping(run,'candidate'),environment)
        result['create_verified']=True
        need(end-time.monotonic()>=603,'Unshortened candidate wall allowance')
        candidate_end=time.monotonic()+600
        result.update(stream_start_attempted=True,attach_dispatch_or_reaping_extent_unknown=True)
        stream=Stream(name,candidate_end)
        need(decode(stream.line())=={'status':'ready'},'Exact startup handshake')
        stream.send(wire({'protocol':PROTOCOL,'status':'initialize','rounds':ROUNDS,'warmup_rounds':WARMUP,
                          'scored_rounds':22090,'channels':96,'mean_unit':'count_per_bin'}))
        need(decode(stream.line())=={'status':'initialized','protocol':PROTOCOL},'Exact protocol acknowledgement')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        journal=os.fdopen(fd,'wb');journal.flush();os.fsync(journal.fileno());sync(folder)
        fd=os.open(obs_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        observations=os.fdopen(fd,'rb');before=os.fstat(observations.fileno())
        need(before.st_size==files['observations.jsonl']['bytes'] and stamp(before)==stamp(obs_path.lstat()),
             'Exact sealed private stream descriptor')
        seen_bytes=0;observed_hash=hashlib.sha256();previous_observation=None
        for sequence in range(ROUNDS):
            need(time.monotonic()<candidate_end,'Candidate deadline before prediction request')
            request=gate.reveal(uuid.uuid4().hex)
            need(not stream.out,'No unsolicited or speculative response')
            body=wrapped(request,previous_observation)
            revealed=time.monotonic();stream.send(body)
            if previous_observation is not None:result['feedback_rows_sent']+=1
            response=answer(stream.line(),request)
            need(time.monotonic()<candidate_end,'Response admitted before absolute deadline')
            record={'sequence':sequence,'target_bin':FIRST_BIN+sequence,'scored':sequence>=WARMUP,
                    'nonce':request['nonce'],'request_sha256':hashlib.sha256(body).hexdigest(),
                    'mean_counts':response['mean_counts'],'previous_commit':gate.previous,
                    'revealed':revealed,'received':time.monotonic()}
            raw=wire(record);need(len(raw)<=COMMIT_CAP,'Compact complete96-vector commit')
            budget.check(len(raw))
            journal.write(raw);journal.flush();os.fsync(journal.fileno())
            need(time.monotonic()<candidate_end,'Durable commit before absolute deadline')
            gate.commit(response,raw,lock(raw),True);result['committed']=gate.position
            # No row read/forward authorization until ALL96 means are durably committed.
            gate.feedback(sequence)
            previous_observation=observations.readline(2049)
            need(0<len(previous_observation)<=2048 and previous_observation.endswith(b'\n'),
                 'One complete bounded private count-row frame')
            observed_hash.update(previous_observation);seen_bytes+=len(previous_observation)
        need(not observations.read(1) and seen_bytes==files['observations.jsonl']['bytes']
             and observed_hash.hexdigest()==files['observations.jsonl']['sha256']
             and stamp(before)==stamp(os.fstat(observations.fileno()))==stamp(obs_path.lstat()),
             'Exactly22100 sealed row frames; no private stream drift')
        observations.close();observations=None
        journal.close();journal=None;path.chmod(0o444);sync(folder)
        stop=wrapped({'protocol':PROTOCOL,'status':'stop','observation':None},previous_observation)
        need(not stream.out,'No trailing speculative prediction before final feedback')
        stream.send(stop);result['feedback_rows_sent']+=1
        need(decode(stream.line())=={'status':'stopped'},'Explicit final feedback/stop acknowledgement')
        stream.finish()
        need(time.monotonic()<candidate_end,'Complete shutdown inside candidate allowance')
        state=engine.inspect('container',name)['State']
        need(state['Status']=='exited' and state['Running'] is False and state['Pid']==0
             and state['ExitCode']==0 and state['OOMKilled'] is False and gate.position==ROUNDS
             and gate.pending is None and gate.feedback_released==ROUNDS and result['feedback_rows_sent']==ROUNDS,
             'Complete causal protocol and normal exit')
        result.update(status='complete',commit_file=pin(path,JOURNAL_CAP),last_commit=gate.previous,
                      candidate_wall_seconds=time.monotonic()-(candidate_end-600))
    except BaseException as error:
        result.update(status='invalid_or_failed_candidate',error=repr(error)[:1500])
        if not result['create_verified'] or stream is None:result.update(status='infrastructure_failure',infrastructure_failure=True)
    finally:
        for handle,label in ((journal,'journal_close'),(observations,'private_stream_close')):
            if handle is not None:
                try:handle.close()
                except BaseException as error:result['errors'].append({label:repr(error)[:500]})
        if stream is not None:
            try:
                result.update(stream.close());result['attach_dispatch_or_reaping_extent_unknown']=not result['attach_cli_reaped']
            except BaseException as error:result.update(attach_cli_reaped=False,attach_close_error=repr(error)[:1000])
            for label,data in (('stdout_prefix',bytes(stream.stdout)),('stderr',bytes(stream.stderr))):
                try:budget.write(folder/(label+'.bin'),data,receipt=True,mode=0o444)
                except BaseException as error:result['errors'].append({label+'_retention':repr(error)[:1000]})
        else:
            result.update(attach_cli_reaped=not result['stream_start_attempted'],candidate_start_not_dispatched=not result['stream_start_attempted'],
                          attach_dispatch_or_reaping_extent_unknown=result['stream_start_attempted'])
        try:result['cleanup']=remove(run,folder,engine,budget)
        except BaseException as error:result['cleanup']=[{'absence_verified':False,'error':repr(error)[:1000]}]
        result['all_owned_absent']=bool(result['cleanup']) and all(r['absence_verified'] for r in result['cleanup'])
        if result['errors'] and result['status']=='complete':result['status']='invalid_or_failed_candidate'
        if path.exists():
            if result['all_owned_absent'] and result['attach_cli_reaped']:
                result['retained_commits']=seal_opaque(path,JOURNAL_CAP)
            else:result['retained_commits']={'sealed':False,'extent_unknown':True,'reason':'Producer/attach cleanup unresolved'}
        save(folder/'outcome.json',result,budget)
    return result


def main(args):
    run=args.run;budget=HostBudget(run,MANAGED,6000000)
    result={'status':'started','private_grader_dispatched':False,'private_read_accounting':None,
            'trusted_count_decode_extent_unknown':False,'candidate_fit_count':None,'new_reference_fits':0,
            'model_api_calls_by_controller':0,'host_neural_array_decodes':0}
    try:
        from protocol_checks import run_checks
        checks=run_checks()
        generated(checks,'rtt_causal_protocol_generated_checks_passed',22,assets()['protocol_control_names'])
        save(run/'protocol_checks.json',checks,budget,65536)
        result['protocol_checks']=checks
        engine=Engine(args.deadline,run,budget);reply=engine.run(['image','inspect',IMAGE],cap=65536)
        need(reply.returncode==0,'Existing exact image; no pull')
        image=strict(reply.stdout)[0];need(image['Id']==IMAGE,'Fixed candidate/trusted image')
        environment=dict(row.split('=',1) for row in image['Config']['Env'])
        save(run/'image.json',{'image':IMAGE,'environment':environment},budget)
        (run/'prepared').mkdir(mode=0o777);(run/'prepared').chmod(0o777)
        need(args.deadline-time.monotonic()>=680,'Full preparation/candidate/grade and removal margins')
        budget.check(57000000)
        result['trusted_count_decode_extent_unknown']=True
        prep=trusted(run,'prepare',budget,time.monotonic()+40,environment)
        files=preparation(run,prep,budget)
        result.update(trusted_count_decode_extent_unknown=False,preparation_receipt=files['prepare_receipt.json'])
        schedule=strict(regular(run/'prepared/schedule.json',2000000))
        need(set(schedule)=={'candidate_id','first_target_bin','warmup_rounds','scored_rounds','intervals'}
             and schedule['candidate_id']=='NEURAL-024' and schedule['first_target_bin']==FIRST_BIN
             and schedule['warmup_rounds']==WARMUP and schedule['scored_rounds']==22090,'Exact native schedule metadata')
        need(args.deadline-time.monotonic()>=650,'Full candidate and grade windows')
        outcome=participant(run,schedule,files,budget,time.monotonic()+610,environment);result['candidate']=outcome
        need(outcome['all_owned_absent'] and outcome['attach_cli_reaped'] and not outcome['infrastructure_failure'],
             'Candidate and attach absent before any private grade')
        commits=run/'candidate/commits.jsonl'
        if not commits.exists():budget.write(commits,b'',receipt=True,mode=0o444)
        commits.chmod(0o444);sync(commits.parent)
        complete=outcome['status']=='complete' and outcome['committed']==ROUNDS
        grade=run/'grade';grade.mkdir(mode=0o700);(grade/'output').mkdir(mode=0o777);(grade/'output').chmod(0o777)
        private={name:files[name] for name in ('prepare_receipt.json','observations.jsonl','schedule.json','references.json')}
        save(grade/'invocation.json',{'submission':pin(commits,JOURNAL_CAP,empty=True),
             'producer_stopped_attested':True,'protocol_complete':complete,'committed_rounds':outcome['committed'],
             'private_inputs':private},budget,32768)
        result.update(protocol_complete=complete,committed_prediction_count=outcome['committed'])
        need(args.deadline-time.monotonic()>=40,'Full private grade and cleanup window')
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
    except BaseException as error:result.update(status='failed_preserved',error=repr(error)[:1500])
    finally:save(run/'result.json',result,budget,131072)
    return int(result['status']=='failed_preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);parser.add_argument('--deadline',type=float,required=True)
    raise SystemExit(main(parser.parse_args()))
