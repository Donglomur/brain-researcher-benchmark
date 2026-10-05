"""Source-bound experiment receipts; missing atlas records are not observed zeros."""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "allen-projection-summary-v2"
RECORD_STATUSES = ("observed", "api_absent", "zero_domain")
NUMERIC_ATOL, NUMERIC_RTOL = 1e-12, 1e-9
SUMMARY_ATOL, TIE_ATOL = 1e-9, 1e-12
EMPTY = {"", "na", "null"}


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    value = float(value)
    assert math.isfinite(value), "finite numeric value required"
    return value


def integer(value):
    value = number(value)
    assert value >= 0 and value.is_integer(), "nonnegative integer required"
    return int(value)


def optional_number(value):
    return np.nan if value is None or str(value).strip().lower() in EMPTY else number(value)


def optional_integer(value):
    return -1 if value is None or str(value).strip().lower() in EMPTY else integer(value)


def boolean(value):
    if value is True or value is False:
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "1.0"): return True
    if text in ("false", "0", "0.0"): return False
    raise AssertionError("boolean must be true/false or 0/1")


def optional_boolean(value):
    return None if value is None or str(value).strip().lower() in EMPTY else boolean(value)


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"nonstandard JSON number: {value}")
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
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        assert set(required) <= set(fields), f"missing required columns in {Path(path).name}"
        assert len(fields) == len(set(fields)), "duplicate CSV column name"
        rows = list(reader)
    assert rows, "empty CSV table"
    assert all(None not in row and all(v is not None for v in row.values()) for row in rows), "malformed CSV row"
    return rows


def load_experiment_targets(path):
    fields = {"experiment_id", "source_id", "target_id", "record_status", "unionize_id",
              "projection_density", "sum_projection_pixels", "sum_pixels"}
    result = {}
    for row in csv_rows(path, fields):
        key = integer(row["experiment_id"]), integer(row["target_id"])
        assert key not in result, "duplicate experiment/target row"
        status = row["record_status"].strip()
        assert status in RECORD_STATUSES, "unknown record status"
        result[key] = (integer(row["source_id"]), status, optional_integer(row["unionize_id"]),
                       optional_number(row["projection_density"]), optional_number(row["sum_projection_pixels"]),
                       optional_number(row["sum_pixels"]))
    return result


def load_matrix(path, target_ids):
    rows = csv_rows(path, {"source_id"})
    columns = {}
    for header in rows[0]:
        if header == "source_id": continue
        try:
            target = integer(header)
        except (AssertionError, ValueError):
            continue  # Extra descriptive (nonnumeric) columns are harmless.
        assert target not in columns, "duplicate numeric target column"
        columns[target] = header
    assert set(columns) == set(target_ids), "exact target-ID matrix columns required"
    result = {}
    for row in rows:
        source = integer(row["source_id"])
        assert source not in result, "duplicate matrix source"
        result[source] = {target: optional_number(row[header]) for target, header in columns.items()}
    return result


def load_support(path):
    result = {}
    for row in csv_rows(path, {"source_id", "target_id", "n_observed", "n_expected"}):
        key = integer(row["source_id"]), integer(row["target_id"])
        assert key not in result, "duplicate matrix-support key"
        result[key] = integer(row["n_observed"]), integer(row["n_expected"])
    return result


def load_strongest(path):
    result = {}
    fields = {"source_id", "status", "strongest_targets", "is_self_strongest", "max_density", "n_missing_targets", "n_experiments"}
    for row in csv_rows(path, fields):
        source = integer(row["source_id"])
        assert source not in result, "duplicate strongest source"
        targets = json.loads(row["strongest_targets"])
        assert isinstance(targets, list), "strongest_targets must be a JSON list of IDs"
        targets = [integer(value) for value in targets]
        assert len(set(targets)) == len(targets), "duplicate tied target"
        assert row["status"].strip() in ("complete", "incomplete"), "unknown source status"
        result[source] = {"status": row["status"].strip(), "strongest_targets": set(targets),
            "is_self_strongest": optional_boolean(row["is_self_strongest"]),
            "max_density": optional_number(row["max_density"]),
            "n_missing_targets": integer(row["n_missing_targets"]), "n_experiments": integer(row["n_experiments"])}
    return result


