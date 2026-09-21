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
config (r>=0.80); (2) ROI mean recomputes to the reported FA and a physically real FA (with a
generous UPPER margin so an honest free-water-corrected FA at the top of the band passes);
(3) the free-water dependence forced as un-fabricable PER-VOXEL WORK: fa_sweep.csv must hold the
per-voxel FA for >=2 models, each a REAL per-voxel fit matching one held-out config's pattern
(r >= 0.80) AND its ROI-mean FA, at DISTINCT configs INCLUDING the free-water-corrected model,
spanning the real deflation. The corrected (higher tissue FA) and naive (single-tensor,
CSF-deflated) estimates must both be PRESENT and differ by the real amount -- a single FA, a
guessed/fabricated sweep, or a rescaled copy of one fit cannot pass. The lever (free water / CSF
partial volume) is never named.
"""
import re

import numpy as np

from proof_of_work import (
    OUT, load_reference, load_voxel_table, align, best_corr, mean_in_range, nonconstant,
    load_json, walk_numbers, load_sweep_table, validate_sweep,
)

REF = load_reference()
ST = REF["stats"]
CFG_MEAN = {k: float(v) for k, v in ST["mean_by_config"].items()}

PLAUS_LO, PLAUS_HI = 0.1, 0.9
COVER = 0.5
CORR = 0.80
# Upper-band-ceiling fairness (SECOND_PASS_BRIEF): the corrected free-water FA sits at the top of
# the config band (0.617) and an honest fwDTI can run ~+10% high; the sanity range must admit an
# honest value at the upper edge, so the margin is generous (pillar 1's per-voxel pattern match,
# not this coarse range, is the fabrication gate).
RANGE_MARGIN = 0.10
CONSIST = 0.03
# --- free-water SWEEP (per-voxel-backed) tolerances ---
SWEEP_MEAN_TOL = 0.08          # each sweep group's ROI-mean FA vs its matched config's mean;
                               #   admits an honest fwDTI ~+10% high (< the 0.09 fwdti-vs-DTI gap,
                               #   so a rescaled/shifted single-tensor map cannot pass as fwdti)
SWEEP_MIN_SPREAD = 0.06        # fwDTI (0.617) vs single-tensor (0.527/0.427); closest gap 0.09
CORRECTED_CONFIG = "fwdti"     # the free-water-corrected config label in the held-out reference

FA_KEYS = ("fa_periventricular_wm", "faperiventricularwm", "fa_mean", "famean", "mean_fa",
           "meanfa", "fa", "fractional_anisotropy", "fa_pv", "fa_wm")


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


def test_freewater_sweep_matches_reference():
    """The un-cued discriminating judgement, forced as un-fabricable per-voxel work: these
    periventricular voxels are CSF partial-volume contaminated, so the FA depends on whether the
    free-water compartment is modelled (a single tensor conflates the fast isotropic CSF signal
    and DEFLATES FA). The submission must report `fa_sweep.csv`, the per-voxel FA under each model
    it evaluates, and among those groups the free-water-corrected model AND >=1 single-tensor
    model must each be a REAL per-voxel fit -- matching one held-out config's FA pattern
    (r >= 0.80) AND its ROI-mean FA -- at DISTINCT configs whose means span the real deflation.
    This forces the analyst to actually run the free-water-corrected model (higher tissue FA)
    alongside the naive single tensor -- both PRESENT and differing by the real amount -- rather
    than report a single FA as 'the' periventricular FA, or guess the corrected value. A
    fabricated group matches no config; a rescaled/shifted copy of one single-tensor fit still
    best-correlates with the SAME config (r is scale/shift-invariant) and its shifted mean no
    longer matches -> a single fit cannot fake the free-water dependence, and cannot fake the
    corrected model (which requires actually estimating the free-water compartment per voxel).

    The instruction asks for FA 'under each diffusion model you evaluate' -- a neutrally described
    robustness table; it does NOT name free water, fwDTI, CSF partial volume, or which model is
    correct."""
    groups = load_sweep_table("fa_sweep.csv", key_hints=("model", "method", "estimator", "recon",
                              "config", "fit", "algo"), value_hints=("fa", "anisotrop"))
    assert len(groups) >= 2, (
        f"fa_sweep.csv evaluates only {len(groups)} diffusion model(s); report the per-voxel FA "
        f"under >=2 models over the same ROI so the model dependence is shown, not a single FA "
        f"as 'the' periventricular FA.")
    ok, info = validate_sweep(
        groups, REF, CORR, COVER, SWEEP_MEAN_TOL, SWEEP_MIN_SPREAD, min_groups=2,
        require_config=CORRECTED_CONFIG)
    assert ok, (
        f"the model sweep in fa_sweep.csv is not a real per-voxel diffusion sweep of this ROI: "
        f"{info['n_valid']} group(s) matched a real model config's per-voxel pattern+mean across "
        f"{info['n_configs']} distinct config(s) {info.get('configs')}, spanning {info['span']:.3f} "
        f"FA (need >=2 groups at >=2 distinct configs incl. the free-water-corrected model, "
        f"spanning >= {SWEEP_MIN_SPREAD}). Each model's per-voxel FA must reproduce a held-out fit "
        f"(Pearson r >= {CORR} AND ROI-mean FA within {SWEEP_MEAN_TOL} of that config); a single FA, "
        f"a fabricated/guessed sweep, or a rescaled copy of one fit cannot reproduce the real "
        f"free-water dependence ({sorted(round(v,3) for v in CFG_MEAN.values())}). The corrected "
        f"model recovers a materially HIGHER tissue FA than the single tensor.")
