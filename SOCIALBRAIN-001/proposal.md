# SOCIALBRAIN-001: ToM–pain connectivity sensitivity

Richardson et al. (2018), [Development of the social brain from age three to
twelve years](https://doi.org/10.1038/s41467-018-03399-2), motivates this
public-data methods task. It retains all 155 released ds000228 participants
(122 children, 33 adults), twelve fixed overlapping spheres, and two explicit
preprocessing arms: without and with global-signal regression.

The target is a signed connectivity sensitivity analysis, not exact replication
of the paper's primary-motor/artifact-adjusted pipeline. Participants are the
independent units. The task reports child age-rank associations, their
motion-rank-adjusted counterparts, and adult participant means. Cross-sectional
movie data do not establish within-person maturation or causal effects; GSR
sensitivity alone does not identify an artifact or a neural mechanism.

## Reproducible contract

The public method fixes source membership, geometry, full confound columns,
missingness, normalization, detrending, nuisance projection, numerical support,
and downstream statistics. Raw headers remain unchanged; the source notice
separates their unspecified units from the release's documented spatial/timing
conventions. Build-time capture verifies immutable source identities; runtime
and grading are offline. No source-bearing image is published by this repair.

Agents submit signal primitives, complete signed participant measurements,
group results, source/processing receipts and a short interpretation. The
private verifier authenticates originals and independently reconstructs signal
primitives. Once cleaned series pass the declared source-fidelity bounds,
their own unrounded values determine all downstream measurements. A public
reporting kernel is shared explicitly; raw/CSV/JSON receipts do not become
alternative numerical inputs.

There is no keyword, expected sign, significance band, required GSR attenuation,
or hidden estimator. Undefined measurements keep all participant slots and
explicit null/support records. The old fixed answer bank and outcome-specific
claims are retired, with their historical state recoverable in Git.

## Validation and interpretation

Authoring tests cover source integrity, numerical boundary cases, equivalent
representations and fabricated/mismatched artifacts. Production scoring is one
source-bound validation, not the authoring mutation suite. Local fixture and
oracle results are recorded separately in `authoring/REPAIR_STATUS.md`.

Difficulty is unassigned pending a separately authorized current-head model
run and trajectory review. Prior model scores from the retired task do not
establish difficulty for this revision. Passing an oracle or verifier is
engineering evidence, not scientific replication.
