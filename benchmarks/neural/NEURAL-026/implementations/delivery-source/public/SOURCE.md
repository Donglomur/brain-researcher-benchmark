# Source lineage and scientific scope

Official author revision: `815b610b3beddfed5a3abf611d3a465ab9e4ce5c`,
<https://github.com/kaufmanlab/GSK26-public>. Repository code is CC0; the
Figshare version-one data inventory records CC BY 4.0. The source inventory,
provider metadata and original helper copies are retained operator-side.
No raw files were acquired for this task and no redistribution of the missing
raw collection is asserted. The task specification is newly authored.

The fixed author's `eventLockKinematics.m` supplies the centroid definition,
joint-angle smoothing, camera/synchronization relation and LR field. The
`eventLockDataSmooth.m`/`eventLockData.m` path supplies events/ROI-lag timing.
`loadLock4Decode.m` supplies the original quality flags. We use the previously
reviewed NEURAL025 portable implementation without editing that package.

The author [distance-removal decoder](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/decodePartialD2S.m)
regresses coarse distance out before its later cross-validation call.
The author [residual decoder](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/decodeResiduals.m)
uses target-specific across-trial mean subtraction before cross-validation.
Both also construct neural PCA before that call. These establish relevant
coarse-motion and target/time comparisons, but do not establish this new
held-out nuisance protocol. The main Figure5 script enables its richer
controls for RADICaL, while the smoothed-deconvolution branch selects its
plain decoder. We use smoothed events, not RADICaL predictions.

Consequently the new combined nuisance basis, 128-cell matching, paired
target-trial matching, five deterministic folds, training-only transforms,
fixed ridge penalty, shifted-arm refit and paired inference are **prospective
analysis choices**, not claims about the historical numerical method.
They are fixed before any NEURAL026 empirical result. Time-since-lift and
lift-to-grab duration define a retrospective phase proxy; no independently
annotated phase categories are supplied by the observed header census.

The primary paper identifies mouse sensorimotor reaching/grasping; this
delivery does not claim to reproduce the full paper, optogenetic findings,
published Figure5 values, or a population-generalizable improvement.
The source-data overlap with025 is explicit; the independent experimental
units remain five mice. Reference predictions are missing rather than
replaced by historical prose, a catalog score, or fabricated values.
