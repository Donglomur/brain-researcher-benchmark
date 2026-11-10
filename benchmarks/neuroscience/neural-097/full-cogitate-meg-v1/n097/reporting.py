"""Complete H01-H05 report source; no scientific reports executed during build."""
from .io import need, canonical
from .contract import ARMS,ACCESS,MODES,SEEDS,RELEVANCES,METRICS,FEATURE_PAIRS,condition

def absolute(grade,arm,relevance,metric):
    if grade is None or grade.get("status")!="complete_descriptive_score":
        return None,["condition_unavailable"]
    value=grade["metrics"]["macro"][arm][relevance][metric]
    return value,[]if value is not None else["required_support_unavailable"]

def delta(left,right):
    lv,lr=left;rv,rr=right
    return {"left":lv,"right":rv,"value":None if lv is None or rv is None else lv-rv,"unavailable_reasons":lr+rr}

def summary(values):
    need(len(values)==3,"Exactly three fixed seed records")
    if any(v is None for v in values):return {"mean":None,"min":None,"max":None,"reason":"incomplete_three_seed_summary"}
    return {"mean":sum(values)/3,"min":min(values),"max":max(values),"reason":None}

def reference_value(grade,reference,arm,relevance,metric):
    if grade is None or grade.get("status")!="complete_descriptive_score":
        return None,["condition_unavailable"]
    row=grade["references"].get(reference)
    if not row or row["status"]!="complete":return None,["reference_unavailable"]
    v=row["metrics"]["macro"][arm][relevance][metric]
    return v,[]if v is not None else["reference_support_unavailable"]

def comparison_scope(left,right):
    return (left and right and left.get("status")=="complete_descriptive_score"and right.get("status")=="complete_descriptive_score"
            and left["scope_key"]==right["scope_key"]and left["campaign_agent_policy"]==right["campaign_agent_policy"])

