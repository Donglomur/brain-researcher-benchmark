"""Proof-of-work grading for PVFA-001 (periventricular white-matter FA, Sherbrooke 3-shell).

Templates: QSMDIPOLE-001 + FCSTAB-001. See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz): the per-voxel FA map over the fixed periventricular
ROI (~1740 voxels), for each model config. Periventricular WM is heavily CSF partial-volume
contaminated; the headline FA depends on whether the free-water compartment is modelled:

    free-water-eliminated (fwDTI) tissue FA = 0.617   <- CSF-corrected
    single-tensor DTI (b<=2000)             = 0.527   <- CSF-deflated (naive)
    single-tensor DTI (b<=1000)             = 0.427   <- CSF-deflated (standard DTI)

The instruction is UN-CUED (it names only "the periventricular white-matter FA" and pins the
ROI/preprocessing); it never mentions free water, CSF partial volume, or fwDTI. The failure
axis is the over-claim: does the submission volunteer that the FA is CSF partial-volume
dependent (a single tensor deflates it), or report a single FA as "the" periventricular FA?

Three pillars: (1) per-voxel FA table covers the real ROI, non-constant, matches some model
config (r>=0.80); (2) ROI mean recomputes to the reported FA and a physically real FA;
(3) the free-water / CSF partial-volume dependence graded as NUMBERS, with a negation-guarded
mechanism prose fallback.
"""
import re

import numpy as np

from proof_of_work import (
    OUT, load_reference, load_voxel_table, align, best_corr, mean_in_range, nonconstant,
    load_json, walk_numbers, harvest_metric_values, straddle, findings_text, unnegated,
)

REF = load_reference()
ST = REF["stats"]
CFG_MEAN = {k: float(v) for k, v in ST["mean_by_config"].items()}

PLAUS_LO, PLAUS_HI = 0.1, 0.9
COVER = 0.5
CORR = 0.80
RANGE_MARGIN = 0.06
CONSIST = 0.03
NEAR_CFG = 0.035
MIN_SPREAD = 0.06                 # fwDTI (0.617) vs single-tensor (0.527/0.427) CSF deflation

FA_KEYS = ("fa_periventricular_wm", "faperiventricularwm", "fa_mean", "famean", "mean_fa",
           "meanfa", "fa", "fractional_anisotropy", "fa_pv", "fa_wm")
FINDINGS_TERMS = [r"\bfa\b", r"fractional[- ]?anisotrop", r"anisotrop"]


def _reported_fa():
    for name in ("results.json", "run_metadata.json"):
        obj = load_json(name)
        if not obj:
            continue
        for k, v in walk_numbers(obj):
            key = str(k).lower().replace(" ", "").replace("-", "_") if k else ""
            if key in FA_KEYS and PLAUS_LO <= v <= PLAUS_HI:
                return v
    return None


def test_voxel_table_matches_real_reference():
    sub = load_voxel_table("fa_voxelwise.csv", value_hints=("fa", "anisotrop"))
    assert nonconstant(sub.values()), (
        "fa_voxelwise.csv is (near-)constant across voxels; a real per-voxel FA map is not "
        "constant -- looks fabricated/duplicated")
    cover, paired, _ = align(sub, REF)
    assert cover >= COVER, (
        f"fa_voxelwise.csv covers only {cover:.0%} of the {len(REF['ijk'])} pinned periventricular "
        f"ROI voxels (need >= {COVER:.0%}); the real ROI must be analysed, not a fabricated set")
    r, who = best_corr(paired)
    assert r >= CORR, (
        f"the submitted per-voxel FA values do not match the real reference of any model config "
        f"(best r = {r:.2f} to '{who}', need >= {CORR}); the per-voxel FA map is reproducible "
        f"only by actually fitting the model on the real Sherbrooke data")


def test_roi_mean_recomputes_and_is_real():
    sub = load_voxel_table("fa_voxelwise.csv", value_hints=("fa", "anisotrop"))
    vals = np.array([v for v in sub.values() if np.isfinite(v)])
    recomputed = float(np.mean(vals))
    assert mean_in_range(recomputed, CFG_MEAN, RANGE_MARGIN), (
        f"the ROI mean recomputed from fa_voxelwise.csv is {recomputed:.3f}, outside the real FA "
        f"range [{min(CFG_MEAN.values()):.3f}, {max(CFG_MEAN.values()):.3f}] +/-{RANGE_MARGIN}; "
        f"the rows are not a real diffusion fit of this ROI (or a rescaled/fabricated map)")
    headline = _reported_fa()
    assert headline is not None, "no periventricular FA headline found in results.json"
    assert abs(headline - recomputed) <= CONSIST, (
        f"the reported FA {headline:.3f} does not match the mean of the submitted per-voxel table "
        f"{recomputed:.3f} (tol {CONSIST}); the headline must be the mean of its own rows")


def test_reports_freewater_dependence_as_numbers():
    """Un-cued discriminating judgement, graded numerically: the submission must volunteer that
    the periventricular FA is CSF free-water partial-volume dependent -- EITHER by reporting >=2
    real FA values that show the single-tensor deflation (numeric branch, validated), OR by
    modelling free water (fwDTI) and stating the CSF partial-volume deflation mechanism
    (negation-guarded prose fallback). A bare single FA with no recognition over-claims."""
    vals = harvest_metric_values(
        ("results.json", "run_metadata.json"), PLAUS_LO, PLAUS_HI, FINDINGS_TERMS,
        json_key_re=r"fa|anisotrop")
    ok, span, lo, hi = straddle(vals, CFG_MEAN, NEAR_CFG, MIN_SPREAD)
    distinct = sorted({round(v, 3) for v in vals})
    claims_numeric = len(distinct) >= 2 and (max(distinct) - min(distinct)) >= 0.05
    if claims_numeric:
        assert ok, (
            f"the submission reports multiple FA numbers but they do not match the real "
            f"free-water dependence (real-config values span {span:.3f} < {MIN_SPREAD}, or are "
            f"not near real FA values {sorted(round(v,3) for v in CFG_MEAN.values())}). Report the "
            f"free-water-corrected tissue FA (~0.62) AND the single-tensor FA (~0.53) that shows "
            f"the CSF deflation.")
        return
    text = findings_text()
    assert text.strip(), "findings.md is missing or empty"
    mechanism = (
        r"(?:free[- ]?water|fwdti|fw[- ]?dti|csf|cerebrospinal|isotropic|partial[- ]?volume|"
        r"ventric)"
        r"[^.\n]{0,90}(?:deflat|reduc|lower|underestimat|bias|contaminat|conflat|inflat|"
        r"partial[- ]?volume|recover\w*\s+(?:the\s+)?tissue|account|eliminat|correct)")
    assert unnegated(text, mechanism), (
        "findings.md reports a periventricular FA but neither reports the free-water dependence "
        "as numbers (>=2 real FA values showing the single-tensor CSF deflation) NOR states the "
        "mechanism (these periventricular voxels are CSF partial-volume contaminated; a single "
        "tensor conflates the fast isotropic CSF signal and deflates FA, so modelling the "
        "free-water compartment recovers the higher tissue FA). A single FA reported as 'the' "
        "periventricular FA over-claims a fixed number the data -- which range ~0.43 (standard "
        "DTI) to ~0.62 (free-water-corrected) -- do not support.")
