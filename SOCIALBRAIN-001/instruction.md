# ToM–pain connectivity: GSR and motion sensitivity

Richardson et al. (2018, https://doi.org/10.1038/s41467-018-03399-2) studied
social-network development during *Partly Cloudy*. This task applies a specified
connectivity sensitivity analysis to the public ds000228 derivatives. It is **not
an exact reproduction** of the paper's primary-motor/artifact-adjusted analysis.

Use the frozen files in `/app/data/socialbrain`. All 155 literal participants
`sub-pixar001`–`sub-pixar155` are required. Join `Age` and `Child_Adult` from
`participants.tsv` by `participant_id`: 122 children and 33 adults. Do not select
participants, frames, ROIs or edges based on motion or the measured result.
The image is self-contained; no network access is needed.
Each participant has 168 released frames. The original headers omit spatial and
time units; use the release's documented millimeter convention, retain raw
header receipts, and detrend by frame order. All selected confound entries are
finite, so no imputation is needed. See `SOURCE_NOTICE.md` for these limits.

Extract the twelve overlapping 9-mm spheres listed in
`/app/method_contract.json`. Compute two arms, without and with global-signal
regression. Both use linear detrending and the specified fifteen original
confound columns. The GSR arm appends the mean of individually detrended voxels
in the specified anatomical-template mask; the released `global_signal` column
is not that measurement. Do not add temporal filtering or censoring.

The public method document fixes sphere inclusion, template normalization and
resampling, confound missingness, detrending, QR projection, standardization and
numerical support. These conventions make the analysis reproducible; there is
no hidden estimator. In particular, do not turn an unresolved residual into a
unit-variance signal. Source-inactive ROI series use zero sentinels and yield
explicitly undefined affected metrics. Other scientifically undefined results
retain their participant slots and use the declared null/status convention.

For each participant, summarize signed correlations as
`tanh(mean(atanh(clip(r, -0.999999, 0.999999))))` over the complete fixed edge
families: within-ToM and within-pain without GSR, and across-network with and
without GSR. Use all 15, 15, 36 and 36 edges respectively; never average only the
available edges or replace signed values by absolute values.

For children, report the age Spearman correlation and its conventional
two-sided t-approximation p-value. Also report the age–connectivity rank
correlation after adjustment for the rank of observed-entry mean FD and an
intercept. Use the actual nuisance rank for degrees of freedom, as specified in
the method. Report equal-participant arithmetic network means for adults.
Compute ranks and group quantities from unrounded cleaned-series measurements,
not from displayed CSV numbers. The public `/app/reporting_kernel.py` implements
these downstream rules; using it is optional.

Write exactly the five required named artifacts to `/app/output` (or the
`OUTPUT_DIR` selected for your own invocation):

- `signal_evidence.npz`: keyed raw ROI, global-signal and cleaned ROI time series,
  complete original frame keys and canonical activity masks.
- `network_connectivity.csv`: all 155 signed participant measurements and their
  source age/group/motion receipts, with explicit metric statuses.
- `age_effects.json`: complete child ordinary/adjusted results and adult summaries.
- `run_metadata.json`: source identities, cohort, geometry, missingness, cleaning
  support and software receipts.
- `findings.md`: measured results and their limitations.

Exact field definitions, accepted axis/row permutations, null rules, size caps
and numeric tolerances are in `/app/output_schema.json`. `/app/SOURCE_NOTICE.md`
records provenance and attribution. The verifier authenticates the original
files, reconstructs the signal primitives and replays the accepted cleaned
series. It does not require a particular sign, p-value, GSR ordering, attenuation
or conclusion. A passed verifier is not evidence that the paper was replicated
or that this task is difficult for a particular model.

If source integrity, geometry or a declared precondition fails, exit nonzero and
write `failure_report.json` with the reason in your owned output directory.
Preserve that failure; do not download replacements, omit participants or invent
zero endpoints. Keep outputs separate from the source files and public contracts.
