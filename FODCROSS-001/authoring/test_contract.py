"""Parser/label mechanics only: these tiny rows are not a scientific reference."""
import csv
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from peak_contract import validate_maps, validate_metadata
from proof_of_work import ESTIMATORS, estimator_values, load_maps, match_contract, ordered_values


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("defect", [
    None, "fractional_coordinate", "negative_coordinate", "fractional_peak", "negative_peak",
    "large_peak", "nan", "inf", "duplicate", "unknown_estimator", "missing_column",
])
def test_strict_map_rows(tmp_path, defect):
    rows = [
        dict(i="1.0", j=2, k=3, n_peaks="2.0", estimator="msmt", note="harmless"),
        dict(i=2, j=2, k=3, n_peaks=0, estimator="msmt", note="harmless"),
    ]
    if defect == "fractional_coordinate":
        rows[0]["i"] = "1.1"
    elif defect == "negative_coordinate":
        rows[0]["i"] = -1
    elif defect == "fractional_peak":
        rows[0]["n_peaks"] = "2.1"
    elif defect == "negative_peak":
        rows[0]["n_peaks"] = -1
    elif defect == "large_peak":
        rows[0]["n_peaks"] = 4
    elif defect in ("nan", "inf"):
        rows[0]["n_peaks"] = defect
    elif defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "unknown_estimator":
        rows[0]["estimator"] = "csd_all"
    elif defect == "missing_column":
        for row in rows:
            row.pop("n_peaks")
    path = tmp_path / "peaks.csv"
    write_rows(path, rows)
    if defect is None:
        assert load_maps(path, sweep=True) == {"msmt": {(1, 2, 3): 2, (2, 2, 3): 0}}
    else:
        with pytest.raises((AssertionError, ValueError)):
            load_maps(path, sweep=True)


@pytest.mark.parametrize("defect", ["partial", "padding", "extra"])
def test_exact_coordinate_membership(defect):
    reference = {"keys": [(1, 2, 3), (2, 2, 3)]}
    mapping = {(1, 2, 3): 2, (2, 2, 3): 1}
    if defect == "partial":
        mapping.pop((1, 2, 3))
    elif defect == "padding":
        mapping[(999, 2, 3)] = mapping.pop((1, 2, 3))
    else:
        mapping[(999, 2, 3)] = 1
    with pytest.raises(AssertionError, match="exact complete ROI"):
        ordered_values(mapping, reference)


def test_public_label_binding_no_variability_or_direction_gate():
    # Small parser/mechanical example only, never saved as a task reference.
    keys = [(1, 2, 3), (2, 2, 3)]
    reference = {"keys": keys, "maps": {"msmt": np.array([3, 3]), "csd_b1000": np.array([0, 0])}}
    groups = {name: dict(zip(keys, values)) for name, values in reference["maps"].items()}
    values, arrays = validate_maps(groups["csd_b1000"], groups, reference, "csd_b1000")
    assert np.array_equal(values, [0, 0])
    assert set(arrays) == {"msmt", "csd_b1000"}
    groups["csd_b1000"] = groups["msmt"].copy()
    with pytest.raises(AssertionError, match="declared estimator csd_b1000"):
        validate_maps(groups["msmt"], groups, reference, "msmt")


@pytest.mark.parametrize("summary", [{"csd_all": 0.5}, {"msmt": float("nan")}, {"msmt": True}, {}])
def test_summary_schema(summary):
    with pytest.raises(AssertionError):
        estimator_values(summary)


def test_metadata_required_fields_and_geometry_rounding():
    match_contract({"header_voxel_sizes": [1.123457], "header_spatial_units": "unknown"},
                   {"header_voxel_sizes": [1.123456789], "header_spatial_units": "unknown"})
    expected = {"affine": [[1.123456789]], "peak_parameters": {"npeaks": 3}, "flag": True}
    match_contract({"affine": [[1.123457]], "peak_parameters": {"npeaks": 3.0}, "flag": True, "extra": 1}, expected)
    with pytest.raises(AssertionError):
        match_contract({"affine": [[1.12]], "peak_parameters": {"npeaks": 3}, "flag": True}, expected)
    with pytest.raises(AssertionError):
        match_contract({"affine": [[1.123457]], "peak_parameters": {"npeaks": 2}, "flag": True}, expected)
    with pytest.raises(AssertionError):
        match_contract({"affine": [[1.123457]], "peak_parameters": {"npeaks": 3}, "flag": 1}, expected)


@pytest.mark.parametrize("defect", [None, "missing_status", "wrong_source", "extra_source", "wrong_primary", "duplicate_fit"])
def test_metadata_submission_choices(defect):
    hashes = {"image": "a" * 64}
    reference = {"stats": {"metadata_contract": {"source_sha256": hashes}, "source_sha256": hashes}}
    metadata = {"source_sha256": dict(hashes), "status": "ok", "primary_estimator": "csd_b3500",
                "fitted_estimators": ["csd_b3500", "csd_b1000"]}
    if defect == "missing_status":
        metadata.pop("status")
    elif defect == "wrong_source":
        metadata["source_sha256"]["image"] = "b" * 64
    elif defect == "extra_source":
        metadata["source_sha256"]["extra"] = "b" * 64
    elif defect == "wrong_primary":
        metadata["primary_estimator"] = "msmt"
    elif defect == "duplicate_fit":
        metadata["fitted_estimators"].append("csd_b3500")
    if defect is None:
        validate_metadata(metadata, reference, "csd_b3500", {"csd_b1000", "csd_b3500"})
    else:
        with pytest.raises(AssertionError):
            validate_metadata(metadata, reference, "csd_b3500", {"csd_b1000", "csd_b3500"})
