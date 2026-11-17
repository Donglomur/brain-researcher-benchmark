# Full EEG trial identity preparation

`trial_roster.py` prepares the row identities needed by NEURAL-079's existing
encoding assembler. It preserves every retained EEG trial in its original HDF5
row order. Optional eye metadata adds covariate row indices using the exact
participant/session/run/trial key; eye rejection cannot remove an EEG target
row. Repeated presentations of a video remain distinct trials and retain the
same training/query assignment (1–1000 / 1001–1102).

The existing NEURAL-080 `join_metadata.py` constructs an EEG/eye intersection
for that task's different endpoint. Its intersection must not replace this
task's complete EEG target support. This component does not replace the
historical encoding runtime, change its scorer, or reclassify any neural access
mode. Encoding remains prediction of held EEG from video features.

## Input and execution

Use reviewed primitive JSON exported by an isolated, trusted metadata intake.
The author NPY dictionaries contain pickled objects and test-derived noise
ceilings; this program does not load NPY, HDF5, recordings, predictions or noise
ceilings. Existing shared selected-field exports can supply the `eeg` and `eye`
objects described here. Derivation and provenance of those exports still need
independent verification; a hash authenticates these supplied JSON bytes, not
their claimed scientific origin.

The input has exactly these outer fields:

```json
{"schema":"n079_primitive_trial_metadata_v1","people":[
  {"person":"sub-01","eeg":{},"eye":null}
]}
```

The shortened example shows structure only and is deliberately incomplete.
Provide all six people `sub-01` through `sub-06`. Each `eeg` object contains
exactly `stimulus_id`, `run_number`, `trial_number`, `ch_names` and `times`.
Each optional `eye` object contains the same fields except `ch_names`.
Each of the three trial fields maps all eight `ses-01` through `ses-08` keys to
integer lists in source array row order. The source ranges are respectively
1–1102, 1–16 and 1–66. Supply all 127 ordered channel names and all 1800
stimulus-relative time points, in seconds, from −0.100 to 3.498 at 500 Hz.
Do not include `args`, `ncsnr`, `noise_ceiling` or recording arrays.

```sh
python3 -I -B trial_roster.py \
  --metadata /operator/private/primitive-metadata.json \
  --output /operator/private/full-eeg-trial-roster.json
```

The output must be fresh and is created with mode 0600. Keep it outside Git and
outside participant mounts: it contains original video/trial correspondences.
The CLI prints only the output byte count/hash, session count and absence of
signal reads. It rejects duplicate JSON keys, nonfinite numbers, unselected
metadata fields, missing/duplicate people or sessions, duplicate trial keys,
inconsistent trial columns, changed channel/time order, conflicting EEG/eye
video IDs, absent EEG video coverage and EEG sessions without fitting trials.
Eye metadata may be absent or have empty sessions; this produces explicit
missing covariates without narrowing the EEG endpoint.

## Output use

The 48 ordered `sessions` records contain the source-order `trial_video_ids`,
zero-based `train_rows`/`query_rows`, an EEG-only `trial_roster_pin`, and
`source_rows` with optional `eye_row` indices. Use `train_rows` and `query_rows`
to select the corresponding source recording rows; never sort the recording
by video or substitute the paired-eye subset. `eye_only_rows` and
`unpaired_eeg_rows` explicitly account for independent rejection.

For the existing `PreparationProducer` / `RecordingReader`, the operator can
bind `person`, `session`, `trial_video_ids` and `trial_roster_pin` into the
session and array descriptors. The roster pin hashes compact ASCII JSON with
sorted keys and no trailing newline for `{person, session, rows}`, where each
row includes `row`, `video_id`, `run` and `trial`. It excludes optional eye
covariates, so an eye rejection cannot change the target roster identity.
The source HDF5 descriptor, actual shape/dtype, channel/time pins, schema
admission and complete study provenance still require separate authentication.
This program does not fabricate those bindings or claim to launch that runtime.

Per-person counts include every video, the full EEG support and optional paired
eye support. Complete EEG coverage is enforced independently for each of the
six people. Query identity metadata is not a held neural response; it remains
operator-private because it could reveal private mismatch correspondences if
carelessly combined with runtime aliases.

## Evidence and limits

The author code is pinned in the preserved package at EMD commit
`a7408c8be3e015770dd986628dbc3f0ed499def3`. `preprocess.py` stores the three
trial columns with each session array, and `eeg_utils.py` derives them after
trial rejection. The cached source derivative READMEs specify the ranges and
exact EEG/eye join; `SOURCE_PINS.json` records the inspected bodies. The
127×1800 basis and full six-person/eight-session scope follow the current
NEURAL-079 contract and `n079_plan.py`.

Generated controls exercise reordered eye rows, repeated video presentations,
asymmetric rejection, absent/empty eye support, person-specific full coverage,
identity conflicts, malformed inputs and CLI byte pinning/no overwrite. They
are software evidence only. No authentic metadata or signal was processed in
this revision; no numerical preparation, model call, training, new solver
result or scientific qualification is established. Raw preprocessing defects,
target normalization, actual derivative authentication, clock alignment and
participant transport remain separate unresolved work.
