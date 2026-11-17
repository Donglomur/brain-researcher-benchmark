# Initial evaluator v1: explicit segment-aligned correlations

[Package overview](../implementations/initial-evaluator-v1/README.md) · [Source provenance and requirements](../implementations/initial-evaluator-v1/source-provenance.json) · [Published paper](https://www.nature.com/articles/s41593-025-02060-8)

This original Python implementation recomputes cross-context correlations and same-context repeated-presentation noise ceilings from broadband-gamma electrode timecourses. It completes an explicit prospective correlation component for `PAPER-FIND-024`; it does **not** complete the canonical task, reproduce the native TCI implementation, refit integration windows, or establish scientific qualification.

The input is measured response timecourses plus an independently prepared segment-epoch map. It is not a table of expected answers. The engine extracts each response at requested lags, joins central segments by identity across contexts, computes Pearson correlations across those segments, and emits every declared electrode and condition, including undefined results. The task's immutable `task.json` retains authority.

## Run

Use an existing Python 3.10+ environment with NumPy. No dependency installation is part of this deliverable. Engineering controls were checked with Python 3.11 and NumPy 2.4.6.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-024/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/paper/PAPER-FIND-024/implementations/initial-evaluator-v1/evaluator.py /absolute/path/manifest.json /absolute/path/result.json
```

The CLI is offline. It loads only the local NPZ files named in the manifest, checks their SHA-256 values, and records file and manifest receipts. It neither acquires data nor loads Python pickles. The public function `evaluate(manifest, arrays)` supports an already loaded, participant-keyed array mapping; production artifact hashing is performed by the CLI loader.

## Input contract

Each participant NPZ contains exactly:

- `D`: real numeric array with axes **time × stimulus × electrode × repetition**; responses are processed broadband gamma in a consistent within-electrode unit, not raw iEEG.
- `t`: strictly increasing finite timestamps in **seconds** from stimulus onset, matching the time axis. Sampling may be irregular; interpolation uses actual timestamps.

A manifest has the following shape. The abbreviated arrays below are a documentation template; it is intentionally not an executable empirical example. A fully generated executable control is defined in `tests/test_evaluator.py:fixture`.

```json
{
  "schema": "find024-segment-correlations-v1",
  "input_role": "empirical_electrode_timecourses",
  "cohort_id": "prospectively-frozen-cohort-id",
  "eligibility_provenance": "independent cohort/electrode eligibility record",
  "selection_uses_assessment_effects": false,
  "boundary_policy": "explicit_distinct_contexts",
  "alignment_policy": "linear_interpolation",
  "lags_sec": [0.0, 0.01, 0.02],
  "evaluation_mode": "unsplit_recomputation",
  "story_splits": {"actual-source-story-id": "analysis"},
  "expected_participants": ["participant-id"],
  "participants": [{
    "participant_id": "participant-id",
    "electrode_ids": ["electrode-id"],
    "stimulus_ids": ["stimulus-id"],
    "stimulus_durations_sec": {"stimulus-id": 27.0},
    "repetition_ids": ["repeat-1", "repeat-2"],
    "bad_stimuli": {},
    "source": {
      "role": "empirical_electrode_timecourses",
      "npz_path": "participant-timecourses.npz",
      "sha256": "replace-with-the-actual-file-sha256"
    },
    "expected_cells": [{
      "story_id": "actual-source-story-id",
      "speech_rate": 0.5773502691896258,
      "segment_duration_sec": 0.037
    }],
    "epochs": [{
      "epoch_id": "unique-physical-epoch-id",
      "stimulus_id": "stimulus-id",
      "story_id": "actual-source-story-id",
      "speech_rate": 0.5773502691896258,
      "segment_duration_sec": 0.037,
      "context_id": "independently-established-context-arrangement-id",
      "segment_id": "same-central-acoustic-segment-id-across-contexts",
      "onset_sec": 0.0
    }]
  }]
}
```

Both main-experiment rates, `1/sqrt(3)` and `sqrt(3)`, must occur in each participant's frozen `expected_cells`. Values within an absolute tolerance of `1e-10` are canonicalized to those two rates before matching; duplicate canonical cells fail. This is stricter than the author rate selector and is a prospective input policy. Pairing of both rates is required at the participant level, not at every story/duration, and no paired hypothesis comparison is inferred. Each cell requires at least two contexts, three matched central segments, and two repetitions. The example template must therefore be expanded before use. Segment durations are **seconds**, unlike author `unique_segs`, which is in milliseconds. Lags must lie within the demo's `[-2, 4]` second domain and entirely within each extracted recording. No extrapolation occurs.

`context_id` identifies a repeatable surrounding arrangement, such as a natural order or a particular random order. `segment_id` identifies the identical central acoustic segment within one source story, duration and rate. Every context must have exactly the same segment roster in a cell; the engine refuses to silently intersect incomplete rosters. A physical `(stimulus_id, onset_sec, segment_duration_sec)` occurrence cannot be relabeled across contexts or segment IDs. Each stimulus is bound to one source story and rate. `stimulus_durations_sec` must cover all stimuli with their actual sound durations. Central segments must lie inside the sound interval `[0, stimulus_duration_sec]`, preventing recorded pre/post padding from being relabeled as a speech segment; response lags can legitimately extend beyond the sound interval if they remain within the recorded timestamps. The epoch map can represent nested segment durations, but it must be derived independently from real stimulus metadata before analysis; matching labels alone do not verify matching audio.

`bad_stimuli` maps known unusable stimulus IDs to prespecified reasons. All stimuli, including excluded ones, require epoch coverage so exclusions remain auditable. Nonfinite values are permitted only in explicitly excluded stimuli. Loss of a required cell or complete matched design fails the evaluation. Every expected participant and every declared electrode is retained; no assessment-dependent electrode filtering is implemented. The declared roster and eligibility statement are inputs requiring independent verification, not an authentication mechanism.

## Frozen prospective calculations

For each participant, electrode, source story, speech rate, duration and lag:

1. Evaluate the measured timecourse at `onset_sec + lag_sec` by linear interpolation of `t`.
2. For every context, correlate corresponding central-segment vectors between each unordered pair of repetitions. The arithmetic mean of these correlations is `same_context`.
3. For every unordered pair of distinct contexts, correlate central-segment vectors for **all** ordered cross-context repetition combinations. Their arithmetic mean is `diff_context`.
4. If both quantities are defined and the ceiling is positive, report `diff_context / same_context`. Do not clip negative CCC values or corrected values above one.

The endpoint definition is grounded in the paper. The linear interpolation, exhaustive context/repetition pairing, equal weighting, complete-case rejection and minimum three-segment rule are **prospective engineering policies**, not established author defaults. They make small-sample degeneracy, missingness and population changes visible and reproducible. Native TCI equivalence remains held until its alignment, boundary matching and pair-weighting source is resolved and independently compared.

A constant response vector makes a pair's Pearson correlation undefined. If any prespecified pair is undefined, its aggregate remains undefined instead of dropping that pair. Nonpositive ceilings retain their raw values and receive a null normalized result. If dividing by a positive subnormal ceiling overflows floating-point arithmetic, the raw CCC and ceiling remain intact and the normalized result is null with `nonfinite_normalization` status; no arbitrary reliability threshold is introduced. Complex arrays are rejected rather than silently discarding imaginary components. JSON outputs use null and explicit status/counts rather than NaN or a plausible-looking zero.

Population summaries keep each story and split separate. They average electrodes within each participant and then average participants equally. The ratio of these separately averaged CCC and ceiling values is reported distinctly from the mean of electrode-wise ratios. This is a **prospective descriptive participant-balanced summary**. It is not the paper's electrode-pooled anatomical ROI analysis, a hierarchical bootstrap, a Bayesian mixed-effects fit or an inferential claim.

## Split and exposure boundary

`unsplit_recomputation` requires every story to be labeled `analysis`. It does not claim held-out performance. This is necessary because verified independent story identities and enough units for a split are still unknown; no train/test split is invented from the published main experiment.

`prospective_story_holdout` requires both `train` and `assessment` source stories. A global story-to-partition map prevents one declared story from occurring in both partitions, and stimulus bindings prevent a recording from being relabeled across stories or rates. All copies across rate, context and repetition of a source story stay in its partition. The engine performs no tuning or model fitting. It computes both partitions into an **operator-only** report; assessment arrays and reports must not be sent to a candidate or used for selection. It cannot detect secretly aliased stories/audio, nor establish independent participant/stimulus membership. Participant holdout, candidate isolation and protected reference control remain held.

## Source boundaries and unmet requirements

See `source-provenance.json` for pinned source identities, retrieved-content pin semantics and the requirements map. No author source code or empirical data is redistributed.

The native gamma model predicts empirical CCC by multiplying a noise-free window prediction by a lag-, duration- and rate-specific ceiling. Its demo specifies `unbiased-sqerr`, 100 widths from 0.0312 to 2 seconds, zero delay, shapes 1–5, interval mass 0.75, boundary strengths 0, 0.25, 0.5, 1, 2, and shape tying across rates. Its actual prediction and loss implementation is not resolved from the top-level snapshot. This package therefore does not substitute a 0.75 threshold crossing, a curve-width surrogate or cached `model_fits.mat` for refitting neural integration windows.

Remaining gates include the empirical MATLAB-to-NPZ/epoch-map bridge; exact source dependency commits; all authentic input and cohort pins; native CCC numerical parity; gamma fits and the absolute-time/structure-yoking comparison; anatomical pooling; hierarchy inference; equal access and budgets; protected references; acceptance tolerance; native environment qualification; data/code redistribution rights; and authentic baseline/candidate evaluation. Scientific qualification is **unknown**, and the package registers no binary reward or numeric paper-reproduction target.
