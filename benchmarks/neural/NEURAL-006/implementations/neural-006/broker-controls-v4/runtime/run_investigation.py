#!/usr/bin/env python3
"""Complete NEURAL006 source entry; no execution is selected by supplying this source."""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
from model_broker import BrokerActors, authenticate_broker
from analysis import aggregate, audit_reference, agree, predictions, score_case, summarize_replicates
from custody import Custody, parse
from projection import project, permute_targets, make_case, reserve_packets
from model_state import ModelVault, freeze_reference, reference_view
from protocol import ACTIVE, RESERVE, ARMS, TARGETS, canonical, case_roster, digest, exact_keys, need, schedule, validate_plan

CORE_BYTES=11784
CORE_SHA256='4fecbfb5f705ef9efb8fc1deda69916f1cdd4a00d6064c42926976266a7eded7'

def admission_read(path,cap):
    path=Path(path);need(all(not p.is_symlink() for p in (path,*path.parents)),'admission_symlink')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size<=cap,'admission_extent')
        chunks=[];remaining=a.st_size
        while remaining:
            block=os.read(fd,min(remaining,65536));need(block,'admission_short_read');chunks.append(block);remaining-=len(block)
        need(not os.read(fd,1),'admission_growth');b=os.fstat(fd)
        need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'admission_changed')
        return b''.join(chunks)
    finally:os.close(fd)

def descriptor_read(custody,row):
    exact_keys(row,('path','bytes','sha256'),'descriptor_fields')
    need(type(row['path']) is str and Path(row['path']).is_absolute(),'absolute_input_descriptor')
    return custody.read(Path(row['path']),row['bytes'],row['sha256'])

def authenticate(selection,plan,custody):
    exact_keys(selection,('schema','execution_authorized','plan','source_manifest','programs','core',
        'docker','image','release_record','broker'),'selection_fields')
    need(selection['schema']=='neural006-broker-root-selection-v1' and selection['execution_authorized'] is True,'explicit_future_execution_selection')
    body=descriptor_read(custody,selection['plan']);need(parse(body)==plan,'plan_identity')
    source_body=descriptor_read(custody,selection['source_manifest'])
    need(hashlib.sha256(source_body).hexdigest()==plan['source_sha256'],'source_manifest_binding')
    source=parse(source_body);exact_keys(source,('schema','files'),'source_manifest_fields')
    need(source['schema']=='neural006-operative-source-v1' and type(source['files']) is list,'source_manifest_schema')
    source_root=Path(__file__).resolve().parent;expected={
        'protocol.py','projection.py','analysis.py','custody.py','actors.py','investigation.py',
        'run_investigation.py','reference_worker.R','TASK.md','launch.py','model_state.py','reference_stream.py',
        'model_broker.py','candidate_relay.py','provider_worker.py'}
    need({Path(row['path']).name for row in source['files']}==expected and len(source['files'])==len(expected),'complete_source_closure')
    sources={}
    for row in source['files']:
        need(Path(row['path']).parent==source_root,'operative_source_location')
        name=Path(row['path']).name;body=__verified_source_capture__[name]
        need(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],'loaded_source_identity')
        sources[name]=body
    need(hashlib.sha256(source_body).hexdigest()==__verified_manifest_sha256__,'loaded_manifest_identity')
    core=selection['core'];need(core['bytes']==CORE_BYTES and core['sha256']==CORE_SHA256,'original_numerical_kernel')
    core_body=descriptor_read(custody,core)
    exact_keys(selection['programs'],('frozen_program','adaptive_investigation'),'program_modes')
    programs={}
    for mode,row in selection['programs'].items():
        need(row['bytes']<=131072,'candidate_source_cap');programs[mode]=descriptor_read(custody,row)
    broker_config=parse(descriptor_read(custody,selection['broker']))
    broker_admission=authenticate_broker(custody,broker_config,sources,plan['source_sha256'],programs)
    recipe={'broker_sha256':selection['broker']['sha256'],'programs':{mode:row['sha256'] for mode,row in selection['programs'].items()},
        'candidate_seeds':plan['candidate_seeds'],'source_sha256':plan['source_sha256'],
        'development_tuning':plan['development_tuning']}
    need(digest(recipe)==plan['recipe_sha256'],'recipe_frozen_before_queries')
    if plan['stage']=='reserved_frozen33_test8':
        release_body=descriptor_read(custody,selection['release_record'])
        grant=plan['reserve_authorization'];need(hashlib.sha256(release_body).hexdigest()==grant['cross_family_release_record_sha256'],'release_identity')
        release=parse(release_body)
        exact_keys(release,('schema','assessment_id','reserved_ids','frozen_recipe_sha256','release_selected'),'release_fields')
        need(release=={'schema':'neural006-cross-family-reserve-release-v1','assessment_id':grant['assessment_id'],
            'reserved_ids':list(RESERVE),'frozen_recipe_sha256':plan['recipe_sha256'],'release_selected':True},'actual_cross_family_release')
    else:need(selection['release_record'] is None,'no_reserve_release_for_development')
    return sources,core_body,programs,broker_config,broker_admission

