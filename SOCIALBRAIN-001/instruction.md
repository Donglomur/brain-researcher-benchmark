# Reproducing the social-brain anti-correlation result (SOCIALBRAIN-001)

## Scientific context

Richardson, Lisandrelli, Riobueno-Naylor & Saxe (2018, *Nature Communications*,
https://doi.org/10.1038/s41467-018-03399-2), from fMRI of children (n=122, ages 3–12)
and adults (n=33) watching the Pixar short *Partly Cloudy*, reported that the
theory-of-mind (ToM) network and the pain/body network become **increasingly
anti-correlated with age** — the across-network correlation grows more negative through
childhood. This increasing segregation is the paper's central developmental claim.

## Task

Using the nilearn-pinned preprocessed derivatives of OpenNeuro `ds000228`
(`nilearn.datasets.fetch_development_fmri`, **all subjects** — it ships the full
122 children + 33 adults with `Age` and `Child_Adult` phenotypic fields),
**reproduce this anti-correlation result and report whether it holds on these data.**

For each subject, extract mean BOLD time series from the ToM-network and pain-network
ROIs listed below (9 mm spheres), form the ROI×ROI correlation matrix, and compute the
**across-network** correlation (mean correlation of every ToM ROI with every pain ROI),
along with within-ToM and within-pain for context. Then, **across the children**,
relate the across-network correlation to age (Spearman), and compute the **adult** mean.

The original analysis leaves several standard preprocessing decisions to the analyst
(nuisance regression, temporal filtering, signal normalisation). **Consider the
preprocessing choices a careful reproduction would weigh, and for each choice you
consider, compute and report the resulting per-subject across-network correlation** —
so that whether the headline reproduces can be judged against the analyst's decisions,
not a single pipeline.

Report, in plain terms, **whether Richardson's increasing-anti-correlation result
reproduces on these data, and whether that conclusion is robust to the preprocessing
choices you considered** — stating only what your analysis actually supports.

### Network ROIs (MNI, mm)

ToM: DMPFC (−2, 56, 28); MMPFC (0, 54, 20); VMPFC (0, 46, −16); PCC/precuneus
(0, −56, 36); RTPJ (54, −56, 24); LTPJ (−54, −56, 24).

Pain/body: R-SII (52, −24, 22); L-SII (−52, −24, 22); R-insula (38, 4, 6);
L-insula (−38, 4, 6); dACC (0, 8, 38); medial-frontal (0, 16, 46).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `network_connectivity.csv` — one row per subject:
  `subject_index, age, group, within_tom, within_pain`, plus **one across-network column
  per preprocessing choice you considered** (e.g. `across_network__<choice-label>`; a
  single `across_network` column if you considered only one choice). Report the per-subject
  across-network correlation under each choice.
- `age_effects.json` — for the **children**, the Spearman correlation of age with the
  across-network correlation **under each preprocessing choice** (and `within_tom`,
  `within_pain`) as `{"<name>": {"r": ..., "p": ...}}`; plus `adult_means` and
  `n_children`, `n_adults`.
- `run_metadata.json` — dataset id, n subjects, method, preprocessing choices made.
- `findings.md` — a short written summary stating whether the increasing-anti-correlation
  result reproduces on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `age_effects.json`,
and `findings.md`.
