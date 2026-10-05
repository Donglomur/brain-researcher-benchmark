"""Mechanical verifier boundary tests; no source reconstruction or bank generation."""
import json

import numpy as np
import pytest

from test_table import small_reference, mechanical_output, write_output, q
from build_reference import verify_unmasked_solution
from test_real_outputs import change_flat


@pytest.mark.parametrize("value", [True, False, "", "NaN", "inf", None, "1.1"])
def test_integer_rejects_nonintegers(value):
    with pytest.raises(AssertionError): q.integer(value, "fixture")


@pytest.mark.parametrize("value", ["1", "1.0", "1e0", 1, 1.0])
def test_integer_accepts_equivalent_notation(value):
    assert q.integer(value, "fixture") == 1


@pytest.mark.parametrize("mutation", ["offset", "scale", "sign", "units", "paint", "zero", "permute"])
def test_coherent_map_and_summary_forgeries_rejected(mechanical_output, small_reference, mutation):
    chi = small_reference["map"].copy()
    mask = small_reference["mask"]
    if mutation == "offset": chi[mask] += .001
    elif mutation == "scale": chi *= 1.01
    elif mutation == "sign": chi *= -1
    elif mutation == "units": chi *= 1000
    elif mutation == "paint":
        for label in q.LABELS: chi[small_reference["roi"] == label] = np.median(chi[small_reference["roi"] == label])
    elif mutation == "zero": chi[:] = 0
    elif mutation == "permute": chi[mask] = chi[mask][::-1]
    write_output(mechanical_output, small_reference, chi)
    with pytest.raises(AssertionError, match="complete susceptibility"):
        q.validate_output_directory(mechanical_output, small_reference)


@pytest.mark.parametrize("mutation", ["nan_inside", "nan_outside", "inf_inside", "inf_outside", "finite_outside", "complex", "integer", "shape"])
def test_invalid_map_domain(mechanical_output, small_reference, mutation):
    chi = small_reference["map"].copy()
    if mutation in {"nan_inside", "inf_inside"}: chi.ravel()[0] = np.nan if mutation.startswith("nan") else np.inf
    elif mutation in {"nan_outside", "inf_outside"}: chi.ravel()[-1] = np.nan if mutation.startswith("nan") else np.inf
    elif mutation == "finite_outside": chi.ravel()[-1] = 1e-30
    elif mutation == "complex": chi = chi.astype(complex)
    elif mutation == "integer": chi = chi.astype(int)
    elif mutation == "shape": chi = chi.reshape(9, 3)
    np.save(mechanical_output / "susceptibility_ppm.npy", chi)
    with pytest.raises(AssertionError): q.validate_output_directory(mechanical_output, small_reference)


@pytest.mark.parametrize("fraction,accepted", [(.99, True), (1.01, False)])
def test_public_per_voxel_tolerance(small_reference, fraction, accepted):
    chi = small_reference["map"].copy()
    chi.ravel()[0] += fraction * (q.MAP_ATOL + q.MAP_RTOL * abs(chi.ravel()[0]))
    if accepted: q.validate_map(chi, small_reference)
    else:
        with pytest.raises(AssertionError): q.validate_map(chi, small_reference)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_float_storage_and_fortran_layout(mechanical_output, small_reference, dtype):
    chi = np.asfortranarray(small_reference["map"].astype(dtype))
    write_output(mechanical_output, small_reference, chi)
    q.validate_output_directory(mechanical_output, small_reference)


@pytest.mark.parametrize("key,value", [
    ("status", "failed_precondition"), ("pipeline_id", "old"),
    ("reg", .1), ("dc_kernel", 0), ("b0_axis_index", 1),
    ("gradient_spacing", "physical_mm"), ("n_brain_voxels", 18),
    ("n_rois_reported", 5), ("brain_mask_mean_ppb", 0),
    ("input_hashes", {"fixture": "2" * 64}),
    ("input_hashes", {"fixture": "1" * 64, "extra": "2" * 64}),
    ("voxel_size_mm", [1, 1, 1]), ("shape", [3, 3, 4]),
])
def test_bad_required_metadata(mechanical_output, small_reference, key, value):
    path = mechanical_output / "run_metadata.json"
    data = json.loads(path.read_text()); data[key] = value; path.write_text(json.dumps(data))
    with pytest.raises(AssertionError): q.validate_output_directory(mechanical_output, small_reference)


