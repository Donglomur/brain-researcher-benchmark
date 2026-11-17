"""Evaluator-only complete 50-view join; target access occurs after actor barrier."""
from pathlib import Path
from .core import need,digest
from .native.io import load,dump
from .numeric_io import array
from .protocol import PARTICIPANTS,ROIS,MODELS,VIDEOS,MEASUREMENT_LABEL,REFERENCE_MODELS,REFERENCE_PRODUCER,reference_procedure_identity
def run(request):
    import numpy as np
    from .metrics import cell,complete_report
    from .statistics import crossed_bootstrap
    root=Path("/inputs");cap=request["member_bytes"];manifest=load(root/"score_inputs.json")
    need(manifest["barrier"]=="all_actor_lifetimes_closed_and_predictions_immutable","Actual Engine barrier is required")
    expected_views={p+"/fold-"+str(f)for p in PARTICIPANTS for f in range(5)}
    bindings=manifest["reference_bindings"]
    need(set(manifest["views"])==set(bindings)==expected_views,"All50 protected original reference views")
    need(digest(bindings)==manifest["reference_binding_identity"]==request["reference_binding_identity"],"Actual host-composed fixed reference binding, independently passed in issued request")
    need(len({v["source_identity"]for v in bindings.values()})==1,"One fixed reference source across all50 views")
    groups=manifest["groups"];targets={};predictions={};references={};cells={}
    for person in PARTICIPANTS:
        order=[];ys={r:[]for r in ROIS};ps={(r,m):[]for r in ROIS for m in MODELS};rs={(r,m):[]for r in ROIS for m in REFERENCE_MODELS};widths={}
        for fold in range(5):
            row=manifest["views"][person+"/fold-"+str(fold)]
            y=load(root/row["target_manifest"]);p=load(root/row["prediction_manifest"]);r=load(root/row["reference_manifest"])
            binding=bindings[person+"/fold-"+str(fold)]
            need(binding["participant"]==person and binding["fold"]==fold and binding["job_id"]=="REFERENCE/"+person+"/"+str(fold),"Original protected reference operation")
            need(p["participant"]==y["participant"]==person and p["fold"]==y["fold"]==fold,"Original person/fold")
            need(p["query_videos"]==y["query_videos"] and p["split_identity"]==y["split_identity"]==manifest["split_identity"],"Complete exact query join")
            need(p["measurement"]==y["measurement"]==MEASUREMENT_LABEL,"Conditional label retained")
            need(p["coordinate_identity"]==y["coordinate_identity"],"Exact fixed ROI coordinate order")
            need(all(r[k]==y[k]for k in("participant","fold","query_videos","split_identity","measurement","coordinate_identity")),"Actual fixed reference has identical protected query/coordinate pairing")
            need(r["producer"]==REFERENCE_PRODUCER and r["procedure_identity"]==reference_procedure_identity(),"Selected fixed procedure identity, backed by original host capture")
            need(set(p["predictions"])==set(MODELS),"All mandatory matched controls")
            need(all(set(p["predictions"][m])==set(ROIS)for m in MODELS),"All and only 46 ROI predictions per control")
            need(set(y["responses"])==set(ROIS) and set(r["predictions"])==set(MODELS),"Complete target and fixed reference model roster")
            need(all(set(r["predictions"][m])==set(ROIS)for m in MODELS),"Complete fixed reference ROI roster")
            n=len(y["query_videos"])
            need(n>0 and n==len(set(y["query_videos"])) and set(y["query_videos"])<=set(VIDEOS),"Unique original fold query videos")
            order.extend(y["query_videos"])
            for roi in ROIS:
                target=array(root/row["target_root"],y["responses"][roi],cap)
                need(target.ndim==2 and target.shape[0]==n and target.shape[1]>0,"Protected actual target matches fold query extent")
                need(widths.get(roi,target.shape[1])==target.shape[1],"Identical fixed coordinate width across folds");widths[roi]=target.shape[1]
                ys[roi].append(target)
                for model in MODELS:
                    prediction=array(root/row["prediction_root"],p["predictions"][model][roi],cap)
                    need(prediction.ndim==2 and prediction.shape==target.shape,"Actual per-fold candidate query rows and coordinates before concatenation")
                    ps[roi,model].append(prediction)
                for model in REFERENCE_MODELS:
                    reference=array(root/row["reference_root"],r["predictions"][model][roi],cap)
                    need(reference.ndim==2 and reference.shape==target.shape,"Actual per-fold protected reference query rows and coordinates")
                    rs[roi,model].append(reference)
        need(len(order)==1102 and set(order)==set(VIDEOS),"Full held-video OOF denominator")
        permutation=[order.index(v)for v in VIDEOS]
        for roi in ROIS:
            targets[person,roi]=np.concatenate(ys[roi])[permutation]
            for model in MODELS:predictions[person,roi,model]=np.concatenate(ps[roi,model])[permutation]
            for model in REFERENCE_MODELS:references[person,roi,model]=np.concatenate(rs[roi,model])[permutation]
            cells[person,roi]=cell(targets[person,roi],{m:predictions[person,roi,m]for m in MODELS},{m:references[person,roi,m]for m in REFERENCE_MODELS})
    report=complete_report(cells)
    report["cells"]={p:{r:cells[p,r]for r in ROIS}for p in PARTICIPANTS}
    report["uncertainty"]=crossed_bootstrap(targets,predictions,references,list(VIDEOS),groups,request["draws"],request["seed"])if report["aggregate_status"]=="defined"else {"status":"unavailable_full_denominator"}
    report["protected_reference_binding_identity"]=manifest["reference_binding_identity"];report["protected_reference_bindings"]=bindings
    report["condition"]=manifest["condition"];report["arm"]=manifest["arm"]
    return dump(Path("/output")/"report.json",report)

