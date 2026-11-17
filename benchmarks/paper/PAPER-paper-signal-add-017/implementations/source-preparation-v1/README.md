# Original finger-EEG training input preparation

This component repairs an input incompatibility in the historical construction
path: original offline runs contain thumb, index, **middle**, and pinky labels
`1/2/3/4`. The historical `initial-evaluator-v1` accepts only binary or ternary
source runs, so an intact original offline run cannot pass its importer.
The author loader loads four-finger trials before selecting binary
`[1,4]` or ternary `[1,2,4]` targets. This implementation follows that order and
reports excluded original-class counts. The historical files remain unchanged.

`source_preparation.py` supplies executable, operator-side stages:

- `parse_member` checks retained-subject and ordinary offline/online run identity.
- `read_mat` requires a pinned original MAT file, checks dimension metadata,
  reads the documented structures and passes only raw EEG, rate and events to
  extraction. Recorded online predictions/probabilities are not decoder inputs.
- `extract_trials` verifies all original class counts and paired 1-based events,
  retains original trial identity, crops at five seconds and applies common
  average referencing. It rejects the documented S07 session-5 ternary Base
  missing-event family; it does not silently reduce a complete panel.
- `prepare_training` selects the author binary/ternary classes, checks
  participant/MI-versus-ME and chronological training/calibration access, then
  applies an explicitly supplied trial permutation and the author's 80/20
  training/validation partition. Validation indices follow the source
  `np.setdiff1d` ordering. All windows from one trial stay in one partition.
- `segment_trials` reproduces offset-major window ordering: 1,024 raw samples,
  stride 128, then original trial order at each offset. Incomplete padded windows
  are omitted while original trial and sample identities remain attached.
- `source_transform` Fourier-resamples each window to 100 samples, pads 100 zeros
  on both sides, applies a causal fourth-order Butterworth 4–40 Hz filter at
  100 Hz, removes padding and z-scores each channel within each window. Output
  shape is `windows × 128 channels × 100 samples × 1 kernel`.

Raw voltage units are unspecified in the inspected dictionary: no amplitude
conversion is introduced. Output is dimensionless channel/window z-score.
Source labels remain distinct from zero-based decoder labels: binary pinky
source label `4` becomes decoder label `1`; ternary index source label `2`
becomes decoder label `1`. There is no label inference from model outputs.

The API accepts already-authorized source files and an explicit original run
roster. A local SHA256 authenticates the supplied bytes, not their origin in a
public archive. Complete acquisition/member receipts remain required. Callers
must supply all source-selected runs and the exact author folder/file/event
order. The API checks order and eligible routes but cannot establish missing-run
or full-cohort completeness from a subset. Binary fine-tuning accepts both
same-day Base class families; source-complete admission must require all eight
runs from each family. Ternary fine-tuning accepts only the ternary Base family.
Smooth sessions are outside this implementation.

There is deliberately no inferred seed: the source uses an unseeded random
permutation. A saved original permutation or a separately declared reproduction
permutation is necessary. This 80/20 training split is **not** the paper's
five-fold offline evaluation split. No scoring, candidate success threshold,
paper panel, published performance or native EEGNet rerun is fabricated here.

## Verification

Python, NumPy and SciPy are required; the final generated check used Python
3.12.8, NumPy 2.2.6 and SciPy 1.15.3, with no dependency installation. Seven
controls passed, including the exact-author differential; final test peak RSS
was 454,492,160 bytes. These are generated-fixture resource observations only.
Generated checks exercise class-3 handling, exact
sample boundaries and CAR, independent offset ordering, disjoint trial splits,
route and malformed-event failures, original MAT structures, content-pin
failure, and invariance to recorded online outputs.

The optional `--author-source /path/to/Functions.py` check requires SHA256
`53dbd4f587673b562d3558fbf5f85307e0e78ed45a64a298c10d24ad8149a223`. It executes
the original MAT loader and exact `train_models` preprocessing prefix on small
generated files, stopping before the first EEGNet assignment. For binary and
ternary routes it compares every training/validation EEG value and label with
this implementation. TensorFlow/EEGNet is neither imported nor executed.
In the parallel build these checks must use the shared two-slot test pool.

## Source scope and remaining scientific requirements

The [paper](https://www.nature.com/articles/s41467-025-61064-x), especially
Methods “Offline tasks”, “Offline decoding”, “Training effects”, and Figure 6,
describes 21 retained BCI responders, both ME/MI, all offline finger combinations
and five-fold offline decoding. The [author source](https://github.com/bfinl/Finger-BCI-Decoding/blob/c3a51c374d85f7b01e33ec4e998cf007d7da7763/Functions.py)
supplies the training loader and preprocessing implemented here. Source hashes
and exact roles are recorded in `source-pins.json`.

This component has only generated-fixture qualification. No authentic recording
has been prepared here. Original complete panel/fold membership, figure-specific
decision rules and aggregation, matched EEGNet weights/training/environment,
baseline numerical outputs and candidate access/resource budgets remain
unqualified. The published online human-adapting control headline cannot be an
offline replay victory threshold. The 21-person retained cohort must not become
a one-subject or incomplete-run substitute; all relevant MI/ME and class
conditions need preservation when a source endpoint is bound.

Paper reproduction and paper improvement are separate first-class outcomes.
Neither outcome is established by this preparation component. Future delivery
must preserve separate reproduction/improvement scores and paired paper+data
versus paper+data+author-code conditions on the same original cases; the optional
author-source software differential is an operator check, not a participant
result in either condition.

Source-compatible preprocessing does not establish nuisance robustness. The
required no-neural, within-session trial-label permutation, temporal alignment,
and cue/eye/muscle controls still need the same authentic original panel. The
historical spectral controls remain prospective software controls and are not
an EEGNet baseline. No model training, inference, new participant experiment,
scientific improvement or current-SOTA claim is made. Native preprocessing RAM
and runtime on a full session remain unmeasured and require a frozen resource
protocol before execution.

Data retain CC BY-NC 4.0 terms. The official repository license is MIT, with
separate EEGModels notices. This component contains newly written preparation
code; no author implementation or data is vendored.
