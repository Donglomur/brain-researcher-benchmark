"""Independent target-last scorer; raw predictive R2, no positive clipping."""
from .core import need
from .protocol import PARTICIPANTS,ROIS,MODELS,PRIMARY,REFERENCE_MODELS,MEASUREMENT_LABEL
def coordinate_scores(target,prediction):
    import numpy as np
    need(target.ndim==prediction.ndim==2 and target.shape==prediction.shape,"Exact query-video/coordinate pairing")
    if not np.isfinite(target).all()or not np.isfinite(prediction).all():
        return {"status":"undefined_nonfinite","r2":None}
    denom=((target-target.mean(0))**2).sum(0)
    if (denom<=0).any():return {"status":"undefined_constant_target_coordinate","r2":None}
    return {"status":"defined","r2":1-((target-prediction)**2).sum(0)/denom}
def cell(target,predictions,references):
    import numpy as np
    need(set(predictions)==set(MODELS),"Every matched control is mandatory")
    need(set(references)==set(REFERENCE_MODELS),"Both actual protected fixed comparators mandatory")
    scores={m:coordinate_scores(target,predictions[m])for m in MODELS}
    fixed={m:coordinate_scores(target,references[m])for m in REFERENCE_MODELS}
    failed={m:s["status"]for m,s in scores.items()if s["status"]!="defined"}
    failed.update({"protected_reference/"+m:s["status"]for m,s in fixed.items()if s["status"]!="defined"})
    if failed:return {"status":"undefined","dispositions":failed,"primary":None,"model_r2":None,"paired_improvement":None}
    means={m:float(scores[m]["r2"].mean())for m in MODELS}
    reference_means={m:float(fixed[m]["r2"].mean())for m in REFERENCE_MODELS}
    primary=means[PRIMARY]
    return {"status":"defined","primary":primary,"primary_metric":"raw_unclipped_candidate_dynamic_motion_category_R2",
            "model_r2":means,"protected_reference_r2":reference_means,
            "paired_improvement":{m:primary-reference_means[m]for m in REFERENCE_MODELS},
            "candidate_self_contrast_descriptive":primary-means["static_motion_category"],
            "candidate_self_contrast_affects_reward_or_pass":False,
            "coordinates":target.shape[1],"videos":target.shape[0],
            "temporal_controls_direction_only":all(primary>means[m]for m in
              ("static_center","static_mean","static_orderless","static_motion_category","motion_only","shuffled_motion_category")),
            "measurement":MEASUREMENT_LABEL}
def complete_report(cells):
    need(set(cells)=={(p,r)for p in PARTICIPANTS for r in ROIS},"All 460 person/ROI cells, including failures")
    vector={r:[cells[p,r]for p in PARTICIPANTS]for r in ROIS}
    failed=[{"participant":p,"roi":r,"status":cells[p,r]["status"]}for p in PARTICIPANTS for r in ROIS if cells[p,r]["status"]!="defined"]
    per_roi={r:None if any(c["status"]!="defined"for c in vector[r])else sum(c["primary"]for c in vector[r])/10 for r in ROIS}
    comparisons={m:{r:None if any(c["status"]!="defined"for c in vector[r])else sum(c["paired_improvement"][m]for c in vector[r])/10 for r in ROIS}for m in REFERENCE_MODELS}
    descriptive={r:None if any(c["status"]!="defined"for c in vector[r])else sum(c["candidate_self_contrast_descriptive"]for c in vector[r])/10 for r in ROIS}
    aggregate=None if failed else sum(per_roi.values())/46
    return {"measurement":MEASUREMENT_LABEL,"primary_metric":"raw_unclipped_candidate_dynamic_motion_category_R2",
            "roi_vector":per_roi,"aggregate":aggregate,
            "paired_improvement_roi_vectors":comparisons,
            "paired_improvement_aggregates":{m:None if failed else sum(v.values())/46 for m,v in comparisons.items()},
            "candidate_self_contrast_descriptive_roi_vector":descriptive,
            "candidate_self_contrast_descriptive_aggregate":None if failed else sum(descriptive.values())/46,
            "candidate_self_contrast_affects_reward_or_pass":False,
            "aggregate_status":"unavailable_full_denominator"if failed else"defined",
            "dispositions":failed,"expected_people":10,"expected_rois":46,
            "cell_count":460,"negative_or_null_results_retained":True,
            "claim":"conditional predictive performance; protected reference comparisons separately reported; performance alone is not temporal understanding",
            "revision":"prospective_V2_metric_amendment_not_historical_score_parity"}

