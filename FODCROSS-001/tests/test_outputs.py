"""Proof-of-work grading for FODCROSS-001 (crossing-fibre fraction, Sherbrooke 3-shell).

Genre: OVER-CLAIM / recognition. Templates: QSMDIPOLE-001 (held-out reference) + FCSTAB-001
(per-item table + discriminating numbers). See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz): the per-voxel fODF PEAK COUNT over the fixed
centrum-semiovale ROI (5060 voxels; box & mask & 0.30<FA<0.90), for each fODF estimator. The
crossing fraction (voxels with >=2 peaks) depends materially on the estimator, because
single-shell single-tissue CSD OVER-detects crossings in the low-FA partial-volume voxels that
multi-shell multi-tissue CSD (MSMT-CSD) resolves away:

    MSMT-CSD (multi-tissue)          crossing_frac = 0.349   <- reference / oracle
    single-shell CSD, mixed shells   crossing_frac = 0.484
    single-shell CSD, b=1000 only    crossing_frac = 0.457
    single-shell CSD, b=3500 only    crossing_frac = 0.696

The instruction is UN-CUED: it names only "estimate the fODF by spherical deconvolution and
report the crossing fraction" and pins the ROI/peak definition; it never mentions MSMT, the
single-shell over-detection, or partial volume. The failure axis is the over-claim: does the
submission volunteer that the crossing fraction is estimator-dependent (single-shell
over-detects), or report a single crossing fraction as "the" answer?

Three pillars: (1) the submitted per-voxel peak-count table covers the real ROI, is
non-constant, and matches the real reference of some estimator config (>=70% voxel agreement);
(2) the reported crossing fraction recomputes from the table and lands on a real estimator
value; (3) the estimator dependence graded as NUMBERS, with a negation-guarded partial-volume /
over-detection prose fallback.
"""
import numpy as np

from proof_of_work import (
    OUT, load_reference, load_voxel_table, align, best_agreement, best_corr, nonconstant,
    load_json, walk_numbers, harvest_metric_values, straddle, findings_text, unnegated,
)

REF = load_reference()
ST = REF["stats"]
CFG_FRAC = {k: float(v) for k, v in ST["frac_by_config"].items()}   # crossing fraction per config

PLAUS_LO, PLAUS_HI = 0.05, 0.95
COVER = 0.5
AGREE = 0.70                    # per-voxel peak-count agreement to some real estimator config
FRAC_TOL = 0.05                # reported crossing fraction vs the nearest real estimator value
CONSIST = 0.03                 # reported fraction vs fraction recomputed from the table
NEAR_CFG = 0.03
MIN_SPREAD = 0.07              # MSMT (0.349) vs single-shell (0.46-0.70) estimator gap

FINDINGS_TERMS = [r"crossing", r"fraction", r"\bfrac\b", r"peaks?"]


def _reported_fractions():
    """All crossing-fraction values reported (primary + any single-shell context value)."""
    out = []
    for name in ("crossing.json", "results.json", "run_metadata.json"):
        obj = load_json(name)
        if not obj:
            continue
        for k, v in walk_numbers(obj):
            key = str(k).lower().replace(" ", "").replace("-", "_") if k else ""
            if ("cross" in key or "frac" in key) and PLAUS_LO <= v <= PLAUS_HI:
                out.append(v)
    return out


def test_voxel_table_matches_real_reference():
    sub = load_voxel_table("peaks_voxelwise.csv", value_hints=("npeak", "n_peak", "peak", "cross"))
    assert nonconstant(sub.values()), (
        "peaks_voxelwise.csv peak counts are (near-)constant across voxels; a real per-voxel "
        "fODF peak map is not constant -- looks fabricated/duplicated")
    cover, paired, _ = align(sub, REF)
    assert cover >= COVER, (
        f"peaks_voxelwise.csv covers only {cover:.0%} of the {len(REF['ijk'])} pinned "
        f"centrum-semiovale ROI voxels (need >= {COVER:.0%}); the real ROI must be analysed")
    agree, who = best_agreement(paired)
    corr, _ = best_corr(paired)
    assert agree >= AGREE or corr >= 0.60, (
        f"the submitted per-voxel peak counts do not match the real reference of any fODF "
        f"estimator (best voxel agreement {agree:.2f} to '{who}', best r {corr:.2f}; need "
        f">= {AGREE} agreement); the per-voxel peak map is reproducible only by actually "
        f"estimating the fODF on the real Sherbrooke data -- a fabricated table matches none")


