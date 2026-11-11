"""Late independent human-rubric finalization; no prediction/investigation reentry.
This separate future operation consumes already completed, source-bound grading
and an explicit root rating selection. It never changes the original report.
"""
import argparse,time
from pathlib import Path
from zuco.io import *
from zuco.products import success
from zuco.investigation import rate
from zuco.qualification import status
from zuco.authority import Authority
from zuco.budget import Ledger
from zuco.closure import final_file

def run(selection_path,output):
    start=time.process_time();selection=decode(read(selection_path,1024**2));exact(selection,['schema','rating_execution_authorized','original_execution_review','completed_score','investigation_capture','rater_record','rater_qualification','deadline_monotonic','budget','selection_id'])
    need(selection['schema']=='zuco2-rating-selection-v1' and selection['rating_execution_authorized']is True,'rating_not_authorized');ledger=Ledger(selection['budget']);need(selection['budget']['deadline_monotonic']==selection['deadline_monotonic'],'rating_deadline');guard=ledger.guard
    def selected(k):
        d=selection[k];descriptor(d);return decode(read(d['path'],d['bytes'],d,guard))
    original=selected('original_execution_review');score=selected('completed_score');success(score['actual_grade_receipt']);need(score['review_pin']==selection['original_execution_review'],'original_grade_selection');report=score['report'];investigation=selected('investigation_capture');need(investigation['product']==report['investigation'],'completed_interpretation_binding');success(investigation['actual_process']);success(investigation['executed_analysis_receipt']);evidence=report['evidence'];ratings=rate(investigation['product'],evidence,selected('rater_record'),selected('rater_qualification'),guard)
    # Original completed source review can be expired now. It cannot dispatch or
    # grant new data access; only the separately selected rating budget applies.
    qualifying=type('CompletedQualifications',(),{})();qualifying.gates=report['all_28_gate_records'];qualifying.review=original;qualifying.qualify_metric=lambda task,rep,mode:Authority.qualify_metric(qualifying,task,rep,mode)
    results=[]
    for r in evidence['reports']:
        if r['task']!='NEURAL-086':continue
        q=status(qualifying,r['task'],r['representation'],r['mode'],r['contexts']['FFD']['D_R']['complete_support'],evidence['control_evidence'],True);results.append({'task':r['task'],'representation':r['representation'],'mode':r['mode'],'primary_score':ratings['primary_score'] if q['qualified_metric'] else None,'qualification':q,'ratings':ratings})
    out=path_guard(output);need(not out.exists(),'fresh_rating_output');ledger.charge_controller(time.process_time()-start);result={'schema':'zuco2-rating-finalization-v1','original_completed_score':selection['completed_score'],'independent_rater_record':selection['rater_record'],'results':results,'prediction_reentry':False,'full_task_scientifically_qualified':False};final_file(out/'RATINGS.json',result,ledger,selection['budget']['controller_cpu_reserve']);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.selection,a.output)
