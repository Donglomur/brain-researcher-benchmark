"""Third original-source implementation: bincount parcels, GELSD span, BFS graph.

No reference-solution/checker imports and no participant CSV used as source.
Only a parent-authorized full run may replace the historical answer bank.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import platform
import tempfile
import numpy as np
import scipy
from scipy import linalg
import graph_contract as graph
import proof_of_work as proof

CONFOUNDS = ("csf","constant","linearTrend","wm","global","motion-pitch",
    "motion-roll","motion-yaw","motion-x","motion-y","motion-z","gm",
    "compcor1","compcor2","compcor3","compcor4","compcor5")
SHAPE = (61,73,61)
AFFINE = np.array([[-3,0,0,90],[0,3,0,-126],[0,0,3,-72],[0,0,0,1]],float)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    graph.require(not any(p.is_symlink() for p in (path,*path.parents)), "Source path or ancestor is a symlink")


def load_sources(root,method_path):
    root,method_path = Path(root),Path(method_path)
    no_symlink(root)
    no_symlink(method_path)
    graph.require(root.is_dir() and method_path.is_file(), "Source directory and public method file required")
    graph.require(len(proof.METHOD_SHA256) == 64 and len(proof.SOURCE_MANIFEST_SHA256) == 64,
        "No source/method freeze; source reading prohibited")
    graph.require(sha256(method_path) == proof.METHOD_SHA256, "Frozen method checksum mismatch")
    manifest_path = root/"source_manifest.json"
    no_symlink(manifest_path)
    graph.require(sha256(manifest_path) == proof.SOURCE_MANIFEST_SHA256, "Frozen source manifest checksum mismatch")
    method,manifest = graph.read_json(method_path),graph.read_json(manifest_path)
    graph.require(method["pipeline_id"] == graph.PIPELINE_ID, "Wrong method pipeline")
    graph.require(isinstance(manifest.get("files"),list) and manifest["files"], "Source manifest file list missing")
    expected,identities = {"source_manifest.json"},set()
    for record in manifest["files"]:
        relative = record["path"]
        pure = PurePosixPath(relative)
        graph.require(not pure.is_absolute() and ".." not in pure.parts and str(pure) == relative, "Invalid source-relative path")
        graph.require(relative not in expected, "Duplicate manifest file identity")
        expected.add(relative)
        path = root/relative
        no_symlink(path)
        graph.require(path.is_file() and path.stat().st_size == graph.integer(record["size_bytes"]), "Source member missing or wrong size")
        graph.require(sha256(path) == record["sha256"], "Original source member checksum mismatch")
        if record["role"] in ("bold","confounds"):
            identity = (graph.integer(record["participant"]),record["role"])
            graph.require(identity not in identities, "Duplicate participant-role source member")
            identities.add(identity)
    graph.require(identities == {(p,r) for p in graph.PARTICIPANTS for r in ("bold","confounds")}, "Exact40 original BOLD-confound joins required")
    actual = set()
    for path in root.rglob("*"):
        graph.require(not path.is_symlink(), "Unexpected symlink in staged source")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    graph.require(actual == expected, "Extra/missing staged source member")
    return method,manifest


def explicit_nearest(labels,source_affine,target_shape=SHAPE,target_affine=AFFINE):
    """Direct index mapping, not oracle's scipy.ndimage.affine_transform."""
    labels = np.asarray(labels)
    graph.require(labels.ndim == 3 and np.isfinite(labels).all() and np.array_equal(labels,np.floor(labels)), "Invalid original label image")
    transform = np.linalg.inv(np.asarray(source_affine,dtype=np.float64)) @ target_affine
    target = np.indices(target_shape,dtype=np.float64).reshape(3,-1)
    coordinates = transform[:3,:3] @ target + transform[:3,3,None]
    valid = np.all((coordinates >= 0) & (coordinates <= (np.asarray(labels.shape)-1)[:,None]),axis=0)
    nearest = np.floor(coordinates[:,valid]+.5).astype(np.int64)
    result = np.zeros(target.shape[1],dtype=np.int16)
    result[valid] = labels[tuple(nearest)].astype(np.int16)
    return result.reshape(target_shape,order="C")


