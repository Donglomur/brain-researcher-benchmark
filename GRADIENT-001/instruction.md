# Connectivity gradients on a fixed movie cohort

Characterise the network organisation of connectivity gradients in the fixed
20-person released developmental movie cohort, using the Schaefer 400-parcel,
seven-network atlas and the four public configurations. This is a descriptive
method application, not a replication of the adult HCP cohort in
[Margulies et al. (2016)](https://doi.org/10.1073/pnas.1608282113), a population
inference, or a test with a required stable/unstable result.

The complete mathematical and serialization specifications are
`/app/method_contract.json` and `/app/output_schema.json`. Use the original files
under `/app/data/gradient`, authenticated by its `source_manifest.json`; do not
fetch replacement data or use historical reference outputs. Preserve all fixed
people, all 168 released frames, and all 400 source parcel IDs. Effective TR=2 s
and frame origin=0 are computational conventions, not independently established
movie-onset or slice-timing references.

## Computation

Use the exact participant order in the contract. It comes from the pinned Nilearn
loader and pandas ordering, not lexical IDs. The first/last-ten groups are
convenience subsets of that order, not randomized or independent replication
groups; their age composition can differ.

1. Transfer atlas labels to each native BOLD grid by the declared nearest
   identity-world mapping. Average calibrated voxel values in float64 using all
   assigned voxels and no implicit brain mask. The atlas's legacy FSL
   MNI152/MNI152NLin6Asym coordinates and the BOLD's MNI152NLin2009cAsym designation
   do not establish nonlinear inter-template registration: this is a disclosed
   operational mask approximation.
2. Demean and linearly detrend parcels and the 15 named nuisance columns;
   standardize nuisance columns, apply the pivoted QR projection, and retain
   residuals without final z-scoring. The band-pass arm applies the specified
   0.01–0.1 Hz fifth-order Butterworth SOS filter **after** regression, not joint
   data/confound filtering.
3. Apply the public numerical-resolution guard before Pearson FC. A parcel is
   active only when its residual centered L2 norm exceeds
   `1e-12 * sqrt(168) * max(1, original_raw_sample_SD)`. Both arms use the same
   original raw scale. This prevents projection roundoff becoming apparent
   signal; do not omit members, add epsilon to Pearson denominators, or replace
   undefined FC with zero. Preserve masks and scale/norm/threshold diagnostics.
4. Form four complete group-mean FCs: `nobp_all`, `bp_all`,
   `nobp_firstHalf`, and `nobp_secondHalf`. In every embedding keep exactly the
   largest **40 signed** entries per FC row among all 400 candidates including
   the diagonal; exact ties choose smaller source parcel ID. The diagonal is not
   forcibly retained. Use normalized-angle affinity and alpha=0.5.
5. Solve the real symmetric diffusion operator, retaining ten leading algebraic
   nontrivial modes and the eleventh eigenvalue as a boundary diagnostic. Use
   multiscale `lambda/(1-lambda)` coordinates. This explicitly corrects
   BrainSpace 0.1.20's symmetric eigensolver on a nonsymmetric row-normalized
   operator and its largest-magnitude selection, and replaces the floating
   expression that can retain 39 rather than 40 entries.
6. Give each raw coordinate its largest-absolute-entry sign. Align all 20
   no-band-pass embeddings by the specified ten-dimensional generalized
   Procrustes procedure initialized with raw `nobp_all`. Save every iteration's
   rotations, reference and distance. Residual-valid bases in unresolved
   eigenvalue blocks and certified nonunique optimal rotations are accepted;
   there is no hidden reference-basis gate.

Source-canonical means, cleaned series, FC, support and eigenvalues govern the
operator and diffusion scaling. Serialized receipts are not rethresholded to
create a different graph. Accepted certified eigenvectors and rotations govern
coordinates and summaries; rounded CSV values do not decide apex labels.

## Reporting and undefined results

Preserve the distinction between embedding each group-mean FC and averaging
aligned individual coordinates. An aligned coordinate is a multicomponent
rotation, not necessarily the individual's first eigenvector. Report all seven
network means for all five quantities, orientation signs, apex/bottom and the
descriptive leading-plane between/within ratio. Report all 190 signed
cross-person parcelwise correlations before/after alignment and each person's
complete 19-partner mean.

No apex identity, consistency gain, sign, between/within lower bound, or
stable/fragile narrative is required. The robustness Boolean reports whether all
four defined apex labels agree: true, false and null (incomplete support) are
valid. Undefined denominators, near-singular multiscale factors, unresolved
principal axes and unresolved retained-component boundaries use the public
null/status rules. Keep every member and dependency count. A completed run can
honestly contain undefined estimands.

Signed top-40 normalized-angle affinity is a BrainSpace-derived method choice,
not the exact original paper algorithm. The paper used adult HCP data, different
FC aggregation, residual-negative pruning and cosine similarity. Figures 1 and 3
supply context, not an expected answer for this movie cohort. Numerical
tolerances do not establish scientific stability near sparsity, sign, spectral
gap or apex ties.

## Outputs

Write these eight files to `${OUTPUT_DIR}` (default `/app/output`):

- `cohort.csv`: all 20 identities, frozen positions and subset membership.
- `parcels.csv`: all 20×400 source parcel/support records.
- `gradient_arrays.npz`: keyed source receipts, FCs, spectral certificates,
  Procrustes histories, displayed coordinates, masks and pairwise measurements.
- `configurations.csv`: all five quantities × seven networks.
- `per_subject.csv`: all 20 people, support/status and signed consistency.
- `results.json`: complete denominators and descriptive group summaries.
- `run_metadata.json`: exact public pins, source/header/support facts, software
  versions, numerical amendments and actual warnings.
- `findings.md`: measured results and limitations, acknowledging undefined
  support. There is no phrase-based grading.

Coherent keyed axis/row reorderings and harmless finite extras are allowed within
public bounds. Preserve enough spectral-array precision for the published
residual/orthogonality certificates. See the schema for exact fields, null/mask
rules and size limits.

Use a fresh output directory and protect source/code/contracts. On unsupported
source or numerical failure, exit nonzero and preserve `failure_report.json`
with a reason. Do not fabricate completion, silently retry changed settings, or
choose exclusions from outcomes. A `resource_pilot` is not a complete submission.

## JSON field and representation clarification (version 2.1)

The source, method and output-schema JSON files and their SHA-256 identities
remain unchanged. This section clarifies the JSON containers and documentary
fields without changing estimators, source truth, tolerances or null rules.
JSON objects reject duplicate keys; counts/Booleans are typed, numeric strings
are not numeric receipts, and all JSON numbers must be finite. Required
unavailable values use null. Extra finite descriptive fields are allowed.

`results.json` requires `schema_version: gradient-results-v2`, `status: ok`,
`n_subjects`, `n_parcels`, `n_components`, `n_frames`, `unaligned_signed`,
`aligned_signed`, `configuration_summaries`, `aligned_mean_summary`,
`principal_gradient_identity_robust`, `robustness_status`,
`apex_networks_observed`, `gpa` and a nonempty descriptive `claim_scope` string.
The fixed counts and all computed values remain as specified by the contracts.

- Each signed aggregate is an object with `value`, `status`, `n_expected` and
  `n_defined`; the complete 190-pair mean is null unless all pairs are defined.
- `configuration_summaries` may be a list of four records carrying `config`,
  **or** an object keyed by the four exact configuration IDs. In the object form
  an inner `config` may be omitted; if present it must equal its outer key.
  Every configuration appears once. Missing/unknown/duplicate/conflicting
  identities are errors. Order does not matter.
- Each configuration record requires `subject_ids`, `bandpass`,
  `embedding_status`, `principal_status`, `retained_span_status`, `apex_network`,
  `bottom_network`, `between_within`, `between_within_status`, `principal_gap`
  and `retained_boundary_gap`, in addition to its configuration identity.
  `subject_ids` is a duplicate-free list with exact source membership; list
  order is immaterial. Field values are checked against source-bound replay.
  For configuration-level `embedding_status` only, `inactive_parcel` and
  `source_incomplete` both denote an unavailable group embedding caused by
  source-inactive parcel support. The alias is accepted only when the source
  masks and certified operator establish that case; it does not denote an
  available embedding or `multiscale_singular`. Other statuses/nulls/gaps remain
  unchanged, and this alias does not apply to per-subject CSV status fields.
- `aligned_mean_summary` is an object with `quantity: aligned_mean`, `status`,
  `n_subjects_expected`, `n_subjects_defined`, `apex_network`, `bottom_network`,
  `between_within`, `between_within_status`, `principal_gap` and
  `retained_boundary_gap`. It remains distinct from group-FC embeddings.
- `gpa` is an object with `status`, `n_iterations` and `termination`, using the
  schema's enum/null-support rules. `apex_networks_observed` is the distinct
  defined-network list in public network order. The robustness Boolean/null
  and status remain computed quantities, not desired outcomes.

`run_metadata.json` requires `schema_version: gradient-metadata-v2`, `status:
ok`, `task_id: GRADIENT-001`, the exact `source_manifest_sha256`, `method_sha256`
and `output_schema_sha256`, `source_files`, `source_observed`,
`software_versions`, `numerical_method_amendments` and `warnings`.

- `source_files` is an order-free list of complete source records, keyed by
  `path`, each containing `path`, `role`, `participant_id` (nullable for shared
  files), `size_bytes` and `sha256`.
- `source_observed` requires `participant_ids`, `source_order`,
  `participant_column_names`, `confound_column_names`, `headers`, `atlas_header`,
  `atlas_labels`, `voxel_support_by_subject`, `frame_alignment`,
  `raw_clock_metadata`, `effective_TR_s` and `effective_origin_s`.
  `participant_ids` is an order-free exact-membership list; `source_order` and
  original column-name lists retain source order. The four per-person fields
  `confound_column_names`, `headers`, `voxel_support_by_subject` and
  `raw_clock_metadata` are objects keyed by all 20 literal IDs.
- Each header record carries `shape`, `affine`, `source_dtype`, `spatial_units`,
  `temporal_units`, `raw_TR`, `raw_toffset`, `effective_scaling_slope` and
  `effective_scaling_intercept`. `atlas_header` carries the same spatial fields
  but does not require the three temporal fields. Shapes and affine row/column
  axes are ordered. Equivalent endian-aware dtype spellings are accepted.
- `atlas_labels` is an order-free list of 400 records keyed by `parcel_id`, with
  `label` and `network`. Each per-person voxel-support value is an order-free
  list of 400 records keyed by `parcel_id`, with `n_voxels` and `support_sha256`.
  Each raw-clock record has `raw_TR`, `raw_toffset` and `temporal_units`.
  Header and clock numbers retain the source values, not the effective clock.
- `frame_alignment` is a nonempty descriptive string, not a verbatim phrase
  target. `software_versions` contains nonempty actual-version strings for
  python/numpy/scipy/nibabel/nilearn/brainspace (`not_used` is allowed when true).
- `numerical_method_amendments` may be one nonempty descriptive string or a
  nonempty list of nonempty descriptive strings. No exact phrase is required;
  the machine-readable source/operator checks enforce the actual method.
  `warnings` is a list of actual warning descriptions/records, which may be
  empty; its content is not matched to a hidden expected warning list.

All source identities, membership/support, array certificates, CSV receipts,
derived numbers and scientific statuses continue to be checked independently.
