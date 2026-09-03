# Functional network segregation in a developmental cohort (NETSEG-001)

## Scientific context

A hallmark of cortical functional organisation is that regions couple more strongly within
their own network than between networks. **System segregation** (Chan et al., 2014, *PNAS*,
https://doi.org/10.1073/pnas.1415122111) summarises this as the fraction by which mean
within-network connectivity exceeds mean between-network connectivity,

    S = (mean_within − mean_between) / mean_within,

and it changes systematically with development and ageing. Here you will quantify it in a
naturalistic movie-watching cohort of children and adults (Richardson et al., 2018,
*Nature Communications*).

## Data

nilearn's **developmental fMRI** sample, fetched at runtime (open, no credentials):

```python
from nilearn import datasets
dev = datasets.fetch_development_fmri(n_subjects=40)   # dev.func, dev.confounds, dev.phenotypic
atlas = datasets.fetch_atlas_schaefer_2018(n_rois=100, yeo_networks=7)
```

* `dev.func[i]` — a preprocessed BOLD run (MNI space), TR = 2 s.
* `dev.confounds[i]` — the matching confound-regressor table for that run. **Regress these
  confounds** when you extract the time series (standard practice for this sample).
* `dev.phenotypic` — a table with `participant_id`, `Age`, and `Child_Adult`
  (`child` / `adult`).
* `atlas.maps` / `atlas.labels` — the **Schaefer-2018 100-parcel / 7-network** cortical
  atlas. Each parcel label encodes its Yeo-7 network (e.g. `7Networks_LH_Default_1`), which
  gives the within-/between-network partition. Use this atlas.

Extract each participant's 100 parcel time series with a labels masker (regressing the
provided confounds, detrending, and z-scoring the series), and form the parcel×parcel Pearson
connectome. Do not substitute a different or manually-prepared dataset or atlas.

## Task

For **each of the 40 participants**, compute the **system segregation** of the cortical
connectome — the degree to which within-network connectivity exceeds between-network
connectivity, S = (mean_within − mean_between) / mean_within — from the Fisher-z transformed
Pearson connectome and the atlas's 7-network partition. Summarise the cohort: the average
system segregation, and how it differs between children and adults.

The details the measure leaves to the analyst should follow **common practice** for system
segregation; the brief does not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `segregation.csv` — one row per participant with at least a participant identifier and the
  system-segregation value; a `group` (child/adult) column may be included.
- `run_metadata.json` — dataset, atlas, number of participants, the preprocessing you
  applied, and the cohort-average system segregation.
- `findings.md` — a short written summary reporting the cohort-average system segregation and
  the child-vs-adult difference, stating only what your analysis supports.

## Failure handling

If the data cannot be fetched, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `segregation.csv`, and `findings.md`.
