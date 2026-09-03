# Decoding drift direction from a mouse V1 two-photon population (ALLEN Brain Observatory)

## Scientific context

In the Allen Brain Observatory (de Vries et al. 2020, *Nature Neuroscience*, "A large-scale
standardized physiological survey reveals functional organization of the mouse visual cortex",
https://doi.org/10.1038/s41593-019-0550-9), head-fixed mice passively view a battery of visual
stimuli while a two-photon microscope records the calcium activity (dF/F) of hundreds of
GCaMP6-expressing cortical neurons in a single field of view. One stimulus block is a **drifting
grating**: a full-field sinusoidal grating that drifts in one of 8 directions (0-315 deg in 45 deg
steps) at several temporal frequencies. A standard population-level question is how much information
about the stimulus the simultaneously recorded neurons carry -- for instance, **how accurately the
drift direction of the grating can be read out from the single-trial population response** with a
linear decoder.

## Task

Using the Allen Brain Observatory two-photon experiment with **`ophys_experiment_id =
501271265`** (a VISp, `three_session_A` recording that contains the drifting-gratings block),
**train a linear decoder to predict the drift direction of the grating from the single-trial
population response, and report the decoder's accuracy at predicting direction.**

Obtain the data at runtime with the AllenSDK `BrainObservatoryCache`: construct the cache with a
writable `manifest_file`, then call `get_ophys_experiment_data(501271265)` to get the
`BrainObservatoryNwbDataSet`. The dF/F traces come from `get_dff_traces()` and the stimulus timing
from `get_stimulus_table('drifting_gratings')`. The cache downloads the session's NWB from the
public Allen Institute API (no credentials); do not assume a local copy.

Pinned analysis choices (use exactly these so the reported number is comparable):

- **Neurons / features.** Use every neuron in the imaging field (each `cell_specimen_id` with a
  dF/F trace) as a feature of the population response vector.
- **Trials and labels.** Use the `drifting_gratings` stimulus table. Each row has an `orientation`
  (drift direction, 0-315 deg in 45 deg steps), a `temporal_frequency`, and a `blank_sweep` flag;
  drop the blank sweeps and use every non-blank grating presentation as one trial, with the
  **drift direction (8 classes)** as its label. **Pool across temporal frequency** -- the label is
  the drift direction regardless of temporal frequency.
- **Single-trial response.** For each neuron and each grating presentation, take the **mean dF/F
  over the presentation window** (the frames from the presentation's `start` to `end`); the
  population response of a trial is the vector of these values across neurons.
- **Decoder.** A **linear** multi-class classifier on the single-trial population response vectors
  (for example a linear support vector machine or multinomial logistic regression), with the
  features standardized. Report the classification **accuracy** (fraction of trials whose direction
  is predicted correctly), and note the chance level (1/8).

Standard implementation choices the brief leaves to the analyst should follow common practice for
population decoding -- report an accuracy you would stand behind as this field's read-out accuracy
for drift direction, stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: `decoding_accuracy` (the accuracy you would report), the
  chance level, the number of neurons, the number of trials, the number of directions, and the
  analysis parameters you used.
- `run_metadata.json` -- experiment id, targeted structure, session type, number of neurons,
  number of grating trials, number of directions, chance level, and a short description of the
  decoder and how you estimated its accuracy.
- `findings.md` -- a short written summary (a few sentences) stating how accurately drift direction
  can be decoded from this VISp field and how reliable that estimate is. State only what your
  analysis actually supports.

## Failure handling

If the experiment cannot be resolved or the session lacks the expected dF/F traces or
drifting-gratings data, exit non-zero with `failed_precondition` and a non-empty reason, and still
write a parseable `run_metadata.json`, `results.json`, and `findings.md`.
