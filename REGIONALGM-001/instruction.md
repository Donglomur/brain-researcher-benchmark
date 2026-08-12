# Localized sex differences in gray-matter volume (REGIONALGM-001)

## Scientific context

A common structural-neuroimaging analysis localizes *where* in the brain gray-matter volume differs
most between groups and reports the strength of that difference in the identified region. Total head
size (estimated total intracranial volume, eTIV) differs between groups and is routinely adjusted
for before looking for regionally specific differences, so that what remains reflects local
tissue rather than overall brain size.

## Task

Using the nilearn OASIS VBM dataset (`nilearn.datasets.fetch_oasis_vbm`, 150 subjects), from the
modulated gray-matter maps and each subject's sex (`mf`) and head size (`eTIV`) in `ext_vars`,
**adjust the gray-matter maps for head size, then identify the brain region whose gray-matter
volume differs most between the sexes and report the strength / significance of that regional sex
difference.**

Concretely: residualize each voxel's gray-matter value on `eTIV` to remove the global head-size
effect, locate the cluster of voxels with the largest male–female difference, and report the
significance of the sex difference in that region. The standard analytic choices the analysis
leaves to the analyst (brain masking, voxel selection, how significance is assessed) should follow
common practice.

Report, in plain terms, **whether there is a localized sex difference in gray-matter volume beyond
overall head size, and how strong it is** — stating only what your analysis actually supports.

## Data

**Dataset:** OASIS cross-sectional VBM (nilearn) — modulated gray-matter maps + a phenotypic table
(`ext_vars`) including sex (`mf`) and head size (`eTIV`). Downloaded programmatically at runtime;
**internet access is required** on the first run (cached afterwards):

```python
from nilearn.datasets import fetch_oasis_vbm
oasis = fetch_oasis_vbm(n_subjects=150)  # oasis.gray_matter_maps, oasis.ext_vars['mf'], oasis.ext_vars['eTIV']
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `roi.json` — the number of subjects and the significance / strength of the region's sex
 difference that your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the region's sex difference. State only what your
 analysis actually supports.

You may also write any supporting tables your analysis produces (e.g. the per-subject values you used).

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `roi.json`, and `findings.md`.
