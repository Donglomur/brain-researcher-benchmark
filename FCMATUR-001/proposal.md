# FCMATUR-001: connectivity and age in ABIDE

## Scientific question and interpretation boundary

This task is a cross-sectional ABIDE case study of aggregation and conditioning:
how does a signed connectivity summary relate to age across participants,
conditional on site, and across equally weighted site means? These are different
estimands and independent-unit choices. None is a substitute for another.

The task is not a reproduction of a published result, diagnostic comparison,
age-prediction challenge, or longitudinal developmental study. No sign, ordering,
attenuation, or significance is prescribed. Site conditioning is descriptive:
SITE_ID combines scanner, protocol, and cohort composition, so it does not
identify a scanner cause. An interval containing zero does not establish a true
null. Reported analytic intervals/p-values are model-based, neither
cluster-robust nor multiplicity-adjusted.

## Original sources and estimand

The fixed 1,035 literal FILE_IDs are unchanged. Runtime contains all 1,035
original CPAC `filt_noglobal/rois_cc200` time-by-200 text tables, the original
1,112-row phenotype CSV, and a commit-pinned Nilearn dataset notice: 1,037 source
members, 406,541,576 bytes. The 77 original `no_filename` rows are provenance,
not substitute participants. Source authentication and staging do not reuse any
previous task's estimator, derived connectivity, classifier, or answer bank.

The participant statistic is the signed mean of Fisher-transformed strict-upper
Pearson edges, clipping each correlation to `[-0.999, 0.999]`. All original
frames remain. Only exactly constant/zero-centered-norm columns are inactive;
no new preprocessing, shrinkage, missing-value imputation, or coverage exclusion
is introduced. This deliberately preserves the existing available-edge target:
participants with inactive columns have different spatial support, a limitation
that must be disclosed rather than silently repaired into another estimand.

The base sample requires defined source connectivity and valid source-normalized
age. The eligible-site set is fixed once at five base participants per site.
Pooled, site-conditioned, and equally weighted between-site associations include
explicit samples, ranks, degrees of freedom, null/status rules, and uncertainty.
The existing five sensitivities remain: motion adjustment, typical-control
restriction, sex adjustment, nested quadratic age, and site-specific slopes.
Complete-case sensitivities inherit the site-parent sample without a second
site-size filter. Missing/invalid metadata tokens and all participant identities
remain visible in the ledgers.

## Public method and source-bound validation

The public method contract and output schema specify the estimator, numerical
rank rule, stable reductions, tolerances, inferential support, and five output
files. A readable public statistics kernel is an optional implementation aid,
not a hidden estimator or source of answers. Its deliberate reuse for downstream
arithmetic is disclosed; it is not described as an independent solver.

Private reconstruction authenticates original bytes and independently parses
metadata and reconstructs participant connectivity. Accepted submitted
participant connectivity must satisfy per-person source closeness and the
public centered/projected directional-fidelity checks. Every downstream result
then comes from a single replay of those accepted values with source-defined
covariates, support, and samples. There is no hidden canonical r/p/F threshold,
sign target, ordering target, or prose keyword target. Complete ledgers, exact
identity sets, typed fields, and coherent nulls prevent fabricated or partially
reported samples from being treated as complete work.

Scoring is all-or-nothing under the production checks; this proposal makes no
partial-credit promise. Manufactured qualification, source reconstruction,
actual positive/negative controls, native execution, Harbor delivery, and model
calibration are separate evidence categories. Prose quality remains a human
scientific-review question beyond machine-readable numeric checks.

## Packaging, source terms, and qualification status

The source-only image uses checksum-pinned original bytes, not lossy
float16/float32 replacement snapshots. Runtime network access is disabled.
Build-time S3 requests retain exact versions and conditional ETags plus full
content hashes; a `null` version is not called immutable and an ETag is not
presumed to be an MD5 checksum. Runtime source identity is independent of mutable
fetch helpers. Solutions, tests, derived answers, and capture leftovers must not
be baked into the source-only image.

The public SOURCE_NOTICE preserves the upstream non-commercial research,
registration, acknowledgement, and CC BY-NC-SA conditions. Public S3 readability
is not commercial-use or redistribution clearance. No public release of the
source data or source-bearing container is authorized here.

The source-bound implementation passed 439 installed source-free checks and
289 native full-QA checks, including independent original-source reconstruction
and genuine-output controls. The cold image's 1,045 application files were
authenticated. See `authoring/REPAIR_STATUS.md` for the scoring/authoring partition
and the nondiscriminating control, which is not counted as a rejection.
These are pre-commit qualification results; clean-commit Harbor and final-image
delivery checks require separate execution receipts. Historical proposal metrics
and old acceptance claims are not current evidence or grading targets.
Difficulty remains uncalibrated; engineering or oracle success alone does not
establish benchmark hardness.
