# GRADIENT-001: a four-configuration connectivity-gradient method case

## Scientific target

This task applies a disclosed diffusion-gradient procedure to a fixed convenience
cohort of 20 released developmental movie recordings and the Schaefer 400-parcel,
seven-network atlas. It characterises four specified configurations and preserves
two distinct quantities: embeddings of group-mean FC and the mean of aligned
individual embeddings. No configuration must have a particular apex, sign or
minimum separation; agreement and disagreement are both valid.

[Margulies et al. (2016)](https://doi.org/10.1073/pnas.1608282113), especially
Figures 1 and 3, motivates the scientific question. Its adult HCP cohort and
original FC/affinity construction are not reproduced. Its group Fisher-z/tanh
aggregation, residual-negative pruning and cosine similarity differ from this
movie-data arithmetic FC mean and signed top-40 normalized-angle kernel. These
network summaries are descriptive properties of this method/sample, not evidence
against or for the original population finding.

[BrainSpace](https://doi.org/10.1038/s42003-020-0794-7) supplies algorithmic context.
The historical source is identified by tag v0.1.20 and
[commit dcc0bf64](https://github.com/MICA-MNI/BrainSpace/tree/dcc0bf64b82f02565baacadfbeb29aa5d607d45c).
This repair prospectively replaces nonsymmetric `eigsh` use with a real symmetric
conjugate and selects leading algebraic modes. It retains exactly 40 signed row
entries instead of a floating expression that can produce 39. These are explicit
estimator amendments, not legacy bitwise equivalence. A captured source subset
does not authenticate the entire installed BrainSpace package.

## Scope and source limitations

All 20 selected people, 168 released frames, 400 source parcel IDs and four
predeclared configurations remain in scope. The first/last-ten split follows the
exact loader order and can be age-confounded; it is not independent replication.
The whole released window and effective TR=2 s do not establish precise stimulus
timing. Legacy FSL MNI152/MNI152NLin6Asym atlas to MNI152NLin2009cAsym BOLD
nearest-label transfer is an identity-world measurement convention, not verified
nonlinear inter-template registration.

Explicit float64 source means, nuisance operations, post-regression band-pass
and a public raw-scale residual-resolution guard define the numerical inputs.
Empty geometry/inactive signals retain IDs and invalidate dependent quantities;
no outcome-based exclusion or zero-filled FC is allowed. Unresolved principal
axes/truncation boundaries, zero within-network denominators and near-singular
multiscale factors are reported, not hidden. No p-value, population confidence
interval, clinical claim or causal interpretation is added.

## Source-bound validation design

Eight artifacts expose source keys/support, complete source-close raw/cleaned/FC
receipts, spectral vectors/eigenvalues, Procrustes histories and summaries.
Canonical source inputs govern discontinuous graph selection and eigenvalue
scaling. Validation checks orthogonality, stationary-mode separation and
symmetric-operator residuals, not a secret eigenvector correlation target.
Repeated retained blocks may use equivalent bases. Certified rotations attaining
the public Procrustes optimum may differ when that optimum is nonunique.
Summaries replay accepted valid coordinates, not a desired paper-like outcome.

All seven networks are reported for four group-FC embeddings and the distinct
aligned mean. Raw and aligned signed consistency have no required gain;
robustness is a computed Boolean or explicit null, not a demanded conclusion.
Free findings prose is ungraded except for presence. Tolerances define a
computational acceptance envelope, not scientific stability near degeneracies.

## Current validation status

Contracts, including the numerical activity threshold, were frozen before
original BOLD values. The separately gated first-person pilot found exact
dual-route agreement in raw means, cleaned series and FC. The one-attempt
full-20 source-only oracle completed in 25.65 s, emitting all eight artifacts
without warnings. Real incomplete signal support led to explicitly undefined
dependent endpoints under the unchanged predeclared rules; no source exclusion,
threshold tuning or numerical-contract change followed these outcomes. The
independent source-bound grader subsequently passed with reward 1 in 25.89 s.
This is method/data-quality-control validation, not a positive gradient finding,
an original-paper replication or difficulty evidence. The native whole suite
passes 360 cases: 325 manufactured, one production grade, six genuine/equivalent
positives, 24 effective negatives and four explicitly nondiscriminating or
unavailable controls. Six additional packaging checks pass. These engineering
checks do not demonstrate model difficulty. Clean-commit Harbor delivery needs
its separate external receipt; historical agent scores do not validate this
revised contract, and difficulty metadata remains provisional. Preserve the
execution/failure and amendment chronology.
