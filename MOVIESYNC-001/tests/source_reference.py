"""Grader-owned source authentication and independent MOVIESYNC reconstruction.

No historical numerical bank, solution code, mutable source-stage helper, or
participant output is imported. Nibabel decoding and SciPy primitives are shared
libraries, while map interpolation/extraction/cleaning are explicitly composed
by this route. Pending pins deliberately make original execution fail closed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import stat

import numpy as np

import artifact_reader as a
import isc_math as m
import source_numerics as s

SOURCE_SHA256 = "773af02ee4f4ca1883565f298cad351fadef302fb1f11fef6dd65cc8c55c13d6"
METHOD_SHA256 = "b2fb69c436627a0c11d3aa39a6b56a551b95a1338ea90e859647e9fadfa12d63"
SCHEMA_SHA256 = "fcd1d8743b70e11df22a5a48c66db4bf3d0d32f63dd469650e573226aae4e028"


def authenticated_json(path, expected_sha256, name):
    a.require(isinstance(expected_sha256,str) and len(expected_sha256)==64, f"{name}: pin not frozen")
    body = a.read_bytes(path, 8*2**20)
    a.require(hashlib.sha256(body).hexdigest()==expected_sha256, f"{name}: SHA256 mismatch")
    return a.parse_json(body)


def verify_file(path, row):
    path = a.guarded_path(path)
    before = path.stat()
    a.require(before.st_size == row["size_bytes"], "source size mismatch")
    sha = hashlib.sha256()
    count = 0
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as handle:
        a.require(a.identity(os.fstat(handle.fileno())) == a.identity(before), "source replaced before hash")
        while True:
            chunk = handle.read(min(2**20, row["size_bytes"]-count+1))
            if not chunk: break
            count += len(chunk)
            a.require(count <= row["size_bytes"], "source grew")
            sha.update(chunk)
        a.require(a.identity(os.fstat(handle.fileno())) == a.identity(before), "source changed during hash")
    a.require(a.identity(path.stat()) == a.identity(before), "source replaced after hash")
    a.require(count == row["size_bytes"] and sha.hexdigest() == row["sha256"], "source digest mismatch")
    return a.identity(before)


def authenticate_source(root):
    root = a.guarded_path(root, directory=True)
    manifest = authenticated_json(root/"source_manifest.json", SOURCE_SHA256, "source manifest")
    entries = manifest.get("files")
    a.require(isinstance(entries,list) and len(entries)>=83, "source file inventory")
    files = {"source_manifest.json"}; directories = set()
    for entry in entries:
        a.require(isinstance(entry,dict), "source entry")
        name = entry.get("path")
        a.require(isinstance(name,str) and name and not name.startswith("/") and
                  "\\" not in name and "\x00" not in name and
                  all(p not in ("", ".", "..") for p in name.split("/")), "unsafe source path")
        a.require(name not in files, "duplicate source path")
        files.add(name)
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p)!=".")
        a.require(type(entry.get("size_bytes")) is int and entry["size_bytes"]>0, "source size type")
        digest = entry.get("sha256")
        a.require(isinstance(digest,str) and len(digest)==64 and all(c in "0123456789abcdef" for c in digest), "source digest type")
        a.require(isinstance(entry.get("role"),str) and (entry.get("participant_id") is None or
                  isinstance(entry["participant_id"],str)), "source role/participant type")
    observed = set()
    for item in root.rglob("*"):
        name, mode = item.relative_to(root).as_posix(), item.lstat().st_mode
        if stat.S_ISDIR(mode):
            a.require(name in directories, "unexpected source directory")
        else:
            a.require(stat.S_ISREG(mode), "nonregular source inventory")
            a.require(name in files, "unexpected source file")
            observed.add(name)
    a.require(observed==files, "missing source file")
    identities={row["path"]:verify_file(root/row["path"],row) for row in entries}
    return manifest,identities


def unchanged(root, name, identities):
    path = a.guarded_path(root/name)
    a.require(a.identity(path.stat()) == identities[name], "authenticated source changed before/after parse")
    return path


def source_table(root, row, identities, delimiter):
    path=unchanged(root,row["path"],identities)
    body=a.read_bytes(path,16*2**20)
    a.require(hashlib.sha256(body).hexdigest()==row["sha256"],"source table digest mismatch")
    reader=csv.DictReader(io.StringIO(body.decode("utf-8-sig"),newline=""),delimiter=delimiter,strict=True)
    fields=reader.fieldnames
    a.require(fields and all(fields) and len(fields)==len(set(fields)),"source table columns")
    rows=[]
    for record in reader:
        a.require(len(rows)<10000 and None not in record and all(v is not None for v in record.values()),"source table malformed")
        rows.append(record)
    unchanged(root,row["path"],identities)
    return fields,rows


def image(root,row,identities):
    import nibabel as nib
    obj=nib.load(str(unchanged(root,row["path"],identities)))
    a.require(all(holder.filename is None or Path(holder.filename).resolve()==(root/row["path"]).resolve()
                  for holder in obj.file_map.values()),"external image storage")
    a.require(len(obj.shape)==4 and all(int(n)>0 for n in obj.shape),"source 4D shape")
    affine=m.real_array(obj.affine,"source affine",2)
    a.require(affine.shape==(4,4) and np.linalg.det(affine[:3,:3])!=0,"source affine invalid")
    header=obj.header
    spatial,temporal=header.get_xyzt_units()
    slope,intercept=float(obj.dataobj.slope),float(obj.dataobj.inter)
    a.require(np.isfinite([slope,intercept]).all(),"source scaling nonfinite")
    out={"shape":list(obj.shape),"affine":affine.tolist(),"source_dtype":str(obj.get_data_dtype()),
         "spatial_units":spatial,"effective_scaling_slope":slope,"effective_scaling_intercept":intercept}
    if row["role"]=="bold":
        raw_tr=float(header.get_zooms()[3]); toffset=float(header["toffset"])
        out.update(participant_id=row["participant_id"],temporal_units=temporal,
                   raw_TR=raw_tr if np.isfinite(raw_tr) else None,
                   raw_toffset=toffset if np.isfinite(toffset) else None)
    unchanged(root,row["path"],identities)
    return obj,out


def reconstruct(data_dir=None,method_path=None,schema_path=None, *, subjects=None):
    """Source-only basis. Optional explicit subset is authoring-pilot-only.

    Production validate requires all40; no acceptance or participant-output cache.
    Entire source identity is checked on every construction before decoding.
    """
    import nibabel, scipy
    root=Path(data_dir or os.environ.get("MOVIESYNC_DIR","/app/data/moviesync"))
    method_path=Path(method_path or "/app/method_contract.json")
    schema_path=Path(schema_path or "/app/output_schema.json")
    method=authenticated_json(method_path,METHOD_SHA256,"method")
    schema=authenticated_json(schema_path,SCHEMA_SHA256,"output schema")
    manifest,identities=authenticate_source(root)
    root=a.guarded_path(root,directory=True)
    a.require(method["source"]["source_manifest_sha256"]==SOURCE_SHA256,"source/method pin mismatch")
    records=manifest["files"]
    def single(role, person=None):
        found=[r for r in records if r["role"]==role and r.get("participant_id")==person]
        a.require(len(found)==1,f"source role identity: {role}/{person}")
        return found[0]
    ids=list(method["source"]["participant_ids"])
    a.require(len(ids)==40 and len(set(ids))==40,"fixed cohort")
    chosen=ids if subjects is None else list(subjects)
    a.require(chosen and len(set(chosen))==len(chosen) and set(chosen)<=set(ids),"pilot subset")
    # Canonical ordering is source declared, never inferred from serialization.
    chosen=[person for person in ids if person in chosen]
    phenotype_header,phenotype=source_table(root,single("participants"),identities,"\t")
    lookup={row["participant_id"]:i for i,row in enumerate(phenotype)}
    a.require(len(lookup)==len(phenotype) and set(ids)<=set(lookup),"phenotype identity")
    _,label_rows=source_table(root,single("atlas_labels"),identities,",")
    labels=[row["name"].strip() for row in label_rows]
    a.require(len(labels)==39 and all(labels),"39 atlas label rows")
    visual=[]
    for name in method["source"]["visual_labels"]:
        a.require(labels.count(name)==1,"unique visual label")
        visual.append(labels.index(name))
    atlas_record=single("atlas_image")
    atlas_obj,atlas_header=image(root,atlas_record,identities)
    a.require(atlas_obj.shape[-1]==39,"atlas map count")
    atlas=atlas_obj.get_fdata(dtype=np.float64)
    m.real_array(atlas,"atlas source",4)
    unchanged(root,atlas_record["path"],identities)
    cohort=[]; headers=[]; raw_all=[]; clean_all=[]; confound_headers={}; basis_cache={}
    for person in ids:
        bold_record,conf_record=single("bold",person),single("confounds",person)
        bold,header=image(root,bold_record,identities); headers.append(header)
        a.require(bold.shape[-1]==168,"BOLD frame count")
        fields,rows=source_table(root,conf_record,identities,"\t")
        confound_headers[person]=fields
        a.require(len(rows)==168,"confound row count")
        columns=method["temporal_cleaning"]["confound_columns"]
        a.require(len(columns)==15 and set(columns)<=set(fields),"confound columns")
        conf=m.real_array([[a.real(row[col]) for col in columns] for row in rows],"source confounds",2)
        if person not in chosen: continue
        key=(bold.shape[:3],np.asarray(bold.affine,dtype="<f8").tobytes())
        if key not in basis_cache:
            maps=s.resample_maps(atlas,atlas_obj.affine,tuple(int(v) for v in bold.shape[:3]),bold.affine)
            basis_cache[key]=s.map_basis(maps)
            del maps
        basis=basis_cache[key]
        unchanged(root,bold_record["path"],identities)
        data=bold.get_fdata(dtype=np.float64)
        raw=s.extract_coefficients(data,basis)
        del data
        unchanged(root,bold_record["path"],identities)
        clean,diagnostic=s.clean_coefficients(raw,conf)
        raw_all.append(raw); clean_all.append(clean[:,visual])
        cohort.append(dict(participant_id=person,participant_source_row=lookup[person],
                           bold_path=bold_record["path"],confounds_path=conf_record["path"],
                           n_frames=168,n_confound_rows=168,n_maps=39,map_rank=basis["rank"],
                           nuisance_rank=diagnostic["confound_rank"],status="ok"))
    x=np.asarray(clean_all)
    canonical=m.support(x) if len(chosen)>=2 else None
    for i,row in enumerate(cohort):
        row["n_active_visual"]=int(sum(m.stable_l2(m.centered(x[i,:,r]))>m.SUPPORT_FACTOR*np.sqrt(168) for r in range(3)))
    observed=dict(participant_ids=ids,map_labels=[dict(map_id=i,map_label=label) for i,label in enumerate(labels)],
                  visual_map_ids=visual,headers=headers,atlas_header=atlas_header,
                  confound_column_names=confound_headers,participant_column_names=phenotype_header,
                  effective_TR_s=2.,effective_origin_s=0.,frame_alignment="released_frame_index_only_no_measured_movie_onset")
    metadata=dict(schema_version="moviesync-metadata-v2",status="ok",task_id="MOVIESYNC-001",
                  method_sha256=METHOD_SHA256,output_schema_sha256=SCHEMA_SHA256,source_manifest_sha256=SOURCE_SHA256,
                  source_files=[{key:row.get(key) for key in ("path","role","participant_id","size_bytes","sha256")} for row in records],
                  source_observed=observed,
                  software_versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,nibabel=nibabel.__version__,nilearn="not_used"))
    return dict(method=method,schema=schema,cohort=cohort,participant_ids=np.asarray(chosen),
                map_ids=np.arange(39),map_labels=np.asarray(labels),frame_indices=np.arange(168),
                visual_map_ids=np.asarray(visual),raw_coefficients=np.asarray(raw_all),isc_inputs=x,
                canonical_support=canonical,metadata=metadata)
