"""Source-bound VISCAT verifier, not proof of execution or biological validity."""
from __future__ import annotations

import os
import numpy as np
import category_statistics as stats
import io_contract as io
import population_contract as population
from source_reference import load_reference

require = io.require
INTEGER_ARRAYS = ("response_unit_index", "source_trial_row", "trial_id", "category_code", "spike_count", "repeat_id")
ARRAY_FIELDS = ("unit_key", *INTEGER_ARRAYS, "rate_hz", "train_membership")
CLOSED_OBJECTS = {"source_sha256", "method_contract", "populations", "population_overlap",
                  "phase_experiment_ids", "clock_mapping_counts", "label_membership_counts", "unit_electrode_link_counts"}


def tolerance(name):
    if name.endswith("_time_s"): return 1e-9, 0
    if name in ("kw_p", "train_p"): return 1e-10, 1e-7
    if name in ("kw_H", "train_H"): return 1e-10, 1e-8
    return 1e-8, 0


def compare_number(value, expected, name, exact=False):
    value = io.number(value)
    a, r = (0, 0) if exact else tolerance(name)
    require(abs(value-expected) <= a+r*abs(expected), f"{name}: numerical mismatch")
    if name in ("kw_p", "train_p") or "auc" in name or "proportion" in name:
        require(0 <= value <= 1, f"{name}: probability domain")
    elif "mean_rate" in name or name in ("rate_hz", "kw_H", "train_H"):
        require(value >= 0, f"{name}: nonnegative domain")


def compare_cell(value, expected, name):
    if expected is None: require(value == "", f"{name}: expected blank undefined field")
    elif type(expected) is bool: require(io.flag(value) == expected, f"{name}: Boolean mismatch")
    elif type(expected) is int: require(io.integer(value) == expected, f"{name}: integer mismatch")
    elif type(expected) is float: compare_number(value, expected, name)
    else: require(value == expected, f"{name}: literal identity mismatch")


def validate_table(path, expected_rows, schema):
    rows = io.csv_load(path, schema["columns"])
    expected = {tuple(row[k] for k in schema["keys"]): row for row in expected_rows}
    require(len(expected) == len(expected_rows), "Invalid authoring table identity")
    kinds = {key: type(expected_rows[0][key]) if expected_rows else str for key in schema["keys"]}
    actual = {}
    for row in rows:
        key = tuple(io.integer(row[k]) if kinds[k] is int else row[k] for k in schema["keys"])
        require(key not in actual, "Duplicate CSV identity"); actual[key] = row
    require(set(actual) == set(expected), "Missing/extra CSV identities")
    for key, wanted in expected.items():
        for name in schema["columns"]: compare_cell(actual[key][name], wanted[name], name)


def match_json(actual, expected, name="root", exact=False, closed=False):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f"{name}: missing JSON fields")
        if closed or exact or name in CLOSED_OBJECTS:
            require(set(actual) == set(expected), f"{name}: unexpected scientific identity fields")
        for key, value in expected.items():
            match_json(actual[key], value, key, exact=exact or name in ("method_contract", "source_sha256"), closed=name == "populations")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{name}: list coverage mismatch")
        if name in ("sessions", "category_mapping"):
            key_name = "asset_path" if name == "sessions" else "category_code"
            def keyed(rows):
                result = {}
                for row in rows:
                    require(isinstance(row, dict) and key_name in row, "Missing record identity")
                    key = row[key_name]
                    if key_name == "category_code":
                        require(type(key) in (int, float), "JSON category identity must be numeric"); key = io.integer(key)
                    else: require(type(key) is str, "JSON source identity must be string")
                    require(key not in result, "Duplicate JSON record identity"); result[key] = row
                return result
            a, e = keyed(actual), keyed(expected)
            require(set(a) == set(e), "JSON record coverage mismatch")
            for key in e: match_json(a[key], e[key], name+"_record", exact=exact, closed=name == "category_mapping")
        else:
            for a, e in zip(actual, expected): match_json(a, e, name, exact=exact)
    elif expected is None: require(actual is None, f"{name}: expected null")
    elif type(expected) is bool: require(type(actual) is bool and actual == expected, f"{name}: Boolean mismatch")
    elif type(expected) is int:
        require(type(actual) in (int, float) and io.integer(actual) == expected, f"{name}: integer mismatch")
    elif type(expected) is float:
        require(type(actual) in (int, float), f"{name}: JSON numeric type"); compare_number(actual, expected, name, exact)
    else: require(type(actual) is type(expected) and actual == expected, f"{name}: literal mismatch")


