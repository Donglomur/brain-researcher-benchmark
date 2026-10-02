# ABIDE protocol-label prediction: held-site and random-fold sensitivity

Estimate how well resting-state regional connectivity predicts the released
eyes-open/eyes-closed protocol label under two validation designs. The primary
design holds out each named `SITE_ID`; the sensitivity uses shuffled,
stratified ten-fold subject splits. Report both, with their source support and
simple baselines.

This is a paper-derived **method case**, not a reproduction of a published
eye-state finding. ABIDE/PCP provide the real source data. Site and protocol
are strongly confounded: most sites have only one label. Holding out a site
does not identify a biological eye-state effect or eliminate cross-site
confounding. Neither accuracy is required to exceed the other or chance.

## Inputs and public contract

The original regional time series and phenotype table are already staged at
`/app/data/eyestate`; analysis runs offline. Do not fetch another cohort or
substitute a different phenotype table. `source_manifest.json` identifies
every original file and its measured SHA-256. Preserve the source bytes.

Read `/app/method_contract.json`: it specifies the complete source selection,
equations, splits, schemas, numerical tolerances and failure policy. It is a
public part of the task, not a hidden estimator specification. The original
`Phenotypic_V1_0b_preprocessed1.csv` row order controls random-fold allocation.
Retain all 1,112 phenotype rows in the cohort ledger, including the 77
`no_filename` records; these are unavailable derivatives, not failed QC.
Exact source-defined column order and structural eligibility are specified in
the contract. Do not invent anatomical ROI labels, acquisition TR or units.

All 1,035 named derivatives pass the finite-array/200-column/>50-frame rule;
their lengths range from 78 to 316 frames. Every header lists `#1` through
`#200` in that order. Forty-six participants have one or more constant ROI
columns (up to 118); retain them under this declared no-extra-QC selection,
report the per-person counts, and disclose this data-quality limitation.
Constant columns are not silently dropped or anatomically imputed. This
unfiltered source cohort is not evidence of uniformly adequate brain coverage.

These are already preprocessed C-PAC band-pass/no-global-signal-regression
CC200 derivatives. Do not add temporal filtering, nuisance regression,
censoring, feature selection or discretionary cohort exclusions. An unexpected
source mismatch, malformed/nonfinite input or undefined calculation is a
failed precondition, not permission to silently repair or replace the data.

## Analysis

1. Map eye code 1 to label 1 (open), and code 2 to label 0 (closed). Compute
   each person's features independently: center and population-SD standardize
   each original ROI column (`ddof=0`; SD below float64 epsilon gets denominator
   one), then estimate Ledoit-Wolf covariance with centering. Convert it to
   correlation and retain the strict lower triangle in row-major order:
   `(1,0), (2,0), (2,1), …, (199,198)`, using zero-based original column indices.
   There are 19,900 features, with no Fisher transform or diagonal entries.
   This is shrunk-covariance correlation, **not ordinary Pearson correlation**.

2. Construct `LeaveOneGroupOut` over exact `SITE_ID` values and
   `StratifiedKFold(10, shuffle=True, random_state=0)` in selected source-row
   order. LOSO fold IDs follow sorted site strings. Preserve each subject's
   identity, true label, test fold and complementary training membership.
   All training folds must contain both classes.

3. In each fold, fit `StandardScaler(with_mean=True, with_std=True)` only on
   training features and transform train/test with those parameters. The
   contract states the population-variance and numerical-constant rule.
   Fit the binary L2-regularized squared-hinge linear SVM with `C=1`, no class
   or sample weighting, and a **regularized** intercept of scaling one.
   This is the objective of scikit-learn's binary `LinearSVC` with these
   settings. The first supplied `LinearSVC` implementation failed its fixed
   single-fold pilot at 30,000 iterations and also failed the public certificate.
   The oracle now uses the equivalent nonnegative dual described below; the
   objective and acceptance thresholds have not changed.

