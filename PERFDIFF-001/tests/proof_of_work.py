"""Strict IVIM receipt parsing; numerical agreement is not perfusion truth."""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "ivim-explicit-qc-v2"
DATASET_ID = "ivim-figshare-3395704-v1"
METHODS = ("trr_explicit", "segmented_b200")
PARAMETERS = ("S0", "f", "Dstar", "D")
FLAGS = ("init_projected", "fallback", "eligible", "common_valid", "component_swap")
STATUSES = {"not_tissue", "invalid_signal", "initialization_invalid", "segmented_out_of_bounds",
            "optimizer_failed", "invalid_parameters", "degenerate_or_unordered", "ok"}
NO_SOLVER = {"not_tissue", "invalid_signal", "initialization_invalid", "segmented_out_of_bounds"}
BOUND_NAMES = ("a_lower", "f_lower", "f_upper", "Dstar_lower", "Dstar_upper",
               "D_lower", "D_upper", "Dstar_D_lower")
# Public provisional tolerances; genuine native repeats remain a release gate.
PARAMETER_ATOL = {"S0_over_b0": 1e-6, "f": 1e-6, "Dstar": 1e-8, "D": 1e-8}
PARAMETER_RTOL = 1e-6
NRMSE_ATOL = 1e-6
PREDICTION_ATOL_OVER_B0 = 1e-5
SUMMARY_ATOL = {"S0_mean": 1e-6, "f_mean": 1e-6, "Dstar_mean": 1e-8,
                "D_mean": 1e-8, "nrmse_mean": 1e-6}


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    result = float(value)
    assert math.isfinite(result), "finite numeric value required"
    return result


def integer(value):
    result = number(value)
    assert result >= 0 and result.is_integer(), "nonnegative integer required"
    return int(result)


def optional_number(value):
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "nan", "null")):
        return float("nan")
    return number(value)


def boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
        return value.strip().lower() in ("true", "1")
    raise AssertionError("explicit boolean required")


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"nonstandard JSON number: {value}")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    assert isinstance(value, dict), f"{path.name} must contain a JSON object"
    return value


