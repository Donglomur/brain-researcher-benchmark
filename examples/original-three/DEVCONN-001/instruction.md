# Reproducing the developmental "local-to-distributed" connectivity finding (DEVCONN-001)

## Scientific context

A well-established developmental-neuroimaging finding (Fair et al. 2009, *PLoS
Computational Biology*, "Functional Brain Networks Develop from a 'Local to Distributed'
Organization"; see also Dosenbach et al. 2010) is that functional connectivity
**reorganizes from a local to a distributed pattern across development**: young children
show relatively **stronger short-range** cortico-cortical functional connectivity, and
connectivity becomes progressively **less locally dominated with age**. This shift toward
a more distributed organization is one of the most-cited maturational signatures of the
developing functional connectome.

## Task

Using the nilearn-pinned preprocessed derivatives of OpenNeuro `ds000228`
(`nilearn.datasets.fetch_development_fmri`, **all subjects** — it ships the full
122 children + 33 adults, with `Age` and `Child_Adult` phenotypic fields),
**reproduce this local-to-distributed developmental result and report whether it holds
on these data.**

For each subject, extract mean BOLD time series from the **Power et al. (2011) 264-ROI
coordinate atlas** (`nilearn.datasets.fetch_coords_power_2011`, 5 mm spheres) and form the
ROI×ROI correlation matrix. Bin the ROI pairs by the **Euclidean distance between ROI
coordinates**, and define **short-range** and **long-range** connectivity as the mean
correlation over, respectively, the **bottom tertile** and the **top tertile** of the
ROI-pair distance distribution. A useful summary of local dominance is the **segregation
index** = short-range − long-range.

Then quantify the developmental effect: across the children, relate short-range
connectivity (and the segregation index) to **age** (Spearman), and compare the
**children vs adults** group means. The standard preprocessing choices the analysis leaves
to the analyst (nuisance regression, temporal filtering, signal normalisation) should
follow common practice.

Report, in plain terms, **whether the local-to-distributed developmental result reproduces
on these data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.csv` — one row per subject:
  `subject_index, age, group, short_range, long_range, segregation`.
- `age_effects.json` — for the **children**, the Spearman correlation of age with
  `short_range`, `long_range`, and `segregation` as
  `{"children_age_spearman": {"<name>": {"r": ..., "p": ...}}}`; plus `group_means`
  (child vs adult per measure) and `n_children`, `n_adults`.
- `run_metadata.json` — dataset id, n subjects, atlas, distance bins, and the
  preprocessing choices you made.
- `findings.md` — a short written summary stating whether the local-to-distributed
  developmental result reproduces on these data. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `age_effects.json`,
and `findings.md`.
