# NEURAL-003 causal reaction-time source component

This is an incomplete source component for a prospective EEG reaction-time task. It is not a runnable benchmark, registered task, scientific result, or qualified data pipeline. No authentic scientific run, reference fitting, data acquisition, or dependency installation is qualified by this snapshot. Generated arithmetic controls exercise the scoring code only. It adds no canonical assignment or qualification.

The planned population is 26 people. Whole-person outer holdouts and inner validation keep each person's sessions and original blocks together. The two matched arms are EEG plus contrast/instruction and contrast/instruction alone. Complete evaluation would require 52 person-by-arm output sets, with matching opaque query identifiers admitted before target access. A positive EEG gain is not required.

The prospective source uses a forward-only fixed smoother at native 1024 Hz and a fixed 100 ms landmark. This is a new causal recipe, not reproduction of the original retrospective preprocessing. The planned score is participant-macro mean absolute error in seconds, with paired person gains. The unchanged construction decision and missing-input contract give the scientific limits and distinguish this proposal from retrospective evidence.

## Included source

- `neural003/partition.py`: whole-person split construction from original trial and block identities.
- `neural003/window.py`: downstream causal-window and fixed-feature components; it does not authenticate a raw acquisition.
- `neural003/reference.py`: train-only matched ridge reference implementation.
- `neural003/prediction_schema.py`: complete two-arm output admission before target access.
- `neural003/scoring.py`: target-last scoring arithmetic; the protected target producer is still missing.
- `neural003/__init__.py`: package marker; no runtime entrypoint.

The partition, reference, prediction schema and both included contracts retain their previous source bytes. The scoring module preserves finite participant means when an intermediate sum overflows, while retaining the original successful arithmetic, equal-person weighting and target-last barrier. The window reader now binds absolute acquisition sample numbers to the reader’s first_samp and translates them into zero-based get_data indices; its complete acquisition-start history and deadline support are checked before the first signal read. This README is only a scope summary; it does not replace or amend either contract. No recordings, participant identifiers, targets, predictions, primary-paper copies, execution records, source locks, or private build history are included.

## Prerequisites still open

The component still needs the original raw-data roster and redistribution rights; original person, session, block and trial joins; event and acquisition-clock calibration; verified native decoder and channel identity; outcome-independent eligibility and deadline support; a scientifically justified nonresponse/censoring policy; separately enforced fold/arm isolation; and a protected complete target producer. Resource feasibility, numerical agreement, reference competence and uncertainty qualification are also open. Missing total reaction times must not be silently imputed or given a replacement estimand.

## Dependencies

The code uses Python standard-library `dataclasses` and `math`. Python 3.11 or later provides the diagnostic `BaseException.add_note` API used by the raw-read error handler. NumPy is imported only inside the reference-fit and prediction functions. A future admitted MNE Raw-compatible object is required by the downstream window reader; MNE and an actual acquisition/decoder are not supplied here. No dependency versions or environments have been qualified, and this snapshot supplies no installation or execution recipe.

## Generated scoring regression checks

Run `python3 -I -S -B benchmarks/neural/NEURAL-003/implementations/causal-reaction-time/test_scoring.py` from the repository root. The 12 tests use the actual public prediction schema and scorer with invented complete26-person/52-product inputs. `fixtures/scoring_before_overflow.py` is the ordinary predecessor regression fixture (2,737 bytes; SHA-256 `11299c87f9b0a4affa50bdaff57cad8923a2b1599effb90e767f82cad6761d45`), not an alternative runtime. No authentic targets or private history are included. The existing scientific-contracts CI job runs the same checks. The new internal mean materializes a tuple; its authentic aggregate memory/CPU cost remains unqualified.

## Acquisition sample coordinates

`Schedule` fields and response sample numbers use the original acquisition's
absolute integer sample numbering. `raw.first_samp` must equal the independently
supplied `session_start`; `raw.n_times` must cover the entire required prefix.
Only the arguments sent to `raw.get_data` are translated to zero-based reader
offsets. A later crop cannot supply the omitted filter history by changing the
reader start alone. Authentication of the original acquisition and its onset
join remains the caller's unresolved prerequisite.

The previous code passed absolute coordinates directly as reader offsets. For a
reader starting at sample2000, a schedule beginning at2000 requested data starting
at offset2000 (absolute sample4000). Expected array shape did not detect that
shift. This was a downstream coordinate hazard; no authentic recording or past
scientific outcome has been shown affected.

The [official MNE Raw documentation](https://mne.tools/stable/generated/mne.io.Raw.html#mne.io.Raw.get_data)
describes zero-based start/stop indexing and the separate first-sample timeline;
its crop documentation explains preservation of nonzero `first_samp`. This was
reviewed as hosted documentation, not used to qualify an installed MNE runtime.

`test_window_grid.py` uses a generated MNE-interface-shaped reader, not MNE or
neural data. It verifies nonzero-origin translation, zero-origin equivalence to
the retained predecessor fixture, future-only perturbation invariance, complete
history, and refusal of absent/mismatched/short sample grids before reading.
It also verifies that a forged `Schedule` cannot alter early-response eligibility.
Run from this implementation directory with `python3 -I -S -B test_window_grid.py`
through the shared construction test pool. These controls do not establish
hardware timing, acquisition authentication, physical I/O causality or task readiness.

## Target callback roster binding

The scorer snapshots all expected opaque ID sequences before admitting public
outputs. The same immutable tuples are used to join returned private targets.
Changes to the caller's mapping or lists inside the target callback cannot
retarget already admitted predictions. This preserves the existing 26-person,
two-arm MAE and target-last barrier; it does not authenticate a target producer
or enforce process isolation.

Previously, the scorer reread the caller's mutable expected roster after the
callback. A callback that reversed the IDs and target rows could silently pair
predictions with different trials. `test_target_binding.py` demonstrates that
failure on the retained `fixtures/scoring_before_roster_snapshot.py` and checks
snapshot binding, unchanged scores, caller mutation, and refusal before private
access. All cases are generated software controls, not authentic reaction-time
observations or evidence that any historical scientific result was affected.
Run `python3 -I -S -B test_target_binding.py` from this implementation directory.
