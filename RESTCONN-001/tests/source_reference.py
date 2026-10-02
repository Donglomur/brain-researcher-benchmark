"""Prospective independent RESTCONN source reconstruction; no import-time I/O.

Private source/method/schema pins bind the parent's pre-values freeze.
All ten original identities precede parsing. No solution, stage helper, output,
historical bank, or oracle numerical module is imported.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
import os
from pathlib import Path, PurePosixPath
import platform
import stat

import numpy as np

import artifact_reader as a
import circular_contract as c
import source_numerics as s

SOURCE_SHA256 = "465cfd8f113be362b39172782713c504432c51e529d82f222bda8ba9f1fb734e"
METHOD_SHA256 = "a9d473e0192d723d023e16540040a6fde7dc9b3a0d878d5cef840e2c5f8cc40e"
SCHEMA_SHA256 = "aa447d96db059f2bc824f5978dc48237c76474c5be8efa401b0ae05969093657"
ROLES = {"bold", "confounds", "cohort_ids", "phenotype_metadata", "slice_timing_metadata", "atlas_image", "atlas_labels"}
NUISANCE = {"motion-pitch", "motion-roll", "motion-yaw", "motion-x", "motion-y", "motion-z",
            "compcor1", "compcor2", "compcor3", "compcor4", "compcor5", "csf", "wm"}


def authenticated_json(path, expected, name):
    a.require(isinstance(expected, str) and len(expected) == 64, name + ": pin not frozen")
    body = a.read_bytes(path, 8 * 2**20)
    a.require(hashlib.sha256(body).hexdigest() == expected, name + ": SHA256 mismatch")
    return a.parse_json(body)


def verify_file(path, row):
    path = a.guarded_path(path)
    before = path.stat()
    a.require(before.st_size == row["size_bytes"], "source size mismatch")
    digest, count = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        a.require(a.identity(os.fstat(handle.fileno())) == a.identity(before), "source replaced before hash")
        while True:
            block = handle.read(min(2**20, row["size_bytes"] - count + 1))
            if not block: break
            count += len(block)
            a.require(count <= row["size_bytes"], "source grew")
            digest.update(block)
        a.require(a.identity(os.fstat(handle.fileno())) == a.identity(before), "source changed during hash")
    a.require(a.identity(path.stat()) == a.identity(before), "source replaced after hash")
    a.require(count == row["size_bytes"] and digest.hexdigest() == row["sha256"], "source digest mismatch")
    return a.identity(before)


def authenticate_source(root):
    root = a.guarded_path(root, directory=True)
    manifest = authenticated_json(root / "source_manifest.json", SOURCE_SHA256, "source manifest")
    records = manifest.get("files")
    a.require(isinstance(records, list) and len(records) == 10, "exact ten source entries")
    a.require(manifest.get("participant_ids") == [c.SUBJECT], "literal source participant")
    files, directories, roles = {"source_manifest.json"}, set(), []
    for row in records:
        a.require(isinstance(row, dict), "source row")
        name = row.get("path")
        a.require(isinstance(name, str) and name and not name.startswith("/") and "\\" not in name and "\x00" not in name
                  and all(p not in ("", ".", "..") for p in name.split("/")), "unsafe source path")
        a.require(name not in files, "duplicate source path")
        files.add(name)
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
        a.require(type(row.get("size_bytes")) is int and 0 < row["size_bytes"] <= 256 * 2**20, "source size type/range")
        digest = row.get("sha256")
        a.require(isinstance(digest, str) and len(digest) == 64 and all(x in "0123456789abcdef" for x in digest), "source digest")
        role = row.get("role"); roles.append(role)
        a.require(role in ROLES | {"provenance"}, "source role")
        a.require(row.get("participant_id") == (c.SUBJECT if role in ("bold", "confounds") else None), "source participant identity")
    a.require(all(roles.count(role) == 1 for role in ROLES) and roles.count("provenance") == 3, "source role completeness")
    observed_files, observed_dirs = set(), set()
    for item in root.rglob("*"):
        mode = item.lstat().st_mode
        name = item.relative_to(root).as_posix()
        a.require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "nonregular source inventory")
        (observed_dirs if stat.S_ISDIR(mode) else observed_files).add(name)
    a.require(observed_files == files and observed_dirs == directories, "closed source inventory")
    identities = {row["path"]: verify_file(root / row["path"], row) for row in records}
    return manifest, identities


def unchanged(root, row, identities):
    path = a.guarded_path(root / row["path"])
    a.require(a.identity(path.stat()) == identities[row["path"]], "authenticated source changed before/after parse")
    return path


def source_text(root, row, identities):
    payload = a.read_bytes(unchanged(root, row, identities), 16 * 2**20)
    a.require(hashlib.sha256(payload).hexdigest() == row["sha256"], "source text digest mismatch")
    unchanged(root, row, identities)
    return payload.decode("utf-8-sig")


def source_table(root, row, identities, delimiter):
    text = source_text(root, row, identities)
    a.require("\x00" not in text, "source NUL")
    a.require(delimiter in (",", "\t"), "source table declared delimiter")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    columns = reader.fieldnames
    a.require(columns and len(columns) <= 256 and all(columns) and len(set(columns)) == len(columns), "source table columns")
    rows = []
    for record in reader:
        a.require(len(rows) < 10000 and None not in record and all(v is not None for v in record.values()), "source table shape")
        rows.append(record)
    return columns, rows


def literal(value):
    value = float(value)
    return value if math.isfinite(value) else "NaN" if math.isnan(value) else "+Inf" if value > 0 else "-Inf"


def image(root, row, identities):
    import nibabel as nib
    path = unchanged(root, row, identities)
    # Preserve on-disk scaling before nibabel's loaded header consumes it.
    with path.open("rb") as source:
        if path.name.endswith(".gz"):
            with gzip.GzipFile(fileobj=source) as stream: raw = stream.read(352)
        else: raw = source.read(352)
    a.require(len(raw) == 352, "NIfTI header length")
    header = nib.Nifti1Header(binaryblock=raw[:348], check=False)
    a.require(int(header["sizeof_hdr"]) == 348 and header["magic"].tobytes() == b"n+1\0", "single-file NIfTI1 required")
    shape = tuple(int(n) for n in header.get_data_shape())
    a.require(len(shape) == 4 and all(n > 0 for n in shape) and math.prod(shape) <= 200_000_000, "image shape/resource cap")
    offset = float(header["vox_offset"])
    dtype = header.get_data_dtype()
    a.require(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= 16 * 2**20,
              "bounded NIfTI extension/payload offset")
    a.require(dtype.kind in "iuf" and dtype.fields is None, "real scalar NIfTI storage")
    a.require(int(offset) + math.prod(shape) * dtype.itemsize <= 2 * 2**30, "decoded image byte cap")
    affine = c.real_array(header.get_best_affine(), 2)
    a.require(affine.shape == (4, 4) and np.linalg.det(affine[:3, :3]) != 0, "image affine")
    spatial, temporal = header.get_xyzt_units()
    slope, intercept = header.get_slope_inter()
    slope, intercept = 1. if slope is None else float(slope), 0. if intercept is None else float(intercept)
    a.require(np.isfinite([slope, intercept]).all(), "nonfinite image scaling")
    facts = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=header.get_data_dtype().str,
                 spatial_units=spatial, temporal_units=temporal, zooms=[literal(v) for v in header.get_zooms()],
                 raw_toffset=literal(header["toffset"]), raw_scl_slope=literal(header["scl_slope"]),
                 raw_scl_inter=literal(header["scl_inter"]), effective_slope=slope, effective_intercept=intercept)
    obj = nib.load(str(path))
    a.require(all(h.filename is None or Path(h.filename).resolve() == path for h in obj.file_map.values()), "external image storage")
    a.require(obj.shape == shape and np.array_equal(obj.affine, affine), "image header disagreement")
    a.require(int(obj.dataobj.offset) == int(offset), "image payload offset disagreement")
    a.require(float(obj.dataobj.slope) == slope and float(obj.dataobj.inter) == intercept, "image scaling disagreement")
    unchanged(root, row, identities)
    return obj, facts


def reconstruct(data_dir=None, method_path=None, schema_path=None):
    """One source-bound basis; no output cache and no original default N guess."""
    import nibabel, scipy
    root = a.guarded_path(data_dir or os.environ.get("RESTCONN_DIR", "/app/data/restconn"), directory=True)
    method = authenticated_json(method_path or "/app/method_contract.json", METHOD_SHA256, "method")
    schema = authenticated_json(schema_path or "/app/output_schema.json", SCHEMA_SHA256, "schema")
    manifest, identities = authenticate_source(root)
    source = method["source"]
    a.require(source["source_manifest_sha256"] == SOURCE_SHA256 and source["participant_id"] == c.SUBJECT, "method/source identity")
    n = a.integer(source["n_frames"], json_number=True)
    a.require(33 < n <= 10000, "declared source frame count")
    a.require(source["map_ids"] == list(range(39)) and all(type(v) is int for v in source["map_ids"]), "fixed39 map IDs")
    a.require(source["target_labels"] == list(c.TARGETS), "fixed target labels")
    a.require(a.real(source["operational_TR_s"], json_number=True) == 2.
              and a.real(source["operational_origin_s"], json_number=True) == 0., "operational frame clock")
    targets = [a.integer(v, json_number=True) for v in source["target_map_ids"]]
    a.require(len(targets) == len(set(targets)) == 2 and all(0 <= v < 39 for v in targets), "target map IDs")
    records = manifest["files"]
    single = lambda role: next(row for row in records if row["role"] == role)
    ids = source_text(root, single("cohort_ids"), identities).split()
    a.require(len(ids) == len(set(ids)) and ids.count(c.SUBJECT) == 1, "cohort literal identity")
    _, label_rows = source_table(root, single("atlas_labels"), identities, ",")
    a.require(len(label_rows) == 39 and all("name" in row for row in label_rows), "atlas labels39")
    labels = [row["name"].strip() for row in label_rows]
    a.require(all(labels) and len(set(labels)) == 39 and [labels[k] for k in targets] == list(c.TARGETS), "atlas target identity")
    columns, confound_rows = source_table(root, single("confounds"), identities, "\t")
    a.require(columns == source["original_confound_columns"], "original confound header")
    selected = method["temporal_cleaning"]["confound_columns"]
    a.require(isinstance(selected, list) and len(selected) == 13 and set(selected) == NUISANCE,
              "exact thirteen nuisance names")
    a.require([col for col in columns if col in NUISANCE] == selected and len(confound_rows) == n, "nuisance source order/frames")
    confounds = c.real_array([[a.real(row[col]) for col in selected] for row in confound_rows], 2)
    bold, bold_header = image(root, single("bold"), identities)
    atlas, atlas_header = image(root, single("atlas_image"), identities)
    a.require(bold.shape[-1] == n and atlas.shape[-1] == 39, "original image dimensions")
    a.require(list(bold.shape) == source["bold_shape"] and list(atlas.shape) == source["atlas_shape"], "declared image shape")
    maps = c.real_array(atlas.get_fdata(dtype=np.float64), 4)
    unchanged(root, single("atlas_image"), identities)
    maps = s.resample_maps(maps, atlas.affine, tuple(int(v) for v in bold.shape[:3]), bold.affine)
    spatial = s.map_basis(maps)
    del maps
    raw = s.extract_coefficients(bold.get_fdata(dtype=np.float64), spatial)
    unchanged(root, single("bold"), identities)
    clean, diagnostics = s.clean_coefficients(raw, confounds)
    support = [dict(map_id=k, map_label=labels[k], raw_sample_sd=float(diagnostics["raw_sample_sd"][k]),
                    residual_centered_l2=float(diagnostics["residual_centered_l2"][k]),
                    activity_threshold=float(diagnostics["activity_threshold"][k]), active=bool(diagnostics["active"][k])) for k in targets]
    metadata = dict(schema_version="restconn-metadata-v2", status="ok", task_id="RESTCONN-001",
                    method_sha256=METHOD_SHA256, output_schema_sha256=SCHEMA_SHA256, source_manifest_sha256=SOURCE_SHA256,
                    source_files=[{key: row.get(key) for key in ("path", "role", "participant_id", "size_bytes", "sha256")} for row in records],
                    source_observed=dict(bold_header=bold_header, atlas_header=atlas_header, frame_count=n,
                        confound_columns=columns, selected_confound_columns=selected,
                        excluded_confound_columns=[col for col in columns if col not in NUISANCE], n_confound_rows=n,
                        map_labels=[dict(map_id=i, map_label=label) for i, label in enumerate(labels)], target_map_ids=targets,
                        operational_TR_s=2., frame_origin_s=0.),
                    analysis_observed=dict(map_rank=spatial["rank"], confound_rank=diagnostics["confound_rank"], target_support=support),
                    software_versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, nibabel=nibabel.__version__, nilearn="not_used"),
                    warnings=[])
    return dict(method=method, schema=schema, participant_id=c.SUBJECT, frame_indices=np.arange(n),
                map_ids=np.arange(39), map_labels=np.asarray(labels), target_labels=c.TARGETS, target_map_ids=np.asarray(targets),
                raw_coefficients=raw, cleaned_series=clean[:, targets], active=diagnostics["active"][targets],
                metadata=metadata, diagnostics=diagnostics)
