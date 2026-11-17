# Full120 method specification

This shared method assistance documents the original procedure. The source-local collector and120-field comparator are already engineering-qualified; these facts do not establish fullV5 or independent solver performance. The current comparison policy is27 source-reporting bins,21 exact integers and72 continuous-only diagnostics, as specified in TASK.md.


The exact official script is `scripts/s3_RmetaAnalysis.R` at NIDER commit `90e8f324f78701bc3b1a8af3b79685ca91084d05`, 18,666 bytes, SHA256 `caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334`. The shared AUTHOR_LABELS.json provides the exact label and exclusion convention without effect values. Condition B additionally receives the pinned full official script.

The original preprocessing selects eight scientific columns, averages the two Morawetz2016b rows arithmetically on raw r (without `na.rm`), retains the first row's metadata/sample sizes and removes the second row (lines29,73–75). All other source rows retain order. Labels are changed at77–140. This averaging is an original implementation convention. It is not a claim that a merged effect has independent-study variance or that the two samples are disjoint.

Three calls, in original order:

| Contrast | Subset | n supplied | Original call |
|---|---|---|---|
| quest_self | nonmissing questSelfRating; onlineRatings | sample size quest, explicitly coerced numeric | 149,153 |
| amy_quest | nonmissing amyQuestCorr | sample size quest | 216,219 |
| amy_self | nonmissing amySelfRating; onlineRatings | sample size rating | 262,265 |

`onlineRatings` excludes exactly the three author-labelled rows at141. No candidate or collector chooses another subset. The separate Bayesian branch at298 uses sample size quest for amy_self; that does not change the original direct DL call. Bayesian model averaging, power curves, voxelwise analyses and their alternate sample-size branches are not silently folded into these three DL calls.

The clean R4.3.2/meta7.0-0 replay has sm=ZCOR, common/random=TRUE, level/level.ma=.95, classic random-effects interval and method.tau=DL. The default method.tau.ci=NULL resolves to J for these unclustered DL calls (`metagen`1705–1711); it is not a mismatch. A sparse-data branch can disable the tau interval, and native NA/sign metadata are preserved. Historical author ambient state is not independently recovered merely by pinning a clean replay.

## Mathematical meaning and limits

For ordinary admitted correlation r_i with supplied n_i, the archived implementation uses z_i = atanh(r_i) and s_i = sqrt(1/(n_i−3)) (`metacor`616–619). This is the **literal package procedure** applied after the author's duplicate averaging. No unknown merged-effect covariance is invented, and no assertion is made that these s_i are a scientifically justified covariance model for every consortium contribution.

For a nondegenerate unclustered sample, w_i=1/s_i², common estimate = sum(w_i z_i)/sum(w_i), SE = sqrt(1/sum(w_i)); Q = sum(w_i(z_i−common)²). The usual DL expression is max(0,(Q−(k−1))/(sum(w_i)−sum(w_i²)/sum(w_i))). Operationally, the pinned `hetcalc`93–103 delegates the DL tau² estimate to metafor4.6-0 `rma.uni`; this packet does not reimplement that algorithm or claim independent binary equivalence. Random weights are 1/(s_i²+tau²), with the package's explicit NA/exclusion and tau fallback branches (`metagen`1835–1876). Pooled classic inference delegates to `ci` at1861–1866 and1925–1931. Stored estimates and interval endpoints remain on Fisher-z scale.

The separate correlation output is tanh applied to each native estimate and each interval endpoint. There is no tanh transformation of SE, Q, tau or tau². `metacor`78–82 states that backtransf changes printouts/plots. The author's Table1 helper reads TE.random/lower.random/upper.random directly but calls them r (31–63); retain this discrepancy without claiming a proven published error. The existing 12-number caption criterion's coarse agreement does not resolve this scale ambiguity for every table field.

Tau is in Fisher-z units, tau² in squared Fisher-z units. Jackson tau intervals use a separate generalized-Q model with weights1/seTE (`hetcalc`141–146), **not** 1/seTE² and not a normal Wald interval. The package extracts tau and tau² bounds and bound-sign flags at297–305. H and I² plus their bounds are returned directly from `calcH`/`isquared` at287–288; I² is a fraction, not a percentage. This packet has not independently authenticated the complete transitive `ci`, `calcH`, `isquared`, or metafor confidence-limit implementations. The exact pinned runtime is the source of their native fields; an independent derivation or claimed numerical error proof must authenticate that closure. This is not a prerequisite for authentic native collection, a justified reporting-precision comparison, or a separately predeclared scientific accuracy criterion.

## Complete implemented interface

`extended_reference.R::extended_collect` receives the unchanged `author_reference_core` environment and the already admitted scientific dataframe. It invokes no estimator and reads no file. The owner must authenticate these inputs; a candidate cannot supply the environment. It verifies source subset/native model alignment, sample-size columns and actual model methods before collecting:

- Common and random: estimate, SE, test statistic, two-sided p, lower95%, upper95%, on z scale; estimate/lower/upper additionally on r scale.
- Q, df.Q, pval.Q; tau, tau², SE(tau²), both tau/tau² interval endpoints; H and I² with their native intervals.
- k, k.all, k.TE, k.study, original sum(model$data$.n), and supplied subset-row count.
- Exact ordered membership: original source ID, data-record ordinals, retained first ordinal, author label, n source column, and membership in the native k calculation.
- The native tau interval method and bound signs, plus exact replay settings.

Data-record ordinal1 means the first admitted scientific record after the worksheet header. It is not a claimed participant ID. Two Morawetz source ordinals map to one retained unit. `k.study` equals k in the unclustered package procedure; neither it nor a distinct source label establishes an independent participant cohort. `N_author_sum` is a source sample-size sum, not unique persons.

Finite scalar values are JSON numbers; NA, NaN and positive/negative infinity have explicit tags. A missing reference value cannot become a passing field by matching NA. No R-formatted strings are scientific targets. The 65,536-byte existing numeric decoder limit is retained; the future authentic collection must demonstrate that all original membership and120fields fit without omission. Failure to fit is a preserved integration failure, not permission to truncate.


The original source workbook reference contains all120 fields within65,536 bytes. Candidate output must obey the same complete limit.
