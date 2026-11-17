"""Prospective full-panel execution authority; no inherited runtime qualification."""
from pathlib import Path
import re
TASK='NEURAL-052'
RETAIN=201326592
ADMIT_SECONDS=300
def whole(seconds):return seconds+1200

def selection(s,source):
    keys={'schema','execution_selected','task_id','repository','output','program','source','docker_binary','docker_socket','image','candidate_seconds','memory_bytes','other_future_bytes','scope','retained_bytes','managed_reads','managed_writes','whole_seconds','method_review','runtime_review','support_admission_authorized','numeric_grading_authorized'}
    c.need(type(s)is dict and set(s)==keys,'exact selection fields')
    c.need(s['schema']=='neural052_full3_program_selection_v1' and s['execution_selected'] is True and s['task_id']==TASK,'explicit whole3 selection')
    c.need(s['source']==source and s['scope']=={'participants':['01','02','03'],'rows_per_person':1200,'total_rows':3600,'folds_per_person':15,'fixed_models':4,'shared_concept_draws':1000},'complete source-bound panel')
    c.need(s['support_admission_authorized'] is True and s['numeric_grading_authorized'] is False,'auxiliary admission only; numerical grade separate')
    c.need(type(s['candidate_seconds'])is int and 2<=s['candidate_seconds']<=7200,'candidate2..7200 seconds')
    c.need(type(s['memory_bytes'])is int and 536870912<=s['memory_bytes']<=4294967296 and s['memory_bytes']%1048576==0,'candidate512MiB..4GiB')
    c.need(type(s['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',s['image']),'explicit immutable existing image')
    for k,v in [('retained_bytes',RETAIN),('managed_reads',c.READS+16000000),('managed_writes',c.WRITES+16384),('whole_seconds',whole(s['candidate_seconds']))]:
        c.need(type(s[k])is int and s[k]==v,'fixed prospective full-panel budget')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh outside reservation')
    for k in ('repository','output','docker_binary','docker_socket'):
        c.need(type(s[k])is str and len(s[k].encode())<=512 and Path(s[k]).is_absolute(),'absolute bounded operand');c.path(s[k])
    for k,cap in [('program',1048576),('method_review',32768),('runtime_review',32768)]:
        p=s[k];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['path'])is str and Path(p['path']).is_absolute() and len(p['path'].encode())<=512,'pinned external input')
        c.need(c.only_pin(p)['bytes']<=cap,'pinned input cap');c.path(p['path'])
    return s

def reviews(s,budget):
    for name in ('method_review','runtime_review'):
        p=s[name];v=c.parse(c.capture(p['path'],32768,c.only_pin(p),budget.tick,budget.read))
        c.need(type(v)is dict and v.get('task_id')==TASK and v.get('approved') is True and v.get('source')==s['source'] and v.get('program')==c.only_pin(s['program']),'root-attested exact source/program review')
        c.need(v.get('other_future_bytes')==s['other_future_bytes'] and v.get('scope')==s['scope'],'fresh authority and full scope')
        if name=='method_review':
            c.need(v.get('schema')=='neural052_full3_method_review_v1','method review schema')
            for key in ('all3_people_3600_rows_complete_voxels','one_program_before_signal_access','responses_and_labels_intentionally_public','fixed15_fold_four_model_protocol','shared1000_concept_bootstraps_without_refit','all_null_and_support_dispositions_preserved','complete_two_file_output_before_feedback','no_private_source_exposure'):
                c.need(v.get(key) is True,'reviewed scientific/access requirement: '+key)
            c.need(v.get('numerical_agreement_proves_scientific_reasoning') is False,'no numerical-to-reasoning inference')
            c.need(v.get('hashes_alone_prove_chronology') is False,'external authority, not hash-derived authorship')
        else:
            c.need(v.get('schema')=='neural052_runtime_profile_review_v1' and v.get('image')==s['image'] and v.get('candidate_seconds')==s['candidate_seconds'] and v.get('memory_bytes')==s['memory_bytes'],'exact reviewed runtime profile')
            c.need(v.get('runtime_versions')=={'python':'3.12.8','numpy':'2.2.6'},'selected dependency versions')
            c.need(v.get('native_full_panel_qualification_required_before_campaign') is True and v.get('qualification_inherited') is False,'no historical qualification transfer')
            c.need(v.get('independent_cli_groups_and_native_failure_recovery_acknowledged') is True,'honest failure ownership scope')
