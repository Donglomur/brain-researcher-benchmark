# Explicit source-reconstruction conventions

These conventions define the finite `spec_data` assignment. They are disclosed resolutions of the selected released computation, not proof that the unavailable supplementary Methods or every historical figure used an identical protocol. Any valid algorithm is permitted if it reconstructs these quantities within the published tolerances and preserves the required support identities.

## Rows, variables, and dtype

Read the manifest and numeric archive described in `DATA_FORMAT.md`. Every observation has the unique key `(source_member, source_row0)`. Preserve every original member and row for raw-cohort accounting; do not deduplicate repeated values, collapse rows to mouse means, or infer biological identity from matching dendrite labels. Missing dendrite IDs are provenance uncertainty, not automatic numerical exclusions.

For each compartment, traverse members in their supplied manifest order and concatenate each raw numeric field sequentially along its one-dimensional row axis. Preserve source dtypes and NumPy dtype promotion at each concatenation. Perform division after concatenation, not separately within each member. Early conversion of all arrays to float64 can change the declared calculation. The supplied ordering is the frozen reconstruction order, not a claim about the authors' historical filesystem traversal.

The local predictor is the supplied `distance_coactivity_rate_norm_row0`, exactly the source `distance_coactivity_rate_norm[0,:]`. The coincident predictor is the supplied `dendrite_coincident_rate_norm`. Both are already processed normalized features. Do not reconstruct chance normalization, substitute another distance bin, use `relative_local_coactivity_rate_norm`, or z-score these vectors.

On eligible rows, calculate:

```python
y = followup_volumes / spine_volumes
```

Use NumPy's division semantics for the concatenated dtypes. The outcome is a dimensionless ratio: no subtraction of one, logarithm, baseline subtraction, or division by a sum. The retained source field names say `volume`, while the article describes structural area measurements. This task does not recalibrate that upstream measurement.

## Eligibility and endpoint pairing

Flag tokens preserve a `kind` and `value`. For `kind="str"`, test Python substring membership in the complete string. For `kind="list"` or `kind="tuple"`, test exact whole-label membership in the serialized sequence. Do not split strings, lowercase labels, or substitute substring tests for sequence membership.

A row is structurally eligible exactly when:

1. Neither the baseline nor follow-up flag contains any of `New Spine`, `Eliminated Spine`, or `Absent`, under those typed membership rules.
2. The **follow-up** flag does not contain `Shaft Spine`. A baseline-only Shaft flag does not impose this additional exclusion.

Do not pad mismatched flags or repair misaligned arrays. Such structural inconsistencies must be surfaced as invalid input. Do not select only potentiated or depressed spines; plasticity-class thresholds are not part of these four correlations.

For each endpoint, take its predictor x and the ratio y on eligible rows, then retain exactly:

```python
paired = ~(numpy.isnan(x) | numpy.isnan(y))
```

This is a NaN-only mask, not a finite-value mask. Pairing is endpoint-specific. Do not drop extra outliers, rows outside a figure's display bounds, zero baselines in advance, or rows that weaken an association. Do not impute or replace nonfinite values. If infinity remains on the paired support, fewer than two pairs remain, a paired variable is constant, or a required statistic is otherwise nonfinite, report an explicit abstention for that endpoint rather than silently changing the estimator.

## Statistics and outcome diagnostics

Pool paired spine observations within the endpoint's compartment. Reconstruct the result of `scipy.stats.pearsonr(x_paired, y_paired)` with its default two-sided test and default analytical method, using the source-dtype paired vectors. An equivalent implementation is allowed. No mouse centering, hierarchical correction, permutation test, or resampling replaces this source statistic.

The p value is the nominal pooled-spine Pearson output; its independence assumptions are not a claim that nested biological observations are independent. This assignment checks reconstruction of that scalar, not valid animal-population inference.

For `paired_y_mean` and `paired_y_sd`, first compute the ratio and pairing as above. Sort the paired observations by their canonical `(source_member, source_row0)` keys, then convert the already-computed y values to float64. Accumulate the mean in float64 and the population standard deviation in float64 with `ddof=0`. These diagnostics distinguish outcomes such as ratio versus ratio-minus-one that Pearson r and p alone cannot distinguish.

## Counts and hashes

Derive the five `cohort` fields from all members and all original rows, before eligibility or predictor pairing:

- `member_count`: number of source member records.
- `raw_rows`: total number of original source rows.
- `unique_mice`: number of distinct mouse ID strings across all members.
- `shared_mouse_ids`: sorted unique IDs present in both compartments, including members whose rows may later be excluded.
- `raw_row_ids_sha256`: digest of all original row identities.

For each endpoint, `raw_rows` counts its compartment's original rows; `eligible_rows` counts the structural mask before predictor pairing; `paired_rows` counts the endpoint-specific NaN-only support; and `excluded_nan_rows = eligible_rows - paired_rows`. The eligible digest describes the structural support, and the paired digest describes exactly the observations supplied to the Pearson calculation. Shared mice are the same animals across compartments, not additional independent animals.

For every support digest:

1. Collect unique pairs `[source_member, source_row0]`. Duplicate identities are errors; do not silently deduplicate.
2. Sort by the complete member string using Python lexical ordering, then by the integer row index.
3. Serialize the sorted list as compact UTF-8 JSON with `ensure_ascii=False`, separators `(',', ':')`, and **no trailing newline**.
4. SHA256 the resulting bytes and use its lowercase hexadecimal digest.

Use SHA256 of the exact mounted `/public/input_manifest.json` bytes as `input_manifest_sha256`; do not hash a parsed or reformatted manifest. The manifest identifies and pins the numeric archive. A host preparation filename such as `metadata.json` is merely the source of the mounted `input_manifest.json` alias, not a different scientific input.

Every endpoint ID must occur exactly once. Counts and `schema_version` require literal JSON integer tokens, not booleans or decimal/exponent substitutes. Reported numeric values must be finite binary64-representable scalars; JSON NaN and Infinity are forbidden. Follow `OUTPUT_SCHEMA.json` and `PUBLIC_SCORING.md` for the complete artifact contract.
