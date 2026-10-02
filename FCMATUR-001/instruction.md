# Connectivity and age in ABIDE: an aggregation case study

Estimate how a signed connectivity summary relates to age at three levels:
pooled participants, participants conditional on site, and equally weighted
sites. Report uncertainty and the five specified sensitivities. This is a
cross-sectional case study, not a paper replication, diagnostic classifier,
age-prediction benchmark, or longitudinal maturation study.

There is no required sign, ordering, attenuation, or significance. Your
interpretation must follow your source-bound measurements.

## Inputs and public contract

All inputs are baked into `/app/data/fcmatur`; runtime is offline. The exact
1,035 literal FILE_IDs are in `/app/subject_ids.txt`. The directory contains the
original CPAC `filt_noglobal/rois_cc200` tables, the original full phenotype CSV,
the upstream dataset notice, and an internal source manifest. Each ROI file is
**time × 200 columns**, with tab-delimited `#1` through `#200` headers. Do not
replace these originals with a newly fetched cohort, converted snapshot, or
previous task's derived results.

Read these public specifications before implementing:

- [Method and numerical tolerances](/app/method_contract.json)
- [Exact output fields, types, null/status rules, and limits](/app/output_schema.json)
- [Source membership and byte identities](/app/source_manifest.json)
- [Source terms and attribution](/app/SOURCE_NOTICE.md)

The readable [statistics kernel](/app/statistics_kernel.py) implements the public
arithmetic and may be reused, but its use is optional. It contains no source
loader or answers. Equivalent implementations must satisfy the same declared
source fidelity, rank, support, and arithmetic contract. Use the original
normalized covariates for calculations, not rounded output receipts.

## Participant measurement

Authenticate the original inputs and retain every original frame and column
identity. Reject nonfinite ROI values. An exactly constant or zero-centered-norm
column is inactive; do not introduce a near-constant threshold or an additional
coverage/QC cutoff. For each participant, calculate Pearson correlations among
all active columns, clip each correlation to `[-0.999, 0.999]`, Fisher-transform,
and average every strict-upper, off-diagonal edge once, retaining its sign.
Fewer than two active columns gives an undefined measurement, not zero.

This is an **available-edge summary**: inactive columns differ across people,
so spatial support can differ. Preserve and report that support and discuss
this comparability limitation. Do not add filtering, scrubbing, imputation,
time-series nuisance regression, shrinkage, or resampling.

Join the phenotype by exact FILE_ID, source SUB_ID identity, and original row
index. Preserve raw tokens separately from normalized age, site, sex, diagnosis,
and mean FD. Apply the public missing/invalid-token rules without inventing
values or deriving site from FILE_ID. Keep all 1,035 participants in the
participant table and all 1,112 original phenotype rows in the provenance
ledger, including the 77 `no_filename` rows.

## Three primary estimates and five sensitivities

The base sample has defined source connectivity and valid age (`0 < age < 120`).
Missing site alone does not exclude a person from the pooled estimate. Define
the eligible site set once using at least five base-sample participants per
valid site.

1. Pooled: participant-level connectivity–age Pearson correlation on the base
   sample.
2. Within-site: participant-level partial correlation controlling for site
   fixed effects on the eligible-site sample.
3. Between-site: correlation of mean age and mean connectivity across those
   eligible sites, weighting each site equally.

Report signed estimates, analytic 95% intervals, p-values, actual units, sample
identities, ranks, and degrees of freedom as specified. Retain a defined estimate
when only its uncertainty is unavailable; use the prescribed null/status fields
for degenerate support or insufficient degrees of freedom.

Also report:

- Motion: pooled and within-site partial correlations adjusted for mean FD.
- Diagnosis: pooled and within-site correlations restricted to typical controls
  (`DX_GROUP == 2`).
- Sex: pooled and within-site partial correlations adjusted for the released
  numeric sex code.
- Nonlinear age: the specified nested standardized-age quadratic added-term
  test on the base sample.
- Site-specific slopes: each eligible site's correlation and age slope,
  including undefined rows, plus the specified complete-support summaries.

Motion, sex, and control sensitivities inherit the eligible-site sample, then
apply their declared complete-case/restriction rule without reapplying the
five-person threshold. Do not substitute a median of site correlations for the
within-site fixed-effects estimand. Numerical details, including projection,
stable reductions, active-direction fidelity, and quadratic underflow handling,
are fully public in the linked contract.

## Deliverables

Write these five files to `${OUTPUT_DIR}` (default `/app/output`):

- `connectivity.csv`: every fixed FILE_ID, measured connectivity, normalized
  covariates/statuses, source support counts, and analysis eligibility.
- `connectivity_age.json`: the three primary estimates and their samples.
- `sensitivity.json`: all five complete sensitivity records.
- `run_metadata.json`: source/document identities, complete source and phenotype
  ledgers, observed source structure, and actual software versions.
- `findings.md`: a concise interpretation of the estimates and uncertainty.

The output schema defines the required nested fields; extra benign descriptions
are allowed within its limits. Submitted participant connectivity must match
the sources and preserve the declared active directions. Those accepted values
then determine every downstream estimate; reported intermediate values are
receipts, not alternative inputs. Grading is all-or-nothing, not proportional
credit, and does not require a predetermined endpoint or phrase.

Describe the contrast between aggregation levels without attributing a cause
to scanner hardware: SITE_ID mixes acquisition, protocol, and cohort factors.
These cross-sectional estimates cannot establish within-person development.
A small estimate or interval containing zero does not establish a true null.
The analytic uncertainty is model-based, not cluster-robust or
multiplicity-adjusted. Automated checks cover the machine-readable results;
scientific quality of prose still requires human review.

If original-source identity, shape, or finite-value prerequisites fail, stop
with nonzero exit and write `failure_report.json` with
`status: "failed_precondition"` and a nonempty reason. Do not pass off stale or
partial outputs as complete. A legitimately undefined statistic instead stays
in the completed output with its declared null/status and sample identities.