def integer_array(values, *, allow_missing=False):
    values = np.asarray(values)
    assert values.dtype.kind in "iuf" and np.isfinite(values).all() and (values == np.floor(values)).all()
    assert (values >= (-1 if allow_missing else 0)).all(), "invalid integer source array"
    return values.astype(np.int64)


def validate_receipt_arrays(arrays):
    status = arrays["record_status"]
    assert set(np.unique(status)) <= set(RECORD_STATUSES), "unknown record status"
    absent, observed, zero = status == "api_absent", status == "observed", status == "zero_domain"
    unionize = arrays["unionize_id"]
    assert (unionize[absent] == -1).all() and (unionize[~absent] >= 0).all(), "unionize IDs do not match record status"
    for name in ("density", "sum_projection_pixels", "sum_pixels"):
        values = arrays[name]
        assert values.shape == status.shape, "receipt shape differs"
        assert np.isnan(values[absent]).all() and np.isfinite(values[~absent]).all(), "missing/finite fields do not match source record status"
        assert (values[~absent] >= 0).all(), "negative source measurement"
    assert (arrays["sum_pixels"][observed] > 0).all(), "observed record must have positive domain"
    assert (arrays["sum_pixels"][zero] == 0).all(), "zero_domain must have zero domain"
    assert (arrays["density"][~absent] <= 1).all(), "projection density must be in [0,1]"
    assert (arrays["sum_projection_pixels"][~absent] <= arrays["sum_pixels"][~absent]).all(), "projection pixels cannot exceed domain pixels"
    assert np.allclose(arrays["density"][observed],
        arrays["sum_projection_pixels"][observed]/arrays["sum_pixels"][observed],
        atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL), "projection density disagrees with pixel ratio"


def aggregate_receipt(arrays, source_ids):
    sources, density, status = arrays["experiment_source_ids"], arrays["density"], arrays["record_status"]
    matrix = np.full((len(source_ids), density.shape[1]), np.nan)
    observed = np.zeros(matrix.shape, dtype=np.int64)
    expected = np.zeros(matrix.shape, dtype=np.int64)
    for row, source in enumerate(source_ids):
        selected = sources == source
        valid = status[selected] == "observed"
        observed[row] = valid.sum(axis=0)
        expected[row] = int(selected.sum())
        sums = np.where(valid, density[selected], 0.).sum(axis=0)
        np.divide(sums, observed[row], out=matrix[row], where=observed[row] > 0)
    return matrix, observed, expected


def load_reference(path=None):
    with np.load(REF_PATH if path is None else path, allow_pickle=False) as archive:
        stats = json.loads(str(archive["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale atlas reference"
        arrays = {key[4:]: archive[key].copy() for key in archive.files if key.startswith("ref_") and key != "ref_stats"}
    for name in ("experiment_ids", "experiment_source_ids", "target_ids", "source_ids"):
        arrays[name] = integer_array(arrays[name])
        assert arrays[name].ndim == 1
    for name in ("experiment_ids", "target_ids", "source_ids"):
        assert len(arrays[name]) > 0 and len(set(arrays[name])) == len(arrays[name]), "duplicate source IDs"
    assert arrays["experiment_ids"].shape == arrays["experiment_source_ids"].shape
    assert set(arrays["experiment_source_ids"]) == set(arrays["source_ids"])
    assert set(arrays["source_ids"]) <= set(arrays["target_ids"])
    shape = len(arrays["experiment_ids"]), len(arrays["target_ids"])
    assert arrays["record_status"].shape == shape
    arrays["unionize_id"] = integer_array(arrays["unionize_id"], allow_missing=True)
    assert arrays["unionize_id"].shape == shape
    validate_receipt_arrays(arrays)
    matrix, observed, expected = aggregate_receipt(arrays, arrays["source_ids"])
    assert np.array_equal(arrays["n_observed"], observed) and np.array_equal(arrays["n_expected"], expected), "reference support does not reconstruct"
    assert np.allclose(arrays["matrix"], matrix, atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL, equal_nan=True), "reference matrix does not reconstruct"
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and hashes
    assert all(isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef") for value in hashes.values())
    assert stats["metadata_contract"]["pipeline_id"] == PIPELINE_ID and stats["metadata_contract"]["source_sha256"] == hashes
    return {**arrays, "stats": stats}
