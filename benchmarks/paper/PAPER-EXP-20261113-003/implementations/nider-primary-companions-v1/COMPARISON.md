# Paired comparison of original-result exports

`compare_exports.py` compares the existing Table1/Extended Data Figures1–3
numerical exports from both information conditions against one owner-selected
reference. The previous full120 comparator does not cover the study-level forest
vectors, original Bayesian exports or literal Table1 CSV. This additive tool
retains those companion quantities and their source coordinates in one report.
It does not execute a candidate, R, an estimator or a native-object verifier.

The owner supplies a SHA256-pinned request with exactly this structure:

```json
{
  "schema": "nider_original_export_comparison_request_v1",
  "task": "PAPER-EXP-20261113-003",
  "exports": {
    "reference": {"arm": "A", "files": {}},
    "paper_data": {"arm": "A", "files": {}},
    "paper_data_author_code": {"arm": "B", "files": {}}
  }
}
```

Each `files` map must contain all nine relative artifact names:
`full120.json`, `row_lineage.json`, `table1/habit_associations.csv`, and
`dl/<contrast>.json` / `bayes/<contrast>.json` for `quest_self`, `amy_quest`,
`amy_self`. Each value has exactly `path` (absolute existing regular file),
`bytes` (measured positive integer) and `sha256` (measured digest). Empty maps
above are explanatory placeholders and fail validation. Symlink paths and
individual files over256KiB are rejected. The inherited strict JSON decoder
further limits each of the eight JSON exports to64KiB; the literal CSV may use
the256KiB file limit. Extra files in a containing bundle are neither read nor
authenticated by this operation.

```text
python3 -I -B compare_exports.py --implementations /absolute/task/implementations \
  --request /owner/private/request.json --request-sha256 ACTUAL_REQUEST_SHA256 \
  --output /owner/private/NEW_COMPARISON.json
```

Use an owner-controlled private directory and a fresh output path. The report
is mode0600 and never replaces an existing report. Inputs and reports may
contain study data, reference values and local paths; they remain outside public
Git and participant observations. An I/O failure can leave a partial report;
retain it as failed evidence and choose a new path for a separately justified
attempt. Exit0 means comparison completed, not scientific success.

The loader authenticates the current companion validator and its existing
predecessor/public-contract pins. The request binds one reference, A and B
simultaneously. Arm labels express owner assignment; they do not establish
independent execution, author-code isolation or matched compute. The reference
must be qualified independently. A supplied digest establishes byte identity,
not authentic source generation or correctness.

All three contrasts must retain exactly the reference's complete ordered
membership and source-row lineage. A smaller internally consistent cohort is
rejected; no matching-subset or available-case comparison is produced. This
establishes coverage **relative to the supplied reference**, not authentication
of the original study population. Both arms must retain the source-native
Fisher-z, raw-weight, sample-size-column and Bayesian model conventions already
required by the existing validators. No value is transformed, clipped or filled.

For each of three comparisons (A−reference, B−reference, B−A), the report retains:

- All120 full120 scalar positions, with settings, membership and tau-interval
  metadata. These are120 interface positions, not120 independent observations.
- All eight forest values for every reference membership row, keyed by contrast,
  vector, source position and source ID, with native names/storage metadata.
- All123 Bayesian positions: inclusion scalars, inclusion/model vectors and each
  cell of the three4×4 pairwise-BF matrices. Inclusion BF10 remains separate
  from the pairwise model BF. Native labels/dimensions remain attached.
- The original33 Table1 text cells, preserving headers and model order. Text
  comparison does not reinterpret the source helper's `r` label or parse a
  rounded string into a new numerical endpoint.

Finite differences are exact rational `left_minus_right` values derived from
the JSON decimals. `NA`, `NaN`, `+Inf` and `-Inf` remain distinct. Matching
nonfinite states are explicitly unscored and are not numerical agreement.
Counts describe compared interface cells; they do not weight or aggregate the
three scientific associations. Metadata disagreements remain visible even when
the numbers coincide.

There is no reproduction tolerance, primary superiority rule, aggregate
scientific pass, improvement result or readiness promotion. Native RDS objects,
Bayesian print text, image rendering, native computation, runtime custody,
final-paper/archive correspondence and scientific reference qualification remain
unassessed. The separate Figure5b endpoint and held-study CRPS extension are not
compared or redefined. Existing historical files and pinned producers remain
unchanged.

Generated controls exercise complete support, missing-row rejection, exact
decimal differences, undefined-state distinctions, matrix orientation, metadata,
literal Table1 shape, paired input identities and output nonreplacement:

```text
python3 -I -B tests/comparison_controls.py \
  --implementations /absolute/task/implementations --scratch /private/generated-tests
```

The tests use invented values and source-shaped fixtures, never authentic study
inputs or R. Their success establishes only the described software behavior.
