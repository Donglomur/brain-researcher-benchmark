NEURAL-035: chronological held-out astrocytic peak-order reproducibility

Predict the relative ordering of cell fluorescence peaks in later30-second blocks
from earlier recordings of the same accepted astrocytes. This finite task tests
within-session order stability in two recall contexts. It operationalizes a narrower
question than the catalog's event-specific reproducibility beyond selection: the
released activity-selected anchors have too few events in some sessions for a
credible train/query event split, so those anchors and the paper's reconstruction
statistic are not used. No source-selected event or causal-memory conclusion follows.

The complete selected cohort is seven mice with both recall contexts,14 sessions.
All1,012 accepted session-local cells are retained, with no amplitude-based subset.
Cell correspondence is stable within each session only; there is no claimed
cross-context or longitudinal cell registration. Windows and cells are nested
measurements, not additional animals. Context and mouse identities stay private.

For each opaque session, public data contains four calibration blocks at0–30,
30–60,60–90 and90–120 seconds, and one validation block at150–180 seconds.
Query blocks are210–240 and270–300 seconds. Thirty-second gaps separate roles
and query blocks. Each block contains300 samples on the source-interpolated10Hz
grid, centered at0.05,0.15,… seconds within the block. Interpolation uses true
source timestamps without extrapolation. Traces are author-processed accepted
fluorescence; no physical spike-rate unit is asserted. Whole-session preprocessing
and ROI acceptance remain inherited, so this is retrospective held-out prediction,
not a strictly causal online forecast or a new-animal test.

Use calibration for method development and validation for selection. After fixing
the method, final refit may use all five public blocks. No query traces, peak
indices, flat-cell masks or surrogate values are supplied. The same frozen program
should produce predictions for all14 sessions before any private feedback.
`load_public.py` loads exactly these permitted arrays. The original whole traces,
NEURAL-034 folds and PAPER-FIND-NEW-001 inputs must not be candidate tools; prior
access to them disqualifies a protected-heldout claim. These source data are
historically public, so no globally unseen evaluation is asserted.

Submit one JSON document with schema `neural035-order-predictions-v1` and28
prediction records. Each record contains exactly `query_id` and `ordering_scores`:
one finite, nonboolean number in[0,1] for every public cell in its listed order.
Smaller values predict earlier peaks. Tied scores are valid. Require every query
and cell exactly once; duplicate JSON fields, duplicate/unknown IDs, missing cells,
extra fields, NaN and Infinity are invalid. The entire submission is limited to2MB.

The private target for a cell is its first exact maximum sample within the query
block. A within-cell plateau uses its first maximum. A cell whose whole query
trace is exactly constant has no defined ordering target; its candidate output
is still required, but it does not participate in that block's ranks. Both target
peak times and candidate scores are reranked on the same private active-cell
subset using average ranks for ties, then divided by `n_active−1`. Thus a flat
cell cannot indirectly alter another cell's scored rank. Fewer than two active
cells makes the whole block undefined, propagating to the complete primary;
there is no silent subset renormalization. An all-tied active target is retained
and reported, not interpreted as a resolved sequence.

The primary is mean absolute normalized-rank error, lower is better. Average
cells within query block, both query blocks within session, both contexts within
mouse, then the seven mice equally. All per-block and per-mouse results remain
visible. There is no binary performance threshold. The fixed analytic reference
is each cell's mean normalized peak rank across all five public blocks after
final refit; calibration-flat cells, or blocks with fewer than two active cells,
receive0.5 for that reference calculation. It is evaluated during future scoring,
not fitted or evaluated during package construction.

Diagnostics report paired context-A-minus-context-B error for each mouse and
the equal-mouse mean, plus error under99 fixed independent per-cell circular
shifts of each private query block (PCG64 seed35035). Shifts preserve each cell's
cyclic autocorrelation and value distribution, while changing relative cell phase.
The surrogate-mean-error minus observed error is descriptive; it is not a
permutation p-value and does not establish stationarity, event alignment,
causality or control of all biological/selection confounds. Finer event-specific
questions, raw event detection and full-paper reproduction remain outside scope.

Source: [Zenodo21780255](https://zenodo.org/records/21780255), associated with
[Hippocampal astrocytic sequences](https://doi.org/10.1038/s41593-026-02448-0) and
[author code](https://github.com/rsenne/dCA1_Paper), commit
`5be84b41dc3580dd4942ea72b8c50a3248538821`. This cohort overlaps NEURAL-034 and
PAPER-FIND-NEW-001; it is one distinct endpoint, not another independent dataset.
