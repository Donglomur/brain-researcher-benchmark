# NEURAL-026 — fine-joint information beyond a reach-phase proxy

Reconstruct a **prospectively specified, within-mouse controlled analysis** of
joint-angle information in M1 and S1. This is a distinct endpoint from
NEURAL-025's calibrated 48-channel angle/velocity decoding. It is not an exact
reproduction of the author's Figure 5 or a causal test of cortical necessity.
The same five mice and ten imaging sessions overlap NEURAL-025; they are not
new biological data. The separate optogenetic cohort is excluded.

The scientific result is signed incremental explained variance from neural
predictors beyond a fixed nuisance model. Zero, negative, null, or inconclusive
results are valid. The submission grade is a continuous reconstruction error
against a separately authenticated trusted execution of this fixed procedure;
it does not reward a larger positive neural effect or a weaker nuisance model.
No trusted execution or real-data score exists for this new task yet.

## Cases and access

There are 50 computational cases: five mice × two areas × five folds. These
are one benchmark, with **five paired biological units**, not 50 independent
animals. Each fold is run separately. Candidate-visible files for one case are
`case.json`, `input.npz`, this task, the contract/schema, and method source.
The operator must never expose the aligned session collection, query angles,
other folds, private reference predictions, or the private package tree.
Overlapping folds make collection-wide visibility a direct target leak.

`input.npz` has exactly `train_x`, `train_z`, `train_y`, `train_id`,
`train_target`, `query_x`, `query_z`, `query_id`, `query_target`.
`x` is trial × 51 time bins × 128 selected ROIs; `z` is trial × 51 × 141;
`train_y` is trial × 51 × 24 original joint angles. IDs are whole original
trials. The query arrays contain no individual marker coordinates, joint
angles, aperture, or label-validity mask. All arms receive identical `z`.
The 10 ms resampling grid is not independent 100 Hz imaging, and the source
events are deconvolved fluorescence events, not measured spike counts.

## Fixed scientific procedure

Use all five paired mice: cfa17, cfa19, cfa20, cfa22, cfa24. Within each
mouse and each target (LR 1 or 2), retain the first chronological
`min(N_M1, N_S1)` eligible trials from each area. Require at least ten per
target/area; otherwise the declared task is unavailable, not shortened.
Assign target-stratified trial ordinal modulo five to folds. Select exactly
128 ROI ordinals per session by the specified SHA256 ordering, without
examining their activity or target correlation. Fewer than 128 is unsupported.
Sessions are different days; this is matched support, not paired reaches.

Use the source quality/window rules, `events` smoothed at 35 ms, precomputed
24 joint angles smoothed at 15 ms, and the complete −100 through +400 ms
window relative to `liftTimeDLC`. The inherited Python alignment is a source
port; numerical parity with MATLAB has not been measured. Original native
joint-angle units are retained without guessing radians versus degrees.

The nuisance basis is fixed: 102 target-by-time indicators; 12
target-interacted phase terms (phase, phase², phase³, pre-lift indicator,
post-grab indicator, and duration in seconds); six centroid position/velocity
coordinates; and their 21 upper-triangle quadratic terms. Phase is
`clip(time_ms/(grabTimeC-liftTimeDLC),0,1)`. The centroid is the mean of original
markers 9–12. It controls coarse translation, not all possible joint/limb
confounds. The two event times and complete trajectory are retrospectively
available: this is **noncausal analysis**, not online movement prediction.
No independently annotated discrete movement-phase labels are asserted.

`protocol.py` fixes the method. Every ridge uses centered training data,
training-column population standard deviations (constant columns use 1), an
unpenalized intercept, and mean squared loss plus alpha=1 times coefficient
squared norm. First fit nuisance→angles. For the neural arm, fit nuisance→neural
on training trials; subtract those predictions; standardize those neural
residuals using training statistics; retain the first training PCA components
covering 90% variance; fit ridge to training angle residuals. Apply those
training transforms to query data and add the nuisance prediction. Zero
training neural residual variance gives exactly the nuisance prediction.
Ridge residuals are not orthogonal to their nuisance predictors: DeltaEV is
gain over this specified regularized nuisance model, not nuisance-free
conditional information or a causal effect.

The shifted control cyclically shifts **whole training neural trials** by
floor(n/2) within each target stratum, with no identity fallback and no query
shift. It then refits the entire neural nuisance regression, scaling, PCA,
and residual-angle decoder. This preserves time-within-reach and target
composition while disrupting trial-specific neural–kinematic association;
it is not a unique test of fine-joint causality. No model selection, extra
seed search, repeated partitions, or query-score tuning is part of the task.

## Submission and scoring

For each case write `predictions.npz` with exactly `trial_id`, `nuisance`,
`neural`, `shifted`; every prediction is a finite float array query-trial ×
51 × 24 in frozen ID order. The operator collects the 50 files as
`<case_id>.npz` and a strict `submission.json` with byte/SHA256 descriptors.
Each file is at most 128 MiB; the aggregate is at most 2 GiB. This is a file
format limit, not an authorized runtime or memory budget. Optional figures
and arbitrary extra artifacts are not accepted.

For each mouse/area/joint, pool held-out predictions across the five folds
once and compute `DeltaEV=(SSE_nuisance-SSE_neural)/SST_query`.
SST is the pooled query mean-centered sum of squares, not a fold-wise mean.
All 24 joints require positive SST; the task is unscorable if a prescribed
target is constant, rather than silently excluding that target. Also report
R² for all three arms, neural-versus-shifted incremental EV, and prediction
RMSE versus each trusted arm. Neither cells, bins, trials nor folds become
independent population units.

The primary grade is mean absolute error of these 240 DeltaEV values against
the fixed trusted procedure, weighting mice, areas and joints equally
(dimensionless; lower is better). Report the five paired S1−M1 vectors,
their mean, descriptive t95 interval (df=4), and exact 32-sign-flip p values;
24 joint-specific comparisons receive Holm adjustment. Exchangeability and
the t interval's assumptions are not established by this small exposed
cohort; with five units the smallest two-sided sign-flip p is 0.0625.
The scalar paired-area reconstruction error is secondary. There is no
binary pass threshold or novelty/SOTA/research-qualification claim.

All candidate files must be structurally admitted before private reads.
The grader verifies arithmetic from submitted predictions, not the candidate's
claimed metrics. An artifact alone cannot prove that a program ran, used
the prescribed fits, respected access isolation, or did not reuse outputs.
Those are external execution conditions. A future arbitrary-method improvement
study needs its own declared access/model budget and controls; it is not
silently included in this reconstruction task.

## Current delivery limits

The code, source inventory and preparation recipe are present. The full ten
recordings total 12,707,357,935 bytes and are not bundled. The earlier 4.65 MB
header intake observed only one recording's structural fields; it did not
validate LR values, phase intervals, eligibility, all ten sessions, model
fits, or control predictions. Actual preparation, protected case bindings,
trusted reference predictions and environment execution remain absent.
The package is therefore partial and cannot currently produce a scientific
grade. Local-use construction and public redistribution rights are separate.

Source: [GSK26 author repository at the fixed revision](https://github.com/kaufmanlab/GSK26-public/tree/815b610b3beddfed5a3abf611d3a465ab9e4ce5c),
[paper DOI](https://doi.org/10.7554/eLife.106270.3),
[version-one data](https://figshare.com/articles/dataset/28326998/1).
The source lineage and deviations are recorded in `SOURCE.md`.
