# Exact descriptive endpoint mapping

The accepted contract defines one full assay, not 42 session benchmarks. This
component covers its P01–P05 quantitative outputs and the two fixed examples.
The separate prospective protected neural-to-pupil task, its fresh-context
authoring controls, and its competent baselines remain unimplemented here.

The model source is the release-equivalent scientific blob at
`pcca_fa_mdl.py`, SHA256
`3c37c6a543d5de74aec72d07e5a7a7bf004c083f4bd1b8396a12cc1ca927d198`.
The accepted source review established equality of the scientific blobs between
the retained default-head source and the paper release trees. It did not prove
every release commit-to-tree object association; preserve that provenance limit.
The two newly authenticated figure notebooks have no cached outputs.

* P01: `compute_psv`, lines 908–958, partitions each channel's total variance into
  the diagonal of WWᵀ, LLᵀ and independent noise. Divide each channel's component
  by its own total, multiply by 100, then average channels within an area. The
  Figure4 caller combines the two hemisphere-specific area values across all
  42 sessions, and repeats within each animal. A ratio of covariance traces or a
  neuron-weighted grand mean is a different endpoint.
* P02: `compute_dshared`, lines 792–861, uses the minimum number of descending
  covariance eigenvalues whose cumulative fraction reaches `0.95 - 1e-9`.
  The `1e-9` is the actual published code's numerical boundary convention, not
  a tolerance chosen from observed results. This evaluator obtains the same
  nonzero spectrum from the at-most-15-dimensional Gram matrix of loadings using
  a bounded Jacobi eigensolver. It reports normalized spectra and both full
  covariance components. It refuses an all-zero selected loading space.
* P03: `compute_pupil_pred.py`, lines 32–45, derives population-variance outliers
  separately within animal, using linear-interpolated 25th/75th percentiles and
  strict outside `Q1 - 2*IQR` / `Q3 + 2*IQR` boundaries. The operator's complete
  pre-z-score target supports this selection. Historical denominators must be
  Pe16/Wa9/Sa16; a mismatch is a diagnostic refusal, never permission to force a
  particular exclusion. Lines 67–88 z-score each entire retained session and fit
  OLS with `CROSSVAL=False`. Report R² = 1 − SSE/SST from every prediction.
* P04: the explicit `compute_pupil_pred_1d.py` caller invokes
  `orthogonalize_latents(..., do_across=True, across_mode='paired')` and takes the
  first transformed coordinate. Core lines 444–517 use SVD of the jointly
  stacked across-area loading matrices and separate within-area loadings.
  Prediction consistency does not verify this fitting provenance. Latent signs
  and equivalent rotations are not directly scored; covariance and predictions
  are invariant comparison objects. Degenerate leading spectra can leave the
  single-mode direction non-unique; a future reference policy must address that
  without tuning to published values.
* P05: both full and single-latent drivers compare every distinct ordered pair
  within animal. The source session supplies latents, the target supplies its
  originally z-scored pupil, and both are truncated to the common prefix length.
  The main Figure6 caller pools each animal's pair scores and takes the default
  linear 2.5/97.5 percentiles. These are empirical distribution intervals, not
  confidence intervals based on 552 independent animals. All 240/72/240 pair
  identities, trial prefixes, six prediction arrays and derived scores remain
  present. The extra single-latent pair summaries are explicit source controls,
  not additional benchmark counts or a new primary paper target.

Figure4 cells 1–4 establish the aggregation and paired one-sided tests. Figure6
cells 3–5 establish the animal strata, two area contrasts per pupil session,
one-sided t-test against zero, and the single-latent pooled contrast. This
evaluator independently computes Student-t tails through the regularized beta
integral. It keeps every contrast, including negative values and negative R².
Zero contrast variance is explicitly distinguished from finite t statistics;
tail underflow is not reported as exact numerical certainty. There is no
candidate-controlled `nanmean` or dropped prediction support.

Figure4 cell2 identifies Pe180726 as P06; Figure6 cell2 identifies Sa191206 as
P07. The latter displays only trials 300:340, but scoring retains the complete
prepared session. Its published 1,258-trial count remains a native-preparation
check, not a count inferred from our fabricated fixture. No session was selected
by proximity to a published result. Full42 support is always retained for P01/2.

Continuous errors to an optional admitted reference compare full within-area
across/within covariance matrices, diagonal noise, cross-area covariance, area
means/dimensions, and each full prediction array. They do not compare raw loading
coordinates. Published means and log10-p discrepancies are contextual only;
`numerical_pass` is always null. This does not establish fitting, full dimension
search, reproducibility, A/B code benefit, biological causality, or an improvement.
Three animals and paired areas do not support treating 84 areas as independent
animals. No new clustered inferential claim is added.

Remaining qualification work is substantive: exact native trial/channel joins,
42-session data verification and the authentic Wa exclusion, preprocessing
policy adjudication, rights and executable environment for any future official fitting code, full
reference fits/search evidence, numerical variability and tolerances, isolated
candidate execution. The separate protected prediction protocol is needed only
for a protected-prediction claim, not for this descriptive output component. This
source component closes output mathematics and admission for the existing full
historical endpoint while preserving those holds.
