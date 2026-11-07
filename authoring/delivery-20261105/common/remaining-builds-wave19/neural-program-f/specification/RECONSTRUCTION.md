# NEURAL-026: specification-only controlled-analysis reconstruction

Implement the following fixed analytical procedure from this specification.
The specification-only condition supplies no answer-producing implementation.
A separately reported reference-code condition supplies the same specification
and inputs plus the original method implementation. These are two access
conditions of one benchmark, not additional tasks or independent datasets.

This is retrospective, within-mouse reconstruction of a prescribed analysis,
not arbitrary-method improvement, native neural understanding, historical
Figure 5 reproduction, an online decoder, or a causal necessity test. The
source cohort is five mice (cfa17, cfa19, cfa20, cfa22, cfa24), each with M1 and
S1 imaging on different days. Five folds per session make 50 computational
cases and five paired biological units. All 50 cases and all 24 joint-angle
targets are required. This cohort overlaps NEURAL-025; it is not new data.

## Inputs and isolation

One invocation receives exactly one case's `input.npz` and `case.json`.
The NPZ has exactly `train_x`, `train_z`, `train_y`, `train_id`,
`train_target`, `query_x`, `query_z`, `query_id`, and `query_target`.
For each side, x is trial by 51 time bins by 128 selected ROIs and z is
trial by 51 by 141 nuisance features. Training y is trial by 51 by 24 native
joint angles. IDs are sorted, distinct positive whole-trial IDs; target is
LR 1 or 2. The case metadata fixes the IDs/order. Both sides contain at least
two trials per target, and their IDs do not overlap. All covariates and
training angles are finite. Query angles are unavailable. Training/query
packet arrays preserve the admitted preparation's types and values; do not
silently shrink or replace them for capacity reasons.

No other case packet, aligned-session collection, previous predictions or
trained model state is available. Other folds' training sets include this
fold's query labels, so cross-case access is a direct leak. One program and
its settings are frozen separately for each access condition before any case
input exposure. Every invocation starts fresh. No query-score tuning, seed
search, refitting across cases, or repeated partitions is permitted.

Preparation retains, per mouse and LR target, the first chronological
min(N_M1, N_S1) eligible trials from each area, at least ten each. Per-target
ordinal modulo five selects the query fold; the complement trains. Exactly
128 ROI ordinals are selected by outcome-free SHA256 ordering. The source
quality/window rules, events smoothed at 35 ms, angles smoothed at 15 ms,
per-ROI lags and source clocks are retained. The 51 samples span -100 through
+400 ms at 10 ms spacing relative to lift. This grid is not independent
100 Hz imaging; events are deconvolved fluorescence, not measured spikes.
Original angle units are retained. Portable alignment's numerical parity
with MATLAB is unmeasured. Matched session support does not pair reaches.

The already prepared nuisance basis has 102 target-by-time indicators;
12 target-interacted phase terms; six centroid xyz/velocity coordinates;
and their 21 upper-triangle quadratic products. The phase terms are phase,
phase squared, phase cubed, pre-lift indicator, post-grab indicator and
duration in seconds. Phase is clip(time_ms / (grabTimeC-liftTimeDLC), 0, 1).
Centroid is the mean of markers 9-12. Retrospective events and complete coarse
trajectory are available. This does not control every possible limb confound.

## Exact mathematical recipe

Flatten trial and time dimensions in their existing order: each whole trial's
51 rows stay consecutive. Z and QZ are training/query nuisance matrices;
X and QX are training/query neural matrices; Y is training angles. The query
target vector does not supply angles. Do not mix folds or learn any transform
from query inputs.

Define a ridge operation R(A, B, Q) returning both training and query fitted
values. Compute each feature's training mean m and population standard
deviation s (divisor n, not n-1). Replace exactly zero s by 1. Let b be the
training mean of B, U=(A-m)/s and V=B-b. Solve

    C = (U^T U + n I)^(-1) U^T V

