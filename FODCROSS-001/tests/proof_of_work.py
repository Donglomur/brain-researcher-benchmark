"""Strict public-schema helpers for the pinned Sherbrooke estimator comparison."""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "sherbrooke-fodf-v2"
ESTIMATORS = {"msmt", "csd_b1000", "csd_b3500"}
ARITHMETIC_TOL = 1e-6


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    value = float(value)
    assert math.isfinite(value), "finite numeric value required"
    return value


def integer(value):
    value = number(value)
    assert value >= 0 and value.is_integer(), "nonnegative integer required"
    return int(value)


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"{path.name} must contain a JSON object"
    return value


def match_contract(actual, expected, field="metadata"):
    """Check the public required fields, permitting descriptive additions."""
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
        tolerance = 1e-6 if geometry else 1e-12
        assert abs(number(actual) - expected) <= tolerance, f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def estimator_values(values):
    assert isinstance(values, dict) and values, "estimator summaries must be a nonempty object"
    assert set(values) <= ESTIMATORS, "unknown estimator summary label"
    return {key: number(value) for key, value in values.items()}


def load_reference():
    with np.load(REF_PATH, allow_pickle=False) as data:
        stats = json.loads(str(data["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale fODF reference"
        ijk = data["ref_roi_ijk"].copy()
        maps = {name: data[f"map_{name}"].astype(float) for name in ESTIMATORS}
    assert ijk.ndim == 2 and ijk.shape[1] == 3 and len(ijk) > 0
    assert np.isfinite(ijk).all() and (ijk >= 0).all() and (ijk == np.floor(ijk)).all()
    keys = [tuple(int(value) for value in row) for row in ijk]
    assert len(set(keys)) == len(keys), "duplicate reference ROI coordinate"
    for values in maps.values():
        assert values.shape == (len(keys),) and np.isfinite(values).all()
        assert ((values >= 0) & (values <= 3) & (values == np.floor(values))).all()
    fractions = estimator_values(stats["frac_by_config"])
    assert set(fractions) == ESTIMATORS
    for name, values in maps.items():
        assert abs(fractions[name] - np.mean(values >= 2)) <= 1e-12, "reference fraction does not recompute"
    assert integer(stats["n_roi_voxels"]) == len(keys)
    assert isinstance(stats["metadata_contract"], dict)
    assert stats["metadata_contract"]["pipeline_id"] == PIPELINE_ID
    assert stats["metadata_contract"]["dataset_id"] == "sherbrooke_3shell"
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and hashes
    for digest in hashes.values():
        assert isinstance(digest, str) and len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    assert stats["metadata_contract"]["source_sha256"] == hashes
    return {"ijk": ijk, "keys": keys, "maps": maps, "stats": stats}


def load_maps(path, *, sweep=False):
    groups = {}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"i", "j", "k", "n_peaks"} | ({"estimator"} if sweep else set())
        fields = reader.fieldnames or []
        assert required <= set(fields), "missing peak-map columns"
        assert len(fields) == len(set(fields)), "duplicate CSV column name"
        for row in reader:
            key = tuple(integer(row[axis]) for axis in ("i", "j", "k"))
            name = row["estimator"] if sweep else "primary"
            assert not sweep or name in ESTIMATORS, "unknown estimator label"
            values = groups.setdefault(name, {})
            assert key not in values, "duplicate voxel coordinate"
            value = integer(row["n_peaks"])
            assert value <= 3, "peak count must be an integer in 0..3"
            values[key] = value
    assert groups, "empty peak map"
    return groups if sweep else groups["primary"]


def ordered_values(submitted, reference):
    assert set(submitted) == set(reference["keys"]), "exact complete ROI coordinates required"
    return np.asarray([submitted[key] for key in reference["keys"]], dtype=int)
