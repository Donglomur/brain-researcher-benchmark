# NEURAL-003 causal reaction-time source component

This is an incomplete source component for a prospective EEG reaction-time task. It is not a runnable benchmark, registered task, scientific result, or qualified data pipeline. No scientific runs, reference fitting, scoring, data acquisition, or dependency installation were performed for this snapshot. It adds no canonical assignment or qualification.

The planned population is 26 people. Whole-person outer holdouts and inner validation keep each person's sessions and original blocks together. The two matched arms are EEG plus contrast/instruction and contrast/instruction alone. Complete evaluation would require 52 person-by-arm output sets, with matching opaque query identifiers admitted before target access. A positive EEG gain is not required.

The prospective source uses a forward-only fixed smoother at native 1024 Hz and a fixed 100 ms landmark. This is a new causal recipe, not reproduction of the original retrospective preprocessing. The planned score is participant-macro mean absolute error in seconds, with paired person gains. The unchanged construction decision and missing-input contract give the scientific limits and distinguish this proposal from retrospective evidence.

## Included source

- `neural003/partition.py`: whole-person split construction from original trial and block identities.
- `neural003/window.py`: downstream causal-window and fixed-feature components; it does not authenticate a raw acquisition.
- `neural003/reference.py`: train-only matched ridge reference implementation.
- `neural003/prediction_schema.py`: complete two-arm output admission before target access.
- `neural003/scoring.py`: target-last scoring arithmetic; the protected target producer is still missing.
- `neural003/__init__.py`: package marker; no runtime entrypoint.

The six modules and two included contracts are unchanged source bytes. This README is only a scope summary; it does not replace or amend either contract. No recordings, participant identifiers, targets, predictions, primary-paper copies, execution records, source locks, or private build history are included.

## Prerequisites still open

The component still needs the original raw-data roster and redistribution rights; original person, session, block and trial joins; event and acquisition-clock calibration; verified native decoder and channel identity; outcome-independent eligibility and deadline support; a scientifically justified nonresponse/censoring policy; separately enforced fold/arm isolation; and a protected complete target producer. Resource feasibility, numerical agreement, reference competence and uncertainty qualification are also open. Missing total reaction times must not be silently imputed or given a replacement estimand.

## Dependencies

The code uses Python standard-library `dataclasses` and `math`. Python 3.11 or later provides the diagnostic `BaseException.add_note` API used by the raw-read error handler. NumPy is imported only inside the reference-fit and prediction functions. A future admitted MNE Raw-compatible object is required by the downstream window reader; MNE and an actual acquisition/decoder are not supplied here. No dependency versions or environments have been qualified, and this snapshot supplies no installation or execution recipe.
