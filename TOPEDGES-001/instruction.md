# Reproducing the autism-vs-control functional-connectivity differences (TOPEDGES-001)

## Scientific context

A cornerstone case–control finding in autism neuroimaging is that resting-state **functional
connectivity differs between autism (ASD) and typically-developing (TD) controls**. The ABIDE
initiative (Di Martino et al., 2014, *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78),
aggregating resting-state fMRI across many sites, established that a set of cortico-cortical
connections separates ASD from TD, and a standard analysis identifies **which connections differ
most** between the groups and reports **how strongly** they differ (their effect sizes). These "top"
group-differentiating connections are routinely reported as the strongest autism connectivity
signatures.

## Task

Using the provided ABIDE cc200 connectome bundle (`${BUNDLE_DIR}/cc200_connectomes.npz`: `X` = subjects ×
**19,900 upper-triangle edges** of the Craddock-200 functional connectome — Pearson correlation,
Fisher-z transformed; `y` = diagnosis, 1 = ASD, 2 = TD; `subjects` = IDs; ~400 subjects),
**reproduce this ASD-vs-control connectivity-difference result and report whether it holds on these
data.**

For each edge, compute the **group-difference effect size — Cohen's d** (ASD vs TD, pooled SD) across
subjects. **Rank the edges by |d| and take the top 100** most-differing connections, and report those
**top differing connections and their effect sizes** (the Cohen's d of each).

Report, in plain terms, **whether the autism-vs-control connectivity differences reproduce on these
data, and how large the differences at the top connections are** — stating only what your analysis
actually supports.

## Data

**Dataset:** ABIDE cc200 connectomes (subjects × 19,900 upper-triangle edges of the Craddock-200
functional connectome — Pearson correlation, Fisher-z transformed), provided **in the container** at
`${BUNDLE_DIR}/cc200_connectomes.npz` (default `/opt/bundle`). Load it locally — **no network access is
available or needed** (the data is already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_connectomes.npz"),
            allow_pickle=True)
X = d["X"]              # ~400 subjects × 19,900 Fisher-z edges
y = d["y"]              # diagnosis, 1 = ASD, 2 = TD
subjects = d["subjects"]  # subject IDs
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `top_differences.json` — the `top_connections` (each an ROI-pair with its effect size, Cohen's d), how many connections were taken, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects per group, the effect size used, and the
  analytic choices you made.
- `findings.md` — a short written summary of which connections most differ, how strongly they differ,
  and whether those differences hold on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `top_differences.json`, and `findings.md`.
