"""Manufactured basis and serializer for verifier fixtures; no original IO."""
from __future__ import annotations
import copy
import csv
import json
from pathlib import Path
import numpy as np
import isc_math as m
import proof_of_work as p


def manufactured_reference(kind="variable"):
    ids=[f"sub-pixar{i:03d}" for i in (*range(1,32),*range(123,132))]
    rng=np.random.default_rng(129)
    x=rng.normal(size=(40,168,3))
    if kind=="constant": x.fill(.1)
    elif kind=="identical": x[:]=x[0]
    elif kind=="negative":
        z=np.zeros((40,168)); z[:,:40]=np.eye(40)-1/40
        x=np.repeat(z[:,:,None],3,axis=2)
    elif kind!="variable": raise ValueError("unknown manufactured basis")
    support=m.support(x)
    mids=np.arange(39); labels=np.array([f"map_{i}" for i in mids],dtype="U20")
    visual=np.array([3,12,20]); labels[visual]=["Vis","Striate","Occ post"]
    rows=[]; headers=[]
    for i,person in enumerate(ids):
        rows.append(dict(participant_id=person,participant_source_row=i,bold_path=person+".nii.gz",confounds_path=person+".tsv",
                         n_frames=168,n_confound_rows=168,n_maps=39,map_rank=39,nuisance_rank=15,
                         n_active_visual=int(support["person_active"][i].sum()),status="ok"))
        headers.append(dict(participant_id=person,shape=[2,2,2,168],affine=np.eye(4).tolist(),source_dtype="int8",
                            spatial_units="unknown",temporal_units="unknown",raw_TR=1.,raw_toffset=0.,
                            effective_scaling_slope=.5,effective_scaling_intercept=2.))
    observed=dict(participant_ids=ids,map_labels=[dict(map_id=int(i),map_label=str(label)) for i,label in zip(mids,labels)],
                  visual_map_ids=visual.tolist(),headers=headers,
                  atlas_header=dict(shape=[2,2,2,39],affine=np.eye(4).tolist(),source_dtype="float32",spatial_units="mm",
                                    effective_scaling_slope=1.,effective_scaling_intercept=0.),
                  confound_column_names={person:["a","b"] for person in ids},participant_column_names=["participant_id"],
                  effective_TR_s=2.,effective_origin_s=0.,frame_alignment="released_frame_index_only_no_measured_movie_onset")
    meta=dict(schema_version="moviesync-metadata-v2",status="ok",task_id="MOVIESYNC-001",method_sha256="a"*64,
              output_schema_sha256="b"*64,source_manifest_sha256="c"*64,
              source_files=[dict(path="manufactured",role="provenance",participant_id=None,size_bytes=1,sha256="d"*64)],
              source_observed=observed,software_versions={key:"manufactured" for key in ("python","numpy","scipy","nibabel","nilearn")})
    return dict(participant_ids=np.asarray(ids),map_ids=mids,map_labels=labels,visual_map_ids=visual,frame_indices=np.arange(168),
                raw_coefficients=rng.normal(size=(40,168,39)),isc_inputs=x,canonical_support=support,cohort=rows,metadata=meta)


def csv_write(path,rows):
    if not rows: raise ValueError("fixture needs rows")
    with open(path,"x",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def emit(root,ref,estimator="pairwise",*,inputs=None):
    root=Path(root); root.mkdir(exist_ok=False)
    x=ref["isc_inputs"] if inputs is None else inputs
    support=m.support(ref["isc_inputs"])
    arrays={name:ref[name] for name in ("participant_ids","map_ids","map_labels","visual_map_ids","frame_indices","raw_coefficients")}
    arrays.update(isc_inputs=x,person_active=support["person_active"],template_active=support["template_active"])
    with open(root/"timecourses.npz","xb") as stream: np.savez_compressed(stream,**arrays)
    pairs,people,result=p.expected_tables_and_results(x,support,ref,estimator)
    csv_write(root/"cohort.csv",ref["cohort"])
    csv_write(root/"isc_pairs.csv",pairs); csv_write(root/"isc_per_subject.csv",people)
    metadata=copy.deepcopy(ref["metadata"]); metadata["isc_estimator"]=estimator
    for name,value in (("isc_results.json",result),("run_metadata.json",metadata)):
        with open(root/name,"x",encoding="utf-8") as handle: json.dump(value,handle,allow_nan=False)
    with open(root/"findings.md","x",encoding="utf-8") as handle:
        handle.write("Manufactured fixture only. Signed or undefined results are legitimate; no significance claim.\n")
    return root
