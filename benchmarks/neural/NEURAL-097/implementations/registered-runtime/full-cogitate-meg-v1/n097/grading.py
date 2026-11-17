"""Target-last protected grader. Candidate source is never imported here."""
from pathlib import Path
from .io import need, read_json, identity, canonical, write_json
from .contract import require_deployment, ARMS
from .collection import admit_condition,collect_condition_predictions

def grade_condition(plan,closures,access,mode,seed,operator_root,target_artifact,reference_artifacts):
    require_deployment()
    admission=admit_condition(plan,closures,access,mode,seed)
    if admission["status"]!="admitted":
        return {"condition":f"{access}-{mode}-{seed}","status":"unavailable","metrics":None,
                "private_target_reads":0,"private_reference_reads":0,"failures":admission["failures"],
                "original_condition_closures":[r for r in closures if r["job_id"].startswith(f"{access}-{mode}-{seed}/")]}
    # These source/output/process/case checks all precede the private target read.
    predictions=collect_condition_predictions(admission,operator_root)
    expected=set(predictions["SIGNAL"])
    target=read_json(Path(operator_root)/target_artifact["path"],64_000_000,target_artifact)
    need(target["schema"]=="n097-protected-targets-v1"and target["contract"]==plan["contract"]and target["source_panel_identity"]==plan["source_panel_identity"],"Exact private target contract and prepared source panel")
    need(set(target["targets"])==expected,"Complete protected case join; no intersection scoring")
    from .metrics import evaluate
    metrics=evaluate(target["targets"],predictions)
    references={};ref_reads=0
    for ref in ("R0","R1","R2","R3","R4"):
        record=reference_artifacts.get(ref)
        if record is None:
            references[ref]={"status":"unavailable","reason":"reference_not_qualified","metrics":None};continue
        need(record["independently_qualified"]is True,"No unqualified numerical reference admission")
        body=read_json(Path(operator_root)/record["artifact"]["path"],64_000_000,record["artifact"]);ref_reads+=1
        need(body["reference"]==ref and body["seed"]==97097 and body["contract"]==plan["contract"],"Fixed reference recipe/context")
        from .custody import verify_reference_panel
        verify_reference_panel(body,plan,ref,target["source_panel_identity"])
        need(set(body["predictions"])==set(ARMS)and all(set(body["predictions"][a])==expected for a in ARMS),"All330 reference outputs and exact cases")
        references[ref]={"status":"complete","artifact_identity":record["artifact"],"metrics":evaluate(target["targets"],body["predictions"])}
    return {"condition":admission["condition"],"status":"complete_descriptive_score","metrics":metrics,"references":references,
            "contract":plan["contract"],"private_target_reads":1,"private_reference_reads":ref_reads,
            "scope_key":target["comparison_scope"],"campaign_agent_policy":admission["closures"][0]["campaign_agent_policy"],
            "source_and_processes":[r["source_closure"]for r in admission["closures"]],
            "original_condition_closures":admission["closures"],
            "scientific_qualification":False}
