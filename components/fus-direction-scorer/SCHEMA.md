# Private intake and prediction interface

The authoritative V3 contract SHA-256 is
`a0fc7cd1008f907df8d24c8a2133896d99b90915764debd141194022914f301f`.
Angles are 0,45,...315 degrees, encoded as integers 0..7. The original x-right,
y-up `targetPos` convention must be authenticated by future intake; the scorer
does not convert unknown original coordinates or infer their orientation.

Top-level intake keys are exactly `schema` (`fus_adjudicated_intake_v1`),
`contract_sha256`, `source_roster_sha256`, `source_archive_sha256`,
`intake_review_sha256`, and `records`. Hashes must name actual selected evidence
in a future operation. Hash syntax or a content match alone is not independent
review, scientific evidence, exposure clearance or kernel custody.

All 49 records occur once. Each has exactly `record_id`, `native_hz`,
`reconciliation_sha256`, `clock_mapping_sha256`, `representation_sha256`, and
`trials`. Source reconciliation must cover released forms (successful-only
versus all-trial RT), all declared counts and cross-file/Run99 duplicates.
Positive records require native Hz 1 or 2 and evidence identities. The declared
zero record `L-S45-R1` has an empty trial list, null Hz/clock/representation and
a real reconciliation receipt. It cannot disappear from the source census.

Every source trial has exactly these keys:

- `source_trial_id`: evaluator-private globally unique lineage key (nonempty,
  at most 200 characters). The future producer derives identity from originals;
  assigning a new string cannot itself prove two native trials are distinct.
- `source_order`: integer position in the complete source-order list, starting
  at zero. Missing or repeated positions cannot hide omitted trials.
- `disposition`: `eligible` or `adjudicated_excluded`.
- `query_id`: for every eligible trial, opaque `q_` plus 32 lowercase hex
  characters, globally unique. Calibration/query assignment is recomputed;
  caller-supplied split labels cannot change it. Opaqueness alone does not prove
  randomness or absence of a lookup channel.
- `direction`: exact integer 0..7; optional null only for an excluded trial.
- `timing`: eligible trials have eight finite common-clock numbers: `cue`,
  `memory_start`, `memory_end`, `go`, `baseline_start`, `baseline_end`,
  `acquisition_start`, `acquisition_end`. Baseline must have positive duration
  and end strictly before cue. Memory starts at/after cue and ends no later than
  go. The selected positive-duration acquisition lies wholly inside memory.
- `exclusion_reason` and `adjudication_sha256`: null for eligible trials.
  Excluded trials require one of `missing_target`, `missing_timing`,
  `missing_baseline`, `no_complete_memory_acquisition` and the selected
  independent intake-review digest; `timing` and `query_id` must be null.

Unresolved missingness is not an accepted exclusion. The reviewer must inspect
the complete original census and approve each exclusion before the intake is
frozen. The normalized scorer checks structural/interval consistency only. It
cannot prove source-clock alignment, complete source coverage, last-complete
acquisition selection, pre-cue baseline selection or independently justified
missingness from the normalized projection. Those are explicit responsibilities
of the independently reviewed native input bridge, which remains missing.

The representation receipt must bind full spatial fields, training-only scale,
pixel quantization/masking and native dimensions; no label-dependent ROI,
cropping, native-frame substitution, median-state timing or test-set scale is
permitted. Full-resolution native delivery and matched-reference competence
are separate unqualified prerequisites. A whole-session processed input is an
offline vascular response representation, not causal online neural decoding.

Predictions are a JSON list of exact `{query_id, probabilities}` objects with
eight values in canonical angle order. All queries are required. Empty output
is penalized for all queries. Unknown IDs, unassignable row types and calibration
IDs invalidate all queries; duplicated known IDs invalidate that query even if
their values agree. A malformed extra field invalidates its identifiable query.
The committed candidate may not read the private intake or scoreboard, change
frozen membership, or receive feedback. Producer teardown, immutable sources,
bindings and isolated grading must be authenticated by the future owner.

Conditions are `native_A`, `program_B`, `tools_C`, `augmented_program_B`, or
`augmented_tools_C`. They are declared labels; the evaluator cannot verify what
information produced probabilities. Strict A/B/C comparisons require identical
nine-map packets and construction budgets. Embedded/callable learned weights
must remain separately augmented, with training/exposure provenance recorded.
The paired-summary helper preserves condition separation and makes no matched-
information assertion. Public pretraining exposure remains unresolved.

Scores contain per-session aggregates and the complete source census, never
trial IDs, labels or probability vectors. Actual score objects remain private
until explicitly selected for reporting. No genuine input or result is bundled.
