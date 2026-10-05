# MOTORIMAGERY-001: offline held-run condition-decoding method control

The prior five-fold bank, hidden reliability requirement and “BCI illiteracy”
interpretation are retired. This task measures condition discrimination using
CSP+LDA, with entire acquisition runs held out, on fixed EEGBCI participants
1–10 and imagined both-fists/both-feet runs 6/10/14. It does not reproduce a
specific quantitative result of Schalk et al. (2004) or measure online BCI ability.

## Original source and paper connection

PhysioNet EEG Motor Movement/Imagery v1.0.0 (Schalk2009,
DOI 10.13026/C28G6P) supplies 30 unmodified EDF+ files, 77,040,000 bytes.
Each selected original file is bound to the published SHA256 registry and
versioned source identity. Build-time staging supports the documented official
public S3 mirror with identical checksums. Dataset attribution and ODC-By1.0
terms remain explicit; run-time analysis is offline.

Schalk et al. (2004; DOI 10.1109/TBME.2004.827072) is BCI2000 system provenance.
This fixed-subset benchmark recipe is a secondary offline method case, not a
named figure/table reproduction. The raw data are original human recordings,
not synthetic substitutes.

## Scientific and numerical repair

The public contract specifies run-local filtering, complete cue membership,
epoch support, all channels, train-only CSP/LDA, source labels and all
original-adjacent-pair-preserving permutations. Before any genuine fit, original
annotations showed all 210 task pairs across 30 runs contain one hand and one
foot cue. Whole-run unrestricted shuffling would break this source constraint.
The revised conditional null permutes only complete original adjacent pairs and
fixes the final singleton or surviving member of an incomplete pair.
Observed and null scores use the same pooled out-of-fold accuracy;
the former mixture of pooled observed accuracy and equal-fold null accuracy
was not well defined for unequal fold sizes.

The verifier checks every source event, retained epoch, replicate, fold and
source-bound decision score. Subject accuracy, kappa, null SD/mean, permutation
exceedances and p-values, Holm adjustments and group summaries are recomputed.
Complete keyed coverage replaces duplicate-overwriting, partial matching and
loose group bands. Prediction ties are handled from the submitted score, within
a declared source-score tolerance. Findings are not graded by keywords.

No particular accuracy, sign, between-subject variation or significance count
is required. The old 0.5+2*mean(nullSD) “empirical ceiling” is removed: it is not
an empirical null quantile. All 200 null replicates remain available as receipts.

## Interpretation and readiness

Visual cues covary with condition; decoding cannot uniquely attribute the signal
to imagery. Within-original-pair label exchangeability is an explicit conditional
analysis assumption, not a recovered experimental randomization protocol. A significant
offline statistic is not online performance, and nonsignificance is not BCI
inability. With only 200 permutations, Monte Carlo resolution is coarse and the
minimum p barely resolves the first ten-subject Holm threshold.

The task is an easy/method control, not an empirical “Sol cannot solve” claim.
The old public reference is contaminated and stale; any future difficulty study
needs separate authorization and contamination-aware design. REPAIR_STATUS.md
and the dated sequential receipt distinguish staged data, pilot, full oracle,
independent checks and clean-commit container verification. No push/merge or
external comment is implied by a local repair.
