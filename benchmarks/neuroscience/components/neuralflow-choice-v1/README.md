# Premotor choice benchmark components

Four independent Python standard-library components support construction of a benchmark around [The dynamics and geometry of choice in the premotor cortex](https://doi.org/10.1038/s41586-025-09199-1). They implement row projection, participant-visible choice features, grouped split planning and choice scoring. Scientific preparation and full benchmark qualification remain incomplete.

## Use

Import the module from this directory:

```python
from neuralflow_adapter import (
    adapt_rows, choice_feature_view, protected_split_plan, score_choices,
)

# Supply complete, independently verified rows and a frozen evaluator roster.
projection = adapt_rows(
    units_rows, trial_rows, spike_rows, population_roster,
    source_clock=confirmed_clock,
    endpoint_policy=confirmed_endpoint,
)
choice_inputs = choice_feature_view(projection)
assignments = protected_split_plan(
    trial_rows, evaluator_secret=private_secret_bytes,
)
choice_scores = score_choices(
    private_target_rows, prediction_rows, population_roster,
)
```

The names supplied in this example represent caller-owned records, not included data. Do not infer clock or endpoint conventions from the example. `source_clock` must be explicitly confirmed as `absolute_seconds` or `stimulus_relative_seconds`; `endpoint_policy` must be `closed` or `left_closed_right_open`. No authentic convention has been established by these components.

| Input | Required fields |
|---|---|
| Unit metadata rows | `subject_id`, `session_id`, `analysis_type`, ordered `uids` |
| Trial rows | `subject_id`, `session_id`, `trial_id`, `stim_onset`, `reaction_times`, `correct_response`, `stim_difficulty`, `chosen_side`, `recorded_units` |
| Spike rows | `subject_id`, `session_id`, `trial_id`, `unit_id`, `spike_times` |
| Population roster | `population_id`, `subject_id`, `session_id`, ordered `uids` |
| Private scoring targets | `population_id`, `subject_id`, `session_id`, `trial_id`, `chosen_side` |
| Predictions | The same case identifiers, `probability_right`, `fit_status` |

Current adapters accept nonnegative integer IDs and preserve integers above 2^53. Authentic native column types still require verification. Population IDs are strings. Subjects are 0 for monkey T and 1 for monkey O; sides are `Left`/`Right`, difficulty is `easy`/`hard`. Prediction status is `fit` or `fallback_after_fit_failure`.

The complete roster must contain all 30 population attempts, 15 per monkey, with at least three units per population and all four stimulus-direction/difficulty conditions. Population identity includes unit membership; original unit order is retained in a reversible dense-neuron map. Missing spike rows are errors, while an explicit empty spike array represents silence. The window begins 120 ms after stimulus onset and ends at movement time under the declared clock and endpoint policy.

The full projection contains private choice targets. Use the whitelisted `choice_feature_view` for choice inputs; supply labels separately for declared training cases only. Its `lono_safe=False` flag is intentional: it retains all neurons' spikes and is unsuitable for held-neuron evaluation. Split assignments and their secret remain evaluator-owned. This module does not implement an isolated execution environment.

The split planner assigns each subject/session/trial once across neural views, stratifies by stimulus direction, difficulty and choice, and uses a private HMAC ordering. Each observed stratum requires at least three trials. That is an engineering feasibility requirement, not adequate scientific sample-size evidence. Stimulus direction is a disclosed covariate; the monkey's actual choice is the prediction target.

The choice scorer requires exact case coverage and retains failed fits through declared fallback predictions. It reports per-population balanced accuracy, log loss and Brier score, then weights populations equally within each monkey and monkeys equally. Both choices must occur in each scored population. Historical Viterbi hard decisions are not calibrated probabilities; historical two-half scores also require separate fold scoring and averaging.

## Engineering checks

From this directory:

```sh
python3 -B -m unittest discover -s . -p test_neuralflow_adapter.py -v
python3 -B -m unittest discover -s peer -p test_independent_review.py -v
```

The byte-identical source was previously accepted with 22 author controls and four independent controls. Copying it into this standalone layout did not trigger duplicate test runs. All fixtures are invented engineering examples. The controls cover complete-cohort enforcement, identity and original-order preservation, exact timestamp boundaries, missing versus silent neurons, target isolation, grouped assignments, failure coverage and independently calculated scores. Passing these checks establishes no biological result or benchmark qualification.

## Provenance and scientific limits

Field names follow the description accompanying [Figshare version 1](https://doi.org/10.6084/m9.figshare.29052116.v1). Package semantics were inspected at [NeuralFlow commit 508cf7b](https://github.com/engellab/neuralflow/tree/508cf7b6de2759d90dda774837ab90e0a0fbfb52); the paper links [archive v3.0.0](https://zenodo.org/records/15426288). These links establish provenance references, not a verified executed revision. This directory includes authored component code and invented tests, with no recordings, fitted models, official library bodies, private manifests or reference answers.

Authentic cohort IDs and exclusions, native table schemas, spike clocks and endpoints, original splits, archive-to-execution mapping and runtime configuration remain unresolved. There is no native Parquet reader or model runner here. All 30 attempts must remain represented when those gaps are resolved.

The complete scientific task also requires shared-geometry evidence, reaction-time-normalized spike likelihood, held-neuron prediction, matched competent references, grouped uncertainty and protected end-to-end evaluation. Choice accuracy alone cannot identify latent dynamics. The scorer therefore always reports `complete_contract_evaluation=False`; these components cannot certify the full task or a frontier improvement.
