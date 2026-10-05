"""Independent numerical CF-L2 audit; never imports the oracle or verifier.

Uses the archived MATLAB centered/Nyquist-normalized frequency construction,
float64 eps, SciPy real FFTs, and a sin-squared gradient penalty. This is an
implementation-consistency check, not an STI or biological-truth validation.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import fft

SHAPE = (160, 160, 160)
REG = 0.09
MAP_ATOL, MAP_RTOL = 2e-7, 2e-5
ROI_ATOL = 0.02


def matlab_kernels(shape, voxel):
    """Original evaluation-script kernel, restricted to the even cubic source grid.

    For an even axis, fftshift and ifftshift coincide. The original meshgrid
    assignment [ky,kx,kz] places kx on array axis0 and ky on axis1 on this cube.
    Its Nyquist-normalized frequencies are twice modern fftfreq; the factor
    cancels in the quotient except for the original denominator's eps term.
    """
    assert len(shape) == 3 and len(set(shape)) == 1 and shape[0] % 2 == 0
    assert np.isfinite(voxel).all() and np.all(np.asarray(voxel) > 0)
    axes = [np.fft.ifftshift(np.arange(-n//2, n//2, dtype=np.float64)
                            / ((n//2)*spacing)) for n, spacing in zip(shape, voxel)]
    x = axes[0][:, None, None]
    y = axes[1][None, :, None]
    z = axes[2][:shape[2]//2+1][None, None, :]
    kernel = 1/3 - z*z/(x*x+y*y+z*z+np.finfo(np.float64).eps)
    e = 0.0
    for axis, n in enumerate(shape):
        values = 4*np.sin(np.pi*np.arange(n if axis < 2 else n//2+1)/n)**2
        e = e + values.reshape(tuple(-1 if j == axis else 1 for j in range(3)))
    return kernel, e


def spectral_norm(values, full_shape):
    """Full-spectrum Frobenius norm reconstructed from the real-FFT half spectrum."""
    weights = np.full(full_shape[2]//2+1, 2.)
    weights[0] = weights[-1] = 1.
    return float(np.sqrt(np.sum(np.abs(values)**2*weights[None, None, :])))


def independent_reconstruction(field, mask, voxel, reg=REG):
    assert np.isfinite(field).all() and field.shape == mask.shape
    d, e = matlab_kernels(field.shape, voxel)
    measured = fft.rfftn(field, norm="backward", workers=1)
    spectrum = d*measured/(d*d+reg*e)
    unmasked = fft.irfftn(spectrum, s=field.shape, norm="backward", workers=1)
    return unmasked, unmasked*mask, d, e, measured


def check_normal_equation(unmasked, field, voxel, reg=REG):
    d, e = matlab_kernels(field.shape, voxel)
    measured = fft.rfftn(field, norm="backward", workers=1)
    spectrum = fft.rfftn(unmasked, norm="backward", workers=1)
    right = d*measured
    residual = (d*d+reg*e)*spectrum-right
    denominator = spectral_norm(right, field.shape)
    numerator = spectral_norm(residual, field.shape)
    relative = numerator/denominator if denominator > 0 else numerator
    mean_expected, mean_actual = 3*float(np.mean(field)), float(np.mean(unmasked))
    return {"relative_spectral_normal_equation_residual": relative,
            "normal_equation_denominator": denominator,
            "unmasked_mean_ppm": mean_actual, "three_times_field_mean_ppm": mean_expected,
            "dc_mean_absolute_error_ppm": abs(mean_actual-mean_expected)}


def load_source(data):
    root = Path(data).resolve()
    legacy = json.loads((root / "input_manifest.json").read_text())
    protocol = json.loads((root / "protocol.json").read_text())
    names = ("phs_tissue.nii.gz", "msk.nii.gz", "evaluation_mask.nii.gz")
    assert set(legacy["files"]) == set(names)
    images, arrays, hashes = {}, {}, {}
    for name in names:
        path = root / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashes[name] == legacy["files"][name], "shipped input SHA mismatch"
        image = nib.load(path)
        images[name] = image
        arrays[name] = np.asarray(image.dataobj)
        assert arrays[name].shape == SHAPE and np.isfinite(arrays[name]).all()
    geometry = images[names[0]].affine
    for image in images.values():
        assert np.array_equal(image.affine, geometry), "source affine mismatch"
        assert np.array_equal(image.header.get_zooms(), images[names[0]].header.get_zooms())
    assert set(np.unique(arrays[names[1]])) <= {0, 1}, "mask must be binary"
    labels = arrays[names[2]]
    assert np.equal(labels, np.floor(labels)).all()
    assert set(np.unique(labels)) == set(range(12)), "unexpected source evaluation labels"
    mask = arrays[names[1]].astype(bool)
    assert all(np.any(labels == label) for label in range(1, 7))
    assert not np.any(((labels > 0) & (labels <= 6)) & ~mask)
    voxel = np.array(protocol["voxel_size_mm"], float)
    assert np.allclose(voxel, images[names[0]].header.get_zooms(), atol=1e-6, rtol=0)
    assert protocol["b0_axis_index"] == 2 and protocol["b0_direction"] == [0., 0., 1.]
    assert protocol["inversion"]["reg"] == REG
    provenance = {"shipped_sha256": hashes, "original_members_reparsed": []}
    manifest = json.loads((root / "source_manifest.json").read_text())
    assert len(manifest["files"]) == 3 and {item["path"] for item in manifest["files"]} == set(names)
    for item in manifest["files"]:
        assert item["sha256"] == hashes[item["path"]]
        assert (root/item["path"]).stat().st_size == item["size_bytes"]
        original = item["original"]
        original_path = (root / original["path"]).resolve()
        assert original_path.is_relative_to(root)
        raw = original_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == original["sha256"]
        assert len(raw) == original["size_bytes"]
        original_image = nib.load(original_path)
        assert np.array_equal(np.asarray(original_image.dataobj), arrays[item["path"]])
        assert np.array_equal(original_image.affine, images[item["path"]].affine)
        assert np.array_equal(original_image.header.get_zooms(), images[item["path"]].header.get_zooms())
        provenance["original_members_reparsed"].append(original["path"])
    provenance["original_equality_evidence"] = "all original members reparsed; arrays, affines and zooms equal"
    return arrays[names[0]].astype(np.float64), mask, labels, voxel, provenance


def check(data, output, independent_map_path=None):
    field, mask, labels, voxel, provenance = load_source(data)
    out = Path(output)
    submitted = np.load(out / "susceptibility_ppm.npy", allow_pickle=False)
    assert submitted.shape == SHAPE and submitted.dtype.kind == "f" and np.isfinite(submitted).all()
    assert np.equal(submitted[~mask], 0).all(), "outside-mask output must be zero"
    unmasked, independent, d, e, measured = independent_reconstruction(field, mask, voxel)
    with np.load(out / "analysis_arrays.npz", allow_pickle=False) as receipt:
        oracle_unmasked = np.asarray(receipt["chi_unmasked"], dtype=float)
    assert oracle_unmasked.shape == SHAPE and np.isfinite(oracle_unmasked).all()
    assert np.allclose(submitted, independent, atol=MAP_ATOL, rtol=MAP_RTOL)
    assert np.allclose(oracle_unmasked, unmasked, atol=1e-10, rtol=1e-9), "native independent mismatch"
    oracle_masked = oracle_unmasked*mask
    assert np.array_equal(submitted, oracle_masked.astype(np.float32)), "oracle did not serialize prescribed float32 map"
    normal = check_normal_equation(oracle_unmasked, field, voxel)
    assert normal["relative_spectral_normal_equation_residual"] <= 1e-10
    assert np.isclose(normal["unmasked_mean_ppm"], normal["three_times_field_mean_ppm"], atol=1e-11, rtol=1e-9)
    with (out / "nuclei_susceptibility.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    numeric_labels = [float(row["label"]) for row in rows]
    assert len(rows) == 6 and set(numeric_labels) == set(range(1, 7))
    rois = []
    for row in sorted(rows, key=lambda r: float(r["label"])):
        label = int(float(row["label"]))
        sel = labels == label
        median = float(np.median(submitted[sel].astype(np.float64))*1000)
        count = int(sel.sum())
        assert abs(float(row["susceptibility_ppb"])-median) <= ROI_ATOL
        assert float(row["n_voxels"]) == count
        rois.append({"label": label, "n_voxels": count, "median_ppb": median})
    metadata = json.loads((out / "run_metadata.json").read_text())
    protocol = json.loads((Path(data) / "protocol.json").read_text())
    for key, value in protocol["method_contract"].items():
        assert metadata[key] == value, "metadata method contract mismatch: " + key
    assert metadata["input_hashes"] == provenance["shipped_sha256"]
    assert metadata["status"] == "ok" and metadata["n_rois_reported"] == 6
    assert metadata["n_brain_voxels"] == int(mask.sum())
    assert np.isclose(metadata["brain_mask_mean_ppb"], submitted[mask].astype(float).mean()*1000,
                      atol=.001, rtol=1e-5)
    pre_spectrum = fft.rfftn(oracle_unmasked, norm="backward", workers=1)
    forward_error = d*pre_spectrum-measured
    forward = spectral_norm(forward_error, SHAPE)/spectral_norm(measured, SHAPE)
    native_diff = float(np.max(np.abs(oracle_unmasked-unmasked)))
    serial_diff = float(np.max(np.abs(submitted.astype(float)-oracle_masked)))
    if independent_map_path is not None:
        np.save(independent_map_path, independent.astype(np.float64), allow_pickle=False)
    return {
        "status": "passed", "scope": "fixed source-derived recipe consistency, not STI/biological truth",
        "source": provenance, "source_voxel_size_mm": voxel.tolist(),
        "n_brain_voxels": int(mask.sum()), "roi_statistics_from_saved_map": rois,
        "independent_method": "MATLAB-centered-frequency-plus-eps/SciPy-rFFT/sin-squared-gradient",
        "independent_map_filename": Path(independent_map_path).name if independent_map_path is not None else None,
        "oracle_vs_independent_native_max_abs_ppm": native_diff,
        "float32_serialization_max_abs_ppm": serial_diff,
        "saved_map_vs_independent_max_abs_ppm": float(np.max(np.abs(submitted-independent))),
        "normal_equation_pre_mask": normal,
        "regularized_forward_relative_residual": forward,
        "forward_residual_interpretation": "diagnostic; regularization need not reproduce input exactly",
        "final_brain_mask_mean_ppb": float(submitted[mask].astype(float).mean()*1000),
        "dc_interpretation": "D0=1/3 fixes unmasked full-grid DC only; not brain-mask zero mean or STI scale"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/app/data")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = check(args.data, args.output, report_path.parent / "independent_susceptibility_ppm.npy")
    report_path.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"],
                      "native_error_ppm": result["oracle_vs_independent_native_max_abs_ppm"],
                      "serialization_error_ppm": result["float32_serialization_max_abs_ppm"]}))
