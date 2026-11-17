# Original decoder accuracy scoring component

`scoring.py` computes the four-tone decoding endpoint from class predictions and
operator-owned labels. The existing `full-participant-executor-v2` assessor measures
maximum absolute reconstruction error against a reference. That diagnostic cannot
measure a signed decoder gain. This separate component computes accuracy and paired
candidate-minus-author gains without replacing the historical reconstruction route
or the prospective `corrected_methods_v1` analysis.

Reproduction and improvement are separate first-class outcomes. This component
reports absolute participant reconstruction error and its group mean separately
from signed participant accuracy gain and its group mean. Error cannot cancel
across people. Neither decoder score alone reproduces the paper's full scientific
finding or establishes preactivation.

For paired paper+data and paper+data+official-code evaluation, use the same frozen
operator support and author baseline for each arm and report them separately.
This component performs scoring; it does not issue participant access, enforce
equal compute, or replace the existing paired-delivery machinery.

The result is a complete matrix panel, not a scalar benchmark reward. All 33
declared participants, four entropy conditions, and both original and reordered
pipelines are required. Sound and omission produce separate results. The original
publication's inclusion, folds, filtering, and timing remain unresolved; passing
these software checks does not authenticate them.

## Operator API

The operator supplies `frozen_trials`, a mapping from each `FoldKey` to its exact
ordered trial identities, and the exact observed training/testing time axes.
These must come from a separately frozen original source preparation. The panel
scorer does not generate or alter a split, select a time window, infer participant
eligibility, or prepare recordings. A manifest supplied by a caller is not proof
of publication parity or of the candidate's permitted training observations.

The separate `pinned_sound_folds(ordered_event_ids)` helper implements the exact
current author script at `a454439aec8936ff9de2199ab255472c7d140b8c`:
unshuffled `KFold(5)`, removal of the final test event in the first fold, the first
two in the last fold, and both boundaries in interior folds. Boundary events
remain excluded from training as well. All 12 boundary exclusions are retained
explicitly when each fold is nonempty. Input event order must already reflect
the author's matching step. MNE may subsequently drop epochs; the final scoring
manifest must use observed retained events, not infer their survival. This helper
recovers the pinned current-source split, **not** the paper's described stratified
split or an authenticated publication-vintage run.
Replicating this event-index rule is also not a proof of physical sample or
continuous-filter independence across training and testing.

`compare_panel(cases, stimulus=..., train_times=..., test_times=...,
fold_ids=..., frozen_trials=...)` accepts an iterable of
`(FoldKey, Targets, author_predictions, candidate_predictions)`. Both prediction
objects contain ordered trial IDs, actual time axes, and an integer array shaped
`(trial, training_time, testing_time)` with tone codes 1–4. Labels for omission
trials identify the omitted tone. Operator-owned labels stay outside the decoder
interface and outside public Git. `cases` can stream one fold at a time; the
scorer does not require a full study's prediction tensors in memory.

`score_fold` computes correct counts, tested-trial counts, and genuine 4×4
confusion counts for every train/test cell. The confusion axes are **actual,
predicted**. Missing true classes retain zero count rows. No balanced-accuracy
replacement or row imputation is used. These raw counts can feed a separately
qualified theoretical control; this component does not itself calculate the
transition/lag model, most-likely rescoring, Bayes factors, or cluster tests.

`compare_panel` uses the source consumer's equal-fold mean accuracy, then equal
participant averaging. It preserves unequal fold denominators explicitly. Its
participant arrays have axes `(participant, pipeline, condition, train, test)`;
group arrays remove only the participant axis. Accuracy is percent correct and
paired gains are percentage points. No time cells, entropy conditions, or
participants are silently pooled into a new primary scalar. In particular,
nominal 25% chance is not substituted for the author decoder.

The source sound route requires five folds. Omission fold IDs remain an explicit
source input because publication-vintage producer parity must be resolved before
using either the historical source or the separately corrected route. The
module rejects missing/extra/duplicate panel identities, shortened trial support,
trial reuse across folds, reordered trials, shifted/swapped time axes, noninteger
or out-of-range tones, and malformed prediction shapes.

The source files and exact hashes are listed in `SOURCE_BINDINGS.json`. The
recovered sound producer averages its folds before saving `newcv_...` files;
`postprocessing.qmd` loads `cv_...` files and averages a fold axis if present.
Those names and the already documented timing/preprocessing discrepancies are
still unresolved. Retrieval of the registered plural omissions filename returned
404; `base.py` and README retrievals hit the public API rate limit. No scientific
values or private solver targets were acquired.

## Verification and qualification

The adjacent `test_scoring.py` uses generated labels and predictions only. Its
oracle explicitly enumerates confusion counts, distinguishes equal-fold scoring
from pooled-trial scoring, gives one participant ten times more trials to check
equal participant weighting, and checks signed gains and nonuniform temporal
cells. Run it through the shared lightweight test pool using the existing NumPy
environment. Exact executed commands/results belong in `HANDOFF.json` after
execution; this README alone does not report a pass.

No authentic data, source targets, fitted author model, candidate model, or agent
attempt was run. Exact published accuracy matrices and the complete source
participant/trial/fold join still require recovery. Before a same-task victory,
the owner must qualify that original baseline, preserve the empirical and
theoretical controls and sound/omission distinction, and freeze a meaningful
effect and full-panel participant-level uncertainty rule. This arithmetic
component intentionally supplies no inferential result, binary reward, claim of
anticipation, paper improvement, or current-SOTA claim.
