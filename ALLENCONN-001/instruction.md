# Projection-density self-maximum descriptor (ALLENCONN-001)

## Scientific scope

Oh et al. (2014), *A mesoscale connectome of the mouse brain*,
https://doi.org/10.1038/nature13186, introduced an atlas of anterograde tracer
projections. This task is a **secondary atlas method control**, not a reproduction
of the paper's Figure 3 matrix or Figure 4 injection-unmixed regional model.
Compute the fraction of eligible source structures whose own structure is among
their maximum mean projection-density targets on the frozen inputs below.

Density is the fraction of segmented pixels in a sampled anatomical domain; it
is not total projected signal, a synapse count, or a causal connectivity estimate.
The current API cohort and structure set differ from the paper's original ones.
Primary-injection-site grouping does not unmix injections spanning structures.
Some summary targets are nested, so these are not a disjoint parcellation.

## Offline inputs and provenance

`/app/data/allen/source_manifest.json` identifies the original official Allen API
responses, URLs, byte counts and SHA256 hashes. All response files are available
under `/app/data/allen`; no runtime download or AllenSDK installation is needed.
This is a locally frozen API capture, `allen-connectivity-20261001`, **not an
official immutable atlas release**. The data remain subject to the Allen
Institute's research/noncommercial terms. Do not invent an atlas release number
from an SDK cache-schema version.

`/app/method_contract.json` is a public, answer-free metadata template. Preserve
its fields in your metadata and add your computed summary fields. Implement the
following contract using any computationally equivalent approach.

## Analysis contract

1. From the experiment response, select all non-transgenic-line experiments,
   matching `MouseConnectivityCache.get_experiments(cre=False)`: simplify a
   present `transgenic_line` object to its `name`, then retain falsy names/values.
   Use `data_set_id` as the experiment ID. The frozen cohort has 498 experiments.
2. Use all 316 members of structure set `167587189` in graph 1. Map each
   experiment's primary `structure_id` to the **deepest** member of this set in
   its ordered `structure_id_path`, including itself. Fail on an unmapped or
   malformed path. Include one source row for every mapped primary source.
3. Use only original `ProjectionStructureUnionize` records with
   `is_injection=false`, `hemisphere_id=3`, and exact target-set membership.
   Use the published bilateral value; do not average hemispheres 1 and 2 or
   mix injection and projection compartments. Reject duplicate record IDs or
   experiment-target keys. Preserve each record's `projection_density`,
   `sum_projection_pixels`, and `sum_pixels`; for a positive domain, density
   equals numerator divided by denominator within the public tolerance.
4. Represent the full experiment × target Cartesian product. A record with a
   finite positive denominator is `observed`; a present zero-denominator record
   is `zero_domain`; a missing API record is `api_absent`. Neither missing nor
   zero-domain records are zero-density observations. An observed zero density
   **is** an observation. Retain the original values of all present records.
5. For each source-target cell, take the **equal-experiment mean** of observed
   `projection_density` values among experiments assigned to that source. Do not
   pool pixel numerators/denominators across experiments. Report `n_observed`
   and `n_expected` (all experiments assigned to the source) for every cell.
   Leave a mean undefined if no observed experiment supports it.
6. A source is eligible for the full-target descriptor only if all 316 target
   means are defined. Otherwise label it `incomplete`, retain its matrix and
   support row, and exclude it from the fraction's denominator. Report both
   total and eligible source counts. Fail if no source is eligible.
7. For each complete source, report **every** target within absolute `1e-12`
   of its row maximum (relative tolerance zero). Self counts if included in this
   tie set. Thus an all-zero complete row has all targets tied, including self;
   report zero-maximum and tied-maximum counts and do not interpret such ties as
   evidence of preference. Weight eligible sources equally in the final fraction.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). IDs and counts must be integers.
Row order, target-column order and extra descriptive columns are unrestricted.

- `experiment_targets.csv`: one row per experiment-target pair, with columns
  `experiment_id,source_id,target_id,record_status,unionize_id,projection_density,sum_projection_pixels,sum_pixels`.
  For `api_absent`, leave the four measurement/record-ID fields empty. For
  present records, retain all four fields, including for `zero_domain`.
- `connectivity_matrix.csv`: `source_id` plus one numeric-ID column per target.
  Values are the source-target means; undefined means remain empty.
- `matrix_support.csv`: `source_id,target_id,n_observed,n_expected` for every
  source-target cell.
- `source_strongest.csv`: `source_id,status,strongest_targets,is_self_strongest,max_density,n_missing_targets,n_experiments`.
  Use `complete` or `incomplete` for status and a JSON list of unique target IDs
  for `strongest_targets` (order unrestricted). Complete rows use a boolean
  self indicator. Incomplete rows use `[]`, empty self/max fields, and their
  actual missing-target count.
- `self_projection.json`: `status="ok"`,
  `pipeline_id="allen-projection-summary-v2"`, and computed fields
  `n_experiments,n_target_structures,n_source_regions,n_eligible_sources,n_self_strongest,self_strongest_fraction,n_zero_max_sources,n_tied_max_sources`.
  Add `record_status_counts` containing counts for all three record statuses.
- `run_metadata.json`: all fields from `/app/method_contract.json`, plus all
  fields from `self_projection.json`. Additional descriptive metadata is welcome.
- `findings.md`: a short summary of the result, coverage, ties and scientific
  limitations. No particular wording or language is required.

For undefined CSV fields, blank, `NA` or `null` is accepted; `NaN`/infinity is not.
Booleans may be `true`/`false` or `1`/`0`, case-insensitive. Raw measurements and
matrix entries are checked with `atol=1e-12, rtol=1e-9`; the summary fraction uses
absolute tolerance `1e-9`. Identities, statuses and counts must match exactly.
Determine tie membership and zero-maximum categories from the unrounded,
source-derived means; output-number tolerances do not authorize changing them.
The verifier binds the full experiment-level receipt to the frozen source,
recomputes matrix/support/ties and checks the summary. There is no target band
for the fraction, injection-inclusive comparator, hidden algorithm or prose
keyword gate. Scoring is binary: all required checks must pass.

## Failure handling

If source integrity, schema, mapping or numerical preconditions fail, exit
nonzero and write parseable `run_metadata.json` and `self_projection.json` with
`status="failed_precondition"`, the pipeline ID and a nonempty `reason`; also
write `findings.md`. Do not replace missing data or a failed analysis with a
guessed scientific result. Such a failure is diagnostic, not a passing solution.
