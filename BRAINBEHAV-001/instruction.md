# Brain-wide association of functional connectivity with IQ (BRAINBEHAV-001)

## Scientific context

A large literature in **brain-wide association studies (BWAS)** relates individual differences in
resting-state **functional connectivity** to cognitive and behavioural phenotypes — including
**IQ**. The ABIDE resource (Di Martino et al., 2014, *Molecular Psychiatry*,
https://doi.org/10.1038/mp.2013.78) provides resting-state fMRI together with full-scale IQ
(`FIQ`) for a large sample, enabling a brain-wide association analysis of which functional
connections track IQ.

## Task

Using the provided ABIDE cc200 connectome bundle (`data/cc200_bwas.npz`), **characterise the
brain-wide association between functional connectivity and full-scale IQ (`FIQ`) across
subjects.** Each subject's connectome is the **Craddock-200 (cc200)** ROI×ROI functional
connectivity, Fisher-z-transformed, given as the **19,900 upper-triangle edges** (`X`).

For **each connection (edge)**, test its association with IQ — an **edgewise correlation** of the
connection strength with `FIQ` across subjects (Pearson correlation of column `X[:, e]` with
`fiq`). Then identify the connections associated with IQ and report **how strong** that
association is: the **strongest** connection's correlation and the variance it explains, the
typical (median) association, and how many connections are associated with IQ.

Standard analytic choices the analysis leaves to the analyst (e.g. whether to control for nuisance
covariates, how to handle multiple connections) should follow common practice.

Report, in plain terms, **whether and how strongly functional connectivity is associated with IQ
on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE cc200 connectomes + `FIQ` phenotype (`cpac`, band-pass filtered, no global-signal
regression), provided **in the container** at `${BUNDLE_DIR}/cc200_bwas.npz` (default `/opt/bundle`).
Load it locally — **no network access is available or needed** (the data is already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_bwas.npz"),
            allow_pickle=True)
X = d["X"]      # subjects x 19,900 float16 Fisher-z cc200 connectomes (upper triangle of 200x200)
fiq = d["fiq"]  # length-subjects float32 full-scale IQ (FIQ)
```

- `X` — a subjects × **19,900** array: each row is one subject's Fisher-z cc200 functional
  connectome, flattened as the **upper triangle** of the 200×200 ROI correlation matrix
  (`numpy.triu_indices(200, 1)` order, so edge *e* is ROI-pair `(triu[0][e], triu[1][e])`).
- `fiq` — length-subjects array: each subject's full-scale IQ (`FIQ`).
- `atlas` = `"Craddock-200"`, `edges_upper_triangle_of` = `200` (metadata).

The bundle already contains only subjects with a valid `FIQ` and a fully finite connectome
(~925 subjects). Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `iq_association.json` — the **strongest** connectivity–IQ association you find (`max_abs_r` and
  its `r_squared`), the **median** association across edges, the number of connections associated
  with IQ, `n_subjects`, and the reported **top connections** (each an ROI-pair with its
  correlation).
- `edge_associations.csv` — one row per edge: `roi_i`, `roi_j`, `r` (its connectivity–IQ
  correlation), `p`. (The full per-edge association your analysis produced.)
- `run_metadata.json` — dataset, atlas, number of subjects, the test used, and the analytic
  choices you made.
- `findings.md` — a short written summary of whether and how strongly connectivity is associated
  with IQ on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `iq_association.json`, and `findings.md`.
