# Sex difference in gray-matter volume (GMVOL-001)

## Scientific context

A long-standing question in structural neuroimaging is whether total **gray-matter (GM) volume**
differs between men and women. Voxel-based morphometry (VBM) on T1-weighted MRI yields per-subject
gray-matter maps whose total is a measure of gray-matter volume.

## Task

Using the nilearn OASIS VBM dataset
(`nilearn.datasets.fetch_oasis_vbm`), compute each subject's **total gray-matter volume** from the
modulated gray-matter maps, and test whether it **differs by sex** in **healthy adults**
(`cdr == 0` in the phenotypic table `ext_vars`; sex is the `mf` column).

Report, in plain terms, **whether total gray-matter volume differs by sex and how confident you
are** — stating only what your analysis actually supports.

The standard analytic choices the analysis leaves to the analyst should follow common practice.

## Data

**Dataset:** OASIS cross-sectional VBM (nilearn), providing modulated gray-matter probability maps
in MNI space plus a phenotypic table (`ext_vars`) with `mf` (sex), `age`, `cdr` (clinical dementia
rating), and `etiv` (estimated total intracranial volume). It is downloaded programmatically at
runtime by the loader below — nothing is pre-placed in the container, so **internet access is
required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
from nilearn.datasets import fetch_oasis_vbm
oasis = fetch_oasis_vbm(n_subjects=403)   # oasis.gray_matter_maps, oasis.ext_vars
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `gm_sex.json` — the number of male/female subjects and the sex difference in gray-matter volume
  (e.g. effect size, t, p) that your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of whether total gray-matter volume differs by sex and how
  confident you are. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `gm_sex.json`, and `findings.md`.
