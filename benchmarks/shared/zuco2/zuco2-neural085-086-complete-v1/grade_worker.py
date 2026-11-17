"""Protected child grading/investigation source, admitted by score_campaign parent."""
import argparse,copy,resource
from pathlib import Path
from zuco.io import *
from zuco.authority import Authority
from zuco.budget import Ledger
from zuco.programme import admit
from zuco.products import success,result
from zuco.collector import admit as collect,target_last
from zuco.engine import Engine

def run(args):
    need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,"other_reservation_nonnegative");authority=Authority(args.review);review=authority.review;authority.guard();selected=review["external_driver_receipt"];need(type(selected)is dict,"independent_completed_driver_pin_required");descriptor(selected)
    envelope=decode(read(args.submission,selected["bytes"],selected,authority.guard));need(envelope["programme_pin"]==review["programme_pin"] and envelope["runtime_manifest_pin"]==review["runtime_manifest_pin"],"current_outer_closure")
    old=decode(read(envelope["review_pin"]["path"],envelope["review_pin"]["bytes"],envelope["review_pin"],authority.guard));need({k:v for k,v in old.items() if k!="external_driver_receipt"}=={k:v for k,v in review.items() if k!="external_driver_receipt"},"unchanged_original_authority_deadline")
    outer=envelope["driver_receipt"];success(outer);need(outer["actual_launch"]["argv"][1].endswith("campaign_worker.py"),"actual_driver_entry")
    directory=Path(envelope["campaign_result_path"]).parent;verify_inventory(directory,outer["outputs"],review["whole_campaign_reservation"]["driver_limits"]["files"],review["whole_campaign_reservation"]["driver_limits"]["output_bytes"],authority.guard)
    d=next(x for x in outer["outputs"] if x["path"]=="result.json");driver_result=decode(read(directory/"result.json",d["bytes"],d,authority.guard));campaign_pin=driver_result["campaign_pin"];campaign=decode(read(campaign_pin["path"],campaign_pin["bytes"],campaign_pin,authority.guard))
    need(campaign["closed_for_prediction"]is True and campaign["original_failure"]is None and not campaign["not_started"],"complete_campaign_required")
    resource_record=campaign["resources"];spec=copy.deepcopy(resource_record["spec"]);need(spec["deadline_monotonic"]==review["deadline_monotonic"],"original_budget_deadline");spec["prior_cpu_seconds"]=resource_record["actual_charged_cpu_seconds"]+outer["resources"]["cpu_seconds"];spec["prior_bytes"]=resource_record["reserved_materialized_bytes"]+envelope["source_ledger"]["reserved_materialized_bytes"]
    spec["storage_bytes"]-=args.other_reserve_bytes;ledger=Ledger(spec);program=admit(review["programme_pin"]["path"],ledger.guard);refs={j["id"]:j for j in campaign["reference_plan"]};unavailable=campaign["diagnostic_unavailable"];missing_contexts=campaign["prediction_unavailable"]
    for gap in unavailable:need(gap["job_id"]in refs and refs[gap["job_id"]]["identity"]["role"]=="control" and gap["identity"]==refs[gap["job_id"]]["identity"] and gap["phase"]=="source_preparation","allowed_diagnostic_unavailability")
    unavailable_ids={x["job_id"] for x in unavailable};need(len(unavailable_ids)==len(unavailable),"duplicate_diagnostic_gap")
    planned_all=campaign['plan']['jobs']+campaign['reference_plan'];allowed={j['id']:j for j in planned_all if j.get('source_disposition')=='required_unscorable_secondary_context'}
    need(len(missing_contexts)==len(allowed) and {x['job_id'] for x in missing_contexts}==set(allowed),'complete_unavailable_context_census')
    for x in missing_contexts:need(x['identity']==allowed[x['job_id']]['identity'] and x['identity']['task']=='NEURAL-086' and x['identity']['context']!='FFD' and x['source_sha256']==campaign['plan']['source_sha256'],'source_context_disposition')
    admission=collect(campaign["plan"],campaign["candidate_records"],program,ledger,[j for j in refs.values() if j["id"]not in unavailable_ids and j["id"]not in allowed],campaign["reference_records"],outer)
    out=path_guard(args.output);need(not out.exists(),"fresh_score_output");ledger.guard();out.mkdir(parents=True)
    # Exclusive durable attempted grading record precedes the first protected read.
    marker=Path(review["output_root"])/"PROTECTED_SCORING_ATTEMPT.json";write(marker,{"campaign_pin":campaign_pin,"admission_sha256":digest(admission),"original_deadline":review["deadline_monotonic"],"attempted":True},ledger)
    parent=resource.getrusage(resource.RUSAGE_SELF)
    try:
        targets=target_last(admission,campaign["protected_target_pin"],campaign["plan"],ledger)
        from zuco.scoring import score,safe_projection
        evidence=safe_projection(score(admission,targets,authority,{"diagnostic_unavailable":unavailable,"source_gaps":campaign.get("source_control_gaps",[]),"secondary_context_unavailable":missing_contexts,"source_control_observations":campaign.get("source_control_observations",{}),"actual_job_control_observations":campaign.get("job_control_observations",[])}))
        reference_diagnostics=[]
        for record in campaign['reference_records']:
            for d in record['state']['files']:
                if d['path']=='reference-diagnostics.json':reference_diagnostics.append(decode(read(below(record['state']['root'],d['path']),d['bytes'],d,ledger.guard)))
        evidence['fixed_reference_fold_diagnostics']=reference_diagnostics;evidence['evidence_id']=digest(evidence);write(out/'SAFE_EVIDENCE.json',evidence,ledger)
        interpretation=None;ratings=None
        if any(t=="NEURAL-086" for t,r,m in review["selected"]):
            # Separate process and source entry; Engine.launch is used, never Engine.chain/run.
            engine=Engine(out/"investigation",authority,ledger,program,program);view=engine.allocate("safe-evidence");ledger.guard();view.mkdir();e=engine.view_file(view,"evidence.json",evidence)
            i=copy.deepcopy(campaign["plan"]["jobs"][0]["identity"]);i.update(task="NEURAL-086",context="investigation",arm="PLUS_EEG",method="scientific_interpretation");j={"id":digest(i),"identity":i,"limits":review["job_limits"]};request={"phase":"INVESTIGATE","identity":i,"evidence_path":"/view/evidence.json","evidence_pin":{**e,"path":"/view/evidence.json"},"evidence_sha256":digest(evidence),"prediction_campaign_sealed":True,"prediction_reentry_allowed":False,"remaining_deadline_monotonic":review["deadline_monotonic"]}
            captured,receipt,job=engine.launch(j,"INVESTIGATE",program,view,request,entry=program["manifest"]["investigation_entry"][1]);interpretation=result(captured,j["limits"]["output_bytes"],ledger.guard)
            from zuco.investigation import validate_product,rate
            validate_product(interpretation,evidence);files={x["path"]:x for x in captured["files"]};analysis=interpretation["executable_analysis"];need(analysis["path"]in files and analysis==files[analysis["path"]],"actual_executable_analysis_capture")
            need(set(files)=={"result.json",analysis["path"]}|{x["path"] for x in interpretation["trace_files"]},"complete_investigation_inventory")
            # Execute the submitted analysis in another fresh sandbox. The
            # declaration file itself is not evidence that recomputation ran.
            analysis_program={'manifest':{'entry':['python3',analysis['path']]},'source_root':captured['root'],'files':captured['files'],'source_bytes':sum(d['bytes'] for d in captured['files']),'manifest_pin':{'path':captured['root'],'bytes':sum(d['bytes'] for d in captured['files']),'sha256':digest(captured['files'])}}
            analysis_request={**request,'phase':'RECOMPUTE','expected_report_schema':'zuco2-recomputation-v1'}
            analysis_capture,analysis_receipt,_=engine.launch({**j,'id':j['id']+'-recompute'},'RECOMPUTE',analysis_program,view,analysis_request)
            numerical=result(analysis_capture,j['limits']['output_bytes'],ledger.guard);exact(numerical,['schema','evidence_sha256','reports','trace_files']);need(numerical['schema']=='zuco2-recomputation-v1' and numerical['evidence_sha256']==digest(evidence),'actual_recomputation_identity')
            from zuco.metrics import metric_equal
            need(metric_equal(numerical['reports'],evidence['reports']),'actual_executable_numerical_recomputation')
            declared={d['path']:d for d in numerical['trace_files']};actual={d['path']:d for d in analysis_capture['files'] if d['path']!='result.json'};need(declared==actual and len(declared)==len(numerical['trace_files']),'analysis_complete_outputs')
            if review["raters"] is not None:
                raters=review["raters"];record=decode(read(raters["record"]["path"],raters["record"]["bytes"],raters["record"],ledger.guard));qualification=decode(read(raters["qualification"]["path"],raters["qualification"]["bytes"],raters["qualification"],ledger.guard));ratings=rate(interpretation,evidence,record,qualification,ledger.guard)
            write(out/"INVESTIGATION.json",{"product":interpretation,"actual_process":receipt,"capture":captured,"ratings":ratings,"executed_analysis_capture":analysis_capture,"executed_analysis_receipt":analysis_receipt},ledger)
        after=resource.getrusage(resource.RUSAGE_SELF);ledger.charge_controller(max(0.,after.ru_utime+after.ru_stime-parent.ru_utime-parent.ru_stime));ledger.final()
        from zuco.lifecycle import stage,operators
        lifecycle=copy.deepcopy(campaign['lifecycle'])
        for stage_id in ('S17','S18','S19','S20','S21','S22'):stage(lifecycle,stage_id,[{'admission_sha256':digest(admission),'safe_evidence_sha256':digest(evidence)}])
        operators(lifecycle,['O28','O29','O30'],[{'safe_evidence_sha256':digest(evidence)}])
        if interpretation is not None:
            stage(lifecycle,'S23',[{'product_sha256':digest(interpretation),'actual_process_sha256':digest(receipt)}]);stage(lifecycle,'S24',[{'executed_analysis_sha256':digest(analysis_receipt),'ratings':ratings}],'numeric_recomputation_complete_rubric_unavailable' if ratings is None else 'source_executed_unqualified');operators(lifecycle,['O31'],[{'product_sha256':digest(interpretation)}])
        stage(lifecycle,'S25',[{'original_driver_sha256':digest(outer)}]);operators(lifecycle,['O32'],[{'review_sha256':authority.pin['sha256']}])
        report={"lifecycle":lifecycle,"schema":"zuco2-final-report-v1","evidence":evidence,"investigation":interpretation,"ratings":ratings,"admission_sha256":digest(admission),"original_process_failure_denominator":campaign["original_attempts"],"resources":ledger.snapshot(),"scientifically_qualified":False,"all_28_gate_records":authority.gates,"installed_count_delta":0,"ready_count_delta":0,"causal_demand_identified":False,"scorer_outer_completion_must_be_observed_by_caller":True};from zuco.closure import final_file
        final_file(out/"REPORT.json",report,ledger,review['budget']['controller_cpu_reserve']);return report
    except BaseException as e:
        # The original attempted read and subsequent failure are retained, not retried.
        write(out/"FAILURE.json",{"failure":failure(e),"target_attempt":admission.get("target_attempt"),"resources":ledger.snapshot(),"primary_score":None});raise
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument('--request',required=True);a.add_argument('--output',required=True);q=a.parse_args();req=decode(read(q.request,1024**2));exact(req,['review','submission','other_reserve_bytes']);read(req['review']['path'],req['review']['bytes'],req['review'])
    from types import SimpleNamespace
    run(SimpleNamespace(review=req['review']['path'],submission=req['submission'],output=str(Path(q.output)/'grade'),other_reserve_bytes=req['other_reserve_bytes']))
