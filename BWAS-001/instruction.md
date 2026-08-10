# Brain-wide association of functional connectivity with IQ (BWAS-001)

## Scientific context

A large literature in **brain-wide association studies (BWAS)** relates individual differences in
resting-state **functional connectivity** to cognitive and behavioural phenotypes — including
**IQ**. The ABIDE resource (Di Martino et al., 2014, *Molecular Psychiatry*,
https://doi.org/10.1038/mp.2013.78) provides resting-state fMRI together with full-scale IQ
(`FIQ`) for a large sample, enabling a brain-wide association analysis of which functional
connections track IQ.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's ROI×ROI functional connectivity over the **Craddock-200 (cc200)** parcellation
(Fisher-z-transformed correlations over the upper triangle), and **characterise the brain-wide
association between functional connectivity and full-scale IQ (`FIQ`)** across subjects: test each
connection's association with IQ (an edgewise correlation of the connection strength with `FIQ`
across subjects), identify the connections associated with IQ, and report how strong that
association is.

The standard preprocessing and analytic choices the analysis leaves to the analyst (nuisance
regression, temporal filtering, signal normalisation) should follow common practice.

Report, in plain terms, **whether and how strongly functional connectivity is associated with IQ
on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200) + FIQ phenotype. It is downloaded programmatically
at runtime by the loader in the Task section — nothing is pre-placed in the container, so
**internet access is required** on the first run (the download is cached locally afterwards). Fetch
it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `iq_association.json` — the **strongest** connectivity–IQ association you find (`max_abs_r`
 and its `r_squared`), the number of connections associated with IQ, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, the test used, analytic choices.
- `findings.md` — a short written summary of whether and how strongly connectivity is associated
 with IQ on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `iq_association.json`, and `findings.md`.
