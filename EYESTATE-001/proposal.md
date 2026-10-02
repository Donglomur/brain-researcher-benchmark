# EYESTATE-001: protocol-label prediction under site confounding

This is a paper-derived **method/sensitivity case**, not a reproduction of a
published eye-state finding. It retains the public ABIDE PCP CC200 regional
time series and compares prediction of the released eye-protocol label under
leave-one-SITE_ID-out and shuffled subject-level cross-validation.

The [ABIDE resource paper](https://doi.org/10.1038/mp.2013.78) and
[PCP preprocessing resource](https://preprocessed-connectomes-project.org/abide/)
establish the source substrate. They do not establish this task's classifier,
validation comparison, or any target accuracy. There is no named paper figure
or table reproduced by this new analysis.

## What it measures

The main estimand is pooled out-of-fold balanced accuracy for protocol-label
prediction on held-out named SITE_ID groups in this fixed cohort. The random
10-fold result is a separate, site-shared sensitivity. The full phenotype
ledger, source-derived connectivity, training-only scalers, fold models and
held-out predictions make the computation auditable.

Eighteen of the 20 available SITE_ID groups contain only one eye-status label;
MAX_MUN and NYU contain both. Holding out a SITE_ID group does not remove
protocol/acquisition confounding or identify the effect of opening one's eyes.
These groups are the released metadata categories, not a claim of 20
independent institutions or scanners. Overlapping CV fits are not independent
replications. No causal, diagnostic, population-generalization, or permutation
significance claim is made. Neither score is required to exceed chance or the
other score.

## Transparent computational target

The public method contract fixes the original phenotype order, inclusion
ledger, population-SD within-subject standardization, Ledoit-Wolf covariance
shrinkage, lower-triangle correlation features, exact splits, training-only
feature scaling and binary squared-hinge objective. The intercept is
regularized. The first tightened LinearSVC reference failed its fixed pilot
at the iteration cap and failed the public certificate. Its evidence is
preserved. The replacement BVLS implementation solves the same nonnegative
dual objective; that recipe was frozen before any original BVLS fit. Source,
features, splits, objective and acceptance tolerances did not change. This
is an explicitly documented numerical implementation repair, not tuning to
prediction accuracy.
The first BVLS pilot was also rejected because its raw vector contained tiny
negative roundoff values. The documented implementation now retains those raw
values and projects onto the nonnegative constraint before model recovery;
the original certificate still decides acceptance, with no correction-size
threshold or changed scientific target.

The grader reconstructs canonical float64 features from authenticated originals,
checks all source identities and splits, and recomputes each model's convex
optimization certificate and held-out scores. It accepts the disclosed
objective-accuracy tolerance and each accepted model's own predictions; it
does not demand hidden reference coefficients, exact reference labels, a
particular score gap, nonconstant outputs, or prose keywords. Numerical
serialization tolerances never turn submitted rounded features into a new
training dataset. The certificate verifies a function against its declared
training objective, not the author's historical execution chronology.

## Data and release boundary

All 1,112 phenotype records are retained in the ledger; 77 have no released
derivative filename. The selected cpac/filt_noglobal CC200 cache contains 1,035
original files. Authentication, structural eligibility and execution results
are recorded separately in `REPAIR_STATUS.md`, not inferred from this proposal.
Structural inspection found all 1,035 arrays finite with 200 columns and
78–316 frames, but 46 people have constant columns, up to 118 of 200. They
remain included under the declared no-extra-QC rule, with these limitations
reported explicitly. A good classifier fit would not establish good spatial
coverage or biological validity.

The source snapshot preserves original bytes. Named phenotype versions and
conditional ROI-object identities are distinguished: a null S3 version is not
an immutable release, and an ETag is not assumed to be a checksum. Local
SHA-256 pins measured source bytes. The task stages public objects at image
build time and analyzes the baked bundle offline.

The [ABIDE usage agreement](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
links [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/),
requests dataset/funding acknowledgment and describes NITRC/INDI registration.
Public S3 access does not establish unrestricted commercial use. Historical
preprocessing software and atlas-export lineage remain qualified; this task
does not regenerate the derivatives from raw BOLD or anatomically localize
predictive edges. No data/image publication is authorized by local validation.

## Difficulty and evidence

This is an easy/method-control candidate by design, not a claimed Sol failure
or a hidden-estimator trap. Local tests, a reference run and a Harbor reward
are engineering evidence only. Model-agent difficulty calibration is not part
of this repair and remains unmeasured.
