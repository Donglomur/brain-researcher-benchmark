"""New prospective complete-public-membership profile; no inherited qualification."""
from pathlib import Path
import re
TASK='NEURAL-038'
RETAIN=96000000
ADMIT_SECONDS=300
SCOPE=dict(memberships=140,blocks=[dict(block_id=n,rows=r,frames=f,conditions=k) for n,r,f,k in [('original_expt1',9,300,5),('original_expt2',13,300,5),('original_expt3',10,300,5),('revision_pool',108,200,3)]],public_members=25,array_members=18,declared_numeric_operands=866)
def whole(seconds):return seconds+1200

def selection(s,source):
    keys={'schema','execution_selected','task_id','repository','output','program','source','docker_binary','docker_socket','image','candidate_seconds','memory_bytes','other_future_bytes','scope','retained_bytes','managed_reads','managed_writes','whole_seconds','method_review','runtime_review','support_admission_authorized','numeric_grading_authorized'}
    c.need(type(s)is dict and set(s)==keys,'exact selection fields')
    c.need(s['schema']=='neural038_full140_program_selection_v1' and s['execution_selected'] is True and s['task_id']==TASK,'explicit complete140 selection')
    c.need(s['source']==source and c.encoded(s['scope'])==c.encoded(SCOPE),'complete source-bound panel')
    c.need(s['support_admission_authorized'] is True and s['numeric_grading_authorized'] is False,'public schema/support admission only')
    c.need(type(s['candidate_seconds'])is int and s['candidate_seconds']==600,'new complete investigation600-second candidate profile')
    c.need(type(s['memory_bytes'])is int and s['memory_bytes']==1073741824,'new complete investigation1GiB candidate profile')
    c.need(type(s['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',s['image']),'explicit immutable existing image')
    for k,v in [('retained_bytes',RETAIN),('managed_reads',c.READS+20000000),('managed_writes',c.WRITES+16384),('whole_seconds',whole(s['candidate_seconds']))]:
        c.need(type(s[k])is int and s[k]==v,'fixed prospective complete-panel budget')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh outside reservation')
    for k in ('repository','output','docker_binary','docker_socket'):
        c.need(type(s[k])is str and len(s[k].encode())<=512 and Path(s[k]).is_absolute(),'absolute bounded operand');c.path(s[k])
    for k,cap in [('program',131072),('method_review',32768),('runtime_review',32768)]:
        p=s[k];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['path'])is str and Path(p['path']).is_absolute() and len(p['path'].encode())<=512,'pinned external input')
        c.need(c.only_pin(p)['bytes']<=cap,'pinned input cap');c.path(p['path'])
    return s

def reviews(s,budget):
    for name in ('method_review','runtime_review'):
        p=s[name];v=c.parse(c.capture(p['path'],32768,c.only_pin(p),budget.tick,budget.read))
        c.need(type(v)is dict and v.get('task_id')==TASK and v.get('approved') is True and v.get('source')==s['source'] and v.get('program')==c.only_pin(s['program']),'root-attested exact source/program review')
        c.need(type(v.get('other_future_bytes'))is int and v['other_future_bytes']==s['other_future_bytes'] and c.encoded(v.get('scope'))==c.encoded(s['scope']),'fresh authority and full scope')
        if name=='method_review':
            c.need(v.get('schema')=='neural038_full140_method_review_v1','method review schema')
            for key in ('all140_memberships_and_four_blocks','one_program_before_public_input_access','full_public_covariates_intentionally_visible','fixed_native_frames_and_separate_revision','all_null_and_support_dispositions_preserved','complete_report_before_feedback','no_private_answer_exposure'):
                c.need(v.get(key) is True,'reviewed scientific/access requirement: '+key)
            for key in ('numeric_agreement_proves_neural_understanding','heldout_generalization_or_paper_parity','hashes_alone_prove_chronology'):
                c.need(v.get(key) is False,'bounded interpretation: '+key)
        else:
            c.need(v.get('schema')=='neural038_runtime_profile_review_v1' and v.get('image')==s['image'],'exact new image profile')
            for key in ('candidate_seconds','memory_bytes','docker_binary','docker_socket'):
                c.need(type(v.get(key))is type(s[key]) and v[key]==s[key],'exact reviewed runtime operand: '+key)
            c.need(v.get('runtime_versions')=={'python':'3.12','numpy':'2.2.6'},'selected dependency versions')
            c.need(v.get('native_full_panel_qualification_required_before_campaign') is True and v.get('qualification_inherited') is False,'no prior or answer-host qualification transfer')
            c.need(v.get('independent_cli_groups_and_native_failure_recovery_acknowledged') is True,'honest failure ownership scope')
