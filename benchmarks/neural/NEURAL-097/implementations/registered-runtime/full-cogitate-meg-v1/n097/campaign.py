"""Complete programme orchestration, disabled until scientific deployment.

Operator-owned joins, original receipts and private grading never enter candidate
mounts. Named conditions can contribute closures to the same complete campaign;
no partial condition is relabeled as a full benchmark.
"""
from pathlib import Path
from .io import need,read_json,write_json,identity,canonical
from .contract import load,plan,ARMS,ACCESS,MODES,SEEDS,condition,require_deployment
from .execution import Runtime,capture_submission,train_and_query,request,initial_budget
from .exposure import admit_family,knowledge_views
from .splits import outer_plan,episode_view
from .views import materialize_episode
from .collection import global_barrier
from .custody import capture_fold,validate_operation,validate_fold

def source_plan():
    docs,binding=load()
    return plan(binding)

def original_failure_inventory(attempt_root):
    """Preserve every existing original controller/driver artifact after failure."""
    from .io import plain,read,identity
    rows=[]
    for f in sorted(Path(attempt_root).rglob("*")):
        if f.is_file():
            plain(f)
            if f.name in ("PROCESS_RECORD.json","worker_output.json","stdout.bin","stderr.bin","NATIVE_ATTEMPT.json","MONITOR.json")or "ownership"in f.parts or "commands"in f.parts:
                b=read(f,16_000_001)
                rows.append({"path":str(f),**identity(b)})
    return rows


def failure_closure(attempt, process_files, records):
    """Outer launcher exit cannot prove a Docker namespace or child is absent."""
    if not records:return False
    for path,r in zip(process_files,records):
        if r["process_creation_outcome"]=="not_dispatched":continue
        if r["returncode"]is None or any(x.get("cleanup_unconfirmed")for x in r["cleanup"]):return False
        native=path.parent/"native/NATIVE_ATTEMPT.json"
        if not native.is_file():return False
        report=read_json(native,16_000_000)
        if report.get("all_owned_absent")is not True:return False
        if report.get("request_identity")!=r["request_identity"]:return False
    return True

