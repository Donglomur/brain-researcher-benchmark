"""Crossed participant/video-group descriptive uncertainty; future numeric source."""
from .core import need
from .protocol import PARTICIPANTS,ROIS,PRIMARY,REFERENCE_MODELS
def crossed_bootstrap(targets,predictions,references,video_order,groups,draws,seed):
    import numpy as np
    from .metrics import coordinate_scores
    need(type(draws)is int and draws>=20000 and type(seed)is int,"Precommitted finite uncertainty run")
    group_names=sorted(set(groups[v]for v in video_order))
    group_indices={g:[i for i,v in enumerate(video_order)if groups[v]==g]for g in group_names}
    families=("primary_dynamic_R2",)+tuple("improvement_vs_fixed_"+m for m in REFERENCE_MODELS)
    rng=np.random.default_rng(seed);values={name:{r:[]for r in ROIS}for name in families}
    undefined=0
    for _ in range(draws):
        selected_people=rng.integers(0,10,size=10)
        selected_groups=rng.integers(0,len(group_names),size=len(group_names))
        indices=[i for g in selected_groups for i in group_indices[group_names[int(g)]]]
        draw={name:{}for name in families};valid=True
        for roi in ROIS:
            participant_values={name:[]for name in families}
            for j in selected_people:
                p=PARTICIPANTS[int(j)];y=targets[p,roi][indices]
                a=coordinate_scores(y,predictions[p,roi,PRIMARY][indices])
                fixed={m:coordinate_scores(y,references[p,roi,m][indices])for m in REFERENCE_MODELS}
                if a["status"]!="defined"or any(s["status"]!="defined"for s in fixed.values()):valid=False;break
                participant_values["primary_dynamic_R2"].append(float(a["r2"].mean()))
                for m in REFERENCE_MODELS:participant_values["improvement_vs_fixed_"+m].append(float((a["r2"]-fixed[m]["r2"]).mean()))
            if not valid:break
            for name in families:
                need(len(participant_values[name])==10,"Full shared participant resample")
                draw[name][roi]=sum(participant_values[name])/10
        if not valid or any(len(v)!=46 for v in draw.values()):undefined+=1;continue
        for name in families:
            for roi in ROIS:values[name][roi].append(draw[name][roi])
    # No deletion of undefined draws to create a favorable confidence interval.
    if undefined:return {"status":"unavailable_undefined_resample","undefined_draws":undefined,"draws":draws,"intervals":None}
    alpha=0.05/46
    intervals={name:{r:[float(v)for v in np.quantile(values[name][r],[alpha/2,1-alpha/2])]for r in ROIS}for name in families}
    return {"status":"descriptive_uncalibrated","draws":draws,"seed":seed,"roi_family":46,
            "intervals":intervals,"multiplicity":"two_sided_Bonferroni_46_ROIs_within_each_separately_labelled_metric_family",
            "joint_simultaneous_coverage_across_metric_families":False,
            "shared_indices_across_primary_comparisons_and_ROIs":True,
            "candidate_self_contrast_in_primary_or_uncertainty":False,
            "refitting":False,"conditioning":"fixed fitted predictions and released joint measurement",
            "finite_10_person_calibration":"required before inferential claims"}

