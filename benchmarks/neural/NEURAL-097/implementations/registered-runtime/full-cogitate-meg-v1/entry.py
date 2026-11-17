#!/usr/bin/env python3
"""Canonical source entry: full or named N097 campaign; deployment disabled."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n097.io import read_json,need,write_json
from n097.contract import require_deployment
from n097.campaign import source_plan

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--program");p.add_argument("--output",required=True)
    p.add_argument("--review");p.add_argument("--other-reserve-bytes",type=int)
    p.add_argument("--condition",choices=["complete","A-F","A-I","B-F","B-I"],default="complete")
    p.add_argument("--source-plan-only",action="store_true")
    p.add_argument("--stage",choices=["prepare","candidate","references","interpretation","assemble","final-report"],default="candidate")
    a=p.parse_args()
    if a.source_plan_only:
        plan=source_plan();write_json(Path(a.output),plan,8_000_000);return 0
    require_deployment()
    need(a.program and a.review and type(a.other_reserve_bytes)is int and a.other_reserve_bytes>=0,"Full selected execution review and reservations")
    review=read_json(a.review,2_000_000)
    from n097.contract import bind_protected_roster
    bind_protected_roster(review["protected_roster_source"])
    need(review["other_reserve_bytes"]==a.other_reserve_bytes,"Exact concurrent-work reservation")
    if a.stage=="prepare":
        from n097.contract import load,ROSTER
        from n097.prepare import mne_epoch_records,prepare
        from n097.io import identity,canonical
        import secrets
        _,binding=load()
        cohort=read_json(review["cohort"]["path"],4_000_000,review["cohort"])
        inventory=read_json(review["native_manifest"]["path"],4_000_000,review["native_manifest"])
        native_plan=read_json(review["native_plan"]["path"],16_000_000,review["native_plan"])
        census=read_json(review["preparation_census"]["path"],64_000_000,review["preparation_census"])
        qualification=read_json(review["census_qualification"]["path"],4_000_000,review["census_qualification"])
        records=mne_epoch_records(review["native_root"],inventory,native_plan,cohort,binding,review["approved_native_total_bytes"],census,qualification)
        obs=prepare(cohort,records,binding,lambda:secrets.token_hex(24),census,qualification,inventory)
        out=Path(a.output);need(not out.exists(),"Fresh complete preparation output");out.mkdir(parents=True)
        cap=review["max_projected_output_bytes"];need(type(cap)is int and cap>0,"Complete approved projected byte budget")
        op=write_json(out/"OBSERVATIONS.json",obs,cap)
        targets={"schema":"n097-protected-targets-v1","contract":binding,"source_panel_identity":identity(canonical(obs)),
                 "targets":{r["private_id"]:{"person_index":ROSTER.index(r["person"]),"y":r["y"],"stratum":r["stratum"]}for r in obs["rows"]},
                 "comparison_scope":{"contract":binding,"cohort_identity":obs["cohort_identity"],"source_panel_identity":identity(canonical(obs)),
                                     "outer_split":"33persons-x2physical-image-halves","inner_split_seed":97097,"budget_class":"N097-CPU-SMALL-v1"}}
        tp=write_json(out/"TARGETS.json",targets,cap)
        write_json(out/"PREPARATION_RECORD.json",{"observations":op,"targets":tp,"source_semantics_qualified":False,
                    "full_cohort":33,"all22_gates_remain_required":True,"no_scientific_qualification_from_preparation":True})
        return 0
    submission=read_json(a.program,16_000_000)
    from n097.campaign import candidate_campaign,grade_complete_campaign,reference_inputs,build_reference_campaign,assemble_reference_panels,interpretation_campaign
    if a.stage=="assemble":
        from n097.campaign import merge_named_contributions
        plan=source_plan()
        plan["source_panel_identity"]=review["prepared_input_admission"]["source_panel_identity"]
        contributions=[read_json(x["path"],64_000_000,x)for x in review["named_contributions"]]
        rows=merge_named_contributions(plan,contributions)
        grade_complete_campaign(plan,list(rows.values()),review,a.output)
        return 0
    if a.stage=="final-report":
        from n097.interpretation import assemble_interpretations
        from n097.contract import load
        _,binding=load()
        closures=read_json(review["interpretation_closures"]["path"],64_000_000,review["interpretation_closures"])
        need(closures["contract"]==binding,"Exact complete interpretation contract")
        result=assemble_interpretations(closures["records"],review["expert_rubric"],binding,{k:review["complete_report"][k]for k in ("bytes","sha256")})
        write_json(Path(a.output)/"BLINDED_REPORT_COLLECTION.json",result,64_000_000)
        return 0
    if a.stage=="references":
        from n097.contract import load
        from n097.io import identity,canonical
        _,binding=load()
        obs=read_json(review["observations"]["path"],review["observations"]["bytes"],review["observations"])
        root=Path(a.output);need(not root.exists(),"Fresh reference stage root");root.mkdir(parents=True)
        episodes=reference_inputs(obs,root/"views",binding)
        results=build_reference_campaign(review,review["reference_seals"],episodes,root/"execution")
        assemble_reference_panels(results,source_plan(),identity(canonical(obs)),root/"panels")
        return 0
    if a.stage=="interpretation":
        result=read_json(review["complete_report"]["path"],256_000_000,review["complete_report"])
        interpretation_campaign(review,submission,result,a.output)
        return 0
    out=Path(a.output);selected=None if a.condition=="complete"else a.condition.split("-")
    plan,closures=candidate_campaign(review,submission,out/"candidate",selected)
    if selected is None:grade_complete_campaign(plan,closures,review,out/"protected-report")
    else:write_json(out/"NAMED_CONTRIBUTION.json",{"plan":plan,"closures":closures,"full_benchmark_complete":False},64_000_000)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status":"refused","reason":str(exc),"scientific_qualification":False}),file=sys.stderr)
        raise SystemExit(2)
