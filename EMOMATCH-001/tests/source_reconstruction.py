"""Independent source primitives for EMOMATCH; no model fitting or output writes.

Adapted from reviewed TRACK inspector e8f95a3ae0ff82d8f10b28ed5bb01c68c7467bda089d93232b26d6cd00760c4d.
Original parsing is forbidden until a separate execution gate. Source authority
is the grader-owned manifest byte pin below, never an agent helper or hash argument.
BOLD is decoded explicitly one NIfTI Fortran volume at a time through gzip;
NumPy float64 reduction and nibabel header interpretation are shared software.
No signal processing, HRF construction, SVD, or outcome-derived input selection.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import nibabel as nib
import numpy as np

IDS = tuple(f"sub-{i:04d}" for i in (*range(2, 10), *range(11, 23)))
DATA_COMMIT = "81c3294a906d03d41952a06df94c83746c2d7509"
ATLAS_COMMIT = "15d7c02160f79f5218d2545b4febebeecc11531d"
PERSON_ROLES = {"bold", "confounds", "events", "raw_bold_json", "preproc_bold_json", "confounds_json"}
SINGLE_ROLES = {"participants", "participants_schema", "dataset_description", "derivative_description",
                "readme", "task_bold_json", "task_events_json", "atlas_image", "atlas_labels",
                "atlas_description", "atlas_license"}
CONFOUNDS = tuple([f"trans_{v}" for v in "xyz"] + [f"rot_{v}" for v in "xyz"] +
                  [f"a_comp_cor_{i:02d}" for i in range(5)] + ["white_matter", "csf"])
SPHERES = {"amy_L": (-23, -5, -19), "amy_R": (23, -5, -19), "ffa_L": (-40, -52, -18),
           "ffa_R": (42, -52, -18), "dACC": (0, 20, 38), "aIns_L": (-34, 20, 4),
           "aIns_R": (36, 22, 2), "dlPFC_L": (-44, 20, 30), "dlPFC_R": (46, 22, 28),
           "IPS_L": (-28, -58, 46), "IPS_R": (30, -56, 46)}
NETWORKS = {"Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"}
MISSING = {"", "n/a"}  # Parent-approved pre-signal source token policy.
SOURCE_MANIFEST_SHA256 = "70000c5c93c2c43f1e7968feb38aaebb4e7622a5f6d2ec1167191337614ef950"
SOURCE_BOLD_SHAPE = (65, 77, 60, 135)
SOURCE_CONDITION_COUNTS = {"control": 24, "emotion": 24}
MAX_SMALL = 16 * 1024 * 1024
MAX_VOXELS = 20_000_000
SUPPORT_PREFIX = b"EMOMATCH_support_v1\n"


def need(ok, code):
    if not ok:
        raise ValueError(code)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def finite_float(token):
        value = float(token)
        need(math.isfinite(value), "nonfinite_json")
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def safe_path(value):
    p = Path(value)
    need(p.is_absolute(), "absolute_path_required")
    # Check lexical ancestors before normalization, including symlink/../ tricks.
    current = Path(p.anchor)
    for part in p.parts[1:]:
        current /= part
        need(not current.is_symlink(), "symlink_path")
        if current.exists():
            need(current == p or current.is_dir(), "non_directory_ancestor")
    return Path(os.path.abspath(p))


def disjoint(a, b):
    need(a != b and a not in b.parents and b not in a.parents, "overlapping_paths")


def signature(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


@contextmanager
def opened(path, expected=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode), "source_not_regular")
        if expected is not None:
            need(signature(before) == expected, "source_changed_since_authentication")
        yield stream
        need(signature(os.fstat(stream.fileno())) == signature(before), "source_changed_during_read")


def hex_digest(value, length):
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def authenticate(root, manifest_path, manifest_sha):
    need(hex_digest(manifest_sha, 64), "invalid_manifest_pin")
    with opened(manifest_path) as stream:
        raw = stream.read(MAX_SMALL + 1)
    need(len(raw) <= MAX_SMALL and hashlib.sha256(raw).hexdigest() == manifest_sha, "manifest_identity")
    m = strict_json(raw)
    need(m["dataset_id"] == "ds002790" and m["dataset_release"] == "2.0.0", "dataset_identity")
    need(m["dataset_commit"] == DATA_COMMIT and m["templateflow_commit"] == ATLAS_COMMIT, "source_commits")
    need(m["selected_participant_ids"] == list(IDS), "cohort_identity")
    rows = m["files"]
    need(type(rows) is list and len(rows) == len(IDS) * 6 + 11 == m["file_count"], "member_count")
    paths, keys, dirs = set(), set(), set()
    for r in rows:
        rel = PurePosixPath(r["path"])
        need(str(rel) == r["path"] and not rel.is_absolute() and ".." not in rel.parts and
             "\\" not in r["path"] and rel.parts, "unsafe_relative_path")
        need(r["path"] not in paths, "duplicate_source_path")
        paths.add(r["path"])
        dirs.update(str(p) for p in rel.parents if str(p) != ".")
        key = (r["participant_id"], r["role"])
        need(key not in keys, "duplicate_source_key")
        keys.add(key)
        need(type(r["size_bytes"]) is int and r["size_bytes"] > 0, "invalid_source_size")
        need(hex_digest(r.get("sha256"), 64), "completed_measured_sha256_required")
        need(r["source_commit"] == (ATLAS_COMMIT if r["role"].startswith("atlas_") else DATA_COMMIT), "member_commit")
        need(hex_digest(r["source_git_blob_sha1"], 40), "source_git_entry_identity")
        if r["identity_kind"] == "git_blob_content":
            need(r["source_git_mode"] == "100644" and hex_digest(r["content_git_blob_sha1"], 40), "content_git_identity")
            need(r["content_git_blob_sha1"] == r["source_git_blob_sha1"], "regular_git_identity")
        else:
            need(r["identity_kind"] == "published_annex_payload_md5" and r["source_git_mode"] == "120000" and
                 r["content_git_blob_sha1"] is None and hex_digest(r["md5"], 32), "annex_payload_identity")
    expected = {(s, role) for s in IDS for role in PERSON_ROLES} | {(None, role) for role in SINGLE_ROLES}
    need(keys == expected, "source_role_membership")
    need(sum(r["size_bytes"] for r in rows) == m["total_bytes"], "total_bytes")
    actual_files, actual_dirs = set(), set()
    for base, subdirs, filenames in os.walk(root, followlinks=False):
        for name in subdirs + filenames:
            p = Path(base) / name
            mode = p.lstat().st_mode
            rel = p.relative_to(root).as_posix()
            if stat.S_ISDIR(mode):
                actual_dirs.add(rel)
            else:
                need(stat.S_ISREG(mode), "nonregular_inventory_member")
                actual_files.add(rel)
    need(actual_files == paths and actual_dirs == dirs, "closed_source_inventory")
    signatures = {}
    for r in rows:
        sha, md5 = hashlib.sha256(), hashlib.md5()
        git = hashlib.sha1(f"blob {r['size_bytes']}\0".encode())
        count = 0
        with opened(root / r["path"]) as stream:
            before = os.fstat(stream.fileno())
            need(before.st_size == r["size_bytes"], "source_size")
            while chunk := stream.read(1024 * 1024):
                count += len(chunk)
                sha.update(chunk); md5.update(chunk); git.update(chunk)
            signatures[r["path"]] = signature(before)
        need(count == r["size_bytes"] and sha.hexdigest() == r["sha256"], "source_sha256")
        if r["identity_kind"] == "git_blob_content":
            need(git.hexdigest() == r["content_git_blob_sha1"], "source_git_blob")
        else:
            need(md5.hexdigest() == r["md5"], "source_published_md5")
    return m, {(r["participant_id"], r["role"]): r for r in rows}, signatures


def read_small(root, row, sig):
    need(row["size_bytes"] <= MAX_SMALL, "metadata_size_cap")
    with opened(root / row["path"], sig[row["path"]]) as stream:
        raw = stream.read(MAX_SMALL + 1)
    need(len(raw) == row["size_bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], "metadata_changed")
    return raw


def finite_or_none(value):
    return float(value) if math.isfinite(float(value)) else None


def header_from_bytes(raw, role):
    need(len(raw) == 352, "short_nifti_header")
    h = nib.Nifti1Header(raw[:348], check=False)
    need(bytes(h["magic"]) == b"n+1\x00", "single_file_nifti1_required")
    shape = tuple(int(v) for v in h.get_data_shape())
    need(len(shape) == (4 if role == "bold" else 3) and all(v > 0 for v in shape), "nifti_dimensions")
    need(math.prod(shape[:3]) <= MAX_VOXELS and (role != "bold" or shape[3] <= 10000), "nifti_shape_cap")
    dtype = h.get_data_dtype()
    need(dtype.kind in "iuf" and dtype.itemsize <= 8 and int(h["bitpix"]) == dtype.itemsize * 8, "nifti_dtype")
    affine = np.asarray(h.get_best_affine(), dtype=np.float64)
    need(np.isfinite(affine).all() and np.linalg.det(affine[:3, :3]) != 0, "invalid_affine")
    need(np.isfinite(h["pixdim"][1:len(shape)+1]).all() and np.all(h["pixdim"][1:len(shape)+1] > 0), "invalid_pixdim")
    slope, inter = float(h["scl_slope"]), float(h["scl_inter"])
    if not math.isfinite(slope) or slope == 0:
        effective_slope, effective_inter = 1.0, 0.0
    else:
        need(math.isfinite(inter), "invalid_scaling_intercept")
        effective_slope, effective_inter = slope, inter
    offset = float(h["vox_offset"])
    need(math.isfinite(offset) and offset == int(offset) and 352 <= offset <= 1024 * 1024, "nifti_vox_offset")
    spatial, temporal = h.get_xyzt_units()
    tr_raw = float(h["pixdim"][4]) if role == "bold" else None
    tr = tr_raw * {"sec": 1, "msec": .001, "usec": .000001}[temporal] if role == "bold" and temporal in {"sec", "msec", "usec"} else None
    report = {"shape": list(shape), "dtype": dtype.str, "endianness": h.endianness,
              "voxel_sizes": [float(v) for v in h["pixdim"][1:4]], "spatial_unit": spatial, "temporal_unit": temporal,
              "header_tr_raw": tr_raw, "header_tr_seconds": tr, "chosen_affine": affine.tolist(),
              "header_toffset_raw": finite_or_none(h["toffset"]),
              "header_toffset_nonfinite": not math.isfinite(float(h["toffset"])),
              "time_origin_note": "Literal exporter header only; frame0=0 would be a computational convention, not verified slice-time reference. No extra discarded volumes applied.",
              "qform_code": int(h["qform_code"]), "sform_code": int(h["sform_code"]),
              "qform": h.get_qform().tolist(), "sform": h.get_sform().tolist(),
              "raw_scaling_slope": finite_or_none(slope), "raw_scaling_intercept": finite_or_none(inter),
              "raw_scaling_nonfinite": {"slope": not math.isfinite(slope), "intercept": not math.isfinite(inter)},
              "effective_slope": effective_slope, "effective_intercept": effective_inter, "vox_offset": int(offset),
              "description": bytes(h["descrip"]).rstrip(b"\0").decode("utf-8", "replace"),
              "intent_code": int(h["intent_code"]), "extension_flag": list(raw[348:352]), "logical_header_bytes_read": 352}
    return report, dtype, affine


def read_header(root, row, sig):
    need(row["role"] in {"bold", "atlas_image"}, "image_role")
    with opened(root / row["path"], sig[row["path"]]) as stream, gzip.GzipFile(fileobj=stream, mode="rb") as gz:
        raw = gz.read(352)  # Never seek/read a BOLD sample. gzip may buffer compressed bytes.
    return header_from_bytes(raw, row["role"])


def read_atlas(root, row, sig):
    need(row["role"] == "atlas_image", "atlas_decoder_role")
    report, dtype, affine = read_header(root, row, sig)
    need(report["spatial_unit"] == "mm", "atlas_unit_not_mm")
    n = math.prod(report["shape"])
    payload_bytes = n * dtype.itemsize
    with opened(root / row["path"], sig[row["path"]]) as stream, gzip.GzipFile(fileobj=stream, mode="rb") as gz:
        prefix = gz.read(report["vox_offset"])
        raw = gz.read(payload_bytes + 1)
    need(len(prefix) == report["vox_offset"] and len(raw) == payload_bytes, "atlas_payload_length")
    labels = np.frombuffer(raw, dtype=dtype).reshape(report["shape"], order="F").astype(np.float64)
    labels = labels * report["effective_slope"] + report["effective_intercept"]
    need(np.isfinite(labels).all() and np.all(labels == np.floor(labels)), "atlas_labels_not_finite_integer")
    need(set(np.unique(labels).tolist()) <= set(range(101)), "unknown_atlas_label")
    labels = labels.astype(np.int16)
    report["label_counts"] = {str(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    return report, labels, affine


def tsv(raw):
    need(len(raw) <= MAX_SMALL, "table_size_cap")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t"))
    need(rows and len(rows) <= 10001 and 0 < len(rows[0]) <= 1000, "table_shape_cap")
    header = rows[0]
    need(len(header) == len(set(header)) and all(header), "table_header")
    need(all(len(r) == len(header) and all(len(v) <= 4096 for v in r) for r in rows[1:]), "ragged_or_large_table")
    return header, [dict(zip(header, r)) for r in rows[1:]]


def numeric_token(token):
    if token in MISSING:
        return {"token": token, "status": "missing", "value": None}
    try:
        value = float(token)
    except (ValueError, TypeError):
        return {"token": token, "status": "invalid", "value": None}
    return {"token": token, "status": "finite" if math.isfinite(value) else "nonfinite",
            "value": value if math.isfinite(value) else None}


def event_report(raw, n_frames, tr):
    header, source = tsv(raw)
    need({"onset", "duration", "trial_type", "response_time"} <= set(header), "event_required_columns")
    rows, issues, valid_rt = [], [], []
    for i, r in enumerate(source):
        parsed = {key: numeric_token(r[key]) for key in ("onset", "duration", "response_time")}
        included = r["trial_type"] in {"emotion", "control"}
        rt = parsed["response_time"]
        valid = rt["status"] == "finite" and rt["value"] > 0
        if included and valid:
            valid_rt.append(rt["value"])
        if included and not valid and rt["status"] != "missing":
            issues.append({"code": "nonpositive_or_invalid_response_time", "source_row_index": i})
        for key in ("onset", "duration"):
            p = parsed[key]
            if p["status"] != "finite" or (key == "duration" and p["value"] < 0):
                issues.append({"code": "invalid_event_" + key, "source_row_index": i})
        if parsed["onset"]["status"] == "finite" and parsed["onset"]["value"] < -24:
            issues.append({"code": "onset_before_min_onset", "source_row_index": i})
        duration = parsed["duration"]
        diff = duration["value"] - rt["value"] if duration["status"] == "finite" and valid else None
        onset = parsed["onset"]["value"]
        end_outside = (onset < 0 or onset + duration["value"] > n_frames * tr) if onset is not None and duration["value"] is not None and tr is not None else None
        rows.append({"source_row_index": i, "original": r, "numeric": parsed, "included_condition": included,
                     "valid_positive_rt": valid, "duration_minus_rt": diff, "outside_header_frame_span": end_outside})
    median = float(np.median(valid_rt)) if valid_rt else None
    if median is None:
        issues.append({"code": "no_valid_positive_target_rt"})
    for row in rows:
        d, rt = row["numeric"]["duration"], row["numeric"]["response_time"]
        row["omitted_duration_minus_pooled_median"] = d["value"] - median if row["included_condition"] and rt["status"] == "missing" and d["value"] is not None and median is not None else None
    onset = [r["numeric"]["onset"]["value"] for r in rows if r["numeric"]["onset"]["value"] is not None]
    return {"header": header, "row_count": len(rows), "condition_counts": dict(Counter(r["trial_type"] for r in source)),
            "rows": rows, "diagnostic_missing_tokens": sorted(MISSING), "pooled_valid_rt_count": len(valid_rt),
            "pooled_valid_rt_median": median, "duplicate_finite_onsets": len(onset) - len(set(onset)),
            "finite_onset_descents": sum(b < a for a, b in zip(onset, onset[1:])), "issues": issues,
            "modeled_design_or_response_read": False}


def confound_report(raw, n_frames):
    header, rows = tsv(raw)
    result = {"header": header, "row_count": len(rows), "expected_frames": n_frames, "columns": {}, "issues": []}
    if len(rows) != n_frames:
        result["issues"].append({"code": "confound_frame_mismatch"})
    for name in CONFOUNDS:
        if name not in header:
            result["issues"].append({"code": "missing_required_confound", "column": name})
            continue
        parsed = [numeric_token(r[name]) for r in rows]
        finite = [p["value"] for p in parsed if p["status"] == "finite"]
        positions = {s: [i for i, p in enumerate(parsed) if p["status"] == s] for s in ("missing", "invalid", "nonfinite")}
        if positions["invalid"] or positions["nonfinite"]:
            result["issues"].append({"code": "invalid_nonmissing_confound", "column": name})
        result["columns"][name] = {"tokens": [p["token"] for p in parsed], "positions": positions,
                                    "finite_count": len(finite), "finite_min": min(finite) if finite else None,
                                    "finite_max": max(finite) if finite else None,
                                    "finite_values_exact_constant": bool(finite and min(finite) == max(finite)),
                                    "all_declared_missing": len(positions["missing"]) == len(rows)}
    result["imputation_performed"] = False
    result["rank_or_regression_computed"] = False
    return result


def atlas_lut(raw):
    header, rows = tsv(raw)
    need({"index", "name", "color"} <= set(header) and len(rows) == 100, "atlas_lut_shape")
    out = []
    for r in rows:
        need(re.fullmatch(r"[1-9][0-9]*", r["index"]) is not None, "atlas_lut_index")
        parts = r["name"].split("_")
        need(len(parts) >= 4 and parts[0] == "7Networks" and parts[1] in {"LH", "RH"} and parts[2] in NETWORKS, "atlas_lut_name")
        out.append({**r, "label_id": int(r["index"]), "hemisphere": parts[1], "network": parts[2]})
    need({r["label_id"] for r in out} == set(range(1, 101)), "atlas_lut_membership")
    need({r["network"] for r in out} == NETWORKS, "atlas_network_membership")
    return out


def nearest_labels(coords, labels):
    need(np.isfinite(coords).all(), "nonfinite_atlas_coordinates")
    half = .5 * np.rint(2 * coords)
    snapped = np.where(np.abs(coords - half) <= 1e-7, half, coords)
    inside = np.all((snapped >= 0) & (snapped <= np.asarray(labels.shape) - 1), axis=1)
    result = np.zeros(len(coords), dtype=np.int16)
    ijk = np.floor(snapped[inside] + .5).astype(np.int64)
    result[inside] = labels[tuple(ijk.T)]
    return result


def support_digest(indices):
    unique = np.unique(np.asarray(indices, dtype=np.int64))
    return hashlib.sha256(SUPPORT_PREFIX + unique.astype("<i8").tobytes()).hexdigest()


def geometry_support(shape, affine, labels, atlas_affine, chunk_size=65536):
    need(len(shape) == 3 and all(int(v) == v and v > 0 for v in shape) and math.prod(shape) <= MAX_VOXELS, "geometry_shape")
    need(np.isfinite(affine).all() and np.isfinite(atlas_affine).all(), "geometry_affine")
    mapping = np.linalg.inv(atlas_affine) @ affine
    all_ids = list(range(1, 101)) + list(SPHERES)
    hashes = {str(k): hashlib.sha256(SUPPORT_PREFIX) for k in all_ids}
    counts = Counter({str(k): 0 for k in all_ids})
    sphere_overlap = sphere_cortical_overlap = cortical_count = 0
    for start in range(0, math.prod(shape), chunk_size):
        flat = np.arange(start, min(start + chunk_size, math.prod(shape)), dtype=np.int64)
        ijk = np.column_stack(np.unravel_index(flat, shape, order="C"))
        assigned = nearest_labels(ijk @ mapping[:3, :3].T + mapping[:3, 3], labels)
        world = ijk @ affine[:3, :3].T + affine[:3, 3]
        cortical_count += int(np.count_nonzero(assigned))
        for label in np.unique(assigned):
            if label:
                indices = flat[assigned == label]
                hashes[str(label)].update(indices.astype("<i8").tobytes()); counts[str(label)] += len(indices)
        sphere_multiplicity = np.zeros(len(flat), dtype=np.int16)
        for name, center in SPHERES.items():
            distance2 = np.sum((world - np.asarray(center)) ** 2, axis=1, dtype=np.float64)
            selected = distance2 <= 36.0
            indices = flat[selected]
            hashes[name].update(indices.astype("<i8").tobytes()); counts[name] += len(indices)
            sphere_multiplicity += selected
        sphere_overlap += int(np.count_nonzero(sphere_multiplicity > 1))
        sphere_cortical_overlap += int(np.count_nonzero((sphere_multiplicity > 0) & (assigned > 0)))
    return {"supports": [{"roi_id": str(k), "n_voxels": counts[str(k)], "support_sha256": hashes[str(k)].hexdigest()} for k in all_ids],
            "empty_roi_ids": [str(k) for k in all_ids if not counts[str(k)]], "cortical_voxel_count": cortical_count,
            "voxels_in_multiple_spheres": sphere_overlap, "sphere_cortex_overlap_voxels": sphere_cortical_overlap,
            "support_digest_prefix": SUPPORT_PREFIX.decode(), "bold_samples_read": 0,
            "physical_sphere_rule": "distance_squared_mm <= 36; no epsilon, rescue or brain mask",
            "atlas_rule": "composed affine; 1e-7 half-grid snap; closed post-snap center domain; floor(u+0.5)"}



def spatial_indices(shape, affine, labels, atlas_affine, chunk_size=65536):
    """Exact public geometry, ascending C-order source voxel membership."""
    need(len(shape) == 3 and all(type(v) is int and v > 0 for v in shape) and
         math.prod(shape) <= MAX_VOXELS, "geometry_shape")
    need(np.isfinite(affine).all() and np.isfinite(atlas_affine).all(), "geometry_affine")
    mapping = np.linalg.inv(atlas_affine) @ affine
    ids = [str(i) for i in range(1, 101)] + list(SPHERES)
    parts = {key: [] for key in ids}
    for start in range(0, math.prod(shape), chunk_size):
        flat = np.arange(start, min(start + chunk_size, math.prod(shape)), dtype=np.int64)
        ijk = np.column_stack(np.unravel_index(flat, shape, order="C"))
        assigned = nearest_labels(ijk @ mapping[:3, :3].T + mapping[:3, 3], labels)
        world = ijk @ affine[:3, :3].T + affine[:3, 3]
        for label in np.unique(assigned):
            if label:
                parts[str(label)].append(flat[assigned == label])
        for name, center in SPHERES.items():
            selected = np.sum((world - np.asarray(center)) ** 2, axis=1, dtype=np.float64) <= 36
            parts[name].append(flat[selected])
    return ids, {key: np.concatenate(parts[key]) if parts[key] else np.empty(0, dtype=np.int64)
                 for key in ids}


def _read_exact(stream, n):
    need(type(n) is int and 0 <= n <= MAX_VOXELS * 8, "decoded_read_cap")
    data = stream.read(n)
    need(len(data) == n, "truncated_nifti_payload")
    return data


def extract_roi_means(root, row, sig, header, dtype, roi_ids, supports):
    """One full spatial volume at a time; no nibabel BOLD array/proxy API.

    Raw data are NIfTI Fortran storage. The C-order flattened, scaled float64
    volume is indexed by fixed ascending source indices, then ordinary float64
    arithmetic mean is evaluated. The whole declared source volume must be
    finite, not only selected voxels. Parent's pre-signal source policy makes
    empty support a failed precondition, not an exclusion or invented observation.
    """
    need(row["role"] == "bold", "bold_decoder_role")
    shape = tuple(header["shape"])
    need(len(shape) == 4 and math.prod(shape[:3]) <= MAX_VOXELS, "bold_shape")
    need(len(roi_ids) > 0 and len(roi_ids) == len(set(roi_ids)) and set(roi_ids) == set(supports), "roi_membership")
    n_voxels = math.prod(shape[:3])
    for key in roi_ids:
        ix = supports[key]
        need(isinstance(ix, np.ndarray) and ix.dtype.kind in "iu" and ix.ndim == 1 and
             len(ix) > 0, "empty_or_invalid_roi_support")
        need(np.all(ix >= 0) and np.all(ix < n_voxels) and np.all(ix[1:] > ix[:-1]), "source_C_sorted_unique_support")
    means = np.empty((shape[3], len(roi_ids)), dtype=np.float64)
    peaks = np.zeros(len(roi_ids), dtype=np.float64)
    volume_bytes = int(n_voxels * dtype.itemsize)
    with opened(root / row["path"], sig[row["path"]]) as stream, gzip.GzipFile(fileobj=stream, mode="rb") as gz:
        prefix = _read_exact(gz, header["vox_offset"])
        current, current_dtype, _ = header_from_bytes(prefix[:352], "bold")
        need(current == header and current_dtype == dtype, "header_changed_before_decoding")
        for frame in range(shape[3]):
            raw = _read_exact(gz, volume_bytes)
            stored = np.frombuffer(raw, dtype=dtype).reshape(shape[:3], order="F")
            with np.errstate(over="raise", invalid="raise"):
                volume = stored.astype(np.float64) * header["effective_slope"] + header["effective_intercept"]
            need(np.isfinite(volume).all(), "nonfinite_original_or_scaled_BOLD")
            flat = volume.ravel(order="C")
            for r, key in enumerate(roi_ids):
                selected = np.ascontiguousarray(flat[supports[key]], dtype=np.float64)
                with np.errstate(over="raise", invalid="raise"):
                    means[frame, r] = selected.mean(dtype=np.float64)
                peaks[r] = max(peaks[r], float(np.max(np.abs(selected))))
        need(gz.read(1) == b"", "trailing_nifti_payload")
    need(np.isfinite(means).all() and np.isfinite(peaks).all(), "nonfinite_roi_reduction")
    return means, peaks


def event_primitives(report):
    """Preserve every event; selected modeling inputs use declared missing masks."""
    need(not report["issues"], "unsupported_event_metadata_precondition")
    rows = report["rows"]
    selected = [r for r in rows if r["included_condition"]]
    need(selected, "no_target_events")
    onsets = np.asarray([r["numeric"]["onset"]["value"] for r in selected], dtype=np.float64)
    durations = np.asarray([r["numeric"]["duration"]["value"] for r in selected], dtype=np.float64)
    missing = np.asarray([r["numeric"]["response_time"]["status"] == "missing" for r in selected], dtype=bool)
    rt = np.asarray([0.0 if absent else r["numeric"]["response_time"]["value"]
                     for r, absent in zip(selected, missing)], dtype=np.float64)
    need(np.isfinite(onsets).all() and np.isfinite(durations).all() and np.isfinite(rt).all(), "event_numeric_precondition")
    return dict(ledger=rows, column_names=list(report["header"]),
                selected_source_event_row=np.asarray([r["source_row_index"] for r in selected], dtype=np.int64),
                conditions=np.asarray([r["original"]["trial_type"] for r in selected], dtype="U"),
                onsets=onsets, source_durations=durations, response_time=rt, response_time_missing=missing)


def confound_primitives(report):
    need(not report["issues"] and set(report["columns"]) == set(CONFOUNDS), "unsupported_confound_metadata_precondition")
    raw = np.zeros((report["row_count"], len(CONFOUNDS)), dtype=np.float64)
    missing = np.zeros(raw.shape, dtype=bool)
    for j, name in enumerate(CONFOUNDS):
        for i, token in enumerate(report["columns"][name]["tokens"]):
            parsed = numeric_token(token)
            need(parsed["status"] in {"finite", "missing"}, "confound_numeric_precondition")
            missing[i, j] = parsed["status"] == "missing"
            if not missing[i, j]:
                raw[i, j] = parsed["value"]
    return raw, missing


def reconstruct(data_dir="/app/data/emomatch", manifest_path="/app/source_manifest.json", *, subjects=None):
    """Return source primitives only. No normalization/design/fits occur here.

    Production caller must require returned participant_ids == IDS. An explicit
    reviewed native pilot may request a nonempty unique subset; all131 files are
    still authenticated before any original payload parsing or BOLD decoding.
    SOURCE_MANIFEST_SHA256 is grader-owned. Installing the completed public
    source-manifest pin does not authorize original scientific execution.
    """
    need(hex_digest(SOURCE_MANIFEST_SHA256, 64), "source_manifest_freeze_pending")
    root, manifest_path = safe_path(data_dir), safe_path(manifest_path)
    need(root.is_dir() and manifest_path.is_file(), "missing_source_input")
    chosen = IDS if subjects is None else tuple(subjects)
    need(chosen and len(chosen) == len(set(chosen)) and set(chosen) <= set(IDS), "requested_subject_membership")
    chosen = tuple(subject for subject in IDS if subject in chosen)
    manifest, records, sig = authenticate(root, manifest_path, SOURCE_MANIFEST_SHA256)
    atlas_header, labels, atlas_affine = read_atlas(root, records[None, "atlas_image"], sig)
    lut = atlas_lut(read_small(root, records[None, "atlas_labels"], sig))
    phead, participants = tsv(read_small(root, records[None, "participants"], sig))
    need("participant_id" in phead, "participants_id_column")
    pids = [r["participant_id"] for r in participants]
    need(len(pids) == len(set(pids)) and set(IDS) <= set(pids), "participant_identity_join")
    cohort = [dict(source_row=i, participant_id=r["participant_id"], selected=r["participant_id"] in IDS, original=r)
              for i, r in enumerate(participants)]
    # Literal documentary texts are not coerced to duplicate-collapsing objects.
    # Downstream provenance can inspect declared fields with its own strict parser.
    source_documents = {role: read_small(root, records[None, role], sig).decode("utf-8")
                        for role in sorted(SINGLE_ROLES - {"atlas_image", "atlas_labels", "participants"})}
    task_timing = strict_json(read_small(root, records[None, "task_bold_json"], sig))
    prepared, cache = [], {}
    # Metadata for every requested subject is validated before its first BOLD sample.
    for subject in chosen:
        header, dtype, affine = read_header(root, records[subject, "bold"], sig)
        need(tuple(header["shape"]) == SOURCE_BOLD_SHAPE and dtype.kind == "f" and dtype.itemsize == 4,
             "unsupported_BOLD_shape_or_dtype")
        need(header["spatial_unit"] == "mm", "unsupported_BOLD_spatial_units")
        need(header["temporal_unit"] == "sec" and header["header_tr_seconds"] == 2.0, "unsupported_BOLD_frame_TR")
        sidecars = {role: strict_json(read_small(root, records[subject, role], sig))
                    for role in ("raw_bold_json", "preproc_bold_json", "confounds_json")}
        for role in ("raw_bold_json", "preproc_bold_json"):
            tr = sidecars[role].get("RepetitionTime", task_timing.get("RepetitionTime"))
            need(type(tr) in {int, float} and tr == 2.0, "unsupported_documentary_frame_TR")
        event_metadata = event_report(read_small(root, records[subject, "events"], sig), header["shape"][3], 2.0)
        need(event_metadata["condition_counts"] == SOURCE_CONDITION_COUNTS, "unsupported_source_event_membership")
        events = event_primitives(event_metadata)
        confound = confound_report(read_small(root, records[subject, "confounds"], sig), header["shape"][3])
        raw_confounds, missing = confound_primitives(confound)
        key = (tuple(header["shape"][:3]), affine.astype("<f8").tobytes())
        if key not in cache:
            cache[key] = spatial_indices(tuple(header["shape"][:3]), affine, labels, atlas_affine)
        roi_ids, indices = cache[key]
        need(all(len(indices[k]) for k in roi_ids), "empty_roi_support")
        supports = [dict(roi_id=k, source_C_flat_indices=indices[k].copy(), n_voxels=len(indices[k]),
                         support_sha256=support_digest(indices[k])) for k in roi_ids]
        prepared.append(dict(participant_id=subject, header=header, dtype=dtype, events=events,
                             event_column_names=events["column_names"], confound_column_names=list(confound["header"]),
                             confound_raw=raw_confounds, confound_missing=missing, confound_names=list(CONFOUNDS),
                             supports=supports, indices=indices, sidecars=sidecars, roi_ids=roi_ids))
    for person in prepared:
        subject = person["participant_id"]
        means, peaks = extract_roi_means(root, records[subject, "bold"], sig, person["header"], person["dtype"],
                                        person["roi_ids"], person["indices"])
        person["raw_roi_mean"] = means
        person["roi_source_peak_abs"] = peaks
        person["source_frame_index"] = np.arange(means.shape[0], dtype=np.int64)
        person["frame_times_s"] = 2.0 * person["source_frame_index"]
        del person["indices"], person["dtype"]
    for path, expected in sig.items():
        need(signature((root / path).stat(follow_symlinks=False)) == expected, "source_changed_before_return")
    return dict(source_manifest=manifest, source_records=manifest["files"], source_documents=source_documents,
                participant_ids=list(chosen), roi_ids=[str(i) for i in range(1, 101)] + list(SPHERES),
                cohort_rows=cohort, subjects=prepared, atlas=dict(header=atlas_header, lut=lut),
                task_timing=task_timing, source_proof=dict(manifest_sha256=SOURCE_MANIFEST_SHA256,
                file_count_authenticated=len(manifest["files"]), bytes_authenticated=manifest["total_bytes"],
                dataset_commit=DATA_COMMIT, templateflow_commit=ATLAS_COMMIT,
                private_source_pin=True, public_helper_imported=False, model_fitting_performed=False))
