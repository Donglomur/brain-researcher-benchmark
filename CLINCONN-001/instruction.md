# Resting connectivity and motion sensitivity in the CNP cohort

Estimate the signed schizophrenia–control association in resting-state
connectivity, and its sensitivity to mean framewise displacement (FD).
Report the measurements even if adjustment strengthens, reverses, or leaves
the association unchanged. No particular direction or null result is required.

This is a secondary method/sensitivity analysis of public CNP data, not a
reproduction of a schizophrenia finding in the dataset descriptor.
[Poldrack et al. 2016](https://doi.org/10.1038/sdata.2016.110) describes the cohort;
[Gorgolewski et al. 2017, Figure 1 and Table 1](https://f1000research.com/articles/6-1262/v2)
describes its preprocessing and unavailable derivatives. The distance-dependent
motion effects in [Power et al. 2012](https://doi.org/10.1016/j.neuroimage.2011.10.018)
motivate checking sensitivity; they do not determine this cohort's answer.

## Offline source and cohort

Use only the original files staged under `/app/data/clinconn`, authenticated by
the source manifest there. The bundle contains the legacy `ds000030_R1.0.5`
fsaverage5 resting surface derivatives, original confounds and phenotype/timing
metadata, and fixed Destrieux annotations and fsaverage5 pial meshes. Do not
download, resample, regenerate preprocessing, or substitute a newer dataset.

The original participants table identifies 177 candidates with a rest run and
diagnosis `SCHZ` or `CONTROL`. Five controls have no released left/right surface
or confound files: `sub-10299`, `sub-10428`, `sub-10501`, `sub-10971`, `sub-11121`.
They also appear in the preprocessing paper's missing-T1 list. Account for all
177 candidates, with these availability exclusions declared before analysis.
Analyze the fixed remaining 172 participants: 50 SCHZ and 122 CONTROL.
A missing or corrupt selected input is an error, not permission to drop a subject.

The exact legacy dataset metadata declares PDDL. File-specific redistribution
licensing for the supplied atlas/mesh copies is not established; do not equate
Nilearn's software license with a license for every bundled data file.

## Public analysis contract

`/app/method_contract.json` specifies the full estimator, source identities,
field names, undefined cases and tolerances. It is public; no undisclosed
denoising choice or expected diagnosis effect is needed.

- Use float64 equal-weight vertex means for anatomically named cortical
  parcels, with explicit annotation-based Unknown/Medial_wall exclusions.
  Use the source-bound pial centroid geometry; distance is Euclidean, not
  cortical geodesic distance or tract length.
- Detrend and bandpass both parcel series and the 13 declared nuisance columns,
  project out the nuisance span, then sample-standardize residuals. The band is
  0.009–0.08 Hz at TR 2 s. The contract fixes filter order, endpoint handling,
  rank and numerical-zero rules. Use each subject's actual released frame count;
  do not force equal scan durations, add GSR, or censor frames.
- Mean FD uses defined successive-frame measurements. An undefined first FD
  is excluded from its denominator, not treated as measured zero. Later
  missing or negative FD is a failed precondition. Keep all original BOLD frames.
- Compute Pearson correlations and the disclosed clipped Fisher transform.
  Use the same cohort-wide valid edges for every subject, summary and model.
  Define short and long ranges by strict distance-tercile boundaries, including
  the contract's treatment of ties; do not recompute them in a subgroup.
- For short-range connectivity, report three signed OLS diagnosis coefficients:
  all-cohort crude, all-cohort adjusted for mean FD, and crude within the strict
  `mean_fd < 0.2` subset. The last is a QC restriction, **not motion matching**.
  Code SCHZ=1 and CONTROL=0. Report each model's subjects, estimate, classical
  SE, normal-Wald 95% interval and t-reference test as specified.
- Also report complete signed crude/FD-adjusted edgewise OLS results and
  descriptive QC-FC associations. Counts at `|t| > 2` are uncorrected summaries,
  not corrected discoveries or an expected “5% chance” benchmark. Do not treat
  dependent edges as independent participants for a biological p-value.

Equivalent implementations of this public estimator are accepted within its
numerical tolerances. Preserve legitimate zero estimates and explicitly undefined
quantities. Do not add outcome-based exclusions, force attenuation, take absolute
diagnosis coefficients, or turn nonsignificance into evidence of equivalence.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). Exact schemas are in the public
contract. Supply the candidate cohort ledger, original parcel/edge catalogues,
per-subject connectivity and FD diagnostics, full subject-by-edge numeric arrays,
complete edgewise results, `group_stats.json`, `run_metadata.json`, and
`findings.md`. They must describe the same source identities and recompute from
the same signed measurements. Keep sufficient precision; row order and prose
wording are not grading targets.

Interpret differences between adjustment and restriction as observational
sensitivity. Age, sex, medication and selection remain unadjusted limitations.
These analyses cannot establish that motion causes the entire diagnosis
association, that diagnosis-related signal is absent, or that a biomarker
generalizes beyond this cohort. A change in significance is not itself a test
that two effect estimates differ.

If source/schema or numerical prerequisites fail, exit nonzero and write
parseable `group_stats.json`, `run_metadata.json`, and `findings.md` with
`status: failed_precondition` and a nonempty reason. Preserve existing evidence
destinations; never fabricate a completed analysis.
