"""Independent FCVAR source reconstruction, no oracle/stager/bank imports.

Every closed source identity is authenticated before parsing. Numeric image
payloads are streamed in original Fortran frame order, with pinned SHA checks
before AND after consumption. Canonical cleaning is independent composition of
the public low-level recipe; inference uses the shared public statistic kernel.
Private pins intentionally fail closed until the parent's structural freeze.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
import os
from pathlib import PurePosixPath
import platform
import stat
from xml.parsers import expat

import numpy as np

import artifact_reader as a
import source_numerics as n

SOURCE_SHA256 = 'a3d0f6aa1901361c55e29cf6e09a5ee31c8c084d52e4ba7e9a1f7ccddf00609f'
METHOD_SHA256 = '6268f618e7945a9be5ce08bd4adcae38b76bd65f8c510a9cbec4885a5713e080'
SCHEMA_SHA256 = '02211cbf7606a980ba2737a7418d16b446ea7f8b0e5d3cf569df5b2118d62b27'
SOURCE_FILE_COUNT = 67
IDS = "0010042 0010064 0010128 0021019 0023008 0023012 0027011 0027018 0027034 0027037 1019436 1206380 1552181 1679142 2014113 2497695 3007585 3154996 3699991 3884955 3902469 4046678 4134561 4164316 4275075 6115230 7774305 8409791 8697774 9750701".split()
ROIS = list(range(1, 49))
MAX_SOURCE_BYTES = 2 * 2**30
MAX_DECODED_BYTES = 2 * 2**30


def authenticated_json(path, expected, name):
    a.require(isinstance(expected, str) and len(expected) == 64, name + ": private pin not frozen")
    body = a.read_bytes(path, 8*2**20)
    a.require(hashlib.sha256(body).hexdigest() == expected, name + ": pinned SHA mismatch")
    return a.parse_json(body)


def verify_file(path, row):
    path = a.guarded_path(path)
    before = path.stat()
    a.require(before.st_size == row["size_bytes"], "source byte length mismatch")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    sha, count = hashlib.sha256(), 0
    with os.fdopen(fd, "rb") as stream:
        a.require(a.identity(os.fstat(stream.fileno())) == a.identity(before), "source replaced before hash")
        while True:
            block = stream.read(min(2**20, row["size_bytes"] - count + 1))
            if not block: break
            count += len(block)
            a.require(count <= row["size_bytes"], "source grew")
            sha.update(block)
        a.require(a.identity(os.fstat(stream.fileno())) == a.identity(before), "source changed during hash")
    a.require(a.identity(path.stat()) == a.identity(before), "source replaced after hash")
    a.require(count == row["size_bytes"] and sha.hexdigest() == row["sha256"], "source checksum mismatch")
    return a.identity(before)


def authenticate_source(data_dir):
    root = a.guarded_path(data_dir, directory=True)
    manifest = authenticated_json(root / "source_manifest.json", SOURCE_SHA256, "source manifest")
    a.require(manifest.get("participant_ids") == IDS, "frozen literal cohort membership/order")
    rows = manifest.get("files")
    a.require(type(SOURCE_FILE_COUNT) is int and isinstance(rows, list) and len(rows) == SOURCE_FILE_COUNT, "frozen source inventory size")
    names, directories, pairs = {"source_manifest.json"}, set(), set()
    for row in rows:
        a.require(isinstance(row, dict), "source entry object")
        name = row.get("path")
        a.require(isinstance(name, str) and name and not name.startswith("/") and "\\" not in name and "\x00" not in name
                  and all(part not in ("", ".", "..") for part in name.split("/")), "unsafe source path")
        a.require(name not in names, "duplicate source path")
        names.add(name)
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
        a.require(type(row.get("size_bytes")) is int and 0 < row["size_bytes"] <= MAX_SOURCE_BYTES, "bounded source size")
        sha = row.get("sha256")
        a.require(isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "source SHA format")
        a.require(isinstance(row.get("role"), str) and row["role"], "source role")
        if row["role"] in ("bold", "confounds"):
            a.require(row.get("participant_id") in IDS, "literal source person")
            pair = (row["role"], row["participant_id"])
            a.require(pair not in pairs, "duplicate person source role")
            pairs.add(pair)
        else:
            a.require(row.get("participant_id") is None, "nonperson source identity")
    a.require(pairs == {(role, sid) for role in ("bold", "confounds") for sid in IDS}, "all30 original person sources")
    files_seen, dirs_seen = set(), set()
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        a.require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "nonregular source inventory")
        (dirs_seen if stat.S_ISDIR(mode) else files_seen).add(path.relative_to(root).as_posix())
    a.require(files_seen == names and dirs_seen == directories, "closed source namespace")
    identities = {row["path"]: verify_file(root / row["path"], row) for row in rows}
    return root, manifest, identities


def unchanged(root, row, identities):
    path = a.guarded_path(root / row["path"])
    a.require(a.identity(path.stat()) == identities[row["path"]], "authenticated source identity changed")
    return path


def consumed(root, row, identities):
    """A second full pinned SHA is required, not only a size/stat comparison."""
    unchanged(root, row, identities)
    a.require(verify_file(root / row["path"], row) == identities[row["path"]], "source changed during consumption")


def source_text(root, row, identities):
    body = a.read_bytes(unchanged(root, row, identities), 16*2**20)
    a.require(hashlib.sha256(body).hexdigest() == row["sha256"], "source text checksum")
    unchanged(root, row, identities)
    try: return body.decode("utf-8-sig")
    except UnicodeError as exc: raise a.ArtifactError("invalid original text encoding") from exc


def source_table(root, row, identities, delimiter, *, allow_leading_unnamed=False):
    text = source_text(root, row, identities)
    a.require("\x00" not in text and delimiter in (",", "\t"), "source table text/delimiter")
    a.require(type(allow_leading_unnamed) is bool and (not allow_leading_unnamed or row["role"] == "phenotype_metadata"),
              "unnamed index allowed only for documentary phenotype")
    old_limit = csv.field_size_limit(2**20)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        columns = reader.fieldnames
        a.require(columns and len(columns) <= 256 and len(columns) == len(set(columns)), "source table columns")
        named = columns[1:] if allow_leading_unnamed and columns[0] == "" else columns
        a.require(named and all(named), "source table nonempty named columns")
        rows = []
        for row in reader:
            a.require(len(rows) < 10000 and None not in row and all(v is not None for v in row.values()), "source table shape")
            rows.append(row)
        return columns, rows
    except csv.Error as exc:
        raise a.ArtifactError("invalid source table") from exc
    finally:
        csv.field_size_limit(old_limit)


def atlas_labels(text):
    """Bounded original XML; no external entities, network, or DTD expansion."""
    parser = expat.ParserCreate()
    labels, current, chunks = {}, None, []
    def reject(*unused): raise a.ArtifactError("XML DTD/entity forbidden")
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    def start(name, attributes):
        nonlocal current, chunks
        if name == "label":
            a.require(current is None and "index" in attributes, "atlas XML label index")
            current = a.integer(attributes["index"]) + 1
            a.require(current in ROIS and current not in labels, "atlas label identity")
            chunks = []
    def char(data):
        if current is not None:
            a.require(sum(map(len, chunks)) + len(data) <= 4096, "atlas label bound")
            chunks.append(data)
    def end(name):
        nonlocal current
        if name == "label":
            a.require(current is not None, "atlas label nesting")
            label = "".join(chunks).strip()
            a.require(label, "empty atlas label")
            labels[current], current = label, None
    parser.StartElementHandler, parser.CharacterDataHandler, parser.EndElementHandler = start, char, end
    try: parser.Parse(text, True)
    except expat.ExpatError as exc: raise a.ArtifactError("invalid atlas XML") from exc
    a.require(set(labels) == set(ROIS), "complete48 atlas labels")
    return [labels[roi] for roi in ROIS]


def header_literal(value):
    value = float(value)
    return value if math.isfinite(value) else "NaN" if math.isnan(value) else "+Inf" if value > 0 else "-Inf"


def source_participant_id(token):
    """Source-original numeric identifier only; submitted IDs stay literal."""
    a.require(isinstance(token, str) and token.strip(), "source ID token")
    value = a.integer(token)
    a.require(0 <= value <= 9999999, "source ID seven-digit range")
    return f"{value:07d}"


def validate_documentary_clock(header_seconds, header_units, documented, document_units):
    """Validate documentary TR at NIfTI1 pixdim precision; never override TR."""
    factors = {"sec": 1., "msec": .001, "usec": .000001}
    a.require(header_units in factors and document_units in factors, "declared clock units")
    header_seconds = a.real(header_seconds)
    document_seconds = a.real(documented) * factors[document_units]
    a.require(.1 < header_seconds < 10 and .1 < document_seconds < 10, "clock seconds range")
    represented = float(np.float32(document_seconds / factors[header_units])) * factors[header_units]
    a.require(math.isfinite(represented) and math.isclose(header_seconds, represented, rel_tol=1e-9, abs_tol=1e-9),
              "documentary/header clock mismatch at float32 pixdim precision")
    return header_seconds


def open_decoded(path):
    return gzip.open(path, "rb") if path.name.endswith(".gz") else path.open("rb")


def image_header(root, row, identities, ndim):
    import nibabel as nib
    path = unchanged(root, row, identities)
    with open_decoded(path) as stream: body = stream.read(352)
    a.require(len(body) == 352, "NIfTI header truncated")
    header = nib.Nifti1Header(binaryblock=body[:348], check=False)
    a.require(int(header["sizeof_hdr"]) == 348 and header["magic"].tobytes() == b"n+1\0", "single-file NIfTI1")
    shape = tuple(int(v) for v in header.get_data_shape())
    a.require(len(shape) == ndim and all(v > 0 for v in shape), "NIfTI shape")
    dtype = header.get_data_dtype()
    a.require(dtype.kind in "iuf" and dtype.fields is None and dtype.itemsize <= 8, "NIfTI real scalar storage")
    offset = float(header["vox_offset"])
    a.require(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= 16*2**20, "NIfTI bounded extension offset")
    a.require(int(offset) + math.prod(shape)*dtype.itemsize <= MAX_DECODED_BYTES, "NIfTI decoded byte cap")
    affine = n.real_array(header.get_best_affine(), 2, "NIfTI affine")
    a.require(affine.shape == (4, 4) and np.linalg.det(affine[:3, :3]) != 0, "NIfTI nonsingular affine")
    slope, intercept = header.get_slope_inter()
    slope, intercept = 1. if slope is None else float(slope), 0. if intercept is None else float(intercept)
    a.require(np.isfinite([slope, intercept]).all(), "finite NIfTI scaling")
    spatial, temporal = header.get_xyzt_units()
    a.require(spatial == "mm", "declared millimetre source geometry required")
    facts = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
                 spatial_units=spatial, temporal_units=temporal, zooms=[header_literal(v) for v in header.get_zooms()],
                 raw_toffset=header_literal(header["toffset"]), raw_scl_slope=header_literal(header["scl_slope"]),
                 raw_scl_inter=header_literal(header["scl_inter"]), effective_slope=slope, effective_intercept=intercept)
    unchanged(root, row, identities)
    return dict(shape=shape, dtype=dtype, offset=int(offset), affine=affine,
                slope=slope, intercept=intercept, facts=facts)


def image_volumes(root, row, identities, info):
    """Stream calibrated float64 Fortran volumes; finish with cryptographic check."""
    path = unchanged(root, row, identities)
    count = math.prod(info["shape"][:3])
    n_frames = info["shape"][3] if len(info["shape"]) == 4 else 1
    frame_bytes = count * info["dtype"].itemsize
    with open_decoded(path) as stream:
        prefix = stream.read(info["offset"])
        a.require(len(prefix) == info["offset"], "NIfTI header/extensions truncated")
        for _ in range(n_frames):
            body = stream.read(frame_bytes)
            a.require(len(body) == frame_bytes, "NIfTI volume truncated")
            values = np.frombuffer(body, dtype=info["dtype"]).reshape(info["shape"][:3], order="F").astype(np.float64)
            values *= info["slope"]
            values += info["intercept"]
            # BOLD finite support is the geometric union of all48 ROIs, not
            # ignored background. Atlas finiteness is checked by resampling.
            yield values
        a.require(stream.read(1) == b"", "unexpected NIfTI trailing decoded bytes")
    consumed(root, row, identities)


def reconstruct(data_dir=None, method_path=None, schema_path=None, *, subjects=None):
    """Authenticate all originals, then reconstruct full30 or explicit gated pilot."""
    import nibabel, scipy
    method = authenticated_json(method_path or "/app/method_contract.json", METHOD_SHA256, "method")
    schema = authenticated_json(schema_path or "/app/output_schema.json", SCHEMA_SHA256, "schema")
    root, manifest, identities = authenticate_source(data_dir or os.environ.get("DATA_DIR", "/app/data/fcvar"))
    source = method["source"]
    a.require(source["participant_ids"] == IDS and source["source_manifest_sha256"] == SOURCE_SHA256, "method cohort/source binding")
    a.require(method["temporal_cleaning"]["confound_columns"] == list(n.CONFOUNDS), "exact public nuisance order")
    selected = IDS if subjects is None else list(subjects)
    a.require(selected and len(selected) == len(set(selected)) and set(selected).issubset(IDS), "explicit pilot subject subset")
    rows = manifest["files"]
    def single(role, sid=None):
        matches = [r for r in rows if r["role"] == role and r.get("participant_id") == sid]
        a.require(len(matches) == 1, "unique required source role")
        return matches[0]
    # Exact phenotype column names are declared by source metadata before values.
    phenotype_info, timing_info = source["phenotype_join"], source["site_timing_join"]
    a.require(phenotype_info["allow_leading_unnamed_index"] is True, "frozen phenotype index policy")
    columns, phenotype_rows = source_table(root, single("phenotype_metadata"), identities, phenotype_info["delimiter"], allow_leading_unnamed=True)
    timing_columns, timing_rows = source_table(root, single("slice_timing_metadata"), identities, timing_info["delimiter"])
    id_name, site_name = phenotype_info["id_column"], phenotype_info["site_column"]
    a.require(id_name in columns and site_name in columns, "source phenotype columns")
    phenotype = {}
    for row in phenotype_rows:
        sid = source_participant_id(row[id_name])
        a.require(sid not in phenotype, "duplicate literal phenotype subject")
        phenotype[sid] = row
    a.require(set(IDS).issubset(phenotype), "all30 literal phenotype joins")
    original_ids = source_text(root, single("cohort_ids"), identities).split()
    a.require(len(original_ids) == len(set(original_ids)) and set(IDS).issubset(original_ids), "original cohort-ID membership")
    a.require(timing_info["site_column"] in timing_columns and timing_info["tr_column"] in timing_columns, "source timing columns")
    timing = {}
    for record in timing_rows:
        site = record[timing_info["site_column"]]
        a.require(site and site not in timing, "unique nonempty source timing site")
        timing[site] = record[timing_info["tr_column"]]
    labels = atlas_labels(source_text(root, single("atlas_labels"), identities))
    atlas_info = image_header(root, single("atlas_image"), identities, 3)
    atlas_volumes = list(image_volumes(root, single("atlas_image"), identities, atlas_info))
    a.require(len(atlas_volumes) == 1, "atlas volume count")
    atlas = atlas_volumes[0]
    headers, confounds, column_map, supports, clocks = {}, {}, {}, {}, {}
    info_map = {}
    for sid in IDS:
        info = image_header(root, single("bold", sid), identities, 4)
        info_map[sid], headers[sid] = info, info["facts"]
        t = info["shape"][-1]
        a.require(t == a.integer(source["n_frames_by_participant"][sid], json_number=True), "source frame count")
        temporal = info["facts"]["temporal_units"]
        a.require(temporal in ("sec", "msec", "usec"), "unrecognized source temporal units")
        tr = float(info["facts"]["zooms"][3]) * {"sec": 1., "msec": .001, "usec": .000001}[temporal]
        a.require(.1 < tr < 10 and .08 < .5/tr and tr == a.real(source["tr_sec_by_participant"][sid], json_number=True), "source TR conversion")
        site = phenotype[sid][site_name]
        a.require(site in timing, "source phenotype/timing site join")
        validate_documentary_clock(tr, temporal, timing[site], timing_info["tr_units"])
        clocks[sid] = dict(tr_sec=tr, frame_origin_s=0., frame_alignment="released_frame_index_only")
        cols, records = source_table(root, single("confounds", sid), identities, "\t")
        a.require(set(n.CONFOUNDS).issubset(cols) and len(records) == t, "complete nuisance columns/frames")
        confounds[sid] = n.real_array([[a.real(row[col]) for col in n.CONFOUNDS] for row in records], 2, "selected source confounds")
        column_map[sid] = cols
        grid = n.resample_labels(atlas, atlas_info["affine"], info["shape"][:3], info["affine"])
        supports[sid] = n.support_records(grid, ROIS, info["affine"])
    persons, cohort, analysis = {}, [], []
    for order, sid in enumerate(IDS):
        if sid not in selected: continue
        info, support = info_map[sid], supports[sid]
        raw = np.zeros((info["shape"][-1], 48), dtype=np.float64)
        for t, volume in enumerate(image_volumes(root, single("bold", sid), identities, info)):
            raw[t] = n.parcel_means(volume[..., None], support)[0]
        cleaned = n.clean_roi_signals(raw, confounds[sid], clocks[sid]["tr_sec"], support["geometry_present"])
        p = dict(raw=raw, n_frames=len(raw), tr_sec=clocks[sid]["tr_sec"], site=phenotype[sid][site_name],
                 source_paths={role: single(role, sid)["path"] for role in ("bold", "confounds")},
                 **{k: support[k] for k in ("geometry_present", "n_voxels", "support_sha256")}, **cleaned)
        persons[sid] = p
        active_count = int(p["active"].sum())
        cohort.append(dict(subject=sid, source_order=order, site=p["site"], n_timepoints=len(raw), tr_sec=p["tr_sec"],
                           bold_path=p["source_paths"]["bold"], confounds_path=p["source_paths"]["confounds"],
                           n_global_active_rois=active_count, n_edges=active_count*(active_count-1)//2, status="ok"))
        analysis.append(dict(subject=sid, cleaning_rank=p["cleaning_rank"], n_global_active_rois=active_count, n_edges=active_count*(active_count-1)//2))
    observed = dict(atlas_header=atlas_info["facts"], roi_labels=[dict(roi_id=i, roi_label=label) for i, label in zip(ROIS, labels)],
                    phenotype_columns=columns, slice_timing_columns=timing_columns,
                    persons={sid: dict(bold_header=headers[sid], confound_columns=column_map[sid], selected_confound_columns=list(n.CONFOUNDS),
                              excluded_confound_columns=[c for c in column_map[sid] if c not in n.CONFOUNDS],
                              n_confound_rows=info_map[sid]["shape"][-1], frame_count=info_map[sid]["shape"][-1],
                              site=phenotype[sid][site_name], source_participant_token=phenotype[sid][id_name],
                              operational_TR_s=clocks[sid]["tr_sec"], frame_origin_s=0.) for sid in IDS})
    files = [{k: row.get(k) for k in ("path", "role", "participant_id", "size_bytes", "sha256")} for row in rows]
    pins = dict(source_manifest_sha256=SOURCE_SHA256, method_contract_sha256=METHOD_SHA256, output_schema_sha256=SCHEMA_SHA256)
    metadata = dict(schema_version="fcvar-metadata-v3", task_id="FCVAR-001", status="ok" if subjects is None else "resource_pilot", **pins,
                    source_files=files, source_observed=observed, analysis_observed={"persons": {row["subject"]: {k:v for k,v in row.items() if k != "subject"} for row in analysis}},
                    software_versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, nibabel=nibabel.__version__, nilearn="not_used"), warnings=[])
    return dict(status="complete" if subjects is None else "resource_pilot", pins=pins, method=method, schema=schema,
                participant_ids=selected, roi_ids=ROIS, roi_labels=labels, persons=persons,
                source_files=files, source_observed=observed, cohort=cohort, metadata=metadata)
