# Decoding upcoming choice from mouse cortical population spiking (STEINMETZ-001)

## Scientific context

In the Steinmetz et al. (2019, *Nature*, "Distributed coding of choice, action and
engagement across the mouse brain", https://doi.org/10.1038/s41586-019-1787-x) task, a
head-fixed mouse views gratings of varying contrast on left and/or right screens and, after
a go cue, turns a wheel to bring the higher-contrast grating to centre — a left or right
choice (or holds still on no-go trials). Neuropixels probes record hundreds of neurons
simultaneously across many brain areas. A standard population-level question is how well the
animal's **upcoming choice** can be read out from the simultaneously recorded spiking.

## Task

Using the NWB file for session **`sub-Cori/sub-Cori_ses-20161214T120000.nwb`** from DANDI
dandiset **`000017`**, **decode the mouse's upcoming left/right choice from the population
spiking and report the cross-validated decoding accuracy.**

Fetch this one session's asset at runtime from the DANDI archive — obtain its download/content
URL with the `DandiAPIClient` (`get_dandiset("000017").get_asset_by_path(...)`) and read it;
do not download the whole dandiset and do not assume a local copy.

Use the trials the dataset marks as valid (the `included` flag) that have a left or right
choice (`response_choice` = −1 or +1; drop no-go / `0`). Build the population feature for each
trial as **each recorded unit's spike count in a 250 ms window** (one count per unit, using
**all recorded units**), and train a **standardized linear classifier** (e.g. logistic
regression) to predict the choice, scored by **5-fold cross-validated accuracy**. Report the
accuracy together with the chance level.

Standard implementation choices the brief leaves to the analyst (which trial event the 250 ms
window is placed relative to, how the cross-validation folds are assigned, the classifier's
regularization strength) should follow common practice for reading out an *upcoming* decision.

Report, in plain terms, **how accurately the upcoming choice can be decoded on this session,
relative to chance** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the headline result: `cross_validated_accuracy` (the population choice-decoding
  accuracy you would report), `chance_level`, `n_trials`, `n_units`, and the analysis parameters
  you used (window, cross-validation, classifier).
- `run_metadata.json` — dandiset id, session, n trials, n units, choice definition, window, CV.
- `findings.md` — a short written summary (a few sentences) stating how accurately the upcoming
  choice can be decoded relative to chance, and how reliable that estimate is. State only what
  your analysis actually supports.

## Failure handling

If the dandiset asset cannot be resolved or the session lacks the expected trials/units data,
exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
