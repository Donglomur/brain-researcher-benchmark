# Exact native semantics in the complete S2 design

These rules repair OFC-D01, D02 and D05 throughout the complete design. They are required native-reproduction contracts, not executed findings about authentic data. Original source remains unchanged. Every source below resolves through the independently reauthenticated 59-file index and `SOURCE_FREEZE.json`. A separately labeled Methods-conformance or prospective sensitivity analysis must never overwrite a native product, its inclusion table or its reference.

## Signed permutation statistic and physical group roles

`utils/permute_test.m:6–10` takes the absolute observed difference only when `varargin` is empty. Any extra argument, including the active value 1, instead computes `mean(a,'omitnan')-mean(b,'omitnan')`, signed. This explicitly corrects the original design's D11 transcription; it makes no claim about an authentic paper p-value being wrong.

For each required alignment, pre/post status, time bin and subgroup, the active caller supplies nonpref as `a`, pref as `b`, 1,000 draws, and the extra argument 1. Do not swap groups to obey the helper comment that `a` should be smaller; do not take absolute values or perform a two-sided conversion. Array names denote transition roles, not simply high versus low firing. `analysis/Electrophysiology/incongruentResponse_twentyPreVsPost.m:21–49,97–120` selects significant high-versus-low cells, assigns high-preferring cells `prefvec=2`, and gives this exact map:

| Cell firing preference | nonpref transition (`a`) | pref transition (`b`) |
|---|---|---|
| High (`prefvec=2`) | high→mixed | low→mixed |
| Low (`prefvec=3`) | low→mixed | high→mixed |

Each transition has distinct last-pre and first-post 20-µL trial selections. The source does not compare pre to post in one call: it compares the two transition groups separately at pre and at post. Preserve the original block-selection and concatenated-trial-index quirks in D05/D20, NaN placeholders for unselected cells, source `omitnan` behavior and the exact row map into any TCA/ATI/brain-area subset. No English label can substitute for physical trial keys.

`permute_test.m:11–27` concatenates `[a;b]`; each null draw chooses `length(a)` indices with replacement using `ceil(rand(length(a),1)*length(mix))`. It computes the first mean from those potentially repeated values and the second mean from the sorted complement of their unique indices, `setdiff(1:length(mix),samp_indx)`. The null is signed first-minus-second. The p-value is exactly `count(null > observed)/1000`: strict greater-than, no plus-one correction, and no removal or renormalization of nonfinite draws. Native arrays/NaNs and RNG/version/seed provenance must be retained. If native arithmetic produces a numerically misleading zero from comparisons with an undefined observed mean, the faithful native value and a separate undefined-scientific-status flag must both be returned; zero is not promoted to inferential evidence. Native RNG edge behavior or source errors are recorded, never silently repaired.

The p<.05 booleans are padded with false at each end; start/end transitions delimit contiguous true runs. Keep all bins belonging to runs with length >2 (at least three), not merely their third bin. Preserve each caller's exact `xvec` bin membership/order and time mapping. No new cross-event or across-group continuity is allowed. Both raw per-bin p-values and raw/masked significance vectors are required.

| Active caller | Signed call / threshold | Pre / post consecutive-bin logic |
|---|---|---|
| `vis/plotFigure3_expertEphys.m` | 76–91 | 129–143 / 169–180 |
| `vis/plotFigure4_TCA.m` | 109–117 | 120–129 / 156–165 |
| `vis/plotFigure7_naiveEphys.m`, low ATI | 161–175 | 185–195 / 216–227 |
| same, high ATI | 274–287 | 298–308 / 329–340 |
| `vis/plotFigureS6_otherAreas.m` | 165–180 | 189–200 / 222–233 |
| `vis/plotFigureS7_TCAsupp.m` | 113–121 | 124–133 / 160–169 |

Required cell-statistic records bind physical group roles, cell/session/rat IDs, selected trial IDs, original versus subgroup row indexes, event/bin, signed observation, all 1,000 null values or exact reproducible draws, p-value, NaN counts, raw and consecutive masks, source seed/algorithm and downstream panel IDs. F3/F4/F7/S6/S7 native comparisons use this contract. A corrected exchangeable, paired, animal/session-aware or two-sided procedure requires its own prespecified estimator, units, null and scientific justification in a later selected analysis. It cannot supply the native p-value or qualify an original causal claim by relabeling.

## Native TCA whole-slice zero-fill

