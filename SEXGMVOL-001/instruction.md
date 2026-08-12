# Reproducing the gray-matter-volume sex difference (SEXGMVOL-001)

## Scientific context

Whether total **gray-matter (GM) volume** differs between the sexes is a long-standing question in
structural neuroimaging, and the most-cited answer is that **men have larger gray-matter volume than
women**. A meta-analysis of sex differences in human brain structure (Ruigrok et al., 2014,
*Neuroscience & Biobehavioral Reviews*, https://doi.org/10.1016/j.neubiorev.2013.12.004) reports
that males have larger absolute volumes, including total gray matter. Voxel-based morphometry (VBM)
on T1-weighted MRI yields per-subject gray-matter maps whose total is a direct measure of GM volume.

## Task

Using the nilearn OASIS VBM dataset (`nilearn.datasets.fetch_oasis_vbm`, 403 subjects), **reproduce
this gray-matter sex difference and report whether it holds on these data.**

For each subject, compute **total gray-matter volume** as the sum over the subject's **modulated**
gray-matter probability map (modulation preserves absolute volume). Restrict to **healthy adults**
(`cdr == 0` in the phenotypic table `ext_vars`; sex is the `mf` column), and test whether total GM
volume **differs by sex** — report an effect size, t and p, and the direction of the difference. The
standard analytic choices the analysis leaves to the analyst (how the per-subject volumes are
summarised and compared between groups) should follow common practice.

Report, in plain terms, **whether the gray-matter-volume sex difference reproduces on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** OASIS cross-sectional VBM (nilearn), providing modulated gray-matter probability maps
in MNI space plus a phenotypic table (`ext_vars`) with `mf` (sex), `age`, and `cdr` (clinical
dementia rating). It is downloaded programmatically at runtime by the loader below — nothing is
pre-placed in the container, so **internet access is required** on the first run (the download is
cached locally afterwards). Fetch it with:

```python
from nilearn.datasets import fetch_oasis_vbm
oasis = fetch_oasis_vbm(n_subjects=403)   # oasis.gray_matter_maps, oasis.ext_vars
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `gm_sex.json` — the number of male/female subjects and the sex difference in gray-matter volume
  (e.g. effect size, t, p, and the direction), plus any analytic choices you made.
- `gm_subjects.csv` — one row per subject in your analysis sample, with at least the subject id, sex,
  and that subject's total gray-matter volume (the per-subject data behind the group comparison).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary stating whether the gray-matter-volume sex difference
  reproduces on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `gm_sex.json`, and `findings.md`.