def report(grades,binding):
    expected={condition(a,m,s)for a in ACCESS for m in MODES for s in SEEDS}
    need(set(grades)==expected,"All12 setting/seed outcomes, including failures")
    rows=[];by_key={}
    for a in ACCESS:
        for mode in MODES:
            for seed in SEEDS:
                cid=condition(a,mode,seed);g=grades[cid]
                for arm in ARMS:
                    for rel in RELEVANCES:
                        for metric in METRICS:
                            value,reasons=absolute(g,arm,rel,metric)
                            key=("absolute",a,mode,seed,arm,rel,metric)
                            row={"kind":"absolute","access":a,"mode":mode,"seed":seed,"arm":arm,"relevance":rel,"metric":metric,"value":value,"unavailable_reasons":reasons}
                            rows.append(row);by_key[key]=row
                            for ref in ("R0","R1","R2","R3","R4"):
                                rows.append({"kind":"candidate_minus_reference","reference":ref,"access":a,"mode":mode,"seed":seed,"arm":arm,"relevance":rel,"metric":metric,**delta((value,reasons),reference_value(g,ref,arm,rel,metric))})
                for left,right in FEATURE_PAIRS:
                    for rel in RELEVANCES:
                        for metric in METRICS:
                            rows.append({"kind":"feature_pair","access":a,"mode":mode,"seed":seed,"left_arm":left,"right_arm":right,"relevance":rel,"metric":metric,**delta(absolute(g,left,rel,metric),absolute(g,right,rel,metric))})
    for kind,pairs in [("access",[("B",m,"A",m)for m in MODES]),("mode",[(a,"I",a,"F")for a in ACCESS])]:
        for la,lm,ra,rm in pairs:
            for seed in SEEDS:
                l=grades[condition(la,lm,seed)];r=grades[condition(ra,rm,seed)]
                for arm in ARMS:
                    for rel in RELEVANCES:
                        for metric in METRICS:
                            d=delta(absolute(l,arm,rel,metric),absolute(r,arm,rel,metric))if comparison_scope(l,r)else{"left":None,"right":None,"value":None,"unavailable_reasons":["comparison_scope_or_generation_policy_unqualified"]}
                            rows.append({"kind":kind,"left_access":la,"left_mode":lm,"right_access":ra,"right_mode":rm,"seed":seed,"arm":arm,"relevance":rel,"metric":metric,**d})
    hierarchy={}
    for name in ("H01","H02","H03","H04"):hierarchy[name]=[]
    for seed in SEEDS:
        g=grades[condition("B","F",seed)]
        hierarchy["H01"].append({"seed":seed,"value":absolute(g,"SIGNAL","Irrelevant","balanced_accuracy")[0]})
        hierarchy["H02"].append({"seed":seed,**delta(absolute(g,"SIGNAL","Irrelevant","balanced_accuracy"),reference_value(g,"R2","SIGNAL","Irrelevant","balanced_accuracy"))})
        for key,right in (("H03","NUISANCE"),("H04","PRE_NUISANCE")):
            hierarchy[key].append({"seed":seed,**delta(absolute(g,"SIGNAL_NUISANCE","Irrelevant","balanced_accuracy"),absolute(g,right,"Irrelevant","balanced_accuracy"))})
    seed_summaries={}
    for key,items in hierarchy.items():
        matching=all(comparison_scope(grades[condition("B","F",SEEDS[0])],grades[condition("B","F",s)])for s in SEEDS)
        seed_summaries[key]=summary([x["value"]for x in items])if matching else{"mean":None,"min":None,"max":None,"reason":"incomplete_or_incomparable_three_seed_generation_policy"}
    grouped={}
    for row in rows:
        context={k:v for k,v in row.items()if k not in ("seed","value","left","right","unavailable_reasons")}
        key=canonical(context).decode()
        grouped.setdefault(key,[]).append(row)
    all_seed_summaries=[]
    for key,items in grouped.items():
        need(sorted(x["seed"]for x in items)==list(SEEDS),"Three exact required seed rows per report quantity")
        context=__import__("json").loads(key)
        scopes=[(context["access"],context["mode"])]if "access"in context else[(context["left_access"],context["left_mode"]),(context["right_access"],context["right_mode"])]
        matching=all(all(comparison_scope(grades[condition(a,m,SEEDS[0])],grades[condition(a,m,s)])for s in SEEDS)for a,m in scopes)
        value=summary([x["value"]for x in sorted(items,key=lambda x:x["seed"])])if matching else{"mean":None,"min":None,"max":None,"reason":"incomplete_or_incomparable_three_seed_generation_policy"}
        all_seed_summaries.append({"context":context,**value})
    # References are repeated in grade comparisons for join checking, but the
    # absolute panel is published once per recipe, never as three replicates.
    refs={}
    for ref in ("R0","R1","R2","R3","R4"):
        complete=[g["references"][ref]for g in grades.values()if g.get("status")=="complete_descriptive_score"and g["references"].get(ref,{}).get("status")=="complete"]
        if complete:
            need(all(x["artifact_identity"]==complete[0]["artifact_identity"]for x in complete),"Same fixed reference panel reused")
            refs[ref]=complete[0]
        else:refs[ref]={"status":"unavailable","metrics":None}
    from .report_details import pair_record,paired_seed_summaries
    pairs=[pair_record(row,grades)for row in rows if row["kind"]!="absolute"]
    need(len(pairs)==3264,"Complete reference/feature/access/mode paired-person contrasts")
    return {"paired_person_contrasts":pairs,"paired_person_seed_summaries":paired_seed_summaries(pairs,grades),"schema":"n097-H01-H05-report-v1","contract":binding,"hierarchy":hierarchy,"primary_seed_summary_descriptive":seed_summaries,
            "H05_macro_records":rows,"H05_seed_summaries":all_seed_summaries,"fixed_reference_panels":refs,
            "all_condition_results":grades,"scientific_qualification":False,"population_or_theory_verdict":False,
            "sign_convention":"Literal left-minus-right; BA higher favors left, losses lower favor left; no information or independence verdict.",
            "full_completion":False,"completion_reason":"All22 scientific/runtime/exposure/reference/rubric gates require independent evidence; source build cannot close them."}

def interpretation_projection(report,selected_condition):
    from .report_details import safe_condition,safe_references,UNITS
    need(selected_condition in report["all_condition_results"],"Existing interpretation setting")
    projection={"schema":"n097-interpretation-aggregate-v2","contract":report["contract"],"hierarchy":report["hierarchy"],
                "seed_summaries":report["primary_seed_summary_descriptive"],"H05_macro_records":report["H05_macro_records"],"H05_seed_summaries":report["H05_seed_summaries"],
                "selected_condition":selected_condition,"all_condition_status_support_cost_failures":{cid:safe_condition(g)for cid,g in report["all_condition_results"].items()},
                "fixed_reference_panels":safe_references(report["fixed_reference_panels"]),"metric_units_directions":UNITS,
                "paired_person_tables":"All33 operands/deltas/support for3264 contrasts and1088 three-seed summaries retained in the complete protected report; interpretation uses this fixed aggregate projection.",
                "failure_projection":"Source-owned codes derived from each original failure are retained; private exception text/paths stay in the complete protected record, never candidate view.",
                "sign_convention":report["sign_convention"],"unavailable_results_are_required":True}
    need(len(canonical(projection))<=4_000_000,"Complete fixed aggregate report cap; no row pruning")
    return projection
