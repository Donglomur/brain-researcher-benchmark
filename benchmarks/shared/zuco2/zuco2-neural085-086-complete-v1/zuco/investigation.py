"""Separate executable interpretation with independently sourced bounded ratings."""
from .io import *
from .contracts import rubric
from .metrics import metric_equal

def validate_product(product,safe):
    exact(product,["schema","evidence_sha256","numerical_recomputation","claims","follow_up","executable_analysis","trace_files"])
    need(product["schema"]=="zuco2-investigation-v1" and product["evidence_sha256"]==digest(safe),"investigation_evidence_identity")
    need(metric_equal(product["numerical_recomputation"],safe["reports"]),"investigation_numerical_admission")
    need(type(product["claims"])is list and product["claims"] and type(product["follow_up"])is dict,"investigation_claims")
    known={safe["evidence_id"]}|{r["evidence_id"] for r in safe["reports"]}
    for c in product["claims"]:
        exact(c,["claim","evidence_ids","limitations"]);need(type(c["claim"])is str and c["claim"] and set(c["evidence_ids"])<=known and c["evidence_ids"] and type(c["limitations"])is list,"traceable_claim")
    descriptor(product["executable_analysis"])
    return product

def rate(product,safe,rater_record,qualification,guard=lambda:None):
    validate_product(product,safe);need(rater_record["product_sha256"]==digest(product) and rater_record["evidence_sha256"]==digest(safe),"independent_rater_binding");rows=rubric(rater_record["dimensions"])
    need(type(qualification['calibration_evidence'])is list and qualification['calibration_evidence'] and type(qualification['independent_review'])is dict and qualification['rubric_sha256']==rater_record['rubric_sha256'],'rubric_unqualified')
    for d in qualification['calibration_evidence']+[qualification['independent_review']]:descriptor(d);read(d['path'],d['bytes'],d,guard)
    known={safe['evidence_id']}|{r['evidence_id']for r in safe['reports']}
    need(all(set(row['evidence_ids'])<=known for row in rows),'rubric_evidence_identity')
    final=[r["adjudicator"]["value"] if r["adjudicator"]is not None else r["ratings"][0]["value"] for r in rows]
    return {"primary_score":sum(final)/12,"dimension_scores":final,"original_ratings":rows,"qualifying_rubric_evidence":qualification,"positive_EEG_gain_required":False,"null_negative_unavailable_answers_allowed":True}