def candidate_campaign(review,submission,output,selected_setting=None):
    require_deployment()
    docs,binding=load();programme=plan(binding)
    need(review["contract"]==binding and review["root_authorized"]is True,"Protected original execution selection")
    runtime=Runtime(review["runtime"],review["operator_root"])
    root=Path(output);need(not root.exists(),"Fresh complete campaign output");root.mkdir(parents=True)
    knowledge=knowledge_views(review["knowledge_root"],review["knowledge_manifest"],binding)
    knowledge_pins={}
    from .io import relative,write_new
    for access in ACCESS:
        folder=root/"knowledge"/access;folder.mkdir(parents=True)
        rows=[]
        for name,body in knowledge[access].items():
            path=relative(name);pin=write_new(folder/path,body,100_000_000)
            rows.append({"path":name,**pin})
        descriptor={"schema":"n097-audited-knowledge-view-v1","access":access,"files":rows,"audit_identity":knowledge["audit_identity"]}
        path=folder/"KNOWLEDGE_VIEW.json";pin=write_json(path,descriptor,4_000_000)
        knowledge_pins[access]={"path":str(path.absolute()),**pin}
    # Capture every F pre-data seal/I policy before any evaluation data view.
    seals={}
    for a in ACCESS:
        for m in MODES:
            for s in SEEDS:
                cid=condition(a,m,s)
                selected=submission["conditions"][cid]
                seals[cid]=capture_submission(selected["source_root"],selected["manifest"],binding,
                       {"access":a,"mode":m,"seed":s},review["pre_data_controller_evidence"][cid])
                need(review["pre_data_controller_evidence"][cid]["knowledge_audit_identity"]==knowledge["audit_identity"],"Actual pre-data A/B knowledge release provenance")
                seals[cid]["knowledge_view"]=knowledge_pins[a]
                admit_family(review["exposure"][cid],binding,seals[cid]["campaign_agent_policy"])
    # Prepared observations must carry independent source/native/cohort admission.
    need(review["prepared_input_admission"]["independently_qualified"]is True,"Original complete source/native/input gate")
    obs=read_json(review["observations"]["path"],review["observations"]["bytes"],review["observations"])
    need(obs["contract"]==binding,"Exact prepared observations")
    programme["source_panel_identity"]=identity(canonical(obs))
    need(review["prepared_input_admission"]["source_panel_identity"]==programme["source_panel_identity"],"Independently qualified complete prepared panel identity")
    folds=outer_plan(obs);by_fold={(f["person_index"],f["half"]):f for f in folds}
    alloc=review["authoring_allocations"]
    need(set(alloc)=={j["id"]for j in programme["jobs"]},"Every fold has original authoring-cost allocation")
    for cid in seals:
        audit=review["authoring_cost_reviews"][cid]
        need(audit["independently_qualified"]is True and audit["source_closure"]==seals[cid]["source_closure"],"Source-bound original authoring review")
        group=[alloc[j["id"]]for j in programme["jobs"]if j["condition"]==cid]
        for key in("cpu_seconds","wall_seconds","model_input_tokens","model_output_tokens","tool_calls"):
            need(sum(x["allocated_resources"][key]for x in group)==audit["original_observed_resources"][key],"Charge original authoring once across its330 fold-arm closures")
    closures=[]
    for job in programme["jobs"]:
        cid=job["condition"];attempt=root/"candidate"/job["id"];seal=seals[cid]
        base={"job":job,"job_id":job["id"],"arm":job["arm"],"contract":binding,"family_policy":seal["family_policy"],
              "campaign_agent_policy":seal["campaign_agent_policy"],"status":"not_started","all_processes_closed":True,
              "failure_reasons":[],"public_failure":{"code":"not_started","stage":"preflight","original_exception_type":"none"},"actual_source_process_join_verified":False,"runtime_semantics_qualified":False,
              "input_projection_qualified":False,"family_exposure_qualified":False}
        if selected_setting is not None and (job["access"],job["mode"])!=tuple(selected_setting):
            base["failure_reasons"]=["outside_named_condition_contribution"];closures.append(base);continue
        stage="view_preparation"
        try:
            f=by_fold[job["person_index"],job["half"]]
            episode,private=episode_view(f,job["arm"],job["access"],job["mode"],job["seed"],binding)
            train,queries=materialize_episode(episode,root/"protected_views"/job["id"])
            budget=initial_budget(docs["RESOURCE_MODEL.json"],review["authoring_allocations"][job["id"]])
            # Each query artifact descriptor resolves under its own view directory;
            # only that file and the sealed state are mounted by the runtime.
            for q in queries:q["path"]=str((Path(train["path"]).parent/q["path"]).absolute())
            fold_pin=capture_fold(root/"fold_bindings"/(job["id"].replace("/","_")+".json"),"candidate",job,binding,programme["source_panel_identity"],episode["opaque_episode_nonce"],[train],[{"nonce":q["opaque_query_nonce"],"private_id":private[q["opaque_query_nonce"]]["private_id"],"artifact":q}for q in queries],[{"role":"knowledge_view","artifact":seal["knowledge_view"]}],budget)
            active_seal={**seal,"protected_job":job,"protected_binding":fold_pin}
            stage="training_queries"
            result=train_and_query(runtime,active_seal,train,queries,None,attempt,budget)
            stage="collection"
            need(all(x["status"]=="complete"and x["prediction_artifact"]for x in result["outcomes"]),"All original query outcomes required")
            predictions=[]
            for out in result["outcomes"]:
                art=out["prediction_artifact"]
                pred=read_json(art["path"],100_000,art)
                from .io import exact
                exact(pred,["schema","opaque_episode_nonce","opaque_query_nonce","status","p_face"])
                need(pred["schema"]=="neural097-query-prediction-v2"and pred["status"]=="complete","Exact scientific query result schema")
                need(pred["opaque_query_nonce"]==out["query"]and pred["opaque_episode_nonce"]==episode["opaque_episode_nonce"],"Actual query output identity")
                predictions.append({"opaque_query_nonce":out["query"],"status":"complete","p_face":pred["p_face"]})
            manifest={"schema":"n097-query-outcomes-v1","opaque_episode_nonce":episode["opaque_episode_nonce"],"outcomes":predictions}
            path=attempt/"PREDICTIONS.json";pin=write_json(path,manifest,16_000_000)
            base.update(status="complete",source_closure=seal["source_closure"],fold_binding=fold_pin,
              operation_chains=[x["chain"]for x in result["operations"]],
              actual_process_receipts=[x["receipt_identity"]for x in result["operations"]],
              resources=[x["runtime_receipt"]["resources"]for x in result["operations"]],
              actual_source_process_join_verified=True,runtime_semantics_qualified=True,
              family_policy_conformity_evidence=review["method_conformity_reviews"].get(cid),
              input_projection_qualified=True,family_exposure_qualified=True,
              opaque_episode_nonce=episode["opaque_episode_nonce"],
              private_query_joins={k:v["private_id"]for k,v in private.items()},
              prediction_artifact={"path":str(path.absolute()),**pin})
        except Exception as exc:
            from .report_details import public_failure
            base["public_failure"]=public_failure(exc,stage)
            base.update(status="failed",failure_reasons=[type(exc).__name__+": "+str(exc)],
                        retained_original_artifacts=original_failure_inventory(attempt))
            # Runtime failure records must demonstrate termination. A missing
            # completion cannot become true just because this Python call ended.
            process_files=list(attempt.rglob("PROCESS_RECORD.json"))if attempt.exists()else[]
            records=[read_json(f,1_000_000)for f in process_files]
            from .custody import artifact
            if stage=="view_preparation"and not process_files:
                base["failure_closure_evidence"]={"kind":"before_dispatch","job":job,"attempt_root":str(attempt.absolute()),"phase":stage,"process_dispatch_attempted":False,"records":[]}
                base["all_processes_closed"]=True
            else:
                base["failure_closure_evidence"]={"kind":"original_process_records","job":job,"attempt_root":str(attempt.absolute()),"records":[{"process":artifact(f,1_000_000),"native_attempt":artifact(f.parent/"native/NATIVE_ATTEMPT.json",16_000_000)if(f.parent/"native/NATIVE_ATTEMPT.json").is_file()else None}for f in process_files]}
                base["all_processes_closed"]=failure_closure(attempt,process_files,records)
        closures.append(base)
        write_json(root/"closed_jobs"/(job["id"].replace("/","_")+".json"),base,16_000_000)
    write_json(root/"CAMPAIGN_CLOSURES.json",{"plan":programme,"closures":closures},64_000_000)
    return programme,closures

