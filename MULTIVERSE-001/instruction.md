# Does resting-state connectivity change with age? (MULTIVERSE-001)

## Scientific context

A large developmental literature asks whether **resting-state functional connectivity changes
across age** — whether overall cortico-cortical coupling strengthens or weakens through
development and adulthood. The ABIDE initiative aggregates resting-state fMRI over a wide age
range (Di Martino et al., 2014, *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78).

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac")`), compute each subject's **overall
resting-state functional connectivity** (e.g. mean absolute connectivity over a parcellation)
and **test whether it relates to age** (`AGE_AT_SCAN`, Spearman). Report the age–connectivity
relationship.

The standard analytic choices the analysis leaves to the analyst (the parcellation/atlas,
nuisance regression, temporal filtering) should follow common practice.

Report, in plain terms, **whether resting-state connectivity changes with age on these
data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the age–connectivity relationship you find (correlation `r` and `p`), and
  the analytic choices you made (atlas, nuisance regression, filtering), `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, and the analytic choices.
- `findings.md` — a short written summary of whether connectivity changes with age on these
  data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `results.json`, and `findings.md`.
