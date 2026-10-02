# LIFESPAN-001 output contract

Read with `/app/method_contract.json`. Evidence tolerances do not authorize a different computational estimator; the public canonical-source calculation governs all downstream fields.

## 2. Serialization and equivalence rules

Require these nine named regular files. Extra harmless files, CSV columns, JSON keys and NPZ arrays are permitted; an explicitly reserved `failure_report.json` is not harmless. Reject it even when empty or dangling, and reject required-artifact links/nonregular files. No creation of files is performed by the validator.

CSV row order, JSON object order/whitespace, NPZ member order/compression and coherent scientific-axis permutations are irrelevant. Exact keys must occur once; missing, duplicate or unexpected required scientific rows/axis identities fail. CSV may use any finite decimal/scientific notation that meets the field rule. Integral counts/indices accept exact integral numeric representations, but not Booleans, fractional values or coercion by truncation. JSON Booleans are distinct from numbers. NPZ identity strings may be Unicode or valid UTF-8 fixed-width byte strings; object arrays/pickle are prohibited. Numeric real NPZ arrays may be float32 or float64; no dtype-only equality gate is needed. Masks may use Boolean or exact numeric0/1 storage.

Undefined CSV numbers are empty; undefined JSON numbers are null; undefined real NPZ entries are NaN only where their declared canonical validity mask is false. Infinities are never accepted. Defined fields must be finite. Strings such as 'NaN', zero substitutes and omitted required rows do not mean undefined. Statuses are exact categorical fields, not prose targets.

Bound the complete public evidence to **128MiB**: both the total on-disk artifact bytes and the combined uncompressed NPZ member bytes plus all text-artifact bytes must be at most134,217,728. Count permitted extra files/members in this resource ceiling too. Check declared shapes/ZIP uncompressed sizes against the source axes and bound before allocation/decompression, and bound actual reads. With the 59*895*148 time series, float64 evidence occupies about62.5MB; both59*10,878 edge arrays about10.3MB together. The remaining masks/axes/group matrix/text leave the complete design comfortably within the ceiling without requiring float32 serialization or omitting data. All originals have 895 frames; no shape-based cohort change is permitted.

Implementation may normalize identities and axes internally, but the canonical computational order remains the frozen source order. Pilot output is explicitly `resource_pilot`, names its scope, and is never accepted as a complete59-person result. A valid complete run may have mathematically undefined endpoints and still report top-level `status='ok'` with complete evidence.

## 3. Nine required files

### 3.1 `cohort.csv` — exactly59 rows

Key: `subject_id`.

Required columns:

`subject_id, cohort_index, left_path, right_path, left_sha256, right_sha256, phenotype_row_index, age_source, age_computational, sex, n_frames, n_constant_parcels, n_valid_edges, global_status, segregation_status`.

`cohort_index` is the immutable0..58 manifest position, independent of row order. Paths are manifest-relative originals, not host paths. Phenotype row index is zero-based among data rows after the original CSV header. Preserve the source sex token without requiring a particular set of sex categories. `age_source` is the parsed original number, not the original decimal spelling; `age_computational` is the promoted float32 value. Frame/parcel/edge counts and statuses are canonical-source-derived. All ages must be finite and nonnegative; no new age cutoff is imposed.

Missing phenotype/hemisphere/ID, duplicate phenotype joins or unparseable/nonfinite age is a source precondition failure, not a reason to shorten this table.

### 3.2 `parcels.csv` — exactly148 rows

Key: `roi_index`, uniquely bound to `(hemisphere, annotation_id)`.

Required columns:

`roi_index, hemisphere, annotation_id, label_name, vertex_count`.

`roi_index` is0..147 in frozen computational order. Hemisphere is `lh` or `rh`; `annotation_id` is the original label-table index used by the declared reader, not a reinterpreted packed color value. `label_name` is original source text. `vertex_count` is positive and exact. The authenticated annotations establish this table-index convention. Preserve packed FreeSurfer color IDs separately in source diagnostics; do not conflate them with table indices.

### 3.3 `connectome_primitives.npz` — complete keyed numerical evidence

Let S=59, R=148, E=10,878 and F=sum of all source frame counts. Each of the59 original pairs has895 frames, so F=52,805. Flat frame blocks permit coherent serialization reordering, not changed support.

