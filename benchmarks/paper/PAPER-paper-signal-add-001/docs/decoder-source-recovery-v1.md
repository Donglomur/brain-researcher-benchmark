# Empirical decoder source recovery

The pinned release's geometry classifier is a binary simulation example, not
the missing empirical five-category author decoder. Recovering that distinction
prevents a seemingly runnable but incompatible author baseline. The new
[geometry reproduction component](../implementations/geometry-reproduction-v1)
implements only source-described numerical transforms; it does not advance the
empirical cohort, split or baseline to qualified status.

## Original panels that must remain distinct

The [published paper](https://www.nature.com/articles/s41586-024-07309-z),
Methods “Noise correlations and population category decoding,” describes
correct load-1 maintenance trials, five balanced image categories, z-scored
firing rates, one-versus-one linear `fitcecoc` classification, 80% training and
20% testing, and averaging over 500 repetitions. Each region/session is built
into a greedy ensemble: start from the best individual neuron, test additions
of every remaining neuron, retain the best pair/triplet/etc., and continue
until every neuron has been added. The maximum can occur before the full
ensemble. An all-neuron classifier alone is therefore insufficient.

| Panel | Original support/operation | Missing binding |
|---|---|---|
| Fig. 6b | Example maintenance ensemble; intact and category-preserving per-neuron shuffled trials | Exact example identity, selections and accuracy trace |
| Fig. 6c | 21 PAC-neuron contributions before peak decoding | Neuron/session joins, peak-selection details and contribution values |
| Fig. 6d/e | 22 hippocampal sessions; at least one PAC neuron and at least two neurons after PAC removal | Exact complete eligible session/unit roster and all condition scores |
| Fig. 6g | 32 sessions with at least two hippocampal neurons; ensemble where intact/removed accuracy difference is maximal | Selected ensembles; ten binary learners × 500 repetitions per session |
| Fig. 6h | 19 sessions; PAC removal from selected ensembles with at least two neurons remaining | Paired source coefficients and projection SDs |
| Extended Data Fig. 7a | Encoding pseudo-populations; 1,000 decoding repetitions | Complete neuron/trial selection and matching author route |

Fig. 6d/e requires intact/removed conditions, removal of all PAC neurons, and
the matched removal of the same number of non-PAC neurons (500 random removal
selections). None can be replaced with a convenient neuron subset. The paper's
reported 72.77% hippocampal and 88.71% amygdala accuracies concern **encoding
category-neuron pseudo-populations**, not the Fig. 6 maintenance conditions.
The reported significance tests and archive counts of 44 sessions/36 patients
are not decoding scores or the figure-specific eligible roster. Repeated
decoding draws are not independent biological subjects.

## What the pinned release supplies

Source revision:
[`a25e8cc3f61630a428f190381745257d4506f148`](https://github.com/rutishauserlab/SBCAT-release-NWB/tree/a25e8cc3f61630a428f190381745257d4506f148).
The recursive GitHub tree was recovered with `truncated=false`; it has 85
entries and 71 blobs. The source inventory and content hashes are in
[source-evidence.json](../implementations/geometry-reproduction-v1/source-evidence.json).
The release README advertises example data analysis and selected figure
calculations. Its “Simulating Noise Correlations” section and main script's
final section direct the operator to `main_popGeometry_noiseCorrs.m`.

That script selects two neurons, one tuned dimension, two categories and 200
simulated trials per category. It enables two shared-noise terms and chooses
pooled-covariance noise-axis mode 2. Its `popGeometry_defineAxes.m` classifier
mode 2 calls `fitclinear(..., 'KFold', 5)`, computes cross-validation loss and
uses `Trained{1}` for the plotted geometry. It does not recover the empirical
five-category `fitcecoc` route, its 80/20 repetitions, greedy search, PAC
selection or matched ablations. The two modes must not share a baseline label.

Additional exact source distinctions matter for a faithful reproduction:

- `noiseCorr_genData.m` multiplies standard-normal innovations by the variable
  called `sigma`; this is a standard deviation, despite a “variance” comment.
- Signal-dependent noise is added to every dimension in each trial, including
  the untuned neuron, despite a comment describing tuned dimensions.
- The selected noise covariance pools both classes, preserving between-class
  signal variation. It is not the average of class-centered covariances.
- The example's projection summary averages two sample **standard deviations**.
  The helper named `getNoiseVar_alongSignalAxis` returns projections, not
  variances. The later source plot performs `std` and then an arithmetic mean.
- The hyperplane helper constructs random points and uses QR; its first-
  coefficient division can fail. A normalized coefficient vector describes the
  same signal subspace on the nondegenerate domain but is an explicitly
  disclosed numerical reexpression, not a native parity result.

All 37 MATLAB files outside the directory named `3rdParty` (152,456 bytes)
were acquired and their Git blob hashes checked against the pinned tree.
An ASCII-token scan found the classifier calls only in the geometry helper;
it found no `fitcecoc` or `greedy` tokens. This directory filter is not an
authorship or licensing assertion: bundled EEGLAB code also lives under
`internal/PAC`. The inventory, README and inspected main entrypoint support
the limited release scope; a token search alone is not a proof of semantic
absence. This audit is scoped to this exact release, not every author
repository or unpublished analysis. No full empirical decoder entrypoint
has been recovered. Code text, metadata
and the previously cached paper were inspected; binary trial masks, NWB
recordings, private targets, fitted models and scientific outputs were not.

## Consequential next deliverable

For empirical reproduction or same-task improvement, first recover the full
Fig. 6 condition-specific session/unit roster, category/PAC-selection outputs,
trial choices, exact z-scoring/window and ensemble-search implementation, plus
the matching original accuracy vectors. Bind the author rerun to that source
protocol and preserve matched non-PAC removal controls. Alternatively, the
distinct original encoding panel needs its own complete source binding; its
reported accuracy cannot fill a maintenance-baseline gap.

The exact empirical target remains the integration owner's decision. This
addition does not modify the canonical task or activate a new panel. Separate
reproduction and improvement outcomes remain first-class, with paired access
conditions still to be constructed and tested. No readiness, paper victory,
current-SOTA result or historical-score promotion follows from this recovery.
