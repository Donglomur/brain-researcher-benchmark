# Single-neuron working-memory load discriminability in the human medial temporal lobe (WMLOAD-001)

## Scientific context

Patients undergoing intracranial monitoring for epilepsy performed a **Sternberg working-memory
task** while single neurons were recorded from the human medial temporal lobe (MTL: hippocampus and
amygdala) and frontal cortex (Daume et al. 2024, *Nature*,
"Control of working memory by phase-amplitude coupling of human hippocampal neurons",
https://doi.org/10.1038/s41586-024-07309-z; Rutishauser lab). On each trial the subject **encodes**
either **one or three pictures**, holds them across a **maintenance (delay) period**, and is then
shown a **probe** and judges whether it was in the memorized set. A long-standing question is whether
individual MTL neurons carry a **working-memory load** signal -- whether a single neuron's
maintenance-period firing rate distinguishes trials on which one item vs three items are being held
-- and how strong that single-neuron signal is.

## Task

Using **all sessions** of DANDI dandiset **`000673`**, analyze the **maintenance (delay) period** and
**report how well an individual load-selective MTL neuron discriminates the working-memory load** (one
vs three items) from its firing rate -- the mean single-neuron **load ROC AUC** across the
load-selective neurons -- and the **proportion of MTL neurons that are load-selective**.

Fetch the assets at runtime from the DANDI archive: obtain each asset's content URL with the
`DandiAPIClient` (`get_dandiset("000673", "draft").get_asset_by_path(...)`) and read it by streaming
the remote NWB (e.g. with `remfile`); reading only the units' `spike_times` and the trials table
keeps the streaming light. Do not assume a local copy.

Pinned analysis choices (use exactly these so the reported numbers are comparable):

- **Neurons / region.** Consider units in the **MTL** -- map each unit to its peak-channel
  electrode's brain-region `location` and keep units whose location contains `hippocampus` or
  `amygdala` (case-insensitive). Pool neurons across all sessions.
- **Trials.** Use trials with working-memory **load 1** or **load 3** (the trials table column
  `loads`).
- **Epoch / response.** For each neuron and each trial, take the mean firing rate over the
  **maintenance (delay) period** -- from the maintenance-onset timestamp (`timestamps_Maintenance`)
  to the probe onset (`timestamps_Probe`). Because the delay length varies slightly across trials,
  use the firing **rate** (spike count divided by the window length).
- **Load-selective.** A neuron is **load-selective** if its maintenance-period firing rate differs
  between load-1 and load-3 trials by a **two-sided Wilcoxon rank-sum test at p < 0.05**.
- **Load ROC AUC.** For a neuron, the load ROC AUC is the area under the ROC curve for classifying
  load-1 vs load-3 trials from the neuron's maintenance firing rate. Because a load-tuned neuron may
  fire more for the higher load or more for the lower load, take the AUC in the neuron's **preferred
  load direction** (equivalently `max(AUC, 1 - AUC)`), so that every load-tuned neuron contributes a
  value `>= 0.5`.

Report the **mean single-neuron load ROC AUC over the load-selective neurons** (the headline number),
and the **proportion of MTL neurons that are load-selective**.

Standard implementation choices the brief leaves to the analyst -- in particular exactly which trials
are used to identify a neuron as load-selective and to fix its preferred load direction, versus which
trials are used to measure its load AUC -- should follow common practice for a defensible single-neuron
discriminability estimate. Report a mean load AUC you would stand behind as the single-neuron
working-memory load signal, stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: the mean single-neuron load ROC AUC of the load-selective
  neurons, the proportion of MTL neurons that are load-selective, the number of MTL neurons and the
  number load-selective, the number of sessions, and the analysis parameters you used.
- `run_metadata.json` -- dandiset id, number of sessions, number of MTL neurons and number
  load-selective, region, epoch, the loads compared, and your definitions of load-selective and of
  the load AUC.
- `findings.md` -- a short written summary (a few sentences) stating the single-neuron
  working-memory load discriminability of load-selective MTL neurons and how reliable that estimate
  is. State only what your analysis actually supports.

## Failure handling

If the dandiset assets cannot be resolved or the sessions lack the expected units / maintenance-period
data, exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
