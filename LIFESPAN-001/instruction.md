# Cross-sectional connectome organization in a fixed NKI cohort

Characterize how two resting-state connectivity summaries relate to age in the
59-person cohort identified by `/app/cohort_manifest.json`.

Chan et al. (2014), [Figure 2](https://doi.org/10.1073/pnas.1415122111), motivates
the comparison of within- and between-system connectivity and system segregation.
This is a paper-derived **method control**, not reproduction of that paper's
sample or finding. We use a different historical convenience cohort, Destrieux
surface parcels, a cohort-derived age-blind partition and a pooled-pair ratio.
Report what these data support: no negative effect, significance or null result
is required. Cross-sectional differences are not within-person aging.

## Data

Original released files are already present at `/app/data/lifespan`: 118 NKI
hemisphere GIFTIs, the original phenotype CSV and two Destrieux fsaverage5
annotations. `source_manifest.json` binds their exact identities and bytes.
No internet is available or needed. Preserve all 59 declared IDs, all 895 source
frames per person and all 148 cortical parcels. Do not replace the cohort with a cached
subset, add an exclusion or treat the source order as interchangeable with an
arbitrary filename sort. The historical cohort selection is documented, not
retrospectively justified as quality control.

Use the original annotation table index together with hemisphere as a parcel
identity; packed FreeSurfer color IDs are a separate source field. Exclude only
the declared `Unknown` and `Medial_wall` labels. Preserve source vertex membership.
Join phenotype rows by exact subject ID. Keep source age and the specified
float32 computational age distinct. `/app/SOURCE_NOTICE.md` records provenance,
preprocessing uncertainty, documented timing and unresolved redistribution terms.

## Public numerical method

The complete recipe and tolerances are in `/app/method_contract.json` and
`/app/output_contract.md`. They are public parts of the task, not hidden
reference-estimator choices.

1. For each hemisphere, let `X` be its frame-by-vertex matrix and `v` the
   parcel's ascending original vertex indices. Compute
   `np.asarray(X[:,v],dtype=np.float64,order='C').mean(axis=1,dtype=np.float64).astype(np.float32)`;
   then promote to float64 for FC.
   This explicitly amends the old task's float32 intermediate accumulation.
   Do not add preprocessing, censoring, weights or imputation.
2. Compute per-person Pearson correlations and all 10,878 unordered Fisher-z
   edges, using `atanh(clip(r,-0.999,0.999))`. Exact constant parcels have
   undefined correlations; retain their identities and report support.
3. Average the upper-triangle Fisher edges equally across the complete 59-person
   cohort, adding in manifest order. Mirror these means into a symmetric matrix
   and set the diagonal to zero. Fit the public seven-cluster
   KMeans recipe to these ROI rows: sklearn 1.5.2, `init='k-means++', n_init=10,
   max_iter=300, tol=1e-4, random_state=0, copy_x=True, algorithm='lloyd'`, with
   float64 C-order features, `sample_weight=None`, and one numerical thread.
   Do not scale rows, select seeds against age or rerun until an outcome appears.
4. For each person, report the signed mean of all Fisher edges. Separately,
   zero-clip negative Fisher edges and calculate within- and between-network
   means over their **complete pair counts**, including zero entries. System
   segregation is `(within-between)/within`, not an average of network ratios.
5. Relate each primary summary to computational age using signed Pearson r,
   the two-sided Pearson p-value and the stated Fisher interval:
   `tanh(atanh(clip(r,-0.999999,0.999999)) +/- 1.96/sqrt(59-3))`.
   All 59 people are required for each endpoint; do not silently use a subset.

The interval is a plug-in approximation; it does not propagate uncertainty from
learning a partition on the same cohort. Sex, motion, nonlinear age effects and
partition sensitivity are not adjusted or newly searched here. The task does
not support causal, clinical or representative-population conclusions.

## Evidence and scoring

Write the nine files specified in `/app/output_contract.md` to `${OUTPUT_DIR}`
(default `/app/output`): cohort and parcel ledgers, keyed parcel/FC primitives,
the ROI partition and partition status, per-person summaries, group results,
run metadata and a short `findings.md`.

The verifier authenticates originals and recomputes the public method. It accepts
coherent output-axis reorderings, cluster-name permutations and the declared
numerical tolerances. It checks source-derived values and co-assignment, not
historical effect sizes, prose keywords or preferred signs. Rounded evidence is
not an alternative fitting input: canonical-source arithmetic determines support,
FC, partition and endpoint results. Shared NumPy/sklearn reference operations are
disclosed; this is not a claim of independent validation of those libraries.

Completely accounted undefined estimands can be valid: retain all rows and use
the documented statuses/nulls/masks. Missing source data, nonfinite originals or
execution failure must exit nonzero and write `failure_report.json` with a reason
when safe. Its presence overrides any stale successful outputs. A resource pilot
is not a complete result. Scoring is binary: complete valid evidence earns 1;
failed or incomplete submissions earn 0, not proportional partial credit.