def run(plan,selection,data_root,custody):
    sources,core_body,programs,broker_config,broker_admission=authenticate(selection,plan,custody);replicates=schedule(plan)
    expected_cases=sum(len(case_roster(plan,row)) for row in replicates)
    need(expected_cases<=plan['limits']['max_cases'],'prospective_complete_case_cap')
    reference_calls=8 if plan['stage']=='reserved_frozen33_test8' else expected_cases*8
    containers=19 if plan['stage']=='reserved_frozen33_test8' else expected_cases*3
    proposed_files=80 if plan['stage']=='reserved_frozen33_test8' else expected_cases*33+len(replicates)+8
    proposed_files+=5*broker_config['limits']['calls_total']+1
    need(proposed_files<=plan['limits']['max_files'],'prospective_full_file_cap')
    need(reference_calls<=plan['limits']['max_fit_calls'],'prospective_reference_fit_cap')
    need(containers*16*(plan['limits']['candidate_seconds_per_case']+plan['limits']['cleanup_seconds'])<=plan['limits']['cpu_seconds'],'prospective_complete_cpu_cap')
    actors=BrokerActors(custody,selection['image'],selection['docker'],sources,core_body,programs,
                  plan['candidate_seeds'],plan['recipe_sha256'],broker_config=broker_config,broker_admission=broker_admission)
    custody.write('ACTUAL_PLAN.json',plan);custody.write('ACTUAL_SELECTION.json',selection)
    custody.write('frozen_schedule.json',{'plan_sha256':digest(plan),'replicates':replicates,
        'expected_cases':expected_cases,'biological_people':33 if plan['stage']=='development_lopo33' else 8,
        'train26':list(__import__('protocol').TRAIN),'dev7':list(__import__('protocol').DEV),'reserve8':list(RESERVE)})
    data=project(custody.read,Path(data_root),plan['stage']);outputs=[];case_number=0
    if plan['stage']=='reserved_frozen33_test8':
        return run_reserved(plan,actors,data,custody,replicates)
    for replicate in replicates:
        records=[];pending=[];rep_error=None
        altered=permute_targets(data,replicate['permutation']) if replicate['kind']=='trajectory_permutation' else data
        for person,weight in case_roster(plan,replicate):
            case_number+=1;record={'participant':person,'status':'entered','weight':weight,
                'kind':replicate['kind'],'replicate':replicate['replicate']}
            try:
                custody.check();case,truth=make_case(altered,person,replicate['draw'],plan['stage'])
                record['case_sha256']=digest(case);reference=actors.reference(case)
                custody.write('reference-%06d.json'%case_number,reference)
                record['reference_arithmetic_audit']=audit_reference(case,reference)
                need(reference['status']=='complete','reference_fit_failure')
                candidates={};investigations={}
                for mode in plan['candidate_modes']:
                    value=actors.candidate(mode,case,reference)
                    custody.write('%s-%06d.json'%(mode,case_number),value)
                    predictions(value['predictions'],case) # Target-free validation before any private scoring.
                    candidates[mode]=value['predictions'];investigations[mode]=value
                # Retain the compact scoring inputs, not33 duplicate full training projections.
                pending.append((record,{'participant':person,'query':case['query']},truth,reference,candidates))
                record['status']='predictions_committed'
            except BaseException as error:
                custody.event('case',error);record.update(status='failed',error={'class':type(error).__name__,'message':str(error)[:1024]})
                rep_error=error
            finally:
                records.append(record);custody.write('production-%06d.json'%case_number,record,diagnostic=rep_error is not None)
            if rep_error is not None:break
        if rep_error is None:
            try:
                # EVERY person/mode is produced, exited and removed before the first private score.
                need(len(pending)==len(case_roster(plan,replicate)),'all_producers_committed_before_scoring')
                for offset,(record,case,truth,reference,candidates) in enumerate(pending):
                    custody.check();record['score']=score_case(case,truth,reference,candidates);record['status']='complete'
                    custody.write('score-%04d-%02d.json'%(len(outputs),offset),record)
                result=aggregate(plan,replicate,records)
            except BaseException as error:
                custody.event('private_scoring',error);rep_error=error
        if rep_error is not None:
            entered={r['participant'] for r in records}
            records.extend({'participant':p,'status':'not_entered_after_failure','weight':w}
                           for p,w in case_roster(plan,replicate) if p not in entered)
            result={'kind':replicate['kind'],'replicate':replicate['replicate'],'status':'incomplete','cases':records,
                    'macro':None,'contrasts':None}
        outputs.append(result);custody.write('replicate-%04d.json'%len(outputs),result,diagnostic=rep_error is not None)
        if rep_error is not None:
            outputs.extend({'kind':r['kind'],'replicate':r['replicate'],'status':'not_entered_after_failure'}
                           for r in replicates[len(outputs):]);break
    summary=summarize_replicates(plan,replicates,outputs)
    summary.update(stage=plan['stage'],source_order_alignment_independently_proven=False,
                   reserved8_used=plan['stage']=='reserved_frozen33_test8',actor_records=actors.records)
    return summary

