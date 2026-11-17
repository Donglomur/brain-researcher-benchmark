"""Prospective full92 phase custody, not a scientific or runtime qualification."""
from pathlib import Path
import re
TASK='NEURAL-021'
RETAIN=268435456
SCOPE={'training_trials':272,'query_trials':92,'active_queries':52,'perturbation_queries':40,'units':65,'time_bins':30,'history_bins':6,'velocity_axes':2}

def whole(fit_seconds,infer_seconds):return fit_seconds+infer_seconds+1800

def selection(s,source):
    keys={'schema','execution_selected','task_id','repository','output','program','source','docker_binary','docker_socket','image','fit_seconds','infer_seconds','memory_bytes','other_future_bytes','scope','retained_bytes','managed_reads','managed_writes','whole_seconds','method_review','runtime_review','support_admission_authorized','numeric_grading_authorized'}
    c.need(type(s)is dict and set(s)==keys,'exact selection fields')
    c.need(s['schema']=='neural021_full92_program_selection_v1' and s['execution_selected'] is True and s['task_id']==TASK,'explicit full92 selection')
    c.need(s['source']==source and c.encoded(s['scope'])==c.encoded(SCOPE),'complete source-bound panel')
    c.need(s['support_admission_authorized'] is True and s['numeric_grading_authorized'] is False,'public format admission only; numerical grade separate')
    for key in ('fit_seconds','infer_seconds'):
        c.need(type(s[key])is int and 2<=s[key]<=7200,'each candidate phase2..7200 seconds')
    c.need(type(s['memory_bytes'])is int and 536870912<=s['memory_bytes']<=4294967296 and s['memory_bytes']%1048576==0,'candidate512MiB..4GiB')
    c.need(type(s['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',s['image']),'explicit immutable existing image')
    for key,value in [('retained_bytes',RETAIN),('managed_reads',c.READS+64000000),('managed_writes',c.WRITES+16384),('whole_seconds',whole(s['fit_seconds'],s['infer_seconds']))]:
        c.need(type(s[key])is int and s[key]==value,'fixed prospective full-panel budget')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh outside reservation')
    for key in ('repository','output','docker_binary','docker_socket'):
        c.need(type(s[key])is str and len(s[key].encode())<=512 and Path(s[key]).is_absolute(),'absolute bounded operand');c.path(s[key])
    for key,cap in [('program',1048576),('method_review',32768),('runtime_review',32768)]:
        p=s[key];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['path'])is str and Path(p['path']).is_absolute() and len(p['path'].encode())<=512,'pinned external input')
        c.need(c.only_pin(p)['bytes']<=cap,'pinned input cap');c.path(p['path'])
    return s

def reviews(s,budget):
    for name in ('method_review','runtime_review'):
        p=s[name];v=c.parse(c.capture(p['path'],32768,c.only_pin(p),budget.tick,budget.read))
        c.need(type(v)is dict and v.get('task_id')==TASK and v.get('approved') is True and v.get('source')==s['source'] and v.get('program')==c.only_pin(s['program']),'root-attested source/program review')
        c.need(type(v.get('other_future_bytes'))is int and v['other_future_bytes']==s['other_future_bytes'] and c.encoded(v.get('scope'))==c.encoded(s['scope']),'fresh authority and complete scope')
        if name=='method_review':
            c.need(v.get('schema')=='neural021_full92_method_review_v1','method review schema')
            for key in ('one_program_before_any_input','all272_train_92_queries_both_conditions','fit_view_has_no_query_values_or_cases','same_frozen_program_and_sealed_state_before_query','all_learned_transforms_models_tuning_use_training_only','training_retention_and_training_only_lazy_computation_permitted','full_query_batch_retrospective_not_streaming','all_null_negative_and_loss_dispositions_preserved','time_template_baseline_interpretation_preserved','no_private_target_or_roster_exposure','abi_and_prospective_state_budget_known_before_program_freeze'):
                c.need(v.get(key) is True,'reviewed method/access requirement: '+key)
            for key in ('phase_isolation_proves_semantic_training_compliance','all_fitting_must_finish_before_seal','scientific_or_baseline_outcome_already_measured','hashes_alone_prove_history'):
                c.need(v.get(key) is False,'explicit method-proof limitation: '+key)
        else:
            c.need(v.get('schema')=='neural021_runtime_profile_review_v1' and v.get('image')==s['image'] and all(type(v.get(k))is int and v[k]==s[k] for k in ('fit_seconds','infer_seconds','memory_bytes')),'exact reviewed runtime profile')
            c.need(v.get('runtime_versions')=={'python':'3.12.8','numpy':'2.2.6'},'selected dependency versions')
            c.need(type(v.get('state_cap_bytes'))is int and v['state_cap_bytes']==16777216 and type(v.get('submission_cap_bytes'))is int and v['submission_cap_bytes']==4194304,'prospective state and original output domains')
            c.need(v.get('native_full_panel_qualification_required_before_campaign') is True and v.get('qualification_inherited') is False,'no historical qualification transfer')
            c.need(v.get('independent_cli_groups_and_native_failure_recovery_acknowledged') is True,'honest failure ownership scope')
