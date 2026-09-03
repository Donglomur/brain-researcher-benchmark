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
~6 ppb (globus pallidus 153, putamen 78). Validated on real data (mean OR median, pinned reg):

  reference, native scale, median   GP 153 / PUT 78   -> PASS
  reference, native scale, mean     GP 151 / PUT 75   -> PASS
  CSF/ventricle-referenced (offset ~14 ppb) GP 139 / PUT 64  -> FAIL (did not follow the pinned
                                                                  native-scale referencing)
  white-matter re-reference (+19 ppb)       GP 173 / PUT 97  -> FAIL
  differently-regularized inversion (plain Tikhonov) GP 98 / PUT 50  -> FAIL (wrong recipe)

Because the STI reference itself is held out, the reported values can only land near the targets
by actually reconstructing with the pinned recipe on the correct scale (they cannot be guessed).
The grader therefore passes any correct-referenced reconstruction of the pinned recipe (mean or
median) and fails a wrong recipe or a report re-referenced off the pinned native scale.
"""
import csv
import json
import os
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# STI chi_33 reference (ppb), by nucleus label.
TARGET_PPB = {3: ("globus_pallidus", 158.8), 2: ("putamen", 72.2)}
TOL_PPB = 12.0   # passes any faithful recipe implementation (native ~5-8 ppb off the STI ref);
#                  fails a CSF (~14 ppb) or WM (~20-40 ppb) re-reference and any other inversion.


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
    import numpy as np
    p = OUT / "susceptibility_ppm.npy"
    assert p.exists(), f"missing reconstructed susceptibility map {p}"
    chi = np.load(p)
    assert chi.shape == (160, 160, 160), f"expected a 160^3 susceptibility map, got {chi.shape}"
    finite = chi[np.isfinite(chi)]
    assert finite.size > 0 and np.ptp(finite) > 0.05, (
        "susceptibility map has no dynamic range — no real reconstruction was produced")


def test_reproduces_sti_reference_deep_gray():
    # The headline check: the reported deep-gray susceptibilities must reproduce the held-out STI
    # chi_33 reference. The instruction pins the recipe AND the native-scale referencing, so any
    # faithful reconstruction (mean or median, reg=0.09, native scale) passes; a report re-
    # referenced to CSF/ventricles or white matter, or produced by a different inversion, does not
    # — its globus-pallidus value in particular lands well outside tolerance.
    vals = _by_label(_rows())
    misses = []
    for lab, (name, target) in TARGET_PPB.items():
        err = abs(vals[lab] - target)
        if err > TOL_PPB:
            misses.append(f"{name}: reported {vals[lab]:.1f} ppb vs STI reference {target:.1f} ppb "
                          f"(off by {err:.1f} > {TOL_PPB:.0f} ppb)")
    assert not misses, (
        "reported deep-gray susceptibility does not reproduce the STI chi_33 reference: "
        + "; ".join(misses)
        + ". Follow the pinned recipe (closed-form L2 with reg=0.09) and report on the native "
        "scale as instructed — the same scale as the STI reference — without subtracting a "
        "CSF/ventricle or white-matter reference offset.")