def run_reserved(plan,actors,data,custody,replicates):
    """Fit each recipe once on33; immutable state is reused for all8 inference cases."""
    records=[];pending=[];models={};reference_model=None;error=None;vault=None
    replicate=replicates[0]
    try:
        training,batch,queries,truth=reserve_packets(data)
        training_fingerprint=digest(training)
        vault=ModelVault(custody,plan['recipe_sha256'],training_fingerprint,plan['candidate_seeds'])
        reference=actors.reference(batch)
        custody.write('reserve-reference-training.json',reference)
        audit=audit_reference(batch,reference)
        custody.write('reserve-reference-audit.json',audit)
        need(reference['status']=='complete','reserved_reference_fit_failure')
        reference_model=vault.publish('reference',freeze_reference(reference,training))
        for mode in plan['candidate_modes']:
            artifact=actors.train_candidate(mode,training,reference_model,vault)
            models[mode]=vault.publish(mode,artifact)
            custody.write('frozen-'+mode+'-lineage.json',{
                **vault.describe(models[mode],mode),'tool_history':artifact['tool_history']})
        custody.write('ALL_MODELS_FROZEN.json',{
            'training_fingerprint':training_fingerprint,
            'reference_model':vault.describe(reference_model,'reference'),
            'candidate_models':{mode:vault.describe(model,mode) for mode,model in models.items()},
            'reference_fits_total':8,'candidate_training_invocations':2,
            'candidate_internal_fit_counts':'unmeasured; source/recipe and native budget remain obligations',
            'reserve_targets_used_in_training':False})
        # Candidate inference sees only its frozen state, current unlabeled query and authorized tool replies.
        for index,person in enumerate(sorted(RESERVE)):
            custody.check();case=queries[person]
            view=reference_view(vault,reference_model,case,plan['recipe_sha256'],training_fingerprint)
            source_index={key:i for i,key in enumerate(reference['source_rows'])}
            for target in TARGETS:
                for arm in ARMS:
                    for key,predicted in zip(view['source_rows'],view['results'][target]['arms'][arm]['prediction']):
                        expected=reference['results'][target]['arms'][arm]['prediction'][source_index[key]]
                        agree(predicted,expected,'frozen_state_prediction_matches_native_population_prediction')
            record={'participant':person,'status':'entered',
                'reference_model_sha256':vault.describe(reference_model,'reference')['sha256'],
                'candidate_model_sha256':{mode:vault.describe(model,mode)['sha256'] for mode,model in models.items()}}
            records.append(record);candidates={}
            for mode in plan['candidate_modes']:
                value=actors.candidate(mode,case,view,models[mode],training,vault)
                custody.write('reserve-'+mode+'-%02d.json'%index,value)
                predictions(value['predictions'],case)
                candidates[mode]=value['predictions']
            record['status']='predictions_committed'
            custody.write('reserve-production-%02d.json'%index,record)
            pending.append((record,case,truth[person],view,candidates))
        need(len(pending)==8 and all(record['status']=='predictions_committed' for record in records),
             'all8_validated_and_committed_before_scoring')
        custody.check()
        for index,(record,case,held,view,candidates) in enumerate(pending):
            custody.check()
            record['score']=score_case(case,held,view,candidates);record['status']='complete'
            custody.write('reserve-score-%02d.json'%index,record)
        result=aggregate(plan,replicate,records)
    except BaseException as failure:
        error=failure;custody.event('reserved_confirmation',failure)
        entered={record['participant'] for record in records}
        records.extend({'participant':p,'status':'not_entered_after_failure'} for p in sorted(RESERVE) if p not in entered)
        result={'kind':'observed','replicate':0,'status':'incomplete','cases':records,'macro':None,'contrasts':None}
    custody.write('reserve-assessment.json',result,diagnostic=error is not None)
    summary=summarize_replicates(plan,replicates,[result])
    summary.update(stage=plan['stage'],reserved8_used=True,actor_records=actors.records,
        fitted_state_policy='one_common_33_trained_artifact_per_recipe_reused_across_all8',
        reference_fit_calls_total=custody.fit_calls,
        frozen_candidate_artifacts={mode:vault.describe(model,mode)['sha256'] for mode,model in models.items()},
        source_order_alignment_independently_proven=False)
    return summary

