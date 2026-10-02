"""Manufactured-only FCSTAB fixtures; never open a scientific source or bank."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

import output_contract as verifier
import selection_kernel as kernel


def freeze_manufactured_authority(monkeypatch):
    for key, character in (("SOURCE_SHA","1"),("METHOD_SHA","2"),("SCHEMA_SHA","3"),("IDS_SHA","4")):
        monkeypatch.setattr(verifier,key,character*64)
    raw = Path(kernel.__file__).read_bytes()
    monkeypatch.setattr(verifier,"KERNEL_SHA",hashlib.sha256(raw).hexdigest())


def reference(*, constant_edges=False, zero_delta=False):
    ids = [str(10000+i) for i in range(40)]
    fids = ["PITT_fixture_"+sid for sid in ids]
    mask = np.arange(200) < 4
    pairs = np.array([(i,j) for i in range(1,5) for j in range(i+1,5)],dtype=np.int64)
    z = np.random.default_rng(4321).uniform(-.3,.3,size=(40,3,len(pairs)))
    if constant_edges: z[:] = .1
    if zero_delta: z[:,1] = z[:,0]
    header = "\t".join("#"+str(i) for i in range(1,201))
    records = [dict(path="roi/"+fid+".1D",role="roi_timeseries",file_id=fid,subject_id=sid,
                    phenotype_row_index=i,size_bytes=100,sha256="5"*64) for i,(fid,sid) in enumerate(zip(fids,ids))]
    records += [dict(path="phenotype.csv",role="phenotype",size_bytes=100,sha256="6"*64),
                dict(path="notice.txt",role="provenance_abide_notice",size_bytes=100,sha256="7"*64)]
    ledger = []
    for i in range(1112):
        selected = i < 40
        fid = fids[i] if selected else ("other_"+str(i) if i<1035 else "no_filename")
        ledger.append(dict(phenotype_row_index=i,file_id=fid,subject_id=ids[i] if selected else str(20000+i),
                           source_subject_id_token=ids[i] if selected else str(20000+i),selected_derivative=selected,
                           source_path=records[i]["path"] if selected else None,
                           tokens={"SITE_ID":"PITT" if selected else "OTHER","EYE_STATUS_AT_SCAN":"1"}))
    persons = {}
    for i,(fid,sid) in enumerate(zip(fids,ids)):
        persons[fid] = dict(source_path=records[i]["path"],source_sha256=records[i]["sha256"],subject_id=sid,
                           phenotype_row_index=i,tokens=ledger[i]["tokens"],n_frames=196,n_columns=200,L=98,
                           header=header,header_sha256=hashlib.sha256(header.encode()).hexdigest(),
                           source_column_ids=list(range(1,201)),all_finite=True,
                           segment_support={name:mask.tolist() for name in verifier.SEGMENTS},
                           exact_constant_mask={name:(~mask).tolist() for name in verifier.SEGMENTS})
    observed = dict(n_source_files=42,source_bytes=16147721,n_selected_derivatives=40,total_frames=7840,
                    n_phenotype_rows=1112,n_named_phenotype_rows=1035,n_no_filename_rows=77,
                    phenotype_columns=["FILE_ID","SUB_ID","SITE_ID","EYE_STATUS_AT_SCAN"],
                    phenotype_ledger=ledger,persons=persons,segment_ids=list(verifier.SEGMENTS),roi_ids=list(range(1,201)),
                    common_roi_mask=mask.tolist(),clock={"TR_verified":False,"frame_order":"original source row order"})
    return dict(status="complete",participant_file_ids=fids,subject_ids=ids,roi_ids=np.arange(1,201),
                segment_ids=list(verifier.SEGMENTS),common_roi_mask=mask,edge_roi_i=pairs[:,0],edge_roi_j=pairs[:,1],
                fisher_z=z,source_files=records,source_observed=observed,pins=verifier.pins())


def artifacts(ref, *, z=None, accepted_rows=None, accepted_reliability=None):
    z = ref["fisher_z"].copy() if z is None else np.asarray(z)
    pairs = np.column_stack((ref["edge_roi_i"],ref["edge_roi_j"]))
    replay = kernel.analyze(z,ref["fisher_z"],ref["subject_ids"],pairs,accepted_rows=accepted_rows,
                            accepted_reliability=accepted_reliability)
    arrays = dict(subject_ids=np.array(ref["subject_ids"]),segment_ids=np.array(verifier.SEGMENTS),
                  roi_ids=np.arange(1,201),common_roi_mask=ref["common_roi_mask"].copy(),
                  edge_roi_i=pairs[:,0].copy(),edge_roi_j=pairs[:,1].copy(),fisher_z=z.copy())
    subjects = []
    for sid in ref["subject_ids"]:
        row = dict(subject_id=sid,**copy.deepcopy(replay["evidence"][sid]))
        if accepted_reliability is not None: row["reliability"] = copy.deepcopy(accepted_reliability[sid])
        subjects.append(row)
    evidence = dict(schema_version="fcstab-selection-v3",task_id="FCSTAB-001",status="complete",pins=verifier.pins(),
                    n_edges=replay["n_edges"],k=replay["k"],seed=0,subjects=subjects)
    summary = dict(schema_version="fcstab-summary-v3",task_id="FCSTAB-001",status="complete",pins=verifier.pins(),n_subjects=40,
                   cohort=[dict(file_id=fid,subject_id=sid) for fid,sid in zip(ref["participant_file_ids"],ref["subject_ids"])],
                   source_files=copy.deepcopy(ref["source_files"]),source_observed=copy.deepcopy(ref["source_observed"]),
                   software=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
                   source_inference_support={scheme:{"status":replay["support_diagnostics"][scheme]["status"]} for scheme in verifier.SCHEMES},
                   **copy.deepcopy(replay["summaries"]))
    return {"connectivity.npz":arrays,"stability.csv":copy.deepcopy(replay["rows"]),
            "selection_evidence.json":evidence,"summary.json":summary,"findings.md":"Manufactured selection-sensitivity fixture.\n"}


def write_output(root, data):
    root = Path(root)
    root.mkdir(exist_ok=False)
    for name,value in data.items():
        path = root/name
        if name.endswith(".npz"):
            with path.open("xb") as handle: np.savez_compressed(handle,**value)
        elif name.endswith(".csv"):
            with path.open("x",newline="",encoding="utf-8") as handle:
                writer = csv.DictWriter(handle,fieldnames=list(value[0]))
                writer.writeheader(); writer.writerows(value)
        elif name.endswith(".json"):
            with path.open("x",encoding="utf-8") as handle: json.dump(value,handle,allow_nan=False)
        else:
            with path.open("x",encoding="utf-8") as handle: handle.write(value)
    return root


def permute_axes(data):
    """Coherent storage changes, including selected indices in submitted axis."""
    arrays = data["connectivity.npz"]
    p = np.arange(39,-1,-1); s = np.array([2,0,1]); e = np.arange(len(arrays["edge_roi_i"])-1,-1,-1)
    arrays["subject_ids"] = arrays["subject_ids"][p]
    arrays["segment_ids"] = arrays["segment_ids"][s]
    arrays["fisher_z"] = arrays["fisher_z"][np.ix_(p,s,e)]
    arrays["roi_ids"] = arrays["roi_ids"][::-1]
    arrays["common_roi_mask"] = arrays["common_roi_mask"][::-1]
    arrays["edge_roi_i"] = arrays["edge_roi_i"][e]
    arrays["edge_roi_j"] = arrays["edge_roi_j"][e]
    inverse = {int(old):new for new,old in enumerate(e)}
    for row in data["selection_evidence.json"]["subjects"]:
        for scheme in verifier.SCHEMES:
            row[scheme+"_edge_indices"] = [inverse[v] for v in row[scheme+"_edge_indices"]][::-1]
        row["training_subject_ids"].reverse()
    data["selection_evidence.json"]["subjects"].reverse()
    data["stability.csv"].reverse()
    for key in ("cohort","source_files"):
        data["summary.json"][key].reverse()
    data["summary.json"]["source_observed"]["phenotype_ledger"].reverse()
