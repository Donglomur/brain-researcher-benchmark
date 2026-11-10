"""Neutral training/query artifact stager; target joins stay protected."""
import struct
from pathlib import Path
from .io import need,canonical,identity,write_new,write_json,read_json
from .contract import ARMS,require_deployment

def npy_float64(rows):
    """Exact NPY1 little-endian C float64 matrix; preparation source, not run now."""
    need(rows and rows[0]and all(len(r)==len(rows[0])for r in rows),"Rectangular nonempty training matrix")
    header=repr({"descr":"<f8","fortran_order":False,"shape":(len(rows),len(rows[0]))})
    body=header.encode("ascii");pad=(16-((10+len(body)+1)%16))%16
    body+=b" "*pad+b"\n";need(len(body)<65536,"NPY1 header size")
    return b"\x93NUMPY\x01\x00"+struct.pack("<H",len(body))+body+b"".join(struct.pack("<d",float(x))for r in rows for x in r)


def feature_columns(arm):
    from .contract import CHANNELS,DURATIONS,RELEVANCES,ORIENTATIONS
    need(arm in ARMS,"Exact feature arm")
    signal="SIGNAL"if arm.startswith("SIGNAL")else"PRE"
    neural=[{"name":f"{signal}:{ch}:bin{b:02d}","units":"T","channel":ch,"bin_index":b}for ch in CHANNELS for b in range(10)]
    nuisance=[{"name":name+":"+v,"units":"indicator"}for name,values in(("Duration",DURATIONS),("Task_relevance",RELEVANCES),("Orientation",ORIENTATIONS))for v in values]
    return nuisance if arm=="NUISANCE"else neural+(nuisance if arm.endswith("_NUISANCE")else[])

def materialize_episode(episode,root):
    require_deployment();root=Path(root);need(not root.exists(),"Fresh source-neutral episode view")
    root.mkdir(parents=True)
    need(len(episode["train"])<=100000 and len(episode["query"])<=20000,"Complete per-fold train/query caps; never truncate")
    dim={"SIGNAL":60,"PRE":60,"NUISANCE":8,"SIGNAL_NUISANCE":68,"PRE_NUISANCE":68}[episode["feature_arm"]]
    need(all(len(r["x"])==dim for r in episode["train"]),"Exact selected feature projection")
    features=npy_float64([r["x"]for r in episode["train"]])
    rows=[{k:v for k,v in r.items()if k!="x"}for r in episode["train"]]
    fp=write_new(root/"features.npy",features,100_000_000)
    rp=write_json(root/"rows.json",rows,100_000_000)
    ip=write_json(root/"inner.json",episode["inner_validation"],16_000_000)
    train={"schema":"neural097-train-view-v2","opaque_episode_nonce":episode["opaque_episode_nonce"],
           "contract_version":episode["contract"],"access_arm":episode["access"],
           "feature_arm":episode["feature_arm"],"feature_columns":feature_columns(episode["feature_arm"]),
           "feature_units":"T means for SIGNAL/PRE columns; binary design indicators for NUISANCE",
           "features_member":{"path":"features.npy",**fp},"training_rows_member":{"path":"rows.json",**rp},
           "inner_validation_plan_member":{"path":"inner.json",**ip}}
    tp=write_json(root/"TRAIN_VIEW.json",train,1_000_000)
    query=[]
    for n,q in enumerate(episode["query"]):
        view={"schema":"neural097-query-v2","opaque_episode_nonce":episode["opaque_episode_nonce"],**q}
        qp=write_json(root/f"query-{n:06d}.json",view,100_000)
        query.append({"path":f"query-{n:06d}.json",**qp,"opaque_query_nonce":q["opaque_query_nonce"]})
    return {"path":str((root/"TRAIN_VIEW.json").absolute()),**tp,"opaque_episode_nonce":episode["opaque_episode_nonce"]},query

def read_training_view(root,view):
    """Executed only inside future qualified worker; no pickle/object arrays."""
    require_deployment()
    from .io import read
    import io
    import numpy as np
    root=Path(root)
    member=view["features_member"]
    b=read(root/member["path"],100_000_000,member)
    arr=np.load(io.BytesIO(b),allow_pickle=False)
    need(arr.dtype==np.dtype("<f8")and arr.ndim==2 and arr.flags.c_contiguous and np.isfinite(arr).all(),"Finite exact little-endian float64 training features")
    rows=read_json(root/view["training_rows_member"]["path"],100_000_000,view["training_rows_member"])
    need(len(rows)==len(arr),"Training row/features identity")
    inner=read_json(root/view["inner_validation_plan_member"]["path"],16_000_000,view["inner_validation_plan_member"])
    return [{**r,"x":arr[k].tolist()}for k,r in enumerate(rows)],inner
