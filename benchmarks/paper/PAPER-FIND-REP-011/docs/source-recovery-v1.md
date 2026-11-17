# Original MATLAB source recovery

The original analysis scripts have now been recovered from the versioned
[author archive](https://zenodo.org/records/10108836). This resolves the prior
absence of executable source for the activity/coactivity models. It does not
recover a scientific reproduction or improvement result. These remain separate
outcomes, with paper+data and paper+data+author-code access conditions still to
be admitted. No canonical task, original contract or historical result was
changed by this component.

The [paper](https://doi.org/10.1126/sciadv.adk0540) states that model terms were
chosen using log-likelihood comparisons, but it does not report the complete
selection sequence or numeric likelihoods. The recovered final fitting calls
are materially more specific than that prose. A final formula is not proof
that the complete original candidate set has been recovered.

## Acquisition and provenance

The source is `Elim_Paper_Repository.zip` in Zenodo record **10108836**, reported
as 19,743,225,896 bytes with archive MD5
`729d836b9f30a461b27e246efbde8872`. The ZIP directory and selected source members
were fetched using exact HTTP 206 ranges. Each response's `Content-Range` was
checked against the requested extent and total archive size; each decompressed
member passed the archive CRC check and received a SHA-256 pin. The complete
archive was not downloaded, so its whole-file MD5 was not independently checked.
Recording arrays and historical private targets were not accessed. Recovery
used **204,489 response-body bytes**, with no failed HTTP responses, and pinned
**28 files**: 15 MATLAB scripts, two MATLAB backups, ten Python sources and the
archive README. The 503-entry directory was inspected; the dual-plane notebook
and recording files were not acquired.

Source hashes, exact fitting calls and bounded inspection results are in
`source-recovery-v1.json` beside this report. Raw response bodies, author source,
range receipts and archive inventory remain in external operator evidence.
The local source copy is not redistributed here. The prior full-text XML pin
is `d74bdc818160ec9f3f32eef11e9c638c396e85725a17e13ee4388c104e71128c`.

Static inspection of all 17 MATLAB scripts/backups recovered 36 uncommented
`fitlme` calls (33 in `.m` files and three in a backup). None explicitly sets
`FitMethod`; no uncommented `LogLikelihood`, log-likelihood or `compare(...)`
reference was found. This is a scoped source-code finding. It does not prove
that no model-selection history or saved numerical output exists elsewhere.

## Recovered activity definition

`ElimSpineFrequency.m` names the original 27 source animals and loads each
animal's `*_Aligned`, `*_SpineDynamicsSummary` and `*_StatClassified` variables.
Its analysis requires more than two sessions per field; the early and middle
responses use observations preceding the two elimination transitions. Stable
comparison rows enter only when an elimination occurs on the same dendrite in
that transition. This is the source's retrospective population, not the local
extension's mouse-held-out prediction population.

The source counts only positive differences between adjacent binary samples
and divides by `N / (sampling_hz * 60)` to obtain events/minute. Thus a trace
that starts active does **not** receive an initial event, unlike the explicitly
prospective convention in `initial-evaluator-v1`. The source specifies 58.3 Hz
for `GluSNFR` and 30.03 Hz for `GCaMP`. Neither convention is silently changed.
Actual sensor, sampling-rate and complete population parity remain to be
checked against an admitted native preparation.

At line 250, the model fits `Frequency` in `ESfreqTbl` with fixed `ESlabels`
and animal-grouped intercept and separate stability-slope random effects.
At line 270, it adds session and stability/session interaction terms with the
corresponding random effects. The table uses numeric stability and session
columns; converting them to differently coded categorical predictors without
checking parameterization would not be an exact replay. The deposited calls
do not specify `FitMethod`. A historically matched MATLAB release and its
actual fitting/likelihood conventions remain to be pinned; no setting is
invented from an assumed default.

## Consequential source discrepancies

| Source location | Observed issue | Consequence |
| --- | --- | --- |
| `ClusteringbySpineSize.m`, lines 235–264 | Animal tags use bin/session order; response columns use stability/size blocks. | A positional table join can attach the wrong animal group to a response. The accompanying audit supplies an independent generated counterexample. Authentic affected-row counts are unknown. |
| Same script, lines 360–384 | The session response order changes, but line 382 reuses the earlier `AnimalTags_for_stats`. | Session models require their own row-identity reconciliation; merely matching lengths is insufficient. |
| Same script, line 264 versus paper Statistical analysis | The area model uses a distance random slope without its intercept (`Distances-1`), while the printed formula includes a distance intercept and slope. | Random-effect covariance structure differs; do not silently choose one as a verified reproduction. |
| Same script, line 384 versus paper Statistical analysis | The session model additionally includes the distance/stability interaction random effect, absent from the printed session formula. | Source and manuscript represent different covariance structures. |
| Same script, lines 235–253 | The inclusive `0:5:50` loop includes distances below 55 micrometres; fitted distance values are floored to 5-micrometre bins. | Neither a hard 50-micrometre cutoff nor unbinned distances reproduces this code. |
| Same script, lines 209–211 | Executed area cutoff is 1.0960, described as the stable-spine 40th percentile; the median alternative is commented out. | The size strata must be bound to the executed definition, rather than inferred from a nearby comment. |

The [row-order audit](../implementations/source-row-audit-v1/README.md) traces
the two original permutations without changing author results. Before fitting,
an operator must preserve both the deposited computation and any justified
correction as distinct, source-pinned analyses. A corrected source bug cannot
be relabelled as reproduction of an original numeric result without showing
what changed.

## Remaining work

Source presence now supports an exact model/row review. It does not yet bind
authentic rows, eligible pair counts, sensor cohorts, missing values or all
paper panels. A full source-matched preparation and author replay need a
separate frozen native protocol and budget. Published effect summaries,
reproduced effects and likelihood results must stay distinct.

For improvement, the original model-selection alternatives, selection rule,
numeric likelihood baseline, fitting convention, complexity policy and valid
uncertainty comparison remain unresolved. For reproduction, original panel
bindings, reference numerical outputs and tolerances remain unresolved. No
new holdout, elimination classifier, stronger p-value or unconstrained
parameter addition fills either gap.
