"""Proof-of-work grading for WMMD-001 (white-matter mean diffusivity, CFIN multi-b).

Genre: REPRODUCTION (QSMDIPOLE-001 model) -- the un-cued judgement (how to model the wide
multi-b signal) is graded by the VALUE reproducing the unbiased MD, not by an over-claim
write-up. See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz): the per-voxel MD map (in 1e-3 mm^2/s) over the fixed
WM ROI (~10 105 voxels; brain mask & low-b FA>0.5), for each diffusion-model config:

    DKI, all shells (unbiased)          MD = 0.883   <- reference / oracle
    DTI, b<=1000 only (also unbiased)   MD = 0.801   <- alt-correct
    DTI, ALL shells (naive, biased low) MD = 0.585   <- absorbs high-b non-Gaussian curvature

Over this wide acquisition (b up to 3000) the diffusion-weighted signal departs from a single
mono-exponential; a plain tensor over the full b-range absorbs that curvature into an
artificially LOW apparent diffusivity. The diffusion-kurtosis tensor (its b->0 limit) or a
low-b tensor recovers the unbiased MD. Because the per-voxel reference is held out, a passing
submission is impossible without actually fitting an unbiased model on the real data.

Three pillars:
  1. the submitted per-voxel MD table covers the real ROI, is non-constant, and its per-voxel
     values match the real reference of SOME model config (r>=0.75) -- a fabricated/constant/
     guessed table matches none;
  2. the ROI mean recomputed from the rows equals the reported md_mean AND reproduces the
     UNBIASED reference band (0.72-1.03) -- a DTI-over-all-shells value (~0.585) is out of band;
  3. (secondary) findings.md reports an MD consistent with the headline.
"""
import numpy as np

from proof_of_work import (
    OUT, load_reference, load_voxel_table, align, best_corr, nonconstant,
    load_json, walk_numbers, findings_text,
)

REF = load_reference()
ST = REF["stats"]
CFG_MEAN = {k: float(v) for k, v in ST["mean_by_config"].items()}
MD_DKI = CFG_MEAN["dki_all"]; MD_LOWB = CFG_MEAN["dti_lowb"]; MD_NAIVE = CFG_MEAN["dti_all"]

PLAUS_LO, PLAUS_HI = 0.3, 1.3
COVER = 0.5
CORR = 0.75                     # anti-fabrication: matches SOME real config's per-voxel map
UNBIASED_LO, UNBIASED_HI = 0.72, 1.03   # accepts DKI 0.883 & low-b DTI 0.801; rejects DTI-all 0.585
CONSIST = 0.05

MD_KEYS = ("md_mean", "mdmean", "mean_md", "meanmd", "md", "mean_diffusivity",
           "meandiffusivity", "md_wm", "wm_md")


def _submitted_md():
    sub = load_voxel_table("md_voxelwise.csv", value_hints=("md", "diffus"))
    v = np.array(list(sub.values()), float)
    scale = 1e3 if (np.isfinite(v).any() and np.nanmedian(np.abs(v)) < 0.02) else 1.0
    return {k: val * scale for k, val in sub.items()}


def _reported_md():
    for name in ("diffusivity.json", "results.json", "run_metadata.json"):
        obj = load_json(name)
        if not obj:
            continue
        for k, v in walk_numbers(obj):
            key = str(k).lower().replace(" ", "").replace("-", "_") if k else ""
            if key in MD_KEYS:
                val = v * 1e3 if abs(v) < 0.02 else v
                if PLAUS_LO <= val <= PLAUS_HI:
                    return val
    return None


def test_voxel_table_matches_real_reference():
    smap = _submitted_md()
    assert nonconstant(smap.values()), (
        "md_voxelwise.csv is (near-)constant across voxels; a real per-voxel MD map is not "
        "constant -- looks fabricated/duplicated")
    cover, paired, _ = align(smap, REF)
    assert cover >= COVER, (
        f"md_voxelwise.csv covers only {cover:.0%} of the {len(REF['ijk'])} pinned WM ROI voxels "
        f"(need >= {COVER:.0%}); the real ROI must be analysed, not a fabricated voxel set")
    r, who = best_corr(paired)
    assert r >= CORR, (
        f"the submitted per-voxel MD values do not match the real reference of any diffusion "
        f"model config (best r = {r:.2f} to '{who}', need >= {CORR}); the per-voxel MD map is "
        f"reproducible only by actually fitting a diffusion model on the real CFIN data")


def test_reproduces_unbiased_md():
    """The headline check (QSMDIPOLE model): the ROI mean recomputed from the rows must equal
    the reported md_mean AND land in the UNBIASED band. DKI-all (0.883) and low-b DTI (0.801)
    pass; DTI over ALL shells (0.585) is out of band -- it absorbs the high-b non-Gaussian
    curvature and underestimates MD."""
    smap = _submitted_md()
    vals = np.array([v for v in smap.values() if np.isfinite(v)])
    recomputed = float(np.mean(vals))
    headline = _reported_md()
    assert headline is not None, "no md_mean headline found in diffusivity.json"
    assert abs(headline - recomputed) <= CONSIST, (
        f"the reported md_mean {headline:.3f} does not match the mean of the submitted per-voxel "
        f"table {recomputed:.3f} (tol {CONSIST}); the headline must be the mean of its own rows")
    assert UNBIASED_LO <= recomputed <= UNBIASED_HI, (
        f"the WM mean diffusivity {recomputed:.3f} (1e-3 mm^2/s) is not the unbiased value: it is "
        f"outside [{UNBIASED_LO}, {UNBIASED_HI}]. A plain diffusion tensor fit over the full "
        f"b-range (up to 3000) absorbs the high-b non-Gaussian signal curvature and "
        f"underestimates MD (~{MD_NAIVE:.3f}); use the diffusion-kurtosis tensor (its b->0 limit, "
        f"~{MD_DKI:.3f}) or restrict the tensor to the low-b shells (b<=1000, ~{MD_LOWB:.3f}).")


def test_findings_consistent():
    """Secondary: findings.md reports a mean diffusivity consistent with the headline."""
    text = findings_text()
    assert text.strip(), "findings.md is missing or empty"
    import re
    nums = [float(x) for x in re.findall(r"([01]?\.\d{2,})", text)]
    headline = _reported_md()
    assert headline is not None
    assert any(abs(n - headline) <= 0.06 for n in nums), (
        f"findings.md does not report a mean diffusivity consistent with the headline "
        f"{headline:.3f} (1e-3 mm^2/s)")
