"""Build the v2 bank only from a genuine source-checked oracle execution.

This is authoring tooling, never part of participant runtime. It does not fetch
data, change the original images, import a legacy answer or fabricate a map.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests"))
from qsm_contract import PIPELINE_ID, load_reference, validate_output_directory, validate_reference


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def verify_unmasked_solution(field, unmasked, voxel, reg):
    """Verify the full-grid linear normal equation, before the final mask.

    Uses a real FFT and sine-squared index penalty rather than the oracle's
    complex-exponential full FFT construction. This is a numerical identity
    check, not a forward-fit goodness/biological accuracy threshold.
    """
    assert unmasked.dtype == np.float64 and unmasked.shape == field.shape
    assert np.isfinite(unmasked).all(), "nonfinite authoring unmasked solution"
    shape = field.shape
    axes = [np.fft.fftfreq(n, d=spacing) if axis < 2 else np.fft.rfftfreq(n, d=spacing)
            for axis, (n, spacing) in enumerate(zip(shape, voxel))]
    x, y, z = axes[0][:, None, None], axes[1][None, :, None], axes[2][None, None, :]
    radius = x*x + y*y + z*z
    kernel = 1/3 - np.divide(z*z, radius, out=np.zeros_like(radius), where=radius != 0)
    penalty = 0.
    for axis, size in enumerate(shape):
        values = 4*np.sin(np.pi*np.arange(size if axis < 2 else size//2+1)/size)**2
        penalty = penalty + values.reshape(tuple(-1 if dimension == axis else 1 for dimension in range(3)))
    right = kernel * np.fft.rfftn(field, norm="backward")
    residual = (kernel**2 + reg*penalty)*np.fft.rfftn(unmasked, norm="backward") - right
    weights = np.full(shape[-1]//2+1, 2.); weights[0] = weights[-1] = 1.
    right_norm = float(np.sqrt(np.sum(np.abs(right)**2*weights)))
    residual_norm = float(np.sqrt(np.sum(np.abs(residual)**2*weights)))
    relative = residual_norm / right_norm if right_norm else residual_norm
    assert relative < 1e-10, "authoring solution violates the public spectral normal equation"
    dc_error = abs(float(unmasked.mean()) - 3*float(field.mean()))
    assert dc_error < 1e-12, "authoring solution violates the public DC convention"
    return {"relative_spectral_normal_equation_residual": relative, "dc_mean_absolute_error_ppm": dc_error}


def build(data, output, bank, method_contract):
    data, output, bank = Path(data), Path(output), Path(bank)
    oracle = module("qsm_oracle_for_authoring", TASK / "solution/compute.py")
    staging = module("qsm_source_for_authoring", TASK / "environment/stage_data.py")
    # Verify all original member bytes and actual original/shipped geometry and
    # arrays again. This calls no download/staging function and has no fallback.
    manifest, _ = staging.read_manifest(data / "source_manifest.json")
    comparisons = []
    for record in manifest["files"]:
        original = data / record["original"]["path"]
        shipped = data / record["path"]
        staging.verify_file(original, record["original"])
        staging.verify_file(shipped, record)
        comparisons.append(staging.compare_images(original, shipped, record, manifest["geometry"]))
    field, mask, roi = oracle.read_inputs(data)
    contract = oracle.metadata_contract()
    assert json.loads(Path(method_contract).read_text()) == contract, "public template differs from oracle recipe"
    with np.load(output / "analysis_arrays.npz", allow_pickle=False) as receipt:
        unmasked = receipt["chi_unmasked"]
    diagnostics = verify_unmasked_solution(field, unmasked, contract["voxel_size_mm"], contract["reg"])
    saved = np.load(output / "susceptibility_ppm.npy", allow_pickle=False)
    assert saved.dtype.kind == "f" and saved.shape == field.shape and np.isfinite(saved).all()
    assert np.array_equal(saved, (unmasked*mask).astype(saved.dtype)), "saved map is not the recorded genuine post-mask inversion"
    stats = {
        "pipeline_id": PIPELINE_ID, "input_hashes": contract["input_hashes"],
        "metadata_contract": contract, "n_brain_voxels": int(mask.sum()),
        "roi_counts": {str(label): int(np.count_nonzero(roi == label)) for label in range(1, 7)},
        "source_comparisons": comparisons, "authoring_diagnostics": diagnostics,
    }
    reference = validate_reference({"map": saved.astype(np.float32), "mask": mask, "roi": roi, "stats": stats})
    validate_output_directory(output, reference)
    bank.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".reference-v2-", suffix=".npz", dir=bank.parent, delete=False) as stream:
        temporary = Path(stream.name)
        np.savez_compressed(stream, ref_map=reference["map"], ref_mask=mask, ref_roi=roi,
                            ref_stats=np.array(json.dumps(stats, allow_nan=False)))
        stream.flush(); os.fsync(stream.fileno())
    try:
        validate_output_directory(output, load_reference(temporary))
        os.replace(temporary, bank)
    finally:
        if temporary.exists(): temporary.unlink()
    print(json.dumps({"bank": str(bank), "pipeline_id": PIPELINE_ID,
                      "n_brain_voxels": stats["n_brain_voxels"], "roi_counts": stats["roi_counts"],
                      **diagnostics}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bank", type=Path, default=TASK / "tests/reference.npz")
    parser.add_argument("--method-contract", type=Path, default=TASK / "environment/method_contract.json")
    args = parser.parse_args()
    build(args.data, args.output, args.bank, args.method_contract)


if __name__ == "__main__":
    main()
