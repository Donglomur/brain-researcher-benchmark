# Connectivity and age across ABIDE sites (GROUPAGEFC-001)

## Scientific context

Functional connectivity changes systematically with age across development (Dosenbach et al.,
2010, *Science*, https://doi.org/10.1126/science.1194144 — resting-state functional connectivity
tracks brain maturation). ABIDE pools resting-state data from ~20 acquisition sites, which differ
in their mean age. Because the sites together span a wide age range, comparing acquisition sites is
a natural way to summarise the connectivity–age relationship across the cohort.

## Task

Using the provided ABIDE cc200 bundle (see **Data**), **characterise the relationship
between functional connectivity and age.**

Form each subject's **mean connectivity** from their connectome — summarise the subject's Fisher-z
connectome edges as a single per-subject mean-connectivity value. The sites (`site`) differ in mean
age, so a natural way to summarise the connectivity–age relationship across the cohort is to compare
sites: form each site's **mean connectivity** and **mean age** (over sites with enough subjects) and
relate site-mean connectivity to site-mean age across sites.

The standard choices the analysis leaves to the analyst (the connectivity metric, how per-subject
connectivity is summarised, the correlation type, and the minimum subjects per site) should follow
common practice.

Report, in plain terms, **the strength of the connectivity–age relationship** — stating only what
your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state cc200 connectomes, provided **in the container** at
`${BUNDLE_DIR}/cc200_ecolog.npz` (default `/opt/bundle`) — no download, **no network access is
available or needed** (the data is already present). Load it locally with
`numpy.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_ecolog.npz"), allow_pickle=True)`.
It holds:

- `X` — a subjects × **19,900** array: each row is one subject's upper-triangle functional
  connectome over the Craddock-200 (cc200) parcellation (Pearson correlation between ROI time
  series, Fisher-z transformed). A subject's mean connectivity is the average of that row's edges.
- `age` — each subject's age at scan (`AGE_AT_SCAN`), in years.
- `site` — each subject's acquisition site (`SITE_ID`), a string label (~20 sites).

The bundle is already restricted to subjects with a valid age and site. Do not substitute a
different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity_age.json` — the number of subjects and sites, a per-site summary (`site_summary`:
  each site's label, its number of subjects, its mean connectivity, and its mean age), and the
  connectivity–age relationship your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the connectivity–age relationship. State only what your
  analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `connectivity_age.json`, and `findings.md`.
