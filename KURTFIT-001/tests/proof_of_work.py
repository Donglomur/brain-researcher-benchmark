"""Reference and schema helpers for the declared physical-space DKI recipe."""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "cfin-physical-wls-v2"
ALLOWED_CAPS = {1000, 1400, 2000, 2400, 3000}
PRIMARY_CAP = 2000
MAP_TOL = 1e-5
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
    """Check the public required fields; permit additional descriptive metadata."""
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
        geometry = field.startswith(("metadata.affine[", "metadata.voxel_sizes_mm[",
                                     "metadata.preprocessing.sigma_vox["))
        tolerance = 1e-6 if geometry else 1e-12
        assert abs(number(actual) - expected) <= tolerance, f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def cap_values(values):
    assert isinstance(values, dict), "cap summaries must be an object"
    result = {}
    for label, value in values.items():
        cap = integer(label)
        assert cap in ALLOWED_CAPS and cap not in result, "unknown or duplicate cap label"
        result[cap] = number(value)
    return result


def load_reference():
    with np.load(REF_PATH, allow_pickle=False) as data:
        stats = json.loads(str(data["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale DKI reference"
        ijk = data["ref_roi_ijk"].copy()
        maps = {cap: data[f"map_cap_{cap}"].astype(float) for cap in ALLOWED_CAPS}
    assert ijk.ndim == 2 and ijk.shape[1] == 3 and len(ijk) > 0
    assert np.isfinite(ijk).all() and (ijk >= 0).all() and (ijk == np.floor(ijk)).all()
    keys = [tuple(int(value) for value in row) for row in ijk]
    assert len(set(keys)) == len(keys), "duplicate reference ROI coordinate"
    for values in maps.values():
        assert values.shape == (len(keys),) and np.isfinite(values).all()
        assert ((values >= 0) & (values <= 3)).all()
    means = cap_values(stats["means"])
    assert set(means) == ALLOWED_CAPS
    for cap, values in maps.items():
        assert abs(means[cap] - values.mean()) <= 1e-12, "reference mean does not recompute"
    assert isinstance(stats["metadata_contract"], dict)
    assert stats["metadata_contract"]["pipeline_id"] == PIPELINE_ID
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
        required = {"i", "j", "k", "mk"} | ({"max_b"} if sweep else set())
        assert required <= set(reader.fieldnames or ()), "missing voxel-map columns"
        for row in reader:
            key = tuple(integer(row[axis]) for axis in ("i", "j", "k"))
            cap = integer(row["max_b"]) if sweep else PRIMARY_CAP
            assert cap in ALLOWED_CAPS, "unknown shell cap label"
            values = groups.setdefault(cap, {})
            assert key not in values, "duplicate voxel coordinate"
            value = number(row["mk"])
            assert 0 <= value <= 3, "MK must be in the declared clipped range"
            values[key] = value
    assert groups, "empty voxel map"
    return groups if sweep else groups[PRIMARY_CAP]


def ordered_values(submitted, reference):
    assert set(submitted) == set(reference["keys"]), "exact complete ROI coordinates required"
    return np.asarray([submitted[key] for key in reference["keys"]], dtype=float)
