# PhysioP300 complete-panel metric component

This operator-side component computes event AUROC, balanced accuracy and Cohen
kappa for every cell of the selected original PhysioP300 Table 4 panel. It
requires the nine nominal source subjects `1,2,3,4,5,6,7,9,11`, three explicitly
named repetitions, and candidate, EEGPT, BENDR, BIOT and LaBraM predictions: 135
cells. All methods and repetitions must predict precisely the same complete
event set for each subject. Paired candidate-minus-reference differences are
reported separately for all four source methods. These are differences on the
same observations, not independent subject replicates or statistical evidence.

The retained S8 implementation requires seven datasets and prospective control
selection. This component supplies arithmetic for the current selected P300
panel without modifying that historical implementation. It neither executes
models nor authenticates original cohort/preprocessing, model ancestry or LOSO
training. It is not an admitted improvement grader, and produces no paper-win
decision. The authoritative task and improvement contract remain unchanged.

## Operator interface

Use Python 3.10+ with the standard library. The roster contains operator-owned
targets; never deliver it or this scoring invocation to a participant process.

```sh
python3 score_panel.py --operator-roster /operator/roster.json \
  --predictions /operator/frozen_predictions.json > /operator/metrics.json
```

The operator roster has this structure (the illustration is incomplete and will
be rejected until all nine subjects and their complete support are supplied):

```json
{"schema":"physiop300_operator_roster_v1","subjects":[
  {"subject_id":"1","events":[
    {"event_id":"s1:r1:e0","recording_id":"s1:r1","target":0},
    {"event_id":"s1:r1:e1","recording_id":"s1:r1","target":1}
  ]}
]}
```

Use globally unique event and recording identifiers preserving recording/event
lineage. Reusing event indices across recordings is rejected. Recording IDs may
occur in only one nominal subject. Names do not authenticate biological people,
and matching the roster does not prove that it contains every source event.
No roster or real predictions are bundled.

The separate prediction document has only probabilities and identities:

```json
{"schema":"physiop300_predictions_v1",
 "repetitions":["declared-a","declared-b","declared-c"],
 "cells":[{"subject_id":"1","repetition":"declared-a","method":"EEGPT",
   "probabilities":[{"event_id":"s1:r1:e0","p_target":0.2},
                    {"event_id":"s1:r1:e1","p_target":0.8}]}]}
```

All 135 cells are mandatory; event order is irrelevant. Probabilities must be
finite numbers in `[0,1]`, with class 1 meaning attended-character target.
Predictions cannot provide labels. Duplicate identities, duplicate JSON keys,
partial controls, extra cells and altered support fail before scoring output.
Malformed input exits 2. This CLI is an operator utility, not a process sandbox
or an untrusted-file resource enforcement boundary.

## Source fidelity and remaining limits

The pinned probe concatenates validation batches for a held-out subject before
metrics; the kernel similarly pools events within each supplied cell. AUROC
counts positive-negative orderings with half credit for ties. No batch-average,
cross-subject pooling, seed pooling, fold weighting, best epoch or repetition SD
is introduced: the original reporting reduction remains unresolved, so
`source_panel_aggregate` is null. Repetitions are caller-declared fit identities,
not recovered historical seeds or evidence of independent fitting.

The author utility passes a 0.5 threshold to an unpinned PyHealth dependency.
The component reports both `ge` (`p >= 0.5`) and `gt` (`p > 0.5`) BAC/kappa and
confusion matrices. They coincide unless a probability is exactly 0.5. This
keeps the boundary uncertainty visible instead of claiming dependency parity.
No threshold is fitted or selected. Absent fixed-class support produces null
metrics, preserving all affected cells and deltas; the source's AUROC-zero
fallback is not interpreted as a valid measurement.

The eight-subject converter versus nine-subject probe, provider person mapping,
paper/converter epoch mismatch, possible cross-recording overwrites, original
epoch selection, checkpoint/exposure parity, full control production and author
calibration remain unresolved. Passing generated controls establishes software
behavior only. No authentic signals, labels, weights, training or predictions
were read or produced for this component. No numerical improvement is claimed.

`SOURCE_PINS.json` binds the locally inspected public source bytes and existing
task contract. `test_score_panel.py` supplies generated mathematical and paired
coverage controls; run it only through the shared reviewed test pool in this
parallel build. No scientific dependencies or downloads are required.
