"""Explicit source/runtime selection; never grants current execution authority."""
from pathlib import Path
TASK='NEURAL-035'
def whole(seconds):return seconds+900
def selection(s,source):
    keys={'schema','execution_selected','task_id','repository','output','program','source','docker_binary','docker_socket','candidate_seconds','operator_seconds','memory_bytes','other_future_bytes','contexts','retained_bytes','managed_reads','managed_writes','whole_seconds','method_review','runtime_review','private_grading_authorized'}
    c.need(type(s)is dict and set(s)==keys and s['schema']=='neural035_full14_program_selection_v1' and s['execution_selected']is True and s['task_id']==TASK,'explicit complete selection')
    c.need(s['private_grading_authorized']is False and s['source']==source and s['contexts']==[0,1] and all(type(x)is int for x in s['contexts']),'two complete public phases, no grade')
    c.need(type(s['candidate_seconds'])is int and 1<=s['candidate_seconds']<=7200 and type(s['operator_seconds'])is int and s['operator_seconds']==300,'bounded full phases')
    c.need(type(s['memory_bytes'])is int and 536870912<=s['memory_bytes']<=4294967296 and s['memory_bytes']%1048576==0,'prospective memory')
    for k,v in [('retained_bytes',c.RETAIN),('managed_reads',c.READS+16777216),('managed_writes',c.WRITES+16384),('whole_seconds',whole(s['candidate_seconds']))]:
        c.need(type(s[k])is int and s[k]==v,'complete resource profile')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh OTHER')
    for k in ('repository','output','docker_binary','docker_socket'):
        c.need(type(s[k])is str and len(s[k].encode())<=512 and Path(s[k]).is_absolute(),'absolute bounded operand');c.path(s[k])
    for k,cap in [('program',131072),('method_review',32768),('runtime_review',32768)]:
        row=s[k];c.need(type(row)is dict and set(row)=={'path','bytes','sha256'} and type(row['path'])is str and Path(row['path']).is_absolute() and len(row['path'].encode())<=512,'explicit pinned input')
        c.need(c.only_pin(row)['bytes']<=cap,'input cap');c.path(row['path'])
    return s
def reviews(s,binding,budget):
    for name in ('runtime_review','method_review'):
        row=s[name];v=c.parse(c.capture(row['path'],32768,c.only_pin(row),budget.tick,budget.read))
        c.need(type(v)is dict and v.get('task_id')==TASK and v.get('approved')is True and v.get('source')==s['source'] and v.get('program')==c.only_pin(s['program']),'root selected exact-source review')
        if name=='runtime_review':
            c.need(v.get('schema')=='neural035_runtime_review_v1' and v.get('image')==binding['image'] and v.get('candidate_seconds')==s['candidate_seconds'] and v.get('operator_seconds')==300 and v.get('memory_bytes')==s['memory_bytes'],'exact prospective runtime profile')
            c.need(v.get('full14_two_phase_isolation_cleanup_qualified')is True and v.get('numpy_version')=='2.2.6' and v.get('native_scientific_method_parity_claimed')is False,'separate future runtime qualification')
        else:
            c.need(v.get('schema')=='neural035_chronological_method_review_v1','method review')
            for k in ('one_frozen_method_all14_sessions','calibration_development_validation_selection','final_refit_at_most_five_public_blocks','no_query_trace_target_or_related_fulltrace_access','no_private_feedback','prior_exposure_audited'):
                c.need(v.get(k)is True,'method constraint: '+k)
            c.need(v.get('artifact_hashes_alone_prove_chronology')is False and v.get('new_animal_or_event_specific_claim')is False,'limited evidence/endpoint')
