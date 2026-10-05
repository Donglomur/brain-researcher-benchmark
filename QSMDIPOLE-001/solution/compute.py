"""Source-derived CF-L2 method control; no I/O on import.

D(0)=1/3 is a computational convention, not an absolute susceptibility reference
or a zero brain-mask mean constraint.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import nibabel as nib
import numpy as np

PIPELINE_ID = "qsm2016-cfl2-native-dc-v2"
SHAPE = (160, 160, 160)
VOXEL = (1.0625, 1.0625, 1.0714285714285714)
AFFINE = [[1.0625, 0., 0., 1.0625], [0., 1.0625, 0., 1.0625],
          [0., 0., 1.0714285373687744, 1.0714285373687744], [0., 0., 0., 1.]]
INPUT_HASHES = {
    "evaluation_mask.nii.gz": "5c8a25e17372a789144361503bdbac1c892e21ec03b841467508c10281416b69",
    "phs_tissue.nii.gz": "b53d34aff4bca09639768cd16d321af59a9ab158da18655f7829a1a401495b8c",
    "msk.nii.gz": "b9961d0f431e47cfc97577bce7f70a702dcfe9dccd09b5735d319d0f7975a538",
}
CSV_FIELDS = ["label", "nucleus", "n_voxels", "susceptibility_ppb"]


def metadata_contract():
    """Public static template: only source and recipe definitions, no answers."""
    return {"pipeline_id": PIPELINE_ID, "dataset_id": "qsm2016_recon_challenge",
            "input_hashes": dict(INPUT_HASHES), "shape": list(SHAPE),
            "voxel_size_mm": list(VOXEL), "affine": AFFINE,
            "reg": 0.09, "b0_axis_index": 2, "dc_kernel": 1.0 / 3.0,
            "fft_norm": "backward", "padding": "none_periodic",
            "gradient_spacing": "voxel_index_no_mm_scaling",
            "mask_application": "post_inversion_only",
            "referencing": "native_dc_convention_no_offset",
            "field_units": "ppm", "map_units": "ppm", "roi_statistic": "median_ppb"}


def dipole_kernel(shape, voxel, b0_axis=2):
    if len(shape) != 3 or len(voxel) != 3 or b0_axis not in (0, 1, 2):
        raise ValueError("require three spatial dimensions and a valid B0 axis")
    if any(n <= 0 or int(n) != n for n in shape) or not np.all(np.isfinite(voxel)) or min(voxel) <= 0:
        raise ValueError("invalid grid or voxel spacing")
    axes = np.meshgrid(*(np.fft.fftfreq(n, d=v) for n, v in zip(shape, voxel)), indexing="ij")
    k2 = sum(k*k for k in axes)
    kernel = np.full(shape, 1.0/3.0, dtype=float)
    np.subtract(kernel, np.divide(axes[b0_axis]**2, k2,
                                out=np.zeros_like(k2), where=k2 != 0), out=kernel)
    return kernel


def gradient_operator(shape):
    axes = np.meshgrid(*(np.arange(n) for n in shape), indexing="ij")
    return sum(np.abs(1 - np.exp(2j*np.pi*k/n))**2 for k, n in zip(axes, shape))


def cf_l2(field, mask, voxel, b0_axis, reg, return_unmasked=False):
    field = np.asarray(field, dtype=float)
    mask = np.asarray(mask)
    if field.ndim != 3 or mask.shape != field.shape or not np.isfinite(field).all():
        raise ValueError("finite three-dimensional field and aligned mask required")
    if not np.isin(mask, [0, 1]).all() or not np.isfinite(reg) or reg <= 0:
        raise ValueError("binary mask and positive regularization required")
    kernel = dipole_kernel(field.shape, voxel, b0_axis)
    penalty = gradient_operator(field.shape)
    spectrum = kernel * np.fft.fftn(field, norm="backward") / (kernel**2 + reg*penalty)
    unmasked = np.fft.ifftn(spectrum, norm="backward").real
    result = unmasked * mask
    if not np.isfinite(result).all():
        raise ValueError("non-finite reconstructed map")
    return (result, unmasked) if return_unmasked else result


def read_inputs(data):
    data = Path(data)
    manifest = json.loads((data / "input_manifest.json").read_text())
    protocol = json.loads((data / "protocol.json").read_text())
    if manifest.get("files") != INPUT_HASHES:
        raise ValueError("unexpected input manifest")
    if protocol.get("method_contract") != metadata_contract():
        raise ValueError("protocol differs from the public fixed recipe")
    images = {}
    for name, expected in INPUT_HASHES.items():
        path = data / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"source SHA256 mismatch: {name}")
        img = nib.load(path)
        if img.shape != SHAPE or not np.array_equal(img.affine, np.asarray(AFFINE)):
            raise ValueError("source geometry mismatch")
        if not np.allclose(img.header.get_zooms()[:3], VOXEL, atol=1e-7, rtol=0):
            raise ValueError("source spacing mismatch")
        arr = np.asarray(img.dataobj, dtype=float)
        if not np.isfinite(arr).all():
            raise ValueError("non-finite source volume")
        images[name] = arr
    field, mask, roi = (images[name] for name in ("phs_tissue.nii.gz", "msk.nii.gz", "evaluation_mask.nii.gz"))
    if not np.isin(mask, [0, 1]).all() or not mask.any():
        raise ValueError("brain mask must be nonempty and binary")
    if not np.equal(roi, np.rint(roi)).all() or not np.isin(roi, range(12)).all():
        raise ValueError("evaluation labels must be integers 0..11")
    for label in range(1, 7):
        select = roi == label
        if not select.any() or not np.all(mask[select] == 1):
            raise ValueError("empty or out-of-brain measurement ROI")
    return field, mask.astype(bool), roi.astype(np.uint8)


def run(data, output):
    field, mask, roi = read_inputs(data)
    chi, unmasked = cf_l2(field, mask, VOXEL, 2, .09, return_unmasked=True)
    # Derive every reported statistic from exactly the submitted serialization.
    saved = chi.astype(np.float32)
    np.save(output / "susceptibility_ppm.npy", saved, allow_pickle=False)
    saved64 = saved.astype(float)
    rows = [{"label": label, "nucleus": f"ROI_{label}", "n_voxels": int(np.sum(roi == label)),
             "susceptibility_ppb": float(np.median(saved64[roi == label])*1000)}
            for label in range(1, 7)]
    with (output / "nuclei_susceptibility.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    meta = metadata_contract() | {"status": "ok", "n_brain_voxels": int(mask.sum()),
                                  "n_rois_reported": len(rows),
                                  "brain_mask_mean_ppb": float(saved64[mask].mean()*1000)}
    (output / "run_metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False)+"\n")
    # Independent authoring check only; not a participant output requirement.
    np.savez_compressed(output / "analysis_arrays.npz", chi_unmasked=unmasked)
    body = "# Source-derived closed-form L2 reconstruction control\n\n"
    body += "\n".join(f"- ROI_{r['label']}: {r['susceptibility_ppb']:.6f} ppb (median; {r['n_voxels']} voxels)." for r in rows)
    body += f"\n\nBrain-mask mean: {meta['brain_mask_mean_ppb']:.6f} ppb.\n\n"
    body += ("The original challenge code supplies the CF-L2 recipe, regularization 0.09, "
             "physical spacing and D(0)=1/3 convention. All six values are medians from "
             "the saved map, not named-nucleus findings or the paper's regional "
             "error metric. The evaluation regions are small numeric-label "
             "samples; their individual anatomical identities are not authenticated.\n\n"
             "D(0)=1/3 implies the pre-mask computational mean is three times the "
             "input-field mean; post-masking does not enforce a zero brain mean. No "
             "CSF/WM offset is applied. This convention does not establish absolute "
             "susceptibility or equality with STI chi33. Single-orientation inversion, "
             "regularization and tissue anisotropy limit biological interpretation. "
             "The map tests a declared source-derived numerical calculation, not "
             "challenge-wide superiority or empirical model difficulty.\n\n"
             "Original archive and shipped arrays/geometry were compared exactly; "
             "the shipped gzip/header/datatype representations differ losslessly. "
             "The archive is publicly accessible, but dataset redistribution terms "
             "remain unestablished; the included utility-code license is not a data license.\n")
    (output / "findings.md").write_text(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/app/data")))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    try:
        run(args.data, args.output)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        (args.output / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason})+"\n")
        (args.output / "nuclei_susceptibility.csv").write_text(",".join(CSV_FIELDS)+"\n")
        (args.output / "findings.md").write_text("# Failed precondition\n\n"+reason+"\n")
        raise SystemExit(reason)


if __name__ == "__main__":
    main()
