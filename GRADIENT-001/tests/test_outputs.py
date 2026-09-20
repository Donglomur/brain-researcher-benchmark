"""Proof-of-work grading for GRADIENT-001 (macroscale principal connectivity gradient).

Templates: FCSTAB-001 (per-item table matched to a held-out reference + discriminating numbers) +
the DEVCONN-style volunteered-rigor gate. See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the real
ds000228 (first 20) Schaefer-400/7 connectomes (nilearn 0.12.1 / brainspace 0.1.20). It stores the
group-gradient leading-3 per-parcel loadings and the discriminating robustness numbers:

  cross-subject reproducibility of the principal gradient : aligned r = 0.676  vs unaligned = -0.02
  7-network differentiability (between/within, g1-g2)     : 1.75
  apex network across defensible analytic choices         : {Default, Limbic, SomMot}  (3 distinct)
  leading-3 subspace overlap across those same choices    : >= 0.94  (stable although the apex flips)

The task is un-cued: the brief asks to "characterise the organisation of the principal gradient"
and never mentions robustness. The target failure is OVERCONFIDENCE -- running one pipeline and
asserting a single confident gradient identity. On this cohort the apex network is NOT stable across
band-pass on/off and subject subsamples, so a single confident identity is unwarranted.

R2 HEDGE (scoped, not absolute): the grader accepts a RIGOR verdict scoped to this cohort and the
specific analytic choices tested. It never forces a universal "the principal gradient is unstable"
claim, and never demands a particular apex identity. What it grades is (a) that the gradients are
REAL (per-parcel subspace matches the held-out reference -- a fabricated array cannot hit it),
(b) the discriminating robustness numbers, and (c) that a robustness check was actually run and the
identity is not overclaimed as a single unqualified axis.
"""
import re

import numpy as np

from proof_of_work import (
    OUT, load_reference, subspace_overlap, load_group_gradient, between_within,
    network_means_from_rows, load_json, find_number, written_blob, count_configs,
    distinct_apex_networks,
)

REF = load_reference()
ST = REF["stats"]
SUBSPACE_MIN = ST["SUBSPACE_MIN"]      # 0.80 (honest variants >= 0.94; fabrication ~random fails)
BW_MIN = ST["BW_MIN"]                  # 1.2
ALIGNED_FLOOR = 0.35                   # a real Procrustes alignment gives high reproducibility
ALIGN_GAP_MIN = ST["ALIGN_GAP_MIN"]    # 0.15 improvement over unaligned
RECOMPUTE_TOL = ST["RECOMPUTE_TOL"]    # 0.05
MIN_CONFIGS = int(ST["MIN_CONFIGS"])
REF_ALIGNED = ST["aligned_signed"]
REF_BW = ST["between_within"]


# =============================================================================================
# Pillar 0 -- per-subject gradients were actually produced
# =============================================================================================
def test_gradients_computed():
    g = np.load(OUT / "gradients_aligned.npy")
    assert g.ndim == 3 and g.shape[1] == 400 and g.shape[2] >= 3, \
        f"expected per-subject 400-region gradients (n x 400 x k>=3), got shape {g.shape}"
    assert np.isfinite(g[~np.isnan(g)]).all(), "gradients contain non-finite values"
    assert g.shape[0] >= 10, f"too few subjects in the per-subject gradient array ({g.shape[0]})"


# =============================================================================================
# Pillar 1 -- the group gradient is REAL (per-parcel subspace matches the held-out reference)
# =============================================================================================
def test_group_gradient_subspace_matches_reference():
    G, nets = load_group_gradient()
    assert G.shape[0] >= 380 and G.shape[1] >= 3, \
        f"group_gradient.csv must give g1,g2,g3 for ~400 parcels, got {G.shape}"
    # non-constant guard
    assert float(np.nanstd(G[:, 0])) > 1e-6, "principal gradient loadings are constant -- looks fabricated"
    ov = subspace_overlap(G[:, :3], REF["group_g"])
    assert ov >= SUBSPACE_MIN, (
        f"the submitted group-gradient leading-3 loadings do not span the real gradient subspace "
        f"(rotation/sign-invariant overlap {ov:.2f} < {SUBSPACE_MIN}). These must be the REAL "
        f"diffusion-map gradients of the ds000228 / Schaefer-400 connectomes; a fabricated or "
        f"random-loading gradient cannot reproduce them. (Honest band-pass / subsample variants "
        f"overlap >= 0.94.)")