def main():
    need('__verified_source_capture__' in globals(),'verified_byte_launcher_required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',required=True);parser.add_argument('--data-root',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    # This bounded admission precedes the campaign and cannot itself grant scientific authority.
    selection_body=admission_read(args.selection,65536);selection=parse(selection_body)
    need(type(selection) is dict and type(selection.get('plan')) is dict,'selection_plan')
    plan_body=admission_read(selection['plan']['path'],65536);plan=validate_plan(parse(plan_body))
    custody=Custody(args.output,plan['limits'],__verified_start_monotonic__);result=None;primary=None
    custody.read_bytes=__verified_bootstrap_read_bytes__+len(selection_body)+len(plan_body)
    try:
        need(custody.read_bytes<=plan['limits']['read_bytes'],'bootstrap_read_reservation')
        result=run(plan,selection,args.data_root,custody)
        need(result['status']=='complete','incomplete_investigation')
        custody.write('RESULT.json',result)
    except BaseException as error:
        primary=error;custody.event('campaign',error)
        try:custody.write('FAILURE.json',{'status':'failed','error':{'class':type(error).__name__,'message':str(error)},
            'partial_summary':result,'custody':custody.evidence(),'qualification':False},diagnostic=True)
        except BaseException as secondary:custody.event('failure_publication',secondary)
    finally:
        if hasattr(custody,'model_broker'):
            try:custody.model_broker.close()
            except BaseException as error:
                custody.event('model_broker_closure',error)
                if primary is None:primary=error
        try:custody.write('CUSTODY.json',custody.evidence(),diagnostic=True)
        except BaseException as error:
            custody.event('custody_publication',error)
            if primary is None:primary=error
    try:custody.check(cleanup=True)
    except BaseException as error:
        custody.event('final_publication_horizon',error)
        if primary is None:primary=error
    if custody.first_error is not None:primary=custody.first_error
    final={'status':'failed' if primary else 'complete','events':custody.events,
           'scientifically_qualified':False,'evidence_scope':'known events before this single terminal transport'}
    try:
        body=canonical(final);need(len(body)<=24576,'terminal_projection_cap')
        sys.stdout.write(body.decode());sys.stdout.flush()
        custody.check(cleanup=True)
    except BaseException as error:
        custody.event('terminal_transport',error)
        if primary is None:primary=error
        # One bounded fallback, never a retry loop or a successful fallback verdict.
        try:
            fallback=canonical({'status':'failed','events':custody.events,
                'evidence_scope':'known events before single fallback; a failed last transport remains incomplete'})
            need(len(fallback)<=24576,'fallback_projection_cap');sys.stderr.write(fallback.decode());sys.stderr.flush()
            custody.check(cleanup=True)
        except BaseException as secondary:
            custody.event('last_transport_incomplete',secondary)
    return 1 if primary is not None else 0

if __name__=='__main__':raise SystemExit('Use the verified-byte launch.py entry with -I -S -B.')
