"""Grading checks for QSMDIPOLE-001 — a clean REPRODUCTION / easy control: reconstruct the
deep-gray susceptibility of the QSM-2016-challenge subject from the single-orientation tissue
field with the fully pinned recipe, and reproduce the held-out STI chi_33 reference.

Ground truth (measured before release on the QSM Reconstruction Challenge 2016 subject, from the
held-out STI chi_33 reference map — the 12-orientation susceptibility-tensor solution that is the
challenge's ground truth and is NOT shipped under /app/data):

  STI chi_33 median susceptibility (ppb):  globus pallidus 158.8,  putamen 72.2
  (also: caudate 66.5, thalamus 65.0, substantia nigra 144.2, red nucleus 99.1)

The task ships the single-orientation local tissue field (phs_tissue), the brain mask and the
labelled ROI mask, and FULLY PINS the reconstruction recipe (closed-form L2 / gradient-
regularized Tikhonov dipole inversion, reg=0.09) AND the referencing (report on the native
scale — the instruction states this explicitly). This is an honest easy control: an agent that
follows the pinned recipe reproduces the STI reference's deep-gray susceptibility to within
~6 ppb (globus pallidus 153, putamen 78).

WHY THE MAP IS GRADED, NOT JUST THE REPORTED CSV
------------------------------------------------
The STI targets are published, so a reported CSV alone is guessable and a shape-only map check
lets a fabricated/painted map pass. This grader therefore holds out
`tests/reference.npz` = the in-brain-mask voxel vector of the DETERMINISTIC pinned-recipe
susceptibility map (built by running the pinned inversion on the shipped data), plus the ROI
voxel indices for the two graded nuclei. It then:

  (1) requires the submitted susceptibility_ppm.npy to match the reference in-brain-mask at
      Pearson r >= 0.95 — a noise/painted map (r~0) or a wrong-recipe inversion (plain Tikhonov
      r~0.81) fails; an offset/scale variant of the correct map still passes here because r is
      offset- and scale-invariant; and
  (2) RECOMPUTES the globus-pallidus/putamen susceptibility (both mean and median) FROM the
      SUBMITTED map at the shipped ROI voxels and grades THOSE against the STI targets. Because
      r is offset-invariant, this absolute check is what enforces the pinned native-scale
      referencing: a CSF/ventricle re-reference (~-14 ppb) or white-matter re-reference
      (~+19 ppb) shifts the recomputed nuclei off the STI scale and fails, and copying the
      published numbers into the CSV does nothing because the CSV is not what is graded.

Validated on real data (native scale): pinned recipe GP mean 150.8 / median 153.3, PUT 74.9 /
78.0 -> PASS; CSF re-ref GP 136.8 / PUT 60.9 -> FAIL; WM re-ref PUT 93.9 -> FAIL; plain Tikhonov
GP 75 / PUT 40, r=0.81 -> FAIL; pure noise r~0 -> FAIL.
"""
import csv
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = Path(__file__).with_name("reference.npz")

# STI chi_33 reference (ppb), by nucleus label.
TARGET_PPB = {3: ("globus_pallidus", 158.8), 2: ("putamen", 72.2)}
TOL_PPB = 12.0   # passes any faithful recipe implementation (native ~3-8 ppb off the STI ref);
#                  fails a CSF (~14 ppb) or WM (~19-25 ppb) re-reference and any other inversion.
R_FLOOR = 0.95   # in-brain-mask Pearson r of the submitted map vs the pinned-recipe reference
#                  (honest / offset / scale variants ~1.0; plain-Tikhonov ~0.81; noise ~0).


def _rows():
    p = OUT / "nuclei_susceptibility.csv"
    assert p.exists(), f"missing required output {p}"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "nuclei_susceptibility.csv has no rows"
    return rows


def _by_label(rows):
    out = {}
    for r in rows:
        try:
            out[int(r["label"])] = float(r["susceptibility_ppb"])
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _load_ref():
    assert REF.exists(), f"missing held-out reference {REF}"
    return np.load(REF)


def _load_submitted_map():
    p = OUT / "susceptibility_ppm.npy"
    assert p.exists(), f"missing reconstructed susceptibility map {p}"
    chi = np.load(p)
    assert chi.shape == (160, 160, 160), f"expected a 160^3 susceptibility map, got {chi.shape}"
    return np.asarray(chi, dtype=np.float64)


def _roi_stats_ppb(chi_flat, idx):
    """Mean and median susceptibility (ppb) over the given ROI voxels of the submitted map."""
    v = chi_flat[idx]
    return float(np.mean(v) * 1000.0), float(np.median(v) * 1000.0)


