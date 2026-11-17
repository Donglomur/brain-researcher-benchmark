# Original time-decoding endpoint component

This independent scorer computes the original seven-bin Pearson time-decoding
endpoint for PAPER-FIND-ADD-003. The preceding programme's native grader measures
reconstruction error; its prospective grader measures a different odor-decoding
task. Neither is used as the original paper's improvement score here. All
preceding source remains unchanged.

`score.py` pools the seven actual/predicted bin indices over every held-out trial
within each animal/day/cue/control panel. It computes Pearson correlation and the
source confusion convention (predicted rows, actual columns, division by the
number of trials). It preserves 11 mice, four days, two cues and real/shuffled
controls: 176 panels per method. Missing or failed predictions retain their
original positions and prevent scoring the affected panel. Constant predictions
produce an undefined correlation, with their finite confusion matrix retained.
No undefined animal is dropped from paired summaries.

The operator supplies source metadata and predictions as separate JSON files:

* The roster has `schema: h_original_time_roster_v1`, `input_sha256`, and 44
  `sessions`. Each session has `animal`, `day`, 140 `condition_codes`, and 140
  finite `recorded_delay_seconds`, all in original trial order. Allowed
  animal/day identities are explicit in the code. The source selects short
  trials with `code < 100 and recorded_delay_seconds == 2.5`, and long trials
  with `code < 100 and recorded_delay_seconds == 5`, using exact equality.
  Delay values must come from `beh(:,3)`; they cannot be inferred from condition
  codes, because preprocessing copies session `inputs.delay1/delay2`.
  Nonmatching delays remain in the 140-row roster but enter neither cue mask.
  Reversal-coded trials (511/512/521/522) are excluded on reversal days and
  rejected on standard days. Trial indices are zero-based source row positions,
  never re-numbered within a cue.
* Each method's document has `schema: h_original_time_predictions_v1`,
  `roster_sha256`, and `panels`. The hash is SHA256 of the roster serialized by
  Python `json.dumps(sort_keys=True, separators=(',', ':'), allow_nan=False)`.
  Each panel has `animal`, `day`, `cue` (`short`/`long`), `control`
  (`real`/`shuffled`), and `trials`. A finite trial has `trial_index`,
  `status: finite`, and seven integer `predicted_bins`, in actual-bin order 1–7.
  Failed/unstarted trials instead supply `reason`. A missing record is explicitly
  retained as unstarted. Duplicate, extra-cue, or extra-session records fail.

The roster is operator input, not a candidate-supplied way to choose evaluation
support. Its source digest is bound to the original processed
`rawtrialsstand2torev2_n11.mat`; the unsmoothed/unfloored release is a separate
condition. **Hash declarations do not authenticate acquisition or source joins.**
Authentic roster extraction and custody must be independently qualified before
using this component on study predictions. No observation or target file was
read to construct the generated controls.

Run with Python 3.10 or later (stdlib only):

```sh
python3 score.py --roster /operator/roster.json \
  --author /operator/author-predictions.json \
  --candidate /operator/candidate-predictions.json \
  --output /operator/comparison.json
```

The output path must not already exist. Every input is capped at 8 MiB and parsed
without duplicate JSON keys or nonfinite constants. Outputs include both full
method panels and 16 separate day/cue/control paired-animal delta summaries.
Each mean and descriptive SEM requires all 11 paired mice. These summaries are
descriptive; they do not introduce an across-day/cue headline score, significance
test, minimum effect, or paper-win rule.

Upstream author execution still requires the original processed observations,
`iscell > 0.3` eligibility, the native 10,000-ROI branch, ten-frame means over
source frames 97:106 through 157:166, whole-trial leave-one-out across all seven
bins, the full source loop/RNG scope, and the R2021a `fitcecoc` defaults. Shuffled
author predictions must use the original once-per-helper training-label
permutation. This scorer verifies numerical support, not how a model was fit.
Candidate algorithms can differ while retaining the original input/split
comparison. Prediction collection, native baseline reproduction and execution
provenance are not implemented by this component.

Published numerical Fig. 4D outputs remain uninspected. Original ROI/session
joins, native author replay, all companion behavior/sequence/odor/information
analyses, prospective meaningful gain and paired-animal inference remain
unqualified. The source task stays `source_unresolved`. Generated mathematical
controls establish software behavior only; they are not a study result.

The source endpoint is pinned in `SOURCE_PINS.json`; original author bodies are
not redistributed. An independent review identified and corrected an initial
code-only cue-membership shortcut before acceptance. Generated controls now
check recorded-delay/code disagreement and strict equality. Run
`python3 -B test_score.py` through the approved shared
test pool for generated controls.
