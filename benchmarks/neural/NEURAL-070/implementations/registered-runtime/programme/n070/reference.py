"""Fixed full reference prediction caller; no query neural response is opened."""
from pathlib import Path
from .core import need
from .native.io import load,dump
from .numeric_io import array,save
from .protocol import MODELS,ROIS,MEASUREMENT_LABEL,REFERENCE_PRODUCER,reference_procedure_identity
def feature_views(root,manifest,model,cap):
    out={layer:{}for layer in ("layer1","layer2","layer3","layer4")}
    appearance={"static_center":"static_center","static_mean":"static_mean","static_orderless":"static_orderless",
                "static_motion_category":"static_orderless","dynamic_motion_category":"dynamic",
                "shuffled_motion_category":"shuffled","reverse_motion_category":"reverse"}
    for video,row in manifest["rows"].items():
        motion=array(root,row["motion"],cap)
        for layer in out:
            record={}
            if model!="motion_only":record["appearance"]=array(root,row["layers"][layer][appearance[model]],cap)
            if model=="motion_only"or model.endswith("_motion_category"):record["motion"]=motion
            if model.endswith("_motion_category"):record["category"]=row["category"]
            out[layer][video]=record
    return out
def run(request):
    from .models import choose_and_predict
    root=Path("/inputs");out=Path("/output");cap=request["member_bytes"];view=load(root/"view.json")
    need(view["measurement"]==MEASUREMENT_LABEL and view["roi_family"]==list(ROIS),"Exact conditional fixed ROI protocol")
    train=view["training_videos"];query=view["query_videos"];rows=view["training_trials"]
    need(all(r["video"]in train for r in rows) and set(train).isdisjoint(query),"Query responses absent from actor input")
    result={"participant":view["participant"],"fold":view["fold"],"query_videos":query,
            "measurement":MEASUREMENT_LABEL,"split_identity":view["split_identity"],"coordinate_identity":view["coordinate_identity"],"predictions":{},"fits":{},
            "producer":REFERENCE_PRODUCER,"procedure_identity":reference_procedure_identity()}
    for model in MODELS:
        features=feature_views(root,view["features"],model,cap)
        result["predictions"][model]={};result["fits"][model]={}
        for roi in ROIS:
            beta=array(root,view["responses"][roi],cap)
            prediction,fit=choose_and_predict(features,beta,rows,train,query,view["inner"])
            result["predictions"][model][roi]=save(out,"predictions/"+model+"/"+roi+".npy",prediction,cap)
            result["fits"][model][roi]=fit
    return dump(out/"predictions.json",result)

