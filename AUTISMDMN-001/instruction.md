# Group differences in resting-state connectivity in autism (AUTISMDMN-001)

## Scientific context

A large literature asks whether **autism spectrum disorder (ASD)** shows altered resting-state
functional connectivity relative to **typically-developing (TD) controls**. A frequently-cited
example is reduced connectivity within the **default-mode network** (PCC/mPFC) in ASD (Assaf et al.,
2010, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.05.067). The ABIDE initiative
(Di Martino et al., 2014, *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78) aggregates
resting-state fMRI across sites specifically to test such case-control connectivity differences at
scale, and the whole-brain edgewise comparison — which connections differ between the groups — is the
result these analyses report.

## Task

Using the provided ABIDE **Dosenbach-160** connectome bundle (`dos160_autconn.npz`; described
under **Data** below), **characterise which resting-state functional connections differ between ASD
and TD controls** on these data.

Each subject already has an ROI×ROI functional connectome as the upper triangle of the 160×160
Fisher-z correlation matrix — the **160×159/2 = 12,720 unique connections**. Compare the two groups
**edge by edge** — a two-sample contrast of ASD vs TD at each connection — and report the connections
you conclude **significantly differ**, plus the within-default-mode-network connectivity in each group
for context (the Assaf claim).

This is a multi-site case-control sample: the subjects come from **20 acquisition sites** and the
groups differ in **head motion**, **age** and **sex**. Standard analytic choices the brief leaves to
the analyst — how you handle these nuisance variables, how degenerate/NaN edges are dealt with, the
exact test — should follow common practice for a case-control connectivity comparison; the brief does
not spell them out. Report only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 connectomes (`cpac`, band-pass filtered, no
global-signal regression), provided **in the container** at `${BUNDLE_DIR}/dos160_autconn.npz`
(default `/opt/bundle`). Load it locally — **no network access is available or needed** (the data is
already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_autconn.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **12,720** Fisher-z edges (upper triangle of the 160×160 Pearson connectome;
  a degenerate/flat ROI leaves its edges as `NaN`).
- `dx` — diagnosis, **1 = ASD, 2 = TD** control.
- `site` — acquisition site label (20 sites).
- `age` — age at scan (years).
- `sex` — 1 / 2.
- `motion` — mean framewise displacement (head motion) per subject.
- `networks` — the Dosenbach-160 network label of each of the 160 ROIs (e.g. `default` = DMN), same
  ROI order as `X`'s connectome, so within-DMN edges can be identified.

(On the order of ~1000 subjects across 20 acquisition sites, roughly balanced between ASD and TD.)
Do not substitute a different or manually-prepared dataset, and do not attempt any network download.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `group_differences.json` — `n_edges_tested`, `n_significant` (the number of connections you conclude
  **significantly differ** between the groups), and the significant connections (as a list of ROI-pair
  indices in `[0,159]`, or a summary), plus the within-DMN connectivity per group for context.
- `run_metadata.json` — dataset, atlas, number of subjects per group, the test used, and the analytic
  choices you made.
- `findings.md` — a short written summary of whether/where ASD and TD controls differ in resting
  connectivity on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `group_differences.json`, and `findings.md`.
