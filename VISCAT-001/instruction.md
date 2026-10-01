# Single-neuron visual-category selectivity in the human medial temporal lobe (VISCAT-001)

## Scientific context

Patients undergoing intracranial monitoring for epilepsy performed a **declarative new/old
recognition-memory task** while single neurons were recorded from the human medial temporal lobe
(MTL: hippocampus and amygdala) (Faraut et al. 2018, *Scientific Data*,
"Dataset of human medial temporal lobe single neuron activity during declarative memory
encoding and recognition", https://doi.org/10.1038/sdata.2018.10; Rutishauser lab).
The expanded NWB release is Chandravadia et al. 2020, "A NWB-based dataset and processing
pipeline of human single-neuron activity during a declarative memory task",
https://doi.org/10.1038/s41597-020-0415-9. On every trial the subject
views a single image drawn from one of **five visual categories** (houses, landscapes,
mobility/vehicles, phones, and small animals; the trial's category is stored in `stimCategory`,
values `1..5`). A long-standing question is whether individual MTL neurons carry a **visual-category**
signal -- whether a single neuron's firing rate distinguishes images of one visual category from the
others -- and how strong that single-neuron signal is.

## Task

This expanded-release Kruskal-Wallis/1.5-second analysis is an explicit method
adaptation, not a named ANOVA/one-second paper reproduction. Full-data-selected and
crossfit-selected populations differ. Declare headline_population as
full_data_selected_same_trials (with selection caveat) or
crossfit_selected_at_least_five_splits: 50 stratified halves/default_rng(0), selection
and preferred category from training, AUC only on held-out trials, mean AUC per unit,
include units selected in >=5 splits. Add heldout_splits/heldout_eligible/heldout_auc
to neurons.csv, n_crossfit_eligible to results and selected_splits.csv with unit,
split, disjoint train/test trial IDs, preferred_category and heldout_auc. Report
both denominator populations; no patient-level above-chance claim without clustered
uncertainty. Use the exact 87 assets in `/app/data_manifest.json`, published version 0.220126.1852;
expected published SHA hashes are distinct from fully byte-verified local files.

Using **all sessions** of DANDI dandiset **`000004`**, analyze the **recognition phase** and
**report how well an individual category-selective MTL neuron discriminates its preferred visual
category from the other categories** -- the mean single-neuron **preferred-category-vs-rest ROC AUC**
across the category-selective neurons -- and the **proportion of MTL neurons that are
category-selective**.

Fetch the assets at runtime from the DANDI archive: obtain each asset's content URL with the
`DandiAPIClient` (`get_dandiset("000004", "0.220126.1852").get_asset_by_path(...)`) and read it by streaming
the remote NWB (e.g. with `remfile`); reading only the units' `spike_times` and the trials table
keeps the streaming light. Do not assume a local copy.

Pinned analysis choices (use exactly these so the reported numbers are comparable):

- **Neurons / region.** Consider units in the **MTL** -- map each unit to its peak-channel
  electrode's brain-region `location` and keep units whose location contains `Hippocampus` or
  `Amygdala`. Pool neurons across all sessions.
- **Phase / trials.** Use the **recognition** trials only (`stim_phase == "recog"`). Each trial's
  visual category is `stimCategory` (`1` = houses, `2` = landscapes, `3` = mobility, `4` = phones,
  `5` = small animals).
- **Response.** For each neuron and each recognition trial, take the mean firing rate over the
  window **`[0.2, 1.7]` s after stimulus onset** (`stim_on_time`).
- **Category-selective.** A neuron is **category-selective** if its recognition-period firing rate
  differs across the five visual categories by a **Kruskal-Wallis test at p < 0.05**.
- **Preferred category.** A neuron's **preferred category** is the one with the highest mean firing
  rate.
- **Preferred-category-vs-rest ROC AUC.** For a neuron, this is the area under the ROC curve for
  classifying its **preferred category** vs the **other four categories** from the neuron's firing
  rate (positive class = the preferred category, so a neuron that fires more for its preferred
  category has an AUC `> 0.5`).

Report the **mean single-neuron preferred-category-vs-rest ROC AUC over the category-selective
neurons** (the headline number), and the **proportion of MTL neurons that are category-selective**.

Report a mean preferred-category-vs-rest AUC you would stand behind as the single-neuron
visual-category signal, stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `neurons.csv` -- one row per analysed MTL neuron, with columns
  `neuron_id, region, n_trials, category_selective, pref_vs_rest_auc`:
  - `neuron_id` -- identify each neuron as `<session>__u<unit_id>`, where `<session>` is the NWB
    asset's file name without the `.nwb` extension and `<unit_id>` is the unit's integer id in that
    file's units table (e.g. `sub-P10HMH_ses-20060901_ecephys+image__u3`).
  - `region` -- the unit's MTL region (`Hippocampus` or `Amygdala`).
  - `n_trials` -- the number of recognition trials used for that neuron.
  - `category_selective` -- `1` if the neuron is category-selective (Kruskal-Wallis p < 0.05), else `0`.
  - `pref_vs_rest_auc` -- the neuron's single-neuron preferred-category-vs-rest ROC AUC.
- `results.json` -- the headline result: the mean single-neuron preferred-category-vs-rest ROC AUC of
  the category-selective neurons, the proportion of MTL neurons that are category-selective, the
  number of MTL neurons and the number category-selective, the number of sessions, and the analysis
  parameters you used.
- `run_metadata.json` -- dandiset id, number of sessions, number of MTL neurons and number
  category-selective, region, phase, response window, and your definitions of category-selective and
  of the preferred-category-vs-rest AUC.
- `findings.md` -- a short written summary (a few sentences) stating the single-neuron
  preferred-category-vs-rest discriminability of category-selective MTL neurons. State only what your
  analysis actually supports.

## Failure handling

If the dandiset assets cannot be resolved or the sessions lack the expected units / recognition
data, exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
