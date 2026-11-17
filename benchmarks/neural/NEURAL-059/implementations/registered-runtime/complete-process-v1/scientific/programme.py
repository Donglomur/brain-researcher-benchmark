"""Full inactive source composition. Real provider/native profiles remain unavailable."""
import json
from copy import deepcopy
from . import preparation, references, evaluation, diagnostics
from .contracts import need, pin, CONDITIONS, STATUS, check_prepared
from .io import OwnedDirectory, Journal
from .lifecycle import LifecycleLedger
from .campaign import CalibrationViews,fit_references,method_registry,predict_and_grade,calibration,fit_validation_panel
from .actors import build_actor_panel,actor_predictor,close_actor_panel

def bounded_json(value, cap):
    need(type(cap) is int and cap>0,"prospective serialization cap")
    out=bytearray()
    for piece in json.JSONEncoder(sort_keys=True,separators=(",",":"),allow_nan=False).iterencode(value):
        raw=piece.encode()
        need(len(out)+len(raw)+1<=cap,"serialization extent cap before append")
        out.extend(raw)
    out.extend(b"\n")
    return bytes(out)

def run_components(raw_by_eid,members,*,preparation_limits,root,stage_caps,
                   frozen_F_sources,actor_builders,paired_cost_limits,global_cost_limits,
                   measured_global_F,global_F_evidence,runtime_factory):
    """Complete actual producer->projection->fit->barrier->scorer source route.

    Only explicitly inert actor boundaries are currently admitted. A supplied
    runtime_factory must pass references' own runtime checks. No host/process
    qualification, target novelty or native fit authority is issued here.
    """
    keys={"root_metadata","calibration","prediction_grade"}
    need(type(stage_caps) is dict and set(stage_caps)==keys and
         all(type(v) is int and v>0 for v in stage_caps.values()),"exact finite output partitions")
    ledger=LifecycleLedger([m["eid"] for m in members],paired_cost_limits,global_cost_limits)
    ledger.global_development(measured_global_F,global_F_evidence)
    views=None;models={};ref_records=[];actor_records=[];prepared=None
    with OwnedDirectory(root,stage_caps["root_metadata"]) as out:
        def save(name,value):
            return out.write(name,bounded_json(value,stage_caps["root_metadata"]-out.written))
        try:
            prepared=preparation.prepare_all(raw_by_eid,members,limits=preparation_limits)
            check_prepared(prepared,members)
            save("PREPARATION.json",prepared)
            holds=[{"session_id":s["session_id"],"holds":s["structural_holds"]} for s in prepared
                   if s["structural_holds"]]
            if holds:
                save("UNAVAILABLE.json",{"status":STATUS,"structural_holds":holds,
                    "full_sessions":[s["session_id"] for s in prepared],"no_fit_attempted":True})
                save("LIFECYCLE.json",ledger.report())
                return {"status":"unavailable","scientific_ready":False,"holds":holds}
            views=CalibrationViews(out.path/"calibration",prepared,members,
                preparation.project_case,frozen_F_sources,stage_caps["calibration"])
            handles,actor_methods,actor_records=build_actor_panel(prepared,actor_builders,
                preparation.project_case,views,ledger,records=actor_records)
            save("ACTOR_FIT_RECORDS.json",actor_records)
            validation_journal=Journal(out,"VALIDATION.jsonl",stage_caps["root_metadata"])
            try:
                models,runtimes,ref_records=fit_references(prepared,members,runtime_factory,
                    references,preparation.project_case,validation_journal=validation_journal,records=ref_records)
            finally:
                validation_journal.close()
            save("REFERENCE_RECORDS.json",ref_records)
            unavailable=[{"session_id":k[0],"condition":k[1],"family":k[2],
                          "status":v.get("status")} for k,v in models.items()
                         if v.get("status")!="available"]
            if unavailable:
                save("UNAVAILABLE.json",{"status":STATUS,"reference_cells":unavailable,
                    "full_sessions":[s["session_id"] for s in prepared],
                    "all_reference_records_retained":True,"held_prediction_attempts":0})
                save("LIFECYCLE.json",ledger.report())
                return {"status":"unavailable","scientific_ready":False,"cells":unavailable}
            methods=method_registry(prepared,references,models,actor_methods)
            save("METHOD_COMMITMENTS.json",methods)
            result=predict_and_grade(prepared,members,methods,models,runtimes,references,
                preparation.project_case,actor_predictor(handles),lambda:close_actor_panel(handles),
                out.path/"prediction",stage_caps["prediction_grade"],evaluation.score_panel,ledger)
            save("LIFECYCLE.json",ledger.report())
            save("PRIMARY_COMPLETION.json",{"status":STATUS,"completion":result["completion"],
                "scientific_ready":False,"diagnostics":"separate complete roster producer not run by primary",
                "total_output_partition_bytes":sum(stage_caps.values())})
            return result
        except BaseException as error:
            retained={"status":"failed","type":type(error).__name__,"error":str(error),
                      "full_roster":[m["eid"] for m in members],"lifecycle":ledger.report(),
                      "reference_records":ref_records,"actor_records":actor_records,
                      "reference_cells_attempted":len(ref_records),"actor_cells_completed":len(actor_records),
                      "qualification":False}
            try:save("FAILURE.json",retained)
            except BaseException as secondary:error.add_note("failure metadata retention refused: "+repr(secondary))
            raise
        finally:
            if views is not None:views.close()