def test_geometry_rounding_extra_metadata_and_free_prose(mechanical_output, small_reference):
    path = mechanical_output / "run_metadata.json"
    data = json.loads(path.read_text())
    data["voxel_size_mm"] = [round(v, 6) for v in data["voxel_size_mm"]]
    data["dc_kernel"] = .3333333333333
    data["optional_diagnostic"] = "ignored"
    path.write_text(json.dumps(data))
    (mechanical_output / "findings.md").write_text("Measured numerical output is attached.")
    q.validate_output_directory(mechanical_output, small_reference)


@pytest.mark.parametrize("name", q.REQUIRED_FILES)
def test_missing_required_file(mechanical_output, small_reference, name):
    (mechanical_output / name).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(mechanical_output, small_reference)


def test_empty_findings(mechanical_output, small_reference):
    (mechanical_output / "findings.md").write_text(" \n")
    with pytest.raises(AssertionError, match="empty findings"):
        q.validate_output_directory(mechanical_output, small_reference)


def test_bad_reference_pipeline(small_reference):
    small_reference["stats"]["pipeline_id"] = "old-correlation-bank"
    with pytest.raises(AssertionError): q.validate_reference(small_reference)


def test_constant_map_not_intrinsically_rejected_by_a_range_gate(small_reference, tmp_path):
    # A generic mechanical reference can be constant: actual source equality, not
    # an arbitrary dynamic range or physiological gate, rejects a fabricated map.
    small_reference["map"][:] = 0
    output = write_output(tmp_path, small_reference)
    q.validate_output_directory(output, small_reference)


def test_builder_spectral_identity_mechanical_single_mode():
    # A four-voxel periodic cosine has D=-2/3 and E=2 on its z mode.
    field = np.broadcast_to(.01 + .002*np.cos(np.pi*np.arange(4)/2), (4, 4, 4)).copy()
    unmasked = .03 + (field-.01)*(-2/3)/((2/3)**2 + .09*2)
    receipt = verify_unmasked_solution(field, unmasked, [1, 1, 1], .09)
    assert receipt["relative_spectral_normal_equation_residual"] < 1e-12


def test_builder_cannot_bless_a_coherent_wrong_dc_solution():
    field = np.full((4, 4, 4), .01, dtype=float)
    with pytest.raises(AssertionError, match="spectral normal equation"):
        verify_unmasked_solution(field, np.full_like(field, .031), [1, 1, 1], .09)


@pytest.mark.parametrize("order", ["C", "F"])
@pytest.mark.parametrize("value", [np.nan, np.inf, 1e-30])
def test_adversarial_scalar_mutation_writes_through_both_layouts(order, value):
    chi = np.zeros((3, 3, 3), dtype=np.float32, order=order)
    change_flat(chi, 10, value)
    assert np.isnan(chi[1, 0, 1]) if np.isnan(value) else chi[1, 0, 1] == np.float32(value)


@pytest.mark.parametrize("order", ["C", "F"])
def test_adversarial_index_array_mutation_writes_through_both_layouts(order):
    chi = np.zeros((3, 3, 3), dtype=np.float32, order=order)
    indices = np.array([0, 10, 26])
    change_flat(chi, indices, chi.flat[indices] + .001)
    assert np.array_equal(chi[([0, 1, 2], [0, 0, 2], [0, 1, 2])], np.full(3, .001, dtype=np.float32))


def test_adversarial_noop_is_not_mistaken_for_a_negative_control():
    with pytest.raises(AssertionError, match="did not change"):
        change_flat(np.zeros((2, 2, 2)), 0, 0)
