"""Separate one-pass interpretation and blinded rubric collection source."""
from .io import need,exact,identity,canonical
DIMENSIONS=("faithful_estimand","cohort_source","comparisons","uncertainty","alternatives","falsifiability")

def interpret_request(aggregate,paper_source,condition,contract):
    return {"schema":"n097-one-pass-interpretation-request-v1","contract":contract,"condition":condition,
            "aggregate_identity":identity(canonical(aggregate)),"aggregate":aggregate,"public_paper_source":paper_source,
            "predictions_immutable":True,"private_targets_exposed":False,
            "required_claim_boundary":"Only finite-panel fixed-procedure predictive performance. No sign proves information, independence, neural source, confound absence, population or theory. Report all null/negative/unavailable results and H01-H05.",
            "fields":["estimand","cohort_and_source_limits","metric_comparisons","uncertainty","alternative_explanations","falsifying_followup","evidence_refs","report_hierarchy_and_seed_completeness","procedure_and_projection_identity","contrast_sign_and_metric_units"]}

def collect_rubric(reports,interpretation_identity,adjudication=None):
    need(len(reports)==2 and reports[0]["blinded_rater_id"]!=reports[1]["blinded_rater_id"],"Two separate blinded expert raters")
    for row in reports:
        need(row["interpretation_identity"]==interpretation_identity and row["blinded"]is True,"Exact blinded report")
        need(set(row["scores"])==set(DIMENSIONS)and all(type(v)is int and 0<=v<=2 for v in row["scores"].values()),"Six bounded integer rubric dimensions")
        need(row["evidence_refs"]and row["rater_qualification"],"Evidence-linked qualified human assessment")
    disagreement={k:[r["scores"][k]for r in reports]for k in DIMENSIONS if reports[0]["scores"][k]!=reports[1]["scores"][k]}
    if disagreement:need(adjudication,"Preserve disagreements and explicit adjudication")
    if adjudication is not None:
        need(adjudication["interpretation_identity"]==interpretation_identity and set(adjudication["scores"])==set(DIMENSIONS)
             and all(type(v)is int and 0<=v<=2 for v in adjudication["scores"].values()),"Exact interpretation and six integer0-2 adjudicated scores")
    return {"schema":"n097-blinded-rubric-collection-v1","reports":reports,"disagreements":disagreement,
            "adjudication":adjudication,"combined_prediction_score":None,"rubric_construct_validity_qualified":False}


def assemble_interpretations(records,expert_records,binding,complete_report_identity):
    """Full12 typed original programme products, then independent expert inputs."""
    from .contract import ACCESS,MODES,SEEDS,condition,require_deployment
    from .io import read_json
    require_deployment()
    expected={condition(a,m,s)for a in ACCESS for m in MODES for s in SEEDS}
    need(len(records)==12 and {r["condition"]for r in records}==expected,"All12 distinct original interpretation dispositions")
    reports=[]
    fields={"estimand","cohort_and_source_limits","metric_comparisons","uncertainty","alternative_explanations","falsifying_followup","evidence_refs","report_hierarchy_and_seed_completeness","procedure_and_projection_identity","contrast_sign_and_metric_units"}
    for row in records:
        cid=row["condition"]
        if row["status"]!="complete":
            reports.append({"condition":cid,"status":"unavailable","original":row});continue
        from .custody import validate_fold,validate_operation
        job={"id":cid,"kind":"interpretation","condition":cid}
        fold=validate_fold(row["fold_binding"],job,binding,complete_report_identity)
        need(fold["kind"]=="interpretation","Selected interpretation role")
        operation=validate_operation(row["original_operation"]["chain"],job,row["fold_binding"],"interpret")
        need(operation["request"]["inputs"]==fold["inputs"],"Exact selected sealed aggregate interpretation input")
        receipt=operation["runtime_receipt"]
        need(receipt["status"]=="complete"and receipt["descendants_closed"]and receipt["contract"]==binding,"Original closed interpretation custody")
        art=receipt["outputs"]["interpretation"];body=read_json(art["path"],4_000_000,art)
        exact(body,["schema","condition","contract","report"])
        need(body["schema"]=="n097-interpretation-report-v1"and body["condition"]==cid and body["contract"]==binding,"Exact interpretation source/context")
        need(set(body["report"])==fields and all(body["report"][k]for k in fields),"All required evidence/limits fields; no positive-only answer key")
        evidence=expert_records.get(cid)
        rubric=None
        if evidence is not None:
            raters=[read_json(p["path"],1_000_000,p)for p in evidence["raters"]]
            adjudication=read_json(evidence["adjudication"]["path"],1_000_000,evidence["adjudication"])if evidence.get("adjudication")else None
            rubric=collect_rubric(raters,identity(canonical(body)),adjudication)
        reports.append({"condition":cid,"status":"collected_unqualified","artifact":art,"report":body,"rubric":rubric})
    return {"schema":"n097-complete-blinded-interpretation-collection-v1","contract":binding,"reports":reports,
            "scientific_qualification":False,"all22_gates_remain_required":True,"no_prediction_score_combination":True}
