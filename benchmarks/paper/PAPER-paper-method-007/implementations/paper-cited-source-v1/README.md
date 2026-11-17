# Paper-cited UnitMatch functional analysis source

This recovery supplies the native analysis functions needed to investigate the original Figure 4 endpoint. The six files under `native/` are unchanged author bytes, including their license. They were absent from the preserved five-mouse runtime's public source package. `SOURCE.json` binds each file to its Git blob, SHA256, and path at commit `6ef0023cb4a7be0a94dabbab24bb79c084b6fb1e`.

The [paper](https://www.nature.com/articles/s41592-024-02440-1), reference 50, cites **v2.0**, [Zenodo 12734237](https://zenodo.org/records/12734237). The recovered Zenodo metadata links the GitHub `v2.0` tag, whose resolved commit is the same revision already selected by the legacy native reference. Thus the version label alone does not establish a paper-era mismatch. Actual algorithm, input, and evaluation parity still require verification. The earlier suggestion to use v1.0.0 is not supported by this publication citation.

## Recovered native route

`ComputeFunctionalScores(SaveDir, saveFig, recompute)` constructs independent functional fingerprints and appends them to the source `UnitMatch.mat`. Its ISI branch uses original spike-template/session identities, split-half spike sequences, MATLAB `[0 5*10.^(-4:0.1:0)]` histogram edges in seconds, and the complete directed correlation table. Functional data remain evaluation observations, excluded from matching and candidate selection on final recordings.

`summaryFunctionalPlots(UMFiles, 'Corr', groupVector, 0, 0)` reads the source match tables and returns `FPSum`, recording dates, day separations, match counts, available-unit counts, and slope fits. `UMFiles` and the mouse grouping must come from the original recording/location roster; the function's default of one group per file is not an animal mapping. The numerical AUC helper calls MATLAB `perfcurve`. `AssignUniqueIDAlgorithm` and `DefaultParametersUnitMatch` supply the actual UID reassignment and defaults used in this path.

These are recovered source functions, **not a self-contained runnable release**. The complete pinned author checkout, transitive helpers, MATLAB/toolboxes, exact recording metadata and full original inputs remain external. No native call, data preparation, author reproduction, or candidate trial was run for this recovery. Nothing here modifies the historical runtime or silently selects a new scorer.

## Consequential differences from the five-mouse proxy

| Source location | Observed native behavior | Why it matters |
| --- | --- | --- |
| `summaryFunctionalPlots.m:66–67, 116–135` | At least 20 matches; both recordings must last at least 600 seconds. | Duration metadata and all original eligible session pairs are required. |
| `summaryFunctionalPlots.m:147–164` | Reassigns UIDs separately for each session pair with data-driven threshold disabled, then uses `UID1 == UID2`. | The proxy's greedy bidirectional-mean decoder is a different algorithm. |
| `AssignUniqueIDAlgorithm.m:58–80, 108–118, 141–143` | Screens directed probabilities, orders pairs by their mean, and assigns intermediate UIDs using the adjacent-session compatibility condition. | A high bidirectional mean alone is insufficient. The summary uses intermediate UID columns despite a nearby comment mentioning liberal UIDs. |
| `summaryFunctionalPlots.m:160–164, 209–221` | Finds UIDs shared by distinct clusters within a recording and excludes rows whose **first** UID is in that set. | Preserve this directed rule when examining native parity; excluding either endpoint would change the recovered code. |
| `summaryFunctionalPlots.m:235–252` | Eligibility counts cross-match rows divided by two and requires that they are not all NaN, before `perfcurve`. | The legacy requirement for 40 finite match directions is an additional benchmark convention. |
| `summaryFunctionalPlots.m:329–331` | Concatenates retained pair AUCs across files in each mouse group and takes `nanmean`. | It does not first give every recording location equal weight. Unequal numbers of eligible pairs can change a mouse's result. |
| `summaryFunctionalPlots.m:377–378, 460–471` | Plot labels summarize all finite grouped AUCs; the later printed summary restricts mice to those with a finite stability slope. | These are distinct support rules. The exact route underlying the reported 16-mouse number must be established. |

The manuscript describes averaging across recording locations. The source's pair concatenation, slope-conditioned printed summary, and original `groupVector` must therefore be reconciled against the figure-generation invocation. This recovery does not choose a convenient weighting or subset. It also does not identify the exact original 16-mouse session/location roster.

## Separate benchmark outcomes

Reproducing the original finding and exceeding it on the same task are separate first-class outcomes. Both need full original-cohort fidelity and the exact original evaluation path. A reproduction result would report agreement with the published cross-day ISI AUC and its companion controls; an improvement result additionally needs a frozen candidate, same support and match-yield safeguards, paired animal-level uncertainty, and a justified effect criterion. AUC measures functional consistency, not ground-truth neuron identity.

The five-mouse/two-day release remains useful separately scoped evidence. It cannot substitute for the original 16-mouse endpoint in either outcome. Source recovery does not add a qualified benchmark or an empirical result. The paper+data and paper+data+author-code conditions still require separately frozen, paired participant delivery; these recovered files are author-code material, not authorization to expose functional targets.

## Remaining work

Recover the original full recordings and eligible roster, exact invocation and grouping, original metadata duration/date joins, complete transitive environment, and author results. Resolve the weighting and slope-support questions before selecting a definitive reproduction scorer. Then freeze source/data exposure and run the complete author comparison under an approved native protocol. Historical private targets and solver answers were not read in this recovery.

The unchanged author functions retain **CC BY-NC-SA 4.0** under `native/LICENSE`; the repository's license does not relicense them. This directory contains no data, predictions, weights, or private paths.