def validate_arrays(path, ref):
    expected = ref["arrays"]
    with np.load(io.regular(path), allow_pickle=False) as z:
        require(len(z.files) == len(set(z.files)), "Duplicate NPZ members")
        require(set(ARRAY_FIELDS) <= set(z.files), "Missing response primitive array")
        actual = {name: z[name] for name in z.files}
    require(all(a.dtype.kind != "O" for a in actual.values()), "Object array forbidden")
    for a in actual.values():
        if a.dtype.kind in "fc": require(np.isfinite(a).all(), "Nonfinite NPZ array")
    unit_keys = actual["unit_key"]
    require(unit_keys.ndim == 1 and unit_keys.dtype.kind == "U", "Unicode unit-key axis required")
    keys = unit_keys.tolist()
    require(len(keys) == len(set(keys)) and set(keys) == set(expected["unit_key"].tolist()), "Unit-key axis mismatch")
    for name in INTEGER_ARRAYS: actual[name] = stats.integers(actual[name], name)
    index, n = actual["response_unit_index"], len(expected["spike_count"])
    require(len(index) == n and all(actual[name].shape == (n,) for name in INTEGER_ARRAYS if name != "repeat_id"), "Response shape mismatch")
    require(not len(index) or (index.min() >= 0 and index.max() < len(keys)), "Response unit index outside axis")
    repeated = actual["repeat_id"].tolist()
    require(len(repeated) == len(set(repeated)) == 50 and set(repeated) == set(range(50)), "Repeat axis mismatch")
    require(actual["train_membership"].dtype.kind == "b" and actual["train_membership"].shape == (50, n), "Boolean membership matrix required")
    rate = actual["rate_hz"]
    require(rate.dtype.kind == "f" and rate.shape == (n,) and np.isfinite(rate).all() and np.all(rate >= 0), "Invalid rate array")
    by_key = {}
    for pos, (unit_index, row) in enumerate(zip(index, actual["source_trial_row"])):
        key = (keys[int(unit_index)], int(row))
        require(key not in by_key, "Duplicate response identity"); by_key[key] = pos
    expected_keys = [(str(expected["unit_key"][int(i)]), int(row)) for i, row in zip(expected["response_unit_index"], expected["source_trial_row"])]
    require(set(by_key) == set(expected_keys), "Missing/extra source response identity")
    order = np.asarray([by_key[key] for key in expected_keys], dtype=np.int64)
    for name in ("source_trial_row", "trial_id", "category_code", "spike_count"):
        require(np.array_equal(actual[name][order], expected[name]), f"Source {name} mismatch")
    require(np.all(np.abs(rate[order]-expected["spike_count"]/1.5) <= 1e-8), "Source rate mismatch")
    repeat_order = np.asarray([repeated.index(r) for r in range(50)])
    require(np.array_equal(actual["train_membership"][np.ix_(repeat_order, order)], expected["train_membership"]), "Source train membership mismatch")
    return expected


def validate_metadata(value, ref, headline):
    required = ref["method"]["outputs"]["run_metadata.json"]["required_fields"]
    require(isinstance(value, dict) and set(required) <= set(value), "Missing metadata fields")
    expected = dict(ref["metadata"], headline_population=headline)
    for key in ("software_versions", "warnings"): expected.pop(key)
    match_json(value, expected)
    versions = value["software_versions"]
    require(isinstance(versions, dict) and bool(versions) and all(type(k) is str and k and type(v) is str and v for k, v in versions.items()), "Actual nonempty software version string map required")
    require(isinstance(value["warnings"], list) and all(type(w) is str and w for w in value["warnings"]), "Warning string array required")


def validate_output_directory(output, ref=None, *, allow_pilot=False):
    root = io.safe_path(output)
    require(root.is_dir(), "Output directory required")
    require(not os.path.lexists(root/"failure_report.json"), "Authoritative failure_report.json present")
    if ref is None: ref = load_reference()
    require(allow_pilot or ref["metadata"]["status"] == "complete", "Pilot is not a complete grading basis")
    schemas = ref["method"]["outputs"]
    for filename in schemas: io.regular(root/filename)
    require((root/"findings.md").read_text(encoding="utf-8").strip(), "Empty findings")
    for filename, name in (("sessions.csv", "sessions"), ("trials.csv", "trials"), ("units.csv", "units")):
        validate_table(root/filename, ref[name], schemas[filename])
    validate_arrays(root/"responses.npz", ref)
    # Exact accepted primitive identity is the cache key, not rounded p/AUC reports.
    derived = population.analyze(ref)
    for filename, name in (("neurons.csv", "neurons"), ("split_events.csv", "split_events")):
        validate_table(root/filename, derived[name], schemas[filename])
    result = io.json_load(root/"results.json")
    require(isinstance(result, dict) and result.get("headline_population") in population.POPULATIONS, "Invalid headline")
    match_json(result, population.summarize(ref, derived["neurons"], result["headline_population"]))
    validate_metadata(io.json_load(root/"run_metadata.json"), ref, result["headline_population"])
    return dict(n_sessions=len(ref["sessions"]), n_mtl_units=len(ref["arrays"]["unit_key"]),
                n_response_rows=len(ref["arrays"]["spike_count"]), n_split_events=len(derived["split_events"]))
