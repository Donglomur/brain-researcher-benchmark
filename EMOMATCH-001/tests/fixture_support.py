"""Manufactured evidence and exclusive test emitter; no original source reads."""
import copy
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np

import numerical_contract as n
import reference_composition as c
import proof_of_work as p


def documents():
    root=Path(__file__).resolve().parents[1]/"environment"
    method=p.authenticated_json(root/"method_contract.json",p.METHOD_SHA256)
    schema=p.authenticated_json(root/"output_schema.json",p.SCHEMA_SHA256)
    return method,schema


def manufactured_reference(n_people=3, n_frames=80, *, identical_arms=False, missing_condition=False):
    method,schema=documents()
    ids=method["participant_ids"][:n_people]
    rois=[str(i) for i in range(1,101)]+list(c.SPHERES)
    rng=np.random.default_rng(618)
    records=[]
    for s in ids:
        for role in ("bold","confounds","events","raw_bold_json","preproc_bold_json"):
            records.append(dict(participant_id=s,role=role,path=s+"_"+role,size_bytes=17,sha256="a"*64))
    for role in ("atlas_image","atlas_labels","task_bold_json","participants_schema"):
        records.append(dict(participant_id=None,role=role,path=role,size_bytes=17,sha256="b"*64))
    subjects=[]
    for j,s in enumerate(ids):
        onsets=np.arange(6)*18.+2
        rt=np.full(6,1.) if identical_arms else np.asarray([.7,1.4,.9,1.8,1.1,1.2])+j*.02
        missing=np.zeros(6,dtype=bool)
        missing[3]=True
        rt[3]=0
        conditions=np.asarray(["control","emotion"]*3)
        if missing_condition: conditions[:]= "control"
        ledger=[]
        for k in range(6):
            tokens=dict(onset=str(onsets[k]),duration="4.8",response_time="n/a" if missing[k] else str(rt[k]),trial_type=str(conditions[k]))
            numeric={key:dict(token=tokens[key],status="missing" if tokens[key]=="n/a" else "finite",
                              value=None if tokens[key]=="n/a" else float(tokens[key]))
                     for key in ("onset","duration","response_time")}
            ledger.append(dict(source_row_index=k,original=tokens,numeric=numeric,included_condition=True))
        raw=100.+rng.normal(size=(n_frames,111))*(1+j*.1)
        raw[:,0]=.1
        header=dict(shape=[5,5,5,n_frames],chosen_affine=np.eye(4).tolist(),spatial_unit="mm",temporal_unit="sec",
            header_tr_raw=2.,effective_slope=1.,effective_intercept=0.,qform_code=1,sform_code=1,dtype="<f4",
            raw_scaling_slope=1.,raw_scaling_intercept=0.,raw_scaling_nonfinite=dict(slope=False,intercept=False),
            header_toffset_raw=0.,header_toffset_nonfinite=False)
        subjects.append(dict(participant_id=s,header=header,raw_roi_mean=raw,
            sidecars={"raw_bold_json":{"NumberOfVolumesDiscardedByScanner":2}},
            confound_raw=rng.normal(size=(n_frames,13)),confound_missing=np.zeros((n_frames,13),dtype=bool),
            confound_names=list(n.CONFOUNDS),event_column_names=list(ledger[0]["original"]),confound_column_names=list(n.CONFOUNDS),
            events=dict(ledger=ledger,selected_source_event_row=np.arange(6),conditions=conditions,onsets=onsets,
                response_time=rt,response_time_missing=missing),
            supports=[dict(roi_id=key,n_voxels=1,support_sha256=hashlib.sha256(key.encode()).hexdigest()) for key in rois]))
    primitives=dict(participant_ids=ids,roi_ids=rois,source_records=records,
        source_documents={"derivative_description":'{"PipelineDescription":{"Version":"0+unknown"}}',
                          "participants_schema":'{"NEO_A":{"Description":"same"},"NEO_A":{"Description":"same"}}'},
        source_proof=dict(manifest_sha256=p.SOURCE_SHA256),
        cohort_rows=[dict(source_row=j,participant_id=s,selected=True) for j,s in enumerate(ids)]+[
            dict(source_row=n_people,participant_id="sub-unselected",selected=False)],subjects=subjects,
        atlas=dict(header=dict(shape=[5,5,5],chosen_affine=np.eye(4).tolist(),spatial_unit="mm"),
            lut=[dict(label_id=i,name=f"7Networks_LH_{c.NETWORKS[(i-1)%7]}_{i}",network=c.NETWORKS[(i-1)%7]) for i in range(1,101)]),
        task_timing=dict(SliceTiming=[2*i/36 for i in range(36)]))
    ref=c.compile_reference(primitives,method,p.METHOD_SHA256)
    ref["schema"]=schema
    return ref


