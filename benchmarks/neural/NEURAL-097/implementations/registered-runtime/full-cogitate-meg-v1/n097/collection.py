"""Typed source/output/condition admission before any private target read."""
from pathlib import Path
from .io import need, exact, identity, canonical, read_json
from .contract import ARMS, ACCESS, MODES, SEEDS, case_job, condition

def prediction_rows(body,episode_nonce,expected_queries):
    exact(body,["schema","opaque_episode_nonce","outcomes"])
    need(body["schema"]=="n097-query-outcomes-v1"and body["opaque_episode_nonce"]==episode_nonce,"Episode source identity")
    need(type(body["outcomes"])is list and len(body["outcomes"])==len(expected_queries),"Complete query roster")
    out={};failures=[]
    for row in body["outcomes"]:
        need(type(row)is dict and row.get("status")in("complete","abstain","failed"),"Typed query status")
        q=row.get("opaque_query_nonce");need(type(q)is str and q in expected_queries and q not in out,"Unique expected query")
        if row["status"]=="complete":
            exact(row,["opaque_query_nonce","status","p_face"])
            v=row["p_face"]
            need(type(v)in(int,float)and 0<=v<=1,"Finite nonboolean probability; NaN fails range")
            out[q]=v
        else:
            exact(row,["opaque_query_nonce","status","reason"])
            need(type(row["reason"])is str and 0<len(row["reason"])<=256,"Bounded original failure reason")
            out[q]=None;failures.append({"query":q,"status":row["status"],"reason":row["reason"]})
    need(set(out)==set(expected_queries),"No missing/extra query outcomes")
    return out,failures

def global_barrier(plan,closures):
    need(plan["task_id"]=="NEURAL-097"and len(plan["jobs"])==3960,"Full original campaign plan")
    expected={j["id"]for j in plan["jobs"]}
    jobs={j["id"]:j for j in plan["jobs"]}
    need(type(closures)is list and len(closures)==3960,"All3960 attempt dispositions, never a successful subset")
    rows={}
    for row in closures:
        need(row["job_id"]in expected and row["job_id"]not in rows,"Unique planned closure")
        need(row["status"]in("complete","failed","abstained","not_started"),"Every original disposition retained")
        need(row["all_processes_closed"]is True,"No private targets before every attempted descendant closes")
        need(row["contract"]==plan["contract"],"Same scientific and estimand contract")
        need(row["job"]==jobs[row["job_id"]]and row["arm"]==jobs[row["job_id"]]["arm"],"Exact expected planned job and arm")
        rows[row["job_id"]]=row
    need(set(rows)==expected,"Full global closure")
    from .custody import verify_candidate,verify_failed_closure
    for job_id,row in rows.items():
        if row["status"]=="complete":verify_candidate(row,jobs[job_id],plan)
        elif row["status"]in ("failed","abstained"):verify_failed_closure(row)
    return rows

def admit_condition(plan,closures,access,mode,seed):
    rows=global_barrier(plan,closures)
    expected=[j for j in plan["jobs"]if j["condition"]==condition(access,mode,seed)]
    need(len(expected)==330,"Complete66x5 condition")
    selected=[rows[j["id"]]for j in expected]
    failures=[{"job":r["job_id"],"status":r["status"],"reasons":r.get("failure_reasons",[])}
              for r in selected if r["status"]!="complete"]
    if failures:return {"status":"unavailable","private_reads_allowed":False,"failures":failures}
    policies={identity(canonical(r["family_policy"]))["sha256"]for r in selected}
    need(len(policies)==1,"Same sealed family/search/query policy across every feature arm/fold within condition")
    for r in selected:
        need(r["actual_source_process_join_verified"]is True and r["runtime_semantics_qualified"]is True,
             "Actual protected operator evidence; no candidate-written success")
        need(r["input_projection_qualified"]is True and r["family_exposure_qualified"]is True,"Full source/exposure admission")
        need(r["source_closure"]and r["actual_process_receipts"]and r["resources"],"Concrete original custody and costs")
        method=r.get("family_policy_conformity_evidence")
        need(method and method["status"]=="independently_qualified"and method["source_closure"]==r["source_closure"]
             and method["family_policy"]==r["family_policy"]and method["condition"]==condition(access,mode,seed),
             "Source-specific family/search/query conformity cannot follow from a repeated policy label")
    return {"status":"admitted","private_reads_allowed":True,"closures":selected,"contract":plan["contract"],
            "condition":condition(access,mode,seed),"family_policy":selected[0]["family_policy"]}

def collect_condition_predictions(admission,operator_root):
    need(admission["status"]=="admitted","Admission before prediction collection")
    predictions={a:{}for a in ARMS};case_universe=None
    for row in admission["closures"]:
        artifact=row["prediction_artifact"]
        body=read_json(Path(operator_root)/artifact["path"],16_000_000,artifact)
        values,failures=prediction_rows(body,row["opaque_episode_nonce"],set(row["private_query_joins"]))
        need(not failures,"Abstained/failed query is not a complete condition")
        arm=row["arm"]
        for nonce,v in values.items():
            private=row["private_query_joins"][nonce]
            need(private not in predictions[arm],"No cross-half case duplication")
            predictions[arm][private]=v
    for a in ARMS:
        if case_universe is None:case_universe=set(predictions[a])
        need(set(predictions[a])==case_universe,"All five arms exact same case union")
    return predictions