def merge_named_contributions(programme,contributions):
    """Protected controller joins all four named condition contributions once."""
    from .collection import global_barrier
    rows={}
    for contribution in contributions:
        need(contribution["plan"]==programme,"Same full original campaign plan")
        for row in contribution["closures"]:
            if row["failure_reasons"]==["outside_named_condition_contribution"]:continue
            need(row["job_id"]not in rows,"No duplicate successful or failed attempt replacement")
            rows[row["job_id"]]=row
    return global_barrier(programme,list(rows.values()))

def build_reference_campaign(review,reference_seals,episodes,output):
    require_deployment()
    docs,binding=load();programme=plan(binding);runtime=Runtime(review["runtime"],review["operator_root"])
    root=Path(output);need(not root.exists(),"Fresh separate protected reference campaign");root.mkdir(parents=True)
    results=[]
    for job in programme["reference_jobs"]:
        ref=job["reference"];episode=episodes[(job["person_index"],job["half"],job["arm"])]
        seal=reference_seals[ref]
        need(seal["contract"]==binding and seal["family_policy"]["reference"]==ref,"Exact fixed reference producer source")
        budget=initial_budget(docs["RESOURCE_MODEL.json"])
        budget["model_input_tokens"]=0;budget["model_output_tokens"]=0
        fold_pin=capture_fold(root/"fold_bindings"/(job["id"].replace("/","_")+".json"),"reference",job,binding,episode["source_panel_identity"],episode["opaque_episode_nonce"],episode["inputs"],[{"nonce":k,"private_id":v,"artifact":None}for k,v in episode["private_query_joins"].items()],initial_budget=budget)
        seal={**seal,"protected_job":job,"protected_binding":fold_pin}
        req=request(seal,"reference_train",episode["inputs"],budget,runtime.selection["environment"],episode["opaque_episode_nonce"])
        req["reference_recipe"]={"reference":ref,"seed":97097}
        attempt=root/job["id"]
        try:
            result=runtime.launch(req,attempt)
            row={"job":job,"status":"complete","original_operation":result,"fold_binding":fold_pin,"private_query_joins":episode["private_query_joins"]}
        except Exception as exc:
            files=list(attempt.rglob("PROCESS_RECORD.json"))if attempt.exists()else[]
            records=[read_json(f,1_000_000)for f in files]
            row={"job":job,"status":"failed","reason":type(exc).__name__+": "+str(exc),
                 "all_processes_closed":failure_closure(attempt,files,records),"retained_original_artifacts":original_failure_inventory(attempt)}
        results.append(row)
        write_json(root/"closed_jobs"/(job["id"].replace("/","_")+".json"),row,64_000_000)
    need(len(results)==1650,"All5x66x5 original reference closures")
    write_json(root/"REFERENCE_CLOSURES.json",{"contract":binding,"results":results,"independently_qualified":False},64_000_000)
    return results

