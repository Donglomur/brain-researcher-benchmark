# Preprocessing and the original classification task

**Candidates may change preprocessing within the same permitted observations.**
Resampling, filtering and feature extraction are method choices. A difference from
the author's frontend does not by itself change the motor-imagery classification
task or disqualify an improvement comparison. This applies the repository's
[same-task improvement policy](../../../../../docs/science/paper-improvement/README.md)
to REVE; it does not change any task disposition or admission rule.

The fixed requirements are the original people, recordings and channels; event
anchors, class labels and temporal support; participant split; complete eligible
case roster; permitted information; and original scoring and evaluation rules.
Candidates cannot obtain additional recording context, omit difficult test events,
normalize using hidden targets or select a method using final test scores.
Transformations may use permitted training/validation feedback; test-distribution
adaptation is not implied by access to signals.

## Method provenance and case identity are separate

The paper describes 109 people, 9,837 four-second examples and the fixed subject
split 1–70/71–89/90–109. Its preprocessing description includes an intermediate
128-Hz representation with a 64-Hz low-pass before 200-Hz resampling. The released
code instead resamples directly to 200 Hz after referencing, high-pass filtering
and notching. This leaves historical recipe identity unresolved. It does not show
that either method used additional physical recordings. [Paper, Appendix C.5 and
Table 12](https://proceedings.neurips.cc/paper_files/paper/2025/file/20a917f77773ac0fa8bea2bdd6606b66-Paper-Conference.pdf),
[pinned preprocessing](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/preprocessing/preprocessing_physio.py).

If both methods receive the same permitted raw EEG, retaining frequencies that the
author's filter removed is a legitimate method change. It is not acquisition of
extra measurements. Conversely, a condition restricted to prepared windows does
not automatically permit access to entire continuous recordings: filtering context
and the raw-input allowance must be declared for both methods.

The released code constructs annotation-derived events **after** its final 200-Hz
resampling, then extracts 800 samples starting at the event. Intermediate signal
resampling does not necessarily double-round event onsets if annotations survive
and event indices are created only at the final grid. Inspected MNE 1.9 source
supports that conditional mechanism; it does not prove the unrecovered historical
pipeline or numerical equivalence. Recording-length rounding, boundary-short
windows, rejected annotations and library behavior can still alter case membership.
[MNE annotation conversion](https://github.com/mne-tools/mne-python/blob/v1.9.0/mne/annotations.py#L1477),
[MNE resampling](https://github.com/mne-tools/mne-python/blob/v1.9.0/mne/io/base.py#L1301).

Equal totals alone cannot prove an event bijection. The current
[original-panel route](../original-physionet/README.md) binds original recording and
annotation-index event IDs, labels, splits and exclusions. Its complete released
panel preserves all 654 imagery recordings and records the final S104R08 boundary
drop. A historical event-level manifest has not been recovered. Any alternate
frontend must preserve the frozen eligible cases and permitted time support;
changing sample values does not excuse changing which events are scored.

## Current inputs and a possible raw-input condition

The current common packet contains released-profile prepared arrays. Candidate
transforms of those arrays are allowed within the declared development and frozen
prediction rules. A reference and candidate can be compared on that exact complete
1,803-event test panel without first proving which filter produced the historical
paper score.

A future raw-preprocessing condition would need a separately specified common raw
view, equal channel/time/context permissions, and a stable case manifest based on
original recording and annotation anchors. Raw EDF annotations contain class
information; mounting them unchanged into an untrusted held-test worker would
expose answers. No raw view or new participant permission is created here.

## What a completed comparison could claim

A fixed-parameter, validation-selected released-method refit can provide a
same-task author-method comparator once its execution and competence are qualified.
Candidate frontend differences are permitted within the fixed observations and
cases. A comparison still needs a competent verified baseline, complete paired
outputs, declared access/resources and a justified uncertainty/acceptance policy.
Neither source availability nor beating chance supplies those requirements.

Historical Table 12 reproduction remains distinct. The reported 0.6480 balanced
accuracy is contextual until the claimed comparison's case, aggregation and
uncertainty requirements are established. Missing historical seeds or checkpoint
identity do not categorically prohibit every source-method improvement claim;
they limit what can be reconstructed and which historical comparisons are supported.
A preprocessing difference alone must not become a blanket improvement prohibition.

The released Optuna configuration does not close the replication gap: `n_runs`
counts search trials, each initialized with the configured seed plus rank, and its
objective returns a test score for maximization. Those are not authenticated
independent repetitions underlying the paper's SD. That search must not be adopted
as protected validation-only tuning. This source observation does not establish
that the paper used that search. The maintained prospective runner instead keeps
test data out of fitting and selects with validation data.
[Pinned optimization source](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/dt_opt.py).

Current historical reproduction uncertainty, the failed 8 GiB runtime qualification,
and the absence of a complete authentic refit remain unchanged. This clarification
migrates no contract, promotes no readiness count and establishes no improvement or
SOTA result.
