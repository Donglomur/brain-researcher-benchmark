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
value; (3) the estimator dependence forced as un-fabricable PER-VOXEL WORK: peaks_sweep.csv must
hold the per-voxel peak count for >=2 estimators, each a REAL per-voxel fit matching one held-out
config's pattern (voxel agreement >= 0.70) AND its crossing fraction, at DISTINCT configs
INCLUDING the corrected multi-tissue estimator, spanning the real estimator gap. The corrected
(materially fewer crossings) and naive (single-shell over-detected) estimates must both be
PRESENT and differ by the real amount -- a single fraction, a guessed/fabricated sweep, or a
relabelled copy of one fit cannot pass. The lever (MSMT / partial-volume) is never named.
"""
import numpy as np

import numpy as _np

from proof_of_work import (
    OUT, load_reference, load_voxel_table, align, best_agreement, best_corr, nonconstant,
    load_json, walk_numbers, load_sweep_table, validate_sweep,
)

REF = load_reference()
ST = REF["stats"]
CFG_FRAC = {k: float(v) for k, v in ST["frac_by_config"].items()}   # crossing fraction per config

PLAUS_LO, PLAUS_HI = 0.05, 0.95
COVER = 0.5
AGREE = 0.70                    # per-voxel peak-count agreement to some real estimator config
FRAC_TOL = 0.05                # reported crossing fraction vs the nearest real estimator value
CONSIST = 0.03                 # reported fraction vs fraction recomputed from the table
# --- estimator SWEEP (per-voxel-backed) tolerances ---
SWEEP_FRAC_TOL = 0.06          # each sweep group's crossing fraction vs its matched config's
SWEEP_MIN_SPREAD = 0.07        # >=2 real fits at DISTINCT estimators must span this (MSMT 0.349
                               #   vs single-shell 0.46-0.70; closest gap MSMT-vs-b1000 = 0.108)
CORRECTED_CONFIG = "msmt"      # the corrected estimator's config label in the held-out reference


def _crossing_frac(vals):
    return float(_np.mean(_np.rint(_np.asarray(vals, float)) >= 2))


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


def test_estimator_sweep_matches_reference():
    """The un-cued discriminating judgement, forced as un-fabricable per-voxel work: the crossing
    fraction is fODF-ESTIMATOR dependent (single-shell single-tissue CSD over-detects the
    partial-volume crossings that multi-shell multi-tissue CSD resolves away). The submission must
    report `peaks_sweep.csv`, the per-voxel fODF peak count under each estimator it evaluates, and
    among those groups the CORRECTED (multi-tissue) estimator AND >=1 other (single-shell) must
    each be a REAL per-voxel fit -- matching one held-out estimator config's peak-count pattern
    (voxel agreement >= AGREE) AND that config's crossing fraction -- at DISTINCT configs whose
    fractions span the real estimator gap. This forces the analyst to actually run the corrected
    estimator (materially fewer crossings) alongside the naive one -- both PRESENT and differing
    by the real amount -- rather than report a single crossing fraction as 'the' answer, or guess
    the corrected value. A fabricated group matches no config; a relabelled/flipped copy of one
    fit best-agrees the SAME config and its shifted fraction no longer matches -> a single fit
    cannot fake the estimator dependence.

    The instruction asks for peak counts 'under each fODF estimator you evaluate' -- a neutrally
    described robustness table; it does NOT name MSMT, single-shell over-detection, or partial
    volume."""
    groups = load_sweep_table("peaks_sweep.csv", key_hints=("estimator", "method", "model",
                              "fodf", "recon", "config", "algo"),
                              value_hints=("npeak", "n_peak", "peak", "cross"))
    assert len(groups) >= 2, (
        f"peaks_sweep.csv evaluates only {len(groups)} fODF estimator(s); report the per-voxel "
        f"peak count under >=2 estimators so the estimator dependence is shown, not a single "
        f"crossing fraction as 'the' answer.")
    ok, info = validate_sweep(
        groups, REF, AGREE, COVER, SWEEP_FRAC_TOL, SWEEP_MIN_SPREAD, min_groups=2,
        agg=_crossing_frac, matcher=best_agreement, require_config=CORRECTED_CONFIG)
    assert ok, (
        f"the estimator sweep in peaks_sweep.csv is not a real per-voxel fODF sweep of this ROI: "
        f"{info['n_valid']} group(s) matched a real estimator config's per-voxel pattern+fraction "
        f"across {info['n_configs']} distinct config(s) {info.get('configs')}, spanning "
        f"{info['span']:.3f} crossing-fraction (need >=2 groups at >=2 distinct configs incl. the "
        f"corrected multi-tissue estimator, spanning >= {SWEEP_MIN_SPREAD}). Each estimator's "
        f"per-voxel peak counts must reproduce a held-out fODF fit (voxel agreement >= {AGREE} AND "
        f"crossing fraction within {SWEEP_FRAC_TOL} of that config); a single crossing fraction, a "
        f"fabricated/guessed sweep, or a relabelled copy of one fit cannot reproduce the real "
        f"estimator dependence ({sorted(round(v,3) for v in CFG_FRAC.values())}). The corrected "
        f"(multi-tissue) estimator gives materially FEWER crossings than single-shell CSD.")