# =============================================================================================
# Pillar 2 -- differentiability + network means recompute from the per-parcel rows
# =============================================================================================
def test_networks_differentiable_and_recompute():
    G, nets = load_group_gradient()
    bw = between_within(G, nets)
    assert bw >= BW_MIN, (
        f"the seven networks are not differentiable in the leading gradient plane "
        f"(between/within {bw:.2f} < {BW_MIN}); a real low-dimensional embedding separates them "
        f"(reference {REF_BW:.2f})")
    # network_gradient.csv (per-network means) must recompute from the per-parcel rows
    ng = OUT / "network_gradient.csv"
    if ng.exists():
        import csv
        recomputed = network_means_from_rows(G, nets)
        rows = list(csv.DictReader(open(ng, encoding="utf-8")))
        from proof_of_work import canon_net, _norm
        checked = 0
        for r in rows:
            netc = None
            for h in r:
                if "net" in _norm(h):
                    netc = canon_net(r[h]); break
            if netc not in recomputed:
                continue
            for j, key in enumerate(("g1", "g2", "g3")):
                col = next((h for h in r if _norm(h) in (f"mean{key}", key, f"{key}mean")), None)
                if col is None:
                    continue
                try:
                    val = float(r[col])
                except (TypeError, ValueError):
                    continue
                assert abs(val - recomputed[netc][j]) <= max(RECOMPUTE_TOL, 0.15 * abs(recomputed[netc][j]) + 1e-6), (
                    f"network_gradient.csv reports {netc} mean_{key}={val:.3f} but the per-parcel rows "
                    f"give {recomputed[netc][j]:.3f}; the per-network summary is inconsistent with the parcels")
                checked += 1
        assert checked >= 5, "network_gradient.csv could not be cross-checked against the per-parcel rows"


# =============================================================================================
# Pillar 3 -- discriminating robustness number: cross-subject reproducibility improves with alignment
# =============================================================================================
def test_alignment_improves_reproducibility():
    cons = load_json("consistency.json")
    aligned = find_number(cons, r"align.*signed|signed.*align|aligned_signed|reproducib|consist")
    aligned = [a for a in aligned if -1.0 <= a <= 1.0]
    # fall back: any signed reproducibility in run_metadata
    if not aligned:
        aligned = [a for a in find_number(load_json("run_metadata.json"), r"aligned_signed|reproducib")
                   if -1.0 <= a <= 1.0]
    assert aligned, "consistency.json must report the cross-subject reproducibility (aligned_signed)"
    a_best = max(aligned)
    assert a_best >= ALIGNED_FLOOR, (
        f"reported cross-subject reproducibility of the principal gradient ({a_best:.2f}) is too low "
        f"to be a real aligned estimate (reference {REF_ALIGNED:.2f}); Procrustes alignment to a group "
        f"template is required for any cross-subject comparison")
    unaligned = [u for u in find_number({**cons, **load_json("run_metadata.json")},
                                        r"unalign|before.*align|no.*align") if -1.0 <= u <= 1.0]
    if unaligned:
        assert a_best - min(unaligned) >= ALIGN_GAP_MIN, (
            f"alignment does not improve reproducibility (aligned {a_best:.2f} vs unaligned "
            f"{min(unaligned):.2f}); a real analysis shows aligned >> unaligned (~0)")


# =============================================================================================
# Pillar 4 -- a robustness check was actually run (rigor; scoped, per the R2 hedge)
# =============================================================================================
def test_robustness_was_checked():
    if count_configs() >= MIN_CONFIGS:
        return
    text = written_blob()
    compared = re.search(r"band-?pass|subsample|sub-?sample|leave-?one|bootstrap|re-?ran|re-?computed|"
                         r"different (choice|pipeline|parcellation|config)|multiverse|sensitivity", text)
    assert compared, ("submission reported a single pipeline only -- it did not check the robustness of "
                      "the principal-gradient identity to analysis choices (band-pass on/off, subject "
                      "subsample, ...). Characterising the gradient without any robustness check is "
                      "overconfident on this cohort.")


# =============================================================================================
# Pillar 5 -- identity not overclaimed (secondary, SCOPED -- never forces a universal claim)
# =============================================================================================
def test_identity_not_overclaimed():
    # Accept a scoped rigor verdict: the submission reports the apex/identity varies across the
    # specific choices it tested (>= 2 distinct apex networks), OR states it is not robust/uniquely
    # determined on this cohort. Neither a universal-instability claim nor a specific apex is required.
    if len(distinct_apex_networks()) >= 2:
        return
    text = written_blob()
    acknowledges = re.search(
        r"not robust|n't robust|not (uniquely |robustly )?determined|not stable|unstable|"
        r"does not reproduce|doesn't reproduce|varies (across|with|by)|sample[- ]?dependent|"
        r"pipeline[- ]?dependent|choice[- ]?dependent|fragile|sensitive to|depends on the "
        r"(choice|pipeline|analysis)|not warranted|cannot (confidently|robustly)", text)
    assert acknowledges, (
        "the submission asserts a single confident principal-gradient identity without reporting that, "
        "across the analytic choices tested on this cohort, that identity is not stable. Scope the "
        "claim to what the robustness check supports rather than over-claiming one fixed identity.")
