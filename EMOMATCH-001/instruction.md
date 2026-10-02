# Emotion-matching duration-model sensitivity

How much do signed emotion-minus-control coefficients change when the same
trials are modeled with a common duration versus their individual response
times? Measure this on the twenty fixed AOMIC PIOP2 participants supplied here.

This is a paper-derived **method sensitivity case**, not a reproduction of a
paper's group finding. In AOMIC's task, displays ended when participants
responded (or timed out), so response time also relates to stimulus exposure.
Changing the modeled duration changes the regressor's shape and scale; it does
not by itself identify a causal RT confound or establish emotion specificity.

## Data and two models

Use the supplied, version-pinned fMRIPrep BOLD, events and confounds for
`sub-0002`–`sub-0009` and `sub-0011`–`sub-0022`. Keep the same people, frames,
spatial measurements and nuisance regressors in both models. Do not replace
participants, select trials by accuracy, or choose regions based on their effects.

- **Model A:** every included emotion/control trial has that participant's
  median valid RT, pooled across both conditions.
- **Model B:** each included trial has its own valid RT. Replace a declared
  missing RT with the same participant median. This imputation is not the
  observed display duration of an omitted response.

For both models, estimate the signed emotion-minus-control OLS contrast for all
100 released Schaefer parcels and eleven fixed coordinate spheres. Report each
model's complete signed contrast vector, not just their difference. Use the public HRF, drift,
normalization, nuisance, spatial-support and numerical-rank definitions in the
method contract. Equivalent implementations are welcome; no particular solver
code or software-version string is required.

Within each person, form the specified bilateral amygdala, bilateral fusiform,
seven-sphere control and seven network summaries. Then use equal-person group
summaries and paired B-minus-A changes. Report complete support and undefined
cases honestly. A zero, opposite-direction or non-significant result is valid;
there is no required regional ordering or RT difference.

## Deliverables

Inputs are under `/app/data/emomatch`. Read `/app/source_manifest.json`,
`/app/method_contract.json`, `/app/output_schema.json` and `/app/SOURCE_NOTICE.md`
for the complete public source, analysis and evidence contract. Source file
hashes identify unchanged inputs; they are not fitted numerical answer targets.

Write the eight files to `/app/output` as defined by the public output schema: `cohort.csv`,
`events.csv`, `roi_support.csv`, `glm_arrays.npz`, `activation.csv`,
`group_stats.json`, `run_metadata.json` and `findings.md`. They retain original
row identities, both complete designs and signed fits, exact spatial support,
source-duration/RT discrepancies, and the arithmetic behind the group results.
The schema specifies keys, and the method contract specifies tolerances; coherent row and axis reordering is
accepted. Your findings can be brief and should distinguish this fixed-subset
computational comparison from population or causal conclusions.

All input data are available offline. If a declared source precondition fails,
write `failure_report.json` explaining it; do not manufacture successful outputs
or silently analyze a smaller cohort. A failure report is diagnostic evidence,
not a passing submission. Scoring is binary: all required source, numerical and
completeness checks must pass. There is no proportional partial-credit promise.

## Scientific sources

- Snoek et al., *The Amsterdam Open MRI Collection, a set of multimodal MRI
  datasets for individual difference analyses*, Scientific Data (2021),
  [emotion-matching task description](https://www.nature.com/articles/s41597-021-00870-6).
- [AOMIC PIOP2 release 2.0.0](https://doi.org/10.18112/openneuro.ds002790.v2.0.0).
- Grinband et al., *Detection of time-varying signals in event-related fMRI
  designs* (2008), [duration-model motivation](https://pmc.ncbi.nlm.nih.gov/articles/PMC2654219/).