def grade_complete_campaign(programme,closures,review,output):
    require_deployment();global_barrier(programme,closures)
    need(programme["source_panel_identity"]==review["prepared_input_admission"]["source_panel_identity"],"Selected complete source panel before grade")
    from .grading import grade_condition
    from .reporting import report,interpretation_projection
    grades={}
    for a in ACCESS:
        for m in MODES:
            for seed in SEEDS:
                cid=condition(a,m,seed)
                try:
                    grades[cid]=grade_condition(programme,closures,a,m,seed,review["operator_root"],
                                                review["targets"],review["reference_artifacts"])
                except Exception as exc:
                    from .report_details import public_failure
                    grades[cid]={"condition":cid,"status":"unavailable","metrics":None,
                        "original_condition_closures":[r for r in closures if r["job"]["condition"]==cid],
                        "grading_failure":public_failure(exc,"grading"),
                        "grading_failure_original":{"type":type(exc).__name__,"reason":str(exc)},
                        "private_reads":"unmeasured_after_original_refusal; never asserted zero",
                        "scientific_qualification":False}
    result=report(grades,programme["contract"])
    root=Path(output);need(not root.exists(),"Fresh protected reports");root.mkdir(parents=True)
    write_json(root/"COMPLETE_REPORT.json",result,256_000_000)
    for cid in grades:
        try:
            projection=interpretation_projection(result,cid)
            write_json(root/(cid+"-interpretation-input.json"),projection,4_000_000)
        except Exception as exc:
            write_json(root/(cid+"-interpretation-unavailable.json"),{"condition":cid,"reason":str(exc),"no_rows_pruned":True})
    return result


def reference_inputs(observations,root,binding):
    """Complete neutral reference numerical views; no fictional agent condition."""
    require_deployment()
    root=Path(root);need(not root.exists(),"Fresh protected reference views")
    out={}
    for fold in outer_plan(observations):
        for arm in ARMS:
            ep,private=episode_view(fold,arm,"REFERENCE","FIXED",97097,binding)
            location=root/f'p{fold["person_index"]:02d}'/f'h{fold["half"]}'/arm
            train,query=materialize_episode(ep,location)
            qpath=location/"REFERENCE_QUERIES.json"
            qp=write_json(qpath,[{"opaque_query_nonce":q["opaque_query_nonce"],"x_numeric_vector":q["x_numeric_vector"]}for q in ep["query"]],16_000_000)
            out[(fold["person_index"],fold["half"],arm)]={"opaque_episode_nonce":ep["opaque_episode_nonce"],
               "source_panel_identity":identity(canonical(observations)),
               "inputs":[{"role":"training_view","artifact":train},{"role":"query_views","artifact":{"path":str(qpath.absolute()),**qp}}],
               "private_query_joins":{k:v["private_id"]for k,v in private.items()}}
    return out

