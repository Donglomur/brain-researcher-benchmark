# NEURAL-100 typed investigation claims

Submit a separate `claims.json` alongside the unchanged numerical `report.json`. The runner README specifies their output arguments. This document defines every claims field; there are no free-text claim fields or optional extra keys. Use JSON booleans and `null`, and integer support counts rather than strings or booleans. Include the full 47-recording, 41-participant released panel and all eight conditions. Recording row order may vary; identities and membership may not.

The grader first admits both complete artifacts before independently computing the private numerical reference. It then compares these typed interpretations with that same full analysis. A well-formed but scientifically incorrect assertion is a mismatch, not a schema rejection. There is no scientific-reasoning scalar, pass threshold, or SOTA decision. Numerical errors remain separate. Correct typed interpretation does not establish empirical input use, physical timing calibration, model reasoning, or biological causality.

## Top-level object

The exact keys are `schema`, `task_id`, `contract`, `scope`, `interpretation`, `recordings`, and `conditions`.

| Field | Required structure |
| --- | --- |
| `schema` | `"neural100_investigation_claims_v1"` |
| `task_id` | `"NEURAL-100"` |
| `contract` | `"neural100_released_panel_draft_v1"` |
| `scope` | Exactly `{"recordings":47,"participants":41,"source_area_recording_counts":{"A1":39,"A2":8}}` |
| `interpretation` | The exact object below |
| `recordings` | Exactly 47 objects joined to the supplied roster |
| `conditions` | Exactly the eight condition keys below, each containing a condition claim |

The eight condition keys are `primary`, `threshold_2_5`, `threshold_3_5`, `bins_2ms`, `boundary_erosion_one_depth`, `baseline_pseudo_onset`, `development_snr_bin_contact_matched`, and `first_spike_median_descriptive`.

## Interpretation object

Include all eleven boolean assertions below. Each name states the proposition asserted by `true`; `false` denies that proposition.

- `exact_paper_reproduction`
- `physical_timing_calibration_established`
- `complete_window_observation_required`
- `zero_events_prove_observed_silence`
- `causal_pathway_established`
- `manuscript_area_counts_reconciled`
- `pseudo_onset_is_calibrated_permutation_p_value`
- `first_spike_is_chase_young_significance_estimator`
- `intervals_are_simultaneous_significance_declarations`
- `development_matching_establishes_exact_snr_or_biological_matching`
- `boundary_erosion_reconstructs_anatomical_shifts`

Include these three additional fields in the same object:

| Field | Allowed values |
| --- | --- |
| `aggregation_unit` | `"participant"`, `"recording"`, `"unit"`, or `"trial"` |
| `repeated_recordings` | `"average_within_participant_area"` or `"independent_recordings"` |
| `primary_condition` | One of the eight condition keys |

The allowed alternatives make incorrect interpretations expressible and gradeable; they do not amend the frozen scientific protocol.

## Recording objects

Each recording object has exactly `recording_id`, `participant_id`, `area`, `conditions`, and `first_spike_evidence`. The first three values must match that recording's roster row. Its `conditions` object contains all eight condition keys. Each condition value has exactly:

```json
{
  "direction": "L6_earlier",
  "layer_status": {"L4": "defined", "L6": "defined"}
}
```

This is an invented structural example, not an expected recording answer. Every `direction` field in the artifact permits exactly `"L6_earlier"`, `"L6_later"`, `"equal"`, or `"undefined"`. Interpret negative L6−L4 as earlier L6, positive as later L6, numeric zero as equal, and a null contrast as undefined. Each layer status is `"defined"` or `"undefined"`.

`first_spike_evidence` has exactly `L4` and `L6`. Each layer has exactly `status`, `conditional_scope`, `test_trials`, `spiking_trials`, and `no_spike_trials`.

| Field | Allowed values and representation |
| --- | --- |
| `status` | `"retained"` or `"ungradable_missing_full_reference_evidence"` |
| `conditional_scope` | `"spiking_test_trials_only"` or `"all_test_trials"` |
| Three trial counts | For retained evidence: integers from 0 through 2^53, with `spiking_trials + no_spike_trials == test_trials`. For ungradable evidence: all three must be `null`. |

The first-spike median is conditional on trials with a population spike in [1,50) ms. It is distinct from threshold-crossing latency and from a significance-corrected first-spike estimator. The exact core's no-target-unit branch does not retain all three support counts; those missing fields are ungradable. Do not infer a missing count by subtraction or convert missing evidence to zero. The grader reports unavailable evidence separately, and it still checks an unsupported assertion that evidence was retained. A missing event does not certify observed neural silence because complete-window observation remains an assumption.

## Condition objects and area objects

Each top-level condition value has exactly `estimator` and `areas`. `estimator` allows `"population_threshold"`, `"pre_stimulus_pseudo_onset"`, or `"conditional_first_population_spike"`. Report all six population-detector conditions separately: primary, both threshold alternatives, two-ms bins, boundary erosion, and development matching. Baseline pseudo-onset describes pre-click detector behavior; first-spike medians are conditional descriptive estimates. Neither substitutes for the primary.

`areas` contains exactly `A1` and `A2`. Each area object has these exact fields:

| Field | Structure / allowed values |
| --- | --- |
| `full_cohort_direction` | A direction enum above, using the complete participant mean |
| `observed_only_direction` | A direction enum above, using the separately labeled defined-participant mean |
| `observed_only_scope` | `"full_cohort"`, `"defined_participants_only"`, or `"no_defined_participants"` |
| `participant_support` | Exactly `recorded`, `defined`, `undefined`: integers in [0,41], with defined + undefined = recorded |
| `recording_support` | Exactly `recorded`, `defined`, `undefined`: integers in [0,47], with defined + undefined = recorded |
| `interval` | The exact interval object below |
| `direction_relation_to_primary` | `"same"`, `"different"`, or `"unavailable"` |

First average repeats within participant and area, then average participants equally. One undefined repeat makes that participant undefined; any undefined participant withholds the full-area mean. An observed-only mean must not be presented as the full cohort. Recording support counts defined recording contrasts; participant support counts defined within-participant aggregates. A condition's relation to the primary compares their full-cohort direction categories within the same area. It is unavailable when either full direction is undefined. This field is descriptive and is not a robustness or significance threshold.

`interval` has exactly `position`, `defined_draws`, `undefined_draws`, and `complete_unconditional_interval`:

- `position` is `"strictly_below_zero"`, `"strictly_above_zero"`, `"contains_zero"`, or `"withheld"`. A bound equal to zero means contains zero, including [0,0].
- `defined_draws` and `undefined_draws` are integers in [0,1000] whose sum is 1000.
- `complete_unconditional_interval` is a boolean asserting that the complete, unconditioned interval is available.

Intervals are pointwise descriptive percentiles. Retain the full 1,000 shared participant draws; do not redraw or condition on successful draws. Even a defined full-area mean may have a withheld interval if a draw contains no participant from that area. Area-absent draw counts are identical across conditions under the same draw schedule. An undefined full-area mean is not a zero effect, and a withheld interval is not a confidence interval at zero.

## Grading output

The claims comparison reports matching field paths, typed mismatch paths, and ungradable evidence paths separately. It does not release the private expected per-recording counts in mismatch messages. Missing or duplicate recordings, missing conditions, extra fields, invalid enums/types, or broken count partitions are malformed submissions. Well-formed assertions about direction, support, intervals, estimators, and scientific scope can be wrong and remain gradeable. A separate prose explanation may be useful to readers, but it is not silently folded into this typed comparison.