| Array | Shape | Meaning |
|---|---|---|
| `subject_id` | S | Unique exact subject IDs in this file's subject-axis order. |
| `roi_index` | R | Permutation of canonical ROI indices. |
| `subject_frame_offsets` | S+1 | Integral prefix offsets, starts0, endsF; blocks follow `subject_id`. |
| `frame_index` | F | Original0-based frame key in each subject block, complete with no duplicates; block rows may be permuted coherently. |
| `roi_timeseries` | F,R | Submitted evidence for the canonical once-rounded float32 means; finite. |
| `vertex_offsets` | R+1 | Prefix offsets for the ROI blocks in `roi_index` order. |
| `vertex_index` | sum vertex counts | Complete original hemisphere-local membership of each ROI; integer, order within each block irrelevant. Hemisphere comes from `parcels.csv`. |
| `parcel_status` | S,R | `ok`, `constant` or `insufficient_frames`, canonical-source-derived. |
| `edge_roi_index` | E,2 | Every distinct unordered pair once; endpoint orientation and edge-axis order irrelevant. |
| `edge_valid` | S,E | Exact canonical pair support. |
| `raw_r` | S,E | Raw Pearson r if valid; otherwise NaN. |
| `fisher_z` | S,E | Clipped Fisher z if valid; otherwise NaN. |
| `group_valid` | R,R | Symmetric mask; diagonal true. Off-diagonal true only if that pair is defined for all59 people. |
| `group_features` | R,R | Zero diagonal; equal-person group Fisher values where valid, otherwise NaN. Both axes use `roi_index`. |

This is14 required arrays, not a requirement to duplicate whole-surface data. `parcel_status` replaces redundant float-norm/status arrays in the minimal schema. Optional diagnostic norms may be retained privately or as extra arrays, but they introduce no new validity threshold. An edge is valid iff both source parcels are `ok`; group validity is an all59 intersection, never a varying-person average. Partial group evidence remains visible when partitioning is impossible; any false off-diagonal group validity makes the full-cohort partition undefined.

Do not reject a permitted one-neighbor change in `roi_timeseries` merely because its incidental exact constancy differs from `parcel_status`. The latter describes the canonical computation. Conversely, the evidence allowance does not license changing the source-derived masks, FC or downstream results.

### 3.4 `roi_partition.csv` — exactly148 rows

Required columns: `roi_index, network_id, status`.

Key: `roi_index`. When a canonical fit exists, `network_id` is any nonempty string identifying a returned cluster. It need not be numeric or named0..6. Matching requires a bijection preserving every ROI pair's co-assignment; a different partition with similar inertia is not equivalent. `status` repeats the single partition status from `partition.json`.

If there is insufficient canonical group support, `network_id` is empty for every row. If a fit exists but has fewer than seven occupied clusters, preserve its actual co-assignment/IDs while status is `fewer_than_seven_occupied_clusters`; the segregation endpoint remains undefined. No reinitialization until seven clusters appear.

### 3.5 `partition.json`

Required object:

```text
status: 'ok' | 'incomplete_group_connectome' | 'fewer_than_seven_occupied_clusters'
method_contract_sha256: exact public digest
n_rois: 148
n_subjects_expected: 59
n_subjects_complete_connectome: integer0..59
n_clusters_requested: 7
n_clusters_occupied: integer0..7, or null if not fitted
n_within_edges: integer0..E, or null if no valid seven-cluster partition
n_between_edges: integer0..E, or null if no valid seven-cluster partition
clusters: list of {network_id: string, n_rois: positive integer}
incomplete_subject_ids: exact order-free list of people missing any required FC
```

`clusters` is empty when no fit exists; otherwise agrees with `roi_partition.csv`. For `ok`, it has seven entries and within+between=E. The method digest binds all hyperparameters; do not demand a second prose spelling of the full method. Optional `fit_diagnostics` may retain returned centers with explicit ROI/network axes, inertia, iterations and warnings for the supplied oracle's audit, but is not needed to validate the science once the canonical co-assignment is replayed. In particular, do not add an undocumented centroid-mean or exact iteration equality gate for a valid equivalent output. The supplied oracle should retain its actual diagnostics privately even when not required of participants.

The exact hyperparameters and feature recipe are mandatory public-method content, and co-assignment replay is mandatory validation. If the named optional diagnostic fields are supplied, require only declared shape/axes and finite/domain-sane values (inertia>=0, returned centers finite, iteration count integral1..300), not equality with the canonical diagnostics. Unknown ordinary diagnostic extras are descriptive and ungraded. A missing diagnostic receipt never permits weakening the required co-assignment check.

### 3.6 `connectome_summary.csv` — exactly59 rows

Key: `subject_id`.

Required columns:

`subject_id, age, n_edges_expected, n_edges_defined, global_fisher_sum, global_connectivity, global_status, n_within_edges, n_between_edges, within_positive_sum, between_positive_sum, within_network_connectivity, between_network_connectivity, system_segregation, segregation_status`.

`age` is the computational age. Expected edge count is alwaysE; defined count is source support. If allE are defined, global sum is the signed Fisher sum and global connectivity is sum/E; otherwise both global numbers are empty with status `incomplete_edge_support` (or `insufficient_frames` if the entire subject lacks two frames). Do not silently report a partial-edge mean.

