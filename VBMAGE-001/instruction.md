# The cortical region with strongest age-related atrophy (VBMAGE-001)

## Scientific context

Gray-matter atrophy with age is one of the most robust findings in structural neuroimaging,
and identifying **where** atrophy is greatest — which cortical region declines most across the
lifespan — is a common voxel-based-morphometry (VBM) goal (Good et al., 2001, *NeuroImage*,
https://doi.org/10.1006/nimg.2001.0786).

## Task

Using the nilearn-pinned OASIS VBM gray-matter maps
(`nilearn.datasets.fetch_oasis_vbm`, which ship `gray_matter_maps` and an `ext_vars` table with
`age`), relate **regional gray-matter** to **age** across subjects over a cortical parcellation
(e.g. Harvard-Oxford), and **identify the cortical region showing the strongest age-related
atrophy** (the most negative gray-matter–age relationship). Report which region atrophies most
with age.

The standard analytic choices the analysis leaves to the analyst (parcellation, spatial
**smoothing**, modulation) should follow common practice.

Report, in plain terms, **which cortical region shows the strongest age-related atrophy on
these data** — stating only what your analysis actually supports.

## Data

**Dataset:** OASIS-1 VBM gray-matter maps. It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_oasis_vbm(n_subjects=...)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `atrophy.json` — the `top_atrophy_region` (the cortical region with the strongest age-related
  atrophy), its age–gray-matter correlation, `n_subjects`, and the analytic choices you made
  (parcellation, smoothing).
- `run_metadata.json` — dataset, parcellation, number of subjects, smoothing, analytic choices.
- `findings.md` — a short written summary of which region atrophies most with age and how
  confident you are in it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `atrophy.json`, and `findings.md`.