`analysis/Electrophysiology/makeTensor_TCA.m:29–46,62–89` selects sessions by its actual source predicate (not an assumed equivalence to every Methods eligibility claim), uses block order `[3,1,2]` = low,mixed,high, and constructs five event segments. For each session/event it z-scores each neuron's entire event matrix, initializes `initial=zeros(neurons,time,3)`, then constructs the full neurons×time `avg_resp` for each block using `omitnan` trial means. MATLAB's `if ~isnan(avg_resp)` succeeds only when the condition is nonempty and every element is true. Any NaN anywhere prevents assignment of **the entire event/block slice**; all its neurons and time bins retain their initialized zeros, including entries whose individual averages were finite. This is not entrywise missing-value replacement. The predicate is not `isfinite`: Inf without NaN is not stopped by that predicate and must retain its native downstream error/nonfinite disposition.

The native tensor submitted to the native TCA fit retains that exact zero-filled slice, event order, block order and original row order. A measured zero is distinguished from an initialized default zero by a separate provenance table. For each session/event/block record the input and included-trial key sets, exact neuron/time shape, selected window and original indexes, full pre-assignment average matrix (tagged nonfinite values), NaN locations/count, whole-condition result, assignment status, output tensor slice identity and default-zero mask. `assigned_finite_zero` and `default_zero_due_to_nan_elsewhere` are different reasons even though both have numeric value 0. Keep empty/failed branches and all source units in the ledger. A failure to construct or qualify the native tensor leaves TCA and dependent cluster obligations required-unscorable; it does not license dropping a session or reporting a successful smaller fit.

The source's first three event windows are [-1,1]; reward and opt-out use [-1,.8], all indexed using `SU(1).xvec.COFF`. Global z-scoring, negative inputs supplied to nonnegative factors, missing `sortNeuronFact`, external versions and save/cluster bindings remain G05/G06 issues. Full native scope still includes expert and naive tensors, 1–20 ranks×10 starts, final rank 8, cluster 0, all memberships and all cluster/event responses.

An optional corrected masking sensitivity analysis is a distinct, later selected product. It would keep each finite `avg_resp` entry, mark unavailable entries explicitly and use a separately specified missing-data-aware objective and denominator. It may not silently feed the corrected tensor into native rank selection, claim native cluster counts, or discard an entire hard slice from the native obligation roster. No corrected TCA metric or implementation is selected here; any new predictive TCA extension follows the train-only prospective contract and its own predeclared support. The frequency of the native branch in authentic inputs is unknown.

## Native acute muscimol linear-index mutation

`analysis/Muscimol/muscimolPhysiology.m:22–48` constructs `[distance,pre_rate,post_rate]`, including the unresolved right-side post-duration expression. Lines51–58 concatenate hemispheres, exclude baseline FR<.4, sort once by distance, then execute `sortedmat(sortedmat(:,2)==0)=eps` and `sortedmat(sortedmat(:,3)==0)=eps`. Each N×1 logical mask addresses the first N positions of the N×3 array in MATLAB linear indexing: the **distance column**. It does not replace zero rates. Baseline finite zero is ordinarily already removed by line53; that does not justify deleting line57 or assuming line58 is inactive. Actual zero-post-rate occurrence is unknown.

After the two assignments there is no resort. Ratios use the original retained pre/post rate columns (line60); zero post rate remains a ratio of zero when pre rate is valid. Bin edges are `sortedmat(1,1):100:sortedmat(end,1)` after mutation (line62), not min-to-max edges recomputed from corrected distances. Membership uses inclusive lower and exclusive upper edges, original ordering, source omitnan means/SEM, the source NaN-bin omission for its fit and all 50 sigmoid starts (lines63–76). Preserve any empty range, dropped endpoint, undefined mean, unit mismatch or fitting failure as native provenance; do not repair ordering/edges in an adapter.

Required S3 per-unit provenance includes original hemisphere/unit IDs and source row, distance before filtering, baseline exclusion result, sort permutation, both logical mask bits and their exact linear locations, distance after each assignment, unchanged pre/post rates, final ratio, edge-construction first/last rows, assigned bin or unbinned reason, full bin support, original nonfinite status, fit-inclusion status and all optimizer outcomes. Retain original input units, infusion/duration roles and the distinct acute-animal role. The nine paired behavioral animals are not this physiology sample, and unit count is not animal count.

A corrected column-targeted epsilon handling or a distance-preserving zero-post-rate analysis would be a distinct, explicit Methods-conformance sensitivity product with its own units, epsilon/zero policy, sorting, bin construction and denominator. Neither is selected as a replacement native statistic. S3 remains required-unscorable until the authentic input/units, native implementation and independent full reference are qualified. This source reasoning does not establish or refute the reported 1.25-mm inactivation extent.