When partition status is `ok`, within/between counts are the common full-pair family sizes. Positive sums sum max(z,0), including nonpositive entries as zero in the complete denominator. Means divide by those counts. Segregation is (within-between)/within. Preserve within/between values when within is zero; only the ratio is undefined. Status precedence: undefined partition -> `partition_undefined`; empty family -> `empty_pair_family`; missing required FC -> `incomplete_edge_support`; within==0 -> `zero_within_mean`; otherwise `ok`. If no valid seven-cluster partition exists, within/between counts and all four corresponding numeric sum/mean fields and the ratio are empty. Global values remain independently reportable.

For the fixed full-cohort construction, missing FC already prevents partitioning; the local missing-FC branch is still explicit to avoid permissive partial support in general validators. There is no near-zero-within cutoff: an arbitrarily small positive within mean gives its finite ratio or a recorded numerical failure if nonfinite, not a capped result.

### 3.7 `results.json`

Required top-level fields:

```text
status: 'ok' for a complete run, including explicitly undefined estimands
n_subjects: 59
age_range: [min canonical computational age, max canonical computational age]
overall_connectivity_vs_age: endpoint object
system_segregation_vs_age: endpoint object
```

Each endpoint object has exactly these required fields (extra fields allowed):

```text
status: 'ok' | 'incomplete_subject_support' | 'constant_age' | 'constant_summary'
n_expected: 59
n_defined: integer0..59
undefined_subject_ids: exact order-free list
pearson_r: finite number or null
p: finite number or null
ci95: [finite lower, finite upper] or null
```

Precedence is incomplete support, then constant age, then constant summary, then `ok`. `n_defined` counts persons with a defined summary and finite computational age, not the effective rank of the correlation. Thus a constant complete vector has n_defined59 but a null endpoint. Undefined statuses require all r/p/CI fields null. Valid endpoints use two-sided SciPy1.14.1 Pearson default p and the already public 1.96/sqrt(59-3) Fisher interval with internal r clamp±0.999999. Preserve signed r itself. Do not require the clamped approximate CI to contain an exact r=±1; this known boundary limitation is disclosed.

The old oracle's additional within-age/between-age/Spearman fields are **optional nonprimary diagnostics**, not new required endpoints or absence gates. If supplied, do not let them override the two required primary records. No new adjusted model, inference family, bootstrap or stability grid is introduced.

### 3.8 `run_metadata.json`

Required fields:

```text
status: 'ok'
method_contract_sha256: exact frozen public-method bytes
source_manifest_sha256: exact frozen public-source bytes
cohort_manifest_sha256: exact declared cohort bytes
dataset_id: 'nki_enhanced_surface'
cohort_order: all59 canonical IDs, ordered
roi_order: all148 canonical indices, ordered
counts: {n_subjects:59, n_parcels:148, n_edges:10878,
         n_frames_total: exact, n_constant_parcels_total: exact,
         n_subjects_complete_connectome: exact}
source_files: order-free list of {path, role, size_bytes, sha256}
software_versions: object of actual used implementation/version descriptions
warnings: list of captured warning strings (possibly empty)
source_observed: structural object defined below
```

`source_files` binds all121 staged originals in the source manifest; public provenance documents are outside that closed original inventory, not just the two hemispheres of one person. No absolute host paths or timestamps are required in participant outputs. Unknown software names/versions, truthful alternative implementation descriptions, different warning wording or additional provenance keys are not rejection reasons; numerical/source/method validity is independently established. Method hash, rather than duplicate narrative software strings, defines the reference recipe. The supplied oracle must actually use the pinned runtime and retain warnings, but participants are judged on the public source/partition/numerical evidence.

Only the explicitly listed scientific identity/count/structural fields are required and source-checked. Additional metadata is ungraded descriptive material: do not recursively compare arbitrary extra strings or ordinary numeric values against a reference object, and do not reject an implementation merely for supplying additional timing/diagnostic facts. Required fields cannot be displaced or contradicted through duplicate JSON keys; duplicate keys are invalid. The generic size/syntax/safety bounds still apply to extras.

Required `source_observed` required fields: `left_vertices`, `right_vertices`, `left_cortical_parcels`, `right_cortical_parcels`, and order-free `subjects` records keyed by `subject_id` with `left_data_array_count`, `right_data_array_count`, `left_values_per_array`, `right_values_per_array`, `left_storage_dtype`, `right_storage_dtype`, `left_intents`, `right_intents`. Dtypes use canonical NumPy dtype names; intents are sorted unique source integer codes. All originals contain895 time-series arrays of10,242 float32 values per hemisphere; there are74 cortical parcels per hemisphere. Also require `header_timestep_literals=['1000.000000']`, `header_timing_unit=null`, `documented_tr_seconds=0.645`, and `timing_policy='index_order_no_new_temporal_processing'` in `source_observed`. The unitless header token is not a measured TR in seconds. Hemisphere/fsaverage5 correspondence is established by source filenames/release provenance, not absent anatomical/coordinate metadata.