4. Supply each fitted model and a checkable optimization certificate. For
   standardized training matrix `Z`, let `A=[Z,1]`, `theta=[w,b]`, signed labels
   `t=2*y-1`, and `h=max(0,1-t*(A@theta))`. Compute
   `P=0.5*||theta||²+||h||²`, `alpha=2*h`,
   `G=0.5*||theta-A.T@(t*alpha)||²`. Require
   `G <= 1e-6*(1+P)` for every fold. This primal-dual bound assesses the declared
   training objective; it does not prove stable near-zero decisions or the
   historical order in which someone produced the files. A mathematically
   equivalent solver passing the same public check is acceptable. The supplied
   BVLS oracle must also report optimizer success, stop below its cap and emit
   no warnings.
   This last cap/warning rule is an authoring check on the supplied reference
   oracle, not a solver-name-based acceptance gate for submitted candidates;
   those must pass the mathematical certificate and report their diagnostics.

   An efficient equivalent route is public: form
   `Q=diag(t)@(Z@Z.T+ones(n,n))@diag(t)+0.5*I=L@L.T`, solve
   `d=solve(L,ones(n))`, and minimize `0.5*||L.T@alpha-d||²` with `alpha>=0`.
   Recover `w=Z.T@(t*alpha)` and `b=sum(t*alpha)`; then independently recompute
   the certificate above from this candidate. The supplied oracle uses
   SciPy 1.17.0 `lsq_linear(method="bvls", lsq_solver="exact", tol=1e-12,
   max_iter=30000)`. Preserve its raw finite coefficient vector, then set
   `alpha=max(raw_alpha,0)` before recovering `w,b`; this is deterministic
   projection onto the stated constraint, without a chosen epsilon. Retain
   both vectors and solver diagnostics. The raw optimizer status is not proof
   that the projected model passes the independently recomputed certificate.
   The first BVLS pilot returned tiny negative roundoff coefficients and was
   rejected; this projection correction was documented and frozen before
   the next original-data fit. The earlier failed LinearSVC and BVLS attempts
   remain preserved. Neither repair changes the scientific target or uses
   prediction accuracy to select an estimator or tolerance.

5. Replay each model's signed held-out scores. Prediction is 1 iff its own
   reported score is positive; zero maps to 0. The verifier reconstructs
   canonical float64 features and training scalers from the originals for
   optimization and score replay. Submitted feature/scaler arrays may use the
   stated serialization tolerances, but their rounding errors must not become
   a different training dataset. There is no hidden reference-label or
   reference-coefficient equality requirement.

6. Pool all LOSO held-out predictions before calculating the headline
   balanced accuracy: `(open recall + closed recall)/2`. Report random-fold
   pooled BA separately. Per-fold supported-class mean recall and the
   equal-site mean are descriptive, not substitutes for the headline.
   An absent test class has a null recall, not zero. Include training-majority
   fallback predictions (ties go open), and pooled always-open/always-closed
   baselines. The latter equal 0.5 for a cohort containing both labels;
   that does not make 0.5 the baseline for a one-class site's recall.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`), disjoint from inputs. Do not
overwrite existing evidence. Exact columns/array keys and permitted coherent
reordering are documented in the public contract.

- `cohort.csv`: every original phenotype row, identities, source availability,
  shape, inclusion reason and selected source order.
- `features.npz`: source-keyed correlation features, edge axes and shrinkage.
- `fold_models.npz`: all model keys, training scaler statistics, coefficients
  and intercepts, with their feature axis.
- `oof_predictions.csv`: one row per selected person **per scheme**, including
  exact split, signed score, prediction and training-majority fallback.
- `per_fold.csv`: all fold support/confusion counts, recalls, objective and
  certificate values, plus truthful solver/convergence diagnostics.
- `eye_decoding_results.json`: recomputed pooled, per-design and baseline
  summaries and complete cohort/site-label support.
- `run_metadata.json`: exact source/method identities, observed source
  structure, actual software versions and fit warnings.
- `findings.md`: a short interpretation of your results and their limits.
  State what the two split designs measure. No fixed wording is graded.

The supplied oracle additionally stores its raw/projected dual vectors in
optional `oracle_*` arrays in `fold_models.npz`, with explicit person axes and
a training mask (held-out zeros are padding). These diagnostic arrays are not
required of other solvers and are not additional scoring targets.

The verifier checks the full source-bound computation, not just aggregate
accuracy or prose. Reward is binary: all required checks must pass; there is
no promised proportional partial credit. Equivalent valid solutions can have
different near-zero classifications if each satisfies the public certificate,
score tolerances and internally consistent metrics.

If a precondition fails, exit nonzero and preserve `status="failed_precondition"`
with a nonempty reason in results, metadata and findings. Do not omit failing
folds or silently substitute a solver objective, source or split.
If a late failure occurs after some complete-looking files have been written,
preserve those files and add `failure_report.json` with the failure status and
reason. Its presence marks an incomplete run and is rejected by the verifier.

## Provenance and interpretation

The [ABIDE paper](https://doi.org/10.1038/mp.2013.78) describes the source
resource; [PCP](https://preprocessed-connectomes-project.org/abide/) describes
the preprocessing initiative. This new classifier comparison is not one of
their reproduced figures/tables. The
[source usage agreement](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
links [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/),
with attribution/funding and registration conditions. Public access is not
unrestricted commercial-use clearance. Historical processing/export lineage
is qualified in the manifest. Predictive transfer here is not causal,
clinical, population-level or biological eye-state identification.
