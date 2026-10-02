"""Source-only NETSEG reconstruction; no oracle, prior bank or output inputs.

This independently implements extraction and downstream arithmetic. Nibabel
reading and SciPy's pivoted QR are shared numerical dependencies, not three
independent implementations of those algorithms. No numerical bank is loaded.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat

import numpy as np
from scipy.linalg import qr

METHOD_SHA256 = "d3b67c864af6855b654ddf5e803e7908bc0d973ae7d5ea45b27604fc5787db47"
EPS = np.finfo(np.float64).eps


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def regular(path):
    path = Path(path).absolute()
    for node in (path, *path.parents):
        require(not node.is_symlink(), f"Symlink path: {node}")
    require(stat.S_ISREG(path.stat().st_mode), f"Not a regular file: {path}")
    return path


def digest(path):
    h = hashlib.sha256()
    with regular(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def finite_json(value):
    if isinstance(value, dict):
        require(all(isinstance(k, str) for k in value), "JSON keys must be strings")
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    elif isinstance(value, float):
        require(math.isfinite(value), "Nonfinite JSON")


def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, f"Duplicate JSON key: {k}")
            result[k] = v
        return result

    def bad(value):
        raise AssertionError(f"Nonfinite JSON token: {value}")

    value = json.loads(regular(path).read_text(), object_pairs_hook=pairs,
                       parse_constant=bad)
    finite_json(value)
    return value


def numeric(array, name):
    a = np.asarray(array)
    require(a.dtype.kind in "iuf" and a.dtype.kind != "b", f"{name}: real numeric required")
    a = a.astype(np.float64)
    require(np.isfinite(a).all(), f"{name}: nonfinite values")
    return a


def nearest_labels(atlas, atlas_affine, shape, target_affine):
    atlas = numeric(atlas, "atlas")
    require(atlas.ndim == 3 and np.equal(atlas, np.floor(atlas)).all(), "Invalid atlas labels")
    transform = np.linalg.solve(numeric(atlas_affine, "atlas affine"),
                                numeric(target_affine, "target affine"))
    ijk = np.indices(shape, dtype=np.float64).reshape(3, -1)
    coordinates = transform[:3, :3] @ ijk + transform[:3, 3, None]
    valid = np.all((coordinates >= 0) &
                   (coordinates <= (np.array(atlas.shape) - 1)[:, None]), axis=0)
    labels = np.zeros(ijk.shape[1], dtype=np.int64)
    nearest = np.floor(coordinates[:, valid] + 0.5).astype(np.int64)
    labels[valid] = atlas[tuple(nearest)].astype(np.int64)
    return labels.reshape(shape)


def parcel_means(data, labels, parcel_ids):
    data = numeric(data, "full scaled BOLD")
    require(data.ndim == 4 and data.shape[:3] == labels.shape, "BOLD/label shape mismatch")
    ids = np.asarray(parcel_ids, dtype=np.int64)
    require(np.array_equal(ids, np.arange(1, len(ids) + 1)), "Canonical parcel IDs required")
    flat_labels = labels.ravel()
    require(np.all((flat_labels >= 0) & (flat_labels <= len(ids))), "Unknown target labels")
    counts = np.bincount(flat_labels, minlength=len(ids) + 1)[1:]
    require(np.all(counts > 0), "SOURCE_PRECONDITION_FAILURE: missing target parcel")
    flat = data.reshape((-1, data.shape[3]))
    result = np.empty((data.shape[3], len(ids)), dtype=np.float64)
    for frame in range(data.shape[3]):
        sums = np.bincount(flat_labels, weights=flat[:, frame], minlength=len(ids) + 1)
        result[frame] = sums[1:] / counts
    require(np.isfinite(result).all(), "Nonfinite parcel mean")
    return result, counts


def demean(x):
    # Exact constant columns retain exact zero, including nonbinary decimals.
    mean = np.mean(x, axis=0)
    same = np.all(x == x[0], axis=0)
    mean = np.where(same, x[0], mean)
    return x - mean


def detrend(x):
    x = numeric(x, "detrend input")
    require(x.ndim == 2 and len(x) >= 2, "Need at least two frames")
    centered = demean(x)
    time = np.arange(len(x), dtype=np.float64)
    time -= time.mean()
    time /= np.linalg.norm(time)
    return centered - np.outer(time, time @ centered)


def clean_parcels(raw, confounds):
    raw, confounds = numeric(raw, "raw mean"), numeric(confounds, "confounds")
    require(raw.ndim == confounds.ndim == 2 and len(raw) == len(confounds), "Confound axes")
    require(len(raw) >= 2, "Insufficient frames")
    signals = detrend(raw)
    nuisance = demean(detrend(confounds))
    sd = np.sqrt(np.mean(nuisance * nuisance, axis=0))
    nuisance /= np.where(sd < EPS, 1.0, sd)
    q, r, _ = qr(nuisance, mode="economic", pivoting=True)
    keep = np.abs(np.diag(r)) > 100 * EPS
    basis = q[:, keep]
    residual = demean(signals - basis @ (basis.T @ signals))
    raw_sd = np.sqrt(np.sum(demean(raw) ** 2, axis=0) / (len(raw) - 1))
    residual_sd = np.sqrt(np.sum(residual ** 2, axis=0) / (len(raw) - 1))
    require(np.isfinite(raw_sd).all() and np.isfinite(residual_sd).all(), "Nonfinite source SD")
    require(np.all(residual_sd > 1e-12 * np.maximum(1.0, raw_sd)),
            "SOURCE_PRECONDITION_FAILURE: degenerate residual parcel")
    cleaned = residual / residual_sd
    require(np.isfinite(cleaned).all(), "Nonfinite standardized source")
    return cleaned, int(keep.sum()), raw_sd, residual_sd


def derived(cleaned, participant_ids, groups, parcel_ids, networks, method):
    cleaned = numeric(cleaned, "accepted standardized_clean")
    require(cleaned.ndim == 3 and cleaned.shape[0] == len(participant_ids)
            and cleaned.shape[2] == len(parcel_ids), "Clean axes")
    a, b = np.triu_indices(len(parcel_ids), 1)
    same_network = np.asarray(networks)[a] == np.asarray(networks)[b]
    n_within, n_between = int(same_network.sum()), int((~same_network).sum())
    require(n_within > 0 and n_between > 0, "Both pair families required")
    rows, all_r, all_z, all_positive = [], [], [], []
    for person, group, values in zip(participant_ids, groups, cleaned):
        values = demean(values)
        norm = np.linalg.norm(values, axis=0)
        require(np.isfinite(norm).all() and np.all(norm > 0), "Own cleaned vector degenerate")
        unit = values / norm
        correlations = (unit.T @ unit)[a, b]
        require(np.isfinite(correlations).all() and np.all(np.abs(correlations) <= 1 + 1e-12),
                "Pearson outside mathematical domain")
        correlations = np.clip(correlations, -1, 1)
        z = np.arctanh(np.clip(correlations, -0.999999, 0.999999))
        positive = np.maximum(z, 0)
        within = float(positive[same_network].sum())
        between = float(positive[~same_network].sum())
        w, between_mean = within / n_within, between / n_between
        numerator = w - between_mean
        ratio = None if w == 0 else numerator / w
        row = dict(participant_id=str(person), group=str(group), n_within_pairs=n_within,
                   n_between_pairs=n_between, within_sum=within, between_sum=between,
                   mean_within=w, mean_between=between_mean, numerator=numerator,
                   segregation=ratio, status="zero_within_mean" if ratio is None else "ok")
        finite_json(row)
        rows.append(row)
        all_r.append(correlations); all_z.append(z); all_positive.append(positive)
    return {"pearson_r": np.array(all_r), "fisher_z": np.array(all_z),
            "positive_z": np.array(all_positive), "segregation": rows,
            "results": summarize(rows, method)}


def summarize(rows, method):
    def one(items):
        vals = [r["segregation"] for r in items if r["segregation"] is not None]
        n, k = len(items), len(vals)
        require(n >= 2, "Group variance requires >=2 persons")
        if n != k:
            return dict(n=n, n_defined=k, n_undefined=n-k, mean=None,
                        sample_variance=None, status="undefined_member")
        x = np.asarray(vals, dtype=np.float64)
        mean = float(x[0] if np.all(x == x[0]) else x.mean())
        variance = float(np.sum((x - mean) ** 2) / (n - 1))
        return dict(n=n, n_defined=k, n_undefined=0, mean=mean,
                    sample_variance=variance, status="ok")
    cohort = one(rows)
    groups = {g: one([r for r in rows if r["group"] == g]) for g in ("child", "adult")}
    if any(g["status"] != "ok" for g in groups.values()):
        contrast = dict(estimate=None, se=None, ci95=None, status="undefined_member")
    else:
        c, a = groups["child"], groups["adult"]
        estimate = a["mean"] - c["mean"]
        se = math.sqrt(a["sample_variance"] / a["n"] + c["sample_variance"] / c["n"])
        contrast = dict(estimate=estimate, se=se,
                        ci95=[estimate-1.96*se, estimate+1.96*se], status="ok")
    result = dict(status="ok", task_id=method["task_id"], method_id=method["method_id"],
                  n_participants=len(rows), n_defined=cohort["n_defined"],
                  n_undefined=cohort["n_undefined"], cohort=cohort, groups=groups,
                  adult_minus_child=contrast)
    finite_json(result)
    return result


def source_table(path, delimiter="\t"):
    with regular(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), "Source headers")
        rows = list(reader)
    require(all(None not in r and None not in r.values() for r in rows), "Malformed source rows")
    return rows


def image_header(image, entry):
    spatial, temporal = image.header.get_xyzt_units()
    result = dict(source_path=entry["path"], shape=list(image.shape),
                  affine=image.affine.tolist(), storage_dtype=str(image.get_data_dtype()),
                  intensity_slope=float(image.dataobj.slope),
                  intensity_intercept=float(image.dataobj.inter),
                  zooms=[float(x) for x in image.header.get_zooms()], spatial_units=spatial,
                  temporal_units=temporal, qform_code=int(image.header["qform_code"]),
                  sform_code=int(image.header["sform_code"]))
    if entry["role"] == "bold":
        result["participant_id"] = entry["participant_id"]
    finite_json(result)
    return result


def verify_header(header, method, prefix):
    observed = method["source"]["observed_structure"]
    for name in ("shape", "affine", "storage_dtype", "spatial_units", "temporal_units",
                 "qform_code", "sform_code"):
        require(header[name] == observed[f"{prefix}_{name}"], f"Unexpected {prefix} {name}")
    if prefix == "bold":
        require(header["zooms"] == observed["bold_zooms"], "BOLD zoom mismatch")


def load_reference(source_dir=None, method_path=None):
    """Authenticate and reconstruct once; callers may share returned immutable basis.

    Each public call re-authenticates via the fixed stager. No accepted outputs
    or validation verdicts are cached. Tests can reuse one returned reference.
    """
    import nibabel as nib
    root = Path(source_dir or os.environ.get("REPAIR_SOURCE_DIR", "/app/data/netseg"))
    local_environment = Path(__file__).resolve().parents[1] / "environment"
    method_path = Path(method_path or os.environ.get("REPAIR_METHOD_PATH", "/app/method_contract.json"))
    if not method_path.exists() and method_path == Path("/app/method_contract.json"):
        method_path = local_environment / "method_contract.json"
    require(digest(method_path) == METHOD_SHA256, "Frozen method identity mismatch")
    method = read_json(method_path)
    helper = local_environment / "stage_data.py"
    if not helper.exists():
        helper = Path("/opt/source/stage_data.py")
    regular(helper)
    spec = importlib.util.spec_from_file_location("netseg_source_verifier", helper)
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    manifest = stage.verify_staged(root)
    entries = manifest["files"]
    require(len(entries) == method["source"]["n_files"], "Source entry count")
    def single(role, person=None):
        matches = [r for r in entries if r["role"] == role and r["participant_id"] == person]
        require(len(matches) == 1, f"Source role identity {role}/{person}")
        return matches[0]
    atlas_entry = single("atlas_image")
    atlas_image = nib.load(regular(root / atlas_entry["path"]))
    atlas_header = image_header(atlas_image, atlas_entry)
    verify_header(atlas_header, method, "atlas")
    atlas = atlas_image.get_fdata(dtype=np.float64)
    require(np.isfinite(atlas).all() and np.equal(atlas, np.floor(atlas)).all()
            and np.array_equal(np.unique(atlas), np.arange(101)), "Atlas label identity")
    shape = method["source"]["observed_structure"]["bold_shape"][:3]
    target_affine = method["source"]["observed_structure"]["bold_affine"]
    label_grid = nearest_labels(atlas, atlas_image.affine, shape, target_affine)
    native_count = np.bincount(atlas.astype(np.int64).ravel(), minlength=101)
    target_count = np.bincount(label_grid.ravel(), minlength=101)
    require(np.all(target_count[1:] > 0), "SOURCE_PRECONDITION_FAILURE: atlas coverage")
    lut_lines = regular(root / single("atlas_labels")["path"]).read_text().splitlines()
    parcels = []
    for row_index, line in enumerate(lut_lines):
        fields = line.split()
        require(len(fields) == 6, "Original LUT row")
        parcel_id = int(fields[0])
        tokens = fields[1].split("_")
        require(1 <= parcel_id <= 100 and tokens[0] == "7Networks" and
                tokens[1] in ("LH", "RH") and tokens[2] in method["geometry"]["network_names"], "LUT identity")
        parcels.append(dict(parcel_id=parcel_id, source_lut_row_index=row_index, label=fields[1],
                            hemisphere=tokens[1], network=tokens[2], native_voxel_count=int(native_count[parcel_id]),
                            target_voxel_count=int(target_count[parcel_id]), grid_id=method["geometry"]["grid_id"]))
    require(len(parcels) == 100 and {p["parcel_id"] for p in parcels} == set(range(1, 101)), "Complete LUT")
    parcels.sort(key=lambda x: x["parcel_id"])
    phenotype = source_table(root / single("participants")["path"])
    require(len(phenotype) == 155, "Full phenotype count")
    lookup = {row["participant_id"]: (i, row) for i, row in enumerate(phenotype)}
    require(len(lookup) == len(phenotype), "Duplicate source participant")
    ids = method["source"]["participant_ids"]
    people, headers, raw_all, clean_all, raw_sds, residual_sds = [], [], [], [], [], []
    columns = method["preprocessing"]["confound_columns"]
    for person in ids:
        source_index, row = lookup[person]
        group = row["Child_Adult"].strip().lower()
        age = float(row["Age"])
        require(group in ("child", "adult") and math.isfinite(age), "Source phenotype invalid")
        bold, confounds_entry = single("bold", person), single("confounds", person)
        image = nib.load(regular(root / bold["path"]))
        header = image_header(image, bold)
        verify_header(header, method, "bold")
        headers.append(header)
        confounds_rows = source_table(root / confounds_entry["path"])
        require(len(confounds_rows) == 168, "Confound row count")
        nuisance = numeric([[float(r[c]) for c in columns] for r in confounds_rows], "source confounds")
        data = image.get_fdata(dtype=np.float64)
        raw, _ = parcel_means(data, label_grid, np.arange(1, 101))
        del data, image
        clean, rank, raw_sd, residual_sd = clean_parcels(raw, nuisance)
        raw_all.append(raw); clean_all.append(clean); raw_sds.append(raw_sd); residual_sds.append(residual_sd)
        people.append(dict(participant_id=person, source_row_index=source_index, group=group, age=age,
                           bold_path=bold["path"], confounds_path=confounds_entry["path"], n_frames=168,
                           n_parcels=100, n_confounds=15, nuisance_rank=rank, grid_id=method["geometry"]["grid_id"]))
    counts = {g: sum(p["group"] == g for p in people) for g in ("child", "adult")}
    require(counts == method["source"]["cohort"]["group_counts"], "Source group counts")
    observed = dict(n_source_participants=155, n_selected_participants=40, n_frames=168,
                    n_parcels=100, group_counts=counts, bold_headers=headers, atlas_header=atlas_header,
                    selected_confound_columns=columns, tr_seconds_used=None)
    metadata = dict(status="ok", task_id=method["task_id"], method_id=method["method_id"],
                    source_manifest_sha256=digest(root / method["source"]["manifest_filename"]),
                    method_contract_sha256=METHOD_SHA256,
                    source_sha256={r["path"]: r["sha256"] for r in entries}, source_observed=observed)
    return dict(method=method, participants=people, parcels=parcels,
                participant_id=np.asarray(ids), parcel_id=np.arange(1, 101), frame_index=np.arange(168),
                raw_mean=np.array(raw_all), standardized_clean=np.array(clean_all),
                raw_sd=np.array(raw_sds), residual_sd=np.array(residual_sds), metadata=metadata)
