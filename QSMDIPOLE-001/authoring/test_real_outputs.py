"""Genuine-output positives and coherent adversarial mutations.

Set REPAIR_ORACLE_OUTPUT to a measured output directory. These tests never fit
source data or generate a reference. They skip until a genuine v2 bank exists.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests"))
import qsm_contract as q


@pytest.fixture(scope="module")
def genuine_source():
    configured = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not configured:
        pytest.skip("requires a genuine source-derived oracle execution")
    directory = Path(configured)
    assert directory.is_dir(), "REPAIR_ORACLE_OUTPUT does not exist"
    return directory


@pytest.fixture(scope="module")
def reference(genuine_source):
    measured = q.load_reference(TASK / "tests/reference.npz")
    q.validate_output_directory(genuine_source, measured)
    return measured


@pytest.fixture
def output(tmp_path, genuine_source):
    # Optional authoring intermediates are intentionally absent, not required.
    for name in q.REQUIRED_FILES:
        shutil.copyfile(genuine_source / name, tmp_path / name)
    return tmp_path


def rows(output):
    with (output / "nuclei_susceptibility.csv").open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(output, values, columns=None):
    with (output / "nuclei_susceptibility.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(values[0]))
        writer.writeheader(); writer.writerows(values)


def coherent_map(output, chi, reference):
    """Change the map AND every required derived summary, not only one file."""
    np.save(output / "susceptibility_ppm.npy", chi, allow_pickle=False)
    values = [{"label": label, "n_voxels": count, "susceptibility_ppb": median}
              for label, (count, median) in q.roi_summary(chi.astype(float), reference["roi"]).items()]
    write_rows(output, values)
    path = output / "run_metadata.json"
    meta = json.loads(path.read_text())
    meta["brain_mask_mean_ppb"] = float(np.mean(chi[reference["mask"]], dtype=np.float64)*1000)
    path.write_text(json.dumps(meta))


def change_flat(chi, indices, values):
    """Mutate C-indexed voxels in either memory layout, asserting a real change.

    C-order ravel() can return a copy for a Fortran-stored genuine NPY map.
    flat assignment always writes through to the original array instead.
    """
    before = np.asarray(chi.flat[indices]).copy()
    chi.flat[indices] = values
    assert not np.array_equal(before, chi.flat[indices], equal_nan=True), "adversarial mutation did not change the map"


def test_genuine_output_without_private_intermediate(output, reference):
    assert not (output / "analysis_arrays.npz").exists()
    q.validate_output_directory(output, reference)


def test_public_template_matches_bank(reference):
    template = json.loads((TASK / "environment/method_contract.json").read_text())
    assert template == reference["stats"]["metadata_contract"]


def test_minimal_template_metadata_free_prose_and_no_display_column(output, reference):
    metadata = json.loads((output / "run_metadata.json").read_text())
    minimal = json.loads((TASK / "environment/method_contract.json").read_text())
    minimal.update({key: metadata[key] for key in ("status", "n_brain_voxels", "n_rois_reported", "brain_mask_mean_ppb")})
    (output / "run_metadata.json").write_text(json.dumps(minimal))
    values = [{key: value[key] for key in ("label", "n_voxels", "susceptibility_ppb")} for value in rows(output)]
    write_rows(output, values)
    (output / "findings.md").write_text("The attached table contains numerical measurements; their interpretation is limited.")
    q.validate_output_directory(output, reference)


def test_reordered_csv_extra_columns_two_decimal_medians(output, reference):
    values = rows(output)
    for value in values:
        value["label"] = f'{int(value["label"])}.0'
        value["n_voxels"] = f'{int(value["n_voxels"])}e0'
        value["susceptibility_ppb"] = f'{float(value["susceptibility_ppb"]):.2f}'
        value["nucleus"] = "optional display text is not an anatomical test"
        value["extra"] = "ignored"
    write_rows(output, values[::-1], list(values[0])[::-1])
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_equivalent_float_storage_and_memory_layout(output, reference, dtype):
    chi = np.asfortranarray(np.load(output / "susceptibility_ppm.npy").astype(dtype))
    coherent_map(output, chi, reference)
    q.validate_output_directory(output, reference)


def test_public_geometry_rounding(output, reference):
    path = output / "run_metadata.json"
    meta = json.loads(path.read_text())
    meta["voxel_size_mm"] = [round(v, 6) for v in meta["voxel_size_mm"]]
    meta["affine"] = [[round(v, 6) for v in line] for line in meta["affine"]]
    meta["dc_kernel"] = .3333333333333
    path.write_text(json.dumps(meta))
    q.validate_output_directory(output, reference)


def test_genuinely_independent_numerical_map(output, reference):
    configured = os.environ.get("REPAIR_INDEPENDENT_MAP")
    if not configured:
        pytest.skip("requires the separately measured independent reconstruction, never refitted here")
    report_path = Path(os.environ.get("REPAIR_INDEPENDENT_REPORT", str(Path(configured).with_name("independent.json"))))
    report = q.load_json(report_path)
    assert report["status"] == "passed"
    assert report["source"]["shipped_sha256"] == reference["stats"]["input_hashes"]
    chi = np.load(configured, allow_pickle=False)
    coherent_map(output, chi, reference)
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", [
    "offset", "scale", "sign", "ppb_as_ppm", "zero", "roi_paint",
    "only_reported_rois", "inmask_permutation", "axis_flip", "nonroi_voxels",
])
def test_coherent_wrong_reconstruction(output, reference, mutation):
    chi = np.load(output / "susceptibility_ppm.npy")
    mask, roi = reference["mask"], reference["roi"]
    if mutation == "offset": chi[mask] += .001
    elif mutation == "scale": chi *= 1.01
    elif mutation == "sign": chi *= -1
    elif mutation == "ppb_as_ppm": chi *= 1000
    elif mutation == "zero": chi[:] = 0
    elif mutation == "roi_paint":
        values = q.roi_summary(chi.astype(float), roi)
        chi[:] = 0
        for label, (_, median) in values.items(): chi[roi == label] = median/1000
    elif mutation == "only_reported_rois": chi[~np.isin(roi, q.LABELS)] = 0
    elif mutation == "inmask_permutation": chi[mask] = chi[mask][::-1]
    elif mutation == "axis_flip": chi = chi[::-1, :, :].copy()*mask
    elif mutation == "nonroi_voxels":
        indices = np.flatnonzero((mask & (roi == 0)).ravel())[:100]
        assert len(indices) == 100
        change_flat(chi, indices, chi.flat[indices] + .001)
    coherent_map(output, chi, reference)
    with pytest.raises(AssertionError, match="complete susceptibility map"):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", [
    "nan_inside", "nan_outside", "inf_inside", "inf_outside",
    "finite_outside", "complex", "integer", "wrong_shape",
])
def test_invalid_complete_map(output, reference, mutation):
    chi = np.load(output / "susceptibility_ppm.npy")
    inside = np.flatnonzero(reference["mask"].ravel())[0]
    outside = np.flatnonzero(~reference["mask"].ravel())[0]
    if mutation.startswith("nan"): change_flat(chi, inside if mutation.endswith("inside") else outside, np.nan)
    elif mutation.startswith("inf"): change_flat(chi, inside if mutation.endswith("inside") else outside, np.inf)
    elif mutation == "finite_outside": change_flat(chi, outside, 1e-30)
    elif mutation == "complex": chi = chi.astype(np.complex64)
    elif mutation == "integer": chi = chi.astype(np.int32)
    elif mutation == "wrong_shape": chi = chi[1:]
    np.save(output / "susceptibility_ppm.npy", chi)
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "fractional_id", "foreign_id", "wrong_count", "wrong_median", "nonfinite", "mean_not_median", "swapped_medians"])
def test_wrong_roi_receipt(output, reference, mutation):
    values = rows(output)
    if mutation == "drop": values.pop()
    elif mutation == "duplicate": values.append(dict(values[0]))
    elif mutation == "fractional_id": values[0]["label"] = "1.1"
    elif mutation == "foreign_id": values[0]["label"] = "7"
    elif mutation == "wrong_count": values[0]["n_voxels"] = int(values[0]["n_voxels"]) + 1
    elif mutation == "wrong_median": values[0]["susceptibility_ppb"] = float(values[0]["susceptibility_ppb"]) + 1
    elif mutation == "nonfinite": values[0]["susceptibility_ppb"] = "nan"
    elif mutation == "mean_not_median":
        chi = np.load(output / "susceptibility_ppm.npy").astype(float)
        discrepancies = [abs(float(np.mean(chi[reference["roi"] == int(row["label"])])*1000) - float(row["susceptibility_ppb"])) for row in values]
        index = int(np.argmax(discrepancies)); assert discrepancies[index] > q.ROI_ATOL_PPB
        values[index]["susceptibility_ppb"] = float(np.mean(chi[reference["roi"] == int(values[index]["label"])])*1000)
    elif mutation == "swapped_medians":
        low = min(range(6), key=lambda i: float(values[i]["susceptibility_ppb"]))
        high = max(range(6), key=lambda i: float(values[i]["susceptibility_ppb"]))
        assert abs(float(values[high]["susceptibility_ppb"]) - float(values[low]["susceptibility_ppb"])) > q.ROI_ATOL_PPB
        values[low]["susceptibility_ppb"], values[high]["susceptibility_ppb"] = values[high]["susceptibility_ppb"], values[low]["susceptibility_ppb"]
    write_rows(output, values)
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("key,value", [
    ("status", "failed_precondition"), ("pipeline_id", "old"),
    ("reg", .1), ("dc_kernel", 0), ("b0_axis_index", 0),
    ("gradient_spacing", "physical_mm"), ("padding", "zero_padded"),
    ("mask_application", "before_and_after"), ("referencing", "brain_mean_zero"),
    ("map_units", "ppb"), ("field_units", "radians"), ("roi_statistic", "mean_ppb"),
    ("n_brain_voxels", 1), ("n_rois_reported", 5), ("brain_mask_mean_ppb", 10000),
    ("input_hashes", {}), ("voxel_size_mm", [1, 1, 1]), ("shape", [160, 160, 159]),
    ("affine", np.eye(4).tolist()), ("fft_norm", "ortho"),
])
def test_wrong_public_metadata(output, reference, key, value):
    path = output / "run_metadata.json"
    meta = json.loads(path.read_text()); meta[key] = value; path.write_text(json.dumps(meta))
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("name", q.REQUIRED_FILES)
def test_missing_required_artifact(output, reference, name):
    (output / name).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


def test_empty_findings(output, reference):
    (output / "findings.md").write_text("\n  ")
    with pytest.raises(AssertionError, match="empty findings"):
        q.validate_output_directory(output, reference)
