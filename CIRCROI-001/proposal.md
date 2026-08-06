# CIRCROI-001 — proposal (sibling)

## Topic → paper
Differentiated SIBLING (circular-inference axis), found by the sibling hunt. Anchor: Kriegeskorte et
al. 2009, *Nat Neuro* (circular analysis / double dipping); Vul et al. 2009 (non-independence).

## The un-cued trap (circular inference / double dipping, structural)
Localizing the region with the largest sex difference and testing it on the **same** subjects is
circular. After controlling for head size the overall sex difference is ~null (cf. GMVOL), yet the
circular region is "significant".

Validated (OASIS VBM, 150 subjects, eTIV-residualized): circular region **p ≈ 4e-4**; honest split-half
median **p ≈ 0.5** (n.s.); permuted-grouping null false-positive rate **≈ 89%** (nominal 5%).

## Distinctness
Not a near-dup: GMVOL is the *whole-brain* sex difference's sign-flipping with the correction **method**
(aggregation/method-choice). This is *circular localization* fabricating a **regional** significance
(inference non-independence). Different failure, different fix (independent selection / permutation).
Distinct from AUTCONN/EKLUND multiple-comparisons: the inflation persists even after correcting the
selection step, because inference reuses the selection data.

## Grading
`test_roi_computed` — a significance result is present. `test_recognises_circularity` — findings.md
names circular/double-dipping/non-independence AND that independent selection (split-half/CV/permutation)
is needed. Oracle passes; a naive "significant localized sex difference (p=4e-4)" report fails.
