# Functional connectivity and age across the ABIDE sample (CC200) — a case study

## Scientific context

The **ABIDE** (Autism Brain Imaging Data Exchange) initiative aggregates resting-state fMRI from
~20 acquisition sites spanning childhood to adulthood. Because ABIDE is a **multi-site** sample,
an association measured by pooling every participant (a *marginal* association) and the same
association measured *within* sites (a *site-conditioned* association) can differ. This case study
asks you to characterise how a whole-brain summary of functional connectivity relates to age in
ABIDE, and to **distinguish the marginal association from the site-conditioned one**.

This is **not** a reproduction of any specific paper; it is a self-contained ABIDE case study on
the pinned CC200 preprocessed derivatives.

## Task

Using the pinned ABIDE preprocessed resting-state sample, compute each participant's overall
functional connectivity strength from the Craddock-200 (CC200) parcellation, then estimate and
report the connectivity–age association **at three levels — pooled (marginal), within-site
(site-conditioned), and between-site — each with a measure of uncertainty**, plus basic
sensitivity checks.

### Data

The pinned inputs are the ABIDE CC200 ROI timeseries for a fixed subject list (see
`environment/`). If a baked snapshot is present the solution reads it directly (no network);
otherwise the same selection is obtained with nilearn:

```python
from nilearn.datasets import fetch_abide_pcp
abide = fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True,
                        global_signal_regression=False,
                        derivatives=["rois_cc200"], quality_checked=False)
```

`abide["rois_cc200"]` is a list of per-participant region×time arrays (200 CC200 regions);
`abide["phenotypic"]` is a table aligned row-for-row and contains `FILE_ID`, `AGE_AT_SCAN`,
`SITE_ID`, `SEX`, `DX_GROUP`, and `func_mean_fd` (mean framewise displacement). The pinned
selection is the **cpac / band_pass_filtering=True / global_signal_regression=False / rois_cc200**
derivatives with `quality_checked=False` (see `environment/subject_ids.txt` for the exact
`FILE_ID` list and count).

### Fixed processing (pin exactly)

- For each participant: drop any CC200 region with zero temporal variance, form the
  region×region **Pearson correlation matrix** across the CC200 time series, and
  **Fisher z-transform** the correlations.
- Define the participant's **overall connectivity strength** as the **mean of the
  upper-triangular (off-diagonal) Fisher-z values**.
- Pair each participant's connectivity strength with `AGE_AT_SCAN`; drop participants with
  missing age (keep `0 < age < 120`).

### Estimate and report (three levels, with uncertainty)

1. **Marginal / pooled** — the connectivity–age correlation across all participants
   (Pearson r, a 95% CI, p, n).
2. **Site-conditioned / within-site** — the connectivity–age correlation **after conditioning on
   site** (e.g. site fixed effects / site-demeaning / a partial correlation controlling for
   `SITE_ID`), with a 95% CI and p. Use a minimum per-site sample where appropriate.
3. **Between-site** — the correlation of each site's **mean connectivity** with its **mean age**
   across sites, with a 95% CI.

### Sensitivity checks (report as outputs)

Add basic robustness checks and report their results in `sensitivity.json`:
- **motion / QC** — the association adjusting for `func_mean_fd`;
- **diagnosis** — the association restricted to typical controls (`DX_GROUP == 2`);
- **sex** — the association adjusting for `SEX`;
- **nonlinear age** — whether an `age²` term materially changes the connectivity model;
- **site-specific slopes** — the distribution of the per-site connectivity–age relationship
  (heterogeneity across sites).

### Interpretation (state a bounded conclusion)

Report what the three levels imply. In particular, say whether the marginal association is
**site-conditioned** (i.e. carried by between-site differences and attenuated within sites) or
survives conditioning on site. **Do not over-claim**: these data are cross-sectional (one scan
per participant), and `SITE_ID` conflates scanner, protocol and cohort composition — so do not
assert that scanner hardware *caused* any association, and do not claim a *true null* (a
near-zero within-site estimate with a wide CI is not proof that there is no age relationship at
any site or no within-person developmental change).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.csv` — one row per participant with at least the participant identifier
  (`FILE_ID`), `connectivity` (overall connectivity strength), `age`, and `site_id`.
- `connectivity_age.json` — at minimum
  `{"pooled_r": <float>, "pooled_ci95": [<float>,<float>], "pooled_p": <float>,
  "within_site_r": <float>, "within_site_ci95": [<float>,<float>], "within_site_p": <float>,
  "between_site_r": <float>, "between_site_ci95": [<float>,<float>], "n": <int>,
  "n_sites": <int>, "atlas": "cc200"}`.
- `sensitivity.json` — the five sensitivity checks above (motion, diagnosis, sex, nonlinear age,
  site-specific slopes), each with its numeric result.
- `run_metadata.json` — dataset id, pipeline/derivative, atlas, number of participants and sites,
  the connectivity metric, and the methods used at each level.
- `findings.md` — a short write-up reporting the three-level result with uncertainty and stating
  the bounded conclusion. State only what your analysis supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `connectivity_age.json`, and `findings.md`.