def independent_clean(raw,confounds):
    """GELSD nuisance coefficients, not oracle U U.T residual projection."""
    raw,confounds = np.asarray(raw,dtype=np.float64),np.asarray(confounds,dtype=np.float64)
    graph.require(raw.ndim == confounds.ndim == 2 and len(raw) == len(confounds) and len(raw)>1, "Invalid original signal/confound shape")
    graph.require(np.isfinite(raw).all() and np.isfinite(confounds).all(), "Nonfinite original signal/confound")
    graph.require(not np.any(np.all(raw == raw[0],axis=0)), "Exactly constant original parcel")
    constant = np.all(confounds == confounds[0],axis=0)
    design = confounds[:,~constant].copy()
    design -= design.mean(axis=0)
    scale = np.sqrt(np.mean(design**2,axis=0))
    graph.require(np.all(scale>0) and np.isfinite(scale).all(), "Nonconstant confound has invalid scale")
    design /= scale
    centered = raw-raw.mean(axis=0)
    n,k = design.shape
    epsilon = np.finfo(np.float64).eps
    if k:
        coefficients,_,rank,singular = linalg.lstsq(design,centered,cond=max(n,k)*epsilon,lapack_driver="gelsd")
        threshold = max(n,k)*epsilon*singular[0]
        graph.require(rank == np.sum(singular>threshold), "Independent least-squares rank differs from declared SVD rule")
        residual = centered-design@coefficients
    else:
        rank,threshold = 0,0.
        residual = centered.copy()
    residual -= residual.mean(axis=0)
    original_norm = np.linalg.norm(centered,axis=0)
    norm = np.linalg.norm(residual,axis=0)
    bound = 10*max(n,k)*epsilon*np.maximum(original_norm,np.finfo(np.float64).tiny)
    graph.require(np.all(original_norm>0) and np.isfinite(norm).all() and np.all(norm>bound), "Numerically unresolved residual parcel")
    standardized = residual/(norm/np.sqrt(n-1))
    upper = np.triu_indices(raw.shape[1],1)
    weights = np.array([np.dot(standardized[:,i],standardized[:,j])/(n-1) for i,j in zip(*upper)])
    graph.require(np.isfinite(weights).all() and np.max(np.abs(weights)) <= 1+1e-12, "Invalid empirical Pearson weights")
    info = dict(constant_confound_columns=[name for name,flag in zip(CONFOUNDS,constant) if flag],
        retained_confound_columns=[name for name,flag in zip(CONFOUNDS,constant) if not flag],
        confound_rank=int(rank),confound_rank_threshold=float(threshold))
    return weights,info,dict(raw=raw,cleaned=standardized,residual_norm=norm,residual_zero_bound=bound)


def image_physics(image):
    spatial,temporal = image.header.get_xyzt_units()
    return dict(storage_dtype=str(image.get_data_dtype()),intensity_slope=float(image.dataobj.slope),
        intensity_intercept=float(image.dataobj.inter),spatial_units=spatial,temporal_units=temporal)