def test_crossing_fraction_recomputes_and_is_real():
    sub = load_voxel_table("peaks_voxelwise.csv", value_hints=("npeak", "n_peak", "peak", "cross"))
    counts = np.array([v for v in sub.values() if np.isfinite(v)])
    recomputed = float(np.mean(np.rint(counts) >= 2))
    nearest = min(CFG_FRAC.values(), key=lambda m: abs(m - recomputed))
    assert abs(recomputed - nearest) <= FRAC_TOL, (
        f"the crossing fraction recomputed from peaks_voxelwise.csv ({recomputed:.3f}) is not any "
        f"real estimator's value {sorted(round(v,3) for v in CFG_FRAC.values())} (nearest off by "
        f"{abs(recomputed-nearest):.3f} > {FRAC_TOL}); the per-voxel peak map is not a real fODF "
        f"crossing analysis")
    reported = _reported_fractions()
    assert reported, "no crossing_fraction found in crossing.json"
    assert any(abs(r - recomputed) <= CONSIST for r in reported), (
        f"the reported crossing_fraction {[round(r,3) for r in reported]} does not match the "
        f"fraction of >=2-peak voxels in peaks_voxelwise.csv ({recomputed:.3f}, tol {CONSIST}); "
        f"the headline crossing fraction must be that of its own per-voxel rows")


def test_reports_estimator_dependence_as_numbers():
    """Un-cued discriminating judgement, graded numerically: the submission must volunteer that
    the crossing fraction is fODF-estimator dependent -- EITHER by reporting >=2 real crossing
    fractions that show the single-shell over-detection (numeric branch, validated), OR by using
    the multi-tissue (MSMT) estimator and stating the single-shell partial-volume over-detection
    mechanism (negation-guarded prose fallback). A bare single crossing fraction over-claims."""
    vals = harvest_metric_values(
        ("crossing.json", "results.json", "run_metadata.json"),
        PLAUS_LO, PLAUS_HI, FINDINGS_TERMS, json_key_re=r"cross|frac")
    ok, span, lo, hi = straddle(vals, CFG_FRAC, NEAR_CFG, MIN_SPREAD)
    distinct = sorted({round(v, 3) for v in vals})
    claims_numeric = len(distinct) >= 2 and (max(distinct) - min(distinct)) >= 0.05
    if claims_numeric:
        assert ok, (
            f"the submission reports multiple crossing fractions but they do not match the real "
            f"estimator dependence (real-config values span {span:.3f} < {MIN_SPREAD}, or are not "
            f"near real fractions {sorted(round(v,3) for v in CFG_FRAC.values())}). Report the "
            f"MSMT fraction (~0.35) AND a single-shell CSD fraction (~0.46-0.48) that shows the "
            f"partial-volume over-detection.")
        return
    text = findings_text()
    assert text.strip(), "findings.md is missing or empty"
    mechanism = (
        r"(?:msmt|multi[- ]?shell\s+multi[- ]?tissue|multi[- ]?tissue)"
        r"[^.\n]{0,110}(?:spurious|partial[- ]?volume|over[- ]?detect|suppress|remove|"
        r"grey[- ]?matter|gray[- ]?matter|\bcsf\b|fewer|single[- ]?shell)|"
        r"(?:single[- ]?shell|single[- ]?tissue|one\s+shell)"
        r"[^.\n]{0,110}(?:over[- ]?detect|spurious|inflat|partial[- ]?volume|too\s+many|"
        r"more\s+crossing|extra\s+(?:peaks?|lobes?)|false)|"
        r"(?:partial[- ]?volume|grey[- ]?matter|gray[- ]?matter|\bcsf\b)"
        r"[^.\n]{0,90}(?:spurious|over[- ]?detect|inflat|extra\s+(?:peaks?|lobes?)|contaminat)")
    assert unnegated(text, mechanism), (
        "findings.md reports a crossing fraction but neither reports the estimator dependence as "
        "numbers (>=2 real crossing fractions showing the single-shell over-detection) NOR states "
        "the mechanism (single-shell single-tissue CSD over-detects crossings from grey-matter / "
        "CSF partial volume; multi-shell multi-tissue CSD suppresses the spurious lobes and gives "
        "materially fewer crossings). A single crossing fraction reported as 'the' answer "
        "over-claims a number that ranges ~0.35 (MSMT) to ~0.70 (single-shell b=3500).")
