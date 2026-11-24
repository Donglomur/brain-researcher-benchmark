# Deposited coactivity row-order audit

This component audits a concrete positional join in the original
`ClusteringbySpineSize.m`, recovered from [Zenodo record 10108836](https://zenodo.org/records/10108836).
It supports source-faithful reproduction work and subsequent same-task
improvement work. It does not fit a model or provide either scientific score.
The historical next-visit Brier evaluator and canonical contracts are preserved.

## Source finding

In the deposited script, lines 235–246 concatenate `AnimalTags_for_stats`
by distance bin, with early-session rows followed by middle-session rows.
Lines 248–253 concatenate responses, distances, stability and area by four
blocks: eliminated/small, eliminated/large, stable/small, stable/large. Line
260 joins these columns positionally. The session analysis constructs another
response ordering, but line 382 reuses the earlier `AnimalTags_for_stats`.

For two generated early-session pair rows ordered as stable animal A,
eliminated animal B, the response ordering is B,A while the assigned animal
tags remain A,B. Both random-effect groups are wrong. This is a structural
counterexample to general alignment, not evidence of the number of affected
rows in the authentic deposit. If all permuted rows have the same animal,
the audit correctly reports no animal-group mismatch.

Source member SHA-256:
`ca6c2b52ecb07662722a81b78c513708a2ba36177193f6b9c5a5f562d9fb0c83`.
The source's formulas and row construction are described in the
[source recovery report](../../docs/source-recovery-v1.md).

## Execute the audit

```sh
python3 coactivity_row_audit.py PAIR_ROW_METADATA.json NEW_AUDIT.json
python3 -B test_coactivity_row_audit.py -v
```

The input is a JSON list of row metadata. Each row supplies a unique `row_id`,
`animal_id`, `session` (`early` or `middle`), `stability` (`stable` or
`eliminated`), `distance_um` and `area_um2`. Numeric values must be finite and
nonnegative; JSON `null` explicitly represents source NaN. Only source-tagged
stable/eliminated rows are accepted. Within each session, the supplied order
must match the original concatenated MATLAB pair-array order, including
directed pairs and repeated observations. Authentic mapping of those identities
is a separate prerequisite; this interface does not establish it.

The audit reproduces the source's 1.0960 square-micrometre size threshold,
`0:5:50` distance loop, early/middle concatenation and both response orders.
That loop includes `[50,55)` as its final bin. Missing distances are excluded;
missing areas remain in the source animal vector but do not enter either size
block, which can produce unequal table-column lengths. The session response
does not filter by area.

The output preserves both row orders, reports table-length differences and
lists position-specific animal mismatches. It never repairs/reorders source
data, consumes activity responses, selects a model, or calculates likelihood.
Its findings concern the table before fitting; subsequent removal of rows with
missing responses by a fitter is outside this metadata-only audit.
It refuses to overwrite an existing output. Native outputs, including animal
identities, must stay in external operator evidence.

## Scientific boundary

The generated tests check positional misassignment, distinct size/session
orders, missing-area length failure, exact distance boundaries, harmless
same-animal permutations and invalid identities. They establish software
behavior only. No MATLAB execution, recording preparation, authentic response
table, model fit, likelihood comparison, reproduction score or improvement
score has been produced. Both future paper+data and paper+data+author-code
conditions need the same admitted population and independently defined
scientific scoring; access to this audit/source report must be assigned
consistently with those conditions.

## Export the source coactivity curves

`coactivity_curves.py` supplies a separate, partial original-endpoint preparation
from the same metadata, plus normalized-coactivity responses joined by `row_id`.
It exports all 11 source bins `[0,5)` through `[50,55)` for the two all-spine
curves, four size-stratified curves and four session-stratified curves. These
are the deposited `ClusteringbySpineSize.m` plotting calculations at lines
278–295, 318–327 and 399–412, bound to the source SHA-256 above. They complement
the row-order audit; they do not repair or fit the source mixed-effects tables.

```sh
python3 -B coactivity_curves.py KEYED_PAIR_RESPONSES.json NEW_CURVES.json
python3 -B test_coactivity_curves.py -v
```

The input object has `schema_version: "rep011-coactivity-curves-input-v1"`,
`source_sha256` equal to the pinned source hash, `input_kind` equal to
`generated_engineering_control` or `empirical`, a nonempty `population_id`,
and `native_pair_order_provenance` describing the identity mapping. `rows` is
the audit's metadata list. `responses` is a list of objects containing
`row_id` and `normalized_coactivity`. Every supplied row must have exactly one
response, including distance-excluded rows. Response list order is immaterial.
For example, a generated response is
`{"row_id": "generated-pair-1", "normalized_coactivity": 0.5}`.

Responses are nonnegative finite numbers, JSON `null` for source NaN, or the
string `"Inf"` for source positive infinity. NaN is omitted from `nanmean`
and the `nanstd/sqrt(non-NaN count)` calculation; infinity is retained and
produces an infinite mean and undefined SEM. An empty or all-NaN bin has null
mean and SEM; a singleton finite bin has zero SEM. The SEM uses the source's
sample-standard-deviation convention and pair counts. It is **not** mouse-level
uncertainty and does not treat directed/repeated pairs as independent animals.
The export records each bin's row identities, total, nonmissing, NaN and
infinite counts, including empty bins. Missing area excludes a row only from
the size curves; it remains eligible for all-spine and session curves.

An input content hash, all curve supports, distance/area exclusions and the
unchanged row-permutation audit accompany the results. Output creation is
exclusive. Both results and authentic identity records belong in external
operator evidence. Complete supplied coverage is not verification of the
original population: source-native acquisition, response derivation, cohort
admission, other primary endpoint families, numerical-reference comparison,
and both information-condition evaluations remain unresolved. Generated tests
establish only this export's arithmetic, stratification and coverage behavior;
no scientific reproduction or improvement is claimed.