### 3.9 `findings.md`

Require nonempty UTF-8 prose only. The supplied oracle should summarize both measured associations or undefined cases and the convenience-cohort, cross-sectional, shared-cohort partition and conditional-CI limitations. Do not grade keywords, desired sign, significance, absence, a particular interpretation or exact prose. Statements in prose do not replace the numerical artifacts.

## 4. Prospective numerical tolerances and domains

For a finite canonical reference a and submitted value b, a conventional tolerance means abs(b-a)<=atol+rtol*abs(a), evaluated in float64. Reject nonfinite defined values before comparison. All rules below are prospective; do not widen them after observing real discrepancies. Compare each required numeric field directly to canonical source arithmetic, not to separately rounded submitted intermediates.

| Field family | Acceptance rule | Canonical natural domain |
|---|---|---|
| Identities, membership, counts, statuses, masks, source hashes, partition co-assignment | Exact after keyed normalization | Source/contract-defined; integral counts nonnegative. |
| `roi_timeseries`; computational ages in either CSV | Directed-neighbor interval around canonical once-rounded float32 value q | Finite; ages nonnegative. |
| Parsed source age | atol1e-9, rtol0 | Finite, nonnegative. |
| Raw r | atol1e-8, rtol1e-7 | [-1,1]. |
| Individual Fisher z and group feature values | atol1e-8, rtol1e-7 | [-atanh(.999),atanh(.999)]; diagonal group features exactly0. |
| Global/within/between sums | atol1e-6, rtol1e-7 | Signed global in[-E*zmax,E*zmax]; positive sums in[0,count*zmax]. |
| Global/within/between means | atol1e-6, rtol1e-7 | Global in[-zmax,zmax]; other means in[0,zmax]. |
| Defined segregation | atol1e-6, rtol1e-7 | <=1, no finite lower bound. |
| Endpoint Pearson r and each CI bound | atol1e-6, rtol0 | [-1,1]; CI lower<=upper. |
| Two-sided p | atol1e-10, rtol1e-7 | [0,1]. |
| Age range | Directed-neighbor rule on each canonical float32 bound | Min<=max, nonnegative. |

Directed neighbors are the immediately adjacent binary32 numbers toward negative/positive infinity, promoted to float64. The submitted number can be any finite real inside their closed interval, including a float64 container value. +0/-0 are equivalent. At a largest finite binary32 endpoint, clamp the outward acceptance endpoint to q rather than infinity. No additional exact-constancy or submitted-variance gate is applied.

Natural domains describe the canonical quantity. To avoid rejecting an accepted rounded serialization solely at a transcendental bound, use the same field tolerance as an outward domain allowance for r/z/group/sum/mean/segregation/r/CI numeric evidence. The canonical support/status/zero-within decision is never changed by this allowance. Probability p remains strictly[0,1], and all counts/ages/validity fields retain their strict domains. A tolerance cannot turn undefined into zero or make a nonfinite entry valid. A reported CI with lower greater than upper is invalid regardless of tolerance.

These choices allow ordinary six-decimal scalar summaries but ask finer p reporting when p is small. Full matrices should ordinarily be stored as float64; float32 representations may also pass the declared r/z bounds. One-neighbor means are a narrow precision convention, not a universal guarantee for arbitrary float64 summation under severe cancellation. Shared source-order reference arithmetic remains explicit.

## 5. Failure and completion

Use one public reserved marker: `failure_report.json`. On a precondition, timeout or numerical failure, preserve completed private diagnostics, return nonzero and write this marker when safely possible. It contains `status='failed_precondition'` or `status='failed_numerical'`, a bounded reason/phase and completed support counters; no partial output is presented as complete. Its presence makes the artifact set ineligible even if stale `results.json` or metadata says `ok`.

Mathematically undefined but completely accounted estimands are different from execution failure. They produce all nine files, all required rows/keys/masks and top-level `ok`, with null/NaN only under the explicit status rules. Source corruption/nonfinite originals are failures, not undefined scientific measurements.

Authoring must use fresh output/private paths, no overwrite, no source/output overlap, no followed filesystem/HDF5 links or mutable cached expectations. Those safety guards must not impose an incidental CSV/JSON formatting convention on scientifically equivalent submissions. Authoritative source reconstruction belongs to trusted verifier code with private direct pins; no unverified agent-visible helper/pyc import or participant-supplied manifest establishes truth.
