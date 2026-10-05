# VTDECODE-001: run-held-out object decoding

## Scientific scope

A modern, single-subject method baseline on the real Haxby dataset. The target is
eight-class linear-SVM accuracy on an unseen acquisition run, using subject 1's
577 ventral-temporal voxels and 864 non-rest volumes across twelve runs.

Haxby et al. (2001), Science 293:2425–2430, DOI 10.1126/science.1063736, motivates
the distributed object-category representation. This task does not reproduce the
paper's six-subject pattern-correlation/category-pair statistic or provide a
population estimate. Its role is an easy method control; difficulty is not
established by a model run.
Accuracy is conditional on the supplied fixed VT mask; the benchmark does not
establish independent ROI selection or evaluate an end-to-end ROI-discovery pipeline.

## Public contract and data

The instruction declares the exact preprocessing, classifier, and held-out unit.
Clean each full acquisition run independently before excluding rest. Use
NiftiMasker with sample z-scoring, detrending, TR 2.5 s and runs=chunks; fit a linear
SVC with C=1, tol=0.001, shrinking=True. The held-out run contributes no training
examples. The optional random-volume contrast estimates a different target and
does not affect grading.

The image downloads the dated public PyMVPA subject-1 archive at build time,
checks its published MD5 plus pinned SHA256, and extracts only the BOLD, mask, and
label table. Each selected file is also SHA256 checked. The public manifest retains
CC-BY-SA-3.0 attribution and source URLs. The agent and verifier run offline.

## Reference regeneration

The old 0.7222 bank came from globally detrending/scaling the concatenated runs.
It is replaced by the source-derived runwise-clean-loro-v2 bank, generated with
authoring/build_reference.py from retained outputs of the repaired real-data
oracle. Its unrounded mean accuracy is 0.8333333333 (reported as 0.8333).

An independent preprocessing check directly indexes the mask with nibabel,
detrends with SciPy, and applies sample-standard-deviation scaling per run. All
864 categorical predictions agree with the oracle. This check shares the input
data and sklearn/libsvm classifier; it is not an independent classifier or a
reproduction of the original paper endpoint. The actual globally cleaned control
recovers 0.7222222222 and differs in 247 predicted categories.

## Verification

The hidden bank stores source-indexed true/predicted categories, held-out runs,
per-run scores, source hashes and pipeline metadata. Every non-rest volume is
required exactly once. Predictions must match the declared pinned recipe; fold
scores and headline must recompute. CSV order is immaterial; fold and headline
rounding tolerances are public. The source cohort, mask/voxel count, chance level,
and machine-readable analysis metadata are checked. There is no correlation-only
bypass, private minimum accuracy, random-split gap, or prose-keyword criterion.

Authoring tests include genuine oracle outputs, reordered rows, score-preserving
wrong-label substitutions and a real global-cleaning negative control. Passing
output checks establishes agreement with the declared implementation, not proof
that an agent honestly trained the model. Public historical numerical references
also require contamination-aware future model calibration.

## Execution boundary

The task requests 2 CPUs, 8 GiB RAM, no GPU, and an offline agent environment.
Current local source/oracle/regression receipts and final clean-commit Harbor
result are retained by the maintainer outside the agent image. No Sol/frontier
calibration, push, merge, or acceptance claim follows from these engineering tests.
