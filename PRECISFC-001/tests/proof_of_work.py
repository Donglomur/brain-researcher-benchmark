"""Source-bound, key-order-independent verifier for the disclosed MSC method.

No historical numerical bank is interpreted as the new source evidence. Exact
source primitives bind the submission; all derived results are recomputed from
its accepted ROI means under the explicitly published fidelity condition.
"""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

import qc_contract as q

BANK_SCHEMA = "precisfc-source-primitives-v2"
METHOD_SHA = "497b436132ee5723c3f7209489d77477fe2412ade1190f9aa95d0baf7bf9cda6"
SOURCE_SHA = "4f7fc73e548cfdf744fabbc382cebdd1edff968fe6edd7c1ca846958a1fbb967"
SUBJECTS = ("MSC01", "MSC02", "MSC05", "MSC06", "MSC08", "MSC09")
SESSIONS = ("func01", "func02", "func03")
PRIMITIVES = ("run_subject", "run_session", "roi_ids", "frame_indices", "tmask", "roi_means",
              "roi_source_peak_abs", "voxel_offsets", "voxel_ijk")
ARRAYS = PRIMITIVES + ("arm_names", "common_roi", "edge_roi_ids", "edge_valid", "raw_r", "fisher_z")
require = q.require


def regular_file(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), f"symlink path: {path.name}")
    require(path.is_file(), f"missing/nonregular file: {path.name}")
    return path


def sha256(path):
    h = hashlib.sha256()
    with regular_file(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pairs_hook(items):
    result = {}
    for k, v in items:
        require(k not in result, f"duplicate JSON key: {k}")
        result[k] = v
    return result


def json_text(text):
    def invalid(token):
        raise AssertionError(f"nonfinite JSON token: {token}")
    result = json.loads(text, object_pairs_hook=pairs_hook, parse_constant=invalid)
    def finite_tree(value):
        if isinstance(value, float):
            require(math.isfinite(value), "nonfinite JSON number, including descriptive extras")
        elif isinstance(value, dict):
            for item in value.values():
                finite_tree(item)
        elif isinstance(value, list):
            for item in value:
                finite_tree(item)
    finite_tree(result)
    return result


def read_json(path):
    return json_text(regular_file(path).read_text(encoding="utf-8"))


def integer(value):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not an integer ID/count")
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise AssertionError("invalid integer") from exc
    require(parsed.is_finite() and parsed == parsed.to_integral_value(), "nonintegral/nonfinite integer")
    return int(parsed)


def number(value):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not numeric")
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError("invalid numeric field") from exc
    require(math.isfinite(v), "nonfinite numeric field")
    return v


def flag(value):
    require(isinstance(value, str) and value.strip() in ("0", "1", "false", "true"), "invalid CSV Boolean")
    return value.strip() in ("1", "true")


def match(actual, expected, path="value", atol=0.0, rtol=0.0, closed=False):
    if expected is None:
        require(actual is None, f"{path}: expected null")
    elif isinstance(expected, bool):
        require(isinstance(actual, bool) and actual == expected, f"{path}: Boolean mismatch")
    elif isinstance(expected, (int, float, np.integer, np.floating)):
        require(isinstance(actual, (int, float, np.integer, np.floating)) and
                not isinstance(actual, (bool, np.bool_)), f"{path}: required JSON number")
        require(math.isfinite(actual), f"{path}: nonfinite number")
        if isinstance(expected, (int, np.integer)):
            require(integer(actual) == int(expected), f"{path}: integer mismatch")
        else:
            require(abs(actual - expected) <= atol + rtol * abs(expected), f"{path}: numeric mismatch")
    elif isinstance(expected, str):
        require(isinstance(actual, str) and actual == expected, f"{path}: string mismatch")
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f"{path}: missing object fields")
        if closed:
            require(set(actual) == set(expected), f"{path}: unexpected scientific fields")
        for key, value in expected.items():
            match(actual[key], value, f"{path}.{key}", atol, rtol, closed)
    elif isinstance(expected, (list, tuple)):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{path}: list shape")
        for i, (a, b) in enumerate(zip(actual, expected)):
            match(a, b, f"{path}[{i}]", atol, rtol, closed)
    else:
        raise AssertionError(f"unsupported reference type at {path}")


