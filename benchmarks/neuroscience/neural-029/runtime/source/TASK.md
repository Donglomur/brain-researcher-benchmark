# NEURAL-029: registered-cell calcium transfer across reward delay

Predict all trial-by-registered-cell calcium trajectories in the two-second dopamine
reward-delay condition from the corresponding one-second condition. This is a
retrospective within-animal condition-transfer task for granule cells (GrCs). It is
not CF activity, water-reward transfer, author-figure reconstruction or new-animal
prediction. Source: Filio et al., Zenodo21645651, Nature Neuroscience DOI
10.1038/s41593-026-02449-z. The other cerebellar export from Zenodo19345221 is not
an input to this task.

Use every GrCs=Y/Delay=2 session with chronicGreen and its unique same-mouse,
same-DAT/MFB-type Delay=1 session identified by Alt_Delay_Dir. Retain every positive
one-to-one cell registration in finalMatchesMat. Zero-sided rows are structurally
unmatched cells; no activity/reliability-based cell selection is allowed. Ambiguous
registration orientation, absent required data or nonfinite matched calcium blocks
preparation for the whole cohort instead of creating a convenient subset. The
complete biological cohort and counts remain unverified because both MAT parts
are not locally held.

The signal is endAlgn.sigFilt_right_green, a trial×cell×time processed calcium
array. Its neural clock is tmpx_right; tmpxx is not substituted. Use linear
interpolation without extrapolation at 0,0.05,…,3 seconds after movement end.
All recorded trials are included, without filtering on rewarded, goodMvmt,
reliability or response amplitude. This prospective selection differs from the
paper's rewarded-trial and figure-specific selections. The estimand is the expected
trajectory across all trials in an unknown outcome mixture. No future outcome is
a candidate input.

One-second source trials are split at floor(0.8*N): earlier source-order trials
are calibration, the remainder validation; require at least five source trials.
The source's chronological trial ordering is not independently verified, so this
is explicitly a source-order split. Each whole trial stays in one role. After
method selection, final refit may use all public one-second trials. Every
registered two-second response trajectory is private. The candidate receives
opaque pair/cell/query IDs, the time grid, planned delay and DAT/MFB type only
for query cases. It receives no query calcium/history, movement, licking, actual
reward delivery or treatment-coded acquisition paths. One frozen program must
predict the complete target-condition cohort before any private feedback.

Submit exactly one record per public pair, with pair_id and values. values has
shape [number of query IDs,number of cell IDs,61], using exactly the public orders.
Every scalar must be finite and nonboolean. Duplicate fields, unknown/duplicate
pairs, extra fields, missing samples and nonfinite values are invalid. The whole
JSON submission is bounded at100MB. The complete submission is validated before
any private target array is loaded. No candidate runtime is created by this package.

The primary is mouse-macro normalized RMSE (lower is better). Per pair, compute
mean squared error over all target trials, matched cells and time bins. Divide
by training variance: mean squared deviation of all public one-second calcium
from each cell's mean over public trials and time. Take the square root; average
pairs equally within mouse, then mice equally. Zero training variance makes that
pair and the complete primary undefined; no epsilon or favorable subset is used.
Unrepresentable arithmetic is rejected without a partial score. This preserves
the pooled pair RMSE ratio; it is not a mean of per-cell normalized RMSEs. Cells and trials
are nested observations, not extra animals.

Diagnostics retain raw RMSE and R² for each pair. R² centers each target cell
across target trials/time; zero target variance is undefined. Two fixed analytic
comparators use the mean over all public one-second calibration and validation
trials, with no target calibration:

- The absolute-time comparator repeats the source mean trajectory at the same
  movement-end time for every two-second query trial.
- The fixed timing comparator predicts `mu1(g(t))`, where `g(t)=t/2` for
  `0<=t<2` and `g(t)=t-1` for `2<=t<=3`. At exactly two seconds the latter
  branch applies and both branches meet at source time one second. Linear
  interpolation uses only the same candidate-visible source grid. Extrapolation
  is forbidden. No alpha is fitted and no negative-time additive comparator is used.

Both comparators cover identical cells, query trials and all 61 query times. The
scorer reports candidate-minus-absolute, candidate-minus-warp, and warp-minus-absolute
NRMSE per pair and per mouse, plus the same mouse-macro differences and leave-one-mouse
sensitivity. Lower differences favor the first-named arm. These computations are
reserved for future separately authorized grading; no authentic result exists here.

The bound operator-private support report retains the complete source-session
census, structural registration exclusions, pair/session/cell/trial inverse and
registered-cell graph. It counts repeated component appearances and overlapping
source trials separately from unique animals, sessions, components and trials.
The same recurrent cell can receive weight through several pairs in the preserved
primary. A component-balanced sensitivity is explicitly deferred: this source does
not invent a replacement normalization. Any unsupported required pair blocks the
whole preparation; a successful support report is conditional on a complete index,
not proof of biological completeness. Neither this report nor private identities
are candidate inputs.

Processed signals may use whole-session normalization or noncausal filtering;
this is not online causal forecasting. There are no movement/licking adjustment
claims, optogenetic causal claims, or globally unseen-data claims. The original
release is public, and related paper/NEURAL030 exposure must be disclosed.

This source package is partial: the two required MAT recordings, verified full
cohort/registration/clock/NaN inventory and actual public/private packet are absent.
A checked schema and executable scorer do not make those missing inputs available.

This explicitly versioned method successor uses raw/identity/binding/target/grade v2.
Public inputs and submission v1 are unchanged. The original source packet remains
intact. Every authentic-input, native-execution, scientific-qualification and
submission-readiness gate remains false. Behavioral independence belongs to the
separate NEURAL-030 prospective analysis and is not inferred from this transfer.
