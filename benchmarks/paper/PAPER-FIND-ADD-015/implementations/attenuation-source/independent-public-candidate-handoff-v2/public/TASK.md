# Central processed-trace reconstruction

Existing assignment: **PAPER-FIND-ADD-015**, *Cellular-resolution optogenetics reveals attenuation-by-suppression in visual cortical neurons*, DOI10.1073/pnas.2318837121. Implement the declared Figure2/3 numerical reconstruction from the complete released processed trace panel:364 Figure2 cells,52 multi-power cells and6 multi-visual cells. Preserve all observations, both directed cross-half diagnostics and every fixed clipping/baseline variant below. Null or discrepant results are legitimate.

This is an independently implemented, protocol-guided central-panel task. It does not reproduce raw optical preprocessing, selection, full Figure4/Ricciardi/bootstrap/model comparison, Figure5 variability, physiological mechanism, animal-population inference or the whole paper. The paper contains published results; this is exposed development material, not a blind discovery test.

## Authoring and eventual program interface

Author one UTF-8 Python file, at most131,072 bytes, accepting `--input /input --out /output`. The planned invocation is `python -I /program/program.py --input /input --out /output`. Use Python3.12.8, NumPy2.2.6 and SciPy1.15.3. Standard-library/NumPy/SciPy implementations are allowed; do not import existing benchmark reconstruction code. No empirical execution is authorized by this handoff. Root separately supplies the runtime, resources and permission for any execution.

The exact18-file common input set is13 primitive NPZ trace files, `input_schema.json`, unmodified `article.xml`, this TASK, `OUTPUT_SCHEMA.json` and `CLARIFICATION.md`. Load NPZ with `allow_pickle=False`; reconstruct the declared source lists using the schema's tree and primitive leaf names. A `dtype_metadata` entry is metadata, not an instruction to unpickle. The paper XML includes Methods text and author publication results, but no separately acquired SI PDF. The task instructions specify the finite numerical convention where the source analysis and broader paper differ.

Write exactly one uncompressed ZIP_STORED `/output/central_submission.zip`, at most2,700,000 bytes. It contains exactly `windows.npz` (at most1,400,000 bytes), `paired_vectors.npz` (at most800,000 bytes) and `report.json` (at most300,000 bytes). Both NPZs are uncompressed ZIP_STORED ordinary C-order arrays, with exact names/shapes in OUTPUT_SCHEMA. Numeric arrays are finite float64; five identity arrays retain the specified values/order/dtypes. No pickle, object/complex arrays, duplicate/extra archive members or nonfinite JSON values. No private answer, previous prediction, scorer, reference kernel or control program is public input.

## Source geometry and reductions

Figure2 experiment order is:

`210819-i3487,210825-i3686,211110-i3487,211116-i3776,211117-i3996,211201-i3776,211205-i3996,220413-i4018,220301-i4018,220503-i4158,220504-i4157`.

Use zero-based within-experiment cell indices. Multi-power retains three experiment arrays in source order with18/17/17 cells. Multi-visual retains six cells and visual columns0=activated,1=suppressed; its opto input has one shared column, not two independent opto samples. Do not sort observations by effects.

Let onset=`optoFrStart`, width=`nOptoFr`. For each condition compute B over frames`[onset-width,onset)` and S over`[onset,onset+width)`. Timing is source-record-specific. Figure2/multi-visual timing entries must agree within their record; multi-power timing is per experiment. Reject missing/inadequate windows, nonfinite source observations, inconsistent IDs/timing or geometry.

Save per-trial pre/post means in `windows.npz`. For all-trial response replay, average trials first, then the frame window, matching the literal source reduction order. Cross-half quantities average the per-trial window means over the indicated parity. Never pair ordinal trials across different interleaved conditions; the biological pairing is the same cell across condition means. Trial parity is not established chronological half-session membership or temporal independence.

## Response variants and signs

For visual V, opto O and paired P conditions, define

`R=(P_S-P_B)-(V_S-V_B)`, `C=max(R,0)` for clipped variants (otherwise`C=R`), and `D=C-O`.

For Figure2 and multi-power, `O=O_S-O_B` in both variants. Return source/clipped and unclipped variants. For multi-visual return all four fixed variants: source=`clipped, O_S`; unclipped=`unclipped, O_S`; baseline_only=`clipped, O_S-O_B`; paper_method=`unclipped, O_S-O_B`. The names describe measurement conventions, not a claim that a repaired branch is scientifically superior. Every variant shares cells, windows and the source all-trial group masks. Do not select a favorable branch.

Each response block returns `visual_state=P_B`, `opto=O`, `paired_raw=R`, `paired=C`, `delta=D`, and the six condition pre/post means. Multi-visual opto/pre/post retain shape6×1; its remaining response arrays have shape6×2. The shared opto column broadcasts when computing D.