def read_csv(path, schema):
    with regular_file(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames
        require(headers and len(headers) == len(set(headers)) and all(headers), "missing/duplicate CSV headers")
        require(set(schema["columns"]) <= set(headers), f"{Path(path).name}: missing columns")
        rows = list(reader)
    require(rows, f"{Path(path).name}: empty CSV")
    for row in rows:
        require(None not in row and all(v is not None for v in row.values()), "malformed CSV row")
        for key in schema.get("integer_fields", []):
            row[key] = integer(row[key])
        for key in schema.get("boolean_fields", []):
            row[key] = flag(row[key])
    return keyed(rows, schema["key"])


def keyed(rows, fields):
    result = {}
    for row in rows:
        require(isinstance(row, dict) and all(k in row for k in fields), "missing key fields")
        key = tuple(row[k] for k in fields)
        require(key not in result, f"duplicate key: {key}")
        result[key] = row
    return result


def integral_array(array, name, boolean=False):
    x = np.asarray(array)
    if boolean and x.dtype.kind == "b":
        return x.astype(bool)
    require(x.dtype.kind in "iu", f"{name}: required integer array")
    if boolean:
        require(np.all((x == 0) | (x == 1)), f"{name}: nonbinary values")
        return x.astype(bool)
    # Do not permit unsigned wraparound during canonicalization.
    if x.dtype.kind == "u":
        require(not x.size or int(x.max()) <= np.iinfo(np.int64).max, f"{name}: integer overflow")
    return x.astype(np.int64)


def npz_arrays(path, names):
    with np.load(regular_file(path), allow_pickle=False) as archive:
        require(set(names) <= set(archive.files), "missing required NPZ arrays")
        require(len(archive.files) == len(set(archive.files)), "duplicate NPZ members")
        arrays = {}
        for key in archive.files:
            value = archive[key]
            require(value.dtype.kind != "O", "object NPZ array")
            if key in names:
                arrays[key] = value
    return arrays


def index_order(actual, expected, name):
    require(len(actual) == len(set(actual)), f"{name}: duplicate identity")
    require(set(actual) == set(expected), f"{name}: missing/foreign identity")
    lookup = {v: i for i, v in enumerate(actual)}
    return np.array([lookup[v] for v in expected], dtype=np.int64)


def canonical_arrays(arrays, ref, derived=True):
    a = {k: np.asarray(v) for k, v in arrays.items()}
    R, T, P = ref["roi_means"].shape
    for name in ("run_subject", "run_session") + (("arm_names",) if derived else ()):
        require(a[name].dtype.kind == "U" and a[name].ndim == 1, f"{name}: string axis")
    require(a["run_subject"].shape == a["run_session"].shape == (R,), "run axis shape")
    run_order = index_order(list(zip(a["run_subject"], a["run_session"])),
                            list(zip(ref["run_subject"], ref["run_session"])), "runs")
    for name in ("roi_ids", "frame_indices", "voxel_offsets", "voxel_ijk") + (("edge_roi_ids",) if derived else ()):
        a[name] = integral_array(a[name], name)
    require(a["roi_ids"].shape == (P,), "ROI axis shape")
    roi_order = index_order(list(a["roi_ids"]), list(ref["roi_ids"]), "ROIs")
    require(a["frame_indices"].shape == (R, T), "frame axis shape")
    frame_order = np.stack([index_order(list(a["frame_indices"][r]), list(range(T)), "frames") for r in run_order])
    a["tmask"] = integral_array(a["tmask"], "tmask", True)
    require(a["tmask"].shape == (R, T), "mask shape")
    for name, shape in (("roi_means", (R, T, P)), ("roi_source_peak_abs", (R, P))):
        require(a[name].dtype.kind == "f" and a[name].dtype.itemsize == 8 and a[name].shape == shape,
                f"{name}: required float64 shape")
        require(np.isfinite(a[name]).all(), f"{name}: nonfinite values")
    out = {"run_subject": ref["run_subject"], "run_session": ref["run_session"], "roi_ids": ref["roi_ids"],
           "frame_indices": np.tile(np.arange(T), (R, 1)),
           "tmask": a["tmask"][run_order[:, None], frame_order],
           "roi_means": a["roi_means"][run_order[:, None], frame_order][:, :, roi_order],
           "roi_source_peak_abs": a["roi_source_peak_abs"][run_order][:, roi_order]}
    require(np.array_equal(out["tmask"], ref["tmask"]), "source tmask mismatch")
    require((out["roi_source_peak_abs"] >= 0).all(), "negative source peak")
    require(np.all(np.abs(out["roi_source_peak_abs"] - ref["roi_source_peak_abs"]) <=
                   1e-10 * ref["roi_source_peak_abs"]), "source peak mismatch")
    offsets, ijk = a["voxel_offsets"], a["voxel_ijk"]
    require(offsets.shape == (P+1,) and offsets[0] == 0 and (np.diff(offsets) > 0).all(), "voxel offsets")
    require(ijk.ndim == 2 and ijk.shape[1] == 3 and offsets[-1] == len(ijk), "voxel array shape")
    for dest, origin in enumerate(roi_order):
        values = [tuple(v) for v in ijk[offsets[origin]:offsets[origin+1]]]
        expected = [tuple(v) for v in ref["voxel_ijk"][ref["voxel_offsets"][dest]:ref["voxel_offsets"][dest+1]]]
        require(len(values) == len(set(values)) and set(values) == set(expected), "source sphere membership mismatch")
    out.update(voxel_offsets=ref["voxel_offsets"], voxel_ijk=ref["voxel_ijk"])
    q.validate_fidelity(out["roi_means"], ref["roi_means"], ref["roi_source_peak_abs"], ref["tmask"])
    if not derived:
        return out
    arm_order = index_order(list(a["arm_names"]), list(q.ARMS), "arms")
    edges = list(map(tuple, a["edge_roi_ids"])) if a["edge_roi_ids"].ndim == 2 else []
    expected_edges = [(int(x), int(y)) for j, x in enumerate(ref["roi_ids"]) for y in ref["roi_ids"][j+1:]]
    require(a["edge_roi_ids"].shape == (len(expected_edges), 2), "edge axis shape")
    edge_order = index_order(edges, expected_edges, "edges")
    a["common_roi"] = integral_array(a["common_roi"], "common_roi", True)
    a["edge_valid"] = integral_array(a["edge_valid"], "edge_valid", True)
    require(a["common_roi"].shape == (P,) and a["edge_valid"].shape == (len(edges),), "support shape")
    out.update(arm_names=np.array(q.ARMS), common_roi=a["common_roi"][roi_order],
               edge_roi_ids=np.array(expected_edges), edge_valid=a["edge_valid"][edge_order])
    for name in ("raw_r", "fisher_z"):
        require(a[name].dtype.kind == "f" and a[name].dtype.itemsize == 8 and
                a[name].shape == (R, 2, len(edges)), f"{name}: required float64 shape")
        values = a[name][run_order][:, arm_order][:, :, edge_order]
        valid = out["edge_valid"]
        require(np.isfinite(values[:, :, valid]).all() and np.isnan(values[:, :, ~valid]).all(),
                f"{name}: invalid finite/NaN support")
        bound = 1 if name == "raw_r" else float(np.arctanh(.999))
        require(np.all(np.abs(values[:, :, valid]) <= bound), f"{name}: mathematical domain")
        out[name] = values
    return out


def load_reference(path=None):
    path = Path(path or os.environ.get("REPAIR_REFERENCE_PATH", Path(__file__).with_name("reference.npz")))
    with np.load(regular_file(path), allow_pickle=False) as archive:
        require("bank_schema" in archive.files and str(archive["bank_schema"]) == BANK_SCHEMA,
                "obsolete or untrusted reference bank")
        metadata = json_text(str(archive["metadata_json"]))
        geometry = json_text(str(archive["geometry_json"]))
        ref = {k: archive[f"ref_{k}"] for k in PRIMITIVES}
    require(metadata["method_contract_sha256"] == METHOD_SHA and metadata["source_manifest_sha256"] == SOURCE_SHA,
            "reference provenance pins")
    method = metadata["method_contract"]
    require(method["pipeline_id"] == q.PIPELINE and method["source"]["source_manifest_sha256"] == SOURCE_SHA,
            "reference method/source mismatch")
    local = Path(__file__).parents[1] / "environment"
    method_path = local / "method_contract.json"
    if not method_path.exists():
        method_path = Path("/app/method_contract.json")
    manifest_path = local / "source_manifest.json"
    if not manifest_path.exists():
        manifest_path = Path("/app/data/precisfc/source_manifest.json")
    require(sha256(method_path) == METHOD_SHA and sha256(manifest_path) == SOURCE_SHA,
            "public frozen method/manifest changed")
    match(method, read_json(method_path), "bank frozen contract", closed=True)
    manifest = read_json(manifest_path)
    require(ref["roi_means"].shape == (18, 818, 264), "incomplete source bank")
    require(list(zip(ref["run_subject"], ref["run_session"])) == [(s, t) for s in SUBJECTS for t in SESSIONS],
            "incomplete bank run identities")
    require(np.array_equal(ref["roi_ids"], np.arange(1, 265)), "bank ROI identities")
    canonical_arrays(ref, ref, derived=False)
    source_fields = method["outputs"]["run_metadata.json"]["source_files"]["required_fields"]
    expected_files = []
    for record in manifest["files"]:
        if record["role"] in ("bold", "tmask"):
            values = dict(record, subject_id=record["subject"], session_id=record["session"])
            expected_files.append({k: values[k] for k in source_fields})
    actual_files = keyed(metadata["source_files"], ("subject_id", "session_id", "role"))
    expected_files = keyed(expected_files, ("subject_id", "session_id", "role"))
    require(set(actual_files) == set(expected_files) and len(actual_files) == 36, "bank source identity coverage")
    for key in expected_files:
        match(actual_files[key], expected_files[key], "bank source identity")
    observed = metadata["source_observed"]
    match({k: observed.get(k) for k in ("n_subjects", "n_runs", "n_original_files", "original_files_modified")},
          dict(n_subjects=6, n_runs=18, n_original_files=36, original_files_modified=False), "bank source counts")
    match(observed["timing_policy"], method["timing"], "bank timing", closed=True)
    headers = keyed(observed["headers"], ("subject_id", "session_id"))
    require(set(headers) == {(s, t) for s in SUBJECTS for t in SESSIONS}, "bank header identities")
    for row in headers.values():
        for field, value in method["source"]["expected_header"].items():
            if field == "description_required_suffix":
                require(isinstance(row.get("description"), str) and row["description"].endswith(value), "bank source description")
            else:
                require(field in row, f"missing bank header {field}")
                if field in ("sform", "spatial_zooms_mm"):
                    value = np.asarray(value, dtype=float).tolist()
                match(row[field], value, field, 1e-9 if field in ("sform", "spatial_zooms_mm") else 0)
    require(len(geometry) == 264 and {r["roi_id"] for r in geometry} == set(range(1, 265)), "bank geometry")
    ref.update(metadata=metadata, geometry=geometry, method=method)
    return ref


def table_match(path, expected_rows, schema, ref, derived):
    actual = read_csv(path, schema)
    expected = keyed(expected_rows, schema["key"])
    require(set(actual) == set(expected), f"{Path(path).name}: incomplete/foreign keys")
    run_lookup = {tuple(k): i for i, k in enumerate(zip(ref["run_subject"], ref["run_session"]))}
    roi_lookup = {int(k): i for i, k in enumerate(ref["roi_ids"])}
    for key, expected_row in expected.items():
        row = actual[key]
        for field in schema["columns"]:
            b, a = expected_row[field], row[field]
            if field in schema.get("integer_fields", []) or field in schema.get("boolean_fields", []):
                match(a, b, field)
            elif b is None:
                require(a == "", f"{field}: undefined numeric must be blank")
            elif isinstance(b, str):
                match(a, b, field)
            else:
                a = number(a)
                atol, rtol = 1e-9, 0.0
                if field in ("raw_l2", "centered_l2", "zero_bound"):
                    run = run_lookup[(row["subject_id"], row["session_id"])]
                    scale = ref["roi_source_peak_abs"][run, roi_lookup[row["roi_id"]]]
                    atol, rtol = 1e-10 * scale * math.sqrt(row["n_frames"]), 1e-9
                    require(a >= 0, "negative norm/bound")
                elif field.startswith(("raw_l2_", "centered_l2_", "zero_bound_")):
                    session = row["session_" + field[-1]]
                    run = run_lookup[(row["subject_id"], session)]
                    arm = q.ARMS.index(row["arm"])
                    values = derived["fisher_z"][run, arm, derived["edge_valid"]]
                    scale = float(np.max(np.abs(values))) if values.size else 0.0
                    atol, rtol = 1e-10 * scale * math.sqrt(row["n_common_edges"]), 1e-9
                    require(a >= 0, "negative pair norm/bound")
                elif field == "pair_r":
                    require(abs(a) <= 1, "pair correlation domain")
                    atol, rtol = 1e-8, 1e-7
                elif field.startswith("reliability_"):
                    require(abs(a) <= 1, "reliability domain")
                    atol = 1e-6
                elif field in ("header_tr_seconds", "analysis_tr_seconds", "radius_mm"):
                    atol = 0.0
                elif field == "boundary_min_abs_mm2":
                    require(a >= 0, "negative squared boundary distance")
                match(a, b, field, atol, rtol)


def normalize_status_counts(value, statuses):
    require(isinstance(value, dict) and set(value) <= set(statuses), "unknown status counter")
    result = {s: value.get(s, 0) for s in statuses}
    for n in result.values():
        require(isinstance(n, (int, float)) and not isinstance(n, bool) and integer(n) >= 0,
                "invalid status count")
    return result


def match_summary(actual, expected):
    require(isinstance(actual, dict) and set(expected) <= set(actual), "missing summary fields")
    for key, value in expected.items():
        if key in ("roi_status_counts", "pair_status_counts"):
            statuses = q.ROI_STATUSES if key == "roi_status_counts" else q.PAIR_STATUSES
            match(normalize_status_counts(actual[key], statuses), normalize_status_counts(value, statuses), key, closed=True)
        elif key in ("qc_included_subject_ids", "qc_excluded_subject_ids"):
            require(isinstance(actual[key], list) and len(actual[key]) == len(set(actual[key])) and
                    set(actual[key]) == set(value), f"{key}: QC identities")
        elif key == "group_mean_reliability":
            require(isinstance(actual[key], dict) and set(actual[key]) == set(value), "group population identities")
            for group_id, group_value in value.items():
                if group_value["value"] is not None:
                    require(abs(number(actual[key][group_id]["value"])) <= 1, "group coefficient domain")
                match(actual[key][group_id], group_value, group_id, 1e-6)
        else:
            match(actual[key], value, key)


def validate_metadata(actual, ref, stats):
    expected = ref["metadata"]
    for name in ("status", "pipeline_id", "method_contract_sha256", "source_manifest_sha256"):
        require(name in actual, f"missing metadata {name}")
        match(actual[name], "ok" if name == "status" else expected[name], name)
    match(actual.get("method_contract"), expected["method_contract"], "method_contract", closed=True)
    keys = ("subject_id", "session_id", "role")
    source_a, source_b = keyed(actual.get("source_files", []), keys), keyed(expected["source_files"], keys)
    require(set(source_a) == set(source_b), "metadata source file identities")
    for key in source_b:
        match(source_a[key], source_b[key], "source_files")
    observed = actual.get("source_observed")
    require(isinstance(observed, dict), "missing source observations")
    for key, value in expected["source_observed"].items():
        require(key in observed, f"missing source_observed {key}")
        if key == "headers":
            a, b = keyed(observed[key], ("subject_id", "session_id")), keyed(value, ("subject_id", "session_id"))
            require(set(a) == set(b), "header identities")
            for run in b:
                for field, val in b[run].items():
                    require(field in a[run], f"missing header {field}")
                    if field in ("sform", "spatial_zooms_mm"):
                        val = np.asarray(val, dtype=float).tolist()
                    match(a[run][field], val, field, 1e-9 if field in ("sform", "spatial_zooms_mm") else 0.0)
        else:
            match(observed[key], value, f"source_observed.{key}", closed=key == "timing_policy")
    analysis = actual.get("analysis_observed")
    required = ref["method"]["outputs"]["run_metadata.json"]["analysis_observed"]["required_fields"]
    match_summary(analysis, {k: stats[k] for k in required})
    versions = actual.get("software_versions")
    require(isinstance(versions, dict) and {"python", "numpy", "nibabel"} <= set(versions), "missing software versions")
    require(all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in versions.items()),
            "invalid software version declaration")


