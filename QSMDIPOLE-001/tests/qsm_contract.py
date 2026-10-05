"""Source-bound numerical checks for the publicly specified CF-L2 recipe.

The bank is a measured computational reference, not STI or biological truth.
No anatomical labels, physiological ranges, correlations or prose keywords score.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

PIPELINE_ID = "qsm2016-cfl2-native-dc-v2"
LABELS = tuple(range(1, 7))
MAP_ATOL = 2e-7
MAP_RTOL = 2e-5
ROI_ATOL_PPB = 0.02
MEAN_ATOL_PPB = 0.001
MEAN_RTOL = 1e-5
REQUIRED_FILES = (
    "susceptibility_ppm.npy", "nuclei_susceptibility.csv",
    "run_metadata.json", "findings.md",
)


def finite_number(value, name):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not a number"
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AssertionError(f"{name}: expected a finite number") from exc
    assert np.isfinite(result), f"{name}: expected a finite number"
    return result


def integer(value, name):
    result = finite_number(value, name)
    assert result.is_integer(), f"{name}: expected an integer"
    return int(result)


def load_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise AssertionError(f"cannot read JSON {path}") from exc
    assert isinstance(data, dict), f"{path}: expected a JSON object"
    return data


def validate_reference(reference):
    stats = reference["stats"]
    assert stats["pipeline_id"] == PIPELINE_ID, "obsolete reference pipeline"
    contract = stats["metadata_contract"]
    assert contract["pipeline_id"] == PIPELINE_ID
    assert stats["input_hashes"] == contract["input_hashes"], "reference source hashes differ"
    shape = tuple(contract["shape"])
    chi, mask, roi = (reference[key] for key in ("map", "mask", "roi"))
    assert chi.shape == mask.shape == roi.shape == shape, "reference geometry mismatch"
    assert chi.dtype.kind == "f" and np.isfinite(chi).all(), "nonfinite/nonfloating reference"
    assert mask.dtype.kind == "b" and mask.any(), "reference mask must be nonempty and binary"
    assert roi.dtype.kind in "iu" and np.all((roi >= 0) & (roi <= 11)), "invalid reference ROI labels"
    assert np.all(chi[~mask] == 0), "reference must be zero outside brain mask"
    assert integer(stats["n_brain_voxels"], "reference brain count") == int(mask.sum())
    assert set(stats["roi_counts"]) == {str(label) for label in LABELS}
    for label in LABELS:
        selected = roi == label
        count = int(selected.sum())
        assert count > 0 and np.all(mask[selected]), "reference measurement ROI outside brain/empty"
        assert integer(stats["roi_counts"][str(label)], "reference ROI count") == count
    return reference


def load_reference(path):
    try:
        with np.load(path, allow_pickle=False) as bank:
            reference = {
                "map": bank["ref_map"], "mask": bank["ref_mask"],
                "roi": bank["ref_roi"], "stats": json.loads(str(bank["ref_stats"].item())),
            }
    except (OSError, ValueError, KeyError) as exc:
        raise AssertionError("missing, corrupt, or obsolete measured reference bank") from exc
    return validate_reference(reference)


def require_files(output):
    output = Path(output)
    for name in REQUIRED_FILES:
        assert (output / name).is_file(), f"missing required output {name}"
    assert (output / "findings.md").read_text(encoding="utf-8-sig").strip(), "empty findings.md"


def load_map(path, reference):
    try:
        chi = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise AssertionError("cannot read susceptibility_ppm.npy as a numeric NPY array") from exc
    assert isinstance(chi, np.ndarray), "susceptibility map must be an NPY array"
    assert chi.dtype.kind == "f", "susceptibility map must have a real floating dtype"
    assert chi.shape == reference["map"].shape, "susceptibility map geometry/shape mismatch"
    assert np.isfinite(chi).all(), "susceptibility map must be finite at every voxel"
    assert np.all(chi[~reference["mask"]] == 0), "susceptibility outside the source brain mask must be zero"
    return np.asarray(chi, dtype=np.float64)


def validate_map(chi, reference):
    assert np.allclose(chi, reference["map"], atol=MAP_ATOL, rtol=MAP_RTOL), (
        "complete susceptibility map differs from the source-derived fixed CF-L2 recipe")


def read_roi_rows(path):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames is not None, "missing ROI CSV header"
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            assert len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate CSV column"
            assert {"label", "n_voxels", "susceptibility_ppb"} <= set(reader.fieldnames), "missing ROI CSV columns"
            rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]
    except OSError as exc:
        raise AssertionError("cannot read nuclei_susceptibility.csv") from exc
    parsed = {}
    for row in rows:
        label = integer(row["label"], "ROI label")
        assert label not in parsed, "duplicate ROI label"
        count = integer(row["n_voxels"], "ROI n_voxels")
        value = finite_number(row["susceptibility_ppb"], "ROI susceptibility_ppb")
        parsed[label] = (count, value)
    assert set(parsed) == set(LABELS), "expected exactly numeric ROI labels 1 through 6"
    return parsed


def roi_summary(chi, roi):
    return {label: (int(np.count_nonzero(roi == label)),
                    float(np.median(chi[roi == label]) * 1000.0)) for label in LABELS}


def validate_roi_table(path, chi, reference):
    rows = read_roi_rows(path)
    for label, (count, median) in roi_summary(chi, reference["roi"]).items():
        assert rows[label][0] == count, f"ROI {label}: count differs from source ROI"
        assert abs(rows[label][1] - median) <= ROI_ATOL_PPB, f"ROI {label}: not the saved-map-derived median in ppb"


def match_contract(actual, expected, name="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{name}: expected an object"
        if name.endswith("input_hashes"):
            assert actual == expected, f"{name}: source hash set differs"
            return
        for key, value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_contract(actual[key], value, f"{name}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{name}: list mismatch"
        for index, value in enumerate(expected):
            match_contract(actual[index], value, f"{name}[{index}]")
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert type(actual) is type(expected) and actual == expected, f"{name}: recipe mismatch"
    elif isinstance(expected, (int, float)):
        value = finite_number(actual, name)
        tolerance = 1e-6 if ".affine" in name or ".voxel_size_mm" in name else 1e-12
        assert abs(value - expected) <= tolerance, f"{name}: recipe mismatch"
    else:
        raise AssertionError(f"unsupported public contract field {name}")


def validate_metadata(path, chi, reference):
    metadata = load_json(path)
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata.get("status") == "ok", "metadata status must be ok"
    assert integer(metadata.get("n_brain_voxels"), "n_brain_voxels") == int(reference["mask"].sum()), "brain voxel count differs"
    assert integer(metadata.get("n_rois_reported"), "n_rois_reported") == len(LABELS), "ROI count differs"
    reported_mean = finite_number(metadata.get("brain_mask_mean_ppb"), "brain_mask_mean_ppb")
    actual_mean = float(np.mean(chi[reference["mask"]], dtype=np.float64) * 1000.0)
    assert np.isclose(reported_mean, actual_mean, atol=MEAN_ATOL_PPB, rtol=MEAN_RTOL), "brain-mask mean is not derived from saved map"
    return metadata


def validate_output_directory(output, reference):
    output = Path(output)
    require_files(output)
    chi = load_map(output / "susceptibility_ppm.npy", reference)
    validate_map(chi, reference)
    validate_roi_table(output / "nuclei_susceptibility.csv", chi, reference)
    validate_metadata(output / "run_metadata.json", chi, reference)
    return chi
