#!/usr/bin/env python3
"""Parent-launched original-NWB bank rebuild; no solution imports.

Independently reloads original source identity and row mappings, and uses
math.fsum on each original frame window. The verifier independently derives
condition means and both named sensitivity endpoints from these measured trial
means. Synthetic fixture checks do not constitute source validation.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path,PurePosixPath
import sys
import tempfile

import h5py
import numpy as np

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q

BASE="/processing/brain_observatory_pipeline"
DFF=BASE+"/DfOverF/imaging_plane_1"
CELLS=BASE+"/ImageSegmentation"
STIM="/stimulus/presentation/drifting_gratings_stimulus"


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b""):digest.update(block)
    return digest.hexdigest()


def text(value):
    value=np.asarray(value)
    if value.shape==():value=value.item()
    elif value.size==1:value=value.reshape(-1)[0]
    else:raise AssertionError("scalar source text required")
    if isinstance(value,(bytes,np.bytes_)):return value.decode("utf-8")
    assert isinstance(value,(str,np.str_)),"source text required"
    return str(value)


def source_integer(values,name):
    values=np.asarray(values)
    assert values.dtype.kind in "iuf" and np.isfinite(values).all(),name+": finite numeric IDs required"
    assert np.equal(values,np.floor(values)).all(),name+": noninteger values"
    assert np.all(abs(values)<2**63),name+": out-of-range integer"
    return values.astype(np.int64)


def read_nwb_arrays(path):
    """Actual-source execution: only call under the approved parent run contract."""
    with h5py.File(path,"r") as handle:
        cells=source_integer(handle[CELLS+"/cell_specimen_ids"][:],"cell identifiers")
        rois=np.asarray([text(value) for value in handle[CELLS+"/roi_ids"][:]])
        data=handle[DFF+"/data"]
        assert data.ndim==2 and data.shape[0]==len(cells)==len(rois),"cell row/data pairing mismatch"
        assert len(set(cells))==len(cells) and len(set(rois))==len(rois)
        assert float(data.attrs.get("conversion",1))==1.,"unexpected source dF/F conversion"
        times=np.asarray(handle[DFF+"/timestamps"][:],float)
        assert times.shape==(data.shape[1],) and np.isfinite(times).all() and np.all(np.diff(times)>0)
        feature_names=[text(value) for value in handle[STIM+"/features"][:]]
        assert len(feature_names)==len(set(feature_names)) and set(("orientation","temporal_frequency","blank_sweep"))<=set(feature_names)
        features=np.asarray(handle[STIM+"/data"][:],float)
        bounds=source_integer(handle[STIM+"/frame_duration"][:],"stimulus bounds")
        assert features.shape==(len(bounds),len(feature_names)) and bounds.shape==(len(features),2)
        assert len(features)>0 and not np.isinf(features).any(),"invalid source stimulus metadata"
        start,end=bounds[:,0],bounds[:,1]
        assert np.all((0<=start)&(start<end)&(end<=data.shape[1])),"invalid custom half-open frame windows"
        rows=np.arange(len(start));order=np.lexsort((rows,end,start))
        raw_blank=source_integer(features[:,feature_names.index("blank_sweep")],"blank_sweep")
        arrays=dict(cell_ids=cells,roi_ids=rois,source_row_ids=rows[order],start_frame=start[order],end_frame=end[order],
            direction=features[order,feature_names.index("orientation")],
            temporal_frequency=features[order,feature_names.index("temporal_frequency")],blank_sweep=raw_blank[order])
        response=np.empty((len(cells),len(order)),dtype=np.float64)
        for column,(a,b) in enumerate(zip(arrays["start_frame"],arrays["end_frame"])):
            window=np.asarray(data[:,int(a):int(b)],dtype=np.float64)
            assert np.isfinite(window).all(),"nonfinite original response-window sample"
            assert window.shape==(len(cells),b-a)
            for cell in range(len(cells)):
                response[cell,column]=math.fsum(window[cell].tolist())/int(b-a)
        assert np.isfinite(response).all(),"nonfinite original trial mean"
        arrays["trial_response"]=response
        metadata=dict(ophys_experiment_id=q.integer(text(handle["/general/session_id"][()])),
            targeted_structure=text(handle["/general/optophysiology/imaging_plane_1/location"][()]),
            session_type=text(handle["/general/session_type"][()]),n_source_frames=data.shape[1])
    return arrays,metadata


def original_reference(source_dir,contract_path):
    source_dir=Path(source_dir);contract_path=Path(contract_path)
    contract=q.read_json(contract_path)
    manifest_path=source_dir/"source_manifest.json"
    manifest=q.read_json(manifest_path)
    expected=contract["input"]
    records=manifest.get("files")
    assert isinstance(records,list) and len(records)==1,"one exact original NWB source required"
    item=records[0];relative=PurePosixPath(item["path"])
    assert not relative.is_absolute() and ".." not in relative.parts and str(relative)==expected["file"]
    path=source_dir.joinpath(*relative.parts)
    assert path.is_file() and not path.is_symlink() and path.stat().st_size==q.integer(item["size_bytes"])
    digest=sha256(path)
    assert digest==item["sha256"]==expected["source_sha256"],"original NWB identity mismatch"
    arrays,source_metadata=read_nwb_arrays(path)
    for key in ("ophys_experiment_id","targeted_structure","session_type"):
        assert source_metadata[key]==expected[key],f"source {key} mismatch"
    use=(arrays["blank_sweep"]<=0)&np.isfinite(arrays["direction"])&np.isfinite(arrays["temporal_frequency"])
    directions=np.unique(arrays["direction"][use]);frequencies=np.unique(arrays["temporal_frequency"][use])
    metadata=dict(status="ok",task_id=q.TASK_ID,method="same_trials",source_manifest_sha256=sha256(manifest_path),
        source_nwb_sha256=digest,method_contract_sha256=sha256(contract_path),source_sha256={expected["file"]:digest},
        **source_metadata,n_neurons_total=len(arrays["cell_ids"]),n_presentations_total=len(arrays["source_row_ids"]),
        n_presentations_nonblank=int(use.sum()),n_conditions=len(directions)*len(frequencies),
        directions_deg=directions.tolist(),temporal_frequencies_hz=frequencies.tolist(),
        software_versions={name:importlib.metadata.version(name) for name in ("numpy","h5py")},
        method_contract=contract)
    reference={**arrays,"stats":dict(pipeline_id=q.PIPELINE_ID,metadata=metadata,
        evidence={"trial_mean":"math.fsum(original float32 samples cast to float64)/half-open frame count",
                  "source_reloaded":True,"solution_imported":False,
                  "lineage":"Original NWB source-local SHA-256 snapshot, not an upstream immutable-version claim"})}
    return q.validate_reference(reference)


def build(args):
    reference=original_reference(args.data_dir,args.method_contract)
    for output,expected_method in ((args.same_output,"same_trials"),(args.split_output,"repeated_split_mean_ratio")):
        assert q.read_json(Path(output)/"results.json").get("method")==expected_method,"wrong genuine-output method"
        q.validate_output_directory(output,reference)
    bank={"ref_"+key:reference[key] for key in q.SOURCE_ARRAYS}
    bank["ref_stats"]=np.asarray(json.dumps(reference["stats"],allow_nan=False))
    target=Path(args.reference);target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix=".reference-",suffix=".npz",delete=False) as stream:
            temporary=Path(stream.name);np.savez_compressed(stream,**bank)
        q.load_reference(temporary)
        temporary.replace(target)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
    print(json.dumps(dict(status="ok",reference=str(target),sha256=sha256(target),
        n_cells=len(reference["cell_ids"]),n_presentations=len(reference["source_row_ids"])),allow_nan=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=Path("/app/source"))
    parser.add_argument("--method-contract",type=Path,default=Path("/app/method_contract.json"))
    parser.add_argument("--same-output",type=Path,required=True)
    parser.add_argument("--split-output",type=Path,required=True)
    parser.add_argument("--reference",type=Path,default=TASK/"tests/reference.npz")
    build(parser.parse_args())


if __name__=="__main__":main()