def payload(reference):
    metadata=copy.deepcopy(reference["metadata"])
    metadata.update(software_versions={"fixture":"manufactured"},warnings=[])
    for fit in metadata["fits"]: fit.update(solver={"implementation":"scipy.gesvd"},warnings=[])
    return {"cohort.csv":copy.deepcopy(reference["cohort"]),"events.csv":copy.deepcopy(reference["events"]),
            "roi_support.csv":copy.deepcopy(reference["supports"]),"activation.csv":copy.deepcopy(reference["activation"]),
            "glm_arrays.npz":{k:v.copy() for k,v in reference["arrays"].items()},
            "group_stats.json":copy.deepcopy(reference["groups"]),"run_metadata.json":metadata,
            "findings.md":"Manufactured signed sensitivity, with no required direction.\n"}


def json_default(value):
    if isinstance(value,Decimal): return float(value)
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    raise TypeError(type(value).__name__)


def emit(path,data):
    path=Path(path)
    path.mkdir()
    for name,value in data.items():
        target=path/name
        if name.endswith(".npz"):
            with target.open("xb") as h: np.savez_compressed(h,**value)
        elif name.endswith(".csv"):
            with target.open("x",newline="",encoding="utf8") as h:
                writer=csv.DictWriter(h,fieldnames=list(value[0]))
                writer.writeheader()
                for row in value:
                    writer.writerow({k:("" if v is None else int(v) if type(v) is bool else v) for k,v in row.items()})
        elif name.endswith(".json"):
            with target.open("x",encoding="utf8") as h: json.dump(value,h,default=json_default,allow_nan=False)
        else:
            with target.open("x",encoding="utf8") as h: h.write(value)
    return path


def coherent_permutation(arrays):
    a={k:v.copy() for k,v in arrays.items()}
    rng=np.random.default_rng(923)
    sp,rp,cp,jp=[rng.permutation(len(a[k])) for k in ("participant_id","roi_id","confound_name","column_key")]
    fp,mp,op=[rng.permutation(len(a[k])) for k in ("source_frame_index","fit_model","observation_fit_index")]
    si,fi,mi=np.argsort(sp),np.argsort(fp),np.argsort(mp)
    for key,perm in (("participant_id",sp),("roi_id",rp),("confound_name",cp),("column_key",jp)): a[key]=arrays[key][perm]
    a["frame_subject_index"]=si[arrays["frame_subject_index"][fp]]
    for key in ("source_frame_index","frame_time_s"): a[key]=arrays[key][fp]
    for key in ("roi_mean","roi_normalized"): a[key]=arrays[key][np.ix_(fp,rp)]
    for key in ("roi_raw_mean","roi_raw_sd","normalization_denominator"): a[key]=arrays[key][np.ix_(sp,rp)]
    for key in ("confound_effective","confound_was_missing"): a[key]=arrays[key][np.ix_(fp,cp)]
    a["fit_subject_index"]=si[arrays["fit_subject_index"][mp]]
    a["fit_model"]=arrays["fit_model"][mp]
    a["observation_fit_index"]=mi[arrays["observation_fit_index"][op]]
    a["observation_frame_index"]=fi[arrays["observation_frame_index"][op]]
    a["design_matrix"]=arrays["design_matrix"][np.ix_(op,jp)]
    for key in ("column_present","contrast_vector"): a[key]=arrays[key][np.ix_(mp,jp)]
    a["beta"]=arrays["beta"][np.ix_(mp,jp,rp)]
    for key in ("contrast_estimate","contrast_defined","residual_sse"): a[key]=arrays[key][np.ix_(mp,rp)]
    for key in ("design_rank","residual_df","contrast_estimable"): a[key]=arrays[key][mp]
    return a
