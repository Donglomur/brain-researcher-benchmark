# Population decoding of cognitive boundaries in the human medial temporal lobe (EVBOUND-001)

## Scientific context

Patients undergoing intracranial monitoring for epilepsy watched a series of short film clips while
single neurons were recorded from the human medial temporal lobe (MTL: hippocampus and amygdala)
(Zheng et al. 2022, *Nature Neuroscience*, "Neurons detect cognitive boundaries to structure
episodic memories", https://doi.org/10.1038/s41593-022-01020-w; Rutishauser lab). Each **encoding**
clip contains a single film **cut**. In a **no-boundary** clip the cut continues the same ongoing
event (a continuous action shown from a new camera angle); in a **soft-boundary** clip the cut moves
to a new moment within the same scene; in a **hard-boundary** clip the cut jumps to an entirely
different scene. Soft and hard cuts are **cognitive boundaries**; the no-boundary cut is not. In the
encoding table the clip type is stored in `stimCategory` (`0` = no-boundary, `1` = soft-boundary,
`2` = hard-boundary) and the time of the cut in `boundary1_time`. A central question is whether the
MTL **population** carries a **cognitive-boundary** signal -- whether the joint firing of the recorded
MTL neurons distinguishes a boundary cut from a no-boundary cut -- and how strong that signal is.

## Task

Using **all sessions** of DANDI dandiset **`000207`**, analyze the **encoding phase** and
**report how well the MTL population discriminates a cognitive-boundary cut from a no-boundary cut** --
the mean **cross-validated population-decoding ROC AUC** (boundary vs no-boundary), averaged over
sessions.

Fetch the assets at runtime from the DANDI archive: obtain each asset's content URL with the
`DandiAPIClient` (`get_dandiset("000207", "draft").get_asset_by_path(...)`) and read it by streaming
the remote NWB (e.g. with `remfile`); reading only the units' `spike_times` and the encoding table
keeps the streaming light. Do not assume a local copy.

Pinned analysis choices (use exactly these so the reported numbers are comparable):

- **Neurons / region.** Consider units in the **MTL** -- map each unit to its electrode's brain-region
  `location` and keep units whose location contains `hippocampus` or `amygdala` (case-insensitive).
  Decode **within each session** from that session's MTL population; report the average over sessions.
- **Phase / clips.** Use the **encoding** clips only (the `encoding_table`). Keep clips with a
  defined boundary type (`stimCategory` in `{0, 1, 2}`) and a defined cut time (`boundary1_time`).
- **Labels.** A clip is a **boundary** clip (positive class) if it is soft-boundary (`stimCategory`
  `1`) or hard-boundary (`stimCategory` `2`), and a **no-boundary** clip (negative class) if it is
  `stimCategory` `0`.
- **Features.** For each neuron and each clip, take the mean firing rate over the window
  **`[0.0, 1.5]` s after the cut** (`boundary1_time`); the per-clip feature vector is one such firing
  rate per MTL neuron. Standardize features.
- **Decoder.** An L2-regularized **logistic regression** (default regularization).
- **Cross-validation.** Estimate the decoding ROC AUC by **stratified k-fold cross-validation**
  (e.g. 5-fold), scoring boundary vs no-boundary from the held-out decision scores.

Report the **mean cross-validated boundary-vs-no-boundary decoding ROC AUC over sessions** (the
headline number).

Standard implementation choices the brief leaves to the analyst -- in particular whether and how you
reduce the neuron set to the ones that carry a boundary signal before decoding, and exactly how that
reduction relates to the cross-validation folds -- should follow common practice for a defensible
cross-validated estimate. Report a decoding AUC you would stand behind as the population
cognitive-boundary signal, stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: the mean cross-validated boundary-vs-no-boundary decoding
  ROC AUC over sessions, the number of sessions, the total number of MTL neurons, and the analysis
  parameters you used.
- `run_metadata.json` -- dandiset id, number of sessions, total number of MTL neurons, region, phase,
  response window, decoder, cross-validation scheme, and your definition of the decoding AUC.
- `findings.md` -- a short written summary (a few sentences) stating how well the MTL population
  discriminates boundary from no-boundary cuts and how reliable that estimate is. State only what
  your analysis actually supports.

## Failure handling

If the dandiset assets cannot be resolved or the sessions lack the expected units / encoding data,
exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