using a linear system solve, then return U C+b and ((Q-m)/s) C+b. Here n is
the flattened number of training rows; alpha is exactly 1 under mean squared
loss plus alpha times coefficient squared norm. The intercept is unpenalized.
Every call uses its own training means/scales. No clipping, regularization
search, extra centering convention, or postprocessing is part of this recipe.

First apply R(Z,Y,QZ). Call its results B_train and B_query. Set training
angle residuals E=Y-B_train. The nuisance arm is exactly B_query. Reuse this
same nuisance fit for the other two arms.

For a neural-arm training matrix T (defined below), apply R(Z,T,QZ), giving
F_train and F_query. Compute residuals T-F_train and QX-F_query. Standardize
both using only the training residual mean and population standard deviation,
again replacing exactly zero scales by 1. Denote the standardized training
and query matrices A and Q. Compute the reduced singular value decomposition
of A (no full square expansion); let singular values be s_1,...,s_r in
descending order and right singular vectors form V. Energy is s_j squared.
If the sum of energies is exactly zero, the neural increment is all zeros.
Otherwise keep the smallest positive k whose cumulative energy fraction is
at least 0.9 (the first index at equality). Use the first k columns of V as
the basis, apply R(A V_k, E, Q V_k), and take its query fitted values as the
increment. Add this increment to B_query.

For the neural arm, T=X. For the shifted arm, first shift whole training
neural trials before flattening. Within each target stratum, list training
trial indices in their existing order. For a stratum of length m, destination
position j receives the source trial at position (j-floor(m/2)) modulo m.
This is a positive cyclic roll by floor(m/2), and no trial remains itself.
Keep Z, Y and all query inputs unshifted. Repeat the complete neural nuisance
regression, residual scaling, PCA and decoder for this shifted T. It shares
only B_train, B_query and E with the other arm; do not reuse that arm's neural
fit or PCA. Zero energy returns exactly the nuisance prediction. The recipe
therefore uses three to five ridge fits and two SVDs per case, with decoder
fits omitted only on zero energy.

Regularized nuisance residuals are not orthogonal to nuisance predictors.
The contrast below is gain over this particular fixed nuisance model, not
nuisance-free conditional information or cortical necessity. A shifted
whole-trial control is not a unique test of fine-joint causality.

## Output and grade

Write exactly `predictions.npz`, containing `trial_id` plus `nuisance`,
`neural`, and `shifted`. IDs exactly match the query order. Each arm is a
finite float32 or float64 array shaped query-trial by 51 by 24, obtained by
restoring trial/time dimensions. No figures or extra files are accepted.
The file cap is 128 MiB and a complete 50-file panel's cap is 2 GiB. These
format limits do not authorize runtime, memory or scientific execution.
The operator builds the strict collection manifest from captured outputs.

For each mouse, area and joint, pool each query trial exactly once across
five folds. Let SST be the sum of squared deviations of all pooled true
query values from their pooled mean. All 24 joints must have positive SST;
otherwise the full task is unscorable, with no target dropping. The primary
scientific estimand is DeltaEV=(SSE_nuisance-SSE_neural)/SST. The grade is the
mean absolute difference between the candidate's and trusted procedure's
240 DeltaEV values, weighting five mice, two areas and 24 joints equally.
Lower is better. A positive neural effect is never rewarded in itself;
negative, zero, null or inconclusive findings remain valid.

Secondary reports retain all three R-squared arms, neural-versus-shifted
incremental EV, prediction RMSE versus reference, five paired S1-minus-M1
vectors, descriptive t95 intervals with four degrees of freedom, exact
32-sign-flip p values and Holm adjustment over 24 joint comparisons. With
five mice, the smallest two-sided sign-flip p is 0.0625. Assumptions of these
descriptive summaries are not established by the exposed small cohort.

The two access conditions receive separate unchanged grades against the same
independently produced reference panel. There is no binary pass threshold,
positive-effect reward, extra task count or SOTA claim. Source/data and method
exposure are public; absence of the supplied implementation from a context
cannot prove absence from pretraining. Source construction alone does not
establish real-data, environment or scientific qualification.
