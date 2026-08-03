# Gray-matter correlates of cognition (COGVBM-001)

## Scientific context

A large literature relates individual differences in **gray-matter** structure to **cognitive
ability**. The OASIS resource provides voxel-based-morphometry (VBM) gray-matter maps together
with a cognitive measure (`mmse`, the Mini-Mental State Examination) and `age`, enabling a
whole-brain search for the gray-matter correlates of cognition.

## Task

Using the nilearn-pinned OASIS VBM gray-matter maps
(`nilearn.datasets.fetch_oasis_vbm`, which ship `gray_matter_maps` and an `ext_vars` table with
`age` and `mmse`), test **which gray-matter voxels are associated with cognition (`mmse`)**
across subjects, **controlling for age**. Identify the voxels significantly associated with
MMSE and report them.

The standard analytic choices the analysis leaves to the analyst (mask, statistical test) should
follow common practice.

Report, in plain terms, **whether and where gray matter is associated with cognition on these
data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `mmse_associations.json` — `n_voxels_tested`, `n_significant` (the number of voxels you
  conclude are **significantly associated** with MMSE), and `n_subjects`.
- `run_metadata.json` — dataset, number of subjects, the test used, the covariate, analytic
  choices.
- `findings.md` — a short written summary of whether/where gray matter is associated with
  cognition. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `mmse_associations.json`, and
`findings.md`.
