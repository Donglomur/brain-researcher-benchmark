# OBJCAT-001 — whole-brain nested object-category decoding

## Scientific target

An honestly labeled single-subject method control on original public Haxby data.
Haxby et al. (2001), *Science* 293:2425–2430,
https://doi.org/10.1126/science.1063736, is the data/scientific context.
The original paper used ventral-temporal response-pattern analyses; this
whole-brain ANOVA-500/linear-SVM accuracy is a new analysis, not its named finding.
The nested selection contract is public. No hidden estimator or prose insight
is used to manufacture difficulty.

## Fixed substrate and method

Subject 2's original BOLD and labels from the dated PyMVPA archive, plus the
separately released NITRC whole-brain mask, are checksum-pinned and baked offline.
The public manifest records archive/member identities and transport limits.
Dataset documentation declares CC-BY-SA-3.0; the mask release does not establish
its generation history or an asset-specific license. No redistribution clearance
is inferred from Nilearn's software license. No public image/data release here.

The fixed numeric recipe uses float64 C-order masked extraction, full-run
detrending and sample z-scoring including rest, followed by original non-rest
sample selection. Each held-out run has training-only ANOVA-500 selection and
a fixed linear SVC. Precision and tie handling are stated before execution.
This is offline run normalization, not a prospective/online predictor.

## Verifiable evidence

Natural receipts comprise every original OOF prediction, all 12 fold summaries,
and every fold's 500 selected voxel indices/coordinates/F scores. Scores and
counts recompute from receipts; source identities, actual fitted predictions
and selected features are compared with a genuinely regenerated private bank.
An arbitrary wrong-label substitution preserving accuracy must not pass.
Ordering and equivalent numeric formatting do not change scientific validity.

Remove old correlation/partial-fold alternatives, nonconstant-score heuristics,
above-chance bands, a mandatory circular gap and prose-keyword checks. A
separately measured select-once analysis is an authoring negative control only;
its numerical gap is not a required finding.

Independent checking reconstructs original masked data, detrends/scales with a
separate implementation, computes training ANOVAs and refits held-run models.
Shared acquisition, NiBabel, NumPy and libsvm remain explicit limitations.
Agreement validates this declared implementation, not population generalization.

## Evidence and release boundary

Previous rounded numeric references/readiness assertions are historical, not
evidence for this revised float64 task. Current source acquisition, native runs,
independent checks, measured bank, exact-commit offline Harbor and final-image
regression results are recorded in the local repair receipt and REPAIR_STATUS.md.
Only completed executions count as evidence; planned checks do not.

This is an easy/method-control candidate. No frontier run, Sol-failure evidence,
hardness claim, push, PR comment, merge or public release is included. Its value
is correct training-only feature selection on authentic data, not an unstated
trap. Subject/run/voxel counts are not independent participant counts, and
selected F scores are not localization significance.
