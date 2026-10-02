"""Grader-owned source authentication and independent GRADIENT reconstruction.

No historical numerical bank, solution code, mutable source-stage helper, or
participant output is imported. Nibabel decoding and SciPy primitives are shared
libraries, while label interpolation/extraction/cleaning are explicitly composed
by this route. Pending pins deliberately make original execution fail closed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat

import numpy as np

import artifact_reader as a
import gradient_math as m
import source_numerics as s

SOURCE_SHA256 = "6afac2a68c4ca4847265ac5f890d56aa53a658e78f13b32e0f15f74007ed91c7"
METHOD_SHA256 = "c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872"
SCHEMA_SHA256 = "e9ceb1a15180ed086290c4c7f5eb079038302b4dd5feabc3e99c9acb688bcf16"
SOURCE_FILE_COUNT = 46


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
    a.require(isinstance(entries,list) and len(entries)==SOURCE_FILE_COUNT, "source file inventory")
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


def image(root, row, identities):
    import nibabel as nib
    obj = nib.load(str(unchanged(root, row["path"], identities)))
    a.require(isinstance(obj, nib.Nifti1Image), "single-file NIfTI1 required")
    a.require(all(holder.filename is None or Path(holder.filename).resolve() == (root / row["path"]).resolve()
                  for holder in obj.file_map.values()), "external image storage")
    dims = 4 if row["role"] == "bold" else 3
    a.require(len(obj.shape) == dims and all(int(n) > 0 for n in obj.shape), "source image dimensions")
    a.require(np.prod(obj.shape, dtype=np.int64) <= 100_000_000, "source image voxel cap")
    affine = m.real(obj.affine, "source affine", 2)
    a.require(affine.shape == (4, 4) and np.linalg.det(affine[:3, :3]) != 0, "source affine invalid")
    spatial, temporal = obj.header.get_xyzt_units()
    slope, intercept = float(obj.dataobj.slope), float(obj.dataobj.inter)
    a.require(np.isfinite([slope, intercept]).all(), "nonfinite source calibration")
    metadata = dict(shape=list(obj.shape), affine=affine.tolist(), source_dtype=obj.get_data_dtype().str,
                    spatial_units=spatial, effective_scaling_slope=slope, effective_scaling_intercept=intercept)
    if dims == 4:
        tr, offset = float(obj.header.get_zooms()[3]), float(obj.header["toffset"])
        metadata.update(temporal_units=temporal, raw_TR=tr if np.isfinite(tr) else None,
                        raw_toffset=offset if np.isfinite(offset) else None)
    unchanged(root, row["path"], identities)
    return obj, metadata


def label_table(root, row, identities, networks):
    path = unchanged(root, row["path"], identities)
    body = a.read_bytes(path, 2**20)
    a.require(hashlib.sha256(body).hexdigest() == row["sha256"], "LUT source SHA mismatch")
    records = []
    for line in body.decode("utf-8-sig").splitlines():
        if not line.strip(): continue
        fields = line.split()
        a.require(len(fields) == 6, "LUT six fields")
        parcel = a.integer(fields[0])
        match = re.fullmatch(r"7Networks_(LH|RH)_([A-Za-z]+)_.+", fields[1])
        a.require(match is not None and match[2] in networks, "source LUT network")
        records.append(dict(parcel_id=parcel, label=fields[1], network=match[2]))
    a.require(len(records) == 400 and {x["parcel_id"] for x in records} == set(range(1, 401)), "LUT fixed400 IDs")
    unchanged(root, row["path"], identities)
    return sorted(records, key=lambda x: x["parcel_id"])


def reconstruct(data_dir=None, method_path=None, schema_path=None, *, subjects=None, spectral=True):
    """Authenticate all sources before decode; optional subset is pilot-only.

    No submitted arrays, stored numerical bank or source-stage Python code is
    consumed. Every call reauthenticates. Production proof separately requires
    all20/source order and spectral=True. A diagnostic pilot may request just
    one explicit source person with spectral=False, never a full-task pass.
    """
    import nibabel, scipy
    root = Path(data_dir or os.environ.get("GRADIENT_DIR", "/app/data/gradient"))
    method = authenticated_json(method_path or "/app/method_contract.json", METHOD_SHA256, "method")
    schema = authenticated_json(schema_path or "/app/output_schema.json", SCHEMA_SHA256, "output schema")
    manifest, identities = authenticate_source(root)
    root = a.guarded_path(root, directory=True)
    a.require(method["source"]["manifest_sha256"] == SOURCE_SHA256, "source/method identity")
    records = manifest["files"]
    source_ids = method["source"]["participant_ids"]
    a.require(isinstance(source_ids, list) and len(source_ids) == 20 and
              len(set(source_ids)) == 20 and all(isinstance(x, str) and x for x in source_ids), "frozen20 cohort")
    chosen = source_ids if subjects is None else list(subjects)
    a.require(chosen and len(chosen) == len(set(chosen)) and set(chosen) <= set(source_ids), "pilot subset")
    chosen = [x for x in source_ids if x in chosen]
    a.require(not spectral or chosen == source_ids, "partial source basis cannot construct group spectra")
    def single(role, person=None):
        found = [r for r in records if r["role"] == role and r.get("participant_id") == person]
        a.require(len(found) == 1, f"source role identity: {role}/{person}")
        return found[0]
    scientific = [(r["role"], r.get("participant_id")) for r in records if r["role"] != "provenance"]
    expected = {(role, person) for role in ("bold", "confounds") for person in source_ids} | {
        (role, None) for role in ("participants", "atlas_image", "atlas_labels")}
    a.require(len(scientific) == 43 and set(scientific) == expected, "exact scientific role cohort")
    fields, phenotype = source_table(root, single("participants"), identities, "\t")
    a.require(set(("participant_id", "Age", "Child_Adult")) <= set(fields), "phenotype columns")
    lookup = {row["participant_id"]: i for i, row in enumerate(phenotype)}
    a.require(len(lookup) == len(phenotype) and set(source_ids) <= set(lookup), "phenotype literal identities")
    labels = label_table(root, single("atlas_labels"), identities, method["source"]["networks"])
    parcel_ids = np.arange(1, 401, dtype=np.int64)
    atlas_record = single("atlas_image")
    atlas_obj, atlas_header = image(root, atlas_record, identities)
    atlas = m.real(atlas_obj.get_fdata(dtype=np.float64), "source atlas", 3)
    unchanged(root, atlas_record["path"], identities)
    cohorts, parcels, headers, confound_headers, voxel_support, cache = [], [], {}, {}, {}, {}
    raw_all, diagnostics = [], []
    for position, person in enumerate(source_ids):
        bold_record, conf_record = single("bold", person), single("confounds", person)
        bold, header = image(root, bold_record, identities)
        a.require(tuple(bold.shape) == (50, 59, 50, 168), "frozen released BOLD shape")
        headers[person] = header
        names, rows = source_table(root, conf_record, identities, "\t")
        confound_headers[person] = names
        columns = method["cleaning"]["confounds"]
        a.require(len(rows) == 168 and len(columns) == 15 and set(columns) <= set(names), "confound frame/column support")
        confounds = m.real([[a.real(row[col]) for col in columns] for row in rows], "selected source confounds", 2)
        key = (tuple(bold.shape[:3]), np.asarray(bold.affine, dtype="<f8").tobytes())
        if key not in cache:
            grid = s.resample_labels(atlas, atlas_obj.affine, tuple(int(v) for v in bold.shape[:3]), bold.affine)
            cache[key] = s.parcel_support(grid, parcel_ids)
        support = cache[key]
        voxel_support[person] = [dict(parcel_id=int(parcel), n_voxels=int(size), support_sha256=sha)
                                 for parcel, size, sha in zip(parcel_ids, support["counts"], support["sha256"])]
        for label, receipt in zip(labels, voxel_support[person]):
            parcels.append(dict(participant_id=person, **label, n_voxels=receipt["n_voxels"],
                                support_sha256=receipt["support_sha256"],
                                geometry_status="ok" if receipt["n_voxels"] else "empty_geometry"))
        pheno = phenotype[lookup[person]]
        cohorts.append(dict(participant_id=person, source_position=position, phenotype_row_index=lookup[person],
                            age=a.real(pheno["Age"]), child_adult=pheno["Child_Adult"],
                            bold_path=bold_record["path"], confounds_path=conf_record["path"], n_frames=168,
                            first_half=position < 10, second_half=position >= 10))
        if person not in chosen: continue
        unchanged(root, bold_record["path"], identities)
        data = m.real(bold.get_fdata(dtype=np.float64), "calibrated BOLD", 4)
        raw = np.stack([s.volume_means(data[..., frame], support) for frame in range(168)])
        del data
        unchanged(root, bold_record["path"], identities)
        raw_all.append(raw)
        diagnostics.append(dict(geometry_valid=support["geometry_valid"], **s.reconstruct_person(raw, confounds, support["geometry_valid"])))
    arrays = dict(participant_ids=np.asarray(chosen), source_positions=np.asarray([source_ids.index(x) for x in chosen]),
                  frame_indices=np.arange(168), parcel_ids=parcel_ids, arm_ids=np.asarray(["nobp", "bp"]),
                  raw_means=np.stack(raw_all))
    for key in ("geometry_valid", "cleaned_series", "raw_sample_sd", "clean_centered_l2", "activity_threshold", "person_parcel_active", "fc"):
        arrays[key] = np.stack([x[key] for x in diagnostics])
    bases = None
    if spectral:
        configs = method["configurations"]
        membership = np.zeros((4, 20), bool)
        group_fc, group_active = [], []
        for index, config in enumerate(configs):
            membership[index, config["positions"]] = True
            arm = int(config["bandpass"])
            fc, valid = s.group_connectivity(arrays["fc"][:, arm], arrays["person_parcel_active"][:, arm], membership[index])
            group_fc.append(fc); group_active.append(valid)
        arrays.update(configuration_ids=np.asarray([x["id"] for x in configs]), configuration_membership=membership,
                      configuration_fc=np.stack(group_fc), configuration_parcel_active=np.stack(group_active))
        matrices = list(arrays["fc"][:, 0]) + group_fc
        bases = [m.canonical_basis(fc, parcel_ids) if np.isfinite(fc).all() else None for fc in matrices]
        arrays["embedding_ids"] = np.asarray(["subject:" + x for x in source_ids] + ["configuration:" + x["id"] for x in configs])
    observed = dict(participant_ids=source_ids, source_order=source_ids, participant_column_names=fields,
                    confound_column_names=confound_headers, headers=headers, atlas_header=atlas_header,
                    atlas_labels=labels, voxel_support_by_subject=voxel_support,
                    frame_alignment="released_frame_index_only_no_measured_movie_onset",
                    raw_clock_metadata={person: {key: headers[person][key] for key in ("raw_TR", "raw_toffset", "temporal_units")} for person in source_ids},
                    effective_TR_s=2., effective_origin_s=0.)
    metadata = dict(schema_version="gradient-metadata-v2", status="ok", task_id="GRADIENT-001",
                    source_manifest_sha256=SOURCE_SHA256, method_sha256=METHOD_SHA256, output_schema_sha256=SCHEMA_SHA256,
                    source_files=[{key: row.get(key) for key in ("path", "role", "participant_id", "size_bytes", "sha256")} for row in records],
                    source_observed=observed,
                    software_versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                                           nibabel=nibabel.__version__, nilearn="not_used", brainspace="not_used"))
    return dict(method=method, schema=schema, metadata=metadata, cohort=cohorts, parcels=parcels, arrays=arrays,
                source_bases=bases, nuisance_ranks={person: x["nuisance_rank"] for person, x in zip(chosen, diagnostics)},
                networks=np.asarray([row["network"] for row in labels]), pilot=chosen != source_ids)
