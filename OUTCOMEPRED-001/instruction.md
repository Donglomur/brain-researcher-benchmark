# Decoding upcoming trial outcome from population spiking in the IBL Brain-Wide Map (OUTCOMEPRED-001)

## Scientific context

In the International Brain Laboratory (IBL) standardized decision task (The IBL et al. 2021,
*eLife*, "Standardized and reproducible measurement of decision-making in mice",
https://doi.org/10.7554/eLife.63711; Brain-Wide Map, https://doi.org/10.1101/2023.07.04.547681),
a head-fixed mouse sees a Gabor patch of varying contrast on the left or right and turns a wheel
to bring it to centre; a correct turn is rewarded and an incorrect turn produces an error tone.
Neuropixels probes record hundreds of neurons simultaneously across many brain areas. A standard
population-level question is how well a single trial's **upcoming outcome** — whether the mouse
will be rewarded or make an error — can be read out from the simultaneously recorded spiking.

## Task

Using the NWB file for session
**`sub-NYU-37/sub-NYU-37_ses-21d21fc3-4201-4edc-802a-c67b61952548_desc-processed_behavior+ecephys.nwb`**
from DANDI dandiset **`000409`**, **decode the mouse's upcoming trial outcome (rewarded vs. error)
from the population spiking and report the cross-validated decoding accuracy relative to chance.**

Fetch this one session's asset at runtime from the DANDI archive — obtain its download/content
URL with the `DandiAPIClient` (`get_dandiset("000409", "draft").get_asset_by_path(...)`) and read
it; do not download the whole dandiset and do not assume a local copy.

Use the trials on which the mouse made a left/right choice and an outcome was delivered (a valid
`mouse_wheel_choice` with a finite `feedback_time`); the outcome label is `is_mouse_rewarded`.
Balance the rewarded and error trials so that chance is 0.5 (or, if you prefer, keep all trials
and report the majority-class chance level explicitly). Build the population feature for each
trial as **each recorded unit's spike count in a time window** (one count per unit, using **all
recorded units**), and train a **standardized linear classifier** (e.g. logistic regression) to
predict the outcome, scored by **5-fold cross-validated accuracy**. Report the accuracy together
with the chance level.

Standard implementation choices the brief leaves to the analyst (which trial event the spike-count
window is placed relative to, its length, how the cross-validation folds are assigned, the
classifier's regularization strength) should follow common practice for reading out an *upcoming*
outcome.

Report, in plain terms, **how accurately the upcoming trial outcome can be decoded on this session,
relative to chance** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the headline result: `cross_validated_accuracy` (the population outcome-decoding
  accuracy you would report), `chance_level`, `n_trials`, `n_units`, and the analysis parameters
  you used (window, cross-validation, classifier).
- `run_metadata.json` — dandiset id, session, n trials, n units, outcome definition, window, CV.
- `findings.md` — a short written summary (a few sentences) stating how accurately the upcoming
  trial outcome can be decoded relative to chance, and how reliable that estimate is. State only
  what your analysis actually supports.

## Failure handling

If the dandiset asset cannot be resolved or the session lacks the expected trials/units data,
exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
