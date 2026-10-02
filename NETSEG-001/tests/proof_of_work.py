"""Source-bound, own-primitive NETSEG verification; no hidden outcome target."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import math
import os
from pathlib import Path
import stat

import numpy as np
import source_math as s

require = s.require
load_reference = s.load_reference
LIMIT = np.arctanh(0.999999)


def integer(value):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not an integer")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AssertionError("Invalid integer") from None
    require(d.is_finite() and -(2**63) <= d < 2**63 and d == d.to_integral_value(),
            "Nonintegral or out-of-range integer")
    return int(d)


def number(value):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not a number")
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        raise AssertionError("Invalid finite number") from None
    require(math.isfinite(x), "Nonfinite number")
    return x


def int_axis(values, name):
    a = np.asarray(values)
    require(a.ndim == 1 and a.dtype.kind in "iuf", f"{name}: integer axis required")
    if a.dtype.kind == "f":
        require(np.isfinite(a).all() and np.all(a == np.floor(a)) and
                np.all(a >= -(2**63)) and np.all(a < 2**63), f"{name}: invalid integer")
    elif a.dtype.kind == "u":
        require(np.all(a < 2**63), f"{name}: uint overflow")
    a = a.astype(np.int64)
    require(len(set(a.tolist())) == len(a), f"{name}: duplicate key")
    return a


def strings(values, name):
    a = np.asarray(values)
    require(a.ndim == 1 and a.dtype.kind in "US", f"{name}: string axis required")
    result = [v.decode("utf-8") if isinstance(v, bytes) else str(v) for v in a.tolist()]
    require(all(result) and len(set(result)) == len(result), f"{name}: duplicate/empty key")
    return result


def close(actual, expected, tolerance, name):
    a, b = s.numeric(actual, name), s.numeric(expected, name)
    require(a.shape == b.shape, f"{name}: shape mismatch")
    require(np.all(np.abs(a-b) <= tolerance["atol"] + tolerance["rtol"] * np.abs(b)),
            f"{name}: numerical mismatch")


def match(actual, expected, tolerance, name="JSON", closed=False):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f"{name}: required keys")
        if closed:
            require(set(expected) == set(actual), f"{name}: unexpected identity")
        for k, v in expected.items():
            match(actual[k], v, tolerance, f"{name}.{k}", closed)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{name}: list")
        for i, (a, b) in enumerate(zip(actual, expected)):
            match(a, b, tolerance, f"{name}[{i}]", closed)
    elif expected is None or isinstance(expected, (str, bool)):
        require(type(actual) is type(expected) and actual == expected, f"{name}: value/type")
    elif isinstance(expected, int):
        require(type(actual) in (int, float) and math.isfinite(actual) and
                actual == expected, f"{name}: exact integer")
    else:
        require(type(actual) in (int, float), f"{name}: JSON numeric type")
        close(actual, expected, tolerance, name)


def table(path, fields, key):
    with s.regular(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames))
                and set(fields) <= set(reader.fieldnames), f"{path.name}: headers")
        rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), f"{path.name}: malformed rows")
    keyed = {}
    for row in rows:
        value = integer(row[key]) if key == "parcel_id" else row[key]
        require(value not in keyed, f"{path.name}: duplicate key")
        keyed[value] = row
    return keyed


def table_match(rows, expected, key, tolerance, name):
    source = {r[key]: r for r in expected}
    require(set(rows) == set(source), f"{name}: complete key coverage")
    for k, ref in source.items():
        row = rows[k]
        for field, value in ref.items():
            actual = row[field]
            if value is None:
                require(actual == "", f"{name}.{field}: undefined must be blank")
            elif isinstance(value, str):
                require(actual == value, f"{name}.{field}: exact source/category")
            elif isinstance(value, int):
                require(integer(actual) == value, f"{name}.{field}: exact integer")
            else:
                close(number(actual), value, tolerance, f"{name}.{field}")


def permutation(actual, expected, name):
    actual, expected = list(actual), list(expected)
    require(len(actual) == len(expected) and set(actual) == set(expected), f"{name}: complete axis")
    lookup = {v: i for i, v in enumerate(actual)}
    require(len(lookup) == len(actual), f"{name}: duplicate axis")
    return [lookup[v] for v in expected]


def canonical_arrays(path, reference):
    method = reference["method"]
    with np.load(s.regular(path), allow_pickle=False) as z:
        require(len(z.files) == len(set(z.files)), "Duplicate NPZ member names")
        require(set(method["artifacts"]["connectivity.npz"]["arrays"]) <= set(z.files), "Missing NPZ arrays")
        arrays = {k: z[k] for k in z.files}
    require(all(a.dtype.kind != "O" for a in arrays.values()), "Object NPZ array")
    people = strings(arrays["participant_id"], "participant_id")
    frames = int_axis(arrays["frame_index"], "frame_index")
    parcels = int_axis(arrays["parcel_id"], "parcel_id")
    def endpoint(v, name):
        a = np.asarray(v)
        require(a.ndim == 1 and a.dtype.kind in "iuf", f"{name}: numeric axis")
        return np.array([integer(x) for x in a], dtype=np.int64)
    ei, ej = endpoint(arrays["edge_i"], "edge_i"), endpoint(arrays["edge_j"], "edge_j")
    require(ei.shape == ej.shape and np.all(ei < ej), "Edge orientation")
    source_ids = list(reference["parcel_id"])
    expected_edges = [(int(x), int(y)) for i, x in enumerate(source_ids) for y in source_ids[i+1:]]
    edge_order = permutation(list(zip(ei.tolist(), ej.tolist())), expected_edges, "edges")
    pi = permutation(people, reference["participant_id"].tolist(), "people")
    fi = permutation(frames.tolist(), reference["frame_index"].tolist(), "frames")
    ri = permutation(parcels.tolist(), source_ids, "parcels")
    n, t, r, e = len(people), len(frames), len(parcels), len(expected_edges)
    out = {}
    for k in ("raw_mean", "standardized_clean"):
        a = s.numeric(arrays[k], k)
        require(a.shape == (n, t, r), f"{k}: full tensor shape")
        out[k] = a[np.ix_(pi, fi, ri)]
    for k in ("raw_sd", "residual_sd"):
        a = s.numeric(arrays[k], k)
        require(a.shape == (n, r) and np.all(a >= 0), f"{k}: shape/domain")
        if k == "residual_sd":
            require(np.all(a > 0), "Residual SD receipt must be positive")
        out[k] = a[np.ix_(pi, ri)]
    for k in ("pearson_r", "fisher_z", "positive_z"):
        a = s.numeric(arrays[k], k)
        require(a.shape == (n, e), f"{k}: full edge matrix")
        out[k] = a[np.ix_(pi, edge_order)]
    require(np.all(np.abs(out["pearson_r"]) <= 1), "Pearson domain")
    cap = LIMIT + method["tolerances"]["derived"]["atol"] + method["tolerances"]["derived"]["rtol"] * LIMIT
    require(np.all(np.abs(out["fisher_z"]) <= cap), "Fisher domain")
    require(np.all((out["positive_z"] >= 0) & (out["positive_z"] <= cap)), "Positive-z domain")
    return out


def validate_metadata(meta, reference):
    s.finite_json(meta)
    expected = reference["metadata"]
    tolerance = reference["method"]["tolerances"]["source_scalar_metadata"]
    require(isinstance(meta, dict) and set(expected) <= set(meta), "Required metadata")
    for k in ("status", "task_id", "method_id", "source_manifest_sha256", "method_contract_sha256"):
        match(meta[k], expected[k], tolerance, k)
    match(meta["source_sha256"], expected["source_sha256"], tolerance, "source_sha256", closed=True)
    observed, ref = meta["source_observed"], expected["source_observed"]
    require(isinstance(observed, dict) and set(ref) <= set(observed), "Source observations")
    for k, value in ref.items():
        if k != "bold_headers":
            match(observed[k], value, tolerance, f"source_observed.{k}", closed=k == "group_counts")
    headers = observed["bold_headers"]
    require(isinstance(headers, list) and all(isinstance(h, dict) and "participant_id" in h for h in headers),
            "BOLD header records")
    ids = [h["participant_id"] for h in headers]
    require(all(isinstance(k, str) for k in ids) and len(set(ids)) == len(ids), "Duplicate BOLD header")
    keyed = dict(zip(ids, headers))
    require(set(keyed) == {h["participant_id"] for h in ref["bold_headers"]}, "Header coverage")
    for h in ref["bold_headers"]:
        match(keyed[h["participant_id"]], h, tolerance, "source BOLD header")
    require(isinstance(meta.get("warnings"), list), "warnings must be a list")
    versions = meta.get("software_versions")
    require(isinstance(versions, dict) and versions and
            all(isinstance(k, str) and k for k in versions), "software_versions must be a nonempty object")


def validate_results(result, expected, method):
    match(result, expected, method["tolerances"]["derived"], "cohort_results")
    require(set(result["groups"]) == {"child", "adult"}, "Closed group identities")
    for item in [result["cohort"], *result["groups"].values()]:
        if item["mean"] is not None:
            require(number(item["mean"]) <= 1 and number(item["sample_variance"]) >= 0, "Group natural domain")
    contrast = result["adult_minus_child"]
    if contrast["se"] is not None:
        require(number(contrast["se"]) >= 0 and contrast["ci95"][0] <= contrast["ci95"][1], "Contrast domain")


def validate_output_directory(output, reference):
    output = Path(output).absolute()
    require(not os.path.lexists(output / "failure_receipt.json"), "Reserved failure_receipt.json is authoritative")
    for node in (output, *output.parents):
        require(not node.is_symlink(), f"Output symlink: {node}")
    require(stat.S_ISDIR(output.stat().st_mode), "Output directory required")
    method = reference["method"]
    for filename in method["artifacts"]:
        s.regular(output / filename)
    participants = table(output / "participants.csv", method["artifacts"]["participants.csv"]["columns"], "participant_id")
    parcels = table(output / "parcels.csv", method["artifacts"]["parcels.csv"]["columns"], "parcel_id")
    table_match(participants, reference["participants"], "participant_id", method["tolerances"]["source_scalar_metadata"], "participants")
    table_match(parcels, reference["parcels"], "parcel_id", method["tolerances"]["source_scalar_metadata"], "parcels")
    arrays = canonical_arrays(output / "connectivity.npz", reference)
    for name in ("raw_mean", "raw_sd", "residual_sd"):
        close(arrays[name], reference[name], method["tolerances"]["raw_receipt"], f"source {name}")
    close(arrays["standardized_clean"], reference["standardized_clean"],
          method["tolerances"]["standardized_clean_source"], "source standardized_clean")
    # Receipt rounding never redefines canonical source support.
    own = s.derived(arrays["standardized_clean"], reference["participant_id"],
                    [p["group"] for p in reference["participants"]], reference["parcel_id"],
                    [p["network"] for p in reference["parcels"]], method)
    for name in ("pearson_r", "fisher_z", "positive_z"):
        close(arrays[name], own[name], method["tolerances"]["derived"], f"own {name}")
    rows = table(output / "segregation.csv", method["artifacts"]["segregation.csv"]["columns"], "participant_id")
    table_match(rows, own["segregation"], "participant_id", method["tolerances"]["derived"], "own segregation")
    for row in rows.values():
        for field in ("within_sum", "between_sum", "mean_within", "mean_between"):
            require(number(row[field]) >= 0, f"{field}: negative")
        if row["segregation"] != "":
            require(number(row["segregation"]) <= 1, "Segregation exceeds 1")
    result = s.read_json(output / "cohort_results.json")
    validate_results(result, own["results"], method)
    validate_metadata(s.read_json(output / "run_metadata.json"), reference)
    require((output / "findings.md").read_text(encoding="utf-8").strip(), "Empty findings")
    return {"n_participants": len(participants), "n_parcels": len(parcels),
            "n_defined": own["results"]["n_defined"], "n_undefined": own["results"]["n_undefined"]}
