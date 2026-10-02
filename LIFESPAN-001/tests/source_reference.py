"""Grader-owned original-source reconstruction; no numerical bank or stager.

All public identities below are private constants, never environment overrides.
Only paths are configurable. Every original is authenticated before decoding,
then each decoder consumes a freshly authenticated SAME byte buffer. No agent
module, on-disk feature cache or oracle result supplies expectations.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import stat
import struct
from xml.parsers import expat

import nibabel as nib
import numpy as np

import io_contract as io_c
import lifespan_statistics as science

METHOD_SHA256 = "47c9450cfee4db7140aee2a269510644dde6a3388dfeea9deee2f1f5ae466471"
OUTPUT_CONTRACT_SHA256 = "0399accee9d461daee3481f930318f7db6d4f248443ae41d20ca60a64471cebf"
SOURCE_SHA256 = "18fd1271190687765461243943ced2b82d5d5fb703c3d675a2f7586992b5f932"
COHORT_SHA256 = "9c24cf46cdc138a52fc5a10e064ce7ea052a4834339a71f7e5e3595f81898009"
NOTICE_SHA256 = "0f2546e2dd84fa806c06cf7a1b457748c1690f36cd1e40add2e9427abede1320"
N_FILES, TOTAL_BYTES = 121, 4_997_109_352
MAX_SOURCE_FILE = 50_000_000
need = io_c.need


def source_bytes(root, row):
    return io_c.read_bytes(root / row["path"], MAX_SOURCE_FILE,
                           size=row["size_bytes"], sha256=row["sha256"])


def authenticate(data_dir, method_path, cohort_path):
    root = io_c.safe_path(data_dir)
    method = io_c.pinned_json(method_path, METHOD_SHA256)
    cohort = io_c.pinned_json(cohort_path, COHORT_SHA256)
    manifest = io_c.pinned_json(root / "source_manifest.json", SOURCE_SHA256)
    need(method["source_manifest_sha256"] == SOURCE_SHA256 and
         method["cohort"]["manifest_sha256"] == COHORT_SHA256 and
         method["output"]["schema_document_sha256"] == OUTPUT_CONTRACT_SHA256 and
         method["source_notice_sha256"] == NOTICE_SHA256, "private contract identities differ")
    ids = cohort["subject_ids"]
    need(len(ids) == len(set(ids)) == cohort["n_subjects"] == method["cohort"]["n_subjects"], "cohort identity/count mismatch")
    rows = manifest["files"]
    need(len(rows) == N_FILES == manifest["n_original_files"], "source file count")
    need(sum(row["size_bytes"] for row in rows) == TOTAL_BYTES == manifest["total_original_bytes"], "source byte total")
    expected = {"source_manifest.json"}
    pairs, annotations, phenotype = set(), set(), 0
    for row in rows:
        rel = str(io_c.relative(row["path"]))
        need(rel not in expected, "duplicate source path")
        expected.add(rel)
        if row["role"] == "surface_timeseries":
            key = (row["subject_id"], row["hemisphere"])
            need(key not in pairs, "duplicate hemisphere source")
            pairs.add(key)
        elif row["role"] == "surface_annotation":
            need(row["hemisphere"] not in annotations, "duplicate annotation")
            annotations.add(row["hemisphere"])
        else:
            need(row["role"] == "phenotype", "unexpected original role")
            phenotype += 1
    need(pairs == {(s, h) for s in ids for h in ("lh", "rh")} and annotations == {"lh", "rh"} and phenotype == 1,
         "closed source membership mismatch")
    dirs = {str(p) for name in expected for p in Path(name).parents if str(p) != "."}
    found, seen_dirs = set(), set()
    need(root.is_dir(), "source root required")
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            rel = path.relative_to(root).as_posix()
            if stat.S_ISDIR(mode): seen_dirs.add(rel)
            else:
                need(stat.S_ISREG(mode), "nonregular source member")
                found.add(rel)
    need(found == expected and seen_dirs == dirs, "closed source inventory mismatch")
    for row in rows:
        source_bytes(root, row)  # all121 before any payload is decoded
    return root, method, cohort, manifest


def parse_phenotype(raw, ids):
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    header = next(reader, None)
    need(header == ["", "Age", "Dominant Hand", "Sex"], "source phenotype header")
    rows, seen = {}, set()
    for index, values in enumerate(reader):
        need(len(values) == len(header), "phenotype width")
        subject = values[0]
        need(subject and subject not in seen, "duplicate/empty phenotype identity")
        seen.add(subject)
        if subject in ids:
            age = io_c.number(values[1])
            need(age >= 0, "negative source age")
            rows[subject] = dict(phenotype_row_index=index, age_source=age,
                                 age_computational=float(science.computational_age([age])[0]), sex=values[3])
    need(set(rows) == set(ids), "missing selected phenotype")
    return rows, len(seen)


def parse_annotation(raw, hemisphere, expected_vertices):
    """Independent bounded big-endian FreeSurfer annotation parser (old/v2)."""
    stream = io.BytesIO(raw)
    def integer():
        b = stream.read(4)
        need(len(b) == 4, "truncated annotation integer")
        return struct.unpack(">i", b)[0]
    def text():
        n = integer()
        need(0 < n <= 16384, "annotation string bound")
        b = stream.read(n)
        need(len(b) == n and b.endswith(b"\0"), "annotation string terminator")
        return b[:-1].decode("utf-8")
    n = integer()
    need(n == expected_vertices, "annotation vertex count")
    pairs = np.frombuffer(stream.read(n * 8), dtype=">i4")
    need(pairs.size == n * 2, "truncated annotation assignments")
    pairs = pairs.reshape(n, 2)
    need(np.array_equal(pairs[:, 0], np.arange(n)), "annotation original vertex order")
    labels = pairs[:, 1].astype(np.int64)
    need(integer() == 1, "annotation color table required")
    version = integer()
    table = {}
    if version > 0:
        text()
        count = version
        need(count <= 1024, "annotation table size")
        indices = range(count)
        for index in indices:
            name = text()
            rgba = [integer() for _ in range(4)]
            table[index] = (name, rgba)
    else:
        need(version == -2, "unsupported annotation table version")
        maximum = integer()
        need(0 < maximum <= 1024, "annotation maximum table size")
        text()
        count = integer()
        need(0 < count <= maximum, "annotation entry count")
        for _ in range(count):
            index = integer()
            need(0 <= index < maximum and index not in table, "duplicate annotation table index")
            name = text()
            table[index] = (name, [integer() for _ in range(4)])
    need(stream.read(1) == b"", "trailing annotation data")
    records, all_packed, names = [], set(), set()
    for index in sorted(table):
        name, rgba = table[index]
        need(name not in names and all(0 <= c <= 255 for c in rgba), "ambiguous annotation table")
        names.add(name)
        packed = rgba[0] + (rgba[1] << 8) + (rgba[2] << 16)
        need(packed not in all_packed, "duplicate packed annotation identifier")
        all_packed.add(packed)
        vertices = np.flatnonzero(labels == packed).astype(np.int64)
        records.append(dict(hemisphere=hemisphere, annotation_id=index, label_name=name,
                            vertex_count=len(vertices), vertices=vertices, packed_rgb_id=packed))
    need(np.isin(labels, list(all_packed)).all() and not np.isin(labels, [0, -1]).any(),
         "unassigned/unrecognized source vertex")
    excluded = [r for r in records if r["label_name"] in ("Unknown", "Medial_wall")]
    need({r["label_name"] for r in excluded} == {"Unknown", "Medial_wall"}, "missing exact excluded labels")
    cortical = [r for r in records if r["label_name"] not in ("Unknown", "Medial_wall")]
    need(all(r["vertex_count"] > 0 for r in cortical), "empty cortical parcel")
    return cortical, records


def parse_surface(raw, expected_frames, expected_vertices):
    """Validate XML storage before nibabel decodes this authenticated buffer."""
    parser = expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    arrays = []
    def start(name, attrs):
        if name == "DataArray":
            need(attrs.get("ExternalFileName", "") == "" and attrs.get("Encoding") == "GZipBase64Binary", "external/unexpected GIFTI encoding")
            need(attrs.get("Dimensionality") == "1" and attrs.get("Dim0") == str(expected_vertices), "GIFTI source axis")
            need(attrs.get("DataType") == "NIFTI_TYPE_FLOAT32" and attrs.get("Intent") == "NIFTI_INTENT_TIME_SERIES", "GIFTI dtype/intent")
            need(attrs.get("ArrayIndexingOrder") == "RowMajorOrder" and attrs.get("Endian") == "LittleEndian", "GIFTI source storage convention")
            arrays.append(attrs)
    def bad_entity(*args): raise ValueError("XML entities refused")
    def doctype(name, system, public, internal): need(name == "GIFTI" and not internal, "unsafe XML doctype")
    parser.StartElementHandler = start
    parser.EntityDeclHandler = bad_entity
    parser.ExternalEntityRefHandler = bad_entity
    parser.StartDoctypeDeclHandler = doctype
    parser.Parse(raw, True)
    need(len(arrays) == expected_frames, "GIFTI frame count")
    image = nib.gifti.GiftiImage.from_bytes(raw)
    need(len(image.darrays) == expected_frames, "decoded GIFTI frame count")
    for da in image.darrays:
        need(da.data.shape == (expected_vertices,) and da.data.dtype == np.float32 and da.intent == 2001,
             "decoded source structure")
        need(da.meta.get("TimeStep") == "1000.000000", "literal unitless TimeStep changed")
        need(np.isfinite(da.data).all(), "nonfinite original functional values")
    return np.stack([da.data for da in image.darrays]), dict(data_array_count=expected_frames,
                values_per_array=expected_vertices, storage_dtype="float32", intents=[2001])


def assemble_reference(basis, method, manifest, cohort_rows, parcels, observed):
    """Attach source evidence to trusted math; also supports manufactured inputs."""
    labels = basis["partition"]["labels"]
    partition_status = basis["partition"]["status"]
    complete = np.all(basis["edge_valid"], axis=1)
    counts = dict(n_subjects=len(basis["subject_id"]), n_parcels=len(parcels),
                  n_edges=len(basis["edge_roi_index"]), n_frames_total=int(np.prod(basis["roi_timeseries"].shape[:2])),
                  n_constant_parcels_total=int(np.sum(basis["parcel_status"] == "constant")),
                  n_subjects_complete_connectome=int(complete.sum()))
    for i, row in enumerate(cohort_rows):
        row.update(n_frames=basis["roi_timeseries"].shape[1],
                   n_constant_parcels=int(np.sum(basis["parcel_status"][i] == "constant")),
                   n_valid_edges=int(basis["edge_valid"][i].sum()),
                   global_status=basis["summary_rows"][i]["global_status"],
                   segregation_status=basis["summary_rows"][i]["segregation_status"])
    cluster_rows = [] if labels is None else [dict(network_id=str(k), n_rois=int(np.sum(labels == k))) for k in np.unique(labels)]
    nw = nb = None
    if partition_status == "ok":
        ij = basis["edge_roi_index"]
        nw = int(np.sum(labels[ij[:, 0]] == labels[ij[:, 1]]))
        nb = len(ij) - nw
    partition_doc = dict(status=partition_status, method_contract_sha256=METHOD_SHA256,
                         n_rois=len(parcels), n_subjects_expected=counts["n_subjects"],
                         n_subjects_complete_connectome=int(complete.sum()), n_clusters_requested=7,
                         n_clusters_occupied=basis["partition"]["n_clusters_occupied"],
                         n_within_edges=nw, n_between_edges=nb, clusters=cluster_rows,
                         incomplete_subject_ids=basis["subject_id"][~complete].tolist())
    metadata = dict(status="ok", method_contract_sha256=METHOD_SHA256,
                    source_manifest_sha256=SOURCE_SHA256, cohort_manifest_sha256=COHORT_SHA256,
                    dataset_id="nki_enhanced_surface", cohort_order=basis["subject_id"].tolist(),
                    roi_order=basis["roi_index"].tolist(), counts=counts,
                    source_files=[{k: r[k] for k in ("path", "role", "size_bytes", "sha256")} for r in manifest["files"]],
                    software_versions={"route": "source grader; shared nibabel/NumPy corrcoef/sklearn KMeans; independent annotation/fsum/beta tail"},
                    warnings=basis["partition"]["warnings"], source_observed=observed)
    return dict(basis=basis, method=method, source_manifest=manifest, cohort_rows=cohort_rows,
                parcels=parcels, partition_doc=partition_doc, metadata=metadata)


def reconstruct(data_dir="/app/data/lifespan", method_path="/app/method_contract.json",
                cohort_path="/app/cohort_manifest.json"):
    root, method, cohort, manifest = authenticate(data_dir, method_path, cohort_path)
    ids, facts = cohort["subject_ids"], method["source_observed"]
    records = manifest["files"]
    phenotype = next(r for r in records if r["role"] == "phenotype")
    people, nrows = parse_phenotype(source_bytes(root, phenotype), ids)
    need(nrows == facts["phenotype_rows"], "phenotype total rows changed")
    parcels, by_hemi = [], {}
    for hemi, side in (("lh", "left"), ("rh", "right")):
        row = next(r for r in records if r["role"] == "surface_annotation" and r["hemisphere"] == hemi)
        cortical, all_records = parse_annotation(source_bytes(root, row), hemi, facts[side + "_vertices"])
        need(len(cortical) == facts[side + "_cortical_parcels"], "cortical parcel count changed")
        wall = next(r for r in all_records if r["label_name"] == "Medial_wall")
        unknown = next(r for r in all_records if r["label_name"] == "Unknown")
        need(wall["annotation_id"] == 42 and wall["vertex_count"] == facts[side + "_medial_wall_vertices"]
             and unknown["annotation_id"] == 0 and unknown["vertex_count"] == 0, "source excluded label support changed")
        by_hemi[hemi] = cortical
        for item in cortical:
            item["roi_index"] = len(parcels)
            parcels.append(item)
    q = np.empty((len(ids), facts["frames_per_subject"], len(parcels)), dtype=np.float32)
    rows, headers = [], []
    source_map = {(r["subject_id"], r["hemisphere"]): r for r in records if r["role"] == "surface_timeseries"}
    for i, person in enumerate(ids):
        row = dict(subject_id=person, cohort_index=i, **people[person])
        header = dict(subject_id=person)
        for hemi, side in (("lh", "left"), ("rh", "right")):
            record = source_map[(person, hemi)]
            matrix, observed = parse_surface(source_bytes(root, record), facts["frames_per_subject"], facts[side + "_vertices"])
            for p in by_hemi[hemi]:
                q[i, :, p["roi_index"]] = science.vertex_mean(matrix[:, p["vertices"]])
            del matrix
            row.update({side + "_path": record["path"], side + "_sha256": record["sha256"]})
            header.update({side + "_" + k: v for k, v in observed.items()})
        rows.append(row)
        headers.append(header)
    basis = science.build_basis(q, [r["age_computational"] for r in rows], ids, np.arange(len(parcels)))
    observed = {k: facts[k] for k in ("left_vertices", "right_vertices", "left_cortical_parcels", "right_cortical_parcels",
                "header_timestep_literals", "header_timing_unit", "documented_tr_seconds", "timing_policy")}
    observed["subjects"] = headers
    return assemble_reference(basis, method, manifest, rows, parcels, observed)
