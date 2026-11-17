"""Canonical score route with genuine independent grade-child completion custody."""
import argparse,sys,os,copy,time
from pathlib import Path
from zuco.io import *
from zuco.authority import Authority
from zuco.budget import Ledger
from zuco.process import Process
from zuco.trusted_driver import TrustedDriverBackend
from zuco.closure import final_file

def run(args):
    start=time.process_time();need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,'other_reservation_nonnegative');authority=Authority(args.review);r=authority.review;authority.guard();task=getattr(args,'task',None);need(task is None or task in ('NEURAL-085','NEURAL-086') and any(selected[0]==task for selected in r['selected']),'central_score_task_selection')
    selected=r['external_driver_receipt'];descriptor(selected);envelope=decode(read(args.submission,selected['bytes'],selected,authority.guard));need(envelope['programme_pin']==r['programme_pin'] and envelope['runtime_manifest_pin']==r['runtime_manifest_pin'],'selected_prediction_campaign')
    out=path_guard(args.output);need(not out.exists(),'fresh_independent_score_root')
    spec=copy.deepcopy(r['budget']);prior=envelope['source_ledger'];spec['prior_cpu_seconds']=prior['actual_charged_cpu_seconds'];spec['prior_bytes']=prior['reserved_materialized_bytes'];spec['storage_bytes']-=args.other_reserve_bytes;ledger=Ledger(spec)
    runtime=decode(read(r['runtime_manifest_pin']['path'],8*1024**2,r['runtime_manifest_pin'],ledger.guard));runtime_root=Path(r['runtime_manifest_pin']['path']).parent
    for d in runtime['files']:read(below(runtime_root,d['path']),d['bytes'],d,ledger.guard)
    limits=copy.deepcopy(r['whole_campaign_reservation']['grading_driver_limits']);ledger.guard();out.mkdir(parents=True);directory=out/'grading-driver';request={'review':authority.pin,'submission':str(Path(args.submission).absolute()),'other_reserve_bytes':args.other_reserve_bytes}
    job={'id':'trusted-protected-grader','identity':{'selection_id':r['selection_id'],'phase':'PROTECTED_GRADE'},'source_pin':{'bytes':sum(d['bytes']for d in runtime['files']),'sha256':digest(runtime['files'])},'directory':str(directory),'limits':limits,'engineering':False,'trusted_controller':True}
    backend=TrustedDriverBackend([sys.executable,str(runtime_root/'grade_worker.py'),'--request',str(directory/'request.json'),'--output',str(directory/'output')],str(runtime_root),{'PATH':os.environ.get('PATH',''),'PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8'},r['OCI_profile']['delegated_cgroup_root'])
    process=Process(job,ledger,backend);receipt=process.run(request);original={'original_grade_process':receipt,'original_submission_pin':selected,'review_pin':authority.pin,'runtime_manifest_pin':r['runtime_manifest_pin'],'eligible':receipt['failure']is None}
    # Reserve original custody before launch through the job's explicit receipt
    # allotment. This file is emitted even when Process failed or CPU is unknown.
    raw=encode(original);need(len(raw)<=limits['receipt_bytes'],'outer_grade_receipt_extent');write(out/'ORIGINAL_GRADE_COMPLETION.json',raw);process.require_success()
    records=receipt['outputs'];verify_inventory(directory/'output',records,limits['files'],limits['output_bytes'],ledger.guard);d=next((d for d in records if d['path']=='grade/REPORT.json'),None);need(d is not None,'actual_child_report_required');body=decode(read(directory/'output/grade/REPORT.json',d['bytes'],d,ledger.guard));need(body['admission_sha256'] and body['scorer_outer_completion_must_be_observed_by_caller']is True,'child_report_identity')
    ledger.charge_controller(max(0,time.process_time()-start));report={'schema':'zuco2-independent-grade-envelope-v1','actual_grade_receipt':receipt,'child_report_pin':{**d,'path':str(directory/'output/grade/REPORT.json')},'report':body,'review_pin':authority.pin,'prediction_submission_pin':selected,'grade_runtime_source_sha256':digest(runtime['files']),'full_task_scientifically_qualified':False}
    final_file(out/'REPORT.json',report,ledger,r['budget']['controller_cpu_reserve']);return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--output',required=True);p.add_argument('--review',required=True);p.add_argument('--other-reserve-bytes',type=int,default=0);run(p.parse_args())
