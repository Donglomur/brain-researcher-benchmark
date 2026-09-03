# Single-neuron new/old discriminability in the human medial temporal lobe (MTLMEMORY-001)

## Scientific context

Patients undergoing intracranial monitoring for epilepsy performed a **declarative new/old
recognition-memory task** while single neurons were recorded from the human medial temporal lobe
(MTL: hippocampus and amygdala) (Faraut et al. 2018, *Scientific Data*,
"A NWB-based dataset and processing pipeline of human single-neuron activity during a declarative
memory task", https://doi.org/10.1038/sdata.2018.10; Rutishauser lab). In each session the subject
first **learns** a set of images, then in a **recognition** phase views a mix of previously seen
(**old / familiar**) and never-seen (**new / novel**) images and rates each on a new/old confidence
scale. A long-standing question is whether individual MTL neurons carry a memory signal -- whether a
single neuron's firing rate distinguishes novel from familiar images -- and how strong that
single-neuron signal is.

## Task

Using **all sessions** of DANDI dandiset **`000004`**, analyze the **recognition phase** and
**report how well an individual memory-selective MTL neuron discriminates novel from familiar
images** -- the mean single-neuron **new/old ROC AUC** across the memory-selective neurons -- and the
**proportion of MTL neurons that are memory-selective**.

Fetch the assets at runtime from the DANDI archive: obtain each asset's content URL with the
`DandiAPIClient` (`get_dandiset("000004", "draft").get_asset_by_path(...)`) and read it by streaming
the remote NWB (e.g. with `remfile`); reading only the units' `spike_times` and the trials table
keeps the streaming light. Do not assume a local copy.

Pinned analysis choices (use exactly these so the reported numbers are comparable):

- **Neurons / region.** Consider units in the **MTL** -- map each unit to its peak-channel
  electrode's brain-region `location` and keep units whose location contains `Hippocampus` or
  `Amygdala`. Pool neurons across all sessions.
- **Phase / trials.** Use the **recognition** trials only (`stim_phase == "recog"`). Each recognition
  trial is labelled novel or familiar by `new_old_labels_recog` (`"0"` = new/novel, `"1"` =
  old/familiar).
- **Response.** For each neuron and each recognition trial, take the mean firing rate over the
  window **`[0.2, 1.7]` s after stimulus onset** (`stim_on_time`).
- **Memory-selective.** A neuron is **memory-selective** if its recognition-period firing rate
  differs between novel and familiar trials by a **two-sided Wilcoxon rank-sum test at p < 0.05**.
- **New/old ROC AUC.** For a neuron, the new/old ROC AUC is the area under the ROC curve for
  classifying novel vs familiar trials from the neuron's firing rate. Because a memory neuron may
  fire more for novel images (a novelty cell) or more for familiar images (a familiarity cell),
  take the AUC in the neuron's **preferred direction** (equivalently `max(AUC, 1 - AUC)`), so that
  every memory neuron contributes a value `>= 0.5`.

Report the **mean single-neuron new/old ROC AUC over the memory-selective neurons** (the headline
number), and the **proportion of MTL neurons that are memory-selective**.

Standard implementation choices the brief leaves to the analyst -- for example tie handling in the
rank-sum test and in the ROC computation, and how neurons with very few trials are treated -- should
follow common practice for a defensible single-neuron discriminability estimate. Report a mean
new/old AUC you would stand behind as the single-neuron memory signal, stating only what your
analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: the mean single-neuron new/old ROC AUC of the
  memory-selective neurons, the proportion of MTL neurons that are memory-selective, the number of
  MTL neurons and the number memory-selective, the number of sessions, and the analysis parameters
  you used.
- `run_metadata.json` -- dandiset id, number of sessions, number of MTL neurons and number
  memory-selective, region, phase, response window, and your definitions of memory-selective and of
  the new/old AUC.
- `findings.md` -- a short written summary (a few sentences) stating the single-neuron new/old
  discriminability of memory-selective MTL neurons. State only what your analysis actually supports.

## Failure handling

If the dandiset assets cannot be resolved or the sessions lack the expected units / recognition
data, exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
