# Orientation-/direction-selective fraction in mouse V1 from two-photon calcium responses to drifting gratings (ALLEN2P-001)

## Scientific context

In the Allen Brain Observatory (de Vries et al. 2020, *Nature Neuroscience*, "A large-scale
standardized physiological survey reveals functional organization of the mouse visual cortex",
https://doi.org/10.1038/s41593-019-0550-9), head-fixed mice passively view a battery of visual
stimuli while a two-photon microscope records the calcium activity (dF/F) of hundreds of
GCaMP6-expressing cortical neurons in a single field of view. One stimulus block is a **drifting
grating**: a full-field sinusoidal grating that drifts in one of 8 directions (0-315 deg in 45 deg
steps) at several temporal frequencies. A basic characterization of primary visual cortex
(**VISp**) is what fraction of the imaged neurons are **orientation- or direction-selective** --
respond much more strongly to one grating orientation (or one drift direction) than to the
orthogonal orientation (or the opposite direction).

## Task

Using the Allen Brain Observatory two-photon experiment with **`ophys_experiment_id =
501271265`** (a VISp, `three_session_A` recording that contains the drifting-gratings block),
**report the fraction of the imaged neurons that are orientation- or direction-selective (OSI or
DSI above threshold) in their responses to the drifting gratings.**

Obtain the data at runtime with the AllenSDK `BrainObservatoryCache`: construct the cache with a
writable `manifest_file`, then call `get_ophys_experiment_data(501271265)` to get the
`BrainObservatoryNwbDataSet`. The dF/F traces come from `get_dff_traces()`, the cells from
`get_cell_specimen_ids()`, and the stimulus timing from
`get_stimulus_table('drifting_gratings')`. The cache downloads the session's NWB from the public
Allen Institute API (no credentials); do not assume a local copy.

Pinned analysis choices (use exactly these so the reported number is comparable):

- **Neurons.** Consider every neuron in the imaging field (each `cell_specimen_id` with a dF/F
  trace).
- **Stimulus.** Use the `drifting_gratings` stimulus table. Each row has an `orientation` (drift
  direction, 0-315 deg in 45 deg steps), a `temporal_frequency`, and a `blank_sweep` flag; drop
  the blank sweeps (null orientation / temporal frequency) from the tuning conditions but keep them
  available as a no-stimulus baseline.
- **Response.** For each neuron and each grating presentation, take the **mean dF/F over the
  presentation window** (the frames from the presentation's `start` to `end`).
- **Tuning, OSI and DSI.** For each neuron, take its **preferred condition** -- the (direction,
  temporal frequency) with the largest mean response over the non-blank conditions -- and at that
  preferred temporal frequency read off the direction tuning across the 8 drift directions. With
  `R_pref` the response at the preferred direction, `R_orth` the mean response at the two
  orthogonal directions (preferred +/- 90 deg) and `R_null` the response at the opposite direction
  (preferred + 180 deg), define

  - **OSI = (R_pref - R_orth) / (R_pref + R_orth)**
  - **DSI = (R_pref - R_null) / (R_pref + R_null)**

- **Selective.** A neuron counts as selective if **OSI > 0.5 or DSI > 0.5**.

Report the **fraction of imaged neurons that are selective**, i.e. the number of selective neurons
divided by the number of imaged neurons.

Standard implementation choices the brief leaves to the analyst should follow common practice for
characterizing single-cell tuning in a two-photon population -- report a number you would stand
behind as the selective fraction of this field, stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: `selective_fraction` (the fraction you would report), the
  number of imaged neurons total and the number you analyzed, the number selective, the OSI/DSI
  threshold, and the analysis parameters you used.
- `run_metadata.json` -- experiment id, targeted structure, session type, number of imaged neurons
  (total and analyzed), number of drifting-gratings presentations, OSI/DSI definition and
  threshold.
- `findings.md` -- a short written summary (a few sentences) stating the orientation-/direction-
  selective fraction of this VISp field and how reliable that estimate is. State only what your
  analysis actually supports.

## Failure handling

If the experiment cannot be resolved or the session lacks the expected dF/F traces or
drifting-gratings data, exit non-zero with `failed_precondition` and a non-empty reason, and still
write a parseable `run_metadata.json`, `results.json`, and `findings.md`.