def run_diagnostic_producer(prepared,members,*,primary_predictions,primary_methods,
                            runtime_factory,output_root,max_output_bytes,external_complete,progress):
    """Complete fits, then chronological held panels with separate outside completion.

    Transform construction stays private. Every rerun uses its own final model
    identities and durable paired predictions; primary receipts never substitute.
    """
    from .controller import PanelController
    from .campaign import measured_call
    check_prepared(prepared,members)
    need(type(progress) is dict and not progress,"fresh diagnostic progress")
    need(type(max_output_bytes) is int and max_output_bytes>0,"prospective diagnostic output cap")
    need(callable(external_complete),"separate outside completion boundary required")
    need(len(primary_methods)==3 and {m["method_id"] for m in primary_methods}=={"L","H","prior"}
         and all(m["arm"]=="R" and m["kind"]==("prior" if m["method_id"]=="prior" else "reference")
                 for m in primary_methods),"exact complete reference/prior panel, no actor diagnostic data")
    progress.update(attempted_cells=0,durably_recorded_cells=0,scheduled_fit_slots=0,
        durably_recorded_declared_slots=0,status="running",expected_diagnostic_fit_slots=59160,
        actual_fit_work="individual actual stage/grid/refit/inference records, not scheduled slot count")
    with OwnedDirectory(output_root,max_output_bytes) as directory:
        journal=Journal(directory,"DIAGNOSTICS.jsonl",max_output_bytes)
        held_journal=None
        def retain(record):
            raw=bounded_json(record,max_output_bytes-directory.written)
            ack=journal.append(raw);need(ack==pin(raw),"actual exact diagnostic durable receipt");return ack
        def completion_evidence(tag,replicate):
            value=external_complete(tag,replicate)
            need(type(value) is dict and set(value)=={"capture_identity","all_selected_processes_exited","status"}
                 and value["all_selected_processes_exited"] is True and value["status"]==STATUS,
                 "separately captured source-only outside completion, no authority promotion")
            need(type(value["capture_identity"]) in (str,dict) and bool(value["capture_identity"]),
                 "actual completion capture identity")
            pin(value)
            return value
        current=None
        try:
            for tag in ("D-label","D-neural"):
                conditions=CONDITIONS if tag=="D-label" else ("SHN","SBHN")
                for replicate in range(20):
                    methods=deepcopy(primary_methods);models={};runtimes={};altered_by_case={}
                    failed_cells=[];rows=[];session_records={}
                    for session in prepared:
                        sid=session["session_id"]
                        current={"kind":"diagnostic_fit_session","status":"attempted","session_id":sid,
                            "tag":tag,"replicate":replicate,"fit_records":[],"inference_records":[],
                            "held_dispositions":[]}
                        progress["current_evidence"]=current
                        transformed=diagnostics.diagnostic_transform(session,tag,replicate)
                        altered=transformed["prepared_session"]
                        for case in altered["cases"]:
                            need(case["case_id"] not in altered_by_case,"globally unique original source case identity")
                            altered_by_case[case["case_id"]]=case
                        retain({"kind":"transform","status":STATUS,"tag":tag,"replicate":replicate,
                                "session_id":sid,"transformed":transformed})
                        runtime=runtime_factory(references.shape_from_prepared(altered));runtimes[sid]=runtime
                        current["inference_records"]=runtime.inference_records
                        declared=17*len(conditions);progress["scheduled_fit_slots"]+=declared
                        current["declared_fit_slots"]=declared
                        # Only actual entered stage records increase attempted_cells, even on failure.
                        try:
                            fitted=fit_validation_panel(altered,conditions,runtime,references,
                                preparation.project_case,journal,records=current["fit_records"])
                        finally:
                            current["actual_started_cells"]=len(current["fit_records"])
                            progress["attempted_cells"]+=current["actual_started_cells"]
                        for method in methods:
                            family=method["method_id"]
                            if family=="prior":continue
                            for condition in conditions:
                                model=fitted[(condition,family)];models[(sid,condition,family)]=model
                                entry=next(x for x in current["fit_records"] if
                                           x["family"]==family and x["condition"]==condition)
                                if model.get("status")=="available":
                                    c=references.model_commitment(model)
                                    commit={"session_id":sid,"condition":condition,
                                        "config_identity":c["config_identity"],"parameter_identity":c["parameter_identity"]}
                                else:
                                    commit={"session_id":sid,"condition":condition,"status":"unavailable",
                                        "config_identity":pin(entry["selection"]),"parameter_identity":pin(entry["refit"]),
                                        "error":"complete validation/refit unavailable"}
                                    failed_cells.append({"session_id":sid,"condition":condition,"family":family,
                                                         "model_status":model.get("status")})
                                method["commitments"]=[commit if x["session_id"]==sid and x["condition"]==condition
                                                       else x for x in method["commitments"]]
                                held_count=sum(c["split"]=="test" for c in altered["cases"])
                                current["held_dispositions"].append({"condition":condition,"family":family,
                                    "held_count":held_count,"model_status":model.get("status"),
                                    "inference_attempted":False,"status":"empty_held_support" if not held_count
                                    else "awaiting_complete_final_model_panel"})
                        current["status"]=STATUS
                        progress["last_cell_receipt"]=retain(current)
                        progress["durably_recorded_cells"]+=current["actual_started_cells"]
                        progress["durably_recorded_declared_slots"]+=declared
                        session_records[sid]=current["fit_records"]
                        current=None;progress.pop("current_evidence",None)
                    # All final session/model identities are fixed before any diagnostic held query.
                    retain({"kind":"diagnostic_method_commitments","tag":tag,"replicate":replicate,
                            "methods":methods,"failed_cells":failed_cells})
                    def reused(family,condition):return family=="prior" or condition not in conditions
                    reused_rows={}
                    for row in primary_predictions:
                        if reused(row["method_id"],row["condition"]):
                            key=(row["session_id"],row["case_id"],row["method_id"],row["condition"])
                            need(key not in reused_rows,"unique exact primary reuse row")
                            reused_rows[key]=row
                    if failed_cells:
                        # A required failed model invalidates the whole new inference panel.
                        # Retain exact already-captured C/prior reuse; never predict only favorable new cells.
                        rows=[deepcopy(r) for r in primary_predictions if reused(r["method_id"],r["condition"])]
                        outside=completion_evidence(tag,replicate)
                        retain({"kind":"diagnostic_panel_unavailable","tag":tag,"replicate":replicate,
                            "full_sessions":[s["session_id"] for s in prepared],"failed_cells":failed_cells,
                            "new_held_prediction_attempts":0,"outside_completion":outside,
                            "interpretation":"complete null/failure support; no favorable partial inference"})
                        scoring_support=prepared
                    else:
                        held_name="held-"+tag+"-"+str(replicate).zfill(2)+".jsonl"
                        held_journal=Journal(directory,held_name,max_output_bytes)
                        def current_projection(case,condition,include_label=False):
                            # Only the current original case is projected; the whole donor map is private.
                            altered=altered_by_case[case["case_id"]]
                            return preparation.project_case(altered,condition,include_label=include_label)
                        ctl=PanelController(prepared,members,methods,current_projection,held_journal.append)
                        case_lookup={(s["session_id"],c["case_id"]):(s,c) for s in prepared for c in s["cases"]}
                        while True:
                            request=ctl.next_case()
                            if request is None:break
                            sid=request["session_id"];cid=request["case_id"];session,case=case_lookup[(sid,cid)]
                            current={"kind":"diagnostic_held_case","tag":tag,"replicate":replicate,
                                "session_id":sid,"case_id":cid,"responses":[],"inference_records":[],
                                "completed_fit_records":session_records[sid],"work_records":[]}
                            progress["current_evidence"]=current
                            for method in methods:
                                family=method["method_id"]
                                for condition in CONDITIONS:
                                    if reused(family,condition):
                                        key=(sid,cid,family,condition)
                                        need(key in reused_rows,"complete original C/prior reuse support")
                                        original=reused_rows[key];probability=original["p"]
                                        need(evaluation.build_prediction(session,case,method,condition,probability)==original,
                                             "exact reused original prediction/source/config/state identity")
                                    else:
                                        rt=runtimes[sid];begin=len(rt.inference_records)
                                        view=deepcopy(request["views"][condition])
                                        try:
                                            result,work=measured_call(lambda:references.predict(
                                                models[(sid,condition,family)],[view],rt),
                                                input_value=view,source_evidence=method["method_source_identity"])
                                            need(len(result)==1,"one current held probability")
                                            probability=result[0];current["work_records"].append(work)
                                        except BaseException as error:
                                            if hasattr(error,"n059_work"):current["work_records"].append(error.n059_work)
                                            raise
                                        finally:
                                            current["inference_records"].extend(deepcopy(rt.inference_records[begin:]))
                                    current["responses"].append({"method_id":family,"arm":"R",
                                        "condition":condition,"case_id":cid,"p":probability})
                            current["prediction_commit"]=ctl.commit(current["responses"])
                            retain(current)
                            current=None;progress.pop("current_evidence",None)
                        held_identity=held_journal.seal();outside=completion_evidence(tag,replicate)
                        completion=ctl.finish(outside)
                        scoring_support,rows,methods=ctl.captured_scoring_operands()
                        retain({"kind":"diagnostic_held_completion","tag":tag,"replicate":replicate,
                                "journal_name":held_name,"journal":held_identity,"completion":completion})
                        held_journal.close();held_journal=None
                    report=evaluation.score_diagnostic_change(scoring_support,primary_predictions,rows,
                        primary_methods=primary_methods,diagnostic_methods=methods,tag=tag,replicate=replicate)
                    retain({"kind":"diagnostic_grade","status":STATUS,"tag":tag,"replicate":replicate,
                            "report":report,"no_randomization_pvalue":True})
            need(progress["scheduled_fit_slots"]==progress["durably_recorded_declared_slots"]==59160,
                 "complete diagnostic declared support")
            progress["journal"]=journal.seal();progress["status"]="source_only_complete_dispositions_unqualified"
            return dict(progress)
        except BaseException as error:
            progress.update(status="failed",error_type=type(error).__name__,error=str(error),
                            unattempted_tail_preserved_by_full_roster=True)
            if current is not None:
                current["status"]="failed";current["error_type"]=type(error).__name__;current["error"]=str(error)
            try:
                retain({"kind":"diagnostic_failure","status":"failed","error_type":type(error).__name__,
                        "error":str(error),"current_evidence":current,
                        "attempted_cells":progress["attempted_cells"],
                        "durably_recorded_cells":progress["durably_recorded_cells"],
                        "unattempted_tail_preserved_by_full_roster":True})
            except BaseException as secondary:
                error.add_note("diagnostic failure publication also refused: "+repr(secondary))
            raise
        finally:
            if held_journal is not None:held_journal.close()
            journal.close()
