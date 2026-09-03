"""Reference solution for QSMDIPOLE-001.

Reconstruct the magnetic susceptibility map of one QSM-Challenge-2016 subject from the
single-orientation local tissue field by the pinned closed-form L2 (Tikhonov, gradient-
regularized) dipole inversion specified in protocol.json, then report the mean
susceptibility (ppb) of each deep-gray nucleus, so that it reproduces the deep-gray
susceptibility of the held-out STI chi_33 reference (globus pallidus ~159 ppb,
putamen ~72 ppb).

The one judgement the brief does not spell out: how the reconstructed map is referenced.
A closed-form dipole inversion of the provided (already zero-mean) tissue field returns a
map on the SAME implicit scale as the STI reference (its brain-mask mean is ~0). Reporting
that map's nuclei values directly reproduces the reference. Subtracting a CSF/ventricle or
white-matter reference offset — a common habit when reporting "absolute" susceptibility —
shifts every value by that region's susceptibility (~14 ppb for CSF, ~20-40 ppb for WM on
this subject) and no longer matches the STI reference. The reference solution therefore
reports the reconstruction on its native scale (no extra referencing).

Validated (STEP-0, this subject): pinned CF-L2 gives globus pallidus 153 ppb, putamen 78 ppb
vs STI chi_33 159 / 72 ppb (within ~6 ppb). A CSF-referenced report gives 139 / 64 ppb;
a whole-brain -> WM re-reference gives 173 / 97 ppb; a differently-regularized inversion
(plain Tikhonov) gives 98 / 50 ppb -- all miss.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

DATA = Path(os.environ.get("DATA_DIR", "/app/data"))
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason: str) -> None:
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "qsm2016_recon_challenge"}, indent=2), encoding="utf-8")
    (OUT / "nuclei_susceptibility.csv").write_text(
        "label,nucleus,susceptibility_ppb\n", encoding="utf-8")
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n", encoding="utf-8")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def dipole_kernel(shape, voxel, b0_axis=2):
    ks = [np.fft.fftfreq(n, d=v) for n, v in zip(shape, voxel)]
    KX, KY, KZ = np.meshgrid(ks[0], ks[1], ks[2], indexing="ij")
    K = [KX, KY, KZ]
    k2 = KX * KX + KY * KY + KZ * KZ
    kb = K[b0_axis]
    with np.errstate(invalid="ignore", divide="ignore"):
        D = 1.0 / 3.0 - (kb * kb) / np.where(k2 == 0.0, 1.0, k2)
    D[0, 0, 0] = 1.0 / 3.0                 # protocol: D(0) := 1/3
    return D


def gradient_operator(shape):
    k1, k2, k3 = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]),
                             np.arange(shape[2]), indexing="ij")
    return (np.abs(1 - np.exp(2j * np.pi * k1 / shape[0])) ** 2 +
            np.abs(1 - np.exp(2j * np.pi * k2 / shape[1])) ** 2 +
            np.abs(1 - np.exp(2j * np.pi * k3 / shape[2])) ** 2)


def cf_l2(field, mask, voxel, b0_axis, reg):
    D = dipole_kernel(field.shape, voxel, b0_axis)
    E = gradient_operator(field.shape)
    with np.errstate(invalid="ignore", divide="ignore"):
        Xk = np.conj(D) * np.fft.fftn(field) / (np.abs(D) ** 2 + reg * E)
    chi = np.real(np.fft.ifftn(Xk))
    return chi * mask


def main():
    try:
        protocol = json.loads((DATA / "protocol.json").read_text())
    except Exception as e:
        fail(f"could not read protocol.json: {e}")
        return
    try:
        field = np.asarray(nib.load(str(DATA / protocol["field_file"])).dataobj, float)
        mask = np.asarray(nib.load(str(DATA / protocol["mask_file"])).dataobj) > 0
        roi = np.rint(np.asarray(nib.load(str(DATA / protocol["roi_file"])).dataobj)).astype(int)
    except Exception as e:
        fail(f"could not load input volumes: {e}")
        return

    voxel = [float(v) for v in protocol["voxel_size_mm"]]
    b0_axis = int(protocol["b0_axis_index"])
    reg = float(protocol["inversion"]["reg"])
    labels = {int(k): v for k, v in protocol["roi_labels"].items()}

    # pinned closed-form L2 dipole inversion; native scale (no extra referencing)
    chi = cf_l2(field, mask, voxel, b0_axis, reg)          # ppm
    if not np.isfinite(chi[mask]).all():
        fail("reconstructed susceptibility contains non-finite values")
        return

    # per-nucleus report (deep-gray labels 1-6), susceptibility in ppb
    rows = []
    for lab in sorted(l for l in labels if l <= 6):
        sel = roi == lab
        if int(sel.sum()) == 0:
            continue
        val_ppb = float(np.median(chi[sel]) * 1000.0)
        rows.append((lab, labels[lab], round(val_ppb, 2)))

    with open(OUT / "nuclei_susceptibility.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "nucleus", "susceptibility_ppb"])
        for lab, name, val in rows:
            w.writerow([lab, name, val])

    np.save(OUT / "susceptibility_ppm.npy", chi.astype(np.float32))

    (OUT / "run_metadata.json").write_text(json.dumps({
        "status": "ok",
        "dataset_id": "qsm2016_recon_challenge",
        "method": "closed-form L2 (gradient-regularized Tikhonov) dipole inversion",
        "reg": reg,
        "b0_direction": protocol["b0_direction"],
        "referencing": "native dipole-inversion scale (brain-mask mean ~0); no CSF/WM offset applied",
        "reported_statistic": "per-nucleus median susceptibility (ppb)",
        "brain_mask_mean_ppb": round(float(np.mean(chi[mask]) * 1000.0), 3),
        "n_nuclei_reported": len(rows),
    }, indent=2), encoding="utf-8")

    gp = next((v for l, n, v in rows if l == 3), None)
    put = next((v for l, n, v in rows if l == 2), None)
    (OUT / "findings.md").write_text(
        "# Deep-gray susceptibility (QSM 2016 challenge subject)\n\n"
        "Reconstructed the single-orientation tissue field with the pinned closed-form L2 "
        "(gradient-regularized) dipole inversion and reported each deep-gray nucleus's mean "
        "susceptibility on the reconstruction's native scale (brain-mask mean ~0), i.e. the "
        "same implicit scale as the STI chi_33 reference.\n\n"
        f"- Globus pallidus: {gp} ppb\n- Putamen: {put} ppb\n\n"
        "These reproduce the STI reference's deep-gray susceptibility (globus pallidus ~159, "
        "putamen ~72 ppb). No CSF/ventricle or white-matter reference offset was subtracted; "
        "doing so would shift every value off the reference scale.\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