def match_contract(actual, expected, field="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{field} must be an object"
        for key, value in expected.items():
            assert key in actual, f"missing {field}.{key}"
            match_contract(actual[key], value, f"{field}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"incorrect {field}"
        for index, value in enumerate(expected):
            match_contract(actual[index], value, f"{field}[{index}]")
    elif isinstance(expected, bool):
        assert actual is expected, f"incorrect {field}"
    elif isinstance(expected, (int, float)):
        geometry = field.startswith(("metadata.affine[", "metadata.header_voxel_sizes["))
        assert abs(number(actual) - expected) <= (1e-6 if geometry else 1e-12), f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def csv_rows(path, required):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        assert set(required) <= set(fields), f"missing required columns in {path.name}"
        assert len(fields) == len(set(fields)), "duplicate CSV column name"
        rows = list(reader)
    assert rows, f"empty table: {path.name}"
    assert all(None not in row and all(value is not None for value in row.values()) for row in rows), "malformed CSV row"
    return rows


def load_parameters(path):
    required = {"i", "j", "k", "method", *PARAMETERS, *FLAGS,
                "status", "nrmse", "optimizer_status", "nfev", "bound_flags"}
    groups = {}
    for row in csv_rows(path, required):
        key = tuple(integer(row[axis]) for axis in ("i", "j", "k"))
        method = row["method"].strip()
        assert method in METHODS, "unknown IVIM method"
        group = groups.setdefault(method, {})
        assert key not in group, "duplicate voxel/method row"
        status = row["status"].strip()
        assert status in STATUSES, "unknown fit status"
        optimizer = optional_number(row["optimizer_status"])
        assert np.isnan(optimizer) or (optimizer.is_integer() and -1 <= optimizer <= 4), "invalid optimizer status"
        nfev = integer(row["nfev"])
        assert nfev <= 1000, "nfev exceeds the public optimizer limit"
        flags = row["bound_flags"].strip()
        parts = flags.split("|") if flags else []
        assert len(parts) == len(set(parts)) and all(item in BOUND_NAMES for item in parts), "unknown/duplicate bound flag"
        group[key] = {"params": np.asarray([optional_number(row[name]) for name in PARAMETERS]),
                      "status": status, "nrmse": optional_number(row["nrmse"]),
                      "optimizer_status": optimizer, "nfev": nfev, "bound_flags": flags,
                      **{name: boolean(row[name]) for name in FLAGS}}
    assert set(groups) == set(METHODS), "both declared IVIM methods are required"
    return groups


def load_f_map(path, *, sweep=False):
    groups = {}
    for row in csv_rows(path, {"i", "j", "k", "f"} | ({"method"} if sweep else set())):
        key = tuple(integer(row[axis]) for axis in ("i", "j", "k"))
        method = row["method"].strip() if sweep else "primary"
        assert not sweep or method in METHODS, "unknown IVIM method"
        group = groups.setdefault(method, {})
        assert key not in group, "duplicate f-map coordinate/method"
        group[key] = optional_number(row["f"])
    if sweep:
        assert set(groups) == set(METHODS), "both declared IVIM f maps are required"
    return groups if sweep else groups["primary"]


def ordered_rows(mapping, reference):
    assert set(mapping) == set(reference["keys"]), "exact complete ROI coordinates required"
    return [mapping[key] for key in reference["keys"]]


def assert_numeric_arrays(actual, expected, *, atol, rtol=0.0, label="values"):
    actual, expected = np.asarray(actual, float), np.asarray(expected, float)
    assert actual.shape == expected.shape, f"incorrect {label} shape"
    assert not np.isinf(actual).any(), f"infinite {label}"
    assert np.array_equal(np.isnan(actual), np.isnan(expected)), f"undefined {label} pattern differs"
    finite = np.isfinite(expected)
    assert np.allclose(actual[finite], expected[finite], atol=atol, rtol=rtol), f"incorrect {label}"


def observed_b0(signal, bvals):
    assert np.any(bvals == 0), "source requires an observed b=0 volume"
    return np.mean(signal[:, bvals == 0], axis=1)


def source_masks(signal, bvals):
    b0 = observed_b0(signal, bvals)
    positive = b0[np.isfinite(b0) & (b0 > 0)]
    assert len(positive), "source ROI contains no positive b0"
    tissue = np.isfinite(b0) & (b0 > .5 * np.median(positive))
    eligible = tissue & np.isfinite(signal).all(axis=1) & (signal > 0).all(axis=1)
    return tissue, eligible


def normalized_predictions(params, signal, bvals):
    params = np.asarray(params, float)
    b0 = observed_b0(signal, bvals)
    result = np.full((len(params), len(bvals)), np.nan)
    finite = np.isfinite(params).all(axis=1) & np.isfinite(b0) & (b0 > 0)
    p = params[finite]
    with np.errstate(over="ignore", invalid="ignore"):
        predicted = (p[:, 0] / b0[finite])[:, None] * (
            p[:, 1, None] * np.exp(-bvals[None, :] * p[:, 2, None])
            + (1-p[:, 1, None]) * np.exp(-bvals[None, :] * p[:, 3, None]))
    predicted[~np.isfinite(predicted).all(axis=1)] = np.nan
    result[finite] = predicted
    return result


def signal_nrmse(params, signal, bvals):
    predicted = normalized_predictions(params, signal, bvals)
    b0 = observed_b0(signal, bvals)
    result = np.full(len(params), np.nan)
    valid = (np.isfinite(predicted).all(axis=1) & np.isfinite(signal).all(axis=1)
             & np.isfinite(b0) & (b0 > 0))
    result[valid] = np.sqrt(np.mean((predicted[valid] - signal[valid] / b0[valid, None])**2, axis=1))
    return result


def admissible(params):
    p = np.asarray(params)
    return (np.isfinite(p).all(axis=1) & (p[:, 0] > 0) & (p[:, 1] > 0) & (p[:, 1] < 1)
            & (p[:, 3] >= 0) & (p[:, 3] < p[:, 2]) & (p[:, 2] <= 1))


def bound_flags(params, b0):
    S0, f, fast, slow = params
    a = S0/b0 if np.isfinite(b0) and b0 > 0 else np.nan
    distances = (a, f, 1-f, fast, 1-fast, slow, 1-slow, fast-slow)
    return "|".join(name for name, value in zip(BOUND_NAMES, distances)
                    if np.isfinite(value) and value <= 1e-8)


def load_reference():
    with np.load(REF_PATH, allow_pickle=False) as data:
        stats = json.loads(str(data["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale IVIM reference"
        ijk = data["ref_roi_ijk"].copy()
        signal, bvals = data["ref_signal"].astype(float), data["ref_bvals"].astype(float)
        eligible = data["ref_eligible"].copy()
        tissue, common = data["ref_tissue_eligible"].copy(), data["ref_common_valid"].copy()
        b0 = data["ref_b0_observed"].copy()
        methods = {}
        for name in METHODS:
            methods[name] = {field: data[f"{field}_{name}"].copy() for field in (
                "params", "status", "init_projected", "fallback", "optimizer_status", "nfev",
                "component_swap", "bound_flags", "normalized_predictions", "nrmse")}
    assert ijk.shape == (900, 3) and np.isfinite(ijk).all() and (ijk == np.floor(ijk)).all()
    keys = [tuple(int(value) for value in row) for row in ijk]
    assert len(set(keys)) == 900 and set(keys) == {(i, j, 33) for i in range(90, 120) for j in range(90, 120)}, "incorrect reference box"
    assert signal.shape == (900, 21) and bvals.shape == (21,) and np.isfinite(bvals).all() and (bvals >= 0).all()
    for mask in (eligible, tissue, common):
        assert mask.shape == (900,) and mask.dtype.kind == "b"
    expected_tissue, expected_eligible = source_masks(signal, bvals)
    assert np.array_equal(eligible, expected_eligible) and np.array_equal(tissue, expected_tissue), "reference eligibility differs from source"
    assert_numeric_arrays(b0, observed_b0(signal, bvals), atol=0, label="reference observed b0")
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and len(hashes) == 3
    for digest in hashes.values():
        assert isinstance(digest, str) and len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    contract = stats["metadata_contract"]
    assert contract["pipeline_id"] == PIPELINE_ID and contract["dataset_id"] == DATASET_ID
    assert contract["source_sha256"] == hashes
    masks = []
    for name, ref in methods.items():
        assert ref["params"].shape == (900, 4) and not np.isinf(ref["params"]).any()
        for field in ("status", "init_projected", "fallback", "optimizer_status", "nfev", "component_swap", "bound_flags", "nrmse"):
            assert ref[field].shape == (900,), f"incorrect reference {field} shape"
        for field in ("init_projected", "fallback", "component_swap"):
            assert ref[field].dtype.kind == "b", f"reference {field} must be boolean"
        assert set(ref["status"].astype(str)) <= STATUSES and not ref["fallback"].any()
        ok = ref["status"].astype(str) == "ok"
        assert np.all(~ok | (eligible & admissible(ref["params"]))), "reference success is not admissible"
        assert np.all(~ok | ((ref["optimizer_status"] > 0) & (ref["nfev"] > 0))), "reference success lacks optimizer success"
        assert_numeric_arrays(ref["normalized_predictions"], normalized_predictions(ref["params"], signal, bvals),
                              atol=1e-10, rtol=1e-10, label=f"reference {name} predictions")
        assert_numeric_arrays(ref["nrmse"], signal_nrmse(ref["params"], signal, bvals),
                              atol=1e-10, rtol=1e-10, label=f"reference {name} NRMSE")
        masks.append(ok)
    assert np.array_equal(common, np.logical_and.reduce(masks)), "reference common-valid mask differs"
    return {"ijk": ijk, "keys": keys, "signal": signal, "bvals": bvals, "b0_observed": b0,
            "eligible": eligible, "tissue_eligible": tissue, "common_valid": common,
            "methods": methods, "stats": stats}