def assemble_reference_panels(results,programme,source_panel_identity,output):
    """Typed full producer->numeric bank->private reference assembly."""
    from .collection import prediction_rows
    require_deployment()
    expected={j["id"]for j in programme["reference_jobs"]}
    need(len(results)==1650 and {r["job"]["id"]for r in results}==expected,"Exact all-reference output union")
    need(all(r["status"]=="complete"for r in results),"No survivor-only reference panel; all original failures retained")
    panels={}
    root=Path(output);need(not root.exists(),"Fresh private reference panels");root.mkdir(parents=True)
    for reference in ("R0","R1","R2","R3","R4"):
        chosen=[r for r in results if r["job"]["reference"]==reference]
        need(len(chosen)==330,"Complete reference66x5")
        pred={a:{}for a in ARMS};custody=[]
        for row in chosen:
            expected_job=next(j for j in programme["reference_jobs"]if j["id"]==row["job"]["id"])
            need(row["job"]==expected_job,"Exact immutable reference job")
            fold=validate_fold(row["fold_binding"],expected_job,programme["contract"],source_panel_identity)
            need(fold["kind"]=="reference"and row["private_query_joins"]=={q["nonce"]:q["private_id"]for q in fold["queries"]},"Complete selected reference query joins")
            operation=validate_operation(row["original_operation"]["chain"],expected_job,row["fold_binding"],"reference_train")
            need(operation["request"]["inputs"]==fold["inputs"]and operation["request"]["reference_recipe"]=={"reference":reference,"seed":97097},"Original reference recipe and inputs")
            receipt=operation["runtime_receipt"]
            need(receipt["status"]=="complete"and receipt["descendants_closed"],"Original reference completion")
            artifact=receipt["outputs"]["reference_bank"]
            bank=read_json(artifact["path"],64_000_000,artifact)
            need(bank["schema"]=="n097-reference-bank-v1"and bank["reference"]==reference and bank["seed"]==97097 and bank["contract"]==programme["contract"],"Actual reference producer identity")
            need(bank["fit"]["final_fit_complete"]and bank["numeric_state"],"Fitted numeric state and convergence selection")
            joins=row["private_query_joins"];seen=set();arm=row["job"]["arm"]
            for prediction in bank["predictions"]:
                nonce=prediction["opaque_query_nonce"];value=prediction["p_face"]
                need(nonce in joins and nonce not in seen and type(value)in(int,float)and 0<=value<=1,"Complete typed reference prediction")
                seen.add(nonce);case=joins[nonce];need(case not in pred[arm],"No repeated half/case")
                pred[arm][case]=value
            need(seen==set(joins),"Complete reference query coverage")
            custody.append({"job":expected_job,"fold_binding":row["fold_binding"],"operation_chain":operation["chain"],"bank":artifact,"private_query_joins":joins,"runtime_receipt_identity":operation["receipt_identity"]})
        universe=set(pred["SIGNAL"])
        need(universe and all(set(pred[a])==universe for a in ARMS),"Same complete reference arm cases")
        panel={"schema":"n097-private-reference-panel-v1","reference":reference,"seed":97097,"contract":programme["contract"],
               "predictions":pred,"source_panel_identity":source_panel_identity,"complete_source_process_closure":custody,
               "independently_qualified":False,"qualification_reason":"Original fit/native-bank agreement and competence evidence require separately reviewed scientific qualification."}
        path=root/(reference+".json");pin=write_json(path,panel,64_000_000)
        panels[reference]={"artifact":{"path":str(path.absolute()),**pin},"independently_qualified":False}
    write_json(root/"REFERENCE_PANEL_BINDINGS.json",panels)
    return panels

def interpretation_campaign(review,submission,complete_report,output):
    """Execute twelve new source-captured interpretation programmes after sealing."""
    from .execution import capture_interpreter
    from .reporting import interpretation_projection
    from .interpretation import interpret_request
    require_deployment()
    docs,binding=load();runtime=Runtime(review["runtime"],review["operator_root"])
    root=Path(output);need(not root.exists(),"Fresh one-pass interpretation campaign");root.mkdir(parents=True)
    records=[]
    for a in ACCESS:
        for m in MODES:
            for seed in SEEDS:
                cid=condition(a,m,seed);selected=submission["interpretation"][cid]
                projection=interpretation_projection(complete_report,cid)
                inp=interpret_request(projection,review["public_paper_source"],cid,binding)
                path=root/(cid+"-input.json");pin=write_json(path,inp,4_000_000)
                seal=capture_interpreter(selected["source_root"],selected["manifest"],binding,cid,identity(canonical(complete_report)))
                budget=initial_budget(docs["RESOURCE_MODEL.json"])
                limits=docs["RESOURCE_MODEL.json"]["future_evaluation_envelope_not_authorization"]["interpretation_stage_per_setting_seed"]
                budget.update(cpu_seconds=limits["cpu_seconds"],wall_seconds=limits["wall_seconds"],memory_bytes=limits["memory_bytes"],
                              model_input_tokens=limits["input_tokens"],model_output_tokens=limits["output_tokens"],trained_state_bytes=0)
                job={"id":cid,"kind":"interpretation","condition":cid}
                aggregate_input={"role":"aggregate","artifact":{"path":str(path.absolute()),**pin}}
                fold_pin=capture_fold(root/(cid+"-binding.json"),"interpretation",job,binding,identity(canonical(complete_report)),cid,[aggregate_input],[],initial_budget=budget)
                seal={**seal,"protected_job":job,"protected_binding":fold_pin}
                req=request(seal,"interpret",[aggregate_input],budget,
                            runtime.selection["environment"],cid)
                attempt=root/(cid+"-operation")
                try:
                    row={"condition":cid,"status":"complete","fold_binding":fold_pin,"original_operation":runtime.launch(req,attempt)}
                except Exception as exc:
                    row={"condition":cid,"status":"failed","reason":type(exc).__name__+": "+str(exc),"retained_original_artifacts":original_failure_inventory(attempt)}
                records.append(row)
                write_json(root/(cid+"-closure.json"),row,64_000_000)
    need(len(records)==12,"All setting/seed scientific interpretations")
    write_json(root/"INTERPRETATION_CLOSURES.json",{"contract":binding,"records":records,"blinded_rubric_qualified":False},64_000_000)
    return records