def validate_output_directory(directory, reference=None):
    root = Path(directory)
    ref = reference if isinstance(reference, dict) else load_reference(reference)
    method = ref["method"]
    for name in method["serialization"]["required_files"]:
        regular_file(root / name)
    require((root / "findings.md").read_text(encoding="utf-8").strip(), "empty findings")
    arrays = canonical_arrays(npz_arrays(root / "connectivity_arrays.npz", ARRAYS), ref)
    own = q.derive(arrays)
    for name in ("common_roi", "edge_valid"):
        require(np.array_equal(arrays[name], own[name]), f"{name}: inconsistent own-primitive support")
    for name in ("raw_r", "fisher_z"):
        valid = own["edge_valid"]
        require(np.allclose(arrays[name][:, :, valid], own[name][:, :, valid], atol=1e-8, rtol=1e-7),
                f"{name}: differs from recomputed ROI-mean FC")
    table_match(root / "roi_geometry.csv", ref["geometry"], method["outputs"]["roi_geometry.csv"], ref, own)
    for name in ("session_qc", "roi_status", "session_pairs", "reliability"):
        table_match(root / f"{name}.csv", own[name], method["outputs"][f"{name}.csv"], ref, own)
    match_summary(read_json(root / "reliability_stats.json"), own["stats"])
    validate_metadata(read_json(root / "run_metadata.json"), ref, own["stats"])
    return own
