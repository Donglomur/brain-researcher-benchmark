# Finger EEG: first recorded-session construction evaluator

This package runs a complete selected-recording numeric-array → source-aligned
trial/window → train-only reference → participant-level evaluation path. It also
exports target-free held-out packets and scores external window probabilities.
It advances the recorded finger-imagery scope of `PAPER-paper-signal-add-017`.
It does **not** establish an EEGNet reproduction, a qualified benchmark, or a
new real-time human robotic-control experiment. Scientific qualification remains
unknown; the canonical task and historical evidence are unchanged.

## Primary-source contract

The [paper](https://www.nature.com/articles/s41467-025-61064-x),
[official code at c3a51c3](https://github.com/bfinl/Finger-BCI-Decoding/tree/c3a51c374d85f7b01e33ec4e998cf007d7da7763),
and [Figshare article 29104040, version 2](https://doi.org/10.1184/R1/29104040.v2)
support the following semantics. Exact inspected source hashes are in the
package's `provenance.json`.

* Source EEG is 128 channels × time at 1,024 Hz. `Target` and `TrialEnd` event
  samples are 1-based; the author loader subtracts one at both boundaries and
  uses a half-open slice, without a post-cue offset. Labels 1/2/4 mean
  thumb/index/pinky. Binary tasks exclude index trials after checking the
  original run's full class roster.
* The loader truncates trials at five seconds and performs common average
  referencing. It pads short trials with NaNs before windowing. This package
  produces the equivalent complete finite windows without materializing NaN
  padding: length 1,024, stride 128 samples. A three-second trial yields 17
  windows; a five-second trial yields 33. Nonfinite source samples and trials
  shorter than one second fail explicitly instead of disappearing silently.
* Original source training loads offline and prior sessions. Same-day ternary
  fine-tuning loads the ternary Base folder; binary fine-tuning loads **both**
  binary and ternary Base folders, then removes index trials. The source code
  splits training/validation by original trial 80/20 before overlapping windows.
  This package does not reproduce that validation/training procedure.
* Detailed paper methods and the dataset README specify eight ternary Base,
  eight binary Base, eight ternary Finetune and eight binary Finetune runs per
  online session, in that order. Run numbers restart inside folders; an R01
  filename does not identify global session chronology. Generic paper wording
  about the first eight calibration runs is insufficient for binary source
  routing; the executable selector follows the pinned code's two Base folders.
* Paper trial classification uses the class receiving the most window decisions.
  The evaluator uses this hard vote, not the argmax of mean probabilities.
* `S07/OnlineImagery_Sess05_3class_Base` is unusable because event information is
  missing. Admission rejects that family before loading numeric files. A
  source-complete calibrated S07 session-5 analysis cannot pass by silently
  omitting that folder. Any exclusion/reduced scope must be reviewed separately.
* The 21 retained participants are a selected cohort: 49 were recruited, ten
  withdrew and eighteen failed the offline eligibility criterion. These results
  cannot represent the unselected recruited cohort or all able-bodied people.

## Implemented scope and prospective decisions

`finger017.py` requires an explicit subject/session/run roster, original class
counts, imagery or execution condition, and source member identity. The same
original run cannot appear in more than one role, including through a new run
ID. Reused numeric-export paths, byte-identical exports and identical numeric
EEG arrays under different run identities are rejected. These exact-duplicate
checks do not authenticate arbitrarily transformed or sliced source payloads.
Training is offline/prior-session only. The paired replay endpoint uses
matching-class same-day Finetune runs for **both** reference variants. This
holds recorded test trials fixed; it is not the paper's human-adapting Base
versus Finetune online comparison.

`source_folder_selection` requires all eight calibration runs in each source
eligible family. `prospective_equal_run_subset` supports a declared first-N run
budget per eligible family, identical for all selected participants. The latter
is an explicitly prospective construction control, not a historical recipe.
Complete selected coverage is enforced against the frozen roster and observed
events; complete source-population coverage and payload identities still need
independent admission. A source member string and a numeric-export checksum
alone cannot authenticate a conversion from the public MAT archive.

The implemented reference extracts Hann-window log spectral power in 4–<8,
8–<13, 13–<30 and 30–40 Hz bands from per-window, per-channel standardized CAR
signals. It fits a fixed nearest-centroid model with diagonal training-feature
scaling and equal original-trial weights. All scaling/centers use training
data only. A second model adds the approved calibration trials and is called
**calibration augmented**, not EEGNet fine-tuned. These are prospective,
deterministic NumPy comparators selected to make the full evaluation path
executable without training the author's network. No competent authentic
baseline performance is claimed.

The source EEGNet path instead Fourier-resamples to 100 Hz, applies a causal
fourth-order Butterworth 4–40 Hz filter with 100-sample zero padding, standardizes
per-window channels, and trains/fine-tunes TensorFlow EEGNet. Those operations,
native environment, weights, validation model selection and first-four-layer
freeze remain unexecuted source requirements, not approximations claimed by
this reference.

Hard-window argmax ties and trial vote ties use the first declared class, an
explicit prospective deterministic policy. Accuracy gives every trial equal
weight within a participant and every participant equal weight. Confusion
matrices retain the fixed class universe, with per-class recall and precision
(precision is `null` for a class with no predicted support). Balanced accuracy is undefined
(`null`) when any selected participant has no support for a requested class.
The secondary Brier score uses mean window probabilities and is explicitly
prospective; it does not replace the hard-vote primary accuracy. Paired
accuracy deltas are participant-weighted. Percentile intervals resample paired
participants (2,000 draws, seed 17017); fewer than two participants gives an
undefined interval. These interval and aggregation choices are not frozen
paper tolerances or a significance gate.

The executable controls are training-label frequency (no-neural), seeded
within-session/class-family label permutation at original-trial level, and a
cyclic one-trial target alignment shift within each training run. They preserve
all windows belonging to a trial and never change evaluation targets. The
cyclic control is a prospective trial-correspondence perturbation, not a
validated subsecond cue-timing or ocular/muscle control. Permutations can be
weak or unchanged on tiny generated fixtures; controls are diagnostic and no
pass threshold or difficulty claim is inferred from them.

## Interface

The package needs Python and NumPy; the observed engineering environment was
Python 3.11.5 with NumPy 2.4.6. No dependency installation is part of this work.

```sh
python3 finger017.py reference protocol.json report.json
python3 finger017.py packets protocol.json packet-directory
python3 finger017.py score protocol.json score.json --predictions predictions.json
python3 -m unittest discover -s tests -v
```

The protocol is JSON with `schema_version: 1`, `task_id`, `classes` (`[1,4]` or
`[1,2,4]`), `condition` (`MI` or `ME`), `evaluation_session` (1–5), `subjects`,
`calibration_policy`, `calibration_runs_per_family`, and `runs`. Every run has
`id`, `source_member`, `subject`, `condition`, `session` (0 for offline),
`run_number`, `nclass`, `stage` (`Offline`, `Base`, `Finetune`), `role`
(`train`, `calibration`, `test`) and `expected_class_counts` with original
labels as string keys. The safe numeric-file interface additionally requires
`eeg_npz`, `eeg_npz_sha256` and `events`. NPZ files contain numeric `data` and
scalar `fsample`; they are opened with `allow_pickle=False`. Events are explicit
objects with `type`, `sample` and target `value`. Only `data`/`fsample` are read
from the archive; prediction/probability arrays are never imported. A generated
complete example is constructed in `tests/test_finger017.py::fixture`.

The API `prepare(protocol, recordings)` accepts the same numeric data and
events in memory. `public_packet(prepared, role)` exports EEG windows and a
whitelist of window/trial/run/subject/offset identifiers. Training and
calibration packets include their permitted labels; test packets never include
labels, events, online predictions or probability outputs. The protocol and
prepared truth remain evaluator-private. Public paper and source inputs remain
exposed; these packets do not constitute a sealed assessment.

Predictions map **every** expected held-out window ID to probabilities in the
declared class order. Missing/extra rows, duplicate JSON keys, nonfinite values,
out-of-range values or non-unit sums fail. `score` derives the full trial
result, confusion matrices and participant summaries. `paired_comparison`
requires identical protocol hashes and identical participant/trial/target
rosters; independent candidate-training/budget compliance still needs audit.

## Evidence and retained limits

The tests exercise independent arithmetic expectations, source sample/index
alignment, CAR, 17/33-window counts, binary calibration routing, chronological
and alias leakage failures, known missing-event rejection, roster/simplex
adversaries, target-free packets, target-mutation invariance, equal trial
weighting, hard-vote versus mean-probability disagreement, participant weighting,
cluster uncertainty, the complete reference/control path and all three CLI
commands. They use bounded generated arrays only. They establish engineering
behavior, not authentic signal quality, preprocessing equivalence or paper
reproduction. Runtime observations in the handoff concern these controls, not
full-session RAM/runtime or the 16 GB example subject archive.

Remaining gates include original MAT conversion and authentic source hashes;
complete participant/session inclusion; native EEGNet preprocessing and
fine-tuning; figure-specific targets/tolerances; source exposure and protected
evaluation; the separate participant-generalization extension; independent
eye/muscle/cue artifact controls; and an authentic resource envelope. No new
dataset payload, weight, model/API/native campaign or closed-loop study was run.

Data terms remain CC BY-NC 4.0. The top-level official repository is MIT, while
the EEGModels source carries ARL CC0 and Apache notices; component terms must
remain separate. No upstream code is vendored here. The evaluator is newly
written source informed by the pinned interfaces, and source/readme/paper
provenance is retained without turning public availability into rights or
non-exposure qualification.
