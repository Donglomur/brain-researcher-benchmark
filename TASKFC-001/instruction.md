# Task-state functional connectivity of a co-engaged visual region pair (TASKFC-001)

## Scientific context

During a visual language-localizer task, occipital visual cortex is strongly engaged by
the rapid serial visual presentation of the stimuli. A basic quantity of interest is the
**functional connectivity between homologous left and right visual regions while the task
is being performed** — i.e., how strongly the two regions' BOLD signals co-vary during the
task run. Task-state functional connectivity of this kind is routinely reported alongside
activation results and is used to compare coupling across regions, conditions, and groups.

## Task

Using the nilearn-pinned language-localizer demonstration dataset
(`nilearn.datasets.fetch_language_localizer_demo_dataset`, **all 10 subjects**; each subject
has one preprocessed BOLD run of the `languagelocalizer` task, a 6-parameter motion
confounds file, and a BIDS `events.tsv` describing the block timing of the two stimulus
conditions, `language` and `string`), **estimate the task-state functional connectivity
between the left and right lateral occipital cortex during the task run, and report how
strongly these two regions are coupled.**

Define the two regions as **8 mm-radius spheres** centred on the MNI coordinates

* left lateral occipital cortex  — **(-30, -90, -6)**
* right lateral occipital cortex — **( 30, -90, -6)**

For each subject, extract the mean BOLD time series from each sphere and quantify the
functional connectivity between the two regions across the task run (Pearson correlation of
the regional time series; aggregate across subjects with a Fisher *z* transform). The
standard preprocessing choices the analysis leaves to the analyst (nuisance regression,
detrending, temporal filtering, signal normalisation) should follow common practice.

Report, in plain terms, **the task-state functional connectivity between the two regions**
and what it says about how these regions are coupled during the task. State only what your
analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.csv` — one row per subject: `subject, region_a, region_b, connectivity`
  (the per-subject functional connectivity between the two regions).
- `connectivity_summary.json` — the group-level connectivity (Fisher-*z* averaged Pearson
  correlation) between the two regions as `{"group_connectivity": ..., "n_subjects": ...}`,
  plus any additional connectivity summaries you computed.
- `run_metadata.json` — dataset id, n subjects, ROI definition (coordinates, radius), and
  the preprocessing choices you made.
- `findings.md` — a short written summary reporting the task-state functional connectivity
  between the two regions and what it indicates about their coupling during the task. State
  only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `connectivity_summary.json`, and
`findings.md`.