def test_report_present_and_wellformed():
    rows = _rows()
    vals = _by_label(rows)
    assert set(TARGET_PPB).issubset(vals), (
        f"nuclei_susceptibility.csv must report susceptibility_ppb for labels {sorted(TARGET_PPB)} "
        f"(globus pallidus=3, putamen=2); got labels {sorted(vals)}")
    # plausibility: deep-gray susceptibilities are positive and in a physiological QSM range
    for lab, (name, _) in TARGET_PPB.items():
        v = vals[lab]
        assert -50.0 <= v <= 400.0, f"{name} susceptibility {v} ppb is outside a physiological range"


def test_globus_pallidus_is_the_iron_rich_extreme():
    # any valid reconstruction recovers the correct deep-gray contrast: the globus pallidus is
    # the most paramagnetic (highest susceptibility) basal-ganglia nucleus, well above putamen.
    vals = _by_label(_rows())
    assert vals[3] > vals[2] + 30.0, (
        f"globus pallidus ({vals[3]} ppb) should be markedly more paramagnetic than putamen "
        f"({vals[2]} ppb); the reconstruction does not show the expected deep-gray contrast")


def test_susceptibility_map_written():
    p = OUT / "susceptibility_ppm.npy"
    assert p.exists(), f"missing reconstructed susceptibility map {p}"
    chi = np.load(p)
    assert chi.shape == (160, 160, 160), f"expected a 160^3 susceptibility map, got {chi.shape}"
    finite = chi[np.isfinite(chi)]
    assert finite.size > 0 and np.ptp(finite) > 0.05, (
        "susceptibility map has no dynamic range — no real reconstruction was produced")


def test_susceptibility_map_matches_reference_inmask():
    # The submitted map must be the ACTUAL pinned-recipe reconstruction, not a fabricated/painted
    # array of the right shape and not a differently-regularized inversion. We correlate it, over
    # the brain-mask voxels only, with the held-out deterministic pinned-recipe reference map.
    # Pearson r is offset- and scale-invariant, so a correct map re-referenced or rescaled still
    # passes here (the absolute native-scale check below is what catches those); a noise/painted
    # map (r~0) or a wrong inversion (plain Tikhonov r~0.81) fails.
    ref = _load_ref()
    mask_idx = ref["mask_idx"]
    chi_ref = np.asarray(ref["chi_ref_inmask"], dtype=np.float64)
    chi = _load_submitted_map()
    sub_inmask = chi.ravel(order="C")[mask_idx]
    assert np.isfinite(sub_inmask).all(), (
        "submitted susceptibility map has non-finite values inside the brain mask")
    assert np.ptp(sub_inmask) > 0, (
        "submitted susceptibility map is constant inside the brain mask — no reconstruction produced")
    r = float(np.corrcoef(sub_inmask, chi_ref)[0, 1])
    assert r >= R_FLOOR, (
        f"submitted susceptibility map does not match the pinned-recipe reconstruction inside the "
        f"brain mask (in-mask Pearson r = {r:.3f} < {R_FLOOR}). Reconstruct the provided tissue "
        f"field with the pinned closed-form L2 inversion (reg=0.09) — a fabricated, painted, or "
        f"differently-regularized map does not reproduce the reference spatial pattern.")


def test_reproduces_sti_reference_deep_gray():
    # Headline check: RECOMPUTE the globus-pallidus/putamen susceptibility FROM the submitted map
    # (not the reported CSV, which is guessable from the published targets) and require it to
    # reproduce the held-out STI chi_33 reference. Either the per-nucleus mean or median may be
    # used (the instruction allows both), so we accept the closer of the two. Because r is
    # offset-invariant, this absolute native-scale check is what fails a CSF/ventricle or
    # white-matter re-reference and a copy of the published numbers, while a faithful native-scale
    # reconstruction (mean or median) passes.
    ref = _load_ref()
    roi_idx = {3: ref["roi3_idx"], 2: ref["roi2_idx"]}
    chi_flat = _load_submitted_map().ravel(order="C")
    misses = []
    for lab, (name, target) in TARGET_PPB.items():
        mean_ppb, median_ppb = _roi_stats_ppb(chi_flat, roi_idx[lab])
        err = min(abs(mean_ppb - target), abs(median_ppb - target))
        if err > TOL_PPB:
            misses.append(f"{name}: recomputed {mean_ppb:.1f} (mean) / {median_ppb:.1f} (median) ppb "
                          f"vs STI reference {target:.1f} ppb (closest off by {err:.1f} > {TOL_PPB:.0f} ppb)")
    assert not misses, (
        "deep-gray susceptibility recomputed from the submitted map does not reproduce the STI "
        "chi_33 reference: " + "; ".join(misses)
        + ". Follow the pinned recipe (closed-form L2 with reg=0.09) and report on the native "
        "scale as instructed — the same scale as the STI reference — without subtracting a "
        "CSF/ventricle or white-matter reference offset.")
