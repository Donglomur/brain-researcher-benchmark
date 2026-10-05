# NETINTEG-001: cortical graph-method sensitivity control

This revision retains the released 40-person ADHD subset and original
Schaefer100/17 atlas, but removes the hidden-estimator/"most integrated brain"
framing. It is an **easy, fixed-recipe method control**, not an original-paper
finding reproduction or evidence of model difficulty.

## Paper-to-task mapping

Latora & Marchiori (2001), Eq. 1, supplies the reciprocal-distance efficiency
definition. The task's binary undirected specialization keeps all 100 nodes and
counts unreachable pairs as zero. The paper's general efficiency definition does
not require all connectomes to be binarized.

Van den Heuvel et al. (2017), Methods and Fig. 3, supplies the motivation for
examining threshold-induced differences and their association with overall
connectivity. Its ADHD illustration uses a different cohort and parcellation;
this 40-person/Schaefer100 five-density mean is not that finding. Proportional
thresholding can introduce its own interpretation problems and is not a universal
confound-removal method. The current recipe has no desired sensitivity direction.

## Fixed scientific contract

The public contract specifies original source identities, geometry, empirical
Pearson estimation, all supplied confounds (including global signal), SVD rank,
numerical-zero guards, signed edge selection, complete cutoff ties, all-node
shortest paths, exact-score ties, and the eight graph configurations. All choices
are frozen before new signal outcomes. The primary endpoint is a five-density
arithmetic mean, not an AUC. The absolute-cutoff analyses are required parallel
descriptors, not designated wrong answers.

The independent unit is the participant/run, not a parcel, edge or configuration.
No diagnosis group contrast, population inference, intrinsic integration ranking,
neural information-flow claim or causal bias-removal conclusion is supported.
The atlas contains cortex only. Standard-space affine alignment is not proof of
individual anatomical registration quality. Original preprocessing lineage is
incomplete; no additional processing does not imply unprocessed source data.

## Provenance and verification

Original NITRC archive members are compared with pre-pinned source bytes; measured
archive/member SHA256 values are reproducibility pins, not published checksums or
a promise of source-server immutability. The original atlas, LUT and license are
checked against published Git object identities. Inputs are baked into the image;
the solving agent and verifier need no network. ADHD noncommercial-research terms
are retained separately from the atlas MIT license. Public image/data redistribution
has not been authorized or cleared.

The verifier checks all 198,000 correlations, all 320 graph rows, all 40 primary
scores, exact source identities, geometry and nuisance receipts, and all requested
rankings and diagnostics. It does not use broad correlation-to-reference acceptance,
an arbitrary participant matching fraction, a preferred top-set contrast, keyword
matching or a desired correlation sign. Exact graph ties use integer hop histograms
and rational arithmetic; harmless printed rounding is not a hidden estimator change.

Independent source recomputation, positive formatting/alternative-implementation
cases, malformed/fabricated/naive negative controls, source staging checks and a
clean-commit in-container oracle are separate evidence gates. See REPAIR_STATUS.md
for what has actually run. Historical numerical claims from a different estimator
are removed rather than reused as this revision's bank. A full matching submission
earns binary reward1; incomplete output earns0, with no partial-credit promise.

The reference bank is outside the runtime but public in the repository. Numerical
agreement is not proof of computational provenance. Difficulty is uncalibrated;
no new model, Sol, frontier, GPU or HPC experiment is included in this repair.
