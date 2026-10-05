"""Strict public schemas for the source-bound midpoint SRTM method control."""
import csv
import json
import math
import os
from pathlib import Path
import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "srtm-pwl-midpoint-v2"
SCANS = tuple((subject, session) for subject in ("sub-01", "sub-02") for session in ("ses-baseline", "ses-rescan"))
TARGET = "putamen_equal_hemisphere"
REFERENCE = "cerebellar_cortex_equal_hemisphere"
MODEL = "SRTM-PWL-midpoint"
PARAMETERS = ("R1", "k2", "BP_ND")
SOURCE_TAC_FIELDS = ("left_putamen", "right_putamen", "left_cerebellum_cortex", "right_cerebellum_cortex")
LOWER = np.array([.01, .0001, -.5])
UPPER = np.array([3., 5., 15.])
BOUND_ATOL = 1e-7*np.maximum(1., UPPER-LOWER)
PARAM_ATOL = np.array([1e-6, 1e-7, 1e-6])
PARAM_RTOL = 1e-5
SIGNAL_ATOL, SIGNAL_RTOL = 1e-7, 1e-6
SOURCE_ATOL, SOURCE_RTOL = 1e-10, 1e-9
METRIC_ATOL, METRIC_RTOL = 1e-8, 1e-6
SUMMARY_ATOL, PERCENT_ATOL = 1e-6, 1e-5


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    value = float(value)
    assert math.isfinite(value), "finite numeric value required"
    return value


def integer(value):
    value = number(value)
    assert value >= 0 and value.is_integer(), "nonnegative integer required"
    return int(value)


def boolean(value):
    if isinstance(value, (bool, np.bool_)): return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "1.0"): return True
    if text in ("false", "0", "0.0"): return False
    raise AssertionError("boolean must be true/false or 0/1")


def bound_flags(value):
    parsed = json.loads(value) if isinstance(value, str) else value
    assert isinstance(parsed, list) and len(parsed) == 3, "bound flags must be a three-element JSON boolean list"
    return np.asarray([boolean(item) for item in parsed], bool)


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    def constant(value): raise ValueError(f"nonstandard JSON number: {value}")
    result = json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=constant)
    assert isinstance(result, dict), "JSON object required"
    return result


def match_contract(actual, expected, field="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{field} must be an object"
        for key, value in expected.items():
            assert key in actual, f"missing {field}.{key}"
            match_contract(actual[key], value, f"{field}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"incorrect {field}"
        for index, value in enumerate(expected): match_contract(actual[index], value, f"{field}[{index}]")
    elif isinstance(expected, bool):
        assert actual is expected, f"incorrect {field}"
    elif isinstance(expected, (int, float)):
        assert number(actual) == expected, f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def csv_rows(path, required):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream); fields = reader.fieldnames or []
        assert set(required) <= set(fields), f"missing required columns in {Path(path).name}"
        assert len(fields) == len(set(fields)), "duplicate CSV column name"
        rows = list(reader)
    assert rows, "empty CSV table"
    assert all(None not in row and all(v is not None for v in row.values()) for row in rows), "malformed CSV row"
    return rows


def scan_key(row):
    key = row["subject"].strip(), row["session"].strip()
    assert key in SCANS, "unknown subject/session identity"
    return key


def load_estimates(path):
    numeric = {*PARAMETERS, "k2prime", "sse", "rmse", "normalized_rmse", "reference_scale"}
    discrete = {"selected_start_index", "optimizer_status", "nfev"}
    labels = {"target", "reference_region", "model", "status"}
    required = {"subject", "session", "at_lower_bound", "at_upper_bound"} | numeric | discrete | labels
    result = {}
    for row in csv_rows(path, required):
        key = scan_key(row)
        assert key not in result, "duplicate scan estimate"
        result[key] = {**{field: number(row[field]) for field in numeric},
            **{field: integer(row[field]) for field in discrete}, **{field: row[field].strip() for field in labels},
            "at_lower_bound": bound_flags(row["at_lower_bound"]), "at_upper_bound": bound_flags(row["at_upper_bound"])}
    assert set(result) == set(SCANS), "exact four source scans required"
    return result


def load_tac_fit(path):
    numeric = {"frame_start_s", "frame_end_s", "mid_time_min", *SOURCE_TAC_FIELDS,
               "target", "reference", "predicted_target", "residual"}
    result = {}
    for row in csv_rows(path, {"subject", "session", "frame_index"} | numeric):
        key = (*scan_key(row), integer(row["frame_index"]))
        assert key not in result, "duplicate scan/frame row"
        result[key] = {field: number(row[field]) for field in numeric}
    return result


def integer_array(values):
    values = np.asarray(values)
    assert values.dtype.kind in "iuf" and np.isfinite(values).all() and (values >= 0).all() and (values == np.floor(values)).all()
    return values.astype(np.int64)


def load_reference(path=None):
    with np.load(REF_PATH if path is None else path, allow_pickle=False) as bank:
        stats = json.loads(str(bank["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale midpoint SRTM bank"
        arrays = {key[4:]: bank[key].copy() for key in bank.files if key.startswith("ref_") and key != "ref_stats"}
    assert list(zip(arrays["subject"].tolist(), arrays["session"].tolist())) == list(SCANS), "incorrect bank scan identities"
    arrays["frame_scan"], arrays["frame_index"] = integer_array(arrays["frame_scan"]), integer_array(arrays["frame_index"])
    n = len(arrays["frame_scan"])
    assert arrays["frame_scan"].shape == arrays["frame_index"].shape == (n,) and set(arrays["frame_scan"]) == set(range(4))
    assert arrays["source_tacs"].shape == (n, 4) and np.isfinite(arrays["source_tacs"]).all()
    assert (arrays["source_tacs"] >= 0).all(), "negative required source TAC"
    for field in ("frame_start_s", "frame_end_s", "mid_time_min", "target", "reference", "prediction", "residual"):
        assert arrays[field].shape == (n,) and np.isfinite(arrays[field]).all(), f"invalid bank {field}"
    assert arrays["params"].shape == (4, 3) and np.isfinite(arrays["params"]).all()
    assert ((arrays["params"] >= LOWER) & (arrays["params"] <= UPPER)).all()
    assert arrays["reference_scale"].shape == (4,) and np.isfinite(arrays["reference_scale"]).all() and (arrays["reference_scale"] > 0).all()
    assert np.allclose(arrays["target"], arrays["source_tacs"][:, :2].mean(axis=1), atol=1e-12, rtol=1e-12)
    assert np.allclose(arrays["reference"], arrays["source_tacs"][:, 2:].mean(axis=1), atol=1e-12, rtol=1e-12)
    assert np.allclose(arrays["residual"], arrays["prediction"]-arrays["target"], atol=1e-12, rtol=1e-12)
    for scan in range(4):
        mask = arrays["frame_scan"] == scan
        assert np.array_equal(arrays["frame_index"][mask], np.arange(mask.sum()))
        start, end = arrays["frame_start_s"][mask], arrays["frame_end_s"][mask]
        assert start[0] == 0 and (end > start).all() and np.array_equal(start[1:], end[:-1])
        assert np.allclose(arrays["mid_time_min"][mask], (start+end)/120., atol=1e-12, rtol=0)
        assert arrays["reference_scale"][scan] == float(np.max(arrays["reference"][mask]))
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and hashes
    assert all(isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef") for value in hashes.values())
    assert stats["metadata_contract"]["pipeline_id"] == PIPELINE_ID and stats["metadata_contract"]["source_sha256"] == hashes
    return {**arrays, "stats": stats}
