"""Small parser/arithmetic fixtures; no synthetic scientific reference bank."""
import csv
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from proof_of_work import load_maps, ordered_values, match_contract, cap_values


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("defect", [None, "duplicate", "fractional_coordinate", "negative_coordinate",
                                    "nan", "inf", "out_of_range", "fractional_cap", "unknown_cap"])
def test_voxel_parser(tmp_path, defect):
    rows = [{"i": "1.0", "j": "2", "k": "3", "max_b": "2000.0", "mk": "1.2", "note": "extra"}]
    if defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "fractional_coordinate":
        rows[0]["i"] = "1.1"
    elif defect == "negative_coordinate":
        rows[0]["j"] = "-1"
    elif defect in ("nan", "inf"):
        rows[0]["mk"] = defect
    elif defect == "out_of_range":
        rows[0]["mk"] = "3.01"
    elif defect == "fractional_cap":
        rows[0]["max_b"] = "2000.1"
    elif defect == "unknown_cap":
        rows[0]["max_b"] = "2500"
    path = tmp_path / "map.csv"
    write_rows(path, rows)
    if defect:
        with pytest.raises(AssertionError):
            load_maps(path, sweep=True)
    else:
        assert load_maps(path, sweep=True) == {2000: {(1, 2, 3): 1.2}}


@pytest.mark.parametrize("defect", [None, "missing", "padding"])
def test_complete_coordinate_identity(tmp_path, defect):
    # Two coordinates exercise identity only; this is not a DKI measurement bank.
    keys = [(1, 2, 3), (2, 3, 4)]
    values = {keys[1]: 0.2, keys[0]: 0.1}
    if defect == "missing":
        values.pop(keys[0])
    elif defect == "padding":
        values[(99, 99, 99)] = values.pop(keys[0])
    if defect:
        with pytest.raises(AssertionError):
            ordered_values(values, {"keys": keys})
    else:
        assert np.array_equal(ordered_values(values, {"keys": keys}), [0.1, 0.2])


@pytest.mark.parametrize("summary", [{"2500": 1.0}, {"2000": 1.0, "2000.0": 1.0}, {"2000": float("nan")}])
def test_cap_summary_rejects_unknown_duplicate_or_nonfinite(summary):
    with pytest.raises(AssertionError):
        cap_values(summary)


def test_no_private_mean_or_spread_strength_requirement():
    assert cap_values({"1000": 0.0, "2000": 0.0, "3000": 3.0}) == {1000: 0.0, 2000: 0.0, 3000: 3.0}


def test_metadata_extras_are_allowed():
    match_contract({"fit": "WLS", "clip": [0, 3.0], "extra": "context"}, {"fit": "WLS", "clip": [0, 3]})


def test_metadata_wrong_method_is_rejected():
    with pytest.raises(AssertionError):
        match_contract({"fit": "OLS"}, {"fit": "WLS"})


def test_geometry_rounding_is_not_a_different_estimator():
    match_contract({"voxel_sizes_mm": [2.6, 2.6, 2.6], "preprocessing": {"sigma_vox": [0.20416]}},
                   {"voxel_sizes_mm": [2.600000143, 2.600000143, 2.600000143],
                    "preprocessing": {"sigma_vox": [0.2041604]}})
    with pytest.raises(AssertionError):
        match_contract({"preprocessing": {"fwhm_mm": 1.2500005}},
                       {"preprocessing": {"fwhm_mm": 1.25}})
