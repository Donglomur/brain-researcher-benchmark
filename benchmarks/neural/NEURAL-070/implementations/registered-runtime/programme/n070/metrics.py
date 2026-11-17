"""Independent target-last scorer; raw predictive R2, no positive clipping."""
from .core import need
from .protocol import PARTICIPANTS,ROIS,MODELS,PRIMARY,REFERENCE_MODELS,MEASUREMENT_LABEL
def coordinate_scores(target, prediction):
    import numpy as np
    need(target.ndim == prediction.ndim == 2 and target.shape == prediction.shape,
         "Exact query-video/coordinate pairing")
    need(target.shape[0] > 0 and target.shape[1] > 0,
         "Nonempty query videos and coordinates")
    need(target.dtype.kind in "fiu" and prediction.dtype.kind in "fiu",
         "Real numeric target and prediction arrays")
    # Integer magnitudes outside the consecutive binary64 integer range are
    # refused rather than silently rounding distinct target/prediction values.
    for array in (target, prediction):
        if array.dtype.kind == "f" and array.dtype.itemsize > 8:
            return {"status": "undefined_arithmetic_range", "r2": None}
        if array.dtype.kind in "iu" and ((array > 2**53).any() or
                                        (array.dtype.kind == "i" and (array < -(2**53)).any())):
            return {"status": "undefined_arithmetic_range", "r2": None}
    # Promote integer/low-precision inputs before subtraction and squaring.
    # Finite inputs can still overflow or underflow in the original R2 formula.
    # Such arithmetic cannot yield a defined score, a clipped reward or a win.
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
            target = target.astype(np.float64, copy=False)
            prediction = prediction.astype(np.float64, copy=False)
            if not np.isfinite(target).all() or not np.isfinite(prediction).all():
                return {"status": "undefined_nonfinite", "r2": None}
            if (target == target[0]).all(axis=0).any():
                return {"status": "undefined_constant_target_coordinate", "r2": None}
            denominator = ((target - target.mean(0)) ** 2).sum(0)
            scores = 1 - ((target - prediction) ** 2).sum(0) / denominator
    except FloatingPointError:
        return {"status": "undefined_arithmetic_range", "r2": None}
    if (denominator <= 0).any() or not np.isfinite(scores).all():
        return {"status": "undefined_arithmetic_range", "r2": None}
    return {"status": "defined", "r2": scores}


def _mean(values):
    """Round an exact mean of finite binary64 scores once, without sum overflow."""
    import math
    from fractions import Fraction
    values = list(values)
    need(bool(values) and all(math.isfinite(v) for v in values),
         "Mean requires nonempty finite values")
    exact = sum((Fraction(float(v)) for v in values), Fraction()) / len(values)
    result = float(exact)
    need(math.isfinite(result) and (result != 0 or exact == 0),
         "Representable arithmetic mean")
    return result


def cell(target,predictions,references):
    import numpy as np
    need(set(predictions)==set(MODELS),"Every matched control is mandatory")
    need(set(references)==set(REFERENCE_MODELS),"Both actual protected fixed comparators mandatory")
    scores={m:coordinate_scores(target,predictions[m])for m in MODELS}
    fixed={m:coordinate_scores(target,references[m])for m in REFERENCE_MODELS}
    failed={m:s["status"]for m,s in scores.items()if s["status"]!="defined"}
    failed.update({"protected_reference/"+m:s["status"]for m,s in fixed.items()if s["status"]!="defined"})
    if failed:return {"status":"undefined","dispositions":failed,"primary":None,"model_r2":None,"paired_improvement":None}
    means={m:_mean(scores[m]["r2"])for m in MODELS}
    reference_means={m:_mean(fixed[m]["r2"])for m in REFERENCE_MODELS}
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
    per_roi={r:None if any(c["status"]!="defined"for c in vector[r])else _mean(c["primary"]for c in vector[r]) for r in ROIS}
    comparisons={m:{r:None if any(c["status"]!="defined"for c in vector[r])else _mean(c["paired_improvement"][m]for c in vector[r]) for r in ROIS}for m in REFERENCE_MODELS}
    descriptive={r:None if any(c["status"]!="defined"for c in vector[r])else _mean(c["candidate_self_contrast_descriptive"]for c in vector[r]) for r in ROIS}
    aggregate=None if failed else _mean(per_roi.values())
    return {"measurement":MEASUREMENT_LABEL,"primary_metric":"raw_unclipped_candidate_dynamic_motion_category_R2",
            "roi_vector":per_roi,"aggregate":aggregate,
            "paired_improvement_roi_vectors":comparisons,
            "paired_improvement_aggregates":{m:None if failed else _mean(v.values()) for m,v in comparisons.items()},
            "candidate_self_contrast_descriptive_roi_vector":descriptive,
            "candidate_self_contrast_descriptive_aggregate":None if failed else _mean(descriptive.values()),
            "candidate_self_contrast_affects_reward_or_pass":False,
            "aggregate_status":"unavailable_full_denominator"if failed else"defined",
            "dispositions":failed,"expected_people":10,"expected_rois":46,
            "cell_count":460,"negative_or_null_results_retained":True,
            "claim":"conditional predictive performance; protected reference comparisons separately reported; performance alone is not temporal understanding",
            "revision":"prospective_V2_metric_amendment_not_historical_score_parity"}

