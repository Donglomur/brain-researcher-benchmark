# Cortical graph efficiency: a threshold-sensitivity control

Estimate how a declared graph-construction recipe affects participant-level
binary global efficiency. Use all 40 released ADHD-200 subset runs and the
original Schaefer-2018 100-parcel/17-network/2-mm cortical atlas. This is a
paper-derived **method control**, not a reproduction of a paper's cohort or
numerical finding, a clinical comparison, or a ranking of intrinsic brain function.

Latora and Marchiori (2001), Eq. 1, motivates averaging reciprocal shortest-path
lengths. Here the graph is specifically undirected and binary, and unreachable
pairs contribute zero. Van den Heuvel et al. (2017), Methods and Fig. 3, motivates
examining threshold sensitivity; it does not establish that equal density removes
confounding. The five-density grid and 40-person/Schaefer100 analysis below are
explicit task adaptations, not settings copied from those results.

## Public inputs and method

All inputs are already available offline in `/app/data/netinteg`; its
`source_manifest.json` specifies the exact original paths, participant identities,
sizes and SHA256 pins. Do not download or substitute data. The authoritative
public recipe and complete nested output schemas are `/app/method_contract.json`.
Read it before analysis. The ADHD source is released preprocessed data: its complete
inherited processing history is not established. Its usage terms are noncommercial
research; the atlas/software license does not override those terms.

Use the following fixed recipe, with any numerically equivalent implementation:

1. Resample **labels**, not BOLD, to each original 3-mm BOLD grid. Use nearest
   neighbor with the public affine, half-voxel and background rules. Retain all
   100 original parcel IDs and take float64 spatial means over their assigned voxels.
2. Retain every original frame. Regress the supplied 17-column confound set,
   including `global` and `linearTrend`, using the public centering, constant-column,
   SVD rank and residual numerical-zero rules. Add no filtering, smoothing or
   scrubbing. Form empirical Pearson correlations of the cleaned parcel signals;
   do not silently use a shrinkage covariance estimator.
3. Construct five proportional binary graphs at densities
   `[0.05, 0.075, 0.10, 0.15, 0.20]`, requesting respectively
   `[248, 371, 495, 742, 990]` of the 4,950 unordered pairs. Order **signed**
   correlations, include every exact tie at the cutoff, and report realized density.
   Also construct the three required absolute-cutoff graphs at `[0.2, 0.3, 0.4]`.
   Keep isolates and use all 4,950 pairs in every efficiency denominator.
4. The primary score is the equal arithmetic mean of the five proportional
   efficiencies, not an integral or AUC. Report full rankings for it and all eight
   configurations. Top-eight sets include everyone tied at the eighth score;
   ordering within exact ties is free. Use average ranks for Spearman correlations.
5. Report both signed mean connectivity and the mean positive part (sum of
   `max(r,0)` divided by **all** 4,950 pairs), as well as all public sensitivity
   diagnostics. No effect sign, correlation magnitude, rank reversal, disjoint
   top set or preferred thresholding convention is assumed or required.

## Outputs

Write these six files to `${OUTPUT_DIR}` (default `/app/output`):

- `connectomes.csv`: all 198,000 participant/ROI-pair correlations.
- `graph_metrics.csv`: all 320 participant/configuration rows, including edge,
  cutoff-tie, connectivity, density and binary-efficiency measurements.
- `efficiency.csv`: all 40 participant primary scores and both strength measures.
- `ranking.json`: all full rankings, inclusive top-eight sets and the specified
  cohort-level correlations, overlap counts and density-pair sensitivities.
- `run_metadata.json`: exact source and method identities, observed source geometry,
  parcel coverage, frame/confound/rank records and actual software versions.
- `findings.md`: a concise account of the measured sensitivity and its limits.

The complete column names, JSON fields, undefined-value rules and numerical
tolerances are public in the method contract. CSV row/column order and harmless
extra descriptive fields are free. Alternative software is welcome. Exact source
and scientific identities are not optional. Numerical serialization rounding must
not redefine graph membership or create new ranking ties; retain full-precision
arrays internally. Narrative wording is not a grading keyword gate.

There is no proportional partial scoring: a complete source-consistent analysis
receives reward 1; an incomplete or inconsistent analysis receives 0. A matching
answer is not proof that a particular computation was executed. The authoring
reference is public in the repository but excluded from the runtime image, so
later model evaluation must account for possible answer contamination.

If a required source or numerical precondition fails, exit nonzero and write
`run_metadata.json` with `status=failed_precondition` and a reason, a header-only
`efficiency.csv`, and a nonempty `findings.md`. Do not silently drop a person,
parcel or frame, invent a correlation, or label a partial analysis successful.

## Sources

- Latora & Marchiori (2001), [Efficient Behavior of Small-World Networks, Eq. 1](https://arxiv.org/html/cond-mat/0101396v1).
- Van den Heuvel et al. (2017), [Proportional thresholding in resting-state fMRI functional connectivity networks and consequences for patient-control connectome studies](https://people.csail.mit.edu/ythomas/publications/2017Threshold-NeuroImage.pdf).
- [Pinned Nilearn 0.12.1 ADHD subset description and usage terms](https://raw.githubusercontent.com/nilearn/nilearn/0.12.1/nilearn/datasets/description/adhd.rst).
- [Original Schaefer atlas at the pinned CBIG commit](https://github.com/ThomasYeoLab/CBIG/tree/d1454a611f7de10a3b36665e6fbb3fb6c770d140/stable_projects/brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/MNI).