def source_recompute(root,method_path):
    import nibabel as nib
    root = Path(root)
    method,manifest = load_sources(root,method_path)
    by_role = {}
    for record in manifest["files"]:
        by_role.setdefault(record["role"],[]).append(record)
    graph.require(len(by_role.get("atlas_image",[])) == len(by_role.get("atlas_labels",[])) == 1, "Exact original atlas image and label table required")
    atlas_record,lut_record = by_role["atlas_image"][0],by_role["atlas_labels"][0]
    image = nib.load(root/atlas_record["path"])
    atlas = image.get_fdata(dtype=np.float64)
    graph.require(np.array_equal(np.unique(atlas),np.arange(101)), "Original atlas label membership differs")
    names = {}
    for line in (root/lut_record["path"]).read_text().splitlines():
        columns = line.split()
        graph.require(len(columns) == 6, "Original LUT structure differs")
        roi = graph.integer(columns[0])
        graph.require(roi not in names, "Duplicate original LUT ID")
        names[roi] = columns[1]
    graph.require(set(names) == set(range(1,101)), "Incomplete original ROI IDs")
    resampled = explicit_nearest(atlas,image.affine)
    labels = resampled.ravel(order="C").astype(np.int64)
    counts = np.bincount(labels,minlength=101)[1:]
    graph.require(np.all(counts>0), "All100 source parcels must survive resampling")
    atlas_observed = dict(image_path=atlas_record["path"],label_table_path=lut_record["path"],
        source_shape=list(image.shape),source_affine=image.affine.tolist(),source_label_ids=list(range(101)),
        target_shape=list(SHAPE),target_affine=AFFINE.tolist(),**image_physics(image),
        parcels=[dict(roi_id=i,label=names[i],n_voxels=int(counts[i-1])) for i in range(1,101)])
    records = {(r.get("participant"),r["role"]):r for r in manifest["files"]}
    observations,weights = [],[]
    for participant in graph.PARTICIPANTS:
        bold,confound_record = records[participant,"bold"],records[participant,"confounds"]
        image = nib.load(root/bold["path"])
        graph.require(len(image.shape)==4 and image.shape[:3]==SHAPE and np.array_equal(image.affine,AFFINE), "Original BOLD grid differs")
        graph.require(image.header.get_xyzt_units()==("mm","sec"), "Wrong original BOLD units")
        data = image.get_fdata(dtype=np.float64)
        graph.require(np.isfinite(data).all(), "Nonfinite original BOLD")
        n_frames = data.shape[-1]
        flattened = data.reshape((-1,n_frames),order="C")
        raw = np.stack([np.bincount(labels,weights=flattened[:,frame],minlength=101)[1:]/counts for frame in range(n_frames)])
        del data,flattened
        with (root/confound_record["path"]).open(newline="") as stream:
            reader = csv.DictReader(stream,delimiter="\t")
            graph.require(tuple(reader.fieldnames or ())==CONFOUNDS, "Original17 confound column order differs")
            rows = list(reader)
        graph.require(len(rows)==n_frames and all(None not in row and None not in row.values() for row in rows), "Confound-frame membership differs")
        confounds = np.array([[graph.number(row[name]) for name in CONFOUNDS] for row in rows])
        value,info,_ = independent_clean(raw,confounds)
        weights.append(value)
        observations.append(dict(participant=participant,bold_path=bold["path"],confounds_path=confound_record["path"],
            bold_shape=list(image.shape),affine=image.affine.tolist(),voxel_sizes_mm=list(map(float,image.header.get_zooms()[:3])),
            tr_s=float(image.header.get_zooms()[3]),n_frames=n_frames,n_confounds=17,confound_columns=list(CONFOUNDS),
            all_inputs_finite=True,all_residual_parcels_nonconstant=True,**image_physics(image),**info))
        print(json.dumps(dict(participant=participant,n_frames=n_frames,status="source_recomputed")),flush=True)
    reference = graph.derive(graph.PARTICIPANTS,np.array(weights))
    reference["metadata"] = dict(status="ok",task_id=graph.TASK_ID,pipeline_id=graph.PIPELINE_ID,
        source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,
        source_sha256={r["path"]:r["sha256"] for r in manifest["files"]},method_contract=method,
        source_observed=dict(atlas=atlas_observed,participants=observations),software_versions=dict(
            python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,nibabel=nib.__version__))
    return reference


def save_bank(path,reference):
    provenance = dict(builder_id=proof.BUILDER_ID,pipeline_id=graph.PIPELINE_ID,
        method_contract_sha256=proof.METHOD_SHA256,source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,
        source_sha256=reference["metadata"]["source_sha256"])
    encode = lambda value: np.array(json.dumps(value,allow_nan=False,sort_keys=True))
    np.savez_compressed(path,ref_participants=np.array(reference["participants"],dtype=np.int64),
        ref_weights=reference["weights"],ref_path_histogram=reference["histograms"],
        ref_metadata_json=encode(reference["metadata"]),ref_ranking_json=encode(reference["ranking"]),
        ref_graph_rows_json=encode(reference["graph_rows"]),ref_efficiency_rows_json=encode(reference["efficiency_rows"]),
        ref_provenance_json=encode(provenance))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir",type=Path,default=Path("/app/data/netinteg"))
    parser.add_argument("--method-contract",type=Path,default=Path("/app/method_contract.json"))
    parser.add_argument("--reference-path",type=Path,default=Path(__file__).with_name("reference.npz"))
    parser.add_argument("--oracle-output",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args = parser.parse_args()
    graph.require(not args.report.exists(), "Refuse to overwrite existing evidence report")
    reference = source_recompute(args.source_dir,args.method_contract)
    graph.validate_output_directory(args.oracle_output,reference)
    args.reference_path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary = tempfile.mkstemp(prefix=".independent-reference-",suffix=".npz",dir=args.reference_path.parent)
    os.close(descriptor)
    try:
        save_bank(temporary,reference)
        checked = proof.load_reference(temporary)
        graph.validate_output_directory(args.oracle_output,checked)
        os.replace(temporary,args.reference_path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(dict(status="ok",builder_id=proof.BUILDER_ID,
        reference_sha256=sha256(args.reference_path),source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,
        method_contract_sha256=proof.METHOD_SHA256,n_participants=40,n_connectome_rows=198000,n_graph_rows=320,
        source_only_recomputation="direct nearest indices, bincount parcel sums, GELSD nuisance coefficients, empirical dot products, BFS and exact rational efficiencies"),indent=2)+"\n")


if __name__ == "__main__":
    main()