Figure2 state is`x=P_B`: suppressed`x<-5`, moderate`5<x<60`, high`x>60`. Every other/boundary value stays as unclassified. For each group return cell mean/median/SEM of D and unclipped D; clipped-cell count; and reduction`1-mean(C)/mean(O)`. This is a ratio of group means, not the mean of individual ratios. Empty group or zero mean O gives null ratio plus its reason. Reproduce the source paired rank test with first=O,second=C, so its statistical difference O−C has the opposite sign to biological D=C−O. Unclassified cells are descriptive only, not a fourth test.

Multi-power state is`x=(P_B,low+P_B,high)/2`; suppressed`x<0`, activated`x>0`, zero unclassified. For both clipped/unclipped variants return`alone=O_high-O_low`, `during=C_high-C_low`, and interaction`J=during-alone`. Pair low6.5/high8mW within the same cell/experiment. Test during versus alone separately in the two groups; the third source-family test is between-group Mann–Whitney of alone, with first=suppressed and second=activated, `alternative='two-sided'`, `method='auto'`, and `use_continuity=True`. This does not compare the significance of the two within-group tests. The shared visual-only trajectory cancels from the **unclipped** during power difference; clipping may prevent that cancellation.

For every multi-visual variant return within-cell`K=D[:,0]-D[:,1]` and its paired test (first activated,second suppressed). Subtracting the same opto baseline from both columns must leave K unchanged when comparing source versus baseline_only, and unclipped versus paper_method. It may change the individual condition amplitudes. Do not assume different clipping branches have equal K.

## Both cross-half orientations

For each Figure2 record retain every trial, including odd trial counts. Direction0 uses trial ordinals0,2,4,… only to estimate predictor x; outcome D uses1,3,5,… only. Direction1 reverses those roles. Return all364 predictor states and outcome effects separately for both directions, clipped and unclipped. Do not truncate49/50/54/58-trial records to equal counts.

Derive each cross-half group from that direction's predictor x alone. Never use all-trial state or outcome-half measurements to select these groups. Return continuous all-cell Pearson correlation for each clipping branch, group counts/effect summaries, and descriptive membership changes relative to the source all-trial masks. Preserve unclassified cells. Do not pool orientations as extra cells, assign a population p-value/CI or claim the original upstream selection became independent.

## Statistical report

OUTPUT_SCHEMA defines the exact report structure. Cell summaries contain n,mean,median and ordinary sample SEM (`ddof=1` divided by square-root n); empty summaries are null, and n=1 SEM is null. SEM is not a median confidence interval or an animal-population interval. Paired summaries include both response summaries and first-minus-second, statistic, p, multiplicity, nonzero/zero counts and tie diagnostics. `tied_absolute_nonzero_groups` lists the multiplicities greater than one, ordered by increasing distinct absolute nonzero difference.

Primary paired tests use SciPy1.15.3 Wilcoxon: two-sided,`zero_method='wilcox'`, `method='auto'`, no continuity correction. Figure2's three classified tests and multi-power's two within-group plus one between-group tests each use Bonferroni factor3; multi-visual uses factor1. Correct p as`min(1,factor*p)`. Empty paired sets yield null statistics/p; all-zero differences yield statistic0/p1 by explicit task policy, not claimed historical software parity. Correlation is null with a reason for fewer than two cells or a constant vector.

For exactly two diagnostics—Figure2 high-group O versus C, and suppressed multi-power during versus alone—report all four method rows in order: auto/no correction; untied nonzero exact/no correction; asymptotic/no correction; asymptotic/continuity correction. Mark exact inapplicable if zeros or tied absolute nonzero differences occur. Retain method, warnings, ties, sign and multiplicity. Do not scan alternative hypotheses, thresholds, rounding, exclusions or package versions to match publication. Publication agreement does not establish the author's historical method or identify a mechanism. No reward is tied to significance or a favorable direction.

## Inclusion, independence and access limits

Retain all364/52/6 released cells. Any Figure2 cells whose reconstructed opto response is at or below the stated 5% source threshold must remain; report their count without inventing a new exclusion. Coordinates/target/pattern membership, excluded observations and upstream optical processing are absent. Seven Figure2 filename suffixes are only provisional descriptive groups. The reported7/3/2 animal counts do not supply verified row-to-animal mapping. Panel overlap and physical cell alignment remain unresolved; source correspondence is positional. Do not add panel counts into a claimed independent cohort.

This central task needs neither LOESS nor an official analysis implementation. For the initial independent author, use the common protocol/data/paper condition only. An optional code-access condition would add three curated official notebook-source text files with outputs removed; it is separately declared, not automatically authorized and not a measured code-benefit study. Both conditions would otherwise receive identical data, article, protocol and resources. Do not consult house source, prior reports, private metrics or candidate solutions.

The data deposit records CC BY4.0. The unchanged article XML declares CC BY-NC-ND4.0; preserve its notices and attribution. A separate official-code license has not been established. The legacy compatibility dependency LOESS2.1.2 prohibits redistribution and is deliberately absent here. This handoff does not authorize external/commercial redistribution or establish a rights-cleared release.

The prospective `CLARIFICATION.md` is normative for membership-change counting, float64 cancellation tolerance, paired-test degeneracy precedence, empty Mann–Whitney groups and SciPy API aliases. It supersedes only those ambiguities in the original v1 text.
